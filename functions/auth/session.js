const SUPABASE_URL = "https://zrjmflymsbukwvsyqrkl.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_mmO4XOewe9A6vS8mkxWg7Q_-fwpbHy5";
const COOKIE_NAME = "pg_access_token";

const json = (data, status = 200, extraHeaders = {}) => new Response(JSON.stringify(data), {
  status,
  headers: {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    ...extraHeaders
  }
});

export async function onRequestPost({ request }) {
  const origin = request.headers.get("Origin");
  if (origin && origin !== new URL(request.url).origin) {
    return json({ error: "Cross-origin request rejected" }, 403);
  }

  if (!(request.headers.get("Content-Type") || "").toLowerCase().startsWith("application/json")) {
    return json({ error: "Content-Type must be application/json" }, 415);
  }

  let body;
  try {
    const rawBody = await request.text();
    if (new TextEncoder().encode(rawBody).byteLength > 10000) {
      return json({ error: "Request too large" }, 413);
    }
    body = JSON.parse(rawBody);
  } catch {
    return json({ error: "Invalid request" }, 400);
  }

  if (body?.action === "logout") {
    return json({ ok: true }, 200, {
      "Set-Cookie": COOKIE_NAME + "=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
    });
  }

  const accessToken = typeof body?.access_token === "string" ? body.access_token : "";
  if (!accessToken || accessToken.length > 8192) return json({ error: "Missing or invalid session" }, 400);

  let verification;
  try {
    verification = await fetch(SUPABASE_URL + "/auth/v1/user", {
      method: "GET",
      headers: {
        apikey: SUPABASE_ANON_KEY,
        Authorization: "Bearer " + accessToken
      }
    });
  } catch {
    return json({ error: "Session verification unavailable" }, 503);
  }

  if (!verification.ok) return json({ error: "Session is not valid" }, 401);

  return json({ ok: true }, 200, {
    "Set-Cookie": COOKIE_NAME + "=" + encodeURIComponent(accessToken) + "; Path=/; Max-Age=3600; HttpOnly; Secure; SameSite=Lax"
  });
}
