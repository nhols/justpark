type R2ObjectBody = {
  body: ReadableStream;
  httpEtag: string;
  writeHttpMetadata(headers: Headers): void;
};

type Env = {
  DASHBOARD_BUCKET: {
    get(key: string): Promise<R2ObjectBody | null>;
  };
};

const MONTH_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;

export async function onRequestGet({ request, env }: { request: Request; env: Env }) {
  const month = new URL(request.url).searchParams.get("month") ?? "";
  if (!MONTH_PATTERN.test(month)) {
    return Response.json({ error: "month must use YYYY-MM" }, { status: 400 });
  }

  const object = await env.DASHBOARD_BUCKET.get(`parking-observations/v1/${month}.json`);
  if (!object) {
    return Response.json({ schemaVersion: 1, month, generatedAt: new Date().toISOString(), observations: [] }, {
      headers: { "Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff" },
    });
  }

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Cache-Control", "private, no-store");
  headers.set("ETag", object.httpEtag);
  headers.set("X-Content-Type-Options", "nosniff");
  return new Response(object.body, { headers });
}
