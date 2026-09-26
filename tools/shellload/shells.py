"""What a real quickshell is asked to LOAD, and on which monitors (PLAN D41).

Data and pure helpers, stdlib only. `tools/shellload/load.py` executes it and
`tools/tests/test_shellload.py` reads it, so the shell list, the monitor sizes,
the compositor's config, the private session bus and the one notification this
gate sends are stated once — and anything the harness DECIDES with lives here,
where a test with no compositor can still run it.

WHY THIS GATE EXISTS AT ALL, which is a measurement and not a guess. Until it,
`ops/ralph/hudscreens.sh` was the only gate in this repo that ran a real
quickshell, and `shell/jv-hud/shell.qml` was the only `shell.qml` any engine
ever opened. The bar's and the notifier's were qmllint-clean and nothing more:
every shot harness deletes `shell.qml` from its stage on purpose, because
ShellRoot, PanelWindow and the layer-shell attached properties cannot resolve
outside quickshell's own binary. So the two surfaces that reserve screen space
and take this machine's `org.freedesktop.Notifications` name had their
outermost file held only by a linter — and the D34/D39 shape, a binding that
throws and leaves the surface plausible, is exactly what a linter cannot see.

WHAT IT IS, and the price is the point. One headless sway, one quickshell per
shell, a wait on quickshell's own `Configuration Loaded`, and the D39 scan of
what it said. No pictures, no sheet to compare, and none of `hudscreens.sh`'s
97.7 s idle probe — which is 50% of that harness and most of why it cannot be
run unattended. This is a VERDICT a gate can collect, so `verify.sh` runs it.

WHAT IT IS NOT, and every line of this is a limit somebody will otherwise read
as coverage:

  · It is not a picture. Nothing here looks at a pixel. A surface that loaded
    cleanly and drew in the wrong corner passes this and fails `hudscreens.sh`.
  · A shell with NOTHING TO SAY evaluates almost none of its own QML. The HUD
    runs with no jarvisd, so every plate is unmapped and `Bus` is blind; the
    bar runs with no niri, so `linkUp` is false and the workspaces row builds
    no delegates. What this covers for those two is the outermost file, the
    per-screen `Variants` delegate, and every binding that is evaluated
    whatever the state — which is where D34's and D39's faults both were, and
    is not the same as the whole shell.
  · The notifier is the exception, and deliberately: it has a real client
    here. `NOTIFY` below is sent to it over the private bus by an ordinary
    D-Bus caller, so the corner maps, the `Repeater` builds a `Toast`, and
    the scan covers the plate. It is also the only thing in this repo that
    has ever proved the D-Bus name is claimed and answered (PLAN D22).
  · It says nothing about frames, GPU cost, or how anything reads. Software
    rendering on a headless backend, exactly as `hudscreens.sh` disclaims.
"""

import dataclasses
import pathlib
import tomllib

# The line quickshell's own logger writes once the root component is built and
# every window it declares has been created. Waiting on it is what makes the
# scan below meaningful: a log nobody wrote reads clean, and an engine that
# died on a syntax error never gets here. It is quickshell's string, recorded
# from quickshell 0.3.0 rather than read off its source, because what this has
# to match is what it prints.
READY = "Configuration Loaded"

# How long a shell is left running after it says it is loaded. Nothing is
# measured in it; it is there because a binding queued behind the first frame
# has to be given the frame. Small on purpose — the whole gate's claim over
# `hudscreens.sh` is that it costs seconds instead of minutes.
HOLD_S = 2.0

# How long a shell may take to say READY before this gives up. Generous: the
# first quickshell of a run pays for a cold Qt and a cold font cache, and a
# timeout that fires on a slow machine is a gate that gets switched off.
READY_TIMEOUT_S = 30.0


@dataclasses.dataclass(frozen=True)
class Shell:
    """One shell this gate loads, as the flake attribute that builds it.

    `root` is the directory in THIS repository that holds its `shell.qml`.
    Quickshell prints the paths it throws on relative to the root it loaded —
    which at runtime is a store path — so `core/MotionPolicy.qml` is three
    directories here and one of them is wrong. Told the root, the report names
    a file a reader can open.

    It lives here rather than in the script for the reason
    `tools/hudscreens/sheet.py` gives for its own `SHELL_ROOT`: this gate's one
    claim is that it loads the SHIPPED binary and stages nothing, and
    `test_the_gate_loads_the_shipped_binaries_and_stages_nothing` enforces that
    by refusing `shell/` in any line the script executes. A `cp` out of the
    working tree is exactly how this would stop being a gate on what ships.

    `env` is the variable the script hands the realized binary over in, and
    `wake` is whether anything gives this shell something real to do once it
    has loaded. Only the notifier has one — see NOTIFY.

    `reserves_top` is whether this surface takes a strip off the top of every
    monitor, which only the bar does. It is what the mapping check below asks
    the compositor about, and it is a per-shell property because the answer is
    the opposite for the other two — the same IPC call is their assertion in
    the other direction.

    It is spelled as the fact rather than as `exclusionMode`, and that is
    measured: the bar built with `ExclusionMode.Ignore` and its zone left
    alone STILL reserved all 31 px. What decides the strip is `exclusiveZone`
    (and the anchors); `exclusionMode` is about whose zones this surface is
    positioned around. All three `shell.qml` say otherwise in a comment
    (PLAN D45).
    """

    attr: str
    root: str
    env: str
    wake: bool = False
    reserves_top: bool = False


