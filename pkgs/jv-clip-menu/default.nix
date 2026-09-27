# jv-clip-menu — PLAN H3: clipboard history, the first "super-menu mode" —
# a themed dmenu pick over cliphist's own history.
#
# cliphist already IS the history: `modules/clipboard.nix` runs two
# `wl-paste --watch cliphist store` daemons (text and image, cliphist's own
# documented pair — one `wl-paste --watch` per MIME class, since a single
# watcher only ever sees the type it was started with) that fill a small
# sqlite-backed store under `$XDG_CACHE_HOME/cliphist`. This script is only
# the READ half: list what's there, let fuzzel pick one, decode it back to
# real bytes, put it on the clipboard. It never calls `wl-paste` itself —
# that would make every press of the keybind add "opened the clipboard menu"
# as a new clipboard entry, which is the same class of bug F5c's `[H]` list
# warns about (a sensor observing its own output). Wayland-only like every
# other surface in this repo (CLAUDE.md: "Wayland only, never X11-first") —
# `wl-copy`, never `xclip`/`xsel`.
#
# `cliphist list`'s own output is one line per entry, an opaque id followed
# by a tab and a truncated preview — the id is what `cliphist decode` needs
# back on stdin, not the preview text alone, so the WHOLE line fuzzel returns
# is piped through unchanged rather than re-parsed here.
#
# NO SECOND CONFIRMATION DIALOG, same reasoning as `pkgs/jv-power-menu`:
# opening this menu and picking an entry are already two deliberate steps,
# and pasting a clipboard entry is not a destructive action invariant 3's
# jv-act tier would need to gate. Cancelling (Escape) is fuzzel exiting
# non-zero with nothing on stdout, turned into a clean no-op by `|| exit 0`;
# an empty selection (nothing typed, nothing matched) is caught explicitly
# since fuzzel can exit 0 with an empty line rather than non-zero.
{
  writeShellApplication,
  cliphist,
  fuzzel,
  wl-clipboard,
}:
writeShellApplication {
  name = "jv-clip-menu";

  runtimeInputs = [
    cliphist
    fuzzel
    wl-clipboard
  ];

  text = ''
    choice=$(cliphist list | fuzzel --dmenu --prompt "Clipboard:  ") || exit 0
    [ -z "$choice" ] && exit 0
    printf '%s' "$choice" | cliphist decode | wl-copy
  '';

  meta = {
    description = "Clipboard history picker over cliphist (PLAN H3)";
    mainProgram = "jv-clip-menu";
  };
}
