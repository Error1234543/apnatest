const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store"
  }
});

async function sendTelegramMessage(chatId, text) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) throw new Error("Telegram token is not configured");

  const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      disable_web_page_preview: true
    })
  });

  if (!response.ok) throw new Error("Telegram sendMessage failed");
}

function getSupabaseConfig() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SECRET_KEY;
  if (!url || !key) throw new Error("Supabase is not configured");
  return { url: url.replace(/\/$/, ""), key };
}

async function supabaseGet(path, preferCount = false) {
  const { url, key } = getSupabaseConfig();
  const response = await fetch(`${url}/rest/v1/${path}`, {
    headers: {
      apikey: key,
      ...(preferCount ? { Prefer: "count=exact", Range: "0-0" } : {})
    }
  });

  if (!response.ok) throw new Error(`Supabase request failed: ${response.status}`);
  const data = await response.json();
  const range = response.headers.get("content-range") || "";
  const count = range.includes("/") ? Number(range.split("/")[1]) : null;
  return { data, count: Number.isFinite(count) ? count : null };
}

async function handleCommand(command, chatId) {
  if (command === "/start" || command === "/help") {
    await sendTelegramMessage(
      chatId,
      "PrepGrid Admin Bot\n\nAvailable commands:\n/status - Backend and database status\n/dashboard - Website backend overview\n/courses - List saved courses\n/help - Show commands"
    );
    return;
  }

  if (command === "/status") {
    try {
      await supabaseGet("courses?select=id&limit=1");
      await sendTelegramMessage(
        chatId,
        "Backend: online\nSupabase: connected\nAdmin access: verified"
      );
    } catch {
      await sendTelegramMessage(
        chatId,
        "Backend: online\nSupabase: connection check failed. Check server configuration."
      );
    }
    return;
  }

  if (command === "/dashboard") {
    try {
      const [courses, published, settings, logs] = await Promise.all([
        supabaseGet("courses?select=id", true),
        supabaseGet("courses?select=id&is_published=eq.true", true),
        supabaseGet("site_settings?select=setting_key&limit=1", true),
        supabaseGet("admin_audit_logs?select=id&limit=1", true)
      ]);

      await sendTelegramMessage(
        chatId,
        [
          "PrepGrid Dashboard",
          "",
          `Total courses: ${courses.count ?? "Unavailable"}`,
          `Published courses: ${published.count ?? "Unavailable"}`,
          `Site settings: ${settings.count ?? "Unavailable"}`,
          `Admin log entries: ${logs.count ?? "Unavailable"}`,
          "",
          "Student accounts and paid content are not set up yet."
        ].join("\n")
      );
    } catch {
      await sendTelegramMessage(
        chatId,
        "Dashboard could not load. Check Supabase table access and backend logs."
      );
    }
    return;
  }

  if (command === "/courses") {
    try {
      const { data } = await supabaseGet(
        "courses?select=title,slug,is_published,sort_order&order=sort_order.asc&limit=15"
      );

      if (!data.length) {
        await sendTelegramMessage(
          chatId,
          "No courses have been added yet. Paid content is not required for this setup."
        );
        return;
      }

      const lines = data.map((course, index) =>
        `${index + 1}. ${course.title}\n   ${course.slug} | ${course.is_published ? "Published" : "Draft"}`
      );
      await sendTelegramMessage(
        chatId,
        `Courses (first ${data.length}):\n\n${lines.join("\n\n")}`
      );
    } catch {
      await sendTelegramMessage(
        chatId,
        "Could not load courses. Check Supabase table access and backend logs."
      );
    }
    return;
  }

  await sendTelegramMessage(
    chatId,
    "Unknown command. Use /help to see available commands."
  );
}

export default async (request) => {
  if (request.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

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
  const rawCommand = String(message?.text ?? "").trim().split(/\s+/)[0].toLowerCase();
  const command = rawCommand.split("@")[0];

  if (!chatId || !telegramUserId || !command.startsWith("/")) {
    return json({ ok: true });
  }

  const admins = (process.env.TELEGRAM_ADMIN_IDS || "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);

  if (!admins.includes(telegramUserId)) {
    await sendTelegramMessage(chatId, "Access denied.");
    return json({ ok: true });
  }

  try {
    await handleCommand(command, chatId);
  } catch {
    // Do not expose secrets, provider responses, or internal errors to Telegram users.
    return json({ error: "Command processing failed" }, 500);
  }

  return json({ ok: true });
};