SHELLS = (
    Shell(attr="jv-hud", root="shell/jv-hud", env="JV_HUD_BIN"),
    Shell(attr="jv-bar", root="shell/jv-bar", env="JV_BAR_BIN", reserves_top=True),
    Shell(attr="jv-notify", root="shell/jv-notify", env="JV_NOTIFY_BIN", wake=True),
)


# ------------------------------------------------------------ the compositor

# ares' monitors, headlessly, and the names are the backend's rather than
# ares' — the compositor is real and the monitors are not.
#
# THREE of them, and that is the load-bearing part rather than the sizes: all
# three shells build one surface per `Quickshell.screens` entry, so a single
# output would load one delegate and call it a shell. D37's fault (every plate
# in the corner rebuilt when any one of them changed) and D32's (a row sized
# against the wrong monitor's width) are both per-surface.
#
# Stated again rather than imported from `tools/hudscreens/sheet.py`, and held
# equal to it by `test_the_monitors_are_the_ones_the_screen_sheet_uses` — a
# test that reads both, which is what invariant 1 asks for. The alternative was
# an import, and it would have made every edit to the screen sheet's noise
# floor wake this gate: `sheet.py` is a declared read of a 3-minute harness,
# and a gate that is mostly noise is a gate somebody switches off.
OUTPUTS = [
    {"name": "HEADLESS-1", "width": 2560, "height": 1440, "x": 0},
    {"name": "HEADLESS-2", "width": 1920, "height": 1080, "x": 2560},
    {"name": "HEADLESS-3", "width": 1920, "height": 1080, "x": 4480},
]


def sway_config() -> str:
    """The compositor the shells are loaded on, as a config file.

    Here rather than in the script so a test can read the same text the
    compositor was given.
    """
    lines = [
        # No Xwayland: nothing here is an X11 client, and starting one is one
        # more thing that can fail for reasons unrelated to a shell.
        "xwayland disable",
        # No keybindings and no decorations. There is no user in this session.
        "default_border none",
    ]
    for out in OUTPUTS:
        lines.append(
            f"output {out['name']} mode {out['width']}x{out['height']} "
            f"pos {out['x']} 0"
        )
    return "\n".join(lines) + "\n"


# ------------------------------------------------- did it MAP (PLAN D44)
#
# "It loaded" is not "it mapped", and until D44 nothing asked the second
# question for two of the three shells. `READY` is quickshell saying the root
# component built and its windows were created — a `PanelWindow` whose
# layer-shell attached properties failed to ATTACH would still get that line,
# and `hudscreens.sh` was the only thing in this repo that ever looked at a
# surface (through `grim`, for the HUD alone).
#
# There is one verdict available here for the price of an IPC call, and it is
# the exact check `tools/hudscreens/shoot.py` already makes in the other
# direction. sway shrinks each workspace's rect by every layer surface's
# exclusive zone, so `swaymsg -t get_workspaces` is a direct measurement of
# what a shell reserved:
#
#   · jv-bar sets `exclusionMode: ExclusionMode.Normal` and `exclusiveZone:
#     surface.implicitHeight` on a surface anchored top+left+right, so the
#     usable area on EVERY output must be exactly `BAR_STRIP_PX` shorter than
#     the monitor. That is a PROOF OF MAPPING: an unmapped surface reserves
#     nothing, so this number cannot appear unless the strip is really there.
#   · jv-hud and jv-notify take nothing, so the usable area must be the
#     monitor, untouched. That is a REFUTATION and not a proof — see the two
#     paragraphs below, because what it can refute is much narrower than it
#     looks and reading it as coverage would be the whole mistake.
#
# Each shell is checked THREE times — before it starts, while it is up, and
# after it is stopped — so the bar's verdict is full → shrunk → full. Two of
# those are the control: a strip that was already missing before the bar
# started was not the bar's, and one that never came back was never a layer
# surface's zone at all.
#
# THE INSTRUMENT IS LIVE IN BOTH DIRECTIONS, by injection rather than by
# reading the code:
#   · `exclusiveZone: 0` on the bar — exit 1, naming all three monitors and
#     both numbers, while every other thing about that run stayed green: the
#     shell loaded in 0.40 s, `Configuration Loaded` arrived, and the D39 scan
#     said nothing threw on any of the three logs. A bar that silently stopped
#     reserving its strip is invisible to every other gate in this repo.
#   · a 100 px zone on the notifier — exit 1, and the observed areas were
#     2560x1340 and 1920x980, which is the zone taken off the BOTTOM edge it
#     is anchored to. So "took nothing" is a sentence that can be false.
#
# AND THE LIMIT, WHICH IS THE SHARPEST THING MEASURED HERE AND IS NOT THE ONE
# ANYBODY WOULD GUESS. That second injection only bit once the surface was
# ALSO made `visible: true`. With the notifier's own `visible:
# Notifications.anyLit` — false when the window is created, true a moment
# later when the gate's notification arrives — the identical 100 px zone is
# silently never published, and the compositor reports every monitor whole.
# A conditionally-visible `PanelWindow` gets its exclusive zone at creation
# and a zone declared while it was invisible does not reach the compositor.
# Both of these shells are conditionally visible (`Notifications.anyLit`,
# `selfTest || stack.anyLit`), and the HUD with no jarvisd is never lit at
# all, so no surface of its is ever created in this gate.
#
# So, plainly: the bar's reading is a proof. The notifier's refutes a zone on
# a surface that was mapped when it was born. The HUD's refutes nothing about
# today's HUD — it is the line that notices the day the corner becomes
# always-mapped and takes space, which is the future the bar already is. It is
# kept for the same reason `tools/hudscreens/shoot.py` keeps its own version
# of this check, and for one more: it is the CONTROL that makes the bar's
# 31 px the bar's.


