#!/usr/bin/env python3
import argparse
import json
import sys
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

import boto3

from src.dashboard import build_dashboard


@cache
def s3_client():
    session = boto3.Session()
    if session.get_credentials():
        return session.client("s3")
    raise SystemExit(
        "No AWS credentials found. Configure an AWS profile, AWS_ACCESS_KEY_ID and "
        "AWS_SECRET_ACCESS_KEY."
    )


def read(uri: str) -> bytes:
    if uri == "-":
        return sys.stdin.buffer.read()
    if not uri.startswith("s3://"):
        return Path(uri).read_bytes()
    parsed = urlparse(uri)
    return (
        s3_client()
        .get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))["Body"]
        .read()
    )


def write(uri: str, payload: bytes) -> None:
    if not uri.startswith("s3://"):
        path = Path(uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return
    parsed = urlparse(uri)
    s3_client().put_object(
        Bucket=parsed.netloc,
        Key=parsed.path.lstrip("/"),
        Body=payload,
        ContentType="application/json",
        CacheControl="no-store",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the compact dashboard payload from JustPark bookings"
    )
    parser.add_argument(
        "source", help="Local path or s3:// URI containing fetched bookings JSON"
    )
    parser.add_argument(
        "destination", help="Local path or s3:// URI for the dashboard JSON"
    )
    args = parser.parse_args()

    dashboard = build_dashboard(read(args.source))
    payload = json.dumps(dashboard, indent=2, ensure_ascii=False).encode()
    write(args.destination, payload)
    print(
        f"Prepared {dashboard['summary']['bookings']} bookings "
        f"for {dashboard['summary']['drivers']} drivers → {args.destination}"
    )


if __name__ == "__main__":
    main()
