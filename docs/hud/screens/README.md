# The HUD, on three monitors (and one that is not)

Photographs of the **real** `jv-hud` — quickshell, a layer-shell surface,
its own read-only bridge, a real `jarvisd` — running on a real wlroots
compositor with ares' monitor sizes. Written by `ops/ralph/hudscreens.sh`;
re-run it after any change to `shell/jv-hud` or `personality/theme.toml`
and commit the diff.

This is the companion to [`../README.md`](../README.md), and the two
answer opposite questions. That sheet renders the plates with a plain QML
engine into the 300x826 rectangle the surface declares: the HUD's
**content**, at a size you can read, and it has to disclaim everything a
compositor owns. These are **screens** — the whole desktop, all three of
them, with the HUD where it actually lands on it.

## What is real here, and what is not

Real: the shipped `jv-hud` binary, unmodified and unstaged; quickshell's
layer-shell surface; one surface per screen from `Quickshell.screens`; the
`jv-hud-bridge` child; a real `jarvisd` on a private socket; the frames,
which go over that bus and are read by the HUD the way any frame is.

Not real: the compositor is **sway**, not Niri — close enough for
layer-shell, which is the protocol both implement, and not the same thing
as ares. The outputs are **headless**: the right sizes, no scanout, no
panel, no NVIDIA, and named `HEADLESS-1..3` rather than ares' `HDMI-A-1`
and `DP-1`/`DP-2`. Nothing here can tell you whether an 11 px label is
comfortable from where you actually sit — only how much of the screen it
takes and where.

One thing that used to be not real here is **age**. The surface these
plates are drawn into grew five times over five plates while the PNGs sat
still, and for most of a hundred iterations a paragraph in this spot
existed to say so, with both numbers derived rather than typed so that it
could not itself go stale. It is gone because what it described is gone:
every screen below is the HUD the harness photographs today, and the
notice was written to be **retired** by that rather than updated.

What keeps it that way is not a promise. Every run re-takes all of these
and compares each one against the bytes committed here, under the measured
floor described below; a picture that had stopped being the HUD would end
the run nonzero and name itself, rather than sitting in this directory
looking as finished as the others (B74).

The desktop behind the HUD is flat `#31353B`, deliberately **not** a
`personality/theme.toml` colour, so the paper can never be mistaken for
Jarvis's own palette. Without something behind it the plates' `0.86`
opacity — the glass the whole panel is made of — would be invisible.

In the three-screen shots the black band below the right-hand two thirds
is not a colour choice: those monitors are 1080p and the primary is 1440p,
so there is simply no screen there. That is the desk.

## What the harness checks before it writes a PNG

The pictures are the deliverable, but the measurements are why this exists
rather than being a nicer version of the contact sheet. `shoot.py` fails
the run — no PNGs — unless all of the following hold, none of which any
QML engine can answer:

- **The HUD is on every monitor, in the corner it claims.** Everything
  drawn on each output falls inside the 300x826 box `shell.qml` anchors to
  the top-right, and the gap to the right edge is `inset_px`. *Verified it
  bites: anchoring the surface `left` instead of `right` fails; making one
  surface instead of one per screen fails.*
- **And it earns its left inset on a screen it does not fit.** The 280 px
  output has 248 px of room between the insets and the surface on it is
  300 px wide, so the only thing standing between a plate and the part of
  the surface that is off the screen is the HUD's own clamp. Nothing drawn
  on any output may start inside the left inset. *Verified it bites: the
  clamp measured in a QML engine (D66) is what this puts on a compositor.*
- **A 300 px surface on a 280 px screen is granted 300 px.** Read out of
  the HUD's own `WAYLAND_DEBUG` log — one `zwlr_layer_surface_v1.configure`
  per output, all four `300x826`. The census is the control: a regex that
  stopped matching, or a shell that mapped nothing, both come back empty,
  and "nothing was configured wrongly" is true of an empty log.
- **The keyboard never moves.** The seat's focused node is read with no
  HUD running and again while the HUD is drawing, and must be identical.
  *Verified: `WlrKeyboardFocus.Exclusive` fails.*
