"""tools/gen_sessions_qml.py — recorded sessions -> the HUD tests' Sessions.qml.

PLAN B9. `harness/fixtures/sessions/` holds what jv-ears really published while
listening to each fixture WAV (B3). The HUD's QML tests used to hand-type the
frames they asserted on, which means the same person wrote the input and the
expectation; these recordings let them assert against perception's real output
instead. QML cannot read a file out of the repo, so the recordings are compiled
into one generated QML object — the same shape as the theme (invariant 9): one
source of truth, a generated committed artefact, and a `--check` that fails the
build when the two drift apart.

These tests are what keep that true. The generator carries no schema knowledge
on purpose — `harness/session.py` is the format's only reader and
`harness/tests/test_sessions.py` validates the recordings against the generated
bindings. All this does is move bytes somewhere QML can reach, verbatim, which
is exactly what makes it safe for it to be stdlib-only (it runs in the jv-hud
build and in CI, neither of which has jarvis_bus importable).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import gen_sessions_qml as gen  # noqa: E402

HEADER = '{"boot_id": "sample-clock", "wall_time_utc": "2026-09-24T02:47:50+00:00", "monotonic_now": 0.0}'
FRAME_A = '{"topic": "audio.vad", "ts": 0.8, "seq": 0, "src": "jv-ears", "conf": 1.0, "v": 1, "body": {"event": "speech_start"}}'
FRAME_B = '{"topic": "audio.wake", "ts": 1.44, "seq": 0, "src": "jv-ears", "conf": 0.99, "v": 1, "body": {"model": "hey_jarvis", "score": 0.99, "threshold": 0.5}}'


def write_session(dirpath: Path, name: str, lines: list[str]) -> Path:
    path = dirpath / f"{name}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sessions"
    d.mkdir()
    write_session(d, "one-wake", [HEADER, FRAME_A, FRAME_B])
    write_session(d, "another", [HEADER, FRAME_A])
    (d / "README.md").write_text("not a session\n", encoding="utf-8")
    return d


# --- what the generator reads ---------------------------------------------


def test_a_session_is_its_header_and_its_frames_verbatim(sessions_dir: Path):
    s = gen.load_session(sessions_dir / "one-wake.jsonl")
    assert s.name == "one-wake"
    assert s.header == HEADER
    assert s.frames == [FRAME_A, FRAME_B], "frames must not be reformatted"


def test_a_line_is_copied_and_never_re_serialised(tmp_path: Path):
    """Verbatim means the bytes in the recording, not an equivalent JSON.

    A generator that parsed and re-dumped each line would look right against
    a file `json.dumps` happened to have written, and would quietly hand the
    tests something other than what the recording says — which is the one
    thing these fixtures exist to be. So the line here is deliberately not
    in `json.dumps`' own formatting.
    """
    d = tmp_path / "s"
    d.mkdir()
    compact = '{"topic":"audio.vad","ts":0.80,"seq":0,"src":"jv-ears","conf":1.0,"v":1,"body":{"event":"speech_start"}}'
    write_session(d, "compact", [HEADER, compact])
    s = gen.load_session(d / "compact.jsonl")
    assert s.frames == [compact]
    assert compact in gen.render_sessions_qml([s]).replace("\\", "")


def test_only_jsonl_files_are_sessions_and_they_come_out_sorted(sessions_dir: Path):
    names = [s.name for s in gen.load_sessions(sessions_dir)]
    assert names == ["another", "one-wake"], "sorted, so the output is stable"


def test_a_recording_with_no_frames_is_an_error(tmp_path: Path):
    d = tmp_path / "s"
    d.mkdir()
    write_session(d, "empty", [HEADER])
    with pytest.raises(gen.SessionsError, match="no frames"):
        gen.load_session(d / "empty.jsonl")


def test_a_recording_with_no_header_at_all_is_an_error(tmp_path: Path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "blank.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(gen.SessionsError):
        gen.load_session(d / "blank.jsonl")


@pytest.mark.parametrize("bad", ["[1,2]", "null", "not json at all", '{"a":'])
def test_a_line_that_is_not_a_json_object_is_an_error(tmp_path: Path, bad: str):
    # A fixture we cannot read must fail HERE, loudly, rather than being
    # compiled into a test that then asserts on a line QML will not parse.
    d = tmp_path / "s"
    d.mkdir()
    write_session(d, "broken", [HEADER, bad])
    with pytest.raises(gen.SessionsError):
        gen.load_session(d / "broken.jsonl")


def test_a_non_ascii_line_is_an_error(tmp_path: Path):
    # The recorders write with ensure_ascii=True, so every legal line is
    # ASCII and a QML string literal of it needs no encoding thought at all.
    d = tmp_path / "s"
    d.mkdir()
    write_session(d, "unicode", [HEADER, '{"topic": "audio.transcript", "body": {"text": "shé"}}'])
    with pytest.raises(gen.SessionsError, match="ASCII"):
        gen.load_session(d / "unicode.jsonl")


# --- what it writes -------------------------------------------------------


def test_the_output_announces_that_it_is_generated(sessions_dir: Path):
    qml = gen.render_sessions_qml(gen.load_sessions(sessions_dir))
    assert qml.startswith("//")
    assert "DO NOT EDIT" in qml
    assert "gen_sessions_qml.py" in qml


def test_the_output_imports_nothing_but_qtquick(sessions_dir: Path):
    # It lives beside core/'s tests and must load in a bare QML engine:
    # anything else here would make the whole tests directory unloadable.
    qml = gen.render_sessions_qml(gen.load_sessions(sessions_dir))
    assert re.findall(r"^import .*$", qml, re.M) == ["import QtQuick"]


def test_every_frame_survives_the_trip_into_qml_byte_for_byte(sessions_dir: Path):
    qml = gen.render_sessions_qml(gen.load_sessions(sessions_dir))
    # Pull the string literals back out and parse them: a generator that
    # mangled a quote would produce QML that looks fine and lies.
    literals = [json.loads(m) for m in re.findall(r'"\{.*\}"', qml)]
    assert HEADER in literals
    assert FRAME_A in literals
    assert FRAME_B in literals
    for line in literals:
        assert isinstance(json.loads(line), dict)


def test_the_names_are_listed_so_a_test_can_check_nothing_went_missing(sessions_dir: Path):
    qml = gen.render_sessions_qml(gen.load_sessions(sessions_dir))
    assert '"another", "one-wake"' in qml


def test_rendering_is_deterministic(sessions_dir: Path):
    a = gen.render_sessions_qml(gen.load_sessions(sessions_dir))
    b = gen.render_sessions_qml(gen.load_sessions(sessions_dir))
    assert a == b


def test_an_empty_sessions_directory_is_an_error(tmp_path: Path):
    # Otherwise the generator happily emits an object with no recordings in
    # it and every test built on them passes by asserting nothing.
    d = tmp_path / "s"
    d.mkdir()
    with pytest.raises(gen.SessionsError, match="no recordings"):
        gen.load_sessions(d)


# --- the drift gate -------------------------------------------------------


def run_gen(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_sessions_qml.py"), *args],
        capture_output=True,
        text=True,
    )


def test_write_then_check_is_clean(sessions_dir: Path, tmp_path: Path):
    out = tmp_path / "out"
    out.mkdir()
    assert run_gen("--sessions", str(sessions_dir), "--out-dir", str(out)).returncode == 0
    assert (out / "Sessions.qml").exists()
    assert run_gen("--sessions", str(sessions_dir), "--out-dir", str(out)).returncode == 0
    check = run_gen("--check", "--sessions", str(sessions_dir), "--out-dir", str(out))
    assert check.returncode == 0, check.stderr


def test_check_fails_when_a_recording_changed_under_the_committed_qml(
    sessions_dir: Path, tmp_path: Path
):
    out = tmp_path / "out"
    out.mkdir()
    assert run_gen("--sessions", str(sessions_dir), "--out-dir", str(out)).returncode == 0
    write_session(sessions_dir, "one-wake", [HEADER, FRAME_A])
    check = run_gen("--check", "--sessions", str(sessions_dir), "--out-dir", str(out))
    assert check.returncode == 1
    assert "Sessions.qml" in check.stderr


def test_check_fails_when_the_generated_file_is_missing(sessions_dir: Path, tmp_path: Path):
    out = tmp_path / "out"
    out.mkdir()
    check = run_gen("--check", "--sessions", str(sessions_dir), "--out-dir", str(out))
    assert check.returncode == 1


def test_a_broken_recording_fails_the_run_instead_of_being_compiled(
    sessions_dir: Path, tmp_path: Path
):
    out = tmp_path / "out"
    out.mkdir()
    write_session(sessions_dir, "one-wake", [HEADER, "{oops"])
    bad = run_gen("--sessions", str(sessions_dir), "--out-dir", str(out))
    assert bad.returncode == 1
    assert not (out / "Sessions.qml").exists()


# --- the repo's own recordings --------------------------------------------


def test_committed_sessions_qml_matches_the_recordings_on_disk():
    """The gate that matters: re-record perception and this fails until the
    HUD's fixtures are regenerated and their diff read."""
    committed = (ROOT / "shell" / "jv-hud" / "tests" / "Sessions.qml").read_text("utf-8")
    fresh = gen.render_sessions_qml(gen.load_sessions(ROOT / "harness" / "fixtures" / "sessions"))
    assert committed == fresh, "run: python tools/gen_sessions_qml.py"


def test_the_repo_recordings_are_all_sample_clock_sessions():
    """The QML tests replay `ts` as a virtual clock and assert the real
    seconds at which the state changed. That only means anything while these
    recordings carry the sample clock (harness/fixtures/sessions/README.md);
    a live-bus recording's `ts` would be this boot's CLOCK_MONOTONIC and
    every expectation in tst_sessionreplay.qml would be noise."""
    for s in gen.load_sessions(ROOT / "harness" / "fixtures" / "sessions"):
        assert json.loads(s.header)["boot_id"] == "sample-clock", s.name
