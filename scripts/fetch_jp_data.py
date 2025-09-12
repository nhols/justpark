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
    print(f"Navigating to {DASHBOARD_URL}")
    await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")

    # In headless mode, wait a bit longer for dynamic content
    if HEADLESS:
        await asyncio.sleep(5)  # Extra wait for headless
        await page.wait_for_load_state("networkidle", timeout=15000)
    else:
        await asyncio.sleep(3)

    # Handle cookie banner first - try to reject all cookies
    cookie_banner_handled = False
    cookie_selectors = [
        # Specific selectors for JustPark cookie banner
        'button:has-text("Reject All")',
        'button:has-text("Reject all")',
        'button:has-text("reject all")',
        '[data-testid="cookie-reject-all"]',
        '[data-testid="cookie-reject"]',
        'button[class*="reject"]',
        'button[id*="reject"]',
        # Generic reject selectors
        'button:text-is("Reject All")',
        'button:text-is("Reject all")',
        # Privacy banner specific
        'div[class*="privacy"] button:has-text("Reject")',
        'div[class*="cookie"] button:has-text("Reject")',
        # Fallback to accept if reject not found
        'button:has-text("Accept All")',
        'button:has-text("Accept all")',
        'button:has-text("Accept")',
        'button[data-testid="cookie-accept"]',
        'button[id*="cookie"]',
        'button[class*="cookie"]',
        'button:has-text("OK")',
        '[data-cy="accept-cookies"]',
    ]

    # Wait longer for the cookie banner to appear in headless mode
    wait_time = 5 if HEADLESS else 3
    await asyncio.sleep(wait_time)

    for i, cookie_sel in enumerate(cookie_selectors):
        try:
            locator = page.locator(cookie_sel)
            if await locator.count() > 0:
                # Check if the button is visible
                if await locator.is_visible():
                    print(f"Found cookie banner button: {cookie_sel}")

                    # In headless mode, ensure element is ready and use more explicit clicking
                    if HEADLESS:
                        await locator.wait_for(state="visible", timeout=5000)
                        await locator.scroll_into_view_if_needed()
                        await asyncio.sleep(1)

                    await locator.click(force=HEADLESS)  # Force click in headless mode
                    await asyncio.sleep(4 if HEADLESS else 3)  # Give more time in headless
                    cookie_banner_handled = True
                    break
        except Exception as e:
            print(f"Failed to click cookie selector {cookie_sel}: {e}")
            continue

    if not cookie_banner_handled:
        print("No cookie banner found or handled")
        # Take a debug screenshot to see what's on the page
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = SCREENSHOT_DIR / f"no_cookie_banner_{timestamp}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"Debug screenshot saved to {screenshot_path}")
    else:
        print("Cookie banner handled successfully")

    # Look for "Login with email" button first - try more comprehensive approach
    login_email_button_found = False

    print("Looking for 'Login with email' button...")
    # Give more time in headless mode for dynamic content to load
    await asyncio.sleep(3 if HEADLESS else 2)

    # First, let's see all buttons and links on the page for debugging
    all_buttons = await page.locator("button").all()
    all_links = await page.locator("a").all()

    print(f"Found {len(all_buttons)} buttons and {len(all_links)} links on page")

    # Debug: print text content of visible buttons and links
    for i, btn in enumerate(all_buttons[:10]):  # Limit to first 10
        try:
            if await btn.is_visible():
                text = await btn.text_content()
                if text and ("login" in text.lower() or "email" in text.lower()):
                    print(f"Button {i}: '{text.strip()}'")
        except Exception:
            pass

    for i, link in enumerate(all_links[:10]):  # Limit to first 10
        try:
            if await link.is_visible():
                text = await link.text_content()
                if text and ("login" in text.lower() or "email" in text.lower()):
                    print(f"Link {i}: '{text.strip()}'")
        except Exception:
            pass

    # Now try comprehensive selectors
    login_email_selectors = [
        # Exact text matching
        'button:has-text("Login with email")',
        'a:has-text("Login with email")',
        'button:text-is("Login with email")',
        'a:text-is("Login with email")',
        # Case variations
        'button:has-text("login with email")',
        'button:has-text("Login With Email")',
        'a:has-text("login with email")',
        'a:has-text("Login With Email")',
        # Partial matches
        'button:has-text("email")',
        'a:has-text("email")',
        'button[class*="email"]',
        'a[class*="email"]',
        # Data attributes
        '[data-testid="login-email"]',
        '[data-cy="login-email"]',
        '[data-test="login-email"]',
        # Generic selectors that might work
        'button[type="button"]:has-text("email")',
        'div[role="button"]:has-text("email")',
        # Try finding by partial content
        '*:has-text("Login with email")',
        '*:has-text("email")',
    ]

    for email_btn_sel in login_email_selectors:
        try:
            locator = page.locator(email_btn_sel)
            count = await locator.count()
            if count > 0:
                print(f"Found {count} elements matching: {email_btn_sel}")
                # Get the first one that's visible
                for i in range(count):
                    element = locator.nth(i)
                    if await element.is_visible():
                        text = await element.text_content()
                        print(f"Element {i} text: '{text}' - attempting click")

                        # Enhanced clicking for headless mode
                        if HEADLESS:
                            await element.wait_for(state="visible", timeout=5000)
                            await element.scroll_into_view_if_needed()
                            await asyncio.sleep(1)

                        await element.click(force=HEADLESS)  # Force click in headless
                        await page.wait_for_load_state("domcontentloaded", timeout=15000)

                        # Extra wait in headless mode
                        if HEADLESS:
                            await asyncio.sleep(3)

                        login_email_button_found = True
                        break
                if login_email_button_found:
                    break
        except Exception as e:
            print(f"Failed to click login email selector {email_btn_sel}: {e}")
            continue

    if not login_email_button_found:
        print("Could not find 'Login with email' button")
        # Take a debug screenshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = SCREENSHOT_DIR / f"no_login_email_{timestamp}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"Debug screenshot saved to {screenshot_path}")

        # Also save page HTML for debugging
        html_path = SCREENSHOT_DIR / f"page_html_{timestamp}.html"
        content = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Page HTML saved to {html_path}")
    else:
        print("Successfully clicked 'Login with email' button")

    async def find_login():
        # Wait longer for login form to appear in headless mode
        wait_time = 4 if HEADLESS else 2
        await asyncio.sleep(wait_time)

        for e_sel, p_sel, s_sel in LOGIN_SELECTORS:
            e_count = await page.locator(e_sel).count()
            p_count = await page.locator(p_sel).count()
            s_count = await page.locator(s_sel).count()

            print(f"Checking login selectors - email: {e_count}, password: {p_count}, submit: {s_count}")

            if e_count > 0 and p_count > 0 and s_count > 0:
                # Also check if they are visible
                e_visible = await page.locator(e_sel).is_visible()
                p_visible = await page.locator(p_sel).is_visible()
                s_visible = await page.locator(s_sel).is_visible()

                print(f"Visibility - email: {e_visible}, password: {p_visible}, submit: {s_visible}")

                if e_visible and p_visible and s_visible:
                    return e_sel, p_sel, s_sel
        return None

    sel = await find_login()
    if sel:
        e_sel, p_sel, s_sel = sel
        print("Found login form - filling credentials...")

        # Enhanced form filling for headless mode
        email_locator = page.locator(e_sel)
        password_locator = page.locator(p_sel)
        submit_locator = page.locator(s_sel)

        if HEADLESS:
            # Ensure elements are ready
            await email_locator.wait_for(state="visible", timeout=10000)
            await password_locator.wait_for(state="visible", timeout=10000)
            await submit_locator.wait_for(state="visible", timeout=10000)

            # Clear any existing content
            await email_locator.clear()
            await password_locator.clear()
            await asyncio.sleep(1)

        await page.fill(e_sel, JP_EMAIL)
        await asyncio.sleep(0.5)  # Small delay between fills
        await page.fill(p_sel, JP_PASSWORD)
        await asyncio.sleep(1)  # Pause before submit

        print("Credentials filled, clicking submit...")

        if HEADLESS:
            await submit_locator.scroll_into_view_if_needed()
            await asyncio.sleep(1)

        await page.click(s_sel, force=HEADLESS)

        try:
            # Longer timeout for headless mode
            timeout = 30000 if HEADLESS else 20000
            await page.wait_for_load_state("networkidle", timeout=timeout)
        except PWTimeout:
            print("Timeout waiting for page load, continuing...")
            pass
    else:
        print("No login form found!")
        # Take debug screenshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = SCREENSHOT_DIR / f"no_login_form_{timestamp}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"Debug screenshot saved to {screenshot_path}")

    # sanity check: we should not be on a login page now
    print("Verifying login success...")
    await asyncio.sleep(3)  # Give time for any redirects
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
                    print(f"Still on login page - found: {indicator}")
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
    else:
        print("Login appears successful - no longer on login page")

        # Take screenshot of successful dashboard page
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = SCREENSHOT_DIR / f"dashboard_success_{timestamp}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"Dashboard screenshot saved to {screenshot_path}")

        # Also check for any obvious success indicators
        success_indicators = [
            'text="Dashboard"',
            'text="Bookings"',
            'text="Received"',
            '[data-testid="dashboard"]',
            ".dashboard",
            "nav",
            "header",
        ]

        found_indicators = []
        for indicator in success_indicators:
            try:
                count = await page.locator(indicator).count()
                if count > 0:
                    found_indicators.append(f"{indicator}({count})")
            except Exception:
                pass

        if found_indicators:
            print(f"Found dashboard indicators: {', '.join(found_indicators)}")
        else:
            print("Warning: No clear dashboard indicators found")