- **Earned emptiness is real emptiness** — two different darks, and both
  are now measured on **every output the compositor has**, the three
  monitors and the 280 px one. That screen sits outside the desk capture on
  purpose, so each dark is asked about it through a second 0.3 Mpx exposure
  of its own rather than through the 33 Mpx wide one. The **idle** dark is
  no frames at all: nothing published, no surface mapped, every screen
  pixel-identical to the bare desktop. The **quiet** dark is `01-quiet` —
  frames arrive and every plate decides it has nothing true to say, which
  is the case where a plate drawing a zero-height sliver or an empty
  rectangle of glass would be a bug. Neither costs a picture: the narrow
  exposure is read and thrown away, and the sheet stays at ten PNGs.
  *Verified: a health plate that shows a well machine fails.*
- **No space is reserved.** Each workspace's usable rect must still be the
  whole monitor. On today's corner-anchored surface this proves nothing —
  the protocol ignores an exclusive zone on a corner — and it is kept for
  the day the anchors change; `shoot.py` says so at length, with what was
  tried.
- **A click over the HUD reaches the window underneath.** An ordinary
  window is opened filling the primary monitor and a second one on a side
  monitor to hold the keyboard, and three points are clicked: one clear of
  the HUD (the control — without it a harness whose clicks went nowhere
  would report a perfect pass-through), one on a pixel the HUD actually
  painted, and one inside the 300x826 surface box that it painted nothing
  on. All three must end with the keyboard on the window under the HUD.
  *Verified: deleting `mask: Region {}` fails on the painted pixel; a mask
  covering only the lower, unpainted half of the box passes that one and
  fails the third.*

  This is the last of invariant 10's structural promises to stop being a
  reading of the source (A32), and it is worth being exact about what the
  measurement is. The window's own `wl_pointer` never fires: a headless
  seat has no input device, so it advertises no pointer capability and no
  client binds one. The button is synthesised through sway's IPC and the
  witness is **sway's own routing**, read back over IPC — which is the
  hit test, since `node_at_coords` consults each layer surface's input
  region before it ever looks at a window. The probe runs last (it puts
  windows on screen, and every photograph above needs a bare desktop) and
  with **no jarvisd at all**: it needs a lit HUD that does not expire, and
  a bus the HUD cannot see is the one thing it says indefinitely. *Verified
  that this cannot go vacuous: widening `LinkState.graceS` so the plate
  never arrives fails the probe rather than passing it — an unmapped
  surface passes every click whatever its mask says.*

- **A shot of two plates is a shot of two plates.** `04-unheard` is the
  first picture here whose subject is a *live reading* rather than an
  event, and it is photographed twice. First with an **audible** sink —
  which lights `StatePlate` and nothing else, because SPEAKING has been
  drawn off `jv-voice`'s frame alone since A3 — and then with the mute,
  and the drawn region must have grown *downwards* with its top and right
  edges unmoved. That is a plate arriving under another one on a stack
  docked to the corner. Without it, an `OutputState` that had stopped
  drawing would still produce a perfectly sharp photograph of one plate,
  under a caption describing a line that is not in it. (The left edge
  travels outwards, because OUTPUT MUTED is a longer line than SPEAKING.)

  The same shot is also the first one the harness has to **hold**. Every
  other picture here is of a frame that stands on its own for longer than
  a camera takes; `OutputState` believes a `context.system` snapshot for
  three of `jv-context`'s periods, and a heartbeat speaks for two of its
  own `period_s`. So the settle *is* a feed, at the 1 Hz `jv-context`
  publishes at all day.

  *Measured, rather than argued, because the argument overstates it:*
  publishing the pair **once** and sleeping writes the same picture
  today, byte for byte. One exposure reaches `grim` about two seconds
  after the publish and the snapshot expires at three, so publish-once is
  inside the window — by under a second, on this machine, with this
  shot's single capture. The feed is what stops that margin from being
  the thing that makes the picture right: the frames are true at the
  instant of every exposure whatever else is happening, and they stay
  true if the shot grows a second monitor (a 33 Mpx `grim` and a PNG
  encode each) or the settle gets longer. The far end of that margin is
  not hypothetical — the live-lit window below published a heartbeat
  once, and **jv-voice lost** arrived under the plate it was holding
  still.

