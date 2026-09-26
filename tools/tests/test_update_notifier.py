"""pkgs/jv-update-notifier — the login update check (PLAN G3).

CLAUDE.md's NixOS discipline: a change only exists once it is reviewed and
built deliberately (`nixos-rebuild build` -> review -> `test` -> `switch`).
G3 asks for a login-time notice that commits exist, "never auto-switch" — so
the one thing this suite exists to prove, harder than anything else here, is
that the script genuinely cannot mutate anything: no merge, no rebase, no
checkout, no `nixos-rebuild`, only `git fetch` (which only ever moves
remote-tracking refs) and read-only queries.

WHY THIS RUNS THE REAL SCRIPT AGAINST A REAL GIT REPO rather than reading it
as text (the way tools/tests/test_snapshots.py reads jv-snapshot-restore).
Unlike a btrfs subvolume, a plain git repo in tmp_path is created and deleted
with nothing but ordinary files — there is no `user_subvol_rm_allowed`
problem here, so the real round trip (behind commits appear -> repo fetched
-> notified -> nothing mutated; no commits -> silent; fetch fails -> silent,
no crash) is provable directly, the same way test_verify.py and
test_dependents.py already spin up real git repos in tmp_path.

The script is pulled out of pkgs/jv-update-notifier/default.nix's own `text`
attribute rather than duplicated here, so a change to the shipped script is
exactly the behaviour this suite runs — not a copy of it.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from test_gen_theme_qml import ROOT

MODULE = ROOT / "pkgs" / "jv-update-notifier" / "default.nix"


def module_src() -> str:
    return MODULE.read_text("utf-8")


def script_text() -> str:
    src = module_src()
    m = re.search(r"text = ''\n(.*?)\n  '';\n", src, re.S)
    assert m, "no text = '' ... ''; script body found in default.nix"
    # Nix's '' string escapes bash's ${...} as ''${...} — undo that so the
    # extracted body is plain, runnable bash.
    return m.group(1).replace("''${", "${")


@pytest.fixture()
def script_path(tmp_path: Path) -> Path:
    p = tmp_path / "jv-update-notifier"
    p.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + script_text() + "\n")
    p.chmod(0o755)
    return p


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def make_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real origin, plus a clone that tracks it — the way `git clone`
    wires up `@{u}` on its own, with no explicit `--set-upstream-to`."""
    origin = tmp_path / "origin"
    origin.mkdir()
    git("init", "-q", "-b", "main", cwd=origin)
    git("config", "user.email", "t@example.com", cwd=origin)
    git("config", "user.name", "t", cwd=origin)
    (origin / "f.txt").write_text("1\n")
    git("add", "-A", cwd=origin)
    git("commit", "-q", "-m", "first", cwd=origin)

    work = tmp_path / "work"
    subprocess.run(
        ["git", "clone", "-q", str(origin), str(work)],
        check=True,
        capture_output=True,
        text=True,
    )
    git("config", "user.email", "t@example.com", cwd=work)
    git("config", "user.name", "t", cwd=work)
    return origin, work


def stub_notify_send(tmp_path: Path) -> tuple[Path, Path]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    calls = tmp_path / "notify-send-calls.txt"
    stub = bindir / "notify-send"
    stub.write_text(f'#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> {calls}\n')
    stub.chmod(0o755)
    return bindir, calls


def run_script(script_path: Path, repo: Path, bindir: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env.get('PATH', '')}"
    return subprocess.run(
        [str(script_path), str(repo)], env=env, capture_output=True, text=True
    )


# --------------------------------------------------------- static, always


def test_git_is_only_ever_invoked_read_only():
    # The whitelist this whole item rests on: every `git -C "$repo" <verb>`
    # in the shipped script has to be one that cannot change HEAD, the index
    # or a file in the working tree.
    verbs = re.findall(r'git -C "\$repo" (\S+)', script_text())
    assert verbs, "no `git -C \"$repo\" ...` invocation found in the script"
    assert set(verbs) <= {"fetch", "rev-parse", "rev-list", "log"}, (
        f"a git verb outside the read-only whitelist was used: {verbs}"
    )


