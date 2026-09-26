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
import re
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

# How long a shell may take to say READY before this gives up, and it is not
# one number, because the cost it is written against is paid ONCE per machine
# rather than once per engine (PLAN D53).
#
# THE COLD ONE, for the first engine a run starts. A quickshell that is the
# first on this machine to scan Qt's plugins and build a font cache pays for
# both, and a timeout that fires on a slow machine is a gate that gets switched
# off — so it is generous, and it is a guess, and it has to be: this gate
# cannot make itself pay that cost. Measured here, the first engine of a run
# loads in the same 0.40 s the other three do, because the caches have been
# warm on ares for as many runs as there have been runs.
READY_TIMEOUT_COLD_S = 30.0

# AND THE WARM ONE IS DERIVED, from what this run has already measured, which
# is the only honest thing available: whatever the first engine warmed is warm
# for every engine after it, so a later one cannot be waiting on the cold cost
# and handing it the cold number gives a HUNG engine thirty seconds of a reason
# it cannot have. Four times the slowest load this run has seen — floored, so a
# fast first engine cannot make the bound brittle, and capped, so the worst
# case stays a static number `engine_ceilings()` can add up.
#
# The floor is fifteen times the 0.40 s this gate measures, and it is there so
# that one fast reading cannot make the bound brittle: a first engine clocked at
# a twentieth of a second would otherwise bound the next one at a fifth of one.
# The cap is thirty times it, and it only starts answering once the first engine
# took more than three seconds — a machine already seven times slower than this.
#
# THE CAP IS THE LIMIT AND IT IS WORTH STATING. A machine uniformly slow enough
# that a WARM engine needs more than twelve seconds, after another quickshell in
# the same run has already done it, fails this gate. `ReadyBudget` makes that
# failure say so and name this constant, because the repair for it is a number
# rather than a shell.
READY_WARM_FACTOR = 4.0
READY_WARM_FLOOR_S = 6.0
READY_WARM_CEILING_S = 12.0


