import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLIENT_SPEC = importlib.util.spec_from_file_location("astro_openrouter_client_tests", ROOT / "processing" / "openrouter.py")
CLIENT = importlib.util.module_from_spec(CLIENT_SPEC)
CLIENT_SPEC.loader.exec_module(CLIENT)

DEFAULT_BACKEND_URL = CLIENT.DEFAULT_BACKEND_URL
OPENROUTER_DEFAULT_MODEL = CLIENT.OPENROUTER_DEFAULT_MODEL
OpenRouterConnectionError = CLIENT.OpenRouterConnectionError
OpenRouterError = CLIENT.OpenRouterError
create_chat_completion = CLIENT.create_chat_completion
resolve_backend_url = CLIENT.resolve_backend_url


SPEC = importlib.util.spec_from_file_location("astro_openrouter_tests", ROOT / "Astro Ai Processor.py")
APP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = APP
try:
    SPEC.loader.exec_module(APP)
    APP_IMPORT_ERROR = ""
except ModuleNotFoundError as exc:
    APP = None
    APP_IMPORT_ERROR = str(exc)


class FakeStreamingResponse:
    def __init__(self, events, *, done=True):
        self.lines = [f"data: {json.dumps(event)}\n\n".encode() for event in events]
        if done:
            self.lines.append(b"data: [DONE]\n\n")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self.lines)


def test_production_backend_is_the_default_and_environment_overrides_it(monkeypatch):
    monkeypatch.delenv("ASTRO_AI_BACKEND_URL", raising=False)
    assert DEFAULT_BACKEND_URL == "https://astro-ai-api.jozefgrabowski-main.workers.dev"
    assert resolve_backend_url("") == DEFAULT_BACKEND_URL
    assert resolve_backend_url("https://saved.example") == "https://saved.example"
    monkeypatch.setenv("ASTRO_AI_BACKEND_URL", "http://127.0.0.1:8787/")
    assert resolve_backend_url("https://saved.example") == "http://127.0.0.1:8787"


def test_client_sends_messages_effort_and_stream_request_to_backend(monkeypatch):
    observed = {}

    def opener(request, timeout):
        observed["url"] = request.full_url
        observed["body"] = json.loads(request.data)
        observed["timeout"] = timeout
        return FakeStreamingResponse([{"choices": [{"delta": {"content": "Hello"}}]}])

    monkeypatch.delenv("ASTRO_AI_BACKEND_URL", raising=False)
    answer, _usage = create_chat_completion(
        [{"role": "user", "content": "hello"}],
        reasoning_effort="high", opener=opener, backend_url=DEFAULT_BACKEND_URL,
    )
    assert answer == "Hello"
    assert observed["url"] == DEFAULT_BACKEND_URL + "/v1/chat/completions"
    assert observed["body"] == {
        "messages": [{"role": "user", "content": "hello"}],
        "reasoning_effort": "high", "stream": True,
    }
    assert observed["timeout"] == 100.0
    assert OPENROUTER_DEFAULT_MODEL == "nvidia/nemotron-3.5-lightning:free"


def test_production_worker_request_has_no_origin_header_and_is_not_cors_blocked(monkeypatch):
    observed = {}

    def origin_sensitive_worker(request, timeout):
        observed["url"] = request.full_url
        observed["has_origin"] = request.has_header("Origin")
        if observed["has_origin"]:
            raise HTTPError(request.full_url, 403, "Origin is not allowed", {}, io.BytesIO(b"{}"))
        return FakeStreamingResponse([{"choices": [{"delta": {"content": "Worker response"}}]}])

    monkeypatch.delenv("ASTRO_AI_BACKEND_URL", raising=False)
    response, _usage = create_chat_completion(
        [{"role": "user", "content": "hello"}],
        backend_url=DEFAULT_BACKEND_URL,
        opener=origin_sensitive_worker,
    )

    assert observed["url"] == "https://astro-ai-api.jozefgrabowski-main.workers.dev/v1/chat/completions"
    assert observed["has_origin"] is False
    assert response == "Worker response"


