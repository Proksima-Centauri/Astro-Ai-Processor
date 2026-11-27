const DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free";
const MAX_BODY_BYTES = 64 * 1024;
const MAX_MESSAGES = 32;
const MAX_MESSAGE_CHARS = 16_000;
const MAX_TOTAL_CHARS = 48_000;
const REQUEST_TIMEOUT_MS = 90_000;
const MAX_GENERATION_TOKENS = 4096;
const EFFORTS = new Set(["low", "medium", "high"]);

function createUsageDiagnosticTransform() {
  let pending = "";
  let finishReason = null;
  let completionTokens = null;
  let reasoningTokens = null;
  const decoder = new TextDecoder();

  function readEvent(block) {
    const data = block.split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data || data === "[DONE]") return;
    try {
      const event = JSON.parse(data);
      const choice = event?.choices?.find?.((item) => item && item.finish_reason != null);
      if (choice) finishReason = String(choice.finish_reason).slice(0, 40);
      const usage = event?.usage;
      if (Number.isFinite(usage?.completion_tokens)) completionTokens = usage.completion_tokens;
      const reasoning = usage?.completion_tokens_details?.reasoning_tokens;
      if (Number.isFinite(reasoning)) reasoningTokens = reasoning;
    } catch {
      // Ignore incomplete or non-JSON SSE events; never log event contents.
    }
  }

  return new TransformStream({
    transform(chunk, controller) {
      pending += decoder.decode(chunk, { stream: true });
      pending = pending.replace(/\r\n/g, "\n");
      let boundary;
      while ((boundary = pending.indexOf("\n\n")) !== -1) {
        readEvent(pending.slice(0, boundary));
        pending = pending.slice(boundary + 2);
      }
      controller.enqueue(chunk);
    },
    flush() {
      pending += decoder.decode();
      if (pending) readEvent(pending);
      console.info("astro_ai_usage", JSON.stringify({
        finish_reason: finishReason,
        completion_tokens: completionTokens,
        reasoning_tokens: reasoningTokens,
        max_tokens: MAX_GENERATION_TOKENS,
      }));
    },
  });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" },
  });
}

function corsHeaders(request, env) {
  const origin = request.headers.get("Origin");
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((x) => x.trim()).filter(Boolean);
  const headers = { "access-control-allow-methods": "POST, OPTIONS", "access-control-allow-headers": "content-type", "access-control-max-age": "86400", "vary": "Origin" };
  if (origin && allowed.includes(origin)) headers["access-control-allow-origin"] = origin;
  return headers;
}

function errorResponse(request, env, message, status) {
  const headers = corsHeaders(request, env);
  headers["content-type"] = "application/json; charset=utf-8";
  headers["cache-control"] = "no-store";
  headers["x-content-type-options"] = "nosniff";
  return new Response(JSON.stringify({ error: { message } }), { status, headers });
}

function validate(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return "Request body must be a JSON object.";
  if (!Array.isArray(body.messages) || body.messages.length < 1 || body.messages.length > MAX_MESSAGES) return `messages must contain between 1 and ${MAX_MESSAGES} entries.`;
  if (!EFFORTS.has(body.reasoning_effort)) return "reasoning_effort must be low, medium, or high.";
  let total = 0;
  for (const message of body.messages) {
    if (!message || typeof message !== "object" || !["system", "user", "assistant"].includes(message.role) || typeof message.content !== "string") return "Each message must have an allowed role and text content.";
    if (!message.content.trim() || message.content.length > MAX_MESSAGE_CHARS) return `Each message must contain 1 to ${MAX_MESSAGE_CHARS} characters.`;
    total += message.content.length;
  }
  if (total > MAX_TOTAL_CHARS) return `Combined message text must not exceed ${MAX_TOTAL_CHARS} characters.`;
  if (!body.messages.some((message) => message.role === "user")) return "At least one user message is required.";
  return null;
}

