"""Streaming client for Astro AI's public Cloudflare Worker gateway."""
from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

OPENROUTER_DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free"
DEFAULT_BACKEND_URL = "https://astro-ai-api.jozefgrabowski-main.workers.dev"
MAX_MESSAGES = 32

_DIAGNOSTIC_LOGGER = logging.getLogger("astro_ai.backend_diagnostics")
_DIAGNOSTIC_LOGGER.setLevel(logging.INFO)
_DIAGNOSTIC_LOGGER.propagate = False
if not _DIAGNOSTIC_LOGGER.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("[Altair HTTP diagnostic] %(levelname)s %(message)s"))
    _DIAGNOSTIC_LOGGER.addHandler(_handler)


class OpenRouterError(RuntimeError):
    """Safe-to-display cloud gateway error."""


class OpenRouterConnectionError(OpenRouterError):
    """The cloud gateway could not be reached."""


def _safe_request_headers(request: Request) -> dict[str, str]:
    """Report urllib's explicit and automatically-added HTTP headers safely."""
    headers = {str(name).title(): str(value) for name, value in request.header_items()}
    parsed = urlsplit(request.full_url)
    headers.setdefault("Host", parsed.netloc)
    headers.setdefault("Connection", "close")
    headers.setdefault("Accept-Encoding", "identity")
    if request.data is not None:
        headers.setdefault("Content-Length", str(len(request.data)))
    for name in tuple(headers):
        if name.casefold() in {"authorization", "proxy-authorization", "cookie", "set-cookie"}:
            headers[name] = "[REDACTED]"
    return dict(sorted(headers.items(), key=lambda pair: pair[0].casefold()))


def _extract_delta_content(delta: dict) -> str:
    """Return user-visible text only; never read reasoning fields."""
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict)
            and part.get("type") in {"text", "output_text"}
            and isinstance(part.get("text"), str)
        )
    return ""


def resolve_backend_url(configured_url: str | None = None, environ=None) -> str:
    """Prefer the developer override, then a saved URL, then production."""
    environment = os.environ if environ is None else environ
    return str(environment.get("ASTRO_AI_BACKEND_URL") or configured_url or DEFAULT_BACKEND_URL).strip().rstrip("/")


