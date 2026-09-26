"""transcribe_and_send — the glue between a recording and a Sink, against a
stub Transcriber (no model weights, no faster-whisper). The real engine is
covered separately in tests/test_asr_fixture.py, which skips loudly when
models are not fetched (same pattern as jv-ears' own fixture tests)."""

import numpy as np

from jv_dictate.injector import FakeSink
from jv_dictate.pipeline import transcribe_and_send


class StubTranscriber:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def transcribe(self, audio_i16):
        self.calls.append(audio_i16)
        return self.result


def test_a_nonempty_transcript_reaches_the_sink():
    sink = FakeSink()
    transcriber = StubTranscriber(("remind me to call my sister", "en", 0.9))
    audio = np.zeros(10, dtype=np.int16)

    text = transcribe_and_send(audio, transcriber, sink)

    assert text == "remind me to call my sister"
    assert sink.calls == ["remind me to call my sister"]
    assert transcriber.calls == [audio]


def test_an_empty_transcript_sends_nothing():
    # Silence, or a recording too short for the ASR to say anything: the
    # sink must not be asked to type an empty string.
    sink = FakeSink()
    transcriber = StubTranscriber(("", "en", 0.0))

    text = transcribe_and_send(np.zeros(10, dtype=np.int16), transcriber, sink)

    assert text == ""
    assert sink.calls == []
