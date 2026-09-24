"""harness/session.py — what a recorded session file is allowed to be.

A fixture that has quietly drifted from the bus contract is worse than no
fixture: every test built on it keeps passing while asserting yesterday's
law. So the format has ONE reader, and that reader can be asked whether a
session is still legal — against the GENERATED bindings, never against a
hand-copy of schemas/ (the copy is what rots).
"""

import json
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1]
REPO = HARNESS.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(REPO / "services" / "pylib"))

import session  # noqa: E402

HEADER = {"boot_id": "sample-clock", "wall_time_utc": "2026-09-24T00:00:00+00:00",
          "monotonic_now": 0.0}


def frame(**over):
    f = {"topic": "audio.vad", "ts": 1.0, "seq": 0, "src": "jv-ears", "conf": 1.0,
         "v": 1, "body": {"event": "speech_start", "utterance_id": "u1"}}
    f.update(over)
    return f


def write(tmp_path, header, frames, name="s.jsonl"):
    p = tmp_path / name
    with p.open("w", encoding="utf-8", newline="\n") as fh:
        session.dump(header, frames, fh)
    return p


def write_raw(tmp_path, header, frames, name="raw.jsonl"):
    """Bypass dump() — for files dump() would (rightly) refuse to write."""
    p = tmp_path / name
    body = "\n".join(json.dumps(o) for o in [header, *frames])
    p.write_text(body + "\n", encoding="utf-8")
    return p


# ------------------------------------------------------------- load/dump

def test_dump_then_load_roundtrips(tmp_path):
    frames = [frame(), frame(seq=1, ts=2.0, body={"event": "speech_end",
                                                  "utterance_id": "u1",
                                                  "duration_s": 1.0})]
    s = session.load(write(tmp_path, HEADER, frames))
    assert s.header == HEADER
    assert s.frames == frames
    assert s.path is not None


def test_dump_writes_one_json_object_per_line(tmp_path):
    p = write(tmp_path, HEADER, [frame(), frame(seq=1)])
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3  # header + 2 frames
    assert json.loads(lines[0])["boot_id"] == "sample-clock"


def test_load_rejects_a_file_with_no_header(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"topic": "audio.vad"}\n', encoding="utf-8")
    with pytest.raises(session.SessionError, match="session header"):
        session.load(p)


