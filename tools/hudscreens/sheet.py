"""What the screen sheet photographs, and on which monitors (PLAN A30).

Data and pure helpers, stdlib only. `tools/hudscreens/shoot.py` executes
it and `tools/tests/test_hudscreens.py` reads it, so the shot list, the
monitor sizes, the compositor's config and the frames behind each picture
are stated once — and anything the harness MEASURES with lives here too,
where a test with no compositor can still run it.

The difference between this sheet and the contact sheet in `docs/hud`
(A29) is the whole point of it: A29 renders the plates into a 300x807
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
SURFACE_H = 807
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


def grew_downwards(before, after):
    """Did a plate ARRIVE UNDER another one, in this stack's geometry?

    Both arguments are `drawn_box` results — (x0, y0, x1, y1) around
    everything on a monitor that is not desktop, or None for a bare one.
    The stack is docked to the TOP-RIGHT, so those two edges are what pin
    it and neither may move; the bottom must grow. The left edge may
    travel OUTWARDS and routinely does — OUTPUT MUTED is a longer line
    than SPEAKING — so it is allowed to decrease and not to increase. The
    first version of this rule, written inline, called that widening a
    failure.

    Two things in shoot.py need exactly this and for the same reason:
    `StatePlate` has said SPEAKING since A3 and lights on jv-voice's frame
    alone, so "something is drawn" is never evidence that `OutputPlate`
    is on screen. The idle probe's live-lit window needs to know that the
    thing it holds still for six seconds includes the plate A40 added, and
    the `04-unheard` shot needs to know that the picture it is about to
    write has under it the second line its caption claims. Both light the
    HUD twice — an audible sink, then the mute — and both ask this.

    It lives here, with the frame counter and the compositor config,
    because a rule the harness measures with is one a test with no
    compositor should be able to run.

    WHAT IT DOES NOT SAY (PLAN A47). It proves that something arrived under
    the thing above it, and it can never say WHAT. A `HealthPlate` reporting
    a lost service grows this stack downwards by a similar number of pixels
    from the same pinned corner as the plate any given caller is waiting
    for, and that is not hypothetical — it is exactly what the idle probe
    hit when a heartbeat lapsed mid-window. The sheet's captions are read by
    a person, which is fine for a sheet; a caller that treats a True here as
    proof of an identity is claiming more than the geometry knows.

    The HUD can now answer the identity question itself — every plate
    declares `plateName` and `core/PlateStack.qml` collects `litNames`
    (A53) — and the contact sheet in tools/hudshots asserts exactly that,
    because its scene is built by a QML test. Nothing here can: this harness
    runs the real `.#jv-hud` binary under a real compositor and measures it
    with `grim`, so there is no engine to ask. A47 holds the open decision.
    """
    if before is None or after is None:
        return False
    left, top, right, bottom = before
    grown_left, grown_top, grown_right, grown_bottom = after
    if grown_top != top or grown_right != right:
        return False
    return grown_left <= left and grown_bottom > bottom


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


# The same jv-ears, with the failure that hid for a day (2026-09-15): the
# device is still open, and no audio has arrived for longer than jv-ears'
# own stall budget. ONE frame, two plates — MicPlate says MIC NO AUDIO,
# and jv-ears' own heartbeat says `degraded`, which is a HealthPlate line.
#
# That coincidence is what makes it the idle probe's fourth window (A43).
# Every other way to put those two plates on screen needs two publishers
# agreeing; this needs one heartbeat, re-published, and both stay true for
# as long as it keeps arriving.
#
# The gauges do NOT move between re-publishes, and on a real machine
# `capture_age_s` would climb. That is deliberate: the window's question is
# what a frame ARRIVING costs when nothing it says has changed, so the only
# things that move are the ones the HUD cannot help — `seq` and `ts`.
MIC_DEAF = _beat(
    "jv-ears",
    state="degraded",
    metrics={
        "mic_open": 1,
        "capture_age_s": 9.4,
        "captured_s": 1846.4,
        "capture_stall_s": 2.0,
    },
    notes="capture stalled",
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


# jv-voice stating how it opens its output device (A41). Not decoration
# either: core/OutputState.qml refuses to say OUTPUT MUTED about a sink
# nobody has told it Jarvis uses. The plate's whole claim is that the
# DEFAULT sink jv-context reports is the one the samples land on, and that
# is true only while no device is pinned — so 0 here is jv-voice's ordinary
# configuration (`sd.play()` with no device argument), published rather
# than assumed. Without this frame the pair below lights StatePlate alone
# and the live-lit window measures a HUD with one plate on it.
#
# It does NOT expire: the gauge is jv-voice's configuration, not a reading
# of the world, so one beat holds for as long as the link does — which is
# why the feeds below carry only the snapshot.
VOICE_DEFAULT_SINK = _beat("jv-voice", metrics={"output_device_pinned": 0.0})


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


# The id that threads one turn together. `schemas/intent.action.json` says
# what it is for in as many words — "threads intent.action -> action.confirm
# -> action.result and the audit log" — so the four frames below carry ONE
# of them rather than four copies of the same string. A turn whose id drifts
# between the question and the outcome is a turn core/ActionState.qml would
# refuse to put a tool name on, which is a different plate and a different
# box from the one this harness measures.
TURN_REQUEST_ID = "req-4f21"


# jv-act stopping in front of a destructive tool, in its own words, with
# the window running (A20). COMPOSED — nothing committed has ever recorded
# jv-act asking — which is why every number in it is jv-act's own: the
# window is the 15 s `services/jv-act` declares and `schemas/action.confirm`
# documents, and not a longer one invented to make a harness convenient. A
# frame claiming a ten-minute confirmation window would be a picture of a
# machine that does not exist, and core/ConfirmState.qml would believe it.
#
# ONE THING IN IT IS NOT JV-ACT'S OWN, and A49 is where it got written
# down: `fs.trash` is not in jv-act's registry. `services/jv-act/tools.toml`
# is v0 — "observe + benign only" — so it holds no destructive tool at all,
# and the structural rule is that ONLY destructive and privileged tools are
# confirmed. Asked for `fs.trash` today, the real jv-act would answer
# `unknown_tool` and never ask anybody anything.
#
# The composition is still worth making, and the reason is that the thing
# under test is the CONFIRMATION MACHINERY, which is built, reviewed and
# structural: jv-act opens a 15 s window for destructive tools, and the HUD
# has to be able to show one. Registry v0 says the approved tool mapping is
# observe+benign for now and that the rest "arrive in later phases with
# their own review" — so this frame is the machine jv-act IS, carrying a
# tool it has not yet been granted. What would be dishonest is leaving that
# unsaid, which is what this paragraph fixes.
#
# It lights `ConfirmPlate` and nothing else: the only plate in this HUD
# that is waiting on YOU, and the only one with an ember border.
CONFIRM_REQUEST = {
    "publish": {
        "topic": "action.confirm",
        "src": "jv-act",
        "body": {
            "kind": "request",
            "request_id": TURN_REQUEST_ID,
            "tool": "fs.trash",
            "summary": "move 14 files in ~/Downloads to the trash — yes or no?",
            "window_s": 15.0,
        },
    }
}


# What the user said to get that question asked: one jv-ears FINAL, which
# is the only kind core/HeardState.qml will read (partials are provisional
# and get rewritten, and a plate showing a sentence Jarvis never acted on
# is a more expensive wrong than an empty one).
#
# COMPOSED, and paired with the frame above on purpose. The committed
# recording's final asks what time it is (harness/fixtures/sessions/
# hey-jarvis-clean.jsonl), and nothing destructive follows from that — so
# replaying it under a `fs.trash` confirmation would put two true frames on
# the bus that add up to a machine which had confused itself. These two are
# one turn: the words, and the question they earned.
#
# The envelope `conf` is BORROWED rather than invented — 0.88583 is that
# recording's own final, from a quiet room. Invariant 4 requires a number
# here, and a composed 1.0 would be a certainty no ASR ever reports.
HEARD_FINAL = {
    "publish": {
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
    }
}


# --------------------------------------------- and what came of it (A49)
#
# The three frames that finish the turn above. Until A49 this harness
# stopped at the question, and `ActionPlate` was the last plate in the
# stack that had never been watched standing still — the sixth idle window
# is those three frames arriving, in the order the schemas say they arrive.
#
# They are COMPOSED, and they inherit the one fiction CONFIRM_REQUEST
# already carries (see the note on `fs.trash` there). Everything else about
# them is the machine as it is: the id threads, the answer closes the
# question, the error word is out of the frozen enum, and the failure is
# the kind jv-act reports when a tool it DID run did not work.


# What jv-brain asked for, and the only place the TOOL NAME exists.
#
# `action.result` carries a request_id and no name, so core/ActionState.qml
# will not put a tool on screen unless the intent still on the bus is the
# one that outcome answers — a name taken on faith is a lie about what
# touched the machine. Without this frame the failure below is still
# reported; it is just reported nameless, which is a shorter plate and a
# different box.
#
# `args` is read by nothing, and that is the point of it being here.
# `services/jv-hud-bridge` calls it "the most sensitive body on this list"
# — whatever the tool was asked to operate on, a path or a search string or
# a window title — and forwards the envelope whole because `conf`, `ts` and
# `seq` are how invariant 4 is honoured. Invariant 7 is what stops it at
# the bridge: no element reads it, and a tools gate fails the build if one
# starts to. A frame carrying a real-looking path is the only way this
# harness exercises that claim at all.
#
# `capability` is the brain's CLAIM and not a verdict — the schema says
# jv-act re-derives it from the registry and rejects a mismatch — so
# "destructive" here is jv-brain believing something about a tool, which is
# exactly what the field is for.
TRASH_INTENT = {
    "publish": {
        "topic": "intent.action",
        "src": "jv-brain",
        "body": {
            "request_id": TURN_REQUEST_ID,
            "tool": "fs.trash",
            "args": {"path": "~/Downloads"},
            "capability": "destructive",
            "needs_confirmation": True,
            "utterance_id": HEARD_FINAL["publish"]["body"]["utterance_id"],
        },
    }
}


# The user said yes.
#
# This frame is not decoration and it is not optional: it is what makes the
# window after it a picture of a machine that could exist. `action.result`
# arriving while `ConfirmPlate` still stood would be jv-act having run a
# tool it was still asking permission for, and core/ConfirmState.qml would
# hold the question up quite happily — it only lets go for an answer naming
# THIS request_id, or for the 15 s window running out.
#
# `answered_by` is `voice` because that is the ordinary path:
# `services/jv-act/src/service.rs` classifies the transcript itself inside
# a scoped listen window, which is also why the `src` here is jv-act rather
# than the CLI.
CONFIRM_GRANTED = {
    "publish": {
        "topic": "action.confirm",
        "src": "jv-act",
        "body": {
            "kind": "answer",
            "request_id": TURN_REQUEST_ID,
            "granted": True,
            "answered_by": "voice",
        },
    }
}


# And it did not work. The one category of event a user has the most right
# to see — something acted on my machine on my behalf, and it failed — and
# the only thing that lights `ActionPlate` (A37).
#
# `execution_failed` rather than any other word in the enum, for two
# reasons. It is the outcome of a tool jv-act actually RAN, which is the
# only kind that can follow a granted confirmation; and it is in
# core/ActionState.qml's `reportableReasons`, which deliberately excludes
# `denied` and `confirm_timeout` — those are how a confirmation ENDED, A22
# is an open question for a human about what the screen should do with
# them, and neither would put a word on this plate.
#
# `duration_ms` is required by the schema and is read by no element;
# `detail` is free text for the audit log and is read by no element either.
# Both are here because a result frame without them is one jv-act would
# never send, and the second is the only `detail` this harness has ever
# published — core/ActionState.qml's header promises it never reaches a
# screen, and a frame with an empty one would not be testing the promise.
TRASH_FAILED = {
    "publish": {
        "topic": "action.result",
        "src": "jv-act",
        "body": {
            "request_id": TURN_REQUEST_ID,
            "ok": False,
            "duration_ms": 412.0,
            "error": "execution_failed",
            "detail": "3 of 14 entries could not be moved: Permission denied",
        },
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
        "frames": [MIC_OPEN, CONFIRM_REQUEST],
    },
    {
        "file": "04-unheard",
        "lit": True,
        # The primary alone. The three-screen question (A13/A27) is already
        # asked twice above, and what this shot is for is the one thing
        # neither sheet has ever shown: two plates on a real 1440p panel
        # disagreeing about whether Jarvis is working. One says an
        # utterance is in flight; the one under it says none of it is
        # arriving.
        "captures": ["primary"],
        "source": (
            "composed (nothing committed has recorded jv-voice speaking, and "
            "no recording carries a muted mixer)"
        ),
        # Split in two, because this is the first shot in the sheet whose
        # subject is a LIVE READING rather than an event.
        #
        # The event: one `speaking` from jv-voice. It is ended by a real
        # signal (jv-voice publishing `idle`) and nothing here publishes
        # one, so it stands for the length of the shot.
        "frames": [VOICE_SPEAKING],
        # The reading: republished at jv-context's own 1 Hz for as long as
        # the camera takes. core/OutputState.qml stops believing a snapshot
        # after three of those periods, and core/HealthState.qml calls a
        # service lost after two of the `period_s` its heartbeat declares.
        #
        # Measured rather than argued, because the argument overstates it:
        # publishing this pair ONCE and sleeping writes the same picture
        # today, byte for byte. A single exposure reaches grim about two
        # seconds after the publish and the snapshot expires at three, so
        # publish-once is INSIDE the window — by under a second, on this
        # machine, with one capture. The feed is what stops that margin
        # from being load-bearing: the frames are true at the instant of
        # every exposure whatever the machine is doing, and they stay true
        # if this shot ever grows a second monitor (a 33 Mpx grim and a
        # PNG encode each) or the settle gets longer. The failure at the
        # far end of that margin is not hypothetical: A42's live-lit
        # window published the heartbeat once, and `jv-voice lost` arrived
        # under the plate it was holding still.
        "hold": [VOICE_DEFAULT_SINK, SINK_MUTED],
        # The same HUD one plate shorter. Identical frames with an AUDIBLE
        # sink: StatePlate says SPEAKING on jv-voice's frame alone, so
        # "something is drawn" would be true of a HUD where A40's plate
        # never appeared and the caption under this picture would be
        # describing a line that is not in it. The harness photographs this
        # first and insists the real shot GREW DOWNWARDS from it.
        "grows_from": [VOICE_DEFAULT_SINK, SINK_OK],
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
