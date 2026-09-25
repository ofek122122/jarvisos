# jv-lock — the JarvisOS lock screen (blueprint §06, PLAN D3): swaylock-effects
# with every flag fixed at build time, in the palette the rest of the desktop
# is painted in. It is the first surface on this machine whose job is to say NO
# to whoever is at the keyboard, which is why almost everything below is a
# refusal rather than a decoration.
#
# WHY A STORE SCRIPT AND NOT A CONFIG FILE. swaylock reads
# `$HOME/.swaylock/config`, `$XDG_CONFIG_HOME/swaylock/config` and
# `SYSCONFDIR/swaylock/config` — and this flake can guarantee none of the
# three: the first two are the user's own home (not declared anywhere here,
# which is also why the niri config is still PLAN D4), and the third is the
# sysconfdir the PACKAGE was built with, inside its own store path, not /etc.
# So the configuration IS the binary: one wrapper whose argv cannot drift from
# what was reviewed, the same rule pkgs/jv-bar follows when it pins `niri msg`
# into its wrapper instead of looking one up on $PATH.
#
# THE COLOURS ARE NOT WRITTEN HERE, for the reason modules/theme.nix and
# pkgs/jarvis-wallpaper both give: `personality/theme.toml` says it is the ONLY
# place a colour exists, and every surface that hand-copied the palette drifted
# off it. A tools gate fails if this file grows a literal.
#
# WHAT IT REFUSES, and why each refusal is a decision and not an omission:
#
#   · `--screenshots` (and every `--effect-*` that exists to soften one). A
#     blurred photograph of your desktop is still your desktop — window
#     shapes, the outline of a document, the frame of a video, the fact that
#     you had eleven windows open — held on screen for as long as you are
#     away from the machine. Blur is not redaction. Invariant 7 is that
#     privacy is structural, so the lock screen shows the wallpaper instead:
#     the one image on this desktop that was already being shown to the room.
#
#   · `--grace <seconds>`. A grace period is a stretch in which the lock
#     screen is on the screen and ANY keypress dismisses it with no password.
#     A machine that looks locked and is not is worse than one that is not
#     locked, because you walk away from it.
#
#   · `--daemonize`. The process stays in the foreground, so whatever spawned
#     it — a niri keybind today, a systemd unit when D23 wires
#     `loginctl lock-session` — can see it exit rather than guess.
#
#   · forwarded arguments. There is no `"$@"` on the exec line: swaylock takes
#     the LAST occurrence of a repeated flag, so a caller appending
#     `--grace 60 --screenshots` would silently win every refusal above. If
#     you want a different lock screen, change this file and rebuild — which
#     is the whole point of a declared OS.
{
  lib,
  writeShellApplication,
  swaylock-effects,
  jarvis-wallpaper,
}:
let
  theme = builtins.fromTOML (builtins.readFile ../../personality/theme.toml);

  # Ask theme.toml for a token and throw if it does not have it — the same
  # helper as modules/theme.nix and pkgs/jarvis-wallpaper, for a reason that
  # is sharper here: a colour that silently became "" is an argument swaylock
  # parses as black, and a black ring on a black plate is a lock screen that
  # looks broken at exactly the moment you need to trust it.
  token =
    name:
    theme.palette.${name} or (throw ''
      pkgs/jv-lock spends the colour "${name}", and [palette] in
      personality/theme.toml does not have it. Either the token was renamed
      there (rename it here too — the lock screen is the same identity as the
      desktop behind it) or this file is asking for a colour §06 does not
      define.'');

  face =
    role:
    theme.type."family_${role}" or (throw ''
      pkgs/jv-lock sets the indicator's text in the face for the role
      "${role}", and [type] in personality/theme.toml names no family_${role}.
      A face is identity (invariant 9): named there, bound to a package in
      modules/fonts.nix, spent here.'');

  # Numbers out of theme.toml, by table and key, throwing the same way. The
  # clock's size and the fade's length are not this file's to invent: they are
  # the scale and the motion policy the HUD already obeys.
  num =
    table: key:
    theme.${table}.${key} or (throw ''
      pkgs/jv-lock reads ${table}.${key} out of personality/theme.toml, and it
      is not there. The lock screen's type scale and its motion come from the
      same file as every other surface's.'');

  # --- the tokens this surface spends, and what each one is for ------------
  #
  # A lock screen is a plate on the wallpaper, so it is painted the way a HUD
  # plate is: `ground_deep` inside, a hairline of `line` around it. The ring's
  # IDLE colour is that hairline and nothing louder — nothing is happening,
  # and §06 says a pixel may only be bright because something real is.
  groundDeep = token "ground_deep";
  line = token "line";

  # The two voices, spent exactly as §06 assigns them, which is the one
  # design decision in this file worth arguing about and the reason the states
  # are not all ember: TEAL is your own state, EMBER is the machine doing
  # something. Typing your password is you; checking it is the machine. So a
  # keypress highlights teal and only the verifying ring is ember — which
  # means the one ember moment on this screen is also the only moment
  # something is actually being computed.
  teal = token "teal";
  ember = token "ember";
  emberSoft = token "ember_soft";

  # Status, used only where something is genuinely at risk or needs care:
  # a rejected password is `risk`, and Caps Lock is `warn` because it is the
  # thing that is ABOUT to make you wrong rather than the wrongness itself.
  risk = token "risk";
  warn = token "warn";

  # Words: the clock in `text`, a backspace and a cleared field in the quiet
  # tier (a correction is not news), the keyboard-layout box in `text_2` on
  # `surface`.
  text = token "text";
  text2 = token "text_2";
  text3 = token "text_3";
  surface = token "surface";

  # swaylock wants rrggbb[aa] with no '#', and every colour here is opaque:
  # a translucent lock screen is a lock screen you can read through.
  hex = colour: lib.removePrefix "#" colour;

  monoFamily = face "mono";

  # The clock is a measurement, so it is set in the face theme.toml gives one
  # — and at TWICE the size it gives a readout. That doubling is the one
  # number here that is a judgement rather than a token, and it is the same
  # scale rather than a new one: a HUD readout is read from the desk, at arm's
  # length, and this is read from the doorway. It was looked at, not guessed
  # (see below).
  clockPx = 2 * num "type" "readout_px";

  # A ring one hairline thick disappears at this radius — that is the whole
  # reason this number is not `hairline_px`. Four of them is what it took for
  # the circle to read as a drawn edge, and the edge has to read, because the
  # ring is the CHANNEL every state above travels on: an invisible ring is an
  # invisible "checking" and an invisible "wrong".
  ringPx = 4 * num "geometry" "hairline_px";

  # Motion comes from [motion] in theme.toml, the standing choice the HUD
  # obeys through `Motion` — so a machine that has declared it wants no
  # animation gets a lock screen that appears instantly, with no fade flag on
  # the command line at all rather than a fade of zero seconds.
  reducedMotion = num "motion" "reduced_motion";
  fadeInSeconds = builtins.toString (num "motion" "fade_in_ms" / 1000.0);

  # The circle's size is the one number here with no source at all: §06's
  # [geometry] is the rhythm of a rectangular panel (inset, gap, pad, radius,
  # hairline) and says nothing about a ring in the middle of a screen. So it
  # was LOOKED at rather than reasoned about — swaylock rendered on a nested
  # headless sway at ares' 2560x1440, five combinations photographed and
  # compared (radius x thickness x clock: 64x3x17, 96x3x34, 88x2x26,
  # 120x4x40, 120x4x34). The small ones lose the ring into the wallpaper and
  # put a clock on screen you have to walk up to; 120x4x40 crowds the glyphs
  # against the ring. This is the last one. The journal entry for D3 has the
  # measurements.
  indicatorRadiusPx = 120;

  wallpaper = "${jarvis-wallpaper}/share/backgrounds/jarvisos.png";

  flags = [
    # --- what is behind the indicator ---
    # The wallpaper, scaled the way modules/theme.nix scales it for swaybg, so
    # the screen you lock and the desktop under it are the same picture. (Both
    # inherit PLAN D10: one 1440p PNG on three differently-shaped outputs.)
    "--image ${wallpaper}"
    "--scaling fill"
    # The colour behind the image, and the one flag here that matters even
    # when nothing goes wrong: swaylock's default background is WHITE, so an
    # unreadable or missing image on a 6 GB-VRAM machine that is busy means a
    # full-brightness white screen in a dark room. It is the ground instead.
    "--color ${hex groundDeep}"

    # --- the indicator, idle ---
    # Visible without being touched, and the reason is truthfulness rather
    # than decoration: an empty dark screen with a wallpaper on it cannot be
    # told from a monitor that has gone to sleep or a session that crashed.
    # The ring says the machine is up and holding the door, and the clock in
    # it is a real signal (§06: every pixel encodes one).
    "--indicator-idle-visible"
    "--indicator-radius ${toString indicatorRadiusPx}"
    "--indicator-thickness ${toString ringPx}"
    "--clock"
    # %H:%M, not swaylock's default %T. The default puts a seconds counter on
    # screen, which repaints every output once a second for as long as the
    # machine is locked — the exact opposite of §06's "0 fps when idle", and a
    # cost paid all night. A minute is also all a clock you glance at needs.
    ''--timestr "%H:%M"''
    ''--datestr "%a %d %b"''
    "--font ${lib.escapeShellArg monoFamily}"
    "--font-size ${toString clockPx}"
    "--text-color ${hex text}"
    "--ring-color ${hex line}"
    "--inside-color ${hex groundDeep}"
    # The line between the inside and the ring is the inside, by flag rather
    # than by colour: one fewer value to keep in step with the palette.
    "--line-uses-inside"
    # The gaps between highlight segments are the plate showing through.
    "--separator-color ${hex groundDeep}"

    # --- you, typing ---
    "--key-hl-color ${hex teal}"
    "--bs-hl-color ${hex text3}"
    "--inside-clear-color ${hex groundDeep}"
    "--ring-clear-color ${hex text3}"
    "--text-clear-color ${hex text3}"

    # --- the machine, checking ---
    "--inside-ver-color ${hex emberSoft}"
    "--ring-ver-color ${hex ember}"
    "--text-ver-color ${hex ember}"

    # --- no ---
    # The plate stays a plate: the ring and the word carry the refusal, so a
    # wrong password does not turn the middle of the screen into a red disc.
    "--inside-wrong-color ${hex groundDeep}"
    "--ring-wrong-color ${hex risk}"
    "--text-wrong-color ${hex risk}"
    # Count them out loud. Someone tried while you were away, and that is
    # yours to know.
    "--show-failed-attempts"

    # --- the two states that make a correct password read as wrong ---
    # Caps Lock on the indicator, in `warn`, plus its own word; and the xkb
    # layout while typing, because this machine's owner types Hebrew as well
    # as English and a Hebrew layout turns every password into a wrong one
    # with no way to see why.
    "--indicator-caps-lock"
    "--inside-caps-lock-color ${hex groundDeep}"
    "--ring-caps-lock-color ${hex warn}"
    "--text-caps-lock-color ${hex warn}"
    "--caps-lock-key-hl-color ${hex warn}"
    "--caps-lock-bs-hl-color ${hex text3}"
    "--show-keyboard-layout"
    "--layout-bg-color ${hex surface}"
    "--layout-border-color ${hex line}"
    "--layout-text-color ${hex text2}"

    # An accidental Enter is not an authentication attempt: without this it
    # counts as one, and with --show-failed-attempts it would also be
    # reported as somebody having tried.
    "--ignore-empty-password"
  ]
  ++ lib.optional (!reducedMotion) "--fade-in ${fadeInSeconds}";
in
writeShellApplication {
  name = "jv-lock";

  text = ''
    exec ${swaylock-effects}/bin/swaylock \
      ${lib.concatStringsSep " \\\n  " flags}
  '';

  meta = {
    description = "JarvisOS lock screen — swaylock-effects in the §06 palette";
    mainProgram = "jv-lock";
  };
}