async def fetch_all(ctx):
    all_items = []
    page_no = 1
    headers = {
        "accept": "application/json, text/plain, */*",
        "jp-api-key": JP_API_KEY,
        "x-jp-device": "",
        "x-jp-partner": "",
    }

    print(f"Starting API requests to {API_URL}")
    print(f"Using API key: {JP_API_KEY[:8]}...")  # Only show first 8 chars for security

    while page_no <= MAX_PAGES:
        params = {"include": INCLUDE, "page": str(page_no), "per_page": str(PER_PAGE)}
        print(f"Requesting page {page_no} with params: {params}")

        resp = await ctx.request.get(API_URL, headers=headers, params=params)
        print(f"Response status: {resp.status}")
        print(f"Response headers: {dict(resp.headers)}")

        if not resp.ok:
            body = await resp.text()
            print(f"Error response body: {body}")

            if resp.status == 401:
                print("401 Unauthorized - this could mean:")
                print("1. Login session not established properly")
                print("2. Invalid or expired API key")
                print("3. Additional authentication required")
                print("4. Need to be on the dashboard page first to establish session")

                # Try getting cookies from the browser context
                cookies = await ctx.cookies()
                print(f"Current cookies: {len(cookies)} cookies found")
                for cookie in cookies[:5]:  # Show first 5 cookies
                    print(f"  {cookie['name']}: {cookie['value'][:20]}...")

                # Also check if we need to visit dashboard first
                print("Trying to visit dashboard page to establish session...")
                pages = ctx.pages
                if pages:
                    page = pages[0]
                    await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
                    await asyncio.sleep(2)
                    print("Visited dashboard, retrying API request...")

                    # Retry the request
                    resp = await ctx.request.get(API_URL, headers=headers, params=params)
                    print(f"Retry response status: {resp.status}")

                    if not resp.ok:
                        body = await resp.text()
                        print(f"Still failing after dashboard visit: {body[:200]}")

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

        print(f"Page {page_no}: Retrieved {len(items)} items")
        all_items.extend(items)

        link = resp.headers.get("link", "")
        has_next = bool(re.search(r'rel="?next"?', link, re.I)) or (len(items) == PER_PAGE)
        if not has_next:
            print(f"No more pages (got {len(items)} items, expected {PER_PAGE})")
            break

        page_no += 1
        await asyncio.sleep(0.25)

    print(f"Total items retrieved: {len(all_items)}")
    return all_items


