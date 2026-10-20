"""Minimal OpenRouter chat-completions client using the Python standard library."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
OPENROUTER_REFERER = "https://github.com/Proksima-Centauri/Astro-Ai-Processor"
OPENROUTER_TITLE = "Astro AI Processor — Altair"


class OpenRouterError(RuntimeError):
    """A safe-to-display OpenRouter request error without credential material."""


def create_chat_completion(api_key: str, messages: list[dict], *, model: str = OPENROUTER_DEFAULT_MODEL,
                           max_tokens: int = 900, temperature: float = 0.2,
                           timeout: float = 120.0, opener=None) -> tuple[str, dict]:
    key = str(api_key or "").strip()
    if not key:
        raise OpenRouterError("Brak klucza OpenRouter. Dodaj go w Preferencje → AI Chat.")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")

    body = json.dumps({
        "model": str(model or OPENROUTER_DEFAULT_MODEL),
        "messages": messages,
        "max_tokens": int(max(1, max_tokens)),
        "temperature": float(max(0.0, min(1.2, temperature))),
        "top_p": 0.9,
        "stream": False,
    }).encode("utf-8")
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
            raise OpenRouterError("OpenRouter nie udzielił dostępu do bezpłatnego modelu (limit lub uprawnienia).") from None
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
