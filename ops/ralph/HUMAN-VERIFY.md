# Needs Ofek's eyes, ears or hands

The loop appends here whenever it builds something it cannot finish proving on
its own — pressing a key, seeing a screen, speaking, pairing, printing,
launching a game, waving at a sensor. Each line says what to do and what you
should see. Items here are marked `[H]` in PLAN.md: built and auto-tested as
far as honestly possible, awaiting your confirmation.

| item | what to do | what you should see |
|---|---|---|
| F1: niri config declared (`modules/niri.nix`) | After a `nixos-rebuild switch` that includes this change, rename your current `~/.config/niri/config.kdl` out of the way (e.g. `mv ~/.config/niri/config.kdl ~/.config/niri/config.kdl.bak`) — niri's own fallback search (its wiki, "Configuration: Introduction" > Loading) only reads `/etc/niri/config.kdl` when no user config exists, and this loop will not touch a file in your home directory for you. Then log out and back in (or `niri msg action load-config-file` if you stay in the session). | Every keybind you use today still works (F13 app menu, Super+Alt+L lock, the ember focus ring, all the Mod+ binds) — `niri validate -c /etc/niri/config.kdl` already confirms the file is syntactically valid and `bash ops/ralph/nixtest.sh` confirms it is byte-identical to your old file apart from the four theme colours and the output stanzas — but only you can confirm it actually loaded and feels the same. You should also see all three monitors correctly positioned (HDMI-A-1 primary at the left, the two 1080p panels to its right) even on a config niri picked up from `/etc` rather than `~/.config`. If anything looks wrong, `mv ~/.config/niri/config.kdl.bak ~/.config/niri/config.kdl` restores the old behaviour instantly. |
