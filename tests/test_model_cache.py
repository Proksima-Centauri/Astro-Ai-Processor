import sys
from types import SimpleNamespace

from processing import model_cache


def test_background_session_reuses_model_and_invalidates_provider_or_file(tmp_path, monkeypatch):
    model = tmp_path / "model.onnx"
    model.write_bytes(b"first")
    calls = []
    def create(*args, **kwargs):
        result = object()
        calls.append(result)
        return result
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(InferenceSession=create))
    monkeypatch.setattr(model_cache, "_SESSIONS", model_cache.OrderedDict())
    first = model_cache.background_session(str(model), ["CPUExecutionProvider"])
    assert model_cache.background_session(str(model), ["CPUExecutionProvider"]) is first
    assert model_cache.background_session(str(model), ["CUDAExecutionProvider"]) is not first
    model.write_bytes(b"changed model")
    assert model_cache.background_session(str(model), ["CPUExecutionProvider"]) is not first
    assert len(calls) == 3
    assert len(model_cache._SESSIONS) == 2
