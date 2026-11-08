# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "boto3",
#     "botocore[crt]",
#     "pynacl",
# ]
# ///
"""Seal a freshly saved session and upload it for CI.

    JP_SESSION_STATE=session_state.json uv run scripts/fetch_jp_state.py
    uv run scripts/upload_jp_session.py s3://<bucket>/session/jp_session.sealed

Only the public key is needed here; CI holds the private key.
"""

import json
import sys
from pathlib import Path

import jp_session


def main():
    if len(sys.argv) != 2 or not sys.argv[1].startswith("s3://"):
        sys.exit("usage: upload_jp_session.py s3://<bucket>/session/jp_session.sealed")
    state = json.loads(Path("session_state.json").read_text())
    if not any(c["name"] == "jp_refresh" for c in state["cookies"]):
        sys.exit("session_state.json has no jp_refresh cookie; log in again first")
    jp_session.save(sys.argv[1], state)
    print(f"✅ Uploaded sealed session → {sys.argv[1]}")


if __name__ == "__main__":
    main()