- **The HUD renders nothing while nothing changes.** Commits are counted
  on the HUD's own side of the Wayland socket (libwayland's
  `WAYLAND_DEBUG` log) over **six** six-second windows, all of which
  must be **zero**:

  1. **quiet** — a live bus carrying a `context.system` snapshot every
     second that the HUD has nothing to say about. The surface is
     unmapped, and the question is whether a frame *arriving* is a frame
     *drawn*.
  2. **lit** — a plate on screen with no further input at all: no
     `jarvisd`, `LinkPlate` after `LinkState`'s grace. The first
     measurement of stillness as a property of what the elements *do*.
  3. **live and lit** — both at once, which is the state the HUD is
     actually in on a running machine. `jv-voice` says it is speaking and
     a muted snapshot arrives every second, so **SPEAKING** and
     **OUTPUT MUTED** sit on screen for the whole window while `seq` moves,
     `OutputState`'s expiry timer re-arms, and every binding downstream of
     the snapshot re-evaluates to the same value. A commit here would be a
     re-render on *bookkeeping* — the one way of spending the budget that
     neither window above can see.
  4. **mic and health** — live and lit again, with the other two plates
     this harness can hold (A43). One `jv-ears` heartbeat describing a
     device that is **open and delivering nothing** says two things at
     once: **MIC NO AUDIO** on `MicState`'s reading, and
     **jv-ears DEGRADED** in the service's own word for itself. Re-publish
     that single frame at 1 Hz and both plates sit there. Window 3 cannot
     reach them, and it cannot see how they fail either: `HealthPlate`
     renders a *list*, and a roster rebuilt into a fresh array on every
     heartbeat is a `Repeater` model that changed whether or not a word in
     it did. Window 3's findings list is empty the whole time, and an empty
     list rebuilt is still nothing on screen.
  5. **heard and confirm** — the last two plates in the stack, and the only
     two whose words come off a **latch** (A48). Everything the four
     windows above hold is a *reading*: `OutputState` believes a snapshot
     while the snapshots keep coming, `MicState` and `HealthState` read the
     heartbeat in front of them. `HeardState` remembers a final transcript
     because partials ride the same topic and would blank the sentence;
     `ConfirmState` remembers a question because the *answer* lands on the
     same topic and would erase it. So an arriving frame does something
     here it does nowhere above — it **re-takes the latch**: the envelope
     is replaced, `transcriptKey`/`requestKey` move, `armHold`/`armExpiry`
     run and a one-shot timer restarts, once a second, while **HEARD** and
     **CONFIRM** do not move a pixel. A plate that did anything visible
     when its latch was re-taken would be invisible to all four windows
     above.
  6. **and what came of it** — the same turn as window 5, carried to its
     end, and `ActionPlate` is the last plate in the stack that had never
     been watched standing still (A49). The user answers, `jv-act` runs
     `fs.trash`, and it fails: **HEARD** stays where it is and
     **ACTION FAILED** arrives under it with the tool and the error word.
     It is the same broker and the same shell as window 5 — *not* a sixth
     pair of processes, because a window per plate is how a probe stops
     being a measurement and becomes a fixture — and that is what makes it
     the only stretch in this harness where anything has ever **left** the
     screen. It has to: an outcome landing while `ConfirmPlate` still
     stood would be jv-act having run a tool it was still asking
     permission for, and `ConfirmState` would hold that question up quite
     happily. The arriving frame also does one thing here it does nowhere
     above. Re-taking `HeardState.transcript` replaces an envelope and
     re-arms a timer; re-taking `ActionState.failure` does that *and*
     re-runs `toolFor()`, which reaches back to the `intent.action` still
     on the bus, compares its `request_id` and re-resolves the tool name
     from scratch — a binding that reads a **second topic** every time the
     first one arrives, once a second, while the same three words sit
     there.

  Measured: 0, 0, 0, 0, 0 and 0. The fade-in that put the blind plate there cost
  42 commits across the three surfaces and then stopped; lighting SPEAKING
  and then OUTPUT MUTED under it cost 82 across the two steps, and the
  plate that arrived was 41 px taller than the one above it alone; lighting
  MIC and then MIC NO AUDIO with jv-ears DEGRADED under it cost 84, also
  41 px taller; lighting HEARD and then the question above it cost 77, the
  drawn region growing 94 px to (2284, 16, 2543, 178) as `ConfirmPlate`
  docked at the top of the stack and pushed the heard line down. (85 and 84
  on earlier runs of the same HUD — a fade's frame
  count is not a fixture, which is why only the zeros are asserted.) Then the
  user answers, the question goes, and the region falls back **94 px to
  (2284, 16, 2543, 84)** — the very box the heard line occupied before it
  was asked, to the pixel. ACTION FAILED arriving under it cost 36 commits
  and grew the region 78 px to (2284, 16, 2543, 162). Nothing had to be fixed to get window 4 to zero — the
  `Repeater` rebuild above is a real thing that happens once a second on a
  degraded machine, and it costs no commit. Nothing had to be fixed for
  window 6 either, and its `toolFor()` re-resolution is the same kind of
  thing: a second topic read once a second, arriving at the same string.

  Window 3 was impossible before A40. Every other lit state in this HUD is
  a frame ageing out — a heartbeat speaks for two of its own periods, a
  confirmation for the window `jv-act` declared — so the only thing a
  harness could hold still was a HUD with **no bus at all**, and that
  zero is partly a fact about the silence. `OutputState` is a live reading
  of two topics rather than a latch, so it stays true for exactly as long
  as the frames keep coming.

  *Verified that none of the six can go vacuous.* Each is paired with a
  stretch that must contain commits — the HUD being woken by a real
  jv-ears heartbeat, the blind plate arriving, the speaking/muted pair
  arriving, the mic/health pair arriving, the question arriving over the
  transcript, the failure arriving under it — counted by the same code
  through the same log. That control
  is not decoration: it is what caught the first version of this probe,
  whose pattern expected `wl_surface@41` where this libwayland writes
  `wl_surface#41`, and which would otherwise have reported a flawless zero
  forever. The live-lit window carries two more guards of its own, because
  it has two more ways to lie. It is lit in **two steps** — an audible
  sink first, then the mute — and the drawn region then has to grow
  *downwards* with its top and right edges unmoved, which is what a plate
  arriving under another one looks like on a stack docked to the top-right.
  Otherwise the thing being held still might be `StatePlate` alone, with
  `OutputPlate` never having appeared. (The left edge does travel outwards:
  OUTPUT MUTED is a longer line than SPEAKING. The first version of the
  check called that a failure.) And the region is
  re-measured after the window and must be identical, because
  `OutputState` stops believing a snapshot after three of `jv-context`'s
  periods: a window that stopped feeding would watch the plate leave, and
  an unmapped surface commits nothing. *Both were verified by mutation:
  replacing the feed with a plain sleep fails on the box, which had shrunk
  back to SPEAKING alone.*

  Window 4 is lit in two steps for the same reason — a healthy jv-ears
  with the device open lights `MicPlate` *alone*, and the health line then
  has to arrive under it — and it carries one guard the other three do
  not need. A heartbeat speaks for two of its own `period_s` and `jv-ears`
  declares 5, so those two plates outlive a six-second silence on their
  own. That is the opposite of window 3, whose feed is life support: here
  the feed is the *subject*, and a feed that stopped would leave the
  photograph intact and quietly turn this back into window 2. So the
  heartbeats published inside the window are counted, and a window that
  measured fewer than two of them fails rather than reporting its zero.

  Window 5 is lit in two steps for the same reason — the transcript alone
  lights `HeardPlate`, and the question then has to arrive and grow the
  region — and it needs window 4's guard for a sharper version of window
  4's reason. A latch does not merely outlive a six-second silence; it is
  *made* to. `ConfirmState` holds the question for the 15 s `jv-act`
  declared in the frame and `HeardState` holds the line for 30, so a feed
  that never ran at all would leave both plates exactly where they are for
  the whole window. The temptation that would have hidden this is worth
  naming: publishing a `window_s` of 600 would make the feed unnecessary
  and the measurement easy, and it would also be a frame no `jv-act` would
  ever send — the same thing A43 refused to do to a heartbeat's
  `period_s`. So the window is jv-act's own 15 s, the re-publishes inside
  the measured window are counted, and fewer than two is a failure.

  Window 6 is lit in three steps, and the middle one is a step nothing
  else in this harness has ever taken. `HeardPlate` is on screen through
  the whole of it, so "something is drawn" is evidence of nothing; the
  region has to **shrink** when the user answers (the same growth rule
  read with its arguments swapped: the stack with the question on it was
  taller, at the same top-right corner) and then **grow** when the failure
  arrives under the heard line. Skipping the answer would have saved a
  step and produced a picture of jv-act reporting a tool it was still
  asking permission to run — `ConfirmState` lets go for an answer naming
  its own `request_id` or for its 15 s, and for nothing else. It needs
  window 5's counted re-publishes for a blunter version of window 5's
  reason: BOTH latches here hold 30 s, so a feed that never ran would
  leave the two plates exactly where they are for the whole window.

  *Verified that window 3 catches what windows 1 and 2 cannot.* The
  mutation is a "freshness" fade — the dot's opacity bound to the age of
  the snapshot, which is the kind of considerate edit nobody would look at
  twice. There is no animation in it and no timer: the binding re-runs
  only when a new frame lands, which is once a second, forever, on a
  running machine. The drawn box never moves and the photographs are
  identical. The quiet window read **0** (the surface is unmapped), A34's
  lit window read **0** (no bus, so no snapshots), and the live-lit window
  read **18** — three surfaces times six seconds. An infinite
  `SequentialAnimation` inside the same plate, by contrast, is caught by
  the lit window too: an animation runs whether or not anyone can see it,
  and that is the failure the first two windows were already built for.

  *Verified that window 5 catches what windows 1–4 cannot.* The same
  considerate edit again, moved to the one plate only this window has ever
  held: the CONFIRM dot's opacity bound to the age of `jv-act`'s question —
  which is not an invented temptation, because A21 is an open item asking
  this plate to show how much of the answer window is left. There is no
  animation in it and no timer; the binding re-runs only when the latch is
  re-taken, which is once a second for as long as a question stands.
  `ConfirmPlate` is dark in every other window — nothing above it publishes
  an `action.confirm` at all — so windows 1, 2, 3 and 4 all read **0**
  while the fifth read **15**, three surfaces times five re-publishes. The
  drawn box never moved: (2284, 16, 2543, 178) before and after, the same
  region the unmutated run holds still.

  *Verified that window 4 catches what windows 1–3 cannot.* The same
  considerate edit, moved to the plate only this window can hold: the mic
  dot's opacity bound to the age of `jv-ears`' heartbeat. `MicPlate` is
  dark in every other window — window 2 has no bus and window 3 is
  holding `SPEAKING` and `OUTPUT MUTED` — so windows 1, 2 and 3 all read
  **0** while the fourth read **18**, three surfaces times six seconds,
  under six heartbeats that said the same thing every time. The drawn box
  never moved and the photographs are identical.

  This is invariant 10's cost claim — §06 budgets the ambient scene at
  "under 2 ms of GPU per frame and near-zero when nothing changed", and
  asks that an idle desktop render at 0 fps rather than 60. It is worth
  being exact about which half of that was measured. Only the second. This compositor renders with **pixman**, in software,
  on a headless backend: no frame here took any time on a 1660 SUPER, and
  nothing in this harness can tell you what the ambient scene costs on
  one. What it can tell you is whether the HUD asks to be drawn at all
  when the machine is quiet — which is the half an ordinary edit can take
  away without looking wrong. A plate that pulses, a duration that counts
  up, a `NumberAnimation` left on `loops: Animation.Infinite`: each reads
  as correct in a diff, is invisible in a photograph, and costs a
  composite of three monitors forever.