def bar_strip_px(theme_toml: str) -> int:
    """How many pixels of every monitor's top edge the bar takes.

    A COPY of `shell/jv-bar/shell.qml`'s `implicitHeight: Theme.labelPx +
    Theme.padPx * 2`, stated here in the tokens it is derived from, and held
    equal to the QML by `test_the_strip_this_gate_expects_is_the_one_the_bar_
    declares` — a third file that reads both, which is what invariant 1 asks
    of every claim about a relation between two parts of this repo.

    It is a copy for the same reason `OUTPUTS` is: the alternative is an
    import, and there is nothing to import — the number the bar uses only
    exists inside a running QML engine, out of a `Theme.qml` generated from
    these two tokens. Asking the toml is asking the one file the generated
    singleton is made from.

    Derived rather than declared on BOTH sides, which is the part worth
    keeping: the bar's height is "one label with §06's padding above and
    below", so a gate that pinned the number 31 would go red on a change to
    the type scale that the bar handled perfectly.
    """
    tokens = tomllib.loads(theme_toml)
    return int(tokens["type"]["label_px"]) + int(tokens["geometry"]["pad_px"]) * 2


def theme_toml_path() -> pathlib.Path:
    """`personality/theme.toml`, the one file the tokens above come from.

    This module is `tools/shellload/shells.py`, so the repository is two
    directories up. A declared read of this gate already (`DECLARED_GATES` in
    `tools/dependents.py`), because the generated `Theme.qml` in every shell is
    checked against it at build time.
    """
    return pathlib.Path(__file__).resolve().parents[2] / "personality" / "theme.toml"


def usable_areas(reserved_top_px: int) -> dict[str, tuple[int, int]]:
    """What each output's usable area must be, given a strip taken off the top.

    Keyed by output name and in the shape `swaymsg -t get_workspaces` reports,
    so the comparison in `load.py` is one `==` between two dicts and a failure
    can print both.
    """
    return {
        out["name"]: (out["width"], out["height"] - reserved_top_px)
        for out in OUTPUTS
    }


# How long the compositor is given to agree. A layer surface is configured
# over the wayland protocol AFTER the client has drawn, and on the way down it
# is unmapped after the process is gone — neither is synchronous with anything
# this driver can see, so both directions are polled. Short: every one of these
# waits is time added to a gate whose whole argument is that it costs seconds.
MAPPED_TIMEOUT_S = 8.0
MAPPED_POLL_S = 0.1


# ---------------------------------------------------------- the private bus
#
# MEASURED, and it is the reason this file has a D-Bus section at all. Run
# without `DBUS_SESSION_BUS_ADDRESS` unset, `jv-notify` reaches the USER'S OWN
# live session bus and tries to claim `org.freedesktop.Notifications` on it —
# the observed line was
#
#     WARN quickshell.service.notifications: Could not register notification
#     server at org.freedesktop.Notifications, presumably because one is
#     already registered.
#
# which is a test harness losing a race it must never have been in. Had it won,
# a gate would have taken over the notifications of the desktop it was running
# inside. So the bus is this run's own, always.
#
# NO `<servicedir>`, which is the other half. `dbus-run-session` inherits the
# machine's service directories, and the first version of this started
# xdg-desktop-portal, xdg-desktop-portal-gnome, xdg-desktop-portal-gtk and
# gnome-keyring inside a gate about three QML files — none of them from this
# flake, all of them noise in the log this scans. A bus with no activatable
# services can start nothing that was not asked for.
DBUS_CONF = """<!DOCTYPE busconfig PUBLIC \
"-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN" \
"http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:tmpdir=%(tmp)s</listen>
  <policy context="default">
    <allow own="*"/>
    <allow send_destination="*"/>
    <allow receive_sender="*"/>
  </policy>
</busconfig>
"""