async function readJsonLimited(request) {
  if (!request.body) throw new Error("invalid-json");
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY_BYTES) {
      await reader.cancel();
      throw new Error("too-large");
    }
    chunks.push(value);
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(body));
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(request, env) });
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") return json({ status: "ok" });
    if (request.method !== "POST" || url.pathname !== "/v1/chat/completions") return errorResponse(request, env, "Not found.", 404);
    const cors = corsHeaders(request, env);
    if (request.headers.has("Origin") && !cors["access-control-allow-origin"]) return errorResponse(request, env, "Origin is not allowed.", 403);
    if (!env.OPENROUTER_API_KEY || !env.RATE_LIMITER) return errorResponse(request, env, "AI service is not configured.", 503);
    try {
      const ip = request.headers.get("CF-Connecting-IP") || "unknown";
      const decision = await env.RATE_LIMITER.limit({ key: ip });
      if (!decision.success) return errorResponse(request, env, "Too many requests. Please try again shortly.", 429);
    } catch {
      return errorResponse(request, env, "AI service rate limiting is unavailable.", 503);
    }
    const declaredLength = Number(request.headers.get("content-length") || 0);
    if (declaredLength > MAX_BODY_BYTES) return errorResponse(request, env, "Request body is too large.", 413);
    let body;
    try {
      body = await readJsonLimited(request);
    } catch (error) {
      if (error.message === "too-large") return errorResponse(request, env, "Request body is too large.", 413);
      return errorResponse(request, env, "Request body must contain valid JSON.", 400);
    }
    const validationError = validate(body);
    if (validationError) return errorResponse(request, env, validationError, 400);
    const upstreamAbort = new AbortController();
    const timeout = setTimeout(() => upstreamAbort.abort("timeout"), REQUEST_TIMEOUT_MS);
    request.signal.addEventListener("abort", () => upstreamAbort.abort("client disconnected"), { once: true });
    try {
      const upstream = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        signal: upstreamAbort.signal,
        headers: { "authorization": `Bearer ${env.OPENROUTER_API_KEY}`, "content-type": "application/json", "http-referer": env.APP_URL || "https://github.com/Proksima-Centauri/DSOpus", "x-title": "DSOpus" },
        body: JSON.stringify({
          model: env.OPENROUTER_MODEL || DEFAULT_MODEL,
          messages: body.messages,
          reasoning: { effort: body.reasoning_effort },
          max_tokens: MAX_GENERATION_TOKENS,
          temperature: 0.2,
          stream: true,
          stream_options: { include_usage: true },
          provider: { allow_fallbacks: false, require_parameters: true },
        }),
      });
      if (!upstream.ok) {
        clearTimeout(timeout);
        let upstreamMessage = "The selected free model is unavailable or rejected the request.";
        try {
          const payload = await upstream.json();
          const raw = payload?.error?.message;
          if (typeof raw === "string" && raw.length < 300 && !raw.includes(env.OPENROUTER_API_KEY)) upstreamMessage = raw;
        } catch { /* Keep a safe generic message. */ }
        const status = upstream.status === 429 ? 429 : upstream.status === 401 || upstream.status === 403 ? 502 : upstream.status >= 500 ? 503 : 400;
        return errorResponse(request, env, upstreamMessage, status);
      }
      const headers = new Headers(cors);
      headers.set("content-type", "text/event-stream; charset=utf-8");
      headers.set("cache-control", "no-cache, no-transform");
      headers.set("x-accel-buffering", "no");
      headers.set("x-content-type-options", "nosniff");
      const diagnosticBody = upstream.body.pipeThrough(createUsageDiagnosticTransform());
      const reader = diagnosticBody.getReader();
      const stream = new ReadableStream({
        async pull(controller) {
          try {
            const item = await reader.read();
            if (item.done) {
              clearTimeout(timeout);
              controller.close();
            } else controller.enqueue(item.value);
          } catch {
            clearTimeout(timeout);
            controller.error(new Error("Upstream stream interrupted."));
          }
        },
        async cancel(reason) {
          upstreamAbort.abort("client disconnected");
          clearTimeout(timeout);
          await reader.cancel(reason).catch(() => {});
        },
      });
      return new Response(stream, { status: 200, headers });
    } catch (error) {
      clearTimeout(timeout);
      if (request.signal.aborted) return new Response(null, { status: 499, headers: cors });
      if (upstreamAbort.signal.aborted) return errorResponse(request, env, "The AI request timed out. Please try again.", 504);
      return errorResponse(request, env, "Could not reach the AI service. Please try again.", 502);
    }
  },
};

export { validate };
