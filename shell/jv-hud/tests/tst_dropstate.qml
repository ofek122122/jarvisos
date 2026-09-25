// DropState — "did the bus throw frames away", under test (PLAN A75).
//
// `drops` has been in schemas/sys.health.json since v1 — "frames dropped
// since the last heartbeat, keyed by topic, published by jarvisd per slow
// subscriber" — jarvisd's broker really fills it, `jv health` really prints
// it, and until this element nothing in shell/jv-hud read the field at all.
// What it is FOR is one sentence: invariant 5 says nothing blocks the bus,
// and the one moment that promise is broken is the one moment the corner
// above it may be drawn from the frames that got through rather than from
// all of them.
//
// The failures worth writing tests around are the ones that would make the
// row worse than the silence it replaces:
//
//   · becoming a gauge. `drops` is absent or empty on a healthy machine
//     (the schema says so), and a row reading "0 DROPPED" all day is the
//     readout nobody reads on the day it matters (§06's earned emptiness).
//     Zero is not news here — unlike VramState, where 0 MiB free is the
//     reading that explains the most.
//   · showing an interval's news for longer than the interval. The count
//     describes the stretch since the last heartbeat and the next one is
//     due in `period_s`. Two periods is the schema's rule for presuming a
//     SERVICE dead, and borrowing it here would leave a drop on screen for
//     twice the window it happened in.
//   · attributing the broker's aggregate to the reader. The map is summed
//     across every subscriber connection before it is published, so the
//     HUD may have lost nothing at all — the row says the BUS dropped
//     something, and no test here lets it say anything narrower.
//   · reading `drops` off a body that is not the broker's. jv-ears never
//     sets the field; a heartbeat that did would be a service claiming a
//     fact only jarvisd can see.
//   · totalling a map it cannot total. One unreadable value makes the
//     total wrong by an unknown amount, and the total is the only thing
//     this row says.
//
// Headless, like the rest of core/: DropState is pure QtQuick and reads the
// bus through core/BusModel, driven with the same JSON lines jv-hud-bridge
// writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "DropState"

  // The stand-in for CLOCK_MONOTONIC. Every frame is delivered at its own
  // `ts` so it lands zero seconds old; winding this forward is how the
  // freshness window is made to lapse without waiting for it.
  property real fakeNow: 0

  Component {
    id: busModel
    BusModel {}
  }

  Component {
    id: dropState
    DropState {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (see tst_speechstate).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // A DropState on a live, subscribed link, with a clock we drive.
  // opts: { down: true } to leave the link down,
  //       { broker: name } to watch a differently-named broker,
  //       { bus: obj } to hand it something other than a BusModel.
  function makeDrops(opts) {
    const o = opts || {};
    suite.fakeNow = 0;
    const out = spawn(dropState);
    if (o.broker !== undefined)
      out.broker = o.broker;
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

  // One heartbeat. opts: { drops, src, service, period, ts, conf, v, seq,
  // noTs, noDrops, state }. `drops` may be any JSON value, because half of
  // these tests are about a map that is not a map.
  function beat(out, opts) {
    const o = opts || {};
    const src = o.src !== undefined ? o.src : "jarvisd";
    let body = {
      "service": o.service !== undefined ? o.service : src,
      "state": o.state !== undefined ? o.state : "ok",
      "uptime_s": 120,
      "period_s": o.period !== undefined ? o.period : 5
    };
    if (o.noDrops !== true)
      body.drops = o.drops !== undefined ? o.drops : ({ "audio.vad": 2 });
    let env = {
      "topic": "sys.health",
      "seq": o.seq !== undefined ? o.seq : suite.nextSeq++,
      "src": src,
      "conf": o.conf !== undefined ? o.conf : 1.0,
      "v": o.v !== undefined ? o.v : 1,
      "body": body
    };
    if (o.noTs !== true)
      env.ts = o.ts !== undefined ? o.ts : suite.fakeNow;
    suite.deliver(out, env);
    return env;
  }

  // A bus that still HOLDS the broker's heartbeat and says the link is
  // down. A BusModel can never be in that state — `applyLink(false)` wipes
  // its caches — which is exactly why the link check in DropState has to be
  // written rather than inferred from the model that happens to back it
  // today. `ageOf` answers 0, so freshness cannot be what takes the row off.
  function frozenBus(up) {
    return {
      "linkUp": up,
      "latestFrom": (topic, src) => topic === "sys.health" && src === "jarvisd" ? ({
        "topic": "sys.health",
        "ts": 0,
        "seq": 1,
        "src": "jarvisd",
        "conf": 1.0,
        "v": 1,
        "body": {
          "service": "jarvisd",
          "state": "ok",
          "uptime_s": 120,
          "period_s": 5,
          "drops": ({ "audio.vad": 4 })
        }
      }) : null,
      "ageOf": envelope => 0
    };
  }

  function test_a_bus_that_kept_the_frame_through_a_link_loss_is_not_read() {
    const up = suite.makeDrops({ bus: suite.frozenBus(true) });
    verify(up.reporting, "control: the same frame with the link up is news");
    compare(up.line, "4 DROPPED");
    const down = suite.makeDrops({ bus: suite.frozenBus(false) });
    verify(!down.reporting, "a count from a link that is gone describes a broker "
                            + "the HUD can no longer see");
    compare(down.line, "");
  }

  // --- nothing to say ----------------------------------------------------

  function test_says_nothing_on_an_empty_bus() {
    const d = suite.makeDrops();
    verify(!d.reporting, "a bus with nothing on it is not a bus dropping frames");
    compare(d.line, "");
    compare(d.dropped, -1);
  }

  function test_says_nothing_while_the_link_is_down() {
    const d = suite.makeDrops({ down: true });
    suite.beat(d, {});
    verify(!d.reporting, "a HUD that cannot see the bus reports nothing");
    compare(d.line, "");
  }

  function test_a_heartbeat_with_no_drops_field_is_silence() {
    const d = suite.makeDrops();
    suite.beat(d, { noDrops: true });
    verify(!d.reporting, "the schema says absent means none");
    compare(d.line, "");
    compare(d.dropped, -1);
  }

  function test_an_empty_drops_map_is_silence() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({}) });
    verify(!d.reporting, "the schema says empty means none");
    compare(d.line, "");
  }

  // Zero is not a reading here, and this is the one place DropState parts
  // company with VramState on purpose: a free-VRAM figure of 0 is the most
  // informative reading that field can carry, and a drop count of 0 is the
  // healthy machine the row must stay off.
  function test_a_map_that_totals_zero_is_silence() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": 0, "_lagged": 0 }) });
    verify(!d.reporting, "nothing was dropped, so there is nothing to say");
    compare(d.dropped, 0, "the total is still readable — it is just not news");
    compare(d.line, "");
  }

  function test_an_unfed_element_says_nothing() {
    const d = suite.spawn(dropState);
    verify(!d.reporting, "no bus at all is the same nothing as a dead link");
    compare(d.line, "");
  }

  // --- the reading -------------------------------------------------------

  function test_one_dropped_frame_is_news() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": 1 }) });
    verify(d.reporting, "invariant 5 was broken once, which is once");
    compare(d.dropped, 1);
    compare(d.line, "1 DROPPED");
  }

  // The count is the TOTAL. Three keys is the ordinary case on a busy
  // machine and a row that showed only the worst one would understate.
  function test_every_key_in_the_map_is_counted() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": 2, "audio.transcript": 3, "sys.health": 1 }) });
    compare(d.dropped, 6);
    compare(d.line, "6 DROPPED");
  }

  // `_lagged` and `_ctl` are the broker's own keys for two failures that are
  // not topic overflows (A77). They are summed in, because all three are a
  // delivery this bus did not make — and the row's word is the broker's own.
  function test_the_brokers_own_keys_are_counted_like_any_other() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "_lagged": 40, "_ctl": 1 }) });
    compare(d.dropped, 41);
    compare(d.line, "41 DROPPED");
  }

  // The 300 px surface is sized to the longest line any plate may draw
  // (`jv-compat DEGRADED`), so every branch of this renderer is bounded.
  function test_a_count_past_four_digits_is_capped_rather_than_widening_the_box() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": 9999 }) });
    compare(d.line, "9999 DROPPED");
    suite.beat(d, { drops: ({ "audio.vad": 10000 }) });
    compare(d.line, "9999+ DROPPED", "a five-digit count may not widen the plate");
    compare(d.dropped, 10000, "the capping is the rendering, not the reading");
  }

  // A count is a count. The broker adds 1 per dropped frame, so a
  // fractional total is a body this element may not total.
  function test_a_fractional_count_is_refused() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": 1.5 }) });
    verify(!d.reporting, "the schema's own type for these values is integer");
    compare(d.dropped, -1);
  }

  function test_a_negative_count_is_refused() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": -1 }) });
    verify(!d.reporting, "the schema's own minimum is 0");
  }

  // One unreadable value makes the total wrong by an unknown amount, and
  // the total is the only thing this row says. So the FRAME is refused,
  // not the key — a partial total presented as a total is the failure this
  // repo keeps finding.
  function test_one_unreadable_value_refuses_the_whole_total() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": 2, "sys.health": "lots" }) });
    verify(!d.reporting, "a number that cannot be totalled is not a total");
    compare(d.dropped, -1, "and the reading is unknown rather than 2");
  }

  function test_an_infinite_count_is_refused() {
    const d = suite.makeDrops();
    // 1e999 is what an oversized JSON number parses to, and it is not a
    // count of anything.
    d.bus.ingest('{"t":"frame","frame":{"topic":"sys.health","ts":0,"seq":900,'
                 + '"src":"jarvisd","conf":1.0,"v":1,"body":{"service":"jarvisd",'
                 + '"state":"ok","uptime_s":1,"period_s":5,"drops":{"audio.vad":1e999}}}}');
    verify(!d.reporting, "Infinity is not a number of frames");
  }

  function test_a_drops_field_that_is_not_a_map_is_refused() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: 7 });
    verify(!d.reporting, "the schema's own type for `drops` is object");
    // Numbers, not strings: an array of strings is refused by the
    // per-value check whatever the shape test does, which makes it no test
    // of the shape test at all.
    suite.beat(d, { drops: [2, 3] });
    verify(!d.reporting, "an array is not a keyed map either");
  }

  // --- whose heartbeat it is --------------------------------------------

  // Only jarvisd can see a slow subscriber. A `drops` map on anybody
  // else's heartbeat is a service claiming a fact it cannot have.
  function test_drops_on_another_services_heartbeat_are_ignored() {
    const d = suite.makeDrops();
    suite.beat(d, { src: "jv-ears", drops: ({ "audio.vad": 99 }) });
    verify(!d.reporting, "only the broker publishes this field");
    compare(d.line, "");
  }

  function test_the_broker_is_named_rather_than_whoever_published_last() {
    const d = suite.makeDrops();
    suite.beat(d, { src: "jv-ears", drops: ({ "audio.vad": 99 }) });
    suite.beat(d, { src: "jarvisd", drops: ({ "audio.vad": 2 }) });
    compare(d.dropped, 2, "the broker's own count, not the newest frame's");
  }

  // The one that matters on a real machine, and the one the mutation
  // harness had to point out: nine services heartbeat on this bus every
  // five seconds, so the NEWEST `sys.health` frame is almost never the
  // broker's. An element reading `latest("sys.health")` and then checking
  // the name would pass every test above — jv-ears' frame is refused
  // either way — and would take the row off a fraction of a second after
  // it arrived, for the whole life of the machine.
  function test_a_later_heartbeat_from_somebody_else_does_not_take_the_row_off() {
    const d = suite.makeDrops();
    suite.beat(d, { src: "jarvisd", drops: ({ "audio.vad": 7 }) });
    verify(d.reporting);
    suite.beat(d, { src: "jv-ears" });
    suite.beat(d, { src: "jv-voice" });
    compare(d.dropped, 7, "the broker's frame is found by name, not by being newest");
    verify(d.reporting, "the row went out as soon as anybody else spoke");
  }

  // A body naming a different service than the envelope said published it
  // is the same refusal HealthState makes, for the same reason.
  function test_a_body_naming_someone_else_is_refused() {
    const d = suite.makeDrops();
    suite.beat(d, { src: "jarvisd", service: "jv-ears" });
    verify(!d.reporting, "the schema says `service` matches envelope src");
  }

  // The name is configurable for the same reason HealthState's `brain` is:
  // the element does not hardcode a roster it cannot see.
  function test_the_broker_name_is_an_input() {
    const d = suite.makeDrops({ broker: "test-broker" });
    suite.beat(d, { src: "jarvisd" });
    verify(!d.reporting, "jarvisd is not the broker this element was told to watch");
    suite.beat(d, { src: "test-broker" });
    verify(d.reporting);
    compare(d.line, "2 DROPPED");
  }

  // --- bodies this element may not read --------------------------------

  function test_a_schema_version_this_file_was_not_written_against_is_refused() {
    const d = suite.makeDrops();
    suite.beat(d, { v: 2 });
    verify(!d.reporting, "invariant 2: a v2 body means whatever v2 says");
  }

  function test_a_hedged_heartbeat_is_refused() {
    const d = suite.makeDrops();
    suite.beat(d, { conf: 0.6 });
    verify(!d.reporting, "sys.health fixes conf at 1.0; less disagrees with itself");
  }

  function test_a_frame_with_no_clock_is_refused() {
    const d = suite.makeDrops();
    suite.beat(d, { noTs: true });
    verify(!d.reporting, "without a ts there is no age, and so no expiry");
  }

  function test_a_heartbeat_with_no_usable_period_is_refused() {
    const d = suite.makeDrops();
    suite.beat(d, { period: 0 });
    verify(!d.reporting, "period_s is how long this count may speak for");
    suite.beat(d, { period: "5" });
    verify(!d.reporting, "a string is not a period");
  }

  // The state word is not this element's business — a broker that called
  // itself degraded (A76) would still be reporting the same count, and one
  // that says `ok` while dropping is exactly why this row exists.
  function test_the_state_word_does_not_gate_the_count() {
    const d = suite.makeDrops();
    suite.beat(d, { state: "degraded" });
    verify(d.reporting, "the count is the news, whatever the broker calls itself");
    compare(d.line, "2 DROPPED");
  }

  // --- how long an interval's news is news ------------------------------

  // The count describes the stretch since the last heartbeat. One period
  // later the next one is due; two periods is the schema's rule for
  // presuming a service DEAD and is not this window.
  function test_the_count_lapses_after_one_period() {
    const d = suite.makeDrops();
    suite.beat(d, { period: 5 });
    verify(d.reporting);
    suite.fakeNow = 4.9;
    verify(d.reporting, "still inside the period it describes");
    suite.fakeNow = 5.1;
    verify(!d.reporting, "the next heartbeat was due and has not said this again");
    compare(d.line, "");
  }

  // Nothing publishes "the bus has stopped dropping frames" — the next
  // heartbeat simply carries no map. Letting go on a timer is the only way
  // this row ever leaves while nothing arrives.
  function test_the_row_leaves_on_a_timer_with_no_further_frames() {
    const d = suite.makeDrops();
    suite.beat(d, { period: 0.05 });
    verify(d.reporting);
    tryVerify(() => !d.reporting, 2000, "the count outlived its own period on screen");
  }

  // The boundary, and it is the place the two clocks in this file could
  // come apart: a frame that arrives exactly one period old has no time
  // left to wait for, so a window that counted it as fresh would put a
  // count on screen with no deadline armed to take it off again.
  function test_a_frame_that_arrives_exactly_one_period_old_is_not_news() {
    const d = suite.makeDrops();
    // A clean beat first, to pin BusModel's clock: the offset is the
    // largest (ts - elapsed) seen, so the FIRST frame on a bus is always
    // zero seconds old by construction and nothing can arrive late on to
    // an empty one.
    suite.beat(d, { ts: 0, noDrops: true });
    suite.fakeNow = 5;
    suite.beat(d, { ts: 0, period: 5 });
    verify(!d.reporting, "its period had run out in flight");
    compare(d.line, "");
    verify(!d.lifespan.running, "and there was nothing left for a timer to wait for");
  }

  // Two intervals running is the ordinary shape of this failure — whatever
  // blocked the bus for five seconds rarely stops at five — so the row has
  // to be able to come BACK after it has let go once.
  function test_a_lapsed_count_is_replaced_by_the_next_one() {
    const d = suite.makeDrops();
    suite.beat(d, { period: 0.05, drops: ({ "audio.vad": 3 }) });
    verify(d.reporting);
    tryVerify(() => !d.reporting, 2000, "the first count never lapsed");
    suite.beat(d, { period: 5, drops: ({ "audio.vad": 9 }) });
    verify(d.reporting, "the row never came back for the next interval");
    compare(d.line, "9 DROPPED");
  }

  // §06 asks for 0 fps when nothing is happening, and a Timer running on a
  // healthy machine is a thing that exists to change nothing. The control
  // is the third leg: a suite that only ever checks the timer is OFF would
  // pass against an element that never arms one at all.
  function test_runs_no_timer_when_there_is_nothing_to_expire() {
    const d = suite.makeDrops();
    verify(!d.lifespan.running, "an empty bus is running a timer");
    suite.beat(d, { noDrops: true });
    verify(!d.lifespan.running, "a clean heartbeat armed an expiry for a row "
                                + "that is not on screen");
    suite.beat(d, { drops: ({ "audio.vad": 2 }) });
    verify(d.lifespan.running, "control: a real count arms nothing to take it off");
  }

  function test_a_period_is_read_off_the_frame_that_states_it() {
    const d = suite.makeDrops();
    suite.beat(d, { period: 20 });
    suite.fakeNow = 15;
    verify(d.reporting, "a broker beating every 20 s speaks for 20 s");
  }

  // A quiet heartbeat clears the row: the interval that just ended dropped
  // nothing, which is the machine saying so.
  function test_a_later_clean_heartbeat_clears_the_row() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": 3 }) });
    verify(d.reporting);
    suite.beat(d, { noDrops: true });
    verify(!d.reporting, "the newest interval dropped nothing");
    compare(d.line, "");
  }

  function test_a_second_interval_replaces_the_first_rather_than_accumulating() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": 3 }) });
    suite.beat(d, { drops: ({ "audio.vad": 1 }) });
    compare(d.dropped, 1, "the field is per-interval; a running total is jv health's job");
  }

  // The link dropping is not the same as the count lapsing, and it takes
  // the row off for a different reason: a cached count from a link that has
  // since died describes a broker the HUD can no longer see.
  function test_the_link_going_down_takes_the_row_off() {
    const d = suite.makeDrops();
    suite.beat(d, {});
    verify(d.reporting);
    d.bus.ingest('{"t":"link","up":false}');
    verify(!d.reporting, "a count from a link that is gone is not a reading");
    compare(d.line, "");
  }

  // --- what it may not do ----------------------------------------------

  // The map is summed across every subscriber connection before jarvisd
  // publishes it, so the HUD may have lost nothing at all. Nothing this
  // element renders may name a topic, a subscriber or a reader — see A77.
  function test_the_row_names_nobody() {
    const d = suite.makeDrops();
    suite.beat(d, { drops: ({ "audio.vad": 2, "_lagged": 1 }) });
    verify(d.reporting);
    verify(d.line.indexOf("audio") < 0, "the count is an aggregate and names no topic: " + d.line);
    verify(d.line.indexOf("_lagged") < 0, "nor the broker's own keys: " + d.line);
    verify(d.line.indexOf("HUD") < 0, "and never claims whose frames were lost: " + d.line);
  }
}