def warm_ready_timeout(slowest_so_far: float) -> float:
    """How long the NEXT engine may take, given the slowest one so far.

    The slowest rather than the previous: a bound that has learned the machine
    is slower than it thought must not un-learn it on the next fast engine.
    Monotone in its argument for the same reason.
    """
    return min(
        READY_WARM_CEILING_S,
        max(READY_WARM_FLOOR_S, slowest_so_far * READY_WARM_FACTOR),
    )


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
# ALSO made `visible: true`, AND once its anchors had been widened from the
# corner to the bottom triplet — two conditions, not one, which is D59 below and
# is the correction to what this paragraph said for two iterations. With the
# notifier's own `visible: Notifications.anyLit` — false when the window is
# created, true a moment later when the gate's notification arrives — the
# identical 100 px zone is silently never published on ANY anchors, and the
# compositor reports every monitor whole. A conditionally-visible `PanelWindow`
# gets its exclusive zone at creation and a zone declared while it was invisible
# does not reach the compositor. Both of these shells are conditionally visible
# (`Notifications.anyLit`, `selfTest || stack.anyLit`), and the HUD with no
# jarvisd is never lit at all, so no surface of its is ever created in this gate.
#
# AND LIGHTING THE CORNER DOES NOT REPAIR THAT, which is D54 and is why that
# item is closed by measurement rather than built. D43 put real frames into this
# run and D47 lights `LinkPlate` with no bus at all, so the HUD's surface really
# is mapped at both of its `up=True` readings now — and the comment in `load()`
# was amended to claim those readings had therefore become the HUD's own. They
# have not. Three injections, each a full run of the real gate:
#   · `exclusiveZone: 100` + `ExclusionMode.Normal`, unconditional, from birth —
#     all four engines GREEN, every monitor whole, on the lit frames run and the
#     lit blind run both.
#   · the same zone made to appear only on the surface D52 REBUILDS (a latch on
#     `onVisibleChanged`, so surface #1 is born with 0 and surface #2 with 100) —
#     green again, with the HUD's own log showing the latch fire: `lit,
#     darkenings 1 zone 100` on all three monitors, while sway went on reporting
#     2560x1440 and 1920x1080.
#   · and the same zone with `visible: true`, which is the one that says WHY —
#     green again. Mapping was never the missing ingredient.
#
# THE CAUSE IS THE ANCHOR, and `tools/hudscreens/shoot.py` had already found it
# from the other side: `check_no_space_reserved` there says so in as many words,
# and reports the opposite direction measured — the HUD anchored left+right+top
# with `ExclusionMode.Auto` took HEADLESS-1's usable area to 2560x880. sway
# honours an exclusive zone only for a surface anchored to ONE edge or to an edge
# plus both perpendicular ones; this corner is top+right, which is neither, so
# its zone is discarded whatever the value and whoever is looking.
#
# AND THAT LEFT TWO HARNESSES GIVING TWO REASONS FOR ONE ZERO, which is what
# D59 settled and it turns out BOTH were right about their own half. `jv-notify`
# is anchored bottom+right, a bare corner like the HUD's, and the injection above
# reported its 100 px zone coming off every monitor — which under the anchor rule
# should have been discarded too. Three more runs of the real gate, all on the
# notifier, all `ExclusionMode.Normal` + `exclusiveZone: 100`, complete the 2x2:
#
#   anchors            visible:               reserved
#   bottom+right       true                   nothing           (run A, GREEN)
#   bottom+left+right  true                   100 px, bottom    (run B, RED)
#   bottom+left+right  Notifications.anyLit   nothing           (run C, GREEN)
#   bottom+right       Notifications.anyLit   nothing      (what ships, GREEN)
#
# Run B reproduced the D44 numbers to the pixel — 2560x1340 and 1920x980 on all
# three monitors — and the workspace rects came back `y: 0`, so the 100 px really
# did come off the BOTTOM edge, not the top. Run A is the answer to D59's
# question: the old notifier injection had widened the anchors and did not record
# it. Run C is why the earlier paragraph is still true: conditional visibility
# suppresses a zone the anchors WOULD have honoured.
#
# So a surface takes space off a monitor only when three things hold at once — it
# declares a zone, it is mapped when it declares it, and its anchors are a shape
# sway zones — and each of the three alone is enough to make the zero above.
# Which is exactly why the reading is a control and not a proof for these two:
# runs A and C are `exclusiveZone: 100` in a shipped shell with this whole gate
# GREEN. `test_a_shell_whose_zero_is_only_a_control_asks_for_nothing` is what
# covers the two conjuncts the compositor cannot show us, in the cheap gate, on
# the commit that moves one.
#
# AND THE ANCHOR RULE ITSELF IS NOW MEASURED, EVERY SHAPE OF IT (D60), which
# it was not while two tests rested on it. `ZONED_ANCHORS` in
# `tools/tests/test_shellload.py` is sway's `apply_exclusive` written out by
# hand — one edge, or an edge plus both perpendiculars, eight sets — and until
# now six of those eight had never been through a compositor here at all: what
# had been watched was the bar's `{top,left,right}` and run B's
# `{bottom,left,right}`. A wrong entry in that list is a discarded zone this
# gate calls a proof, so each remaining shape is one run of `shellload.sh` with
# `jv-notify` anchored that way, `ExclusionMode.Normal`, `exclusiveZone: 100`,
# `visible: true`, and nothing else moved:
#
#   anchors             reserved
#   {top}               2560x1340 and 1920x980 — 100 off the height, RED
#   {bottom}            2560x1340 and 1920x980 — 100 off the height, RED
#   {left}              2460x1440 and 1820x1080 — 100 off the WIDTH, RED
#   {right}             2460x1440 and 1820x1080 — 100 off the WIDTH, RED
#   {left,top,bottom}   2460x1440 and 1820x1080, RED
#   {right,top,bottom}  2460x1440 and 1820x1080, RED
#
# Six for six: every shape the rule accepts really is honoured, on both axes,
# and the list the two cheap tests read is now evidence rather than recall. The
# left/right shapes are also the first thing in this harness to take space off
# a WIDTH — `usable_areas()` above models a strip off the top, and it reads
# these correctly only because it compares whole rects.
#
# AND ONE SHAPE THE RULE REJECTS WAS MEASURED TOO, because it is the one a
# person would expect to be honoured: anchored to ALL FOUR EDGES — the shape a
# full-screen overlay takes — with the same live zone, the compositor reserved
# NOTHING and this gate stayed green. `apply_exclusive` compares the anchor mask
# for EQUALITY against one edge or one triplet, and four edges is neither. So an
# overlay stretched across the screen can ask for a strip and silently not get
# one, which is the failure direction nobody watches for; it is in
# `DISCARDED_ANCHORS` beside the two corners for exactly that reason.
#
# THE CONSEQUENCE, PLAINLY. The bar's reading is a proof, and it is the only one
# here: its window declares a zone, is always mapped AND is anchored to an edge
# plus both perpendiculars, which is the one configuration in this repo whose
# zone has been watched reaching the compositor. The notifier's reading and both
# of the HUD's are the CONTROL that makes the bar's 31 px the bar's, and nothing
# more — `test_the_only_shell_whose_zone_is_proven_is_configured_for_it` is what
# keeps `reserves_top` and that configuration from drifting apart.
#
# AND INVARIANT 10 IS STILL HELD, by the configuration rather than by this gate:
# every arrangement in which this corner would really take space off a monitor is
# one where sway honours the zone, and a zone sway honours is one this reading
# SEES. The HUD that starts reserving a strip is the HUD that re-anchored to the
# top edge — `shoot.py` measured that exact change taking 560 px — and both this
# gate and that one go red on it. What cannot be caught HERE is any of the three
# conjuncts moving on its own, because the compositor's answer does not change
# until the last of them does; that is the cheap gate's job (D59), and it is why
# the two tests are worth having separately.


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

