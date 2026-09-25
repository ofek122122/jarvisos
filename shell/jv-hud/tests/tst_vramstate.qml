// VramState — "how much of the card is left", under test (PLAN B40).
//
// `gpu_vram_free_mb` has been in schemas/context.system.json since v1 and
// nothing read it until this element. What it is FOR is one sentence: the
// HUD has said `llm CPU RUNG 4` since A6 without ever being able to say
// why, and on ares the why is that 943 MiB of a 6 GB card is free. The
// failures worth writing tests around are the ones that would make that
// line worse than the silence it replaces:
//
//   · becoming a gauge. A VRAM readout on screen all day is one nobody
//     reads on the day it matters (§06's earned emptiness). It may speak
//     only while something is being paid for the shortage — a brain on the
//     CPU floor — and never on its own account.
//   · inventing a shortage. A machine with no GPU publishes no such field
//     AND reports `llm_gpu = 0`, so a missing figure defaulted to zero
//     would draw "0 MiB FREE" under the rung line and explain a CPU brain
//     with a shortage that does not exist. Absent must stay absent — while
//     a real 0 MiB, the most informative reading this field can carry,
//     still has to reach the screen.
//   · showing a figure that has stopped being true. The whole value of
//     this number is that it MOVES: a game starts, a browser closes. A
//     remembered figure is a claim about a machine as it used to be, and it
//     looks exactly like a live one.
//   · standing behind a body it may not read — a v2 schema, a hedged
//     `conf`, a frame with no clock, a figure that is a string or negative
//     or the Infinity `1e999` parses to.
//
// Headless, like the rest of core/: VramState is pure QtQuick and reads the
// bus through core/BusModel, driven with the same JSON lines
// jv-hud-bridge writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "VramState"

  // The stand-in for CLOCK_MONOTONIC. Every frame is delivered at its own
  // `ts` so it lands zero seconds old; winding this forward is how the
  // freshness window is made to lapse without waiting for it.
  property real fakeNow: 0

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: vramState
    VramState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // A VramState on a live, subscribed link, with a clock we drive.
  // opts: { snapshotS } for a different window,
  //       { cpu: false } to leave the brain off the CPU floor (the gate is
  //         ON by default, because almost every test here is about what the
  //         figure does once something is waiting on it),
  //       { down: true } to leave the link down,
  //       { bus: obj } to hand it something other than a BusModel.
  function makeVram(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const out = spawn(vramState);
    if (o.snapshotS !== undefined)
      out.snapshotS = o.snapshotS;
    out.brainOnCpu = o.cpu !== false;
    out.bus = o.bus !== undefined ? o.bus : spawn(busModel);
    if (o.bus === undefined && o.down !== true) {
      out.bus.monotonic = () => suite.fakeNow;
      out.bus.ingest('{"t":"link","up":true}');
    }
    return out;
  }

  // --- building the frames the bridge would write ------------------------

  property int nextSeq: 0

  function deliver(out, env) {
    if (typeof env.ts === "number")
      suite.fakeNow = Math.max(suite.fakeNow, env.ts);
    out.bus.ingest(JSON.stringify({
      "t": "frame",
      "frame": env
    }));
  }

  // One jv-context snapshot. opts: { free, ts, conf, v, seq, noTs,
  // noVram }. `free` may be any JSON value, because half of these tests
  // are about a figure that is not a figure. A raw string body is used for
  // `1e999`, which JSON.parse turns into Infinity and JSON.stringify
  // cannot write.
  function snapshot(out, opts) {
    const o = opts || {};
    let body = {
      "net_online": true,
      "load1": 1.4,
      "mem_used_pct": 38.2,
      "audio_volume": 0.6,
      "audio_muted": false
    };
    if (o.noVram !== true)
      body.gpu_vram_free_mb = o.free !== undefined ? o.free : 943;
    let env = {
      "topic": "context.system",
      "seq": o.seq !== undefined ? o.seq : suite.nextSeq++,
      "src": "jv-context",
      "conf": o.conf !== undefined ? o.conf : 1.0,
      "v": o.v !== undefined ? o.v : 1,
      "body": body
    };
    if (o.noTs !== true)
      env.ts = o.ts !== undefined ? o.ts : suite.fakeNow;
    suite.deliver(out, env);
    return env;
  }

  // --- nothing to say ----------------------------------------------------

  function test_says_nothing_on_an_empty_bus() {
    const vram = makeVram({});
    verify(!vram.known, "a HUD that has heard nothing knows no VRAM figure");
    compare(vram.freeMb, -1);
    verify(!vram.reporting);
    compare(vram.line, "");
  }

  function test_says_nothing_while_the_link_is_down() {
    const vram = makeVram({ down: true });
    verify(!vram.linked);
    verify(!vram.known, "a link that was never up is a machine we cannot see");
    compare(vram.line, "");
  }

  // A bus object that answers nothing: the HUD must not crash on a
  // singleton that is still starting, and it must not claim anything
  // either.
  function test_says_nothing_when_the_bus_cannot_be_read() {
    const vram = makeVram({ bus: ({ "linkUp": true }) });
    verify(!vram.known, "a bus with no latest() is a bus with no frames");
    compare(vram.freeMb, -1);
  }

  // --- the reading -------------------------------------------------------

  function test_reads_the_free_figure_off_the_snapshot() {
    const vram = makeVram({});
    snapshot(vram, { free: 943 });
    verify(vram.known);
    compare(vram.freeMb, 943);
    verify(vram.reporting, "a brain on the CPU floor is something waiting on the card");
    compare(vram.line, "943 MiB FREE");
  }

  // The reading that explains the most: a card with literally nothing left.
  // It must never be mistaken for "no figure" — which is what a sentinel of
  // 0 would have made it.
  function test_zero_free_is_a_reading_and_not_an_absence() {
    const vram = makeVram({});
    snapshot(vram, { free: 0 });
    verify(vram.known, "0 MiB free is the most informative reading this field carries");
    compare(vram.freeMb, 0);
    compare(vram.line, "0 MiB FREE");
  }

  // A machine with no GPU: the field is absent, and jv-brain reports
  // `llm_gpu = 0` for a reason that is not pressure. Inventing 0 here would
  // explain a CPU brain with a shortage that does not exist.
  function test_a_machine_with_no_card_is_not_a_machine_with_no_vram() {
    const vram = makeVram({});
    snapshot(vram, { noVram: true });
    verify(!vram.known, "no gpu_vram_free_mb is no GPU, not an empty one");
    compare(vram.freeMb, -1);
    compare(vram.line, "");
  }

  function test_the_newest_snapshot_wins() {
    const vram = makeVram({});
    snapshot(vram, { free: 4400 });
    snapshot(vram, { free: 943 });
    compare(vram.freeMb, 943, "a VRAM figure is the last one published, never the best one");
  }

  // --- the gate: never a gauge ------------------------------------------

  function test_is_silent_while_nothing_is_waiting_on_the_card() {
    const vram = makeVram({ cpu: false });
    snapshot(vram, { free: 943 });
    verify(vram.known, "the figure is still known");
    verify(!vram.reporting, "a card nobody is waiting on is not news (§06)");
    compare(vram.line, "", "a VRAM readout on screen all day is one nobody reads");
  }

  // An element nobody wired the rung into. The default has to be silence:
  // this row exists to explain the line above it, and one that speaks
  // without having been told the brain is on the floor is the all-day gauge
  // §06 refuses — arrived at by a forgotten binding rather than by a
  // decision.
  function test_an_unfed_gate_is_a_closed_gate() {
    const vram = spawn(vramState);
    suite.fakeNow = 0;
    vram.bus = spawn(busModel);
    vram.bus.monotonic = () => suite.fakeNow;
    vram.bus.ingest('{"t":"link","up":true}');
    snapshot(vram, { free: 943 });
    verify(vram.known, "the figure is there to be read");
    verify(!vram.reporting, "nobody said anything is waiting on the card");
    compare(vram.line, "");
  }

  // The gate is an INPUT, so it can arrive after the frame — jv-brain
  // heartbeats every 5 s and jv-context every second. The line has to
  // appear when the rung is learned, without a new snapshot.
  function test_the_line_appears_when_the_rung_is_learned() {
    const vram = makeVram({ cpu: false });
    snapshot(vram, { free: 943 });
    compare(vram.line, "");
    vram.brainOnCpu = true;
    compare(vram.line, "943 MiB FREE", "the gate is live, not read once at startup");
  }

  // And it has to leave the same way: a brain that got its GPU back (or a
  // heartbeat HealthState stopped believing) takes the explanation with it.
  function test_the_line_leaves_when_the_brain_leaves_the_cpu() {
    const vram = makeVram({});
    snapshot(vram, { free: 943 });
    verify(vram.reporting);
    vram.brainOnCpu = false;
    verify(!vram.reporting);
    compare(vram.line, "");
  }

  // --- what it would take (B46) ------------------------------------------
  //
  // jv-brain publishes the least free VRAM at which its ladder would
  // still land on the card (`llm_gpu_floor_mb`, 5424 MiB on ares), and
  // this element quotes it under the reading. The failures worth pinning
  // are the ones that would make the second row worse than no second row:
  // a requirement standing alone with nothing to compare it against, a
  // requirement rounded DOWN so the pair draws a fit the ladder would not
  // take, and a figure invented here out of a ladder the HUD may not read.

  function test_says_what_the_ladder_would_need_under_what_the_card_has() {
    const vram = makeVram({});
    vram.gpuFloorMb = 5424;
    snapshot(vram, { free: 943 });
    compare(vram.line, "943 MiB FREE", "the measurement is untouched by the requirement");
    verify(vram.needKnown);
    compare(vram.needLine, "NEEDS 5424 MiB");
  }

  // The whole point of the pair: the moment a closed game makes the card
  // enough. Nothing here JUDGES that — no verdict, no colour, no
  // "restart jv-llm" — the two numbers simply stop disagreeing, and the
  // reader can see it without knowing this machine's ladder.
  function test_the_pair_is_quoted_and_never_judged() {
    const vram = makeVram({});
    vram.gpuFloorMb = 5424;
    snapshot(vram, { free: 5600 });
    compare(vram.line, "5600 MiB FREE");
    compare(vram.needLine, "NEEDS 5424 MiB", "the row says the same thing either way");
  }

  // An element nobody wired the floor into draws exactly what this plate
  // drew before B46 — which is also every machine whose brain is already
  // on the GPU, and every machine with no card, because jv-brain
  // withholds the gauge in both.
  function test_an_unfed_floor_is_no_second_row() {
    const vram = makeVram({});
    snapshot(vram, { free: 943 });
    compare(vram.line, "943 MiB FREE");
    verify(!vram.needKnown, "nobody said what the ladder wants");
    compare(vram.needLine, "");
  }

  // The requirement is never the only thing on screen. A reader told
  // "the brain needs 5424 MiB" and not how much the card has cannot do
  // anything with it — it is jv-brain's own rule for its `notes`, and it
  // is this element's for its rows.
  function test_a_requirement_never_stands_without_a_reading() {
    const vram = makeVram({});
    vram.gpuFloorMb = 5424;
    verify(!vram.needKnown, "no snapshot yet: nothing to compare it with");
    compare(vram.needLine, "");
    snapshot(vram, { noVram: true });
    verify(!vram.needKnown, "a machine with no card is not one to quote a floor at");
    snapshot(vram, { free: 943 });
    verify(vram.needKnown, "now there is something to put it beside");
  }

  // And it leaves with the reading. `reporting` gates both rows, so a
  // brain that got its GPU back, a jv-context that went quiet, and a
  // dropped link all take the pair away together rather than leaving half
  // a comparison up.
  function test_the_second_row_leaves_with_the_first() {
    const vram = makeVram({});
    vram.gpuFloorMb = 5424;
    snapshot(vram, { free: 943 });
    verify(vram.needKnown);
    vram.brainOnCpu = false;
    compare(vram.line, "");
    compare(vram.needLine, "", "half a comparison is worse than none");
  }

  // The floor arrives on jv-brain's 5 s heartbeat and the reading on
  // jv-context's 1 Hz snapshot, so it can land either side of the frame.
  function test_the_second_row_appears_when_the_floor_is_learned() {
    const vram = makeVram({});
    snapshot(vram, { free: 943 });
    compare(vram.needLine, "");
    vram.gpuFloorMb = 5424;
    compare(vram.needLine, "NEEDS 5424 MiB", "the floor is live, not read once at startup");
  }

  // -1 is "the brain is not saying", and 0 is not a floor: a ladder that
  // asks for nothing is not one any rung of jv-brain's has. Neither may
  // become a row — `NEEDS 0 MiB` under a card with 943 MiB free would say
  // the requirement is met while the brain sits on the CPU.
  function test_a_floor_that_is_not_a_quantity_is_no_second_row() {
    for (const bad of [-1, 0, NaN, Infinity]) {
      const vram = makeVram({});
      vram.gpuFloorMb = bad;
      snapshot(vram, { free: 943 });
      verify(vram.reporting, "the reading itself is fine");
      verify(!vram.needKnown, bad + " is not a VRAM requirement");
      compare(vram.needLine, "");
    }
  }

  // Rounded UP, always: the pair exists to be compared, and a requirement
  // rounded to nearest could draw `943 MiB FREE` over `NEEDS 943 MiB` on
  // a ladder that wants 943.4 and would not start.
  function test_a_requirement_is_never_rounded_down() {
    const vram = makeVram({});
    snapshot(vram, { free: 943 });
    vram.gpuFloorMb = 5424.2;
    compare(vram.needLine, "NEEDS 5425 MiB");
    vram.gpuFloorMb = 23500;
    compare(vram.needLine, "NEEDS 23.0 GiB", "22.94 GiB is not 22.9 GiB of requirement");
    vram.gpuFloorMb = 102400.5;
    compare(vram.needLine, "NEEDS 101 GiB");
  }

  // The same unit ladder as the reading above it, so the two rows are
  // always in the same units and the comparison never needs arithmetic.
  function test_the_two_rows_are_written_in_the_same_units() {
    const vram = makeVram({});
    snapshot(vram, { free: 23500 });
    vram.gpuFloorMb = 24000;
    compare(vram.line, "22.9 GiB FREE");
    compare(vram.needLine, "NEEDS 23.5 GiB");
  }

  // --- bodies this element may not read ---------------------------------

  function test_refuses_a_schema_version_it_was_not_written_against() {
    const vram = makeVram({});
    snapshot(vram, { v: 2 });
    verify(!vram.known, "invariant 2: a v2 body is not a v1 body");
  }

  function test_refuses_a_hedged_snapshot() {
    const vram = makeVram({});
    snapshot(vram, { conf: 0.9 });
    verify(!vram.known, "context.system publishes conf 1.0; less disagrees with itself");
  }

  function test_refuses_a_frame_with_no_clock() {
    const vram = makeVram({});
    snapshot(vram, { noTs: true });
    verify(!vram.known, "no ts is no age, and no age is no expiry");
  }

  function test_refuses_a_figure_that_is_not_a_number() {
    const vram = makeVram({});
    snapshot(vram, { free: "943" });
    verify(!vram.known, "a string is not a reading");
    compare(vram.line, "");
  }

  function test_refuses_a_negative_figure() {
    const vram = makeVram({});
    snapshot(vram, { free: -1 });
    verify(!vram.known, "the schema's own minimum is 0; a negative figure is a bug upstream");
  }

  // A figure that is a number and still not a quantity. It cannot arrive as
  // a bridge line — a `1e999` or an `Infinity` on the wire is a line QML's
  // JSON parser refuses whole, and core/BusModel drops it (tst_earsbudgets
  // pins that) — but `bus` is a duck-typed property, and the shot harness
  // already hands the plates bodies built in QML rather than parsed from a
  // line. So the guard is reachable by the path a stub takes, and it is
  // tested by that path: "Infinity MiB FREE" is not a thing to put on a
  // screen.
  function test_refuses_a_figure_that_is_not_a_quantity() {
    for (const free of [Infinity, -Infinity, NaN]) {
      const vram = makeVram({ bus: suite.handmadeBus(free) });
      verify(!vram.known, free + " is not a number of mebibytes");
      compare(vram.line, "");
    }
  }

  // The envelope floor is not the clock's job. A frame with no `ts` is
  // caught today by `ageOf` handing back Infinity — but that is the BUS
  // deciding, and `bus` is duck-typed: a stub that reports an age for a
  // frame that carries no time (the handmade one here does exactly that)
  // would hand this element a figure with no expiry at all. The floor
  // refuses it on its own.
  function test_refuses_a_timeless_frame_even_from_a_bus_that_ages_it() {
    const vram = makeVram({ bus: suite.handmadeBus(943, { noTs: true }) });
    compare(vram.ageOf(vram.snapshot), 0, "this bus really does claim the frame is fresh");
    verify(!vram.known, "no ts is no expiry, whatever the bus says about the age");
    compare(vram.line, "");
  }

  // A bus that answers like the real one and was never near a JSON parser:
  // one fresh context.system snapshot, whatever figure the caller wants in
  // it. opts: { noTs } to leave the envelope with no clock at all.
  function handmadeBus(free, opts) {
    const o = opts || {};
    let envelope = {
        "topic": "context.system",
        "ts": 0,
        "seq": 0,
        "src": "jv-context",
        "conf": 1.0,
        "v": 1,
        "body": {
          "net_online": true,
          "load1": 1.4,
          "mem_used_pct": 38.2,
          "audio_volume": 0.6,
          "audio_muted": false,
          "gpu_vram_free_mb": free
        }
    };
    if (o.noTs === true)
      delete envelope.ts;
    return ({
      "linkUp": true,
      "latest": topic => topic !== "context.system" ? null : envelope,
      "ageOf": env => 0
    });
  }

  // A body that says nothing about the card must not resurrect the last one
  // that did: jv-context publishes every second whether or not it can read
  // the card, so a single failed read is a figure the HUD has to let go of.
  function test_a_snapshot_without_the_field_forgets_the_one_that_had_it() {
    const vram = makeVram({});
    snapshot(vram, { free: 943 });
    verify(vram.known);
    snapshot(vram, { noVram: true });
    verify(!vram.known, "the newest snapshot is the only one that describes now");
    compare(vram.line, "");
  }

  // --- freshness ---------------------------------------------------------

  function test_a_stale_snapshot_is_not_a_reading() {
    const vram = makeVram({ snapshotS: 3.0 });
    snapshot(vram, { free: 943, ts: 0 });
    verify(vram.known);
    suite.fakeNow = 3.5;
    verify(!vram.known, "a 3.5 s old figure describes a card as it used to be");
    compare(vram.freeMb, -1, "and the figure goes with the words — nothing may read it either");
    compare(vram.line, "");
  }

  // A frame that was already too old when it ARRIVED: the age alone has to
  // catch it, with no timer involved. It takes two frames to write, because
  // core/BusModel pins its clock offset off the frames themselves — the
  // first frame a HUD ever sees is age 0 by construction, and there is no
  // other honest answer before one has landed.
  function test_a_frame_that_spent_nine_seconds_in_flight_is_not_a_reading() {
    const vram = makeVram({ snapshotS: 3.0 });
    snapshot(vram, { free: 4400, ts: 0 });
    verify(vram.known);
    suite.fakeNow = 10;
    snapshot(vram, { free: 943, ts: 1 });
    verify(!vram.known, "a snapshot nine seconds in flight is not a reading of now");
    compare(vram.line, "", "and it must not leave the figure it replaced on screen either");
  }

  // Nothing re-evaluates a binding because a clock moved, so the window has
  // to lapse on a timer of its own — the case that matters most here,
  // because a jv-context that dies leaves a plausible figure on screen.
  function test_the_figure_expires_on_its_own_without_another_frame() {
    const vram = makeVram({ snapshotS: 0.05 });
    snapshot(vram, { free: 943, ts: 0 });
    verify(vram.known);
    // Nothing touches `fakeNow`: the wall clock is what has to do the work,
    // through the element's own timer.
    tryCompare(vram, "known", false, 2000);
    compare(vram.line, "");
  }

  // And it revives: a card we stopped seeing is not a card we stop seeing
  // forever.
  function test_a_fresh_snapshot_revives_an_expired_figure() {
    const vram = makeVram({ snapshotS: 0.05 });
    snapshot(vram, { free: 943, ts: 0 });
    tryCompare(vram, "known", false, 2000);
    snapshot(vram, { free: 4400, ts: 1 });
    verify(vram.known, "a new snapshot is a new life");
    compare(vram.line, "4400 MiB FREE");
  }

  // The link dropping is the one thing that invalidates a figure
  // immediately: whatever the card is doing now, we are not watching it.
  function test_losing_the_link_drops_the_figure_at_once() {
    const vram = makeVram({});
    snapshot(vram, { free: 943 });
    verify(vram.known);
    vram.bus.ingest('{"t":"link","up":false,"error":"broker gone"}');
    verify(!vram.known, "a dropped link is a card we can no longer see");
    compare(vram.line, "");
  }

  // And it refuses the frame itself, not just the bus that carries it.
  // core/BusModel drops every frame it holds when the link goes down
  // ("nothing observed means nothing shown"), so the guard inside the
  // reader looks redundant against that one bus — but `bus` is duck-typed,
  // and a stub or a future bridge that kept its last snapshot across a
  // reconnect would hand this element a card it is no longer watching. The
  // gate belongs where the frame is read, once, and this is the test that
  // says so.
  function test_refuses_a_frame_from_a_bus_that_kept_it_through_a_drop() {
    const kept = suite.handmadeBus(943, {});
    kept.linkUp = false;
    const vram = makeVram({ bus: kept });
    verify(!vram.linked);
    verify(vram.bus.latest("context.system") !== null, "this bus really did keep the frame");
    verify(!vram.known, "a card we stopped watching is not a card we may report on");
    compare(vram.line, "");
  }

  // A HUD with nothing to expire runs no timer at all (§06: 0 fps when
  // nothing is happening).
  function test_runs_no_timer_when_there_is_nothing_to_expire() {
    const vram = makeVram({});
    verify(!vram.expiry.running, "an empty bus should arm nothing");
    snapshot(vram, { free: 943 });
    verify(vram.expiry.running, "a believed figure has a deadline");
    snapshot(vram, { noVram: true });
    verify(!vram.expiry.running, "a machine with no card has nothing to count down");
  }

  // --- how the figure is written ----------------------------------------

  function test_rounds_to_whole_mebibytes() {
    const vram = makeVram({});
    snapshot(vram, { free: 943.6 });
    compare(vram.line, "944 MiB FREE", "nothing is decided by a fraction of a MiB");
  }

  // The HUD surface is a fixed 300 px box sized to the longest line any
  // plate may draw. A figure in bare MiB grows with the card, so a big one
  // collapses to GiB rather than reaching past the box.
  function test_a_big_card_is_written_in_gibibytes() {
    const vram = makeVram({});
    snapshot(vram, { free: 23500 });
    compare(vram.line, "22.9 GiB FREE");
  }

  // And an absurd card drops the decimal rather than the box: a machine
  // with a terabyte of VRAM is not a machine this HUD may render badly on.
  function test_an_absurd_card_drops_the_decimal() {
    const vram = makeVram({});
    snapshot(vram, { free: 1048576 });
    compare(vram.line, "1024 GiB FREE");
  }

  // The seam between the units, pinned where the row stops being able to
  // grow: five digits of MiB is the first figure written in GiB, so the
  // widest MiB line is four digits.
  function test_the_unit_seam_is_where_the_row_would_widen() {
    const vram = makeVram({});
    snapshot(vram, { free: 9999, seq: 1, ts: 0 });
    compare(vram.line, "9999 MiB FREE");
    snapshot(vram, { free: 10000, seq: 2, ts: 0 });
    compare(vram.line, "9.8 GiB FREE");
  }

  // The claim the seam exists for, held to the line the box was measured
  // against: the row `HealthPlate` draws is the name plus the figure, and
  // `jv-compat DEGRADED` is the widest thing any plate may say. Every
  // branch of `render` is checked, including the biggest number each one
  // can be handed.
  function test_no_card_can_widen_the_row_past_the_box() {
    const vram = makeVram({});
    const widest = ("jv-compat" + "DEGRADED").length;
    for (const free of [0, 943, 9999, 10000, 99.9 * 1024, 102400, 1048576, 9999 * 1024]) {
      snapshot(vram, { free: free, ts: 0, seq: suite.nextSeq++ });
      verify(vram.line.length > 0, "every one of these is a reading");
      verify(("vram" + vram.line).length <= widest,
             free + " MiB renders as \"" + vram.line + "\", which is wider than the box allows");
    }
  }

  // And neither can any ladder (B46). The second row is drawn under the
  // name `llm`, which is three characters to the reading's four, so the
  // requirement gets one more than the figure does — and `NEEDS ` spends
  // six of them. Every branch, at the biggest number it can be handed.
  function test_no_ladder_can_widen_the_second_row_past_the_box() {
    const vram = makeVram({});
    const widest = ("jv-compat" + "DEGRADED").length;
    snapshot(vram, { free: 943 });
    for (const need of [1, 943, 9999, 10000, 99.9 * 1024, 102400, 1048576, 9999 * 1024]) {
      vram.gpuFloorMb = need;
      verify(vram.needLine.length > 0, "every one of these is a requirement");
      verify(("llm" + vram.needLine).length <= widest,
             need + " MiB renders as \"" + vram.needLine + "\", which is wider than the box allows");
    }
  }
}