def test_the_script_never_invokes_nixos_rebuild_or_a_mutating_git_verb():
    src = script_text()
    # The notify-send body is allowed to TALK about nixos-rebuild (it tells
    # the user this never runs it for them) — it must never actually be
    # invoked, which means never followed by one of its own subcommands.
    for sub in ("switch", "test", "build", "boot"):
        assert f"nixos-rebuild {sub}" not in src, (
            f"the script invokes nixos-rebuild {sub}"
        )
    for verb in ("pull", "merge", "rebase", "reset", "checkout", "switch", "push"):
        assert not re.search(rf"\bgit\b[^\n]*\b{verb}\b", src), (
            f"the script invokes a mutating git verb: {verb}"
        )


# ------------------------------------------------------------- behaviour


def test_no_notification_when_already_up_to_date(tmp_path, script_path):
    _origin, work = make_repo(tmp_path)
    bindir, calls = stub_notify_send(tmp_path)

    result = run_script(script_path, work, bindir)

    assert result.returncode == 0, result.stderr
    assert not calls.exists(), f"notified with nothing new: {calls.read_text()}"


def test_notifies_with_the_commit_count_and_latest_subject(tmp_path, script_path):
    origin, work = make_repo(tmp_path)
    (origin / "f.txt").write_text("2\n")
    git("commit", "-am", "second: a change worth knowing about", cwd=origin)
    bindir, calls = stub_notify_send(tmp_path)

    result = run_script(script_path, work, bindir)

    assert result.returncode == 0, result.stderr
    assert calls.exists(), "no notification sent even though upstream is ahead"
    text = calls.read_text()
    assert "1 new commit" in text, text
    assert "second: a change worth knowing about" in text, text


def test_pluralises_more_than_one_commit(tmp_path, script_path):
    origin, work = make_repo(tmp_path)
    for i in (2, 3):
        (origin / "f.txt").write_text(f"{i}\n")
        git("commit", "-am", f"commit {i}", cwd=origin)
    bindir, calls = stub_notify_send(tmp_path)

    run_script(script_path, work, bindir)

    text = calls.read_text()
    assert "2 new commits" in text, text
    assert "1 new commit" not in text, text


def test_never_mutates_head_or_the_working_tree(tmp_path, script_path):
    origin, work = make_repo(tmp_path)
    (origin / "f.txt").write_text("2\n")
    git("commit", "-am", "second", cwd=origin)

    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=work, capture_output=True, text=True, check=True
    ).stdout
    bindir, _calls = stub_notify_send(tmp_path)

    run_script(script_path, work, bindir)

    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=work, capture_output=True, text=True, check=True
    ).stdout
    assert before == after, "HEAD moved — fetch is supposed to be the only git verb run"

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=work, capture_output=True, text=True, check=True
    ).stdout
    assert status == "", f"working tree got dirty: {status}"


def test_quiet_and_clean_exit_when_the_remote_is_unreachable(tmp_path, script_path):
    # The fetch-fails path: an upstream is configured (via a real clone,
    # exactly like `test_notifies_...` above) but the remote is then pointed
    # at a path nothing lives at — a stand-in for "no network".
    _origin, work = make_repo(tmp_path)
    git("remote", "set-url", "origin", str(tmp_path / "does-not-exist"), cwd=work)
    bindir, calls = stub_notify_send(tmp_path)

    result = run_script(script_path, work, bindir)

    assert result.returncode == 0, result.stderr
    assert not calls.exists(), f"notified despite an unreachable remote: {calls.read_text()}"


def test_quiet_and_clean_exit_when_there_is_no_upstream_tracking_branch(tmp_path, script_path):
    repo = tmp_path / "solo"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "user.email", "t@example.com", cwd=repo)
    git("config", "user.name", "t", cwd=repo)
    (repo / "f.txt").write_text("1\n")
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "first", cwd=repo)
    bindir, calls = stub_notify_send(tmp_path)

    result = run_script(script_path, repo, bindir)

    assert result.returncode == 0, result.stderr
    assert not calls.exists()


def test_quiet_and_clean_exit_when_the_path_is_not_a_git_repo(tmp_path, script_path):
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    bindir, calls = stub_notify_send(tmp_path)

    result = run_script(script_path, not_a_repo, bindir)

    assert result.returncode == 0, result.stderr
    assert not calls.exists()