def test_http_403_diagnostic_identifies_urllib_and_logs_full_error_body(monkeypatch):
    logs = []
    monkeypatch.setattr(
        CLIENT._DIAGNOSTIC_LOGGER,
        "info",
        lambda template, *args: logs.append(template % args),
    )
    monkeypatch.setattr(
        CLIENT._DIAGNOSTIC_LOGGER,
        "error",
        lambda template, *args: logs.append(template % args),
    )
    body = '{"error":{"message":"Origin is not allowed","detail":"full worker diagnostic"}}'

    def forbidden(request, timeout):
        raise HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(body.encode()))

    with pytest.raises(OpenRouterError, match="Origin is not allowed"):
        create_chat_completion(
            [{"role": "user", "content": "hello"}],
            backend_url=DEFAULT_BACKEND_URL,
            opener=forbidden,
        )

    combined = "\n".join(logs)
    assert "source=urllib.HTTPError" in combined
    assert "status=403" in combined
    assert "method=POST" in combined
    assert DEFAULT_BACKEND_URL + "/v1/chat/completions" in combined
    assert "Origin is not allowed" in combined
    assert "full worker diagnostic" in combined
    assert "origin_present=False" in combined
    assert "Content-Length" in combined
    assert "User-Agent" in combined
    assert "Authorization" not in combined


def test_client_streams_text_immediately_and_returns_usage():
    chunks = []

    def opener(_request, timeout):
        return FakeStreamingResponse([
            {"choices": [{"delta": {"content": "Cześć"}}]},
            {"choices": [{"delta": {"content": " Altair!"}}]},
            {"choices": [], "usage": {"total_tokens": 12}},
        ])

    response, usage = create_chat_completion(
        [{"role": "user", "content": "hello"}],
        opener=opener, backend_url=DEFAULT_BACKEND_URL, on_chunk=chunks.append,
    )
    assert response == "Cześć Altair!"
    assert chunks == ["Cześć", " Altair!"]
    assert usage == {"total_tokens": 12}


def test_production_sse_reasoning_only_events_then_content_only_is_displayed():
    """Matches the Worker's Chat Completions SSE shape; reasoning is redacted."""
    chunks = []
    stream_events = [
        {"choices": [{"delta": {
            "content": "", "role": "assistant", "reasoning": "[redacted]",
            "reasoning_details": [{"type": "reasoning.text", "text": "[redacted]", "format": "unknown", "index": 0}],
        }, "finish_reason": None}]},
        {"choices": [{"delta": {
            "content": "", "role": "assistant", "reasoning": "[redacted]",
            "reasoning_details": [{"type": "reasoning.text", "text": "[redacted]", "format": "unknown", "index": 0}],
        }, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "SSE_OK", "role": "assistant"}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "", "role": "assistant", "reasoning": None}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {
            "prompt_tokens": 22, "completion_tokens": 163, "total_tokens": 185,
            "completion_tokens_details": {"reasoning_tokens": 158},
        }},
    ]

    def opener(_request, timeout):
        return FakeStreamingResponse(stream_events)

    response, usage = create_chat_completion(
        [{"role": "user", "content": "Reply with exactly: SSE_OK"}],
        opener=opener, backend_url=DEFAULT_BACKEND_URL, on_chunk=chunks.append,
    )

    assert response == "SSE_OK"
    assert chunks == ["SSE_OK"]
    assert usage["completion_tokens_details"]["reasoning_tokens"] == 158


def test_content_text_blocks_are_streamed_without_reasoning_fields():
    chunks = []

    def opener(_request, timeout):
        return FakeStreamingResponse([
            {"choices": [{"delta": {
                "content": [
                    {"type": "text", "text": "Visible "},
                    {"type": "reasoning.text", "text": "[must not display]"},
                    {"type": "output_text", "text": "answer"},
                ],
                "reasoning": "[must not display]",
                "reasoning_details": [{"type": "reasoning.text", "text": "[must not display]"}],
            }}]},
        ])

    response, _usage = create_chat_completion(
        [{"role": "user", "content": "hello"}],
        opener=opener, backend_url=DEFAULT_BACKEND_URL, on_chunk=chunks.append,
    )
    assert response == "Visible answer"
    assert chunks == ["Visible answer"]


