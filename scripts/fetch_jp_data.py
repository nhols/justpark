# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "boto3",
#     "playwright",
# ]
# ///


import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import boto3
from playwright.async_api import TimeoutError as PWTimeout
from playwright.async_api import async_playwright

BASE = "https://www.justpark.com"
DASHBOARD_URL = f"{BASE}/dashboard/bookings/received"
API_URL = f"{BASE}/api/v5/bookings/received"

JP_EMAIL = os.getenv("JP_EMAIL", "neilholloway74@gmail.com")
JP_PASSWORD = os.getenv("JP_PASSWORD", "an4hYS1k@Hd#4&wT%dU")
JP_API_KEY = os.getenv("JP_API_KEY", "faa1fef5-d26e-4c15-b5a3-ee40ed174a13")
HEADLESS = os.getenv("JP_HEADLESS", "1") != "0"
JP_S3_BUCKET = os.getenv("JP_S3_BUCKET", "jp-bookings")
JP_S3_KEY = os.getenv("JP_S3_KEY", "bookings.json")

PER_PAGE = 150
MAX_PAGES = 100
INCLUDE = "driver_price,vehicle,driver,space_owner_earnings"

PROFILE_DIR = Path("./.jp_profile")
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

SCREENSHOT_DIR = Path("./debug_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def require_env(name):
    if not os.getenv(name):
        print(f"ERROR: missing env var {name}", file=sys.stderr)
        sys.exit(2)


for v in ("JP_EMAIL", "JP_PASSWORD", "JP_API_KEY"):
    require_env(v)

LOGIN_SELECTORS = [
    ('input[name="email"]', 'input[name="password"]', 'button[type="submit"]'),
    ('input[type="email"]', 'input[type="password"]', 'button[type="submit"]'),
    ("#email", "#password", 'button[type="submit"]'),
]


async def login_if_needed(page):
    # Go to dashboard; if redirected to login, fill form
    await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")

    # Handle cookie banner first
    cookie_selectors = [
        'button[data-testid="cookie-accept"]',
        'button[id*="cookie"]',
        'button[class*="cookie"]',
        'button:has-text("Accept")',
        'button:has-text("Accept all")',
        'button:has-text("OK")',
        '[data-cy="accept-cookies"]',
    ]

    for cookie_sel in cookie_selectors:
        try:
            if await page.locator(cookie_sel).count() > 0:
                await page.click(cookie_sel)
                await asyncio.sleep(1)
                break
        except Exception:
            continue

    # Look for "Login with email" button first
    login_email_selectors = [
        'button:has-text("Login with email")',
        'a:has-text("Login with email")',
        '[data-testid="login-email"]',
        'button[class*="email"]',
    ]

    for email_btn_sel in login_email_selectors:
        try:
            if await page.locator(email_btn_sel).count() > 0:
                await page.click(email_btn_sel)
                await page.wait_for_load_state("domcontentloaded")
                break
        except Exception:
            continue

    async def find_login():
        for e_sel, p_sel, s_sel in LOGIN_SELECTORS:
            if (
                await page.locator(e_sel).count()
                and await page.locator(p_sel).count()
                and await page.locator(s_sel).count()
            ):
                return e_sel, p_sel, s_sel
        return None

    sel = await find_login()
    if sel:
        e_sel, p_sel, s_sel = sel
        await page.fill(e_sel, JP_EMAIL)
        await page.fill(p_sel, JP_PASSWORD)
        await page.click(s_sel)
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except PWTimeout:
            pass

    # sanity check: we should not be on a login page now
    await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")

    # Check if we're still on a login form (more specific check)
    login_form_indicators = [
        'input[name="email"]',
        'input[type="email"]',
        'form[action*="login"]',
        'button:has-text("Login with email")',
        'button:has-text("Sign in")',
        '[data-testid="login"]',
    ]

    is_login_page = False
    for indicator in login_form_indicators:
        try:
            if await page.locator(indicator).count() > 0:
                # Double check it's visible and not just a hidden element
                if await page.locator(indicator).is_visible():
                    is_login_page = True
                    break
        except Exception:
            continue

    if is_login_page:
        # Take screenshot before failing
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = SCREENSHOT_DIR / f"login_failure_{timestamp}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"Login failed - screenshot saved to {screenshot_path}")
        await asyncio.sleep(5)
        raise RuntimeError("Login unsuccessful; still on login form. Check credentials or updated selectors.")


async def fetch_all(ctx):
    all_items = []
    page_no = 1
    headers = {
        "accept": "application/json, text/plain, */*",
        "jp-api-key": JP_API_KEY,
        "x-jp-device": "",
        "x-jp-partner": "",
    }

    while page_no <= MAX_PAGES:
        params = {"include": INCLUDE, "page": str(page_no), "per_page": str(PER_PAGE)}
        resp = await ctx.request.get(API_URL, headers=headers, params=params)
        if not resp.ok:
            body = await resp.text()
            raise RuntimeError(f"HTTP {resp.status} on page {page_no}: {body[:200]}")

        data = await resp.json()
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = next(
                (data[k] for k in ("data", "results", "bookings", "items") if isinstance(data.get(k), list)), []
            )
        else:
            items = []

        all_items.extend(items)

        link = resp.headers.get("link", "")
        has_next = bool(re.search(r'rel="?next"?', link, re.I)) or (len(items) == PER_PAGE)
        if not has_next:
            break

        page_no += 1
        await asyncio.sleep(0.25)

    return all_items


def write_s3_data(data):
    s3 = boto3.client("s3")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    s3.put_object(Bucket=os.getenv("JP_S3_BUCKET"), Key=os.getenv("JP_S3_KEY", "bookings.json"), Body=data)
    s3.put_object(Bucket=os.getenv("JP_S3_BUCKET"), Key=os.getenv("JP_S3_KEY", f"bookings_{timestamp}.json"), Body=data)


async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await ctx.new_page()

        try:
            await login_if_needed(page)
            items = await fetch_all(ctx)
            payload = {"fetchedAt": datetime.now().isoformat() + "Z", "total": len(items), "items": items}
            data = json.dumps(payload, indent=2)
            write_s3_data(data)
            print(f"Saved {len(items)} bookings")
        except Exception as e:
            # Take screenshot on any failure
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = SCREENSHOT_DIR / f"error_{timestamp}.png"
            try:
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"Error occurred - screenshot saved to {screenshot_path}")
            except Exception as screenshot_error:
                print(f"Failed to take screenshot: {screenshot_error}")
            raise e
        finally:
            await ctx.close()


if __name__ == "__main__":
    asyncio.run(main())
