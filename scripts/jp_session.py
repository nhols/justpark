"""Load, renew and save the JustPark browser session.

The session lives either in a local JSON file or, for CI, in S3 sealed with
the public key below. Only the matching private key (JP_SESSION_KEY) can open
it, so S3 access alone does not expose the session.
"""

import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3
from nacl.public import PrivateKey, PublicKey, SealedBox

BASE = "https://www.justpark.com"
DASHBOARD = f"{BASE}/dashboard/bookings/received"
PUBLIC_KEY = "ZkOjQoUwxghcai004+wp3OUtaBPOoSDMp/YVr0bs13k="

# Renew a little before jp_access expires so a run never starts with a dying token.
RENEW_WITHIN = 24 * 60 * 60


def load(uri):
    if not uri.startswith("s3://"):
        return json.loads(Path(uri).read_text())
    parsed = urlparse(uri)
    sealed = boto3.client("s3").get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))["Body"].read()
    private_key = PrivateKey(base64.b64decode(os.environ["JP_SESSION_KEY"]))
    return json.loads(SealedBox(private_key).decrypt(sealed))


def save(uri, state):
    payload = json.dumps(state).encode()
    if not uri.startswith("s3://"):
        tmp = Path(uri + ".tmp")
        tmp.write_bytes(payload)
        tmp.replace(uri)
        return
    parsed = urlparse(uri)
    sealed = SealedBox(PublicKey(base64.b64decode(PUBLIC_KEY))).encrypt(payload)
    boto3.client("s3").put_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"), Body=sealed)


async def renew_if_needed(ctx, uri, state):
    """Let JustPark swap the refresh token for new tokens once jp_access is about to expire.

    The old tokens stop working as soon as new ones are issued, so they are saved
    before anything else happens.
    """
    jar = await ctx.cookies(BASE)
    before = {c["name"]: c["value"] for c in jar}
    access = next((c for c in jar if c["name"] == "jp_access"), None)
    if access and access["expires"] > time.time() + RENEW_WITHIN:
        return

    # Same as a browser after the cookie expires: only jp_refresh is sent.
    await ctx.clear_cookies(name="jp_access")
    resp = await ctx.request.get(DASHBOARD, headers={"accept": "text/html,application/xhtml+xml"})
    cookies = await ctx.cookies()
    after = {c["name"]: c["value"] for c in cookies}
    renewed = "jp_access" in after
    if renewed or after.get("jp_refresh") != before.get("jp_refresh"):
        save(uri, {"cookies": cookies, "origins": state.get("origins", [])})

    if not renewed or urlparse(resp.url).path.startswith("/auth/login"):
        print(
            "ERROR: JustPark did not renew the session. Log in with fetch_jp_state.py, "
            "then upload it with upload_jp_session.py.",
            file=sys.stderr,
        )
        sys.exit(3)

    print("Renewed JustPark session and saved it.")
