"""Small thread-safe cache of ONNX sessions for repeated background extraction."""
from __future__ import annotations

from collections import OrderedDict
import os
import threading

_SESSIONS = OrderedDict()
_LOCK = threading.Lock()


def background_session(model_path, providers):
    import onnxruntime as ort

    path = os.path.abspath(model_path)
    stat = os.stat(path)
    provider_key = tuple((item[0], tuple(sorted(item[1].items()))) if isinstance(item, tuple) else item for item in providers)
    key = (path, stat.st_mtime_ns, stat.st_size, provider_key)
    with _LOCK:
        if key in _SESSIONS:
            _SESSIONS.move_to_end(key)
            return _SESSIONS[key]
        session = ort.InferenceSession(model_path, providers=providers)
        _SESSIONS[key] = session
        while len(_SESSIONS) > 2:
            _SESSIONS.popitem(last=False)
        return session
