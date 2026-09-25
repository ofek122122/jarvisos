#!/usr/bin/env bash
# ops/ralph/runtests.sh <service> — run a Python service's test suite against the
# WORKTREE source. Nix build has doCheck=false (tests need model weights), so the
# loop's verify gate uses this instead. Reuses a cached venv layered over the
# service's own nix env (which already has every dependency); pytest imports the
# worktree package because the service dir is on sys.path ahead of site-packages.
#
# Usage:  bash ops/ralph/runtests.sh jv-brain
#         bash ops/ralph/runtests.sh jv-voice
# Services: jv-brain jv-ears jv-voice jv-context jv-guard jv-compat
#           jv-hud-bridge pylib tools harness
#
# `--origin <module> <service>` runs no tests: it prints the FILE this
# service's suite would import `<module>` from, resolved by the same
# interpreter, cwd and PYTHONPATH the suite gets (nothing, if there is no such
# file). It exists because "which copy of this module do the tests read" is a
# question about this script and nothing else can answer it honestly —
# tools/mutate.py asks it when a canary lives, to tell a file no test touches
# apart from a file the tests import from somewhere else (PLAN B58).
set -euo pipefail

origin_mod=""
if [ "${1:-}" = "--origin" ]; then
  origin_mod="${2:?usage: runtests.sh --origin <module> <service>}"
  shift 2
fi

svc="${1:?usage: runtests.sh <service>}"
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
testdir="$root/services/$svc"
[ -d "$testdir" ] || testdir="$root/$svc"   # harness lives at repo root
[ -d "$testdir/tests" ] || { echo "no tests dir for $svc ($testdir)"; exit 2; }

# Resolve a python env that carries this service's deps, from its installed unit.
unit=$(ls /etc/systemd/system/$svc.service /etc/systemd/user/$svc.service 2>/dev/null | head -1 || true)
if [ -n "$unit" ]; then
  env=$(dirname "$(grep -o '/nix/store/[^"]*-env/bin/[^" ]*' "$unit" | head -1)")
else
  # fall back to any jarvis python env on the machine
  env=$(dirname "$(ls /nix/store/*-python3-*-env/bin/python | head -1)")
fi
[ -x "$env/python" ] || { echo "could not find a python env for $svc"; exit 2; }

venv="$HOME/.cache/ralph-venv/$svc"
if [ ! -x "$venv/bin/pytest" ]; then
  "$env/python" -m venv --system-site-packages "$venv"
  "$venv/bin/pip" install -q pytest pytest-asyncio
fi

# Every jv-* service imports jarvis_bus, and until now it imported the one in
# the nix store: `python -m pytest` puts the CWD first, which is the service's
# own dir, so a worktree change to services/pylib was invisible to every suite
# but pylib's own. A gate that tests the tree must test the tree it has.
export PYTHONPATH="$root/services/pylib${PYTHONPATH:+:$PYTHONPATH}"

cd "$testdir"

# Asking where a module comes from must resolve it EXACTLY as the suite does,
# so it runs from the same directory with the same path — `-c` seeds sys.path
# with the cwd just as `-m pytest` does — and it stops here: a probe that
# built jarvisd would be paying the suite's setup cost to answer a question
# about imports.
if [ -n "$origin_mod" ]; then
  # Prints the file or prints nothing — never a traceback. `find_spec` RAISES
  # (on a missing parent package, or a name that is not a module at all)
  # rather than returning None, and a suite that has never heard of the module
  # is an ordinary answer here, not a failure to ask.
  exec "$venv/bin/python" -c 'import importlib.util, sys
try:
    spec = importlib.util.find_spec(sys.argv[1])
except (ImportError, AttributeError, ValueError):
    spec = None
print(spec.origin if spec and spec.origin else "")' "$origin_mod"
fi

# jarvisd binary for tests that spawn the real broker
export JARVISD_BIN="${JARVISD_BIN:-$(nix build "$root#jarvisd" --no-link --print-out-paths 2>/dev/null)/bin/jarvisd}"

rc=0
"$venv/bin/python" -m pytest tests -q || rc=$?

# The suite you asked for is not the set of suites that read what you changed,
# and for three iterations running nobody could see the difference (PLAN B68).
# Invariant 1 forbids one service importing another, so every claim this repo
# makes about a RELATION between two of its parts is made by a THIRD suite
# reading them both — and `tools` reads six services, the schemas and the whole
# HUD. So the gate asks, every run, instead of hoping the author guessed:
# `tools/dependents.py` derives the readers from the suites themselves.
# It is advice, not a verdict — the exit status is still pytest's — and it
# prints nothing at all on a clean tree.
# …unless the GATE is what called us (ops/ralph/verify.sh, PLAN B70), which
# derived this same list before it ran anything and is working through it: the
# advice is for whoever chose a suite by hand, and printing it once per step
# would have the gate urging the reader to run the suites it is running.
if [ "${RALPH_GATE:-}" != "1" ]; then
  "$venv/bin/python" "$root/tools/dependents.py" --root "$root" --changed \
    --exclude "$svc" --quiet-when-empty || true
fi

exit $rc