def dbus_conf(tmpdir: str) -> str:
    """The session bus config, listening inside this run's own directory."""
    return DBUS_CONF % {"tmp": tmpdir}


# ------------------------------------------------------------ the notifier
#
# The one shell here that can be given something real to do without a service
# this gate would have to start. Its whole input is the session bus, so an
# ordinary D-Bus client is the whole of its world — and there is one above.

NOTIFY_DEST = "org.freedesktop.Notifications"
NOTIFY_PATH = "/org/freedesktop/Notifications"

# What is sent. `app_name` names this gate rather than anything real, because a
# notification that claimed to be from Jarvis is the one thing the notifier's
# own comment says a corner must never let a stranger do. The body is long
# enough that the plate has to wrap it, which is the binding most likely to
# throw on a value it did not expect.
NOTIFY = {
    "app_name": "jv-shellload",
    "replaces_id": 0,
    "app_icon": "",
    "summary": "the load probe",
    "body": "One notification, sent by an ordinary D-Bus client, so the corner "
    "maps and the plate is built by the same Repeater a real message goes "
    "through.",
    "actions": [],
    "hints": {},
    "expire_timeout": 5000,
}

# What the daemon must say it can do, asked through the protocol rather than
# read out of the QML. `Notifications.qml` calls its capability set an honesty
# declaration — every capability false unless these pixels really do it — and
# until this gate nothing had ever asked the running daemon whether the
# declaration survived into the bus name.
#
# `actions` is the one that matters: the surface's input region is empty, so an
# action is a promise these pixels cannot keep, and a daemon that advertised
# one would have every app on this machine offering buttons that do nothing.
CAPABILITIES_REQUIRED = ("body",)
CAPABILITIES_REFUSED = (
    "actions",
    "action-icons",
    "body-markup",
    "body-hyperlinks",
    "body-images",
)


def gdbus_call(method: str, args: list[str]) -> list[str]:
    """`gdbus call` for one method on the notification daemon."""
    return [
        "call",
        "--session",
        "--dest",
        NOTIFY_DEST,
        "--object-path",
        NOTIFY_PATH,
        "--method",
        f"{NOTIFY_DEST}.{method}",
        *args,
    ]


def notify_args(spec: dict | None = None) -> list[str]:
    """`NOTIFY` as gdbus' own argument syntax, in the order the spec's
    `Notify` declares its parameters.

    Built rather than written out so the sent notification and the one a test
    reads are the same dict. gdbus parses GVariant text, so a string is quoted
    and an empty array is typed — `@as []` — because an untyped `[]` is
    ambiguous and gdbus refuses it.
    """
    spec = NOTIFY if spec is None else spec
    return [
        _gvariant(spec["app_name"]),
        str(spec["replaces_id"]),
        _gvariant(spec["app_icon"]),
        _gvariant(spec["summary"]),
        _gvariant(spec["body"]),
        "@as []" if not spec["actions"] else str(spec["actions"]),
        "@a{sv} {}" if not spec["hints"] else str(spec["hints"]),
        str(spec["expire_timeout"]),
    ]


def _gvariant(text: str) -> str:
    """One string as GVariant text: double quotes, backslash-escaped."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def notify_id(out: str) -> int:
    """The id `Notify` returned, out of gdbus' `(uint32 7,)`.

    Zero is not a valid id in the spec, and a daemon that answered with one
    would be a daemon that accepted nothing — so the caller can simply check
    the number.
    """
    body = out.strip()
    if not (body.startswith("(") and body.endswith(")")):
        raise ValueError(f"not a gdbus reply: {out!r}")
    inner = body[1:-1].rstrip(",").strip()
    if not inner.startswith("uint32 "):
        raise ValueError(f"Notify did not answer with an id: {out!r}")
    return int(inner[len("uint32 ") :])


def capabilities(out: str) -> list[str]:
    """The capability names out of gdbus' `(['body', 'persistence'],)`."""
    body = out.strip()
    if not (body.startswith("([") and body.endswith("],)")):
        raise ValueError(f"not a capability reply: {out!r}")
    inner = body[2:-3].strip()
    if not inner:
        return []
    return [word.strip().strip("'\"") for word in inner.split(",") if word.strip()]