# And the one that cannot be lit by THAT run, which is not an omission but
# the shape of what it reports. `LinkPlate` is on screen exactly while the HUD
# CANNOT see the bus, so it is mutually exclusive with every plate above:
# lighting it means taking the broker away, and then there are no frames for
# anything else. `shell/jv-hud/shell.qml` says the same thing about its own
# box — "in practice it can never share the surface".
#
# So it gets its own run, and this tuple is that run's whole expectation: the
# blind HUD's corner must show exactly these and nothing else. See the D47
# section at the foot of this file.
HUD_PLATES_DARK = ("link",)

# How long the corner is given to name them all. Generous against a cold Qt
# on a cold font cache, and bounded — `test_no_single_engine_can_hang_this_gate_
# for_minutes` holds the worst case of every wait ONE engine can spend.
HUD_LIT_TIMEOUT_S = 20.0

# And how long the PUBLISHER gets to put its first round out, which is a
# different wait about a different thing and used to borrow the number above.
# Separated by D52, because that item gives this gate a second publisher and a
# borrowed number is only one number until somebody needs it to be two.
#
# The two are bounded by different physics, which is the whole argument. The
# corner above is a cold Qt scene building eleven plates; this is a python
# process starting, importing msgpack and connecting to a unix socket that is
# already bound — the same asymmetry `HUD_RELINK_BUS_TIMEOUT_S` is written on.
# A publisher that has not managed a round in four seconds is not slow, it is
# broken, and `Proc.wait_for` already reports one that DIED as itself rather
# than waiting it out. The same four seconds the broker gets to bind, for the
# same reason, and deliberately NOT five: `core/LinkState.qml`'s grace is 5.0
# and `test_the_grace_is_read_out_of_the_qml_rather_than_copied_into_this_gate`
# refuses any constant here that equals it, so that a read stays a read.
HUD_PUBLISH_TIMEOUT_S = 4.0


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


