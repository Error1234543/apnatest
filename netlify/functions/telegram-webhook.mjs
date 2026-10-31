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

async function supabaseRequest(path, { method = "GET", body, count = false } = {}) {
  const { url, key } = getSupabaseConfig();
  const headers = { apikey: key, "content-type": "application/json" };
  if (count) {
    headers.Prefer = "count=exact";
    headers.Range = "0-0";
  }
  if (method === "POST") headers.Prefer = "return=representation";
  const response = await fetch(`${url}/rest/v1/${path}`, {
    method,
    headers,
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  });
  if (!response.ok) throw new Error(`Supabase request failed: ${response.status}`);
  const text = await response.text();
  const data = text ? JSON.parse(text) : [];
  const range = response.headers.get("content-range") || "";
  const total = range.includes("/") ? Number(range.split("/")[1]) : null;
  return { data, count: Number.isFinite(total) ? total : null };
}

const supabaseGet = (path, count = false) =>
  supabaseRequest(path, { count });

async function auditAction(telegramUserId, action, targetId, metadata = {}) {
  await supabaseRequest("admin_audit_logs", {
    method: "POST",
    body: {
      telegram_user_id: Number(telegramUserId),
      action,
      target_type: "course",
      target_id: targetId,
      metadata
    }
  });
}

async function handleCommand(command, chatId, args, telegramUserId) {
  if (command === "/start" || command === "/help") {
    await sendTelegramMessage(
      chatId,
      "PrepGrid Admin Bot\n\n/status - Backend status\n/dashboard - Website overview\n/courses - List courses\n/addcourse slug | title | description - Add a draft course\n/publish slug - Publish a course\n/unpublish slug - Move course back to draft\n/help - Show commands"
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


  if (command === "/addcourse") {
    const parts = args.split("|").map((part) => part.trim());
    if (parts.length < 2 || !parts[0] || !parts[1]) {
      await sendTelegramMessage(chatId, "Format:\n/addcourse slug | Course title | Optional description\nExample:\n/addcourse cell-biology | Cell Biology | Class 11 Biology");
      return;
    }
    const [slug, title, description = ""] = parts;
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug) || slug.length > 80 || title.length > 120 || description.length > 1000) {
      await sendTelegramMessage(chatId, "Invalid details. Slug: lowercase letters, numbers and hyphens only. Title max 120 characters; description max 1000.");
      return;
    }
    try {
      await supabaseRequest("courses", {
        method: "POST",
        body: { slug, title, description: description || null, is_published: false }
      });
      await auditAction(telegramUserId, "course_created", slug, { title });
      await sendTelegramMessage(chatId, `Course added as DRAFT.\\nTitle: ${title}\\nSlug: ${slug}\\nUse /publish ${slug} when ready.`);
    } catch {
      await sendTelegramMessage(chatId, "Course was not added. The slug may already exist, or the database rejected the request. Check Supabase and try again.");
    }
    return;
  }

  if (command === "/publish" || command === "/unpublish") {
    const slug = args.trim();
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
      await sendTelegramMessage(chatId, `Format: ${command} course-slug\\nExample: ${command} cell-biology`);
      return;
    }
    try {
      const result = await supabaseRequest(`courses?slug=eq.${encodeURIComponent(slug)}`, {
        method: "PATCH",
        body: { is_published: command === "/publish", updated_at: new Date().toISOString() }
      });
      if (!result.data.length) {
        await sendTelegramMessage(chatId, "Course not found. Check the slug using /courses.");
        return;
      }
      await auditAction(telegramUserId, command === "/publish" ? "course_published" : "course_unpublished", slug);
      await sendTelegramMessage(chatId, `Course ${command === "/publish" ? "PUBLISHED" : "moved to DRAFT"}: ${slug}`);
    } catch {
      await sendTelegramMessage(chatId, "Course update failed. Check database permissions and try again.");
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
  const messageText = String(message?.text ?? "").trim();
  const commandParts = messageText.split(/\s+/);
  const rawCommand = (commandParts.shift() || "").toLowerCase();
  const command = rawCommand.split("@")[0];
  const args = messageText.slice(rawCommand.length).trim();

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
    await handleCommand(command, chatId, args, telegramUserId);
  } catch {
    // Do not expose secrets, provider responses, or internal errors to Telegram users.
    return json({ error: "Command processing failed" }, 500);
  }

  return json({ ok: true });
};
