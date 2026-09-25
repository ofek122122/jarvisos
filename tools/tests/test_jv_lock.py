"""The lock screen (PLAN D3), read as text, in a checkout with no nix.

`pkgs/jv-lock/default.nix` is one wrapper whose whole argv is fixed at build
time, which makes it unusually easy to get wrong in a way nothing notices: a
flag that is simply ABSENT does not fail, it falls back to swaylock's own
default — and swaylock's defaults were chosen for a generic locker, not for
this palette. Three of them are actively wrong here:

  · the background colour defaults to WHITE, so a missing `--color` is a
    full-brightness screen in a dark room the first time an image fails to
    load;
  · the clock format defaults to `%T`, a seconds counter, which repaints
    every output once a second for as long as the machine is locked (§06:
    0 fps when idle);
  · every indicator state whose colour is not declared keeps swaylock's,
    which is off-palette by construction.

And three flags are wrong by being PRESENT — `--screenshots` (with the
`--effect-*` family that exists to soften one), `--grace`, and a forwarded
`"$@"` that would let a caller re-supply either. Those are refusals the file
argues for in prose; this is where the prose is checked.

The colour and face gates over this same file live with the rest of the
desktop's in test_gen_theme_qml.py (it is in PAINTERS there): no literal
colour, no hand-spelled family, every `token "x"` a name theme.toml defines.
What is here is everything else the built argv has to be.

`ops/ralph/nixtest.sh` asks the same questions of the BUILT script — the
bytes that ship — plus the two this cannot see: that the image the lock
screen shows is the same file the wallpaper unit hands swaybg, and that
/etc/pam.d/swaylock still has an auth line in it. Both halves exist on
purpose: this one runs in a bare checkout, that one needs a nix evaluation.
"""

import re

from test_gen_theme_qml import ROOT

LOCK = ROOT / "pkgs" / "jv-lock" / "default.nix"
THEME_MODULE = ROOT / "modules" / "theme.nix"


def source() -> str:
    return LOCK.read_text("utf-8")


def code() -> str:
    """The file without its comment lines.

    Every refusal below is argued for in a comment that NAMES the flag it
    refuses, so a gate reading the whole file would find `--screenshots` in
    the paragraph explaining why there is no `--screenshots`.
    """
    return "\n".join(
        line for line in source().splitlines() if not line.lstrip().startswith("#")
    )


