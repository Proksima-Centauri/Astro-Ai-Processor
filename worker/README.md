# Astro AI Cloudflare Worker

This Worker is the only component that holds the OpenRouter credential. The desktop sends a bounded recent conversation and selected reasoning effort to this endpoint; the Worker fixes the model from backend configuration and streams OpenRouter SSE back to the client.

## Requirements and security boundaries

- Cloudflare account with Workers enabled, Wrangler (`npx wrangler`), and an OpenRouter account/key.
- Set `OPENROUTER_API_KEY` only with `wrangler secret put OPENROUTER_API_KEY`. It is not a Wrangler variable and must never be committed.
- The client cannot choose the model, temperature, token budget, or provider routing. The configured model is the free `nvidia/nemotron-3.5-lightning:free`; no paid fallback is requested. OpenRouter provider routing is restricted to providers that accept the parameters.
- The endpoint is anonymous. A desktop binary cannot securely carry a shared client secret, and CORS is not authentication. This Worker limits requests by Cloudflare's client IP rate limiter (20 requests/minute/IP), validates body shape and size, and applies a 90-second upstream timeout. Distributed clients, proxies, and bots can evade per-IP limits. For meaningful abuse prevention, add a user sign-in service and issue short-lived, server-verified user tokens with per-account quotas before broad public release. Never embed a service token in the app.
- The model page currently documents `reasoning.effort` and `low`, `medium`, `high` effort support, streaming Chat Completions, and a free endpoint. Free availability is not guaranteed. Errors are returned; the Worker never changes to a paid model. OpenRouter may internally route within that free model's provider set. NVIDIA's page warns that free endpoint traffic may be logged/used to improve NVIDIA products. Do not send confidential information or personal data.
- Messages are not persisted by this Worker. Data necessary for inference is sent upstream to OpenRouter/NVIDIA. Cloudflare request logs/metrics should not be configured to record request bodies.

## Configure and deploy

From this directory:

```sh
npx wrangler login
npx wrangler secret put OPENROUTER_API_KEY
npx wrangler deploy
```

The prompt asks for the secret interactively. Never put the key on a command line, in shell history, Wrangler vars, app settings, or source control. Wrangler config uses namespace ID `1001` as a placeholder; choose a unique integer for your account before deploy. You can adjust the limit there. The binding is Cloudflare's rate limiting binding; check plan availability and current Cloudflare pricing/limits for your account before deployment. It is approximate and applied per Cloudflare location. No Worker has been deployed by this change.

The desktop uses the production service URL by default. Developers can override it with `ASTRO_AI_BACKEND_URL=https://astro-ai-api.<your-subdomain>.workers.dev` or in the local application config; the URL is public configuration, not a secret. For local app + local Worker, set the override to `http://127.0.0.1:8787`.

## Local development

```sh
npx wrangler dev
```

For local development, create a private, ignored `worker/.dev.vars` file containing `OPENROUTER_API_KEY=...`; never commit that file. Local requests use the same validation, fixed model, and streaming path. The Worker fails closed if the rate-limit binding is unavailable, so use a local-only binding while developing if your Wrangler version does not provide it locally.

## Test requests

Health check:

```sh
curl -i http://127.0.0.1:8787/health
```

Streaming request:

```sh
curl -N http://127.0.0.1:8787/v1/chat/completions \
  -H 'content-type: application/json' \
  --data '{"reasoning_effort":"medium","messages":[{"role":"user","content":"Say hello."}]}'
```

Production URL replaces `http://127.0.0.1:8787`. Do not include the OpenRouter key in this request. A 429 indicates rate limiting; 503/502/504 responses identify unavailable upstream, gateway, or timeout conditions.

## Operations

Set a backend model only by changing `OPENROUTER_MODEL` in `wrangler.toml` and reviewing the selected model's pricing and parameter support first. Keep the `:free` slug to retain a no-token-cost model selection. Monitor Worker-level aggregate request/error counts and rate-limit events without recording request bodies, authorization headers, or prompts. Rotate the secret using `wrangler secret put OPENROUTER_API_KEY` and redeploy as required by Wrangler.
