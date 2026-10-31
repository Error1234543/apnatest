const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }
});

async function sendTelegramMessage(chatId, text) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) return;

  await fetch(\`https://api.telegram.org/bot\${token}/sendMessage\`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text })
  });
}

export default async (request) => {
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);

  const expectedSecret = process.env.TELEGRAM_WEBHOOK_SECRET;
  const receivedSecret = request.headers.get("x-telegram-bot-api-secret-token");
  if (!expectedSecret || !receivedSecret || receivedSecret !== expectedSecret) {
    return json({ error: "Unauthorized" }, 401);
  }

  const length = Number(request.headers.get("content-length") || 0);
  if (length > 65536) return json({ error: "Payload too large" }, 413);

  let update;
  try {
    update = await request.json();
  } catch {
    return json({ error: "Invalid JSON" }, 400);
  }

  const message = update?.message;
  const chatId = message?.chat?.id;
  const telegramUserId = String(message?.from?.id ?? "");
  const command = String(message?.text ?? "").trim().split(/\s+/)[0].toLowerCase();

  if (!chatId || !telegramUserId) return json({ ok: true });

  const admins = (process.env.TELEGRAM_ADMIN_IDS || "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);

  if (!admins.includes(telegramUserId)) {
    await sendTelegramMessage(chatId, "Access denied.");
    return json({ ok: true });
  }

  if (command === "/start") {
    await sendTelegramMessage(chatId, "PrepGrid backend is connected. Use /status to check services.");
    return json({ ok: true });
  }

  if (command === "/status") {
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

    if (!url || !key) {
      await sendTelegramMessage(chatId, "Supabase is not configured yet.");
      return json({ ok: true });
    }

    try {
      const response = await fetch(
        \`\${url.replace(/\/$/, "")}/rest/v1/courses?select=id&limit=1\`,
        {
          headers: {
            apikey: key,
            authorization: \`Bearer \${key}\`
          }
        }
      );

      await sendTelegramMessage(
        chatId,
        response.ok
          ? "Backend: online\nSupabase: connected\nAdmin access: verified"
          : "Backend: online\nSupabase: connection check failed. Check server configuration."
      );
    } catch {
      await sendTelegramMessage(chatId, "Backend: online\nSupabase: connection check failed.");
    }

    return json({ ok: true });
  }

  await sendTelegramMessage(chatId, "Unknown command. Available: /start, /status");
  return json({ ok: true });
};