No pixel colour is asserted anywhere. A font ships a new version, Qt
changes its rasteriser, and a byte comparison fails in a way nobody can
read.

Two runs of an unchanged HUD are **not byte-identical**, and the numbers
are worth stating because a journal entry has already read a clean
`git status` here as evidence that nothing moved (A45). Re-running this
harness against an untouched `shell/jv-hud` changes `02-heard` and
`03-confirm` by a **handful of pixels per monitor** — single values, one
channel, on antialiased glyph edges inside the plate and on the plate's
own rounded corner. Over four renders compared six ways, `01-quiet`
(which draws nothing) and `04-unheard` (two short monospace labels) came
back byte for byte every time, and the two shots carrying a long wrapped
sentence never did: 3 to 111 pixels, never more than 3 per channel, and
never more than 1 between two renders taken back to back.

**These screens are compared anyway** (B74). The run reads every picture
it just took against the one committed in git, through the same
`tools/hudsheet.py` the contact sheet uses — with a floor under it, of
**256 px** per screen and **3 per channel**, which is the measurement
above with a little room and nowhere near what a plate can say. §06's
quietest ink sits more than a hundred values from the glass it is drawn
on, so every word, colour and box the HUD can change is two orders of
magnitude above this floor; what the floor cannot see is a glyph landing
a fraction of a pixel over, which is the thing it is made of. A screen
that only moved by that much is **restored to its committed bytes**, so
a run that changed nothing leaves a clean tree — and a dirty `git status`
here now means the HUD really did draw something else. Look at it, and
commit it. A run that finds a real change ends nonzero and names the
screens that moved.

