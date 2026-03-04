# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright",
#     "boto3",
# ]
# ///
import asyncio
import os
import re
import sys
from pathlib import Path

from playwright.async_api import Error as PWError
from playwright.async_api import TimeoutError as PWTimeout
from playwright.async_api import async_playwright

BASE = "https://www.justpark.com"
DASHBOARD = f"{BASE}/dashboard/bookings/received"

OUT = Path(os.getenv("JP_SESSION_STATE", "session_state.json")).resolve()

LOGIN_SELECTORS = [
    ('input[name="email"]', 'input[name="password"]', 'button[type="submit"]'),
    ('input[type="email"]', 'input[type="password"]', 'button[type="submit"]'),
    ("#email", "#password", 'button[type="submit"]'),
]


async def main():
    async with async_playwright() as p:
        # Non-headless so you can complete login/2FA.
        # Prefer real Chrome because some login pages render oddly in bundled Chromium.
        channel = os.getenv("JP_BROWSER_CHANNEL", "chrome")
        launch_kwargs = {
            "headless": False,
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if channel:
            launch_kwargs["channel"] = channel

        try:
            browser = await p.chromium.launch(**launch_kwargs)
        except PWError:
            if channel and channel != "chromium":
                print(f"⚠️ Could not launch browser channel '{channel}', falling back to bundled Chromium.")
                launch_kwargs.pop("channel", None)
                browser = await p.chromium.launch(**launch_kwargs)
            else:
                raise

        # no_viewport=True lets the page use real window size (prevents click offset issues).
        ctx = await browser.new_context(no_viewport=True)
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await ctx.new_page()

        # Go to dashboard (may redirect to login)
        await page.goto(DASHBOARD, wait_until="domcontentloaded")

        # If login form is present, fill (only if you set env vars)
        email = os.getenv("JP_EMAIL")
        password = os.getenv("JP_PASSWORD")

        if email and password:
            for e_sel, p_sel, s_sel in LOGIN_SELECTORS:
                if (
                    await page.locator(e_sel).count()
                    and await page.locator(p_sel).count()
                    and await page.locator(s_sel).count()
                ):
                    await page.fill(e_sel, email)
                    await page.fill(p_sel, password)
                    await page.click(s_sel)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=20000)
                    except PWTimeout:
                        pass
                    break

        print("👉 If prompted, finish login/2FA in the browser. When the bookings dashboard loads, press Enter here.")
        try:
            input()
        except KeyboardInterrupt:
            pass

        # Save storage state (cookies + localStorage)
        await ctx.storage_state(path=str(OUT))
        print(f"✅ Saved session state → {OUT}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
