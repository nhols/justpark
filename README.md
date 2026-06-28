# JustPark dashboard

A small private dashboard with a Python data compiler and a React frontend. The existing JustPark fetch workflow remains responsible for writing raw bookings to S3; `prepare_dashboard.py` turns that response into one display-ready JSON document.

## Prepare data

From a local export:

```sh
PYTHONPATH=. uv run scripts/prepare_dashboard.py bookings.json web/public/dashboard.json
```

Directly between S3 objects:

```sh
PYTHONPATH=. uv run scripts/prepare_dashboard.py \
  s3://my-bucket/bookings.json \
  s3://my-bucket/dashboard.json
```

The script uses the normal AWS environment/profile chain and supports any combination of local and S3 source/destination.

For a local demo with synthetic data:

```sh
uv run python -m tests.sample_data | \
  PYTHONPATH=. uv run scripts/prepare_dashboard.py - web/public/dashboard.json
```

## Run the frontend

```sh
cd web
npm install
npm run dev
```

The frontend reads `web/public/dashboard.json`. Generated dashboard data and local browser session state are ignored by Git.

## Check the project

```sh
UV_CACHE_DIR=/tmp/justpark-uv-cache uv run python -m unittest
UV_CACHE_DIR=/tmp/justpark-uv-cache uv run ruff check src/dashboard.py scripts/prepare_dashboard.py tests
npm --prefix web run build
```