# ------------------------------------------- the blind HUD (PLAN D47)
#
# THE ELEVENTH PLATE, and the only run that can light it. Everything above is
# a HUD with a broker under it; `LinkPlate` is on screen exactly while there
# is none, so it needs its own quickshell — the same shipped binary, started
# after the three, with `JARVIS_BUS` pointed at a path that is not a socket
# and nothing else changed.
#
# WHAT IT PROVES, and it is two things rather than one:
#
#   · The HUD admits it is blind. Nothing anywhere in this repo had ever
#     watched a real HUD do that. `shell/jv-hud/tests` drives `LinkState`
#     against a BusModel it owns, which is a claim about the element; this is
#     the shipped shell, the shipped bridge, and a machine that really is not
#     running underneath it.
#   · And the ten plates above it stay dark, which is the stronger half. Every
#     state machine in `shell/jv-hud/core` is built to REFUSE rather than
#     guess — MicState will not call a mic it cannot see "off", SpeechState
#     will not call an invisible bus "idle" — and a refusal and a calm machine
#     draw the same nothing, so no picture can tell them apart. The corner
#     naming exactly `link` is the one reading that can: a plate that had
#     started guessing from a bus it cannot see would appear beside it.
#
# It also puts `core/LinkState.qml`'s grace under test for the first time. The
# grace is the whole judgement in that file — say nothing until the outage has
# outlasted the bridge's own retry and Bus.qml's respawn — and a HUD that
# reported instantly, or never, would have passed every gate in this repo. A
# grace of 600 s injected into the QML ends this run 1, and the report quotes
# the 600 back, because the message derives the number from the same file.
#
# WHAT IT IS NOT, and it is not what it looks like. This is NOT a fourth log's
# worth of scan coverage. Measured, by injecting `JSON.parse("{")` into
# `LinkPlate.qml`'s own `text:` binding: BOTH HUD logs reported it, three times
# each. A plate's children are constructed with the plate — `visible` and
# `opacity` decide what is drawn, not what exists — so nearly every binding
# under a plate that never shows is evaluated anyway, and the D39 scan already
# had them. What this run adds is the STATE: `blind` true, `shown` true, the
# surface mapped because of it, and a corner naming which plates that produced.
# The fourth log is scanned all the same, and for the ordinary reason — a log
# nobody reads grades clean — which is why `scan_targets()` iterates engines.

# Where the blind HUD's log goes, as a basename under the stage. Its own,
# because the frames run's log is the other half of the HUD's coverage and a
# single file would make the census below read the wrong corner. Named here
# rather than in the script because the SCAN has to find it too: a blind HUD
# that threw on every screen is exactly this gate's D39 failure, and a log
# nobody scanned reports nothing.
HUD_BLIND_LOG = "jv-hud-blind"

# The bus that is not there YET, as a name under the stage. A path rather than
# an empty string: `jv-hud-bridge` falls back to its own default when `--bus`
# and `$JARVIS_BUS` are both empty, and a bridge that quietly found the
# machine's real socket would be a HUD this gate never blinded.
#
# `late-` rather than `no-`, and that is D49 rather than a rename: nothing
# creates this path while the blind census runs, and then the driver starts a
# real broker ON it and the HUD has to let go. So it is a socket that arrives
# late, which is the whole second half of what this run now measures.
HUD_BLIND_BUS = "late-bus.sock"

# How long the blind corner is given to name `link`. It is the one wait here
# that is mostly a real wait rather than a ceiling — the grace below is 5 s of
# it by design — and the headroom on top is held by
# `test_the_blind_run_outlasts_the_grace_it_is_about`.
HUD_BLIND_TIMEOUT_S = 12.0