def test_reasoning_only_stream_ends_as_clear_no_user_visible_content_error():
    stream_events = [{"choices": [{"delta": {
        "content": "", "reasoning": "[must not display]",
        "reasoning_details": [{"type": "reasoning.text", "text": "[must not display]"}],
    }, "finish_reason": "length"}]}]

    def opener(_request, timeout):
        return FakeStreamingResponse(stream_events)

    with pytest.raises(OpenRouterError, match="without user-visible content.*finish_reason=length") as error:
        create_chat_completion(
            [{"role": "user", "content": "hello"}],
            opener=opener, backend_url=DEFAULT_BACKEND_URL,
        )
    assert "must not display" not in str(error.value)


def test_stream_ending_before_done_is_an_error_even_after_partial_text():
    chunks = []

    def opener(_request, timeout):
        return FakeStreamingResponse(
            [{"choices": [{"delta": {"content": "partial"}}]}], done=False,
        )

    with pytest.raises(OpenRouterError, match="ended before completion"):
        create_chat_completion(
            [{"role": "user", "content": "hello"}],
            opener=opener, backend_url=DEFAULT_BACKEND_URL, on_chunk=chunks.append,
        )
    assert chunks == ["partial"]


@pytest.mark.parametrize("status, message", [
    (429, "Too many requests"),
    (408, "timed out"),
    (504, "timed out"),
    (503, "upstream unavailable"),
])
def test_http_errors_are_reported_clearly(status, message):
    def fail(_request, timeout):
        raise HTTPError(
            DEFAULT_BACKEND_URL + "/v1/chat/completions", status, "failure", {},
            io.BytesIO(json.dumps({"error": {"message": "upstream unavailable"}}).encode()),
        )

    with pytest.raises(OpenRouterError, match=message):
        create_chat_completion(
            [{"role": "user", "content": "hello"}], opener=fail,
            backend_url=DEFAULT_BACKEND_URL,
        )


def test_connection_and_timeout_failures_are_distinguished():
    def offline(_request, timeout):
        raise URLError(OSError(-3, "Temporary failure in name resolution"))

    with pytest.raises(OpenRouterConnectionError, match="Could not reach Astro AI"):
        create_chat_completion(
            [{"role": "user", "content": "hello"}], opener=offline,
            backend_url=DEFAULT_BACKEND_URL,
        )

    def timeout(_request, timeout):
        raise TimeoutError

    with pytest.raises(OpenRouterConnectionError, match="timed out"):
        create_chat_completion(
            [{"role": "user", "content": "hello"}], opener=timeout,
            backend_url=DEFAULT_BACKEND_URL,
        )


@pytest.mark.skipif(APP is None, reason=f"Astro application dependencies unavailable: {APP_IMPORT_ERROR}")
def test_worker_sends_conversation_and_reasoning_without_credentials(monkeypatch):
    received = {}

    def fake_completion(messages, **options):
        received["messages"] = messages
        received["options"] = options
        options["on_chunk"]("Altair online")
        return "Altair online", {"total_tokens": 10}

    monkeypatch.setattr(APP, "create_chat_completion", fake_completion)
    worker = APP.AltairAIWorker(
        "What do you see?",
        {"stars": 4, "conversation": [{"role": "user", "content": "Previous question"}]},
        reasoning_effort="high", backend_url=DEFAULT_BACKEND_URL,
    )
    emitted, chunks = [], []
    worker.finished_signal.connect(lambda *values: emitted.append(values))
    worker.chunk_signal.connect(chunks.append)
    worker.run()

    assert chunks == ["Altair online"]
    assert emitted[0][0] == "Altair online"
    assert received["messages"][0]["role"] == "system"
    assert received["messages"][1] == {"role": "user", "content": "Previous question"}
    assert "What do you see?" in received["messages"][2]["content"]
    assert '"stars":4' in received["messages"][2]["content"]
    assert received["options"]["reasoning_effort"] == "high"
    assert received["options"]["backend_url"] == DEFAULT_BACKEND_URL
    assert not hasattr(worker, "api_key")


