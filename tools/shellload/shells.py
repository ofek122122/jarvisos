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
  · A shell with NOTHING TO SAY evaluates almost none of its own QML — and
    the BAR is now the only one of the three in that state. It runs with no
    niri, so `linkUp` is false and the workspaces row builds no delegates;
    what this covers for it is the outermost file, the per-screen `Variants`
    delegate, and every binding that is evaluated whatever the state — which
    is where D34's and D39's faults both were, and is not the same as the
    whole shell. The reason it stays that way is in `Shell.wake` below.
  · The other two are woken, deliberately, and each by the only thing that
    can reach it. `NOTIFY` below is sent to the notifier over the private bus
    by an ordinary D-Bus caller, so the corner maps, the `Repeater` builds a
    `Toast`, and the scan covers the plate — which is also the only thing in
    this repo that has ever proved the D-Bus name is claimed and answered
    (PLAN D22). `HUD_FRAMES` goes onto a real jarvisd, through the HUD's own
    read-only bridge, and lights ten of its eleven plates (PLAN D43).
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
    `wake` NAMES what gives this shell something real to do once it has
    loaded, or is "" for the one shell nothing can. Two of the three have one:
    the notifier gets a D-Bus client (see NOTIFY) and the HUD gets a broker
    and eleven frames (see HUD_FRAMES). It is a name rather than a bool
    because the two wakings share nothing at all — one is a `gdbus call`, the
    other is a second process publishing onto a bus — and a flag would have
    left `load.py` deciding which by looking at `attr`.

    The bar is the one with no cheap answer, and that is measured rather than
    unexplored: `JV_BAR_NIRI` is `--set` into the wrapper, so its event stream
    cannot be pointed at a fake without staging the shell, which is the one
    thing this gate refuses (PLAN D43).

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
    wake: str = ""
    reserves_top: bool = False


