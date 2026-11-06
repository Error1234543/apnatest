const SUPABASE_URL = "https://zrjmflymsbukwvsyqrkl.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_mmO4XOewe9A6vS8mkxWg7Q_-fwpbHy5";
const COOKIE_NAME = "pg_access_token";
const PUBLIC_PATHS = new Set([
  "/login", "/login/", "/login/index.html",
  "/auth/callback", "/auth/callback/", "/auth/callback/index.html"
]);

function withSecurityHeaders(response, request) {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "SAMEORIGIN");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  headers.set("X-Permitted-Cross-Domain-Policies", "none");
  if (new URL(request.url).protocol === "https:") {
    headers.set("Strict-Transport-Security", "max-age=15552000");
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

function readCookie(request, name) {
  const header = request.headers.get("Cookie") || "";
  for (const item of header.split(";")) {
    const part = item.trim();
    if (part.startsWith(name + "=")) {
      try { return decodeURIComponent(part.slice(name.length + 1)); }
      catch { return ""; }
    }
  }
  return "";
}

function redirectToLogin(url, clearCookie = false) {
  const destination = new URL("/login/", url.origin);
  destination.searchParams.set("returnTo", url.pathname + url.search);
  const headers = new Headers({ Location: destination.toString(), "Cache-Control": "no-store" });
  if (clearCookie) headers.append("Set-Cookie", COOKIE_NAME + "=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax");
  return new Response(null, { status: 302, headers });
}

function isHtmlNavigation(request, url) {
  if (request.method !== "GET" && request.method !== "HEAD") return false;
  if (PUBLIC_PATHS.has(url.pathname)) return false;
  if (url.pathname.startsWith("/.well-known/")) return false;
  const accept = request.headers.get("Accept") || "";
  return accept.includes("text/html") || url.pathname === "/" || url.pathname.endsWith(".html") || url.pathname.endsWith("/");
}

async function handleRequest({ request, next }) {
  const url = new URL(request.url);
  if (!isHtmlNavigation(request, url)) return next();

  const accessToken = readCookie(request, COOKIE_NAME);
  if (!accessToken) return redirectToLogin(url);

  let response;
  try {
    response = await fetch(SUPABASE_URL + "/auth/v1/user", {
      method: "GET",
      headers: {
        apikey: SUPABASE_ANON_KEY,
        Authorization: "Bearer " + accessToken
      }
    });
  } catch {
    return new Response("PrepGrid sign-in verification is temporarily unavailable. Please refresh in a moment.", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", "Retry-After": "15" }
    });
  }

  if (response.ok) {
    const page = await next();
    const headers = new Headers(page.headers);
    headers.set("Cache-Control", "private, no-store, max-age=0");
    headers.set("Vary", "Cookie");
    return new Response(page.body, { status: page.status, statusText: page.statusText, headers });
  }
  if (response.status === 401 || response.status === 403) return redirectToLogin(url, true);

  return new Response("PrepGrid sign-in verification is temporarily unavailable. Please refresh in a moment.", {
    status: 503,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", "Retry-After": "15" }
  });
}

export async function onRequest(context) {
  const response = await handleRequest(context);
  return withSecurityHeaders(response, context.request);
}