def test_load_rejects_an_empty_file(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    with pytest.raises(session.SessionError, match="session header"):
        session.load(p)


def test_load_names_the_line_it_could_not_parse(tmp_path):
    p = tmp_path / "torn.jsonl"
    p.write_text(json.dumps(HEADER) + "\n{not json\n", encoding="utf-8")
    with pytest.raises(session.SessionError, match="line 2"):
        session.load(p)


def test_session_error_is_a_value_error():
    """replay.py's caller has caught ValueError since the harness existed."""
    assert issubclass(session.SessionError, ValueError)


# --------------------------------------------------------------- header

@pytest.mark.parametrize("header", [
    {**HEADER, "extra": 1},
    {k: v for k, v in HEADER.items() if k != "wall_time_utc"},
    {**HEADER, "boot_id": ""},
    {**HEADER, "boot_id": 7},
    {**HEADER, "wall_time_utc": ""},
    {**HEADER, "monotonic_now": "0"},
])
def test_a_header_that_cannot_date_the_frames_is_a_problem(tmp_path, header):
    s = session.load(write(tmp_path, header, [frame()]))
    assert session.problems(s), f"accepted {header}"


def test_a_header_with_no_boot_id_is_not_a_session_at_all(tmp_path):
    """Without boot_id nothing can date the frames, so this is not a
    damaged session — it is some other file. load() says so."""
    header = {k: v for k, v in HEADER.items() if k != "boot_id"}
    with pytest.raises(session.SessionError, match="session header"):
        session.load(write_raw(tmp_path, header, [frame()]))


def test_a_nan_anchor_is_a_problem(tmp_path):
    p = write_raw(tmp_path, HEADER, [frame()])
    p.write_text(p.read_text().replace('"monotonic_now": 0.0',
                                       '"monotonic_now": NaN'), encoding="utf-8")
    assert any("monotonic_now" in x for x in session.problems(session.load(p)))


def test_dump_refuses_to_write_a_number_json_cannot_hold(tmp_path):
    """A file only some parsers accept is not a fixture."""
    with pytest.raises(ValueError):
        write(tmp_path, HEADER, [frame(ts=float("nan"))])


def test_a_good_header_with_good_frames_has_no_problems(tmp_path):
    s = session.load(write(tmp_path, HEADER, [frame()]))
    assert session.problems(s) == []


# ---------------------------------------------------------- the envelope

def test_envelope_keys_come_from_the_generated_bindings():
    """Not a hand-copy of schemas/envelope.json — the copy is what rots."""
    assert set(session.ENVELOPE_KEYS) == {
        "topic", "ts", "seq", "src", "conf", "v", "body"}


@pytest.mark.parametrize("bad", [
    {"conf": 1.5},
    {"conf": -0.1},
    {"conf": "1.0"},
    {"v": 0},
    {"v": True},
    {"seq": -1},
    {"seq": 1.5},
    {"seq": True},
    {"ts": "1.0"},
    {"src": ""},
    {"topic": "audio.*"},
    {"topic": "audio"},
    {"topic": 7},
    {"body": []},
])
def test_a_frame_that_is_not_an_envelope_is_a_problem(tmp_path, bad):
    s = session.load(write(tmp_path, HEADER, [frame(**bad)]))
    assert session.problems(s), f"accepted {bad}"


def test_a_missing_envelope_key_is_a_problem(tmp_path):
    f = frame()
    del f["conf"]
    s = session.load(write(tmp_path, HEADER, [f]))
    assert any("conf" in p for p in session.problems(s))


def test_an_extra_envelope_key_is_a_problem(tmp_path):
    s = session.load(write(tmp_path, HEADER, [frame(wall_time="now")]))
    assert any("wall_time" in p for p in session.problems(s))


def test_a_frame_that_is_not_an_object_is_a_problem(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(json.dumps(HEADER) + "\n[]\n", encoding="utf-8")
    assert session.problems(session.load(p))


# --------------------------------------------------- bodies and versions

def test_a_body_missing_a_required_field_is_a_problem(tmp_path):
    f = frame(topic="audio.wake", conf=0.7,
              body={"model": "hey_jarvis", "score": 0.7})
    assert any("threshold" in p for p in session.problems(
        session.load(write(tmp_path, HEADER, [f]))))


def test_a_body_with_a_field_the_schema_does_not_have_is_a_problem(tmp_path):
    body = {"event": "speech_start", "utterance_id": "u1", "loudness": 0.4}
    s = session.load(write(tmp_path, HEADER, [frame(body=body)]))
    assert any("loudness" in p for p in session.problems(s))


def test_an_absent_optional_field_is_fine(tmp_path):
    """duration_s is optional on audio.vad; speech_start omits it."""
    assert session.problems(session.load(write(tmp_path, HEADER, [frame()]))) == []


def test_a_frame_at_a_version_the_schemas_are_not_at_is_a_problem(tmp_path):
    """The whole point of a committed fixture is that it is CURRENT law."""
    s = session.load(write(tmp_path, HEADER, [frame(v=2)]))
    assert any("v=2" in p or "version" in p for p in session.problems(s))


def test_an_unknown_topic_is_not_a_problem(tmp_path):
    """New topics are ordinary reviewed commits (schemas/README.md). An old
    harness refusing to read a recording of a newer topic would be the B5
    mistake: never refuse to show what you merely do not recognise."""
    f = frame(topic="mood.weather", body={"anything": True})
    assert session.problems(session.load(write(tmp_path, HEADER, [f]))) == []


def test_a_non_finite_number_in_a_hand_written_session_is_a_problem(tmp_path):
    p = write_raw(tmp_path, HEADER, [frame()])
    p.write_text(p.read_text().replace('"conf": 1.0', '"conf": Infinity'),
                 encoding="utf-8")
    assert any("conf" in x for x in session.problems(session.load(p)))


# -------------------------------------------------------------- ordering

def test_one_publisher_going_backwards_in_time_is_a_problem(tmp_path):
    """ts is CLOCK_MONOTONIC: one src's own frames on one topic cannot
    move backwards. (Two publishers interleaving out of order can.)"""
    s = session.load(write(tmp_path, HEADER, [frame(ts=2.0), frame(ts=1.0, seq=1)]))
    assert any("ts" in p for p in session.problems(s))


def test_two_publishers_interleaving_out_of_order_is_not_a_problem(tmp_path):
    frames = [frame(ts=2.0, src="jv-ears"),
              frame(ts=1.0, src="jv-voice", topic="speech.state",
                    body={"state": "idle"})]
    assert session.problems(session.load(write(tmp_path, HEADER, frames))) == []


def test_seq_must_strictly_increase_per_publisher_and_topic(tmp_path):
    s = session.load(write(tmp_path, HEADER, [frame(seq=3), frame(seq=3, ts=2.0)]))
    assert any("seq" in p for p in session.problems(s))


def test_a_seq_gap_is_not_a_problem(tmp_path):
    """Gaps are the slow-consumer policy working (schemas/README.md)."""
    frames = [frame(seq=0), frame(seq=9, ts=2.0)]
    assert session.problems(session.load(write(tmp_path, HEADER, frames))) == []


def test_every_problem_names_the_frame_it_is_about(tmp_path):
    frames = [frame(), frame(seq=1, ts=2.0, conf=3.0)]
    (p,) = session.problems(session.load(write(tmp_path, HEADER, frames)))
    assert "frame 2" in p, p


def test_check_raises_with_every_problem_at_once(tmp_path):
    frames = [frame(conf=3.0, v=0)]
    with pytest.raises(session.SessionError) as e:
        session.check(session.load(write(tmp_path, HEADER, frames)))
    assert "conf" in str(e.value) and "v" in str(e.value)


def test_check_is_quiet_when_the_session_is_legal(tmp_path):
    session.check(session.load(write(tmp_path, HEADER, [frame()])))


# --------------------------------------------------- making the anchors

def test_a_live_header_is_legal_and_names_this_boot(tmp_path):
    h = session.live_header()
    assert session.problems(session.load(write(tmp_path, h, [frame()]))) == []
    assert h["boot_id"] != session.SAMPLE_CLOCK
    assert h["monotonic_now"] > 0


def test_a_sample_clock_header_is_legal_and_refuses_to_name_a_boot(tmp_path):
    """Borrowing a real boot_id would claim these ts can be lined up
    against a live recording. They cannot."""
    h = session.sample_clock_header()
    assert session.problems(session.load(write(tmp_path, h, [frame()]))) == []
    assert h["boot_id"] == session.SAMPLE_CLOCK
    assert h["monotonic_now"] == 0.0
