# jv-hud — the heads-up display

Quickshell (QML) layer-shell surfaces over Niri. Blueprint §06: *every
moving pixel encodes a real signal*, and the HUD **never** steals focus or
fakes sensor state (invariant 10).

## What exists today

`shell.qml` maps one layer-shell surface per connected monitor, and that
surface is **unmapped unless an element has something true to draw** — the
default state of the screen is your work and nothing else, and an unmapped
surface renders at 0 fps. Today it stacks eleven plates in the top-right
corner, in this order:

| plate | draws while | topic |
|---|---|---|
| `LinkPlate` (A23) | the HUD cannot see the bus at all | (the pipe itself) |
| `ConfirmPlate` (A20) | jv-act is waiting on your yes or no | `action.confirm` |
| `StatePlate` (A3) | Jarvis is listening, thinking, speaking, was interrupted, or preempted itself | `speech.state` + `audio.wake` + `brain.*` |
| `OutputPlate` (A40/A41) | Jarvis is speaking into a sink you cannot hear | `speech.state` + `context.system` + `sys.health` (jv-voice) |
| `HeardPlate` (A26) | your words are still the live question | `audio.transcript` (+ `audio.vad` for the window, A57) |
| `ReplyPlate` (A71) | the answer you just heard ran out of room | `brain.response` (+ `audio.wake` / `brain.request` for the exit) |
| `ActionPlate` (A37) | the last thing Jarvis did to the machine failed | `intent.action` + `action.result` |
| `GuardPlate` (A51) | this machine refused to run a program | `guard.verdict` |
| `InstallPlate` (A52) | an app jv-compat let through did not install | `compat.install` |
| `MicPlate` (A4) | the microphone is actually open | `sys.health` (jv-ears) |
| `HealthPlate` (A6/B40) | some service is not well — and, under a brain on the CPU floor, how much of the card is left | `sys.health` + `context.system` |

Every one of them reads the bus and nothing else, several take jv-ears' own
tuning from `core/EarsBudgets.qml` (A14) rather than mirroring it, and every
one of them draws NOTHING until it has something true to say — which is why
the ordinary state of this HUD is an unmapped surface. `docs/hud/` is a
contact sheet of all eleven, at the surface's real size.

The skeleton pins the properties that make the HUD safe by construction,
and `tools/tests/test_gen_theme_qml.py` fails the build if any of them is
changed, dropped, or forgotten on a surface added later:

| property | why |
|---|---|
| `WlrKeyboardFocus.None` + `focusable: false` | the surface cannot take the keyboard |
| `ExclusionMode.Ignore` | zero exclusive zone — no window is resized around it |
| `mask: Region {}` | empty input region — clicks pass through to what's below |
| `WlrLayer.Top` | over ordinary windows, yields to fullscreen and the lock screen |
| `color: "transparent"` | the window paints nothing; each plate brings its own ground |

## Running it

The HUD is packaged as `jv-hud` and installed system-wide, but it is not
started automatically yet. Start it by hand in a Niri session:

```sh
jv-hud                      # nothing on screen until the bus says something
JV_HUD_SELFTEST=1 jv-hud    # also maps a marker: the shell loaded
```

Say "hey jarvis" with `jv-ears` running and the plate appears; it goes when
Jarvis does. `jv tap speech.state audio.wake` shows the same frames the HUD
is reading, which is the fastest way to tell a HUD bug from a bus one.

`JV_HUD_SELFTEST` reports that the *shell* is alive, never a sensor — which
is why its marker sits in the opposite corner from the real elements.
Everything in the table above comes off the bus or does not appear.

## Theme tokens (A2)

Every colour, size, duration and inset the HUD uses comes from
`personality/theme.toml` — theme tokens are identity, and identity is
versioned next to the voice and the system prompt (invariant 9). The toml is
compiled into `Theme.qml`, a `pragma Singleton` that QML files read through
the directory import:

```qml
import "."
...
color: Theme.ground
border.color: Theme.ember
```

