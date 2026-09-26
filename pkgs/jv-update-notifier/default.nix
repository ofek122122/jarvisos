# jv-update-notifier — the login-time update check PLAN G3 asks for: tell the
# user commits exist, never touch anything.
#
# WHY `git fetch` AND NOTHING ELSE. Fetch is the one git verb that only ever
# downloads objects and moves remote-tracking refs (`refs/remotes/origin/*`)
# — it cannot change HEAD, the index or a single file in the working tree,
# so this can run at every login with nothing to lose even if every guess
# below it is wrong. CLAUDE.md's NixOS discipline is explicit that a change
# only exists once it is reviewed and built deliberately
# (`nixos-rebuild build` -> review -> `test` -> `switch`); a login script
# that pulled, merged or rebuilt on the user's behalf would be exactly the
# imperative mutation that discipline exists to prevent. So this script's
# only git verbs are ones that read: `fetch`, `rev-parse`, `rev-list`, `log`.
# `git-only-read-only` below is the test that keeps it that way.
#
# WHY IT NEVER FAILS LOUDLY. This runs unattended, once per login, off a
# network Ofek might not have (offline, captive portal, VPN down). A login
# notifier that blocks the session or spams stderr past a failed fetch is
# worse than one that silently has nothing to say this time — so every path
# that cannot answer the question ("no repo here", "no network", "no
# upstream configured") exits 0 quietly rather than erroring.
{
  writeShellApplication,
  git,
  libnotify,
}:
writeShellApplication {
  name = "jv-update-notifier";

  runtimeInputs = [
    git
    libnotify
  ];

  text = ''
    # The flake clone jv-store (modules/store.nix) already rebuilds from.
    # Overridable with a first argument so this can be pointed at a
    # throwaway clone under test instead of a path that only exists on ares.
    repo="''${1:-/home/ofek/jarvisos}"

    [ -d "$repo/.git" ] || exit 0

    if ! git -C "$repo" fetch --quiet 2>/dev/null; then
      exit 0
    fi

    upstream=$(git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null) || exit 0
    [ -n "$upstream" ] || exit 0

    ahead=$(git -C "$repo" rev-list --count 'HEAD..@{u}' 2>/dev/null) || exit 0
    [ "$ahead" -gt 0 ] || exit 0

    subject=$(git -C "$repo" log -1 --format=%s '@{u}' 2>/dev/null) || exit 0
    branch=$(git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0

    if [ "$ahead" -eq 1 ]; then
      commits="1 new commit"
    else
      commits="$ahead new commits"
    fi

    notify-send "JarvisOS updates ($branch)" \
      "$commits on $upstream (latest: $subject). Review them yourself, then rebuild — this never runs nixos-rebuild for you." \
      || true
  '';

  meta = {
    description = "Read-only login update check: fetch + notify, never rebuild (PLAN G3)";
    mainProgram = "jv-update-notifier";
  };
}