---

### 01-quiet-desk.png

![all three monitors, nothing on them](01-quiet-desk.png)

**Recorded** from a live bus with nothing published on it. jarvisd is up,
the bridge is subscribed, and every plate has looked at the bus and
decided it has nothing true to say — so all four surfaces stay unmapped
and the screens are just the desktop. This is the HUD's ordinary state,
and the fact that this picture is boring is the whole of §06's earned
emptiness. It is also the control: every other shot here is measured
against it.

Four surfaces, three monitors, one picture. The fourth screen is the
280 px output, which is outside this capture by design — so the run takes
a second exposure of it for every desk shot and insists on the same
verdict there, without writing an eleventh PNG of an empty screen.

### 02-heard-desk.png

![three monitors, each with the same small stack in its top-right corner](02-heard-desk.png)

**Recorded** — `harness/fixtures/sessions/hey-jarvis-clean.jsonl`, the
real wake word and the real transcript, replayed whole onto the live bus —
plus a **composed** jv-ears heartbeat (for the microphone counters) and a
composed `brain.request`, because nothing committed has ever recorded
`sys.health` or a turn reaching jv-brain (B10/A28).

This is the picture **A13 and A27 are blocked on**: the same THINKING, the
same "Hey Jarvis, what time is it?", the same MIC, three times, once per
screen. Right or noise — that is the question, and it is now a question
you can look at instead of imagine. Note that it is your own sentence
being repeated, which is the part A27 minds more than A13 does.

