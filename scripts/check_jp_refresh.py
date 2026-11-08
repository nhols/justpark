# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright",
# ]
# ///
"""Check that JustPark renews an expired session from its refresh token.

Run it against a throwaway login, never the session CI uses:

    JP_SESSION_STATE=session_state_test.json uv run scripts/fetch_jp_state.py
    JP_BROWSER_CHANNEL=chrome uv run scripts/check_jp_refresh.py session_state_test.json

It drops jp_access to simulate the cookie expiring, loads the bookings page once
and reports what changed. Set JP_API_KEY to also make one bookings API request
with the renewed token. Only cookie names, timestamps and status codes are printed.
"""

import asyncio
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

BASE = "https://www.justpark.com"
DASHBOARD = f"{BASE}/dashboard/bookings/received"
API = f"{BASE}/api/v5/bookings/received"
LIVE_STATE = Path("session_state.json").resolve()


def when(ts):
    if ts == -1:
        return "end of session"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def jwt_claims(token):
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def jp_cookies(cookies):
    return {c["name"]: c for c in cookies if c["name"].startswith("jp_")}


def describe(name, cookie):
    if cookie is None:
        return f"  {name}: missing"
    line = f"  {name}: cookie expires {when(cookie['expires'])}"
    if name == "jp_access":
        claims = jwt_claims(cookie["value"])
        line += f", token issued {when(claims['iat'])}"
    return line


async def main():
    path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "session_state_test.json"
    ).resolve()
    if not path.exists():
        sys.exit(
            f"{path} not found; create it with JP_SESSION_STATE={path.name} uv run scripts/fetch_jp_state.py"
        )
    state = json.loads(path.read_text())
    before = jp_cookies(state["cookies"])

    refresh = before.get("jp_refresh")
    if refresh is None:
        sys.exit(f"No jp_refresh cookie in {path}")
    live = (
        jp_cookies(json.loads(LIVE_STATE.read_text())["cookies"])
        if LIVE_STATE.exists()
        else {}
    )
    if (
        path == LIVE_STATE
        or live.get("jp_refresh", {}).get("value") == refresh["value"]
    ):
        sys.exit(
            "Refusing to run against the session CI uses; log in to a separate state file first."
        )

    print("Before:")
    for name in ("jp_access", "jp_refresh"):
        print(describe(name, before.get(name)))

    # Simulate day 31: the browser stops sending jp_access once its cookie expires.
    state["cookies"] = [c for c in state["cookies"] if c["name"] != "jp_access"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, channel=os.getenv("JP_BROWSER_CHANNEL")
        )
        ctx = await browser.new_context(storage_state=state)

        resp = await ctx.request.get(
            DASHBOARD, headers={"accept": "text/html,application/xhtml+xml"}
        )
        landed = urlparse(resp.url).path
        print(f"\nBookings page: HTTP {resp.status}, landed on {landed}")

        cookies = await ctx.cookies()
        after = jp_cookies(cookies)
        print("After:")
        for name in ("jp_access", "jp_refresh"):
            print(describe(name, after.get(name)))

        renewed = "jp_access" in after and not landed.startswith("/auth/login")
        rotated = (
            "jp_refresh" in after and after["jp_refresh"]["value"] != refresh["value"]
        )
        print(f"\nAccess token renewed: {'yes' if renewed else 'no'}")
        print(f"Refresh token replaced: {'yes' if rotated else 'no'}")

        if renewed and (api_key := os.getenv("JP_API_KEY")):
            api = await ctx.request.get(
                API,
                headers={
                    "accept": "application/json, text/plain, */*",
                    "jp-api-key": api_key,
                    "x-jp-device": "",
                    "x-jp-partner": "",
                },
                params={"page": "1", "per_page": "1"},
            )
            print(f"Bookings API with renewed token: HTTP {api.status}")
            renewed = api.ok

        if "jp_access" in after or rotated:
            # The old tokens may be revoked now, so keep the new ones.
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(
                json.dumps(
                    {"cookies": cookies, "origins": state.get("origins", [])}, indent=2
                )
            )
            tmp.replace(path)
            print(f"Saved renewed session → {path}")

        await browser.close()

    sys.exit(0 if renewed else 1)


if __name__ == "__main__":
    asyncio.run(main())
