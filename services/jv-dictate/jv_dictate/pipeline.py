"""The glue between a finished recording and a sink: run it through the
ASR, and if it produced any text, hand it to the sink. Kept separate from
service.py so it can be unit-tested with a stub transcriber and no bus, no
event loop, no evdev."""

from __future__ import annotations

import numpy as np

from .asr import Transcriber
from .injector import Sink


def transcribe_and_send(audio_i16: np.ndarray, transcriber: Transcriber, sink: Sink) -> str:
    """Runs one finished recording through the ASR and, if it produced any
    text, hands it to the sink. Returns the text (possibly empty) so a
    caller can log or test against it without re-deriving it from the sink."""
    text, _lang, _conf = transcriber.transcribe(audio_i16)
    if text:
        sink.type_text(text)
    return text
