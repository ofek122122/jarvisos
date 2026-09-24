"""What the screen sheet photographs, and on which monitors (PLAN A30).

Data and pure helpers, stdlib only. `tools/hudscreens/shoot.py` executes
it and `tools/tests/test_hudscreens.py` reads it, so the shot list, the
monitor sizes, the compositor's config and the frames behind each picture
are stated once — and anything the harness MEASURES with lives here too,
where a test with no compositor can still run it.

The difference between this sheet and the contact sheet in `docs/hud`
(A29) is the whole point of it: A29 renders the plates into a 300x560
rectangle with a plain QML engine, which is the HUD's CONTENT and nothing
else. This one runs the REAL `jv-hud` — quickshell, layer-shell, the real
bridge, the real jarvisd — on a real wlroots compositor with ares' three
monitors, and photographs the screens. Everything A29 had to disclaim is
what this exists to show: the surface on every monitor at once, the edge
it docks to, and the emptiness it leaves behind when it has nothing to
say.
"""

import re

# ares' monitors, as CLAUDE.md declares them: one 2560x1440 primary and
# two 1920x1080 at its side. The refresh rates are real on ares and
# meaningless here (a headless backend has no scanout), so they are not
# claimed anywhere; what the sheet is asking is a question about SIZE —
# whether an 11 px label docked to the corner of a 1440p panel reads the
# same as on a 1080p one beside it.
#
# The names are the headless backend's, not ares'. ares has HDMI-A-1 and
# DP-1/DP-2, and nothing here should pretend otherwise: the compositor is
# real, the monitors are not.
OUTPUTS = [
    {"name": "HEADLESS-1", "role": "primary", "width": 2560, "height": 1440, "x": 0},
    {"name": "HEADLESS-2", "role": "side", "width": 1920, "height": 1080, "x": 2560},
    {"name": "HEADLESS-3", "role": "side2", "width": 1920, "height": 1080, "x": 4480},
]

DESK_WIDTH = sum(o["width"] for o in OUTPUTS)
DESK_HEIGHT = max(o["height"] for o in OUTPUTS)

# The desktop behind the HUD. The real surface is `color: "transparent"`
# and floats over whatever Niri has on screen, so a photograph has to put
# SOMETHING behind it or `plate_opacity = 0.86` is invisible and the shot
# is a picture of the HUD over a void.
#
# Same flat grey A29's scene uses, and for the same reason: a colour that
# appeared in personality/theme.toml would be a colour a reader could
# mistake for Jarvis's own. tools/tests/test_hudscreens.py holds both
# halves of that — the two harnesses agree, and neither names a palette
# entry.
BACKDROP = "#31353B"

# The surface box shell.qml declares, and the inset it docks by. The shots
# are checked against these: a plate that drew somewhere other than the
# top-right corner of every monitor would be a layer-shell anchor that
# silently stopped working, and it would look perfectly fine in a picture
# nobody measured.
SURFACE_W = 300
SURFACE_H = 560
INSET = 16


# --------------------------------------------------- counting frames (A34)
#
# `probe_idle_frames` in shoot.py asks whether the HUD renders anything
# while nothing changes (invariant 10: "0 fps when idle"). It counts the
# HUD's own Wayland traffic — libwayland's WAYLAND_DEBUG log, from the
# client side of the socket — because that is what actually costs a
# composite, and because it needs no cooperation from Qt.
#
# The counter lives here, next to `sway_config()`, for the same reason
# that does: it is the harness's instrument, and an instrument nothing can
# execute is one nobody can check. shoot.py needs numpy and a compositor;
# this file is stdlib-only, so tools/tests/test_hudscreens.py can run the
# counter over real log lines and prove it counts what it claims to.
#
# Both separators on purpose. libwayland has printed the object id as
# `wl_surface@41`, and the build this harness runs against today prints
# `wl_surface#41`. A debug log is not a stable interface — which is why
# the probe insists on SEEING commits in its control stretches. A pattern
# that silently stopped matching would otherwise report a flawless,
# permanent zero, which is the most convincing way for this measurement
# to be wrong.
COMMIT_RE = re.compile(r"wl_surface[@#]\d+\.commit\(\)")
FRAME_RE = re.compile(r"wl_surface[@#]\d+\.frame\(")