def module_code() -> str:
    """modules/theme.nix without its comment lines.

    The same rule as `code()`, and the same trap: that module argues for the
    lock screen's PAM stack in a paragraph that QUOTES the declaration, so a
    gate reading the whole file would be satisfied by the prose explaining
    the option after somebody deleted the option. Found by mutation — both
    wiring gates below lived through having their subject commented out.
    """
    return "\n".join(
        line
        for line in THEME_MODULE.read_text("utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


# What a flag looks like where it is really being spent: at the start of the
# quoted string that becomes one argv entry. Nix has two string quotes and
# this file uses both — `"--ring-color ${hex line}"` and `''--timestr "%H:%M"''`
# — so a gate that only knew about one of them would read half the argv.
def spends(flag: str) -> bool:
    return re.search(rf"""(?:"|''){re.escape(flag)}(?=[\s"'])""", code()) is not None


# ---------------------------------------------------------------- refusals

FORBIDDEN = {
    # A blurred photograph of your desktop is still your desktop (invariant 7).
    "--screenshots": "shows the desktop it is supposed to be hiding",
    "--effect-blur": "only exists to soften a screenshot",
    "--effect-pixelate": "only exists to soften a screenshot",
    "--effect-greyscale": "only exists to soften a screenshot",
    "--effect-compose": "only exists to soften a screenshot",
    "--effect-custom": "loads a shared object into the lock screen",
    # A stretch in which the lock screen is up and any keypress dismisses it.
    "--grace": "a machine that looks locked and is not",
    # The process must stay in the foreground so its caller can see it exit.
    "--daemonize": "the caller can no longer tell whether it locked",
}


def test_the_lock_screen_refuses_the_flags_it_argues_against():
    spent = {flag: why for flag, why in FORBIDDEN.items() if spends(flag)}
    assert not spent, "pkgs/jv-lock must not spend these:\n" + "\n".join(
        f"{flag}: {why}" for flag, why in sorted(spent.items())
    )


def test_the_lock_screen_refuses_the_short_spelling_of_a_screenshot():
    """`-S` is `--screenshots`, and a gate that only knows the long name is a
    gate somebody walks straight past."""
    assert not spends("-S"), "pkgs/jv-lock spends -S (--screenshots)"
    assert not spends("-f"), "pkgs/jv-lock spends -f (--daemonize)"


def test_the_lock_screen_forwards_no_arguments():
    """swaylock takes the LAST occurrence of a repeated flag, so a forwarded
    argument list would let any caller re-supply every flag above and win."""
    assert '"$@"' not in code(), (
        'pkgs/jv-lock forwards "$@" — a caller could append --grace or '
        "--screenshots and swaylock would honour the later one"
    )


# ------------------------------------------------------- what must be there


def test_the_background_is_declared_because_swaylocks_default_is_white():
    assert spends("--color"), (
        "pkgs/jv-lock declares no --color: swaylock's default background is "
        "white, and it is what you get the moment the image cannot be read"
    )


def test_the_image_is_declared_and_scaled():
    assert spends("--image"), "pkgs/jv-lock shows no image"
    assert spends("--scaling"), (
        "pkgs/jv-lock declares an --image with no --scaling: the lock screen "
        "and the wallpaper unit must fill an output the same way"
    )


def test_an_empty_password_is_not_an_attempt():
    assert spends("--ignore-empty-password"), (
        "without --ignore-empty-password a stray Enter counts as a failed "
        "attempt, and --show-failed-attempts then reports it as one"
    )


def test_the_two_states_that_make_a_correct_password_read_as_wrong_are_shown():
    """Caps Lock and the xkb layout. This machine's owner types Hebrew as
    well as English (personality/voice: Whisper may receive Hebrew), and a
    layout you cannot see turns every password into a wrong one with no way
    to tell why."""
    assert spends("--indicator-caps-lock"), "Caps Lock state is not shown"
    assert spends("--show-keyboard-layout"), "the keyboard layout is not shown"


def test_the_clock_does_not_repaint_every_second():
    """§06: 0 fps when idle. swaylock's default --timestr is %T, which puts a
    seconds counter on every output for as long as the machine is locked."""
    match = re.search(r"--timestr\s+\\?\"([^\"]+)\\?\"", code())
    assert match, "pkgs/jv-lock declares no --timestr, so the clock is %T"
    fmt = match.group(1)
    assert "%T" not in fmt and "%S" not in fmt, (
        f"--timestr is {fmt!r}: a seconds field repaints every output once a "
        "second for as long as the machine is locked"
    )


# Every state the indicator can be in, and the three channels it says it
# with. A channel this file does not paint is not blank — it keeps swaylock's
# own default, which is off-palette by construction, so the identity fails
# exactly in the moments that matter most (being checked, being refused).
STATES = ("", "-clear", "-ver", "-wrong", "-caps-lock")


def test_every_indicator_state_paints_all_three_of_its_channels():
    missing = []
    for state in STATES:
        for channel in ("ring", "inside", "text"):
            # swaylock spells the idle ones `--ring-color` and the rest
            # `--ring-ver-color`; text is `--text-color` / `--text-ver-color`.
            flag = f"--{channel}{state}-color"
            if not spends(flag):
                missing.append(flag)
    assert not missing, (
        "these indicator states keep swaylock's own default colour, which is "
        "not a §06 token:\n" + "\n".join(missing)
    )


def test_typing_and_correcting_are_painted_in_both_states():
    """The highlight segments — the only part of the ring that moves while
    you type — and their Caps Lock variants."""
    for flag in (
        "--key-hl-color",
        "--bs-hl-color",
        "--caps-lock-key-hl-color",
        "--caps-lock-bs-hl-color",
    ):
        assert spends(flag), f"pkgs/jv-lock leaves {flag} at swaylock's default"


# ------------------------------------------------------------------ motion


def test_the_fade_is_gated_on_the_declared_motion_policy():
    """§06's prefers-reduced-motion rule, in the one place where it is
    decidable — `personality/theme.toml`, the same file the HUD's `Motion`
    obeys. A machine that has declared it wants no animation gets a lock
    screen with no `--fade-in` on the command line at all, rather than a fade
    of zero seconds."""
    src = code()
    assert re.search(r'lib\.optional\s*\(\s*!\s*reducedMotion\s*\)\s*"--fade-in', src), (
        "the --fade-in flag is not guarded by the reduced_motion token: a "
        "machine that asked for no motion would still fade"
    )
    assert 'num "motion" "reduced_motion"' in src, (
        "reducedMotion does not come from [motion] in personality/theme.toml"
    )
    assert 'num "motion" "fade_in_ms"' in src, (
        "the fade's length is not read from [motion] in personality/theme.toml"
    )


def test_the_clock_and_the_ring_are_multiples_of_tokens_not_invented_sizes():
    """The two numbers that CAN come from theme.toml do. The indicator's
    radius cannot — §06's [geometry] describes a rectangular panel and says
    nothing about a circle — and it is the only size here allowed to be a
    bare number."""
    src = code()
    assert re.search(r'clockPx\s*=\s*2\s*\*\s*num "type" "readout_px"', src), (
        "the lock screen's clock size no longer derives from the type scale"
    )
    assert re.search(r'ringPx\s*=\s*\d+\s*\*\s*num "geometry" "hairline_px"', src), (
        "the ring's thickness no longer derives from the theme's hairline"
    )


# ------------------------------------------------------------- the wiring


def test_the_lock_screen_is_on_path():
    """Nothing in this flake can press a key: the lock screen is spawned BY
    NAME from the user's own niri config (PLAN D4 moves that file in here),
    so being in systemPackages is the whole delivery mechanism."""
    assert re.search(
        r"environment\.systemPackages\s*=\s*\[[^]]*\bjv-lock\b", module_code(), re.S
    ), "modules/theme.nix no longer puts jv-lock in environment.systemPackages"


def test_the_lock_screen_has_a_pam_stack_to_ask():
    """swaylock is not setuid and cannot read /etc/shadow itself; with no
    /etc/pam.d/swaylock there is no stack to ask and it refuses to start.
    nixpkgs' niri module happens to bring this in today (via
    programs/wayland/wayland-session.nix) — which is exactly why this flake
    declares it too, rather than inheriting the one thing that decides
    whether the screen can ever be unlocked. `ops/ralph/nixtest.sh` reads the
    generated stack; this reads the declaration."""
    assert re.search(
        r"security\.pam\.services\.swaylock\s*=", module_code()
    ), "modules/theme.nix no longer declares the swaylock PAM service"