# --------------------------------------- and then the bus comes back (D49)
#
# THE HALF THAT IS MORE DANGEROUS THAN THE BLINDNESS, and it is the one D47
# could not walk. `core/LinkState.qml` deliberately does NOT clear `waited`
# when the link returns — `blind` goes false because `linked` went true, and
# the next outage clears the flag when it starts. That is correct, and it is
# also one property away from the worst fault this HUD can have: a `link`
# plate that latched on forever is a permanent NO BUS over a healthy machine,
# which teaches the user to ignore the one plate that qualifies all the others.
# A HUD that had it would pass the blind census above exactly as the shipped
# one does.
#
# So the blind run gets a second act. A real broker — the same `jarvisd` the
# flake builds and the script already realized — is started on the very path
# the HUD's bridge has been failing to connect to, and the corner has to go
# DARK: `hud_corner_plates` spells an empty corner `nothing` rather than as an
# absence, for exactly this reading.
#
# It costs no new machinery. The bridge retries forever by design (see
# `bridge_max_backoff_s()`), so nothing has to be restarted and nothing has to
# be told; the only thing this adds to the run is the waiting.

# What the corner must name once the bus is there: nothing at all. Empty on
# purpose, and it is an expectation rather than an omission — every plate above
# `link` needs a frame nobody is publishing on this broker, so the one thing
# that may change is the plate about the pipe. A corner that still said `link`
# is the latch this run is for; one that said anything else is a plate that
# started guessing the moment it could see a bus.
HUD_PLATES_RELINKED: tuple[str, ...] = ()

# Where the late broker's own output goes, as a basename under the stage. Its
# own file, and deliberately NOT in `scan_targets()`: that scan is
# `tools/qmlerrors.py` over what a QML engine said, and a broker's log is not
# a QML log — a Rust tracing line under a scanner that knows quickshell's
# prefixes would be graded by a reader of the wrong language. It is quoted
# into the failure message instead, which is where it is worth having.
HUD_RELINK_BROKER_LOG = "late-broker"

# How long the broker gets to bind that socket before this gives up. Short,
# unlike every Qt wait here, and the asymmetry is the point: binding a unix
# socket is not a cold font cache, so a broker that has not bound in five
# seconds is not going to, and the run should say THAT rather than spending
# the corner's whole budget waiting for a HUD that has nothing to connect to.
HUD_RELINK_BUS_TIMEOUT_S = 4.0

# How long the corner then gets to go dark. This is a real wait rather than a
# ceiling, like the blind one, and what it has to outlast is the BRIDGE's own
# patience rather than the HUD's: the bridge has been failing to connect for
# several seconds by now, so its backoff has already doubled its way up to the
# maximum, and the broker can appear one instant after a failed attempt.
# `test_the_relink_wait_outlasts_the_backoff_it_is_about` holds it above that
# maximum, read out of the bridge rather than copied.
HUD_RELINK_TIMEOUT_S = 16.0


# ------------------------------- and then it has to work again (PLAN D52)
#
# THE THIRD ACT, and without it this run walks half a cycle. D49 takes the HUD
# from `link` to `nothing`, which proves the plate lets go — and then the run
# ends. The engine that was blind is never shown a frame, and the ten-plate
# census above happens on a DIFFERENT quickshell, one that had a broker from
# the moment it started. So nothing anywhere proved that a HUD which SURVIVED
# an outage can still light a plate.
#
# That is not the same claim twice, and the difference is state rather than
# code. This engine is not a fresh HUD:
#
#   · `core/BusModel.qml` emptied every cache it holds when the bridge died,
#     so every plate above is reading a model that has been through a drop.
#   · `core/HealthState.qml` threw away its roster of services — the `health`
#     plate's whole content is a list it has to rebuild from heartbeats.
#   · And it has been told the link is DOWN, repeatedly. The bridge retries
#     on a doubling backoff and emits one `{"t":"link","up":false}` per failed
#     attempt, so `BusModel.applyLink(false, …)` runs half a dozen times here
#     against the frames run's one. Every one of them empties both caches.
#
# That last one is the fault this act is really for, and it is the shape a
# reconnecting client gets wrong: a HUD that is LINKED, SILENT, and certain it
# is fine. The corner going dark is a reading of the SOCKET — `LinkState`
# watches `Bus.linkUp`, not the traffic — so a HUD that came back linked and
# never accepted another frame passes D49 exactly as the shipped one does.
#
# MEASURED, by making `core/BusModel.qml` drop frames after a second
# link-down: the frames run stays green, the D49 census stays green, this one
# goes red, and all 721 of the HUD's own headless QML tests pass. One outage is
# all any of them ever stages.
#
# It costs one publisher and one census, both already built, on the broker D49
# already started. The expectation is `HUD_PLATES_LIT` itself, unchanged and
# not a copy: the recovered corner has to be the SAME corner, and a third
# reading of one tuple is the whole point of it being a tuple.
#
# AND THE SURFACE IT REBUILDS IS NOT MEASURED, which was D54's whole proposal
# and is the one thing this act deliberately does not do. The reasoning was
# sound: this is the only place in the repo where a wl_surface of the HUD's is
# destroyed and another created, so the rebuilt surface looked like the one
# object that could be carrying a zone nothing here had ever read. The
# measurement refutes it — this corner's zone is discarded by the compositor for
# being anchored to a corner, on any surface it ever has (three injections, in
# the D44 section above). A fourth `check_zone` here would have been 8 s of this
# gate's ceiling spent on a reading that cannot come back false, which is worse
# than no reading: it reads, in the log and in the plan, as coverage.

