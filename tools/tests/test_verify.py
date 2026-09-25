"""tools/verify.py — the gate that runs what reads what you changed (PLAN B70).

B68 made the notice and B69 taught it QML, and both stopped one step short of
a verdict: `runtests.sh` PRINTS the other suites that read your change and then
exits with pytest's own status, so an iteration can read the line and not run
them. That is the same shape as the rule it replaced — "run the relevant
suites" — with better information behind it, and the rule it replaced failed
three times in ninety iterations.

B70 asked whether to bind it, and called the answer a cost question. It is
measured now, on this machine, warm venvs, one suite at a time:

    pylib          1.6 s      jv-guard       3.9 s      jv-voice      23.0 s
    jv-hud-bridge  1.6 s      jv-context    11.4 s      jv-brain      36.3 s
    jv-compat      2.7 s      tools         12.2 s      jv-ears      145.8 s
    harness        3.4 s                               ----------------------
                                                        all ten      241.7 s

The worst case in the whole repo is a change to `services/pylib/jarvis_bus/`,
which every service imports: ten suites, four minutes, and 60% of it is
jv-ears alone. Everything else is far cheaper — a service change is that
service plus `tools` (seconds), a HUD change is `tools` + the two QML gates
(~80 s). Against that: a red commit has twice stood for two days.

So it binds always, and the cutoff B70 floated — bind only when the named set
is small — is not a cheaper version of that. It is the same thing with the
`services/pylib/` case cut out, and that case is the ONLY one where the author
cannot possibly have guessed the readers, which is the entire reason any of
this exists. A rule that drops coverage exactly where coverage is the point is
not a compromise.

B72 then added the two gates that are a nix EVALUATION rather than a suite.
`nixtest.sh` is planned like anything else now — declared, because its subject
is a flake attribute and not a path — and `hudscreens.sh` is deliberately not:
it is NAMED on every verdict instead, because a list of what read your change
that quietly drops one entry reads as coverage.

What it does NOT do is claim to be the whole gate: `nixos-rebuild build
--flake .#ares` and `nix build .#jarvisd` are not test suites derived from
what you touched, and PROMPT.md still names them.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import dependents  # noqa: E402
import verify  # noqa: E402

VERIFY_SH = ROOT / "ops" / "ralph" / "verify.sh"
PROMPT = ROOT / "ops" / "ralph" / "PROMPT.md"


# ------------------------------------------------------------- a repo, by hand


def mkrepo(tmp_path: Path) -> Path:
    """A repo with one Python service, one `tools` suite that reads it, one
    Rust crate, and stub gate scripts that record who ran and obey a table.

    The scripts are real and really run: a gate that is only ever exercised
    through a mock proves the plan and not the running of it, and the running
    of it is the half B70 is about.
    """
    root = tmp_path / "repo"
    ralph = root / "ops" / "ralph"
    ralph.mkdir(parents=True)
    for rel, text in (
        ("services/svc-a/pkg_a/__init__.py", ""),
        ("services/svc-a/pkg_a/thing.py", "x = 1\n"),
        ("services/svc-a/tests/test_a.py", "import pkg_a\n"),
        (
            "tools/tests/test_atool.py",
            'from pathlib import Path\n'
            'ROOT = Path(__file__).resolve().parents[2]\n'
            'A = ROOT / "services" / "svc-a"\n',
        ),
        ("services/crate-x/Cargo.toml", '[package]\nname = "crate-x"\n'),
        ("services/crate-x/src/main.rs", "fn main() {}\n"),
        ("README.md", "# repo\n"),
    ):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")

    # Each stub appends its argument to a log and exits with whatever
    # $RED_<name> says, so a test can make exactly one gate fail.
    for name in ("runtests.sh", "cargotest.sh"):
        s = ralph / name
        s.write_text(
            '#!/usr/bin/env bash\n'
            'echo "RAN $1" >> "$RALPH_LOG"\n'
            'echo "output of $1 GATE=${RALPH_GATE:-unset}"\n'
            'var="RED_${1//-/_}"\n'
            'exit "${!var:-0}"\n',
            "utf-8",
        )
        s.chmod(0o755)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "base"],
        check=True,
    )
    return root


def run_cli(root: Path, *args: str, **env) -> subprocess.CompletedProcess:
    log = root.parent / "ranlog"  # outside the repo: the gate reads `git status`
    log.write_text("", "utf-8")
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify.py"), "--root", str(root), *args],
        capture_output=True,
        text=True,
        cwd=str(root),
        env={**os.environ, "RALPH_LOG": str(log), **env},
    )


def ran(root: Path) -> list[str]:
    log = root.parent / "ranlog"
    return [l.removeprefix("RAN ") for l in log.read_text("utf-8").split("\n") if l]


# ------------------------------------------------------------------- the plan


def test_the_plan_is_the_notice_plus_the_rust_the_notice_apologises_for(tmp_path):
    """`dependents` prints a standing caveat about Rust because a crate's tests
    live inside the source they test and there is nothing to derive. It is
    still mechanical — a changed file under a directory with a `Cargo.toml` is
    that crate — so the gate can turn the apology into a step."""
    root = mkrepo(tmp_path)
    steps = verify.plan(root, ["services/svc-a/pkg_a/thing.py",
                               "services/crate-x/src/main.rs"])
    assert [s.command for s in steps] == [
        "bash ops/ralph/runtests.sh svc-a",
        "bash ops/ralph/runtests.sh tools",
        "bash ops/ralph/cargotest.sh crate-x",
    ]


def test_a_crate_is_a_cargo_toml_and_not_a_name_written_down(tmp_path):
    """The two crates are `jarvisd` and `jv-act` today. A third one must not
    need this file edited, and a Python service must never be offered to
    cargo."""
    root = mkrepo(tmp_path)
    assert verify.crates(root) == ["crate-x"]
    assert verify.crates(ROOT) == ["jarvisd", "jv-act"]
    assert verify.plan(root, ["services/svc-a/pkg_a/thing.py"]) == verify.plan(
        root, ["services/svc-a/pkg_a/thing.py"]
    )
    assert not any(
        "cargotest" in s.command
        for s in verify.plan(root, ["services/svc-a/pkg_a/thing.py"])
    )


def test_a_path_outside_the_crate_does_not_wake_cargo(tmp_path):
    """`services/crate-xyz` must not be read as a path under `services/crate-x`
    — the prefix test is per path SEGMENT or it claims a sibling."""
    root = mkrepo(tmp_path)
    (root / "services/crate-xyz").mkdir()
    (root / "services/crate-xyz/f.txt").write_text("", "utf-8")
    assert verify.plan(root, ["services/crate-xyz/f.txt"]) == []


def test_editing_the_rust_runner_runs_every_crate(tmp_path):
    """B73's Rust half. `cargotest.sh` is not a crate and is not read by any
    suite — it is how a crate's tests are run at all: the nix dev shell, the
    vendored registry, the cached target dir. Nothing derived can find it, and
    a change to it is every crate or it is nothing."""
    root = mkrepo(tmp_path)
    steps = verify.plan(root, ["ops/ralph/cargotest.sh"])
    assert [s.command for s in steps] == ["bash ops/ralph/cargotest.sh crate-x"]
    assert steps[0].why == ("ops/ralph/cargotest.sh",)


def test_the_rust_runner_pulls_in_the_crates_and_not_the_paths_beside_it(tmp_path):
    """The test the mutation harness earned. `or (runner and p == CARGOTEST_SH)`
    reads as if the guard alone carried it, and a bare `or runner` passes every
    assertion above — because every one of them changes the runner and NOTHING
    else, so "every crate reads the runner" and "every crate reads everything"
    are the same answer. A README edited in the same breath tells them apart:
    `why` is the audit trail printed beside each step, and a step claiming a
    path that has nothing to do with it is the thing that makes a plan
    unreadable."""
    root = mkrepo(tmp_path)
    steps = verify.plan(root, ["ops/ralph/cargotest.sh", "README.md"])
    crate = [s for s in steps if s.command == "bash ops/ralph/cargotest.sh crate-x"]
    assert crate, [s.command for s in steps]
    assert crate[0].why == ("ops/ralph/cargotest.sh",), crate[0].why


def test_a_rust_runner_that_is_not_in_this_repo_names_nothing(tmp_path):
    """A deleted runner is still a changed path, and `bash
    ops/ralph/cargotest.sh jarvisd` is still a command that cannot run."""
    root = mkrepo(tmp_path)
    (root / "ops" / "ralph" / "cargotest.sh").unlink()
    assert verify.plan(root, ["ops/ralph/cargotest.sh"]) == []


def test_the_python_runner_does_not_wake_cargo_and_the_rust_one_does_not_wake_pytest(tmp_path):
    """Two runners, two halves, and neither is a licence for the other. The
    thing that would make this rule unbearable is one gate script edit costing
    every suite AND every crate."""
    root = mkrepo(tmp_path)
    py = [s.command for s in verify.plan(root, ["ops/ralph/runtests.sh"])]
    rs = [s.command for s in verify.plan(root, ["ops/ralph/cargotest.sh"])]
    assert not any("cargotest" in c for c in py), py
    assert not any("runtests" in c for c in rs), rs


def test_every_gate_appears_once_however_many_paths_pulled_it_in(tmp_path):
    """Two changed files in the same service is one run of its suite. The plan
    is a set of commands, and the paths are why, not how many."""
    root = mkrepo(tmp_path)
    steps = verify.plan(
        root, ["services/svc-a/pkg_a/thing.py", "services/svc-a/pkg_a/__init__.py"]
    )
    assert [s.command for s in steps].count("bash ops/ralph/runtests.sh svc-a") == 1
    assert len(steps[0].why) == 2


def test_the_order_is_fixed_so_two_runs_can_be_compared(tmp_path):
    """The per-step seconds this prints are the only measurement anybody has
    of what the gate costs. A plan whose order depended on dict iteration or
    on which path was listed first would make those numbers incomparable."""
    root = mkrepo(tmp_path)
    a = verify.plan(root, ["services/crate-x/src/main.rs",
                           "services/svc-a/pkg_a/thing.py"])
    b = verify.plan(root, ["services/svc-a/pkg_a/thing.py",
                           "services/crate-x/src/main.rs"])
    assert [s.command for s in a] == [s.command for s in b]


# -------------------------------------------------------------- the running


def test_a_green_plan_runs_every_gate_and_exits_zero(tmp_path):
    root = mkrepo(tmp_path)
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    done = run_cli(root)
    assert done.returncode == 0, done.stdout + done.stderr
    assert ran(root) == ["svc-a", "tools"]
    assert "GREEN" in done.stdout


def test_one_red_gate_makes_the_whole_gate_red(tmp_path):
    """The verdict is the AND. This is the entire point of B70: before it, the
    suite you thought of was green and the one that read your change was red,
    and the exit status was the first one's."""
    root = mkrepo(tmp_path)
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    done = run_cli(root, RED_tools="1")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "RED" in done.stdout
    assert "GREEN" not in done.stdout  # a report that says both says nothing
    assert "bash ops/ralph/runtests.sh tools" in done.stdout


