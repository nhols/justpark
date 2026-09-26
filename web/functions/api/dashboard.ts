type DashboardObject = {
  body: ReadableStream;
  httpEtag: string;
  writeHttpMetadata(headers: Headers): void;
};

type Env = {
  DASHBOARD_BUCKET: {
    get(key: string): Promise<DashboardObject | null>;
    head(key: string): Promise<{ httpEtag: string } | null>;
  };
};

export async function onRequestGet({ env }: { env: Env }) {
  const object = await env.DASHBOARD_BUCKET.get("dashboard.json");
  if (!object) return new Response("Dashboard data is not available yet.", { status: 404 });

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Cache-Control", "private, no-store");
  headers.set("ETag", object.httpEtag);
  headers.set("X-Content-Type-Options", "nosniff");
  return new Response(object.body, { headers });
}

export async function onRequestHead({ env }: { env: Env }) {
  const object = await env.DASHBOARD_BUCKET.head("dashboard.json");
  if (!object) return new Response(null, { status: 404 });
  return new Response(null, { headers: { "Cache-Control": "private, no-store", ETag: object.httpEtag } });
}