# Where the late publisher's output goes, as a basename under the stage. Its
# own file, and — like the late broker's and for the same reason — deliberately
# NOT in `scan_targets()`: `tools/qmlerrors.py` reads what a QML engine said,
# and `publish.py` is not one. What it is for is `Proc.wait_for`, which quotes
# it when the publisher dies instead of saying a round.
HUD_RECOVER_LOG = "late-frames"

# How long the recovered corner gets to name its ten plates. SHORTER than
# `HUD_LIT_TIMEOUT_S`, which covers the same ten, and the asymmetry is a
# statement about what each one waits on rather than a saving. That one is a
# cold Qt building a scene for the first time and a bridge that has to spawn,
# connect and subscribe. This engine has been up for half a minute, its scene
# is built, and D49's census has already proved its bridge is connected — so
# what is left is the frames travelling and the plates deciding, which is one
# round and change.
HUD_RECOVER_TIMEOUT_S = 8.0


def bridge_path() -> pathlib.Path:
    """`services/jv-hud-bridge/jv_hud_bridge/bridge.py`, which decides the wait.

    The process the HUD's own wrapper pins, and the only thing between the
    broker appearing and a plate hearing about it.
    """
    return (
        pathlib.Path(__file__).resolve().parents[2]
        / "services"
        / "jv-hud-bridge"
        / "jv_hud_bridge"
        / "bridge.py"
    )


def bridge_max_backoff_s(bridge_py: str) -> float:
    """The longest the bridge will wait between two connect attempts.

    READ rather than copied, for the reason `link_grace_s()` gives about the
    grace: this is a duration the gate has to OUTLAST, so a stale copy of it
    would make the run flaky rather than red. A bridge given more patience
    than `HUD_RELINK_TIMEOUT_S` allows is a gate that fails a HUD which was
    about to recover — and the test that holds the two apart reads this.

    Imported by regex rather than by `import`: `shells.py` is stdlib-only on
    purpose (a test with no compositor and no service venv runs all of it),
    and the bridge's module imports the bus client.
    """
    found = re.search(r"^MAX_BACKOFF_S\s*=\s*([0-9.]+)\s*$", bridge_py, re.M)
    if not found:
        raise ValueError(
            "services/jv-hud-bridge/jv_hud_bridge/bridge.py no longer declares "
            "`MAX_BACKOFF_S = <number>` — the relink wait is derived from it"
        )
    return float(found.group(1))


def hud_shell() -> Shell:
    """The one shell this second run is about, out of `SHELLS`.

    Asked by `wake` rather than by `attr`, for the same reason `load.py`
    dispatches on it: the list of shells stays the only place that decides
    which of them is the HUD. Exactly one, or this raises — two would mean the
    blind run silently picked one of them.
    """
    found = [s for s in SHELLS if s.wake == "hud"]
    if len(found) != 1:
        raise ValueError(f"expected exactly one shell woken by frames, got {found}")
    return found[0]