def test_a_red_gate_does_not_stop_the_ones_after_it(tmp_path):
    """Fail-fast is the wrong trade for a gate whose whole subject is the
    OTHER red suite you did not know about: stopping at the first one hands
    back exactly the partial picture this replaces, and costs a second full
    run to learn the rest."""
    root = mkrepo(tmp_path)
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    (root / "services/crate-x/src/main.rs").write_text("fn main() {;}\n", "utf-8")
    done = run_cli(root, RED_svc_a="1", RED_crate_x="1")
    assert done.returncode == 1, done.stdout + done.stderr
    assert ran(root) == ["svc-a", "tools", "crate-x"]
    assert done.stdout.count("FAILED") >= 2


def test_the_summary_names_every_gate_with_its_verdict_and_its_price(tmp_path):
    """A run of this is minutes of scrollback from other people's test
    runners. The table at the end is what is actually read, so it has to hold
    the whole answer — and the seconds are in it because nobody has ever been
    able to say what the gate costs without instrumenting it by hand."""
    root = mkrepo(tmp_path)
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    done = run_cli(root, RED_tools="3")
    tail = done.stdout[done.stdout.rindex("verify:") :]
    summary = done.stdout[done.stdout.index("verify: 2 gates") :]
    assert "ok" in summary and "FAILED" in summary
    assert "exit 3" in summary
    assert re.search(r"\d+\.\d s", summary), summary
    assert "do not commit" in tail.lower()