def surface_traffic(text):
    """(commits, frame callbacks requested) in a stretch of WAYLAND_DEBUG.

    A `commit` is the client handing the compositor new surface state —
    one frame reaching the screen. A `frame` request is the client asking
    to be woken for the next one, which is how a continuous animation
    keeps itself alive; it is reported alongside so a failure can say
    whether the HUD is merely redrawing or is driving itself.
    """
    return len(COMMIT_RE.findall(text)), len(FRAME_RE.findall(text))


def sway_config():
    """The compositor the sheet runs on, as a config file.

    Here rather than in the driver so the checks can read the same text the
    compositor was given: a monitor size or an input rule that drifted
    between the two would make every measurement below be about a machine
    the sheet does not describe.
    """
    lines = [
        # No Xwayland: nothing in this harness is an X11 client, and
        # starting one would be one more thing that can fail for reasons
        # unrelated to the HUD.
        "xwayland disable",
        # No keybindings at all. There is no user here, and a stray binding
        # is a way for this to do something nobody asked for.
        "default_border none",
        # The click probe (A32) warps the cursor and then presses. With
        # focus-follows-mouse on, the WARP could move focus on its own and
        # the probe would report a pass-through that no button ever caused.
        # Off, the only thing that can move focus is a click that was
        # routed somewhere — which is the entire measurement.
        "focus_follows_mouse no",
    ]
    for out in OUTPUTS:
        lines.append(
            f"output {out['name']} mode {out['width']}x{out['height']} "
            f"pos {out['x']} 0"
        )
    return "\n".join(lines) + "\n"


def _beat(service, state="ok", metrics=None, notes=None, uptime_s=1847.0, period_s=5.0):
    """A sys.health heartbeat, from the service's own src.

    `src` matters and is not decoration: core/HealthState.qml refuses a
    body that names a service other than the envelope's sender, so a
    heartbeat published under the harness's own name reads as `unknown`
    and the sheet would be a picture of a machine in trouble.
    """
    body = {
        "service": service,
        "state": state,
        "uptime_s": uptime_s,
        "period_s": period_s,
    }
    if metrics is not None:
        body["metrics"] = metrics
    if notes is not None:
        body["notes"] = notes
    return {"publish": {"topic": "sys.health", "src": service, "body": body}}


# jv-ears with a real device open: the counters core/MicState.qml reads to
# decide the recording light. Without it the mic plate says nothing, which
# is correct and also means the sheet would never photograph the one
# indicator invariant 10 says must not be fakeable.
MIC_OPEN = _beat(
    "jv-ears",
    metrics={
        "mic_open": 1,
        "capture_age_s": 0.02,
        "captured_s": 1846.4,
        "capture_stall_s": 2.0,
    },
)


# An ordinary jv-context snapshot: nothing muted, nothing at zero, so
# core/OutputState.qml has nothing to say about it. context.system is the
# only 1 Hz topic the HUD subscribes to (A40) — every other one is an
# event — so this is the frame the idle probe uses to ask whether a bus
# that never stops talking costs a HUD that has nothing to say anything at
# all.
SINK_OK = {
    "publish": {
        "topic": "context.system",
        "src": "jv-context",
        "body": {
            "net_online": True,
            "load1": 1.9,
            "mem_used_pct": 37.5,
            "audio_volume": 0.62,
            "audio_muted": False,
        },
    }
}


