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
    """

    attr: str
    root: str
    env: str
    wake: bool = False


SHELLS = (
    Shell(attr="jv-hud", root="shell/jv-hud", env="JV_HUD_BIN"),
    Shell(attr="jv-bar", root="shell/jv-bar", env="JV_BAR_BIN"),
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