def test_the_output_of_each_gate_reaches_the_terminal_as_it_happens(tmp_path):
    """A 145-second suite behind a captured pipe is a gate nobody can tell
    from a hang, and the pytest line that says WHICH test failed is the only
    thing the author actually needs."""
    root = mkrepo(tmp_path)
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    done = run_cli(root)
    assert "output of svc-a" in done.stdout
    assert "output of tools" in done.stdout


def test_the_gate_does_not_urge_you_to_run_the_suites_it_is_running(tmp_path):
    """`runtests.sh` ends by naming the OTHER suites that read your change. That
    is advice for whoever picked a suite by hand; under the gate it is already
    answered, and a ten-step plan would print it ten times — each one telling
    the reader to run nine suites the gate is in the middle of running. So the
    gate says who it is, and the notice stands down."""
    root = mkrepo(tmp_path)
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    done = run_cli(root)
    assert "GATE=1" in done.stdout, done.stdout
    assert "GATE=unset" not in done.stdout


def test_the_notice_stands_down_only_for_the_gate(tmp_path):
    """The other half, against the real script's own tail with a stub
    interpreter. `RALPH_GATE` unset must still print the notice, or this commit
    has quietly switched B68 off for every author running an inner loop by
    hand — and only the exact string `1` may silence it, because a variable
    that happens to be set to `0` meaning "yes" is a trap."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "python"
    stub.write_text(
        '#!/bin/sh\ncase "$*" in\n'
        "  *pytest*) exit 0 ;;\n"
        "  *dependents.py*) echo ASKED ;;\n"
        "esac\n",
        "utf-8",
    )
    stub.chmod(0o755)
    doc = (ROOT / "ops" / "ralph" / "runtests.sh").read_text("utf-8")
    tail = doc[doc.index("rc=0\n") :]
    script = f'set -euo pipefail\nvenv="{tmp_path}"\nroot="{ROOT}"\nsvc=tools\n' + tail

    for gate, asks in ((None, True), ("", True), ("0", True), ("yes", True), ("1", False)):
        env = {k: v for k, v in os.environ.items() if k != "RALPH_GATE"}
        if gate is not None:
            env["RALPH_GATE"] = gate
        done = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, env=env
        )
        assert done.returncode == 0, done.stderr
        assert ("ASKED" in done.stdout) is asks, (gate, done.stdout)


def test_the_gate_itself_failing_to_spawn_is_a_red_step_and_not_a_traceback(tmp_path):
    """The sibling below proves a MISSING SCRIPT is red, and it proves it
    through bash, which starts fine and exits 127 — so it never reaches the
    branch that catches a spawn failing outright. That branch is what stands
    between "the gate could not run one step" and "the gate produced no
    verdict at all", and a mutation grading found nothing was on it."""
    gone = tmp_path / "never-existed"
    assert verify._spawn(gone, "true") == 127