# The other half of the same snapshot: the sink MUTED. Together with the
# frame below it is the one pair in this whole HUD that keeps a plate on
# screen for as long as a harness cares to feed it, on a bus that never
# stops talking — which is what the idle probe's live-lit window (A42) is
# for.
#
# Nothing else here can do that. Every other lit state is a frame ageing
# out: a heartbeat speaks for two of its own periods, a confirmation for
# the window jv-act declared, a heard line for HeardState's hold. The only
# state A34 could hold still was `LinkPlate` with NO BUS AT ALL, so "0 fps
# with a plate on screen" had only ever been measured on a HUD that could
# see nothing. core/OutputState.qml is a live reading of two topics, and
# re-publishing this snapshot at jv-context's own 1 Hz keeps it true
# indefinitely.
SINK_MUTED = {
    "publish": {
        "topic": "context.system",
        "src": "jv-context",
        "body": {
            "net_online": True,
            "load1": 1.9,
            "mem_used_pct": 37.5,
            "audio_volume": 0.62,
            "audio_muted": True,
        },
    }
}


# jv-voice with an utterance in flight. core/OutputState.qml reads
# `speech.state` verbatim (not SpeechState's answer), and it does not
# expire on its own — jv-voice publishes `idle` when it finishes, and the
# element's 30 s backstop is the only other exit. So ONE of these plus a
# fresh SINK_MUTED is a lit HUD that stays lit, saying two true things:
# SPEAKING above (StatePlate, since A3) and OUTPUT MUTED under it.
VOICE_SPEAKING = {
    "publish": {
        "topic": "speech.state",
        "src": "jv-voice",
        "body": {"state": "speaking", "say_id": "say-6c1d0f42"},
    }
}


SHOTS = [
    {
        "file": "01-quiet",
        "lit": False,
        "captures": ["desk"],
        # Nothing at all. jarvisd is up, the bridge is subscribed, every
        # plate has looked at the bus and decided it has nothing true to
        # say — so the shell leaves all three surfaces unmapped and the
        # screens are the desktop. This is the HUD's ordinary state and
        # the one picture that has to be boring.
        "source": "recorded from a live bus with nothing published on it",
        "frames": [],
    },
    {
        "file": "02-heard",
        "lit": True,
        "captures": ["desk", "primary", "side"],
        # The real recording, whole (B3/B9): wake, partials, the final.
        # The heartbeat and the brain.request under it are composed —
        # nothing committed has ever recorded sys.health or a turn
        # reaching jv-brain (B10/A28).
        "source": (
            "recorded (harness/fixtures/sessions/hey-jarvis-clean.jsonl, "
            "replayed whole onto the live bus) + composed heartbeat and "
            "brain.request"
        ),
        "frames": [
            {"replay": "hey-jarvis-clean"},
            MIC_OPEN,
            {
                "publish": {
                    "topic": "brain.request",
                    "src": "jv-brain",
                    "body": {
                        "text": "Hey Jarvis, what time is it?",
                        "source": "voice",
                        "utterance_id": "5ab8fecf-13d0-4f86-aa5d-0b2cc23b4d5d",
                    },
                }
            },
        ],
    },
    {
        "file": "03-confirm",
        "lit": True,
        "captures": ["desk", "primary"],
        # COMPOSED. jv-act stopping in front of a destructive tool, in its
        # own words, with the window running. The one thing this HUD ever
        # shows that is waiting on YOU — and the reason its size on a real
        # 1440p panel is worth measuring rather than guessing.
        "source": "composed (nothing committed has recorded jv-act asking)",
        "frames": [
            MIC_OPEN,
            {
                "publish": {
                    "topic": "action.confirm",
                    "src": "jv-act",
                    "body": {
                        "kind": "request",
                        "request_id": "req-4f21",
                        "tool": "fs.trash",
                        "summary": (
                            "move 14 files in ~/Downloads to the trash — yes or no?"
                        ),
                        "window_s": 15.0,
                    },
                }
            },
        ],
    },
]


def capture_files(shot):
    """The PNG names one shot writes, in reading order."""
    return [f"{shot['file']}-{c}.png" for c in shot["captures"]]


def all_files():
    out = []
    for shot in SHOTS:
        out.extend(capture_files(shot))
    return out


def output_by_role(role):
    for o in OUTPUTS:
        if o["role"] == role:
            return o
    raise KeyError(role)