def link_state_path() -> pathlib.Path:
    """`shell/jv-hud/core/LinkState.qml`, the file that decides the grace."""
    return (
        pathlib.Path(__file__).resolve().parents[2]
        / "shell"
        / "jv-hud"
        / "core"
        / "LinkState.qml"
    )


def link_grace_s(link_state_qml: str) -> float:
    """How long the HUD stays quiet about its own blindness, per the QML.

    READ rather than copied, unlike `bar_strip_px()` and `hud_corner_line()`,
    and the difference is what each number is for. Those two are expectations —
    the gate states what the shell must do and fails when it does not. This one
    is a DURATION THE GATE HAS TO OUTLAST: it decides how long to wait, and a
    stale copy of it would make the gate flaky rather than red. So the timeout
    above is checked against this, and this is checked against nothing —
    whatever the HUD's grace becomes, the wait covers it or the ceiling test
    says so.
    """
    found = re.search(
        r"^\s*property\s+real\s+graceS:\s*([0-9.]+)\s*$", link_state_qml, re.M
    )
    if not found:
        raise ValueError(
            "shell/jv-hud/core/LinkState.qml no longer declares `property real "
            "graceS: <number>` — the blind run's wait is derived from it"
        )
    return float(found.group(1))


def scan_targets() -> list[tuple[str, str]]:
    """Every log this run produces, with the repo root its paths are under.

    One per quickshell rather than one per shell, which is the whole reason
    this exists: the blind HUD is a fourth engine writing a fourth log, and
    a scan that iterated `SHELLS` would have left it unread. Its root is the
    HUD's — it is the same store path, loaded twice.

    QML engines only. The two brokers write logs too and they are next door in
    `broker_targets()`, because what reads them is a different reader — see
    `FRAMES_BROKER_LOG` below.
    """
    return [(s.attr, s.root) for s in SHELLS] + [
        (HUD_BLIND_LOG, hud_shell().root)
    ]


# ------------------------------- and what the BROKERS said (PLAN D51)
#
# TWO BROKERS RUN HERE AND NOTHING EVER READ EITHER. The script starts one for
# the frames run and `relink()` starts a second on the blind HUD's own socket
# (D49), and the only thing that has ever opened either log is the message D49
# quotes it into when the corner fails. Everything this gate concludes about
# the HUD — ten plates, then nothing, then ten plates again — is a reading of
# what those brokers did, so a broker that came up and then refused the
# bridge's subscription, or logged a decode error per frame, reads here as a
# HUD that ignored its frames. That is the wrong repair by a whole process.
#
# `tools/qmlerrors.py` cannot be pointed at them, and
# `test_the_late_broker_is_not_graded_as_a_qml_engine` says why: it knows three
# QML engines' prefixes and a Rust tracing line is not one, so over a broker's
# log it says "nothing threw" whatever the log says. `tools/brokerlog.py` is
# the second reader, and the pairs below are what it is pointed at — a log and
# the socket that broker was told to bind, because its census is that the
# broker NAMED the path this run gave it.

# The frames run's broker, as the basename of the log the script redirects it
# to and the socket it binds. Here rather than in the script for the reason the
# shells' attributes are: the reader below has to open the same two files the
# broker wrote, and two spellings of one path is how a gate ends up reading a
# file nobody writes.
FRAMES_BROKER_LOG = "jarvisd"
FRAMES_BUS = "bus.sock"


def broker_targets() -> list[tuple[str, str]]:
    """Every broker log this run produces, with the socket it was told to bind.

    Two, and the second is the one D49 added: the same `jarvisd` store path,
    started by the driver on the blind HUD's own bus after that HUD has been
    failing to reach it. They are separate entries rather than one scan because
    the census is per-broker — each has to have announced ITS socket, and a
    reader given both logs at once could only have checked neither.
    """
    return [
        (FRAMES_BROKER_LOG, FRAMES_BUS),
        (HUD_RELINK_BROKER_LOG, HUD_BLIND_BUS),
    ]
