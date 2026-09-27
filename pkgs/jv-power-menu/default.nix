# jv-power-menu — PLAN H2: lock / suspend / reboot / shut down, one key press
# and a themed dmenu pick. `--dmenu` reads this script's four labels off
# stdin and (with no `--config` flag) picks up `/etc/xdg/fuzzel/fuzzel.ini` —
# the SAME themed config `modules/theme.nix` already declares for the plain
# Mod+D launcher — so this menu costs no second palette to keep in step the
# way `modules/super-menu.nix`'s own `jarvis-menu.ini` does for a genuinely
# different UI (a full icon grid, not four words in a list).
#
# THE FIFTH OPTION, "boot Windows", IS NOT HERE. `modules/boot-grub.nix` sets
# `default = 0` and refuses `savedefault`/`default = "saved"` on purpose ("a
# predictable default beats convenience"), and GUARDRAILS marks
# `modules/boot-*.nix` human-review-only. A one-shot reboot into Windows
# needs either that file changed (grub-reboot only affects the next boot if
# the built grub.cfg honours `saved`/`next_entry`, which this config
# deliberately does not wire up) or a new privilege grant letting the desktop
# session write an `efibootmgr -n` NVRAM variable — both are decisions for
# Ofek, not this loop. See PLAN H2b and `docs/optimization-backlog.md` R12.
#
# NO SECOND CONFIRMATION DIALOG. Opening this menu (a deliberate key press)
# and then picking a destructive action (a deliberate selection) already are
# two deliberate steps — the same tier `nixos-rebuild`/PLAN F3's
# `jv-snapshot-restore` sit at (a human running a terminal tool on purpose),
# not a bus-driven `jv-act` capability invariant 3 governs. Cancelling the
# menu (Escape) is fuzzel exiting non-zero with nothing on stdout, which the
# `|| exit 0` below turns into a clean no-op rather than an error.
{
  writeShellApplication,
  fuzzel,
  systemd,
  jv-lock,
}:
writeShellApplication {
  name = "jv-power-menu";

  runtimeInputs = [
    fuzzel
    systemd
    jv-lock
  ];

  text = ''
    choice=$(printf '%s\n' "Lock" "Suspend" "Reboot" "Shut Down" \
      | fuzzel --dmenu --prompt "Power:  ") || exit 0

    case "$choice" in
      Lock)
        exec jv-lock
        ;;
      Suspend)
        exec systemctl suspend
        ;;
      Reboot)
        exec systemctl reboot
        ;;
      "Shut Down")
        exec systemctl poweroff
        ;;
      *)
        exit 0
        ;;
    esac
  '';

  meta = {
    description = "Power menu: lock / suspend / reboot / shut down (PLAN H2)";
    mainProgram = "jv-power-menu";
  };
}
