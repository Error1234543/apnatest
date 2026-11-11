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
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

export async function onRequest({ request, next }) {
  // Public study pages and resources do not require a student login.
  // Individual tools enforce Google sign-in in their own application code.
  const response = await next();
  return withSecurityHeaders(response, request);
}