def test_a_gate_whose_script_is_missing_is_a_failure_and_not_a_crash(tmp_path):
    """`ops/ralph/cargotest.sh` not being there, or nix being absent, must
    come back as a red step with the rest of the plan still run — a traceback
    out of the gate is a verdict nobody gets."""
    root = mkrepo(tmp_path)
    (root / "ops/ralph/cargotest.sh").unlink()
    (root / "services/crate-x/src/main.rs").write_text("fn main() {;}\n", "utf-8")
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    done = run_cli(root)
    assert done.returncode == 1, done.stdout + done.stderr
    assert ran(root) == ["svc-a", "tools"]
    assert "cargotest.sh crate-x" in done.stdout


# --------------------------------------------------- what it refuses to claim


def test_a_clean_tree_is_not_a_green_verdict(tmp_path):
    """The gate runs BEFORE the commit, so an empty plan means it was asked
    after — which is 5a3f1e9 exactly: iteration 89 reported a green that was
    in its working tree while its commit was red. Exiting 0 on "nothing
    changed" would hand that iteration the word it wanted."""
    root = mkrepo(tmp_path)
    done = run_cli(root)
    assert done.returncode == 2, done.stdout + done.stderr
    assert "GREEN" not in done.stdout
    assert "--since" in done.stdout


