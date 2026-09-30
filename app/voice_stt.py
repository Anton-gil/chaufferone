"""Local speech-to-text via faster-whisper.

- Lazy-loads the model on first call so app startup stays fast.
- Uses `base.en` int8 on CPU — ~150MB, ~1s latency for a 5s clip on a modern laptop.
- Accepts webm/opus/wav/mp3/etc. (PyAV decodes anything ffmpeg can).
"""

from __future__ import annotations

import io
import threading
from typing import Optional

_LOCK = threading.Lock()
_MODEL: Optional["object"] = None
_MODEL_NAME = "base.en"


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _LOCK:
        if _MODEL is not None:
            return _MODEL
        from faster_whisper import WhisperModel

        _MODEL = WhisperModel(_MODEL_NAME, device="cpu", compute_type="int8")
    return _MODEL


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe an audio blob (any format PyAV can read) to English text.

    Returns "" for empty audio or when whisper produces no segments. Never raises
    for empty input; caller decides how to react to an empty string.
    """
    if not audio_bytes:
        return ""

    model = _load_model()
    buf = io.BytesIO(audio_bytes)

    segments, _info = model.transcribe(
        buf,
        language="en",
        beam_size=1,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    return text
