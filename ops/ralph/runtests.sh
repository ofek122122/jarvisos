#!/usr/bin/env bash
# ops/ralph/runtests.sh <service> — run a Python service's test suite against the
# WORKTREE source. Nix build has doCheck=false (tests need model weights), so the
# loop's verify gate uses this instead. Reuses a cached venv layered over the
# service's own nix env (which already has every dependency); pytest imports the
# worktree package because the service dir is on sys.path ahead of site-packages.
#
# Usage:  bash ops/ralph/runtests.sh jv-brain
#         bash ops/ralph/runtests.sh jv-voice
# Services: jv-brain jv-ears jv-voice jv-context jv-guard jv-compat pylib harness
set -euo pipefail

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

# jarvisd binary for tests that spawn the real broker
export JARVISD_BIN="${JARVISD_BIN:-$(nix build "$root#jarvisd" --no-link --print-out-paths 2>/dev/null)/bin/jarvisd}"

cd "$testdir"
exec "$venv/bin/python" -m pytest tests -q