def write_s3_data(data):
    s3 = boto3.client("s3")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    s3.put_object(Bucket=os.getenv("JP_S3_BUCKET"), Key=os.getenv("JP_S3_KEY", "bookings.json"), Body=data)
    s3.put_object(Bucket=os.getenv("JP_S3_BUCKET"), Key=os.getenv("JP_S3_KEY", f"bookings_{timestamp}.json"), Body=data)


async def main():
    async with async_playwright() as p:
        # Enhanced browser args for headless compatibility
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-plugins-discovery",
            "--disable-preconnect",
            "--disable-sync",
            "--no-sandbox",  # Often needed in headless environments
            "--disable-dev-shm-usage",  # Prevents crashes in limited memory environments
            "--disable-gpu",  # Reduces headless rendering issues
            "--disable-web-security",  # May help with some authentication flows
            "--disable-features=VizDisplayCompositor",  # Stability improvement
        ]

        # Additional settings for headless mode
        launch_options = {
            "user_data_dir": str(PROFILE_DIR),
            "headless": HEADLESS,
            "args": browser_args,
        }

        # In headless mode, add viewport and user agent to mimic real browser
        if HEADLESS:
            launch_options.update(
                {
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "java_script_enabled": True,
                    "ignore_https_errors": True,
                }
            )

        ctx = await p.chromium.launch_persistent_context(**launch_options)
        page = await ctx.new_page()

        # Additional headless-specific page settings
        if HEADLESS:
            # Add some headers that are often present in real browsers
            await page.set_extra_http_headers(
                {
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Cache-Control": "max-age=0",
                }
            )

        print(f"Browser launched in {'headless' if HEADLESS else 'headed'} mode")

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
