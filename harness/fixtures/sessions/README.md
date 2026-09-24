# harness/fixtures/sessions — recorded perception sessions

Each `*.jsonl` here is what **jv-ears really published** while listening to
the fixture WAV of the same name in `../`. Real openWakeWord, real Silero
VAD, real faster-whisper — no microphone, no hand-written frames.

```
hey-jarvis-clean.jsonl    wake + question in a quiet room
hey-jarvis-music.jsonl    the same shape with a music bed behind it
hey-jarvis-pause.jsonl    a 1.2 s pause MID-SENTENCE that must not split the utterance
speech-no-wake.jsonl      speech with no wake word — heard, never transcribed
```

## Why they are committed

`services/jv-ears/tests/test_pipeline_fixtures.py` needs ~1 GB of model
weights and skips loudly without them. Everything downstream of ears — the
HUD's state machine, jv-brain's turn taking, anything that consumes
perception — then has no example of what perception actually *looks* like
to test against. These files are that example, and they cost nothing to
read: `harness/tests/test_sessions.py` asserts the same requirements
`REVIEW-ears.md` states, on any machine, always.

They also make a behaviour change **visible**. Retune the VAD and the diff
on these files is the answer to "what did that do to the room?".

## The format

JSONL: line 1 is the session header from `schemas/README.md`, every line
after it is one `schemas/envelope.json` frame. `harness/session.py` is the
only reader — `session.problems()` checks a file against the **generated**
bindings (`jarvis_bus.schema`), so a schema that moves fails the fixture
tests instead of silently invalidating everything built on them.

`ts` is the pipeline's own sample clock (`EarsPipeline.clock`), zero at the
first sample of the WAV. That is what makes a session reproducible to the
sample: a diff means the pipeline changed, not that the machine was busy.
It is also why the header's `boot_id` is the `sample-clock` sentinel rather
than a real one — these `ts` are not this boot's `CLOCK_MONOTONIC`, and
saying so in the field that exists to prove they are is better than
borrowing a boot_id that would.

`utterance_id`s are real UUIDs minted during the recording, so they differ
from run to run. Nothing compares them across recordings; what is checked
is that every transcript threads an utterance the VAD opened.

## Who reads them

- `harness/tests/test_sessions.py` — the requirements `REVIEW-ears.md`
  states, asserted on every machine, with no weights installed.
- `services/jv-ears/tests/test_pipeline_fixtures.py` — re-records each WAV
  when the models ARE installed and compares, so these cannot rot quietly.
- **the HUD** (`shell/jv-hud/tests/tst_sessionreplay.qml`, PLAN B9) — the
  first consumer downstream of perception. Its QML tests used to hand-type
  the frames they asserted on; now they replay these and assert the state
  the HUD shows at each real second. A QML engine cannot read a file out of
  the repo, so `tools/gen_sessions_qml.py` compiles these lines verbatim
  into `shell/jv-hud/tests/Sessions.qml`, and `nix build .#jv-hud` runs it
  with `--check`.

## Regenerating

```sh
./models/fetch.sh --only ears          # once
python harness/fixtures/sessions/generate_sessions.py
python tools/gen_sessions_qml.py       # the HUD's compiled copy (or its build fails)
```

Then **read the diff before committing it**. A fixture that changed without
anyone intending it is the finding, not the chore — and the HUD's replay
test is the second half of that answer: it says, in seconds, what the retune
did to what the user would have seen.

Nothing lets them rot quietly: when the models are installed,
`test_the_committed_session_is_what_the_pipeline_still_does` re-records
every WAV and compares which frames arrived, when, and in what state —
plus the final transcripts, normalized. Model *scores* and partial texts
are deliberately not compared: those are the last digits of a float on the
machine that ran it, and a fixture that fails because CI has a different
CPU teaches people to regenerate without reading.
