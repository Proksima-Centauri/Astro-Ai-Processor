import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

const env = {
  OPENROUTER_API_KEY: "test-only-key",
  RATE_LIMITER: { limit: async () => ({ success: true }) },
};

async function invokeWorker(sse) {
  const originalFetch = globalThis.fetch;
  const originalInfo = console.info;
  const logs = [];
  let upstreamRequest;
  globalThis.fetch = async (url, options) => {
    upstreamRequest = { url, options, body: JSON.parse(options.body) };
    return new Response(sse, {
      status: 200,
      headers: { "content-type": "text/event-stream" },
    });
  };
  console.info = (...args) => logs.push(args.join(" "));

  try {
    const request = new Request("https://worker.test/v1/chat/completions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        reasoning_effort: "low",
        messages: [{ role: "user", content: "short test prompt" }],
      }),
    });
    const response = await worker.fetch(request, env);
    const responseBody = await response.text();
    return { response, responseBody, upstreamRequest, logs: logs.join("\n") };
  } finally {
    globalThis.fetch = originalFetch;
    console.info = originalInfo;
  }
}

test("forwards the configured model, low effort, streaming, and 4096 token limit", async () => {
  const result = await invokeWorker("data: [DONE]\n\n");

  assert.equal(result.response.status, 200);
  assert.equal(result.upstreamRequest.url, "https://openrouter.ai/api/v1/chat/completions");
  assert.equal(result.upstreamRequest.body.model, "nvidia/nemotron-3.5-lightning:free");
  assert.equal(result.upstreamRequest.body.reasoning.effort, "low");
  assert.equal(result.upstreamRequest.body.max_tokens, 4096);
  assert.equal(result.upstreamRequest.body.stream, true);
  assert.deepEqual(result.upstreamRequest.body.stream_options, { include_usage: true });
  assert.equal(result.responseBody, "data: [DONE]\n\n");
});

test("logs safe usage diagnostics when the stream ends with finish_reason=length", async () => {
  const sse = [
    `data: ${JSON.stringify({ choices: [{ delta: { content: "visible answer", reasoning: "private reasoning" }, finish_reason: "length" }] })}`,
    `data: ${JSON.stringify({ choices: [], usage: { completion_tokens: 4096, completion_tokens_details: { reasoning_tokens: 3900 } } })}`,
    "data: [DONE]",
    "",
  ].join("\n\n");
  const result = await invokeWorker(sse);

  assert.equal(result.response.status, 200);
  assert.ok(result.responseBody.includes('"finish_reason":"length"'));
  assert.match(result.logs, /"finish_reason":"length"/);
  assert.match(result.logs, /"completion_tokens":4096/);
  assert.match(result.logs, /"reasoning_tokens":3900/);
  assert.match(result.logs, /"max_tokens":4096/);
  assert.doesNotMatch(result.logs, /private reasoning|visible answer|short test prompt/);
});