def test_it_can_be_asked_about_a_commit_instead_of_a_tree(tmp_path):
    """`--since HEAD~1` is the form that works after STEP 4 has already
    happened, and it is the only way this gate can be pointed at what was
    actually committed rather than at what happens to be lying around."""
    root = mkrepo(tmp_path)
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "two"],
        check=True,
    )
    assert run_cli(root).returncode == 2  # the tree is clean again
    done = run_cli(root, "--since", "HEAD~1")
    assert done.returncode == 0, done.stdout + done.stderr
    assert ran(root) == ["svc-a", "tools"]


def test_a_change_no_gate_reads_is_green_and_says_which_paths_it_covered(tmp_path):
    """Editing only the journal is a real and frequent change, and it is not a
    failure. But "no gate ran" and "every gate passed" are different sentences
    and the summary must not print the second one for the first."""
    root = mkrepo(tmp_path)
    (root / "README.md").write_text("# changed\n", "utf-8")
    done = run_cli(root)
    assert done.returncode == 0, done.stdout + done.stderr
    assert ran(root) == []
    assert "no gate" in done.stdout.lower()
    assert "README.md" in done.stdout


def test_the_verdict_says_out_loud_that_it_is_about_the_tree(tmp_path):
    """The other half of 5a3f1e9: the tree was green and `git add` took 31 of
    its 33 files. Nothing here can see the index, so the one honest thing it
    can do is name the paths the verdict covers, so a human or a loop can
    check them against what the commit took."""
    root = mkrepo(tmp_path)
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    (root / "README.md").write_text("# changed\n", "utf-8")
    done = run_cli(root)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "services/svc-a/pkg_a/thing.py" in done.stdout
    assert "README.md" in done.stdout
    assert "commit" in done.stdout.lower()


def test_listing_the_plan_runs_nothing(tmp_path):
    """Four minutes is a real price and `--list` is how you learn it is coming
    before you pay it."""
    root = mkrepo(tmp_path)
    (root / "services/svc-a/pkg_a/thing.py").write_text("x = 2\n", "utf-8")
    done = run_cli(root, "--list")
    assert done.returncode == 0, done.stdout + done.stderr
    assert ran(root) == []
    assert "bash ops/ralph/runtests.sh svc-a" in done.stdout


# ------------------------------------------------------- against the real repo


def test_the_expensive_case_is_the_bus_library_and_it_is_ten_suites():
    """The number B70 was arguing about, asserted rather than remembered."""
    steps = verify.plan(ROOT, ["services/pylib/jarvis_bus/client.py"])
    assert len(steps) == 10
    assert all(s.command.startswith("bash ops/ralph/runtests.sh") for s in steps)


def test_editing_a_runner_is_the_expensive_case_too():
    """The real repo, both halves of B73's argued case. Ten suites is the
    price of `services/pylib/` (241.7 s in the table above) and it is the
    price of the script that runs them, for the same reason: nobody could
    have guessed which of the ten a change there moved."""
    py = [s.command for s in verify.plan(ROOT, ["ops/ralph/runtests.sh"])]
    assert len([c for c in py if c.startswith("bash ops/ralph/runtests.sh ")]) == 10
    rs = [s.command for s in verify.plan(ROOT, ["ops/ralph/cargotest.sh"])]
    assert "bash ops/ralph/cargotest.sh jarvisd" in rs
    assert "bash ops/ralph/cargotest.sh jv-act" in rs