def create_chat_completion(messages: list[dict], *, reasoning_effort: str = "medium",
                           timeout: float = 100.0, opener=None, stream: bool = True,
                           on_chunk: Callable[[str], None] | None = None,
                           backend_url: str | None = None) -> tuple[str, dict]:
    if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES:
        raise ValueError(f"messages must contain between 1 and {MAX_MESSAGES} entries")
    effort = str(reasoning_effort or "medium").lower()
    if effort not in {"low", "medium", "high"}:
        raise ValueError("reasoning_effort must be low, medium, or high")
    base = resolve_backend_url(backend_url)
    if not base.startswith("https://") and not base.startswith("http://127.0.0.1") and not base.startswith("http://localhost"):
        raise OpenRouterError("Set the Astro AI Worker URL in Preferences → AI Chat, or set ASTRO_AI_BACKEND_URL.")
    payload = json.dumps({"messages": messages, "reasoning_effort": effort, "stream": bool(stream)}).encode("utf-8")
    request = Request(base + "/v1/chat/completions", data=payload,
                      headers={
                          "Content-Type": "application/json",
                          "Accept": "text/event-stream",
                          "User-Agent": "Astro-AI-Processor",
                      }, method="POST")
    request_url = request.full_url
    _DIAGNOSTIC_LOGGER.info(
        "request method=%s url=%s headers=%s origin_present=%s",
        request.get_method(), request_url, _safe_request_headers(request), request.has_header("Origin"),
    )
    send = opener or urlopen
    sse_event_count = 0
    reasoning_only_event_count = 0
    finish_reason = None
    try:
        with send(request, timeout=float(timeout)) as response:
            response_status = response.getcode() if hasattr(response, "getcode") else "unknown"
            response_url = response.geturl() if hasattr(response, "geturl") else request_url
            _DIAGNOSTIC_LOGGER.info(
                "response source=urllib status=%s request_url=%s final_url=%s",
                response_status, request_url, response_url,
            )
            chunks, usage = [], {}
            if not stream:
                result = json.loads(response.read().decode("utf-8"))
                text = str(result.get("choices", [{}])[0].get("message", {}).get("content") or "")
                return text, result.get("usage") or {}
            completed = False
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    completed = True
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                sse_event_count += 1
                if isinstance(event.get("error"), dict):
                    raise OpenRouterError(str(event["error"].get("message") or "The AI service returned a stream error."))
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                choices = event.get("choices") or []
                for choice in choices if isinstance(choices, list) else []:
                    if not isinstance(choice, dict):
                        continue
                    if choice.get("finish_reason") is not None:
                        finish_reason = choice["finish_reason"]
                    delta = choice.get("delta") or {}
                    if not isinstance(delta, dict):
                        continue
                    text = _extract_delta_content(delta)
                    if text:
                        chunks.append(text)
                        if on_chunk:
                            on_chunk(text)
                    elif delta.get("reasoning") or delta.get("reasoning_details"):
                        # Count reasoning-only events for diagnostics; never expose their text.
                        reasoning_only_event_count += 1
            if not completed:
                raise OpenRouterError("The AI response stream ended before completion. Please retry.")
            result = "".join(chunks).strip()
            if not result:
                raise OpenRouterError(
                    "The model completed without user-visible content "
                    f"(finish_reason={finish_reason or 'unknown'}). "
                    "Try a lower reasoning effort or a shorter prompt."
                )
            return result, usage
    except HTTPError as exc:
        raw_error_body = exc.read()
        error_body = raw_error_body.decode("utf-8", errors="replace")
        _DIAGNOSTIC_LOGGER.error(
            "response source=urllib.HTTPError method=%s request_url=%s error_url=%s status=%s reason=%r request_headers=%s error_body=%s",
            request.get_method(), request_url, getattr(exc, "url", request_url), exc.code, exc.reason,
            _safe_request_headers(request), error_body,
        )
        try:
            data = json.loads(error_body)
            detail = str(data.get("error", {}).get("message") or "")[:300]
        except Exception:
            detail = ""
        if exc.code == 429:
            raise OpenRouterError("Too many requests. Please try again shortly.") from None
        if exc.code == 504:
            raise OpenRouterError("The AI request timed out. Please try again.") from None
        if exc.code == 408 or exc.code == 524:
            raise OpenRouterError("The AI request timed out. Please try again.") from None
        if exc.code >= 500:
            raise OpenRouterError(detail or "The AI service is temporarily unavailable.") from None
        raise OpenRouterError(detail or f"The AI service rejected the request (HTTP {exc.code}).") from None
    except OpenRouterError as exc:
        _DIAGNOSTIC_LOGGER.error(
            "response source=application status=%s url=%s error=%s sse_events=%s reasoning_only_events=%s finish_reason=%s",
            locals().get("response_status", "unknown"), request_url, exc,
            sse_event_count, reasoning_only_event_count, finish_reason or "unknown",
        )
        raise
    except TimeoutError as exc:
        _DIAGNOSTIC_LOGGER.error("request source=urllib timeout url=%s error=%r", request_url, exc)
        raise OpenRouterConnectionError("The AI request timed out. Please try again.") from None
    except URLError as exc:
        _DIAGNOSTIC_LOGGER.error("request source=urllib.URLError url=%s reason=%r", request_url, exc.reason)
        if isinstance(getattr(exc, "reason", None), TimeoutError):
            raise OpenRouterConnectionError("The AI request timed out. Please try again.") from None
        raise OpenRouterConnectionError("Could not reach Astro AI's cloud service. Check your internet connection and try again.") from None
    except OSError as exc:
        _DIAGNOSTIC_LOGGER.error("request source=urllib.OSError url=%s error=%r", request_url, exc)
        raise OpenRouterConnectionError("Could not reach Astro AI's cloud service. Check your internet connection and try again.") from None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        _DIAGNOSTIC_LOGGER.error(
            "response source=application status=%s url=%s parse_error=%r",
            locals().get("response_status", "unknown"), request_url, exc,
        )
        raise OpenRouterError("Astro AI's cloud service returned an invalid response.") from None
