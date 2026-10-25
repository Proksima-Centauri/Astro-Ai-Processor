import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

from processing.openrouter import (
    OPENROUTER_CHAT_URL,
    OPENROUTER_DEFAULT_MODEL,
    OpenRouterError,
    create_chat_completion,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("astro_openrouter_tests", ROOT / "Astro Ai Processor.py")
APP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = APP
SPEC.loader.exec_module(APP)


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def test_openrouter_sends_free_nemotron_chat_request_and_returns_usage():
    observed = {}
    def opener(request, timeout):
        observed["url"] = request.full_url
        observed["headers"] = request.headers
        observed["body"] = json.loads(request.data)
        observed["timeout"] = timeout
        return FakeResponse({"choices": [{"message": {"content": "Cześć!"}}], "usage": {"total_tokens": 22}})

    response, usage = create_chat_completion(
        "secret-key", [{"role": "system", "content": "system"}, {"role": "user", "content": "hello"}],
        opener=opener,
    )
    assert response == "Cześć!"
    assert usage == {"total_tokens": 22}
    assert observed["url"] == OPENROUTER_CHAT_URL
    assert observed["headers"]["Authorization"] == "Bearer secret-key"
    assert observed["headers"]["X-openrouter-title"] == "Astro AI Processor — Altair"
    assert observed["body"]["model"] == OPENROUTER_DEFAULT_MODEL
    assert observed["body"]["stream"] is False
    assert observed["body"]["messages"][1]["content"] == "hello"
    assert observed["timeout"] == 120.0


def test_openrouter_requires_key_and_never_echoes_it_on_auth_failure():
    with pytest.raises(OpenRouterError, match="Brak klucza"):
        create_chat_completion("", [{"role": "user", "content": "hi"}], opener=lambda *_a, **_k: None)

    secret = "secret-token-value"
    def unauthorized(_request, timeout):
        raise HTTPError(OPENROUTER_CHAT_URL, 401, "Unauthorized", {},
                        io.BytesIO(json.dumps({"error": {"message": f"invalid {secret}"}}).encode()))
    with pytest.raises(OpenRouterError) as error:
        create_chat_completion(secret, [{"role": "user", "content": "hi"}], opener=unauthorized)
    assert secret not in str(error.value)


def test_altair_uses_only_the_openrouter_worker():
    worker = APP.AltairAIWorker("test", {}, api_key="key")
    assert worker.api_key == "key"


def test_openrouter_worker_passes_altair_system_prompt_and_context(monkeypatch):
    received = {}
    def fake_completion(key, messages, **options):
        received.update(key=key, messages=messages, options=options)
        return "Altair online", {"total_tokens": 10}
    monkeypatch.setattr(APP, "create_chat_completion", fake_completion)
    worker = APP.AltairAIWorker("Co widzisz?", {"stars": 4}, api_key="test-key")
    emitted = []
    worker.finished_signal.connect(lambda *values: emitted.append(values))
    worker.run()
    assert emitted[0][0] == "Altair online"
    assert emitted[0][1] == ""
    assert received["key"] == "test-key"
    assert received["messages"][0]["role"] == "system"
    assert "Co widzisz?" in received["messages"][1]["content"]
    assert '"stars":4' in received["messages"][1]["content"]
    assert received["options"]["model"] == OPENROUTER_DEFAULT_MODEL


def test_openrouter_preferences_round_trip_in_user_config(tmp_path, monkeypatch):
    config_path = tmp_path / "user-config.json"
    monkeypatch.setattr(APP, "get_config_path", lambda: str(config_path))
    monkeypatch.setattr(APP, "get_project_config_path", lambda: str(tmp_path / "no-project-config"))
    monkeypatch.setattr(APP, "get_legacy_config_path", lambda: str(tmp_path / "no-legacy-config"))
    APP.save_config(openrouter_api_key="sk-test-private")
    config = json.loads(config_path.read_text())
    assert "local_ai_model_file" not in config
    assert "ai_provider" not in config
    assert config["openrouter_api_key"] == "sk-test-private"
    if os.name == "posix":
        assert config_path.stat().st_mode & 0o077 == 0


def test_existing_user_config_defaults_altair_to_openrouter(tmp_path, monkeypatch):
    config_path = tmp_path / "legacy-config.json"
    config_path.write_text(json.dumps({"local_ai_model_file": "old.gguf", "language": "pl"}))
    monkeypatch.setattr(APP, "get_config_path", lambda: str(config_path))
    monkeypatch.setattr(APP, "get_project_config_path", lambda: str(tmp_path / "missing-project-config"))
    monkeypatch.setattr(APP, "get_legacy_config_path", lambda: str(tmp_path / "missing-legacy-config"))
    config = APP.load_config()
    assert config["openrouter_api_key"] == ""
    assert "local_ai_model_file" not in config
    assert "ai_provider" not in config