def test_every_gate_this_repo_names_is_planned_by_a_change_to_itself():
    """B73 whole, as ONE claim over the tables instead of five per-kind ones.

    The sentence is: the thing that runs a gate is read by it. It is now
    implemented four times in four shapes — `declared_readers` adds
    `gate.script` to a tuple, `qml_reads` seeds its output set with it, and
    the two runners each carry their own `is_file()` guard — and the way that
    goes wrong is the FIFTH gate, which gets the walk or the declaration and
    silently not the self-read. That is exactly what B72 and B73 each spent an
    iteration closing for one code path, so the claim is made here over every
    table this repo has rather than gate by gate.

    Both halves of the plan count: a gate that is NOT run here (`hudscreens.sh`)
    is planned by being named, which is what `unrun` is for."""
    gates = {
        *(g.script for g in dependents.QML_GATES),
        *(g.script for g in dependents.DECLARED_GATES),
        dependents.RUNTESTS_SH,
        verify.CARGOTEST_SH,
    }
    # Ten: three headless QML gates (the HUD's tests, the bar's, the
    # notifier's), THREE contact sheets — one per shell, since D13 gave the bar
    # the last one — the two declared gates (nixtest, hudscreens), and the two
    # runners. The number is written down so that adding a gate is a deliberate
    # edit here rather than a table that grew unnoticed.
    assert len(gates) == 10, sorted(gates)
    for script in sorted(gates):
        assert (ROOT / script).is_file(), script
        named = [s.command for s in verify.plan(ROOT, [script])]
        named += [g.script for g, _ in dependents.unrun(ROOT, [script])]
        assert any(script in c for c in named), (script, named)


def test_editing_a_qml_gate_brings_that_gate_into_the_verdict():
    """B73's headline through the gate rather than the notice: the two HUD
    gates are the strongest assertions this repo makes about what the HUD
    shows, and neither was in the plan for a change to itself."""
    for name in ("qmltest", "hudshots"):
        cmds = [s.command for s in verify.plan(ROOT, [f"ops/ralph/{name}.sh"])]
        assert f"bash ops/ralph/{name}.sh" in cmds, (name, cmds)


def test_a_hud_change_brings_the_two_qml_gates_into_the_verdict():
    """B69's work is what makes this a gate over the HUD at all: a QML file
    names its subject by type, so neither `qmltest.sh` nor `hudshots.sh` can
    be found by any string in it."""
    cmds = [s.command for s in verify.plan(ROOT, ["shell/jv-hud/core/ReplyState.qml"])]
    assert "bash ops/ralph/qmltest.sh" in cmds
    assert "bash ops/ralph/hudshots.sh" in cmds


def test_the_three_iterations_that_lied_would_now_be_red():
    """B65 and B66 changed jv-compat and ran jv-compat. The gate's plan for
    that change contains the suite that was actually red."""
    cmds = [s.command for s in verify.plan(ROOT, ["services/jv-compat/jv_compat/prefix.py"])]
    assert "bash ops/ralph/runtests.sh jv-compat" in cmds
    assert "bash ops/ralph/runtests.sh tools" in cmds


def test_a_change_to_the_broker_is_cargo_and_the_python_that_reads_it():
    """jarvisd is a crate, so the Rust rule fires; and `tools`/`harness` read
    its source as text, so the Python rule fires too. Neither replaces the
    other and the gate is the union."""
    cmds = [s.command for s in verify.plan(ROOT, ["services/jarvisd/src/main.rs"])]
    assert "bash ops/ralph/cargotest.sh jarvisd" in cmds