```sh
python tools/gen_theme_qml.py          # regenerate Theme.qml, the motion trio, qmldir
python tools/gen_theme_qml.py --check  # exit 1 if they drifted
bash ops/ralph/runtests.sh tools       # generator + drift + blueprint tests
```

`Theme.qml`, `Ease.qml`, `Motion.qml`, `core/MotionPolicy.qml` and both
`qmldir`s are generated and checked in — **never hand-edit them.** The last
three are generated for the same reason the tokens are: all three shells get
the same file, byte for byte, so §06's stillness rule is one decision rather
than three copies of one (PLAN D18). Three gates keep the story honest: `nix build .#jv-hud` runs
`--check` before qmllint (a drifted Theme.qml cannot reach a build), qmllint
type-checks every token access (`Theme.emberr` is a build failure, not a
transparent rectangle at runtime), and a test asserts no QML file outside
`Theme.qml` contains a literal hex colour. A fourth test asserts the palette
still equals the blueprint's §06 dark tokens, so the theme cannot quietly
wander away from the design it came from.

## The faces (A8)

`theme.toml`'s `[type] family_sans` / `family_mono` name Archivo and JetBrains
Mono, and for fifteen iterations nothing on the machine installed either:
fontconfig found no such family and quietly substituted something else. A
missing font is the worst shape a missing dependency takes — it does not fail,
it just renders in a different face.

`modules/fonts.nix` closes that. It reads the family names out of
`personality/theme.toml` with `builtins.fromTOML` (same source of truth,
different compiler), binds each to a package, and installs the face it
*checked*: the join's build runs `fc-scan` and fails unless the package really
reports the family the theme asked for. Archivo is not in nixpkgs, so
`pkgs/archivo` pins it upstream — base width only, 18 faces, all verified to
be family `Archivo`. A face named in the toml with nothing bound to it is an
eval-time `throw`; a binding the toml does not name fails an assertion; a
`font.family` in QML that is not a `Theme.family*` fails `runtests.sh tools`.

Only outline formats (`.ttf`/`.otf`/`.ttc`) are installed. jetbrains-mono
ships every face three times and `fc-match monospace` picked
`JetBrainsMono-Regular.woff2` against the first version of this module —
whether a WOFF2 renders depends on how the reader's FreeType was built, which
is the same silent substitution one layer further in.

**Nobody has seen this on screen yet.** `fc-match` resolving `Archivo` and
`JetBrains Mono` was verified against the built system closure; the HUD
actually drawing in them needs a human on ares.

The `qmldir` has no `module` line on purpose. Quickshell synthesizes a qmldir
per directory and steps aside when it finds one; ours registers the singleton
in the way a plain directory import (and qmllint) understands. Any future
singleton has to be added to it.

## The bus link (A5)

QML cannot open a Unix socket or unpack MessagePack, and the HUD is
forbidden from importing another service (invariant 1). So `Bus.qml` runs
one child process — `services/jv-hud-bridge`, pinned into the wrapper as
`JV_HUD_BRIDGE` — which subscribes to a few topics and writes each frame
as one line of JSON. Frames come in; nothing goes out. The bridge's pump
is handed a `ReadOnlyBus` that has no publish method to reach for, and a
test greps the source for `.publish` on top of that.

```
{"t":"frame","frame":{topic,ts,seq,src,conf,v,body}}
{"t":"link","up":true}                 subscribed to a live bus
{"t":"link","up":false,"err":"..."}    not subscribed, and why
```

`link` is deliberately not a bus topic — it describes this pipe, not the
machine, and a topic needs a reviewed schema commit (invariant 2). The HUD
needs it because **`Bus.frames` is emptied whenever the link drops**: a HUD
still drawing "listening" from a bus that died three minutes ago is lying,
and a stale indicator is worse than none (invariant 10).

What an element uses:

| member | meaning |
|---|---|
| `Bus.linkUp` | gate every piece of content on this |
| `Bus.latest(topic)` | last envelope, or `null` if unheard |
| `Bus.latestFrom(topic, src)` | last envelope **from one publisher** — `sys.health` has one per service |
| `Bus.ageOf(env)` | seconds since capture, or `Infinity` if not yet knowable |
| `Bus.frameReceived(topic, env)` | per-frame signal |

