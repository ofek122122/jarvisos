# The HUD, on three monitors

Photographs of the **real** `jv-hud` — quickshell, a layer-shell surface,
its own read-only bridge, a real `jarvisd` — running on a real wlroots
compositor with ares' monitor sizes. Written by `ops/ralph/hudscreens.sh`;
re-run it after any change to `shell/jv-hud` or `personality/theme.toml`
and commit the diff.

This is the companion to [`../README.md`](../README.md), and the two
answer opposite questions. That sheet renders the plates with a plain QML
engine into the 300x560 rectangle the surface declares: the HUD's
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
  drawn on each output falls inside the 300x560 box `shell.qml` anchors to
  the top-right, and the gap to the right edge is `inset_px`. *Verified it
  bites: anchoring the surface `left` instead of `right` fails; making one
  surface instead of one per screen fails.*
- **The keyboard never moves.** The seat's focused node is read with no
  HUD running and again while the HUD is drawing, and must be identical.
  *Verified: `WlrKeyboardFocus.Exclusive` fails.*
- **Earned emptiness is real emptiness.** The quiet shot must come back
  pixel-identical to the bare desktop, on all three monitors. *Verified: a
  health plate that shows a well machine fails.*
- **No space is reserved.** Each workspace's usable rect must still be the
  whole monitor. On today's corner-anchored surface this proves nothing —
  the protocol ignores an exclusive zone on a corner — and it is kept for
  the day the anchors change; `shoot.py` says so at length, with what was
  tried.

No pixel colour is asserted anywhere. A font ships a new version, Qt
changes its rasteriser, and a byte comparison fails in a way nobody can
read.

Two runs of an unchanged HUD are not byte-identical: measured over
consecutive runs, a handful of pixels along an antialiased glyph edge move
by one value. So `git status` after a re-run is not evidence of anything,
and neither is a clean one — look at the picture.

---

### 01-quiet-desk.png

![all three monitors, nothing on them](01-quiet-desk.png)

**Recorded** from a live bus with nothing published on it. jarvisd is up,
the bridge is subscribed, and every plate has looked at the bus and
decided it has nothing true to say — so all three surfaces stay unmapped
and the screens are just the desktop. This is the HUD's ordinary state,
and the fact that this picture is boring is the whole of §06's earned
emptiness. It is also the control: every other shot here is measured
against it.

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
