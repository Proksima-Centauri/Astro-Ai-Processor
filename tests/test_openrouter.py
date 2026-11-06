import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from processing.openrouter import (
    OPENROUTER_CHAT_URL,
    OPENROUTER_DEFAULT_MODEL,
    OpenRouterConnectionError,
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


class FakeStreamingResponse:
    def __init__(self, events):
        self.lines = [
            f"data: {json.dumps(event)}\n\n".encode()
            for event in events
        ] + [b"data: [DONE]\n\n"]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self.lines)


def test_openrouter_sends_nemotron_chat_request_and_returns_usage():
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
    assert observed["headers"]["X-openrouter-title"] == "Astro AI Processor - Altair"
    observed["headers"]["X-openrouter-title"].encode("ascii")
    assert OPENROUTER_DEFAULT_MODEL == "nvidia/nemotron-3-super-120b-a12b"
    assert observed["body"]["model"] == OPENROUTER_DEFAULT_MODEL
    assert observed["body"]["stream"] is False
    assert observed["body"]["messages"][1]["content"] == "hello"
    assert observed["timeout"] == 120.0


def test_openrouter_streams_altair_text_and_returns_usage():
    observed = {}
    chunks = []

    def opener(request, timeout):
        observed["body"] = json.loads(request.data)
        return FakeStreamingResponse([
            {"choices": [{"delta": {"content": "Cześć"}}]},
            {"choices": [{"delta": {"content": " Altair!"}}]},
            {"choices": [], "usage": {"total_tokens": 12}},
        ])

    response, usage = create_chat_completion(
        "secret-key",
        [{"role": "user", "content": "hello"}],
        opener=opener,
        stream=True,
        on_chunk=chunks.append,
    )

    assert response == "Cześć Altair!"
    assert chunks == ["Cześć", " Altair!"]
    assert usage == {"total_tokens": 12}
    assert observed["body"]["stream"] is True
    assert observed["body"]["stream_options"] == {"include_usage": True}


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


def test_openrouter_reports_connection_failures_without_raw_dns_details():
    def offline(_request, timeout):
        raise URLError(OSError(-3, "Temporary failure in name resolution"))

    with pytest.raises(OpenRouterConnectionError, match="Brak połączenia z internetem"):
        create_chat_completion(
            "test-key",
            [{"role": "user", "content": "hello"}],
            opener=offline,
        )


def test_altair_uses_only_the_openrouter_worker():
    worker = APP.AltairAIWorker("test", {}, api_key="key")
    assert worker.api_key == "key"


def test_openrouter_worker_passes_altair_system_prompt_and_context(monkeypatch):
    received = {}
    def fake_completion(key, messages, **options):
        received.update(key=key, messages=messages, options=options)
        options["on_chunk"]("Altair ")
        options["on_chunk"]("online")
        return "Altair online", {"total_tokens": 10}
    monkeypatch.setattr(APP, "create_chat_completion", fake_completion)
    worker = APP.AltairAIWorker("Co widzisz?", {"stars": 4}, api_key="test-key")
    emitted = []
    chunks = []
    worker.finished_signal.connect(lambda *values: emitted.append(values))
    worker.chunk_signal.connect(chunks.append)
    worker.run()
    assert chunks == ["Altair ", "online"]
    assert emitted[0][0] == "Altair online"
    assert emitted[0][1] == ""
    assert received["key"] == "test-key"
    assert received["messages"][0]["role"] == "system"
    assert "Co widzisz?" in received["messages"][1]["content"]
    assert '"stars":4' in received["messages"][1]["content"]
    assert received["options"]["model"] == OPENROUTER_DEFAULT_MODEL
    assert received["options"]["stream"] is True


def test_altair_welcome_switches_to_chat_after_first_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    app = APP.QApplication.instance() or APP.QApplication([])
    app_context = type("AppContext", (), {"language": "pl", "openrouter_api_key": ""})()
    panel = APP.AIAssistantPanel(app=app_context)
    panel.resize(900, 700)
    panel.show()
    app.processEvents()

    assert panel.conversation_stack.currentWidget() is panel.welcome_page
    assert panel.welcome_heading.text() == "Jak mogę pomóc?"
    heading_y = panel.welcome_heading.mapTo(panel, APP.QPoint(0, 0)).y()
    input_y = panel.input_text.mapTo(panel, APP.QPoint(0, 0)).y()
    assert heading_y < input_y
    assert panel.input_text.width() < panel.width()

    class SignalStub:
        def connect(self, _callback):
            pass

    started_workers = []

    class WorkerStub:
        def __init__(self, message, *_args, **_kwargs):
            self.message = message
            self.chunk_signal = SignalStub()
            self.finished_signal = SignalStub()

        def start(self):
            started_workers.append(self)

    monkeypatch.setattr(APP, "AltairAIWorker", WorkerStub)
    panel.get_context_payload = lambda: {}
    panel.input_text.setPlainText("Pomóż mi obrobić zdjęcie")
    panel.on_send_message()
    assert panel.conversation_stack.currentWidget() is panel.chat_page
    assert panel.current_chat_messages[0]["role"] == "User"
    assert panel.chat_history_combo.currentText() == "Pomóż mi obrobić zdjęcie"

    panel.on_ai_finished("", "", {"network_error": True})
    assert panel.stacked_layout.currentWidget() is panel.network_error_page
    assert panel.lbl_network_error.text() == "Brak połączenia z internetem"
    assert panel.network_error_page.styleSheet().find("background: #000000") >= 0
    assert panel.current_chat_messages == [{"role": "User", "content": "Pomóż mi obrobić zdjęcie"}]
    panel.btn_retry_connection.click()
    assert len(started_workers) == 2
    assert started_workers[-1].message == "Pomóż mi obrobić zdjęcie"
    assert len(panel.current_chat_messages) == 1
    assert panel.stacked_layout.currentWidget() is panel.content_widget
    panel._start_new_chat()
    assert panel.conversation_stack.currentWidget() is panel.welcome_page
    panel.close()
    app.processEvents()


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