SHELLS = (
    Shell(attr="jv-hud", root="shell/jv-hud", env="JV_HUD_BIN", wake="hud"),
    Shell(attr="jv-bar", root="shell/jv-bar", env="JV_BAR_BIN", reserves_top=True),
    Shell(attr="jv-notify", root="shell/jv-notify", env="JV_NOTIFY_BIN", wake="notify"),
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


# ------------------------------------------------------------------ the HUD
#
# THE HUD'S HALF (PLAN D43), and the hole it fills is one this file used to
# state as a limit two paragraphs up. The HUD with no jarvisd has nothing to
# say: `Bus` is blind, every plate refuses to guess, `visible: selfTest ||
# stack.anyLit` is false — so no wl_surface of its is ever CREATED, the mapping
# reading D44 added asks the compositor about a shell that is not there, and
# what the D39 scan covers is the outermost file and the bindings that evaluate
# whatever the state. Every plate, every state machine under it and every
# binding that only runs on a real frame was outside this gate.
#
# A broker is milliseconds and eleven frames are bytes, so the whole of that is
# bought for about a second of run time: `ops/ralph/shellload.sh` starts a real
# `jarvisd` on this run's own socket, `tools/shellload/publish.py` puts the
# frames below on it at 1 Hz, and the HUD's own read-only bridge — the one
# pkgs/jv-hud pins into the wrapper — carries them into the plates.
#
# COMPOSED FRAMES RATHER THAN A REPLAY, and D43 asked for the replay, so the
# reason is worth stating. `harness/replay.py` would have been less code, but
# every recorded session in `harness/fixtures/sessions` carries exactly three
# topics — audio.vad, audio.wake, audio.transcript — because they are
# recordings of a MICROPHONE. Replaying one lights two plates. The point of
# coming here at all is the plates, so the frames are composed, which is also
# what `tools/hudscreens/sheet.py` had to do for the same reason.
#
# AND THEY ARE THAT FILE'S FRAMES, restated. Eight of the eleven below are
# byte-equal to a named frame in `sheet.py`, and
# `test_the_frames_this_gate_publishes_are_the_screen_sheets_own` holds them
# so — a third file reading both, which is what invariant 1 asks. Restated and
# not imported for the reason `OUTPUTS` is: `sheet.py` is a declared read of a
# 3-minute harness, and importing it would make every edit to that harness's
# noise floor wake this gate. The three that are new are new because nothing
# in this repo had ever composed them — jv-guard refusing a binary, jv-compat
# failing an install, and jv-brain running out of room — so those three plates
# had never been fed a real frame by anything.

# What is published, IN THIS ORDER, and the order is load-bearing in two
# places. Both are the same shape: a plate that stops being shown when Jarvis
# starts TALKING about it.
#
#   · `heard` goes dark once `speech.state` is stamped after the words
#     (core/HeardState.qml latches `answering`), because by then the user is
#     hearing the answer and the answer is the better report on whether they
#     were heard right.
#   · `action` goes dark the same way (core/ActionState.qml `noteExplained`),
#     because Jarvis explaining the failure out loud is what the plate was
#     standing in for.
#
# So `speech.state` goes FIRST and everything else is newer than it. What that
# makes the corner is a barge-in mid-answer: jv-voice is speaking, and the
# words jv-ears just took down are the next thing the user said over the top of
# it. Every frame is true on its own and the two elements are doing exactly
# what they were written to do.
#
# `conf` is 1.0 on all but the transcript, and that is not decoration: six of
# the state machines require an UNHEDGED envelope (`conf >= 1`) before they
# will read a frame at all, and `audio.transcript` is the one topic whose
# confidence is the ASR's own.
HUD_FRAMES = (
    # jv-voice, mid-sentence. First, per the order rule above.
    {
        "topic": "speech.state",
        "src": "jv-voice",
        "body": {"state": "speaking", "say_id": "say-6c1d0f42"},
    },
    # jv-voice speaking into whatever the system calls the default sink,
    # which is what lets `output` say the room is not hearing it: a HUD that
    # could not tell a pinned device from the default one would be blaming
    # the mixer for a sink nobody is listening to.
    {
        "topic": "sys.health",
        "src": "jv-voice",
        "body": {
            "service": "jv-voice",
            "state": "ok",
            "uptime_s": 1847.0,
            "period_s": 5.0,
            "metrics": {"output_device_pinned": 0.0},
        },
    },
    # jv-ears with the device open and dropping chunks: the counters
    # core/MicState.qml reads for the recording light, on a heartbeat that
    # is `degraded` and therefore also the one service `health` reports.
    # Two plates from one frame, and it is the frame `hudscreens.sh`
    # photographs for 06-lossy.
    {
        "topic": "sys.health",
        "src": "jv-ears",
        "body": {
            "service": "jv-ears",
            "state": "degraded",
            "uptime_s": 1847.0,
            "period_s": 5.0,
            "metrics": {
                "mic_open": 1,
                "capture_age_s": 0.02,
                "captured_s": 1846.4,
                "capture_stall_s": 1.0,
                "capture_loss_age_s": 0.3,
                "capture_loss_window_s": 1.0,
            },
            "notes": "microphone losing audio: jv-ears dropped 0.4s and 1 "
            "device overrun (length unknown) since start",
        },
    },
    # The mixer muted, from jv-context's 1 Hz snapshot. This is the frame the
    # republishing below exists for: core/OutputState.qml calls a snapshot
    # older than 3 s stale, which is correct for a reading that arrives every
    # second and is why `publish.py` is a loop rather than one pass.
    {
        "topic": "context.system",
        "src": "jv-context",
        "body": {
            "net_online": True,
            "load1": 1.9,
            "mem_used_pct": 37.5,
            "audio_volume": 0.62,
            "audio_muted": True,
        },
    },
    # What jv-ears took down. The one frame here whose `conf` is not 1.0 —
    # it is the ASR's own confidence, and invariant 4 says the producer
    # publishes it rather than the consumer assuming it.
    {
        "topic": "audio.transcript",
        "src": "jv-ears",
        "conf": 0.88583,
        "body": {
            "kind": "final",
            "utterance_id": "9d2c71b4-6e05-4a3a-9f1e-0b7c5d84aa10",
            "text": "Jarvis, empty my downloads folder into the trash.",
            "lang": "en",
            "t0": 0.0,
            "t1": 2.9,
        },
    },
    # The destructive thing jv-act has stopped in front of. It can only be
    # read here: the surface takes no input at all, so nothing this gate does
    # could answer it even if it wanted to.
    {
        "topic": "action.confirm",
        "src": "jv-act",
        "body": {
            "kind": "request",
            "request_id": "req-4f21",
            "tool": "fs.trash",
            "summary": "move 14 files in ~/Downloads to the trash — yes or no?",
            "window_s": 15.0,
        },
    },
    # The intent, then its outcome. Both, because `action` names the TOOL
    # that failed and the only thread between an outcome and a tool name is
    # the request id — an id-less pair would light the plate with no name on
    # it, which is a different plate from the one this is meant to cover.
    {
        "topic": "intent.action",
        "src": "jv-brain",
        "body": {
            "request_id": "req-4f21",
            "tool": "fs.trash",
            "args": {"path": "~/Downloads"},
            "capability": "destructive",
            "needs_confirmation": True,
            "utterance_id": "9d2c71b4-6e05-4a3a-9f1e-0b7c5d84aa10",
        },
    },
    {
        "topic": "action.result",
        "src": "jv-act",
        "body": {
            "request_id": "req-4f21",
            "ok": False,
            "duration_ms": 412.0,
            "error": "execution_failed",
            "detail": "3 of 14 entries could not be moved: Permission denied",
        },
    },
    # NEW HERE, and each of these three is a plate no gate in this repo had
    # ever put a real frame in front of.
    #
    # jv-guard refusing a Windows binary (invariant 8). `blocked` rather than
    # `suspicious`: blocked is final, and suspicious is the one that may be
    # overridden through the confirmation flow, which is a different plate's
    # story. Only the hash ever leaves this machine (invariant 7) and the
    # hash is the only thing here that would.
    {
        "topic": "guard.verdict",
        "src": "jv-guard",
        "body": {
            "sha256": "3b1f9c0d5a4e7268bd1c04f7e9a2358c6d0b7e41f582a93cd7e6b40158a2c9f3",
            "verdict": "blocked",
            "reasons": ["matched ClamAV signature Win.Trojan.Agent-1234567"],
            "scanned_by": ["clamav"],
            "path": "/home/ofek/Downloads/setup.exe",
        },
    },
    # jv-compat getting further and then failing: the one thing on this bus
    # that takes minutes, and the one the user walks away from.
    {
        "topic": "compat.install",
        "src": "jv-compat",
        "body": {
            "event": "failed",
            "app": "notepad-plus-plus",
            "sha256": "9f4c2e7b8a10d35f6c9e0b47a25d18f3e6c04b9d7a318e25f0c6b4a97d3e152b",
            "path": "/home/ofek/Downloads/npp-installer.exe",
            "installer": "nsis",
            "arch": "x64",
            "error": "the installer exited 1 after the prefix was created",
        },
    },
    # jv-brain running out of room mid-answer — the one outcome of a turn
    # with no other route to a screen, because a finished reply is its own
    # report and a brain that could not answer at all arrives as a degraded
    # heartbeat instead. Published LAST: core/ReplyState.qml drops the
    # truncation the moment an `audio.wake` or a `brain.request` is stamped
    # after it, and neither is on this bus.
    {
        "topic": "brain.response",
        "src": "jv-brain",
        "body": {
            "text": "The files in ~/Downloads are mostly installers from the "
            "last three weeks, and the largest of them is the Windows "
            "toolchain archive you pulled down on the",
            "finish_reason": "length",
            "conversation_id": "conv-7f2a",
            "model": "llama-3.1-8b-instruct-q4_k_m.gguf",
            "backend": "gpu",
            "latency_ms": 2140.0,
        },
    },
)

# WHY IT REPUBLISHES, and it is one plate's requirement rather than a habit.
# `context.system` is jv-context's 1 Hz snapshot and core/OutputState.qml calls
# one older than 3 s stale — correctly, because a mixer reading from ten
# seconds ago is not a reading of this room. A single pass would light
# `output` and lose it again before the compositor had been asked anything.
#
# The WHOLE set goes out each round rather than just that one frame, and that
# is deliberate: a bus has no backlog, so a frame published before the HUD's
# bridge had subscribed is simply gone, and there is nothing this driver can
# ask that would tell it when the subscription landed. Republishing makes the
# race stop mattering instead of trying to win it.
#
# Re-sending the whole set in order is SAFE for the two latching plates above,
# and the mechanism is worth writing down because it looks like it would not
# be. Round 2's `speech.state` IS newer than round 1's transcript, so
# `answering` latches — and then round 2's transcript arrives, its
# `transcriptKey` (`seq@ts`) changes, and `onTranscriptKeyChanged` clears the
# latch and re-checks against the words it now holds. `action` recovers the
# same way through `apply()`. The flicker is the width of a few milliseconds
# of publishing and it converges every round.
HUD_ROUND_S = 0.5

# Which plates the corner must name, in the stack's own order. Held equal to
# `shell/jv-hud/shell.qml`'s own `PlateStack` — minus the one below — by
# `test_every_plate_the_hud_stacks_is_lit_by_this_gate`, so a plate added to
# that stack fails this gate rather than quietly never being loaded.
HUD_PLATES_LIT = (
    "confirm",
    "state",
    "output",
    "heard",
    "reply",
    "action",
    "guard",
    "install",
    "mic",
    "health",
)

# And the one that cannot be here, which is not an omission but the shape of
# what it reports. `LinkPlate` is on screen exactly while the HUD CANNOT see
# the bus, so it is mutually exclusive with every plate above: lighting it
# would mean taking the broker away, and then there would be no frames.
# `shell/jv-hud/shell.qml` says the same thing about its own box — "in
# practice it can never share the surface". It is covered instead by the
# no-broker state this gate used to be entirely made of: see D43's entry in
# `ops/ralph/PLAN.md` for why that is a separate run and not a longer one.
HUD_PLATES_DARK = ("link",)

# How long the corner is given to name them all. Generous against a cold Qt
# on a cold font cache, and bounded — `test_the_gate_still_costs_seconds_and_
# not_minutes` holds the worst case of every wait in this file together.
HUD_LIT_TIMEOUT_S = 20.0


def hud_corner_line(monitor: str, plates: tuple[str, ...] | list[str]) -> str:
    """The line `shell/jv-hud/shell.qml` logs when its corner changes.

    A COPY of the QML's own template, and
    `test_the_corner_line_this_gate_reads_is_the_one_the_hud_writes` holds the
    two equal by reading both files — the invariant-1 shape `bar_strip_px()`
    already uses, because there is nothing to import: the string only exists
    inside a running QML engine.

    Empty is spelled `nothing` rather than left blank so that a corner going
    dark is a line somebody can grep for, not an absence.
    """
    names = " ".join(plates) if plates else "nothing"
    return f"jv-hud: corner on {monitor} shows {names}"


def hud_corner_plates(said: str, monitor: str) -> list[str] | None:
    """The plates the NEWEST corner line for `monitor` named, or None.

    The newest rather than any, because the corner is a sequence: the plates
    arrive over a round or two and the interesting state is the one it settled
    on. None is "this monitor never wrote a line at all", which is a different
    failure from "it wrote one naming nine plates" — a surface that was never
    built versus a plate that never lit — and the report says which.

    Parsed here rather than in the driver so the writing and the reading of
    this line are one file apart from each other and nothing else.
    """
    prefix = hud_corner_line(monitor, ())[: -len("nothing")]
    found = [line for line in said.splitlines() if prefix in line]
    if not found:
        return None
    names = found[-1].split(prefix, 1)[1].strip()
    return [] if names == "nothing" else names.split(" ")
