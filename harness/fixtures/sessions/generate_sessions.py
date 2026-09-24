#!/usr/bin/env python3
"""Record the bus frames jv-ears really produces from the fixture WAVs.

The blueprint says the replay harness is built in Phase 3 and used forever:
recorded sensor sessions are the test fixtures for all perception work.
These are the first of them. Each `<name>.jsonl` next to this script is
what the REAL pipeline — real openWakeWord, real Silero VAD, real
faster-whisper — emitted while listening to `harness/fixtures/<name>.wav`.

Why commit the output of a test instead of just running the test:

  · `services/jv-ears/tests/test_pipeline_fixtures.py` needs ~1 GB of model
    weights and skips loudly without them. Everything downstream of ears —
    the HUD's state machine, jv-brain's turn taking, anything that consumes
    perception — then has no example of what perception actually looks like
    to test against. A committed session needs no weights and no mic.
  · it makes a behaviour change VISIBLE. Retune the VAD and the diff on
    these files is the answer to "what did that do to the room?".

`ts` is the pipeline's own sample clock (EarsPipeline.clock), zero at the
first sample of the WAV, so a session is reproducible to the sample and a
diff means the pipeline changed rather than the machine being busy. That
is also why the header's `boot_id` is the `sample-clock` sentinel instead
of a real one: these `ts` are not this boot's CLOCK_MONOTONIC and must not
be lined up against a session that is.

The one thing the sample clock cannot see is the ASR, and `ASR_LATENCY_S`
below is where that is put back. Everything else here is a recording; that
constant is a declared model, and it says so.

Regenerate (requires ./models/fetch.sh --only ears):

    python harness/fixtures/sessions/generate_sessions.py

Then read the diff before committing it. A fixture that changed without
anyone intending it is the finding, not the chore.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent
HARNESS = FIXTURES.parent
REPO = HARNESS.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(REPO / "services" / "pylib"))
sys.path.insert(0, str(REPO / "services" / "jv-ears"))

import session  # noqa: E402

# The WAVs of harness/fixtures/generate_fixtures.py, each one a question
# about perception (REVIEW-ears.md): a clean wake, a wake over music, a
# mid-sentence pause that must not split an utterance, and speech with no
# wake word at all.
SOURCES = (
    "hey-jarvis-clean.wav",
    "hey-jarvis-music.wav",
    "hey-jarvis-pause.wav",
    "speech-no-wake.wav",
)

SRC = "jv-ears"

# How much later than the sample clock a final transcript really reaches
# the bus (PLAN A58).
#
# `EarsPipeline.clock()` is samples consumed / rate. It does not advance
# while faster-whisper runs, and jv-ears publishes the final from inside
# `_on_speech_end`, immediately after `asr.transcribe()` returns — so on a
# real bus jarvisd stamps that frame however long the transcribe took AFTER
# the `speech_end` beside it. Stamping it at the sample clock made the ASR
# INSTANTANEOUS, and the gap between "the turn ended" and "the words
# arrived" was therefore exactly zero in every committed recording. That is
# why a HUD bug about precisely that gap (A57) lived through five suites
# built on these files: none of them could express the number.
#
# 2.2 s is the figure measured on ares — PHASE1-STATUS.md, "ASR is ~2.2 s
# fixed (faster-whisper distil-small, CPU, runs after speech_end)" — which
# is the same span `jv tap --latency` calls `hear`. Fixed rather than
# proportional to the utterance because that is how it measured.
#
# A DECLARED constant and not a measurement taken while generating, on
# purpose: a recording whose numbers depended on how busy the generating
# machine was would stop being reproducible to the sample, which is the
# property the rest of this file exists to protect. So a frame's `ts` here
# is the sample clock plus a stated model of one wall-clock cost, and
# nothing else.
ASR_LATENCY_S = 2.2

# PARTIALS ARE NOT DELAYED, and that is a limit rather than a claim. Each
# one costs a transcribe too, but no measurement of that exists, and
# modelling it honestly means modelling the sample clock falling BEHIND the
# room and catching up — the transcribe runs inline on the one thread that
# feeds wake and VAD (docs/optimization-backlog.md §6), so a live mic backs
# its queue up and drops. That would move every other frame in these
# recordings rather than one, and it would be inventing a timeline instead
# of recording one. The final is the frame downstream services act on and
# the only one whose lateness anything already measures. See PLAN A59.


def asr_delay(topic: str, body: Dict[str, Any]) -> float:
    """Seconds between this frame's sample clock and its arrival on the bus.

    One rule, in one place, so `frames_for` and anything re-deriving these
    files agree about what a recorded `ts` means.
    """
    if topic != "audio.transcript" or body.get("kind") != "final":
        return 0.0
    return ASR_LATENCY_S


def _plain(value: Any) -> Any:
    """numpy scalars -> JSON numbers, everywhere in a body.

    The wake score arrives as a float32 and the word timings come out of
    faster-whisper; `json.dumps` refuses both, and a fixture that cannot be
    written is worse than one that is wrong, because nobody sees it.
    """
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (bool, int, str)) or value is None:
        return value
    if isinstance(value, float):
        return value
    item = getattr(value, "item", None)
    return item() if callable(item) else value


def frames_for(wav: Path) -> List[Dict[str, Any]]:
    """Run the real pipeline over one WAV and return the frames it emitted.

    Shared with the jv-ears test that checks these files have not gone
    stale, so there is exactly one definition of how a session is recorded.
    """
    from jv_ears.audio import WavSource
    from jv_ears.config import EarsConfig
    from jv_ears.pipeline import EarsPipeline

    cfg = EarsConfig()
    out: List[Dict[str, Any]] = []
    seq: Dict[str, int] = {}
    pipe: EarsPipeline

    def publish(topic: str, conf: float, v: int, body: dict) -> None:
        n = seq.get(topic, 0)
        seq[topic] = n + 1
        out.append({
            "topic": topic,
            # 6 decimals resolves 1/16000 s with room to spare, and keeps
            # the committed file readable by a human doing the diff.
            "ts": round(pipe.clock() + asr_delay(topic, body), 6),
            "seq": n,
            "src": SRC,
            "conf": round(float(conf), 6),
            "v": v,
            "body": _plain(body),
        })

    pipe = EarsPipeline(cfg, publish)
    pipe.run(WavSource([wav], cfg.chunk_samples))
    # File order is chronological, because replay.py sleeps the DELTA
    # between consecutive lines: a frame written before one it now follows
    # in time would replay with that gap clamped to zero and the recording
    # would silently lose it. A stable sort, so frames sharing a `ts` keep
    # the order jv-ears published them in. Today this moves nothing — every
    # final is already the last frame of its recording — which is exactly
    # when an invariant is cheap to state.
    out.sort(key=lambda f: f["ts"])
    return out


def main() -> int:
    for name in SOURCES:
        wav = FIXTURES / name
        if not wav.exists():
            print(f"missing {wav} — run harness/fixtures/generate_fixtures.py")
            return 1
        out = HERE / (wav.stem + ".jsonl")
        frames = frames_for(wav)
        with out.open("w", encoding="utf-8", newline="\n") as fh:
            session.dump(session.sample_clock_header(), frames, fh)
        session.check(session.load(out))
        print(f"wrote {out.name}  {len(frames)} frames  "
              f"{frames[-1]['ts'] if frames else 0:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