def test_the_gate_that_evaluates_the_flake_is_a_step_like_any_other():
    """B72's cheap half. `nixtest.sh` is the only thing in this repo that
    asserts what a module OPTION does to the unit text ares is handed, and
    until now a change to `modules/` named `tools` — which reads those files
    as TEXT, for the fonts check — and never the gate that evaluates them."""
    for rel in ("modules/jarvis-services.nix", "hosts/ares/default.nix"):
        cmds = [s.command for s in verify.plan(ROOT, [rel])]
        assert "bash ops/ralph/nixtest.sh" in cmds, (rel, cmds)
        # …and it is RUN, not merely named. The skipped block is for the gate
        # that is deliberately left out; a gate that ends up in both lists has
        # been planned and disowned in the same breath.
        assert verify.skipped(ROOT, [rel]) == [], rel


def test_the_gate_it_will_not_run_is_printed_above_the_verdict():
    """B72's other half, and the harder one. `hudscreens.sh` reads the HUD and
    is not a step: measured at 3m00s in this sandbox, it boots a compositor and
    takes photographs of the real shell for a human to look at. B74 took
    away half of B72's argument — the screens are no longer rewritten by a run
    that changed nothing — and left the other half standing: a run that DID
    change the HUD puts new PNGs in the tree the plan was computed from.
    That is not a verdict to collect; it is pictures for a human. So it is
    named, above the
    verdict rather than under it, where it cannot be read as a footnote to a
    GREEN."""
    hud = ["shell/jv-hud/core/HeardState.qml"]
    skips = verify.skipped(ROOT, hud)
    assert [script for script, _, _ in skips] == ["ops/ralph/hudscreens.sh"]
    out = "\n".join(verify.report([], hud, skips))
    assert "NOT RUN" in out
    assert out.index("NOT RUN") < out.index("GREEN")
    assert "ops/ralph/hudscreens.sh" in out


def test_a_red_verdict_names_it_too():
    """The failure mode is a reader who takes the summary for the whole story,
    and that reader exists in both directions: a RED that lists two gates has
    to say the third was never asked."""
    step = verify.Step(command="bash ops/ralph/qmltest.sh", why=("x",))
    out = "\n".join(
        verify.report(
            [verify.Result(step=step, status=1, seconds=1.0)],
            ["shell/jv-hud/core/HeardState.qml"],
            verify.skipped(ROOT, ["shell/jv-hud/core/HeardState.qml"]),
        )
    )
    assert "NOT RUN" in out and "RED" in out
    assert out.index("NOT RUN") < out.index("RED")


def test_nothing_is_skipped_when_nothing_skippable_was_touched():
    """The block has to be silent on the ordinary change, or it becomes the
    boilerplate nobody reads — which is the state it is replacing."""
    assert verify.skipped(ROOT, ["services/jv-compat/jv_compat/prefix.py"]) == []
    out = "\n".join(verify.report([], ["services/jv-compat/jv_compat/prefix.py"]))
    assert "NOT RUN" not in out


def test_listing_the_plan_shows_both_what_runs_and_what_will_not():
    """`--list` is the form you read before paying for the run, so it is the
    form that must be complete: the price AND the gate the price does not
    include."""
    done = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify.py"), "--root", str(ROOT),
         "--list", "shell/jv-hud/core/HeardState.qml"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "bash ops/ralph/qmltest.sh" in done.stdout
    assert "bash ops/ralph/hudscreens.sh" in done.stdout



# ------------------------------------------------------------ and the harness


def test_the_wrapper_exists_and_is_what_the_prompt_tells_the_loop_to_run():
    """STEP 3's rule was prose — "run every one it names" — which is option
    (c) of B68, the one already shown not to work. The prompt must name the
    one command that cannot be half-run."""
    assert VERIFY_SH.exists()
    doc = PROMPT.read_text("utf-8")
    assert "ops/ralph/verify.sh" in doc
    assert "verify.py" in VERIFY_SH.read_text("utf-8")


def test_the_gate_and_the_notice_cannot_disagree_about_what_reads_what():
    """`runtests.sh` prints the notice and `verify.sh` enforces it. If they
    derived their answers separately, an author would be told one thing by the
    inner loop and held to another by the gate. They are the same function."""
    src = (ROOT / "tools" / "verify.py").read_text("utf-8")
    assert "import dependents" in src
    assert "dependents.commands" in src
    assert dependents.RUNTESTS == "bash ops/ralph/runtests.sh"
