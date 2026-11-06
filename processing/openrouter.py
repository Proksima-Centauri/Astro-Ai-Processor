"""Minimal OpenRouter chat-completions client using the Python standard library."""
from __future__ import annotations

import json
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
OPENROUTER_REFERER = "https://github.com/Proksima-Centauri/Astro-Ai-Processor"
# HTTP headers are encoded as Latin-1 by urllib/http.client; keep this ASCII.
OPENROUTER_TITLE = "Astro AI Processor - Altair"


class OpenRouterError(RuntimeError):
    """A safe-to-display OpenRouter request error without credential material."""


def create_chat_completion(api_key: str, messages: list[dict], *, model: str = OPENROUTER_DEFAULT_MODEL,
                           max_tokens: int = 900, temperature: float = 0.2,
                           timeout: float = 120.0, opener=None, stream: bool = False,
                           on_chunk: Callable[[str], None] | None = None) -> tuple[str, dict]:
    key = str(api_key or "").strip()
    if not key:
        raise OpenRouterError("Brak klucza OpenRouter. Dodaj go w Preferencje → AI Chat.")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")

    request_payload = {
        "model": str(model or OPENROUTER_DEFAULT_MODEL),
        "messages": messages,
        "max_tokens": int(max(1, max_tokens)),
        "temperature": float(max(0.0, min(1.2, temperature))),
        "top_p": 0.9,
        "stream": bool(stream),
    }
    if stream:
        request_payload["stream_options"] = {"include_usage": True}
    body = json.dumps(request_payload).encode("utf-8")
    request = Request(
        OPENROUTER_CHAT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": OPENROUTER_REFERER,
            "X-OpenRouter-Title": OPENROUTER_TITLE,
        },
        method="POST",
    )
    send = opener or urlopen
    try:
        with send(request, timeout=float(timeout)) as response:
            if stream:
                chunks = []
                usage = {}
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    event_data = line[5:].strip()
                    if event_data == "[DONE]":
                        break
                    try:
                        event = json.loads(event_data)
                    except json.JSONDecodeError as exc:
                        raise OpenRouterError("OpenRouter zwrócił niepoprawny fragment odpowiedzi.") from exc
                    if not isinstance(event, dict):
                        continue
                    if event.get("error"):
                        error_detail = str(event["error"].get("message") or "błąd strumienia")
                        if key in error_detail:
                            error_detail = error_detail.replace(key, "[REDACTED]")
                        raise OpenRouterError(f"OpenRouter zwrócił błąd strumienia: {error_detail[:400]}")
                    event_usage = event.get("usage")
                    if isinstance(event_usage, dict):
                        usage = event_usage
                    choices = event.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        chunks.append(content)
                        if on_chunk is not None:
                            on_chunk(content)
                text = "".join(chunks).strip()
                if not text:
                    raise OpenRouterError("Model OpenRouter nie zwrócił odpowiedzi tekstowej.")
                return text, usage
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(error_payload.get("error", {}).get("message") or "").strip()
        except Exception:
            detail = ""
        if key and key in detail:
            detail = detail.replace(key, "[REDACTED]")
        detail = detail[:400]
        if exc.code == 401:
            raise OpenRouterError("OpenRouter odrzucił klucz API. Sprawdź go w Preferencje → AI Chat.") from None
        if exc.code == 429:
            raise OpenRouterError("OpenRouter ograniczył liczbę żądań. Spróbuj ponownie za chwilę.") from None
        if exc.code in (402, 403):
            raise OpenRouterError("OpenRouter nie udzielił dostępu do modelu (sprawdź saldo, limity lub uprawnienia).") from None
        raise OpenRouterError(f"OpenRouter zwrócił błąd HTTP {exc.code}: {detail or 'brak szczegółów'}") from None
    except URLError as exc:
        raise OpenRouterError(f"Nie można połączyć się z OpenRouter: {exc.reason}") from None
    except TimeoutError:
        raise OpenRouterError("Przekroczono limit czasu odpowiedzi OpenRouter.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise OpenRouterError("OpenRouter zwrócił niepoprawną odpowiedź.") from None

    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise OpenRouterError("Model OpenRouter nie zwrócił odpowiedzi tekstowej.")
    text = str((choices[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise OpenRouterError("Model OpenRouter zwrócił pustą odpowiedź.")
    usage = payload.get("usage") if isinstance(payload, dict) else None
    return text, usage if isinstance(usage, dict) else {}
