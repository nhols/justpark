# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright",
#     "boto3",
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
from playwright.async_api import async_playwright

BASE = "https://www.justpark.com"
API = f"{BASE}/api/v5/bookings/received"

# Required: path to saved storage_state and jp-api-key
STATE_PATH = Path(os.getenv("JP_SESSION_STATE", "session_state.json")).resolve()
JP_API_KEY = os.getenv("JP_API_KEY")

PER_PAGE = int(os.getenv("JP_PER_PAGE", "150"))
MAX_PAGES = int(os.getenv("JP_MAX_PAGES", "100"))
INCLUDE = os.getenv("JP_INCLUDE", "driver_price,vehicle,driver,space_owner_earnings")


def write_s3_data(data):
    s3 = boto3.client("s3")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    s3.put_object(Bucket=os.getenv("JP_S3_BUCKET"), Key=os.getenv("JP_S3_KEY", "bookings.json"), Body=data)
    s3.put_object(Bucket=os.getenv("JP_S3_BUCKET"), Key=f"bookings_{timestamp}.json", Body=data)


async def main():
    if not STATE_PATH.exists():
        print(f"ERROR: session state not found at {STATE_PATH}", file=sys.stderr)
        sys.exit(2)
    if not JP_API_KEY:
        print("ERROR: set JP_API_KEY (value from request header)", file=sys.stderr)
        sys.exit(2)

    async with async_playwright() as p:
        # Create a context that loads the saved cookies/localStorage
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(storage_state=str(STATE_PATH))

        all_items = []
        page_no = 1
        headers = {
            "accept": "application/json, text/plain, */*",
            "jp-api-key": JP_API_KEY,
            "x-jp-device": "",
            "x-jp-partner": "",
        }

        while page_no <= MAX_PAGES:
            params = {
                "include": INCLUDE,
                "page": str(page_no),
                "per_page": str(PER_PAGE),
            }
            resp = await ctx.request.get(API, headers=headers, params=params)
            if not resp.ok:
                body = await resp.text()
                raise RuntimeError(f"HTTP {resp.status} on page {page_no}: {body[:300]}")

            data = await resp.json()
            # common shapes
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for k in ("data", "results", "bookings", "items"):
                    if isinstance(data.get(k), list):
                        items = data[k]
                        break
                else:
                    items = []
            else:
                items = []

            all_items.extend(items)

            link = resp.headers.get("link", "")
            has_next = bool(re.search(r'rel="?next"?', link, re.I)) or (len(items) == PER_PAGE)
            if not has_next:
                break

            page_no += 1
            await asyncio.sleep(0.25)

        payload = {
            "fetchedAt": datetime.utcnow().isoformat() + "Z",
            "total": len(all_items),
            "items": all_items,
        }
        data = json.dumps(payload, indent=2)
        write_s3_data(data)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