`Bus.qml` itself is only the half that needs Quickshell: the child process,
the respawn timer, and the monotonic clock. The state machine those JSON
lines drive lives in `core/BusModel.qml` and imports nothing but QtQuick —
which is what makes it testable (see below). `Bus` forwards the whole API,
so an element still sees one `Bus`.

The singleton is built on first use. Since A3 that is at load: an element
has to be watching the bus to know whether there is anything to show, so a
running HUD always runs its bridge child and holds one subscription. What
stays lazy is the *screen* — the surface maps only when a frame earns it.

Under `JV_HUD_SELFTEST=1` the marker plate also prints `bus up` / `bus
down`: the state of this pipe, in plain words, never dressed up as a sensor
indicator.

```sh
bash ops/ralph/runtests.sh jv-hud-bridge   # unit tests + a real-jarvisd e2e
```

Note on the build gate: qmllint type-checks *cross-file* access, so
`Bus.linkUpp` in any element is a build failure. It does **not** catch a
typo in a self-assignment inside a file — which is what the QML tests are
for.

## Headless QML tests (A9)

```sh
bash ops/ralph/qmltest.sh                          # inner loop, worktree source
bash ops/ralph/qmltest.sh BusModel::test_received_survives_a_link_drop
nix build .#jv-hud                                # the gate: qmllint + these tests
```

`shell/jv-hud/tests/` runs under `qmltestrunner -platform offscreen`: no
compositor, no bus, no bridge process. That works only because of how this
directory is split:

| directory | imports | who can load it |
|---|---|---|
| `shell/jv-hud/` | Quickshell | the `quickshell` binary, only |
| `shell/jv-hud/core/` | QtQuick | any QML engine — so, the tests |

Quickshell links its QML plugin **into its own binary**, so no other QML
engine can `import Quickshell` at all. And importing a directory resolves
every type its `qmldir` lists — so a single Quickshell import inside `core/`
would make the whole directory unloadable and silently take the HUD's only
tests with it. A test in `tools/` fails if that ever happens.

The rule that follows: **logic that deserves a test goes in `core/`.**
Anything left in a Quickshell file is beyond the reach of any test, so keep
those files to wiring. Components in `core/` are registered in `CORE` in
`tools/gen_theme_qml.py` (which writes `core/qmldir`), exactly like
singletons are registered in `SINGLETONS`.

The tests are a build gate, not shipped QML — `installPhase` drops them.

## Tested on real perception (B9)

Hand-written frames have one flaw: the input and the expectation have the
same author, so a misunderstanding about what jv-ears actually publishes
gets written into both. `harness/fixtures/sessions/` holds four recordings
of what the **real** pipeline published while listening to the fixture WAVs
(B3), and `tests/tst_sessionreplay.qml` replays them through
`core/BusModel` + `core/SpeechState`:

| recording | what the HUD does with it |
|---|---|
| `hey-jarvis-clean` | `unknown` → `listening@1.44` → `thinking@3.76` |
| `hey-jarvis-music` | the same, 0.4 s longer; a noisier wake is not a weaker claim |
| `hey-jarvis-pause` | 1.2 s of real silence mid-sentence and **no flicker**: one entry, one exit, 5.28 s apart |
| `speech-no-wake` | real speech nobody addressed to Jarvis — `unknown` throughout, start to finish |

Those seconds are facts about the recordings, so a flicker or an early
blank shows up as an extra transition rather than as a judgement call.
The words land LATER than the `thinking` above them — 2.2 s later, the
ASR jv-ears runs after the boundary (A58) — which is why the two elements
that a turn puts on screen are timed from the same frame and not each from
its own (A57), and why that is now something a replay can check. Two
of the assertions are about the coupling to jv-ears rather than about the
HUD: the real wake frames must clear SpeechState's "a frame that disagrees
with itself is not a detection" bar (they carry openWakeWord's own `score`
and `conf`), and the longest recorded utterance must still fit inside
`wakeWindowS` — lower `wake_timeout_s` below what a person actually says
and the HUD would drop `listening` while ears was still recording.