### 02-heard-primary.png

![the 1440p monitor alone](02-heard-primary.png)

The same recorded moment on the 2560x1440 primary, at its real size — the
same frames as the desk shot above, composed heartbeat included. How much
of a 1440p panel the HUD occupies, and how small an 11 px label is on one.

### 02-heard-side.png

![the 1080p monitor alone](02-heard-side.png)

The same recorded moment on a 1920x1080 side monitor, same frames and same
composed heartbeat. The plate is the same number of pixels on both, so it
is proportionally larger here — the contact sheet renders one plate and
cannot show that; two screens side by side can.

### 03-confirm-desk.png

![three monitors, each with an ember-bordered question](03-confirm-desk.png)

**Composed** — nothing committed has recorded jv-act asking. The one thing
this HUD ever shows that is waiting on *you*, on all three screens at
once, with the only ember border in the design. If three copies of
LISTENING is a question, three copies of a question with a 15-second
window is a sharper one.

### 03-confirm-primary.png

![the confirmation at 1440p](03-confirm-primary.png)

The same composed request at real size on the primary. The summary is
jv-act's own sentence, wrapped to the plate's width, over the tool id —
and it can only be read: the surface takes no input at all, so answering
stays with your voice or `jv confirm` (invariant 3).

### 03-confirm-narrow.png

![the same confirmation on a 280px screen, between two 16px insets](03-confirm-narrow.png)

**Composed**, the same frames as the two above, on the one screen in this
sheet that is not ares: a 280x1080 output narrower than the HUD's own
300x826 surface. There is no monitor like it on this machine and there is
not meant to be — it exists because `shell.qml` asks every screen for 300
px of corner, and what a compositor does with that request on a smaller
screen had been **assumed** in three comments and never once observed.

It is granted as asked. All four of this run's layer surfaces are
configured `300x826`, the narrow one included, so the surface really does
hang 36 px off the left of that screen — measured from the HUD's own side
of the Wayland socket, not inferred from this picture, because the picture
cannot tell the two readings apart. What keeps a sentence from being laid
out in the part that is not there is the HUD's own clamp: plate room is
`min(surface width, screen width)` less an inset at each edge.

You can see it do its work by putting this beside the primary shot above
— the same request, the same wrap, 16 px from the right edge on both:

| | the plate | the room it had |
|---|---|---|
| primary, 2560 px | 260 px | capped by `ConfirmPlate`'s own 260 px limit |
| narrow, 280 px | 248 px | 280 less 16 px of inset at each edge |

