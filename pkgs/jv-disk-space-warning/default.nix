# jv-disk-space-warning — PLAN G4: warn before the Nix store fills the drive.
#
# There is one filesystem on this machine that matters (CLAUDE.md: "the WD
# Green — models AND the episodic store live here"), and /nix/store is the
# thing on it that grows on its own, unattended, every rebuild — so this
# reads `df` on that path, not a hand-picked mount point.
#
# WHY A DEDUPE STATE FILE. A timer that fires every 30 minutes and notifies
# every single time the disk is still over the threshold would be exactly
# the kind of nag CLAUDE.md's HUD language calls "earned emptiness" against:
# the fact worth telling the user is "you just crossed the line", not "you
# are still over it" repeated forever. So this only notifies on the
# transition — state file absent -> present — and clears it the moment usage
# drops back under threshold, so crossing again later notifies again.
#
# WHY THIS NEVER RUNS nix-collect-garbage OR ANYTHING ELSE. GUARDRAILS.md is
# explicit that this loop must never garbage-collect or delete generations,
# and that discipline extends to what it BUILDS: reclaiming space is a
# decision for a human to make (what to delete, how many generations to
# keep), never something a background timer decides on the user's behalf.
# This script only ever reads `df` and writes its own one-line state file —
# nothing it touches can free a single byte.
{
  writeShellApplication,
  coreutils,
  libnotify,
}:
writeShellApplication {
  name = "jv-disk-space-warning";

  runtimeInputs = [
    coreutils
    libnotify
  ];

  text = ''
    # Overridable so tests can point this at a throwaway path/state file
    # instead of the real disk; JV_DISK_WARN_PCT overrides the threshold.
    path="''${1:-/nix/store}"
    statefile="''${2:-$HOME/.local/state/jv-disk-space-warning/over-threshold}"
    warn_pct="''${JV_DISK_WARN_PCT:-85}"

    pct=$(df --output=pcent "$path" 2>/dev/null | tail -n 1 | tr -dc '0-9') || true
    [ -n "$pct" ] || exit 0

    mkdir -p "$(dirname "$statefile")"

    if [ "$pct" -ge "$warn_pct" ]; then
      if [ ! -e "$statefile" ]; then
        avail=$(df -h --output=avail "$path" 2>/dev/null | tail -n 1 | tr -d ' ')
        notify-send --urgency=critical "JarvisOS disk space" \
          "$path is $pct% full (avail: $avail). Free up space before the store fills the drive." \
          || true
      fi
      touch "$statefile"
    else
      rm -f "$statefile"
    fi
  '';

  meta = {
    description = "Warn once per crossing when the disk holding /nix/store gets full (PLAN G4)";
    mainProgram = "jv-disk-space-warning";
  };
}