QML cannot read a file out of the repository, so the recordings are
compiled into `tests/Sessions.qml`, verbatim, by a generator that knows
nothing about schemas (`harness/session.py` is the format's only reader):

```sh
python tools/gen_sessions_qml.py          # regenerate tests/Sessions.qml
python tools/gen_sessions_qml.py --check  # exit 1 if it drifted — runs in the build
bash ops/ralph/runtests.sh tools          # the generator's own tests
```

Same shape as the theme, for the same reason: re-record perception and
`nix build .#jv-hud` fails until the fixture is regenerated — at which
point the trajectories above change too, and the diff is the answer to
"what did that retune do to the room?".

## Motion (A7)

§06 gives motion four rules, and three are about *not* moving: **off with
`prefers-reduced-motion`, off on battery, full stop under a fullscreen
window** — and, when it does move, *ease toward the target over ~200 ms,
never snap to a raw value*. Those live in one place, so no element has to
remember them:

```qml
// the common case — a value that settles instead of jumping
Text {
  color: Bus.linkUp ? Theme.text2 : Theme.text3
  Ease on color {}                      // Theme.easeMs, gated
}
Rectangle { opacity: shown ? 1 : 0
            Ease on opacity { base: Theme.fadeInMs } }

// anything else that animates
NumberAnimation { duration: Motion.easeMs; running: Motion.animate }
```

| member | meaning |
|---|---|
| `Motion.animate` | may this shell move at all — gate `Behavior.enabled` / `running` on it |
| `Motion.suppressedBy` | `""`, or `reduced-motion` / `battery` / `fullscreen` |
| `Motion.easeMs` … `pulseMs` | the `[motion]` tokens, already **0** when suppressed |
| `Motion.ms(base)` | gate any other duration through this |
| `Ease on <prop> {}` | one `Behavior` that carries the gate with it |

`Ease` is a `PropertyAnimation`, so the same component eases colours — which
is most of what a HUD settles. Its `base` chooses *how long* a move takes;
it can never choose *whether* one happens, because the duration that reaches
the animation is always `Motion.ms(base)`.

Sources, and which are real today:

| input | source |
|---|---|
| declared preference | `personality/theme.toml` → `[motion] reduced_motion` |
| session override | `JV_REDUCED_MOTION=1` (stop) / `=0` (force on); nothing else counts |
| `onBattery` | **none yet** — `context.system.battery_pct` says nothing about discharging |
| `fullscreen` | **none yet** — `context.window` has no fullscreen field |

The two unsourced inputs are properties, not TODOs: wiring one later is a
single binding. They sit at `false`, which is the truth on ares (a desktop
with no battery), and whatever feeds them must feed them a real signal.

The decision itself is `core/MotionPolicy.qml` — pure QtQuick, so it is
tested (`qmltest.sh`); `Motion.qml` is only the binding to real sources. And
a `tools/` test fails the build if any QML file in ANY shell declares an
animation type without consulting `Motion`, so the off switch cannot be
quietly bypassed by the next element someone writes.

All three of these files are written by `tools/gen_theme_qml.py` into every
shell (PLAN D18), so the bar and the notification corner ask exactly this
question, with these inputs, and `JV_REDUCED_MOTION=1` stills the whole
desktop rather than one surface of it. `tst_motionpolicy.qml` lives here and
tests all three, because a byte-for-byte check says they are one file.

## Jarvis's state (A3)

The first element backed by real sensor topics. `StatePlate.qml` draws a
dot and one word; `core/SpeechState.qml` decides which word, from three
topics, and is where the tests are.

| state | comes from | colour |
|---|---|---|
| `unknown` | no link, no frame, or no frame we can trust — **draws nothing** | — |
| `idle` | `speech.state` = idle — **draws nothing** | — |
| `listening` | `audio.wake` fired and the window is still open | teal — the open mic is *yours* |
| `speaking` | `speech.state` = speaking | ember — Jarvis is doing something |
| `interrupted` | `speech.state` = interrupted, and it was *you* (`reason` = wake, or no reason we can read) | quiet; a fact, not an alarm |
| `preempted` | `speech.state` = interrupted with `reason` = preempted — Jarvis stopped its own sentence for something urgent | quiet, exactly like `interrupted` |

`listening` is the claim that costs the most if it is wrong, because it is a
claim about the microphone. jv-ears publishes when a window *opens* and
nothing when it closes, so closing is inferred — and every rule is chosen to
stop saying it too early rather than too late:

- Jarvis answering (`speech.state` → `speaking`, newer than the wake) means
  it already heard you. A `speaking` frame *older* than the wake is barge-in,
  not an answer, so that still reads as listening.
- `audio.vad` `speech_end` newer than the wake closes the window — ears
  disarms there for a wake-gated utterance.
- `interrupted` never closes it: jv-voice publishes that *because* of the
  wake, and blanking the plate there would blank it while you are talking.
  (Neither does `preempted`, which is the same frame under a different
  `reason` — see below.)
- otherwise it expires after `wakeWindowS` — jv-ears' own `wake_timeout_s`,
  read off its heartbeat (see *How jv-ears is tuned* below). This used to be
  a constant typed into the QML under a comment asking the next reader to
  keep it in step with the service.

Frames are refused rather than guessed at: a body from a schema version we
were not written against, a wake that scored below the threshold it declares
(or whose envelope `conf` contradicts that score), a state topic hedging its
confidence, or any frame without a numeric `ts` — ordering a wake against a
speech transition is the whole rule, and an unorderable frame cannot be
ordered. A state word we do not recognise reads as `unknown`, never as the
nearest thing we do know.

Age comes from `Bus.ageOf`, so with no clock pinned yet there is no age and
therefore no `listening` — `Infinity` fails every freshness test by
construction. The expiry timer is armed only while a window is actually
open, and with whatever is *left* of it (a frame delayed in flight is
already partway through its own window), so an idle HUD runs no timer.

## The microphone (A4)

The privacy indicator, and the only element on screen that is **not
optional** (invariant 10): `MicPlate.qml` is lit for as long as the device
is open, whether or not Jarvis is listening and whether or not anyone is
talking. `core/MicState.qml` decides, and is where the tests are.

| state | comes from | on screen |
|---|---|---|
| `unknown` | no link, no heartbeat, a heartbeat too old, or gauges we cannot read — **draws nothing** | — |
| `off` | jv-ears is here and has no microphone open (a `--wav` run) — **draws nothing** | — |
| `live` | the device is open, delivering, and losing nothing | teal dot · `MIC` |
| `losing` | the device is open and delivering, and chunks are going missing anyway | warn dot · `MIC LOSING AUDIO` |
| `stalled` | the device is open and has gone silent | warn dot · `MIC NO AUDIO` |

`losing` and `stalled` are both degraded and only one word fits on the
plate, so the order is jv-ears' own: a stall outranks a loss, because "no
audio at all" is the bigger fact. `capturing` stays true through `losing` —
a microphone dropping chunks is still recording the ones it keeps, and the
privacy light is not a quality light.

It is a different question from `listening` and is never derived from it:
jv-ears runs its VAD continuously, so `listening` answers *is Jarvis
attending to me* while this answers *is audio being captured at all*. Two
signals, two elements.

**What makes it not fakeable.** A process being alive is not evidence about
a device — that is exactly the 2026-09-15 field bug, where PortAudio opened
nothing, jv-ears stayed up and cheerful, and the stream delivered silence
forever. So jv-ears now counts what the device actually hands it
(`CaptureMeter`, wrapping the audio source) and reports it on its own
heartbeat, in the `metrics` section `sys.health` declares free-form and
service-local — no schema change, nothing frozen touched:

| gauge | meaning |
|---|---|
| `mic_open` | `1` for a real microphone, `0` for a `--wav` run |
| `capture_age_s` | seconds since the device last delivered audio — **absent** until it ever has |
| `captured_s` | total audio delivered since start |
| `capture_stall_s` | the stall budget ears judges by — a budget, not a measurement, so it is there from the first heartbeat |
| `capture_loss_age_s` | seconds since a chunk of the room was discarded — by ears' queue or by the device — **absent** until one ever was |
| `capture_loss_window_s` | how long a discard keeps meaning "losing audio" — the other budget, there from the first heartbeat |

How much was lost is deliberately **not** a gauge. Half of it can never be
a number — the device reports an overrun without its length — so a total
would read zero through a run that lost audio only that way. The amounts
go out in `notes` instead, named by culprit, because jv-ears dropping
chunks (this process is too slow) and the device dropping them (the
machine or the driver) send you to different places.

A live microphone that has delivered nothing for longer than
`capture_stall_s` also turns the heartbeat itself `degraded`, so `jv
tap sys.health` tells the same story the HUD is telling.

`capture_age_s` is absent rather than infinite on purpose: the bridge
serializes frames with `json.dumps`, which writes a bare `Infinity` that no
JSON parser accepts, and the HUD would drop the whole line.

The two ways this element can lie are not equally bad — claiming a
microphone that is closed is noise, while going dark over an open one is the
failure that costs trust. So *"I cannot tell" never collapses into "off"*: a
dropped link, a heartbeat older than two of its own `period_s` (the
schema's own "presumed dead" rule), a body whose `service` disagrees with
the envelope `src`, a hedged `conf`, a wrong schema `v`, or a jv-ears too
old to report the gauges all read as `unknown`.

Nothing pulses. A breathing dot would spend GPU every frame to say what a
still one already says (§06: 0 fps when nothing is happening).

```sh
jv tap sys.health --for 12          # the same heartbeats the HUD reads
bash ops/ralph/runtests.sh jv-ears  # CaptureMeter + the heartbeat body
```

## How jv-ears is tuned (A14)

Three of the claims above are only true for as long as jv-ears is tuned to
make them true: how long a wake word means `listening`, how long an open
microphone may go quiet and still read as `live`, and how long a discarded
chunk keeps it reading `losing`. The first two were typed into the QML by
hand, under comments asking whoever retuned the service to remember the
HUD. So jv-ears states the budgets it enforces on its own heartbeat —
`metrics` again, still no schema change — and `core/EarsBudgets.qml` is the
one place that reads them:

| budget | jv-ears | the HUD's fallback |
|---|---|---|
| `wake_timeout_s` | `EarsPipeline.budgets()`, off the sample-clock count the code compares against, not off `cfg` | `wakeWindowDefaultS` |
| `capture_stall_s` | `CaptureMeter.STALL_S` | `stallDefaultS` |
| `capture_loss_window_s` | `CaptureMeter.LOSS_S` | `lossWindowDefaultS` |

The fallbacks cannot be deleted — the HUD has to say something before the
first heartbeat lands — so they are pinned instead: `tools/tests` fails the
build if any of them drifts from the Python that enforces it, and if a plate
stops binding the reported value and quietly runs on the fallback.

A reported budget is refused unless it is a number, positive, and under a
ceiling (`"12"` is not twelve; an infinite window never closes; the value
also ends up in a `Timer` interval). Refused means *fall back*, never zero.

Unlike the mic gauges, budgets do **not** expire with the heartbeat that
carried them: a gauge describes a moment, a budget describes how a service
is configured and stays true until it says otherwise. jv-ears beats
immediately on start, so a retuned restart lands within one frame, and a
jv-ears too dead to beat publishes no wakes for the window to bound.

```sh
bash ops/ralph/qmltest.sh              # EarsBudgets and the elements it feeds
bash ops/ralph/runtests.sh tools       # the drift gates
```

## Next

Track A's open items are `A11` (real sources for
`Motion.onBattery`/`fullscreen` — blocked on proposal R1's schema fields)
and the questions a human has to answer by looking: `A13`/`A27` (one plate
per monitor — right, or noise?), `A21`/`A22`/`A25` (what a plate should do
over seconds). And the standing one: nobody has looked at this HUD on ares
yet — `docs/hud/` and `docs/hud/screens/` are the nearest thing to it.