Twelve pixels, and they are the whole difference between a HUD that knows
what screen it is on and one that draws 36 px of a question where no
screen is. The left gap here is 16 px, the same inset §06 gives the top
and the right.

### 04-unheard-primary.png

![SPEAKING, with OUTPUT MUTED under it, on the 1440p monitor](04-unheard-primary.png)

**Composed** — nothing committed has recorded jv-voice speaking, and no
recording carries a muted mixer. The only picture in either sheet where
two plates **disagree about whether Jarvis is working**: the top one says
an utterance is in flight, the one under it says none of it is arriving.
Both are true. Of all the ways a voice assistant fails, this is the one
with the least evidence attached — no service is unwell, nothing errored,
the audit log is clean, and the only thing wrong is a toggle somewhere
else on the machine (A40).

The second line is on screen only because `jv-voice` published
`output_device_pinned: 0` in its heartbeat — it took the default output
device, so the sink `jv-context` can see is the one the samples land on
(A41). Pin a device and this plate goes dark rather than becoming a
confident statement about the wrong mixer.

The mic plate is absent, and that is the honest picture: nothing on this
bus published `jv-ears`' counters, and invariant 10's recording light is
not drawn on a guess.

### 05-preempted-primary.png

![PREEMPTED, alone in the corner of the 1440p monitor](05-preempted-primary.png)

**Composed** — nothing committed has recorded jv-voice preempting its own
sentence. One frame, one plate, one word, on the primary: `speech.state`
with `state: interrupted` and `reason: preempted`, which is the body
`services/jv-voice` publishes when an **urgent** utterance arrives while an
interruptible one is being spoken. The rest of that turn is dropped, not
resumed.

The word is the whole picture. Until B91 every stopped sentence reached
this plate as **INTERRUPTED**, which is true of both of the ways a sentence
can stop and tells you nothing about which one happened — you talking over
Jarvis, or Jarvis talking over itself. **PREEMPTED** is the second one, and
it is the one you did not do: the only evidence that something you never
asked for took the floor. Everything else in the corner is dark, because
nothing else in this HUD reads a `reason`.

**And you would never catch it.** jv-voice publishes `idle` in the
statement straight after this one, with nothing awaited in between, and
`idle` draws nothing at all — so what is photographed here is on screen for
as long as it takes one frame to follow another over a Unix socket. That is
true of INTERRUPTED too, and has been since the plate was built; this is
the first place in the repo that says so. Whether a word nobody can read is
worth drawing is a question for a human (PLAN B94), and it is a better
question with a picture attached.

### 06-lossy-primary.png

![MIC LOSING AUDIO, with jv-ears DEGRADED under it, on the 1440p monitor](06-lossy-primary.png)

**Composed** — nothing committed has recorded a microphone dropping
chunks. The first photograph in this repo of the recording light saying
anything but a bare **MIC**. The device is open and audio is arriving on
time; what is wrong is that some of it never got here — `jv-ears`' hand-off
queue overflowed, or the device discarded input before `jv-ears` ran — and
every gauge the confident reading is built on stays perfectly fresh through
that. Without a word of its own, this recording would look exactly like the
one in [`03-confirm-primary`](#03-confirm-primarypng), which really is
keeping all of it: the same plate, the same **teal** dot, the same three
letters. (An anchor rather than the file name, because every PNG in this
directory is shown in exactly one section and a gate says so.) Here the dot is `warn` and the line is **MIC LOSING AUDIO** (A84).

**Both lines come from one heartbeat**, and that is the other half of what
this picture is for. `jv-ears DEGRADED` is not a second service agreeing —
it is the same `sys.health` frame read by a second element, because
`CaptureMeter.health()` calls a losing device degraded in the beat that
reports the loss. Every other two-plate picture in this sheet needs two
publishers; these two cannot be photographed apart, and the corner shows
the fault and who owns it in one arrival.

What the picture cannot show is how much was lost or by whom. That is in
the heartbeat's `notes` — *"microphone losing audio: jv-ears dropped 0.4s
and 1 device overrun (length unknown) since start"*, both culprits named
separately because they send you to different places — and `HealthPlate`
draws the service and the word and nothing else. The HUD tells you the
recording has holes in it; `journalctl -u jv-ears` tells you whose.