@pytest.mark.skipif(APP is None, reason=f"Astro application dependencies unavailable: {APP_IMPORT_ERROR}")
def test_existing_empty_backend_preference_migrates_to_production(tmp_path, monkeypatch):
    config_path = tmp_path / "user-config.json"
    config_path.write_text(json.dumps({"astro_ai_backend_url": "", "language": "en"}))
    monkeypatch.setattr(APP, "get_config_path", lambda: str(config_path))
    monkeypatch.setattr(APP, "get_project_config_path", lambda: str(tmp_path / "no-project-config"))
    monkeypatch.setattr(APP, "get_legacy_config_path", lambda: str(tmp_path / "no-legacy-config"))
    monkeypatch.delenv("ASTRO_AI_BACKEND_URL", raising=False)

    config = APP.load_config()
    assert config["astro_ai_backend_url"] == DEFAULT_BACKEND_URL


@pytest.mark.skipif(APP is None, reason=f"Astro application dependencies unavailable: {APP_IMPORT_ERROR}")
def test_environment_override_wins_over_saved_backend_preference(tmp_path, monkeypatch):
    config_path = tmp_path / "user-config.json"
    config_path.write_text(json.dumps({"astro_ai_backend_url": "https://saved.example"}))
    monkeypatch.setattr(APP, "get_config_path", lambda: str(config_path))
    monkeypatch.setattr(APP, "get_project_config_path", lambda: str(tmp_path / "no-project-config"))
    monkeypatch.setattr(APP, "get_legacy_config_path", lambda: str(tmp_path / "no-legacy-config"))
    monkeypatch.setenv("ASTRO_AI_BACKEND_URL", "http://127.0.0.1:8787")

    config = APP.load_config()
    assert config["astro_ai_backend_url"] == "http://127.0.0.1:8787"


@pytest.mark.skipif(APP is None, reason=f"Astro application dependencies unavailable: {APP_IMPORT_ERROR}")
def test_backend_url_is_saved_as_public_config_and_no_api_key_is_written(tmp_path, monkeypatch):
    config_path = tmp_path / "user-config.json"
    monkeypatch.setattr(APP, "get_config_path", lambda: str(config_path))
    monkeypatch.setattr(APP, "get_project_config_path", lambda: str(tmp_path / "no-project-config"))
    monkeypatch.setattr(APP, "get_legacy_config_path", lambda: str(tmp_path / "no-legacy-config"))
    APP.APP_PREFERENCES["astro_ai_backend_url"] = ""
    APP.save_config()

    config = json.loads(config_path.read_text())
    assert config["astro_ai_backend_url"] == DEFAULT_BACKEND_URL
    assert "openrouter_api_key" not in config
    if os.name == "posix":
        assert config_path.stat().st_mode & 0o077 == 0


@pytest.mark.skipif(APP is None, reason=f"Astro application dependencies unavailable: {APP_IMPORT_ERROR}")
def test_altair_welcome_switches_to_chat_after_first_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    app = APP.QApplication.instance() or APP.QApplication([])
    app_context = type("AppContext", (), {"language": "pl", "astro_ai_backend_url": DEFAULT_BACKEND_URL})()
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
    assert panel.current_chat_messages[0]["role"] == "User"
    panel.btn_retry_connection.click()
    assert len(started_workers) == 2
    assert started_workers[-1].message == "Pomóż mi obrobić zdjęcie"
    assert len(panel.current_chat_messages) == 1
    assert panel.stacked_layout.currentWidget() is panel.content_widget
    panel._start_new_chat()
    assert panel.conversation_stack.currentWidget() is panel.welcome_page
    panel.close()
    app.processEvents()
