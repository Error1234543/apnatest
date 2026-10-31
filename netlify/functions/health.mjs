export default async () => {
  const checks = {
    telegramConfigured: Boolean(process.env.TELEGRAM_BOT_TOKEN),
    telegramWebhookSecretConfigured: Boolean(process.env.TELEGRAM_WEBHOOK_SECRET),
    telegramAdminsConfigured: Boolean(process.env.TELEGRAM_ADMIN_IDS),
    supabaseConfigured: Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY)
  };

  return new Response(JSON.stringify({
    ok: true,
    service: "PrepGrid backend",
    configuration: checks
  }), {
    status: 200,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }
  });
};
