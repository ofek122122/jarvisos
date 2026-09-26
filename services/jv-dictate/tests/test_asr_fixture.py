"""jv-dictate's ASR wrapper against a REAL committed fixture and the REAL
faster-whisper engine — no microphone, no evdev, no bus. Mirrors
services/jv-ears/tests/test_pipeline_fixtures.py, which proves the same
weights the same way for jv-ears' own wrapper.

`speech-no-wake.wav` (harness/fixtures) is real speech that names no wake
word — jv-ears' own fixture test proves it is never transcribed there
(test_no_wake_window.py: "no wake word, no VAD, nothing to say"), which is
exactly the shape push-to-talk dictation exists for: a sentence Jarvis was
never addressing.

Skips loudly rather than failing when either the model weights are absent
(this checkout has not run models/fetch.sh) or the test env this suite
happens to be running under lacks faster-whisper/soundfile — see
ops/ralph/runtests.sh's own comment: a service that has never been built
and switched has no unit for it to find an env from, so it falls back to
"any jarvis python env on the machine", and that env is not guaranteed to
be this one's."""

from pathlib import Path

import pytest

from jv_dictate.config import DictateConfig
from jv_dictate.injector import FakeSink
from jv_dictate.pipeline import transcribe_and_send

CFG = DictateConfig()
REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "harness" / "fixtures" / "speech-no-wake.wav"

try:
    import faster_whisper  # noqa: F401
    import soundfile  # noqa: F401

    _DEPS_OK = True
except ImportError:
    _DEPS_OK = False

if not _DEPS_OK:
    pytest.skip(
        "faster-whisper/soundfile not installed in this test env", allow_module_level=True
    )
if not (CFG.whisper_dir / "model.bin").exists():
    pytest.skip(
        "whisper model missing — run ./models/fetch.sh --only ears", allow_module_level=True
    )


def test_real_speech_is_transcribed_and_reaches_the_sink():
    import soundfile as sf

    from jv_dictate.asr import Transcriber

    data, rate = sf.read(FIXTURE, dtype="int16", always_2d=True)
    assert rate == CFG.sample_rate, f"fixture is {rate} Hz, expected {CFG.sample_rate}"
    audio = data[:, 0]

    transcriber = Transcriber(CFG.whisper_dir, beam_size=CFG.asr_beam_size)
    sink = FakeSink()

    text = transcribe_and_send(audio, transcriber, sink)

    assert text, "real speech through the real engine must produce non-empty text"
    assert sink.calls == [text]
