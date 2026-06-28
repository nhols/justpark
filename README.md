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

## Deploy to Cloudflare

The production site uses Cloudflare Pages for the frontend, a Pages Function at
`/api/dashboard` for the data request, and a private R2 bucket containing
`dashboard.json`. Local Vite development continues to read
`web/public/dashboard.json`.

### Cloudflare resources

1. Create an R2 Standard bucket, for example `justpark-dashboard`, and leave its
   public development URL disabled.
2. Create a Pages project connected to this repository with:
   - production branch: `main`
   - root directory: `web`
   - build command: `npm run build`
   - output directory: `dist`
   - environment variable: `NODE_VERSION=22`
3. In the Pages project, add an R2 binding named `DASHBOARD_BUCKET` for the
   bucket and redeploy.
4. Create an R2 API token with object write access and add these repository
   settings in GitHub:
   - secret `CLOUDFLARE_API_TOKEN`
   - secret `CLOUDFLARE_ACCOUNT_ID`
   - variable `CLOUDFLARE_R2_BUCKET`

The existing email-triggered workflow fetches the raw data to S3 unchanged. It
then prepares `dashboard.json` and replaces the object in R2; data refreshes do
not require a Pages rebuild.

### Login

Protect both the production Pages hostname and preview deployments with a
Cloudflare Access application. Enable One-time PIN login and create an Allow
policy listing the two permitted email addresses explicitly. Do not allow the
One-time PIN login method without an email rule, since that would admit any
valid email address.

After a user enters the emailed PIN, Access saves a `CF_Authorization` cookie on
the protected hostname. The default session lasts 24 hours; set the Access
application and policy session duration to one week if weekly re-authentication
is preferred. Users can log out at `/cdn-cgi/access/logout`, and an administrator
can revoke application or individual sessions in Zero Trust.

Cloudflare setup references: [Pages Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/),
[R2 bindings](https://developers.cloudflare.com/pages/functions/bindings/),
[Pages Access setup](https://developers.cloudflare.com/pages/platform/known-issues/#enable-access-on-your-pagesdev-domain),
and [Access session management](https://developers.cloudflare.com/cloudflare-one/access-controls/access-settings/session-management/).
