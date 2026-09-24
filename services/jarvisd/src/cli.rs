//! The pure core of the `jv` debug CLI — latency accounting, utterance
//! tracking, line formatting and exit-status policy.
//!
//! "This CLI is how we debug everything forever", so it is worth testing. All
//! of it lives here rather than in `bin/jv.rs` because an integration test can
//! only observe the binary's stdout; these pieces are where the reasoning is,
//! and they are cheap to pin down directly. `bin/jv.rs` keeps only argument
//! parsing and the async stream loop.

use std::collections::{HashMap, HashSet, VecDeque};

// ---------------------------------------------------------------- envelope reads

/// A field of a msgpack map, or None if absent / not a map.
pub fn get<'a>(v: &'a rmpv::Value, key: &str) -> Option<&'a rmpv::Value> {
    v.as_map()?.iter().find(|(k, _)| k.as_str() == Some(key)).map(|(_, v)| v)
}

/// A string field, or None. Never substitutes a default — a caller that wants
/// one says so, so a missing field is never silently indistinguishable from
/// an empty one at this layer.
pub fn get_str(v: &rmpv::Value, key: &str) -> Option<String> {
    get(v, key)?.as_str().map(|s| s.to_string())
}

/// A numeric field as f64. msgpack narrows on the wire, so an `f64` written by
/// a producer can arrive as an integer or an f32; all three must read back.
pub fn get_f64(v: &rmpv::Value, key: &str) -> Option<f64> {
    match get(v, key)? {
        rmpv::Value::Integer(i) => i.as_f64(),
        rmpv::Value::F32(f) => Some(*f as f64),
        rmpv::Value::F64(f) => Some(*f),
        _ => None,
    }
}

/// One frame as a JSON line. Never panics: a frame we cannot print is still
/// worth reporting as one, in place, rather than killing a tap that may be
/// the only thing watching a live bus.
pub fn to_json(v: &rmpv::Value) -> String {
    serde_json::to_string(v).unwrap_or_else(|e| format!("<unprintable: {e}>"))
}

// ---------------------------------------------------------------- stop policy

/// Why a streaming subcommand stopped.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Outcome {
    /// Delivered the requested `--count` frames.
    Count,
    /// Reached `--for`.
    Deadline,
    /// Ctrl-C.
    Interrupted,
    /// The broker closed the connection.
    BusClosed,
}

/// Process exit status for a finished stream.
///
/// The rule is one thing: **if the caller asked for N frames and did not get
/// N frames, that is a failure.** A script doing `jv sub speech.state -n 1
/// --for 2` needs to tell "here is the frame" from "the bus went away" or
/// "nothing was published", and both of those look like a clean exit
/// otherwise. With no `--count`, any stop is success — an open-ended tap that
/// is Ctrl-C'd or outlives its `--for` did its job.
pub fn exit_code(outcome: Outcome, wanted: Option<usize>, seen: usize) -> i32 {
    match wanted {
        Some(n) if seen < n => 1,
        _ => {
            let _ = outcome;
            0
        }
    }
}

// ---------------------------------------------------------------- latency

/// Nearest-rank percentile of an ALREADY SORTED ascending slice, `p` in
/// 0..=100. Nearest-rank (not interpolated) so every number printed is a
/// latency that was actually measured.
pub fn percentile(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return f64::NAN;
    }
    let rank = (p / 100.0 * sorted.len() as f64).ceil() as usize;
    sorted[rank.saturating_sub(1).min(sorted.len() - 1)]
}

/// Per-topic hop latency (`ts` on the frame -> now in this process),
/// accumulated so `jv tap --latency` can print a summary instead of only a
/// firehose. Invariant 5 says measure, don't assume; a scrolling column of
/// per-frame numbers is not a measurement.
#[derive(Default)]
pub struct HopStats {
    per_topic: HashMap<String, Vec<f64>>,
}

impl HopStats {
    pub fn hop(&mut self, topic: &str, ms: f64) {
        self.per_topic.entry(topic.to_string()).or_default().push(ms);
    }

    pub fn is_empty(&self) -> bool {
        self.per_topic.is_empty()
    }

    /// The summary block, worst p95 first (the interesting end), or an empty
    /// string if nothing was measured — an empty table is noise.
    pub fn summary(&self) -> String {
        if self.is_empty() {
            return String::new();
        }
        let mut rows: Vec<(String, usize, f64, f64, f64)> = self
            .per_topic
            .iter()
            .map(|(topic, v)| {
                let mut s = v.clone();
                s.sort_by(f64::total_cmp);
                (topic.clone(), s.len(), percentile(&s, 50.0), percentile(&s, 95.0), percentile(&s, 100.0))
            })
            .collect();
        // Worst p95 first; topic name breaks ties so the output is stable
        // across runs (a HashMap iteration order is not).
        rows.sort_by(|a, b| b.3.total_cmp(&a.3).then_with(|| a.0.cmp(&b.0)));

        let frames: usize = rows.iter().map(|r| r.1).sum();
        let t = table_topic_columns(&rows.iter().map(|r| r.0.as_str()).collect::<Vec<_>>());
        let mut out = format!("--- hop latency: {frames} frames, {} topics\n", rows.len());
        out.push_str(&format!(
            "{:<t$} {:>5} {:>10} {:>10} {:>10}\n",
            "topic",
            "n",
            "p50",
            "p95",
            "max",
        ));
        for (topic, n, p50, p95, max) in &rows {
            out.push_str(&format!(
                "{:<t$} {n:>5} {p50:>8.2}ms {p95:>8.2}ms {max:>8.2}ms\n",
                clip(topic, t),
            ));
        }
        out
    }
}

/// The widest a topic prints inside a line `jv tap --latency` writes.
///
/// One cap for BOTH views of a topic — the per-frame stream and the summary
/// table under it — because the value of either is that its columns line up,
/// and a label wider than its column breaks the table's alignment exactly as
/// it breaks the stream's width budget. 22 because the table was already
/// built to it; the longest topic any schema declares is `audio.transcript`
/// at 16, so nothing on this bus today is clipped at all.
///
/// The cost is `short_id`'s cost: two topics sharing their first 19
/// characters print alike. The whole topic is one `jv sub '*'` away — that
/// view prints frames, which are raw data and are as wide as they are.
///
/// The table pays that cost only while it can: `table_topic_columns` widens
/// its column past this cap rather than print two topics as one row of
/// numbers (B24). So this is the table's width for every topic set that can
/// be told apart at 22 — which is every topic set this bus can produce — and
/// the STREAM's width always.
pub const TOPIC_COLUMNS: usize = 22;

/// How wide the summary table makes its topic column, for the topics it is
/// about to print.
///
/// `TOPIC_COLUMNS` normally, which is what lines the table up under the
/// per-frame stream — and WIDER when that cap would print two topics as the
/// same label (PLAN B24). A clip is a promise that what it hid is one
/// `jv sub '*'` away, and that promise is good enough for the stream, where
/// every line is about a frame that named itself. It is not good enough for
/// the table, where the label is the only thing saying which topic a row of
/// numbers is about: two rows that cannot be told apart are worse than one
/// row that wraps, so identity outranks alignment here and the column grows.
///
/// It grows by the smallest amount that separates the labels, so the budget
/// is spent only as far as identity needs. That can exceed `TAP_COLUMNS` —
/// deliberately, and only when a distinguishing character sits past column
/// 41 (a row is `columns + 39` wide). Nothing this bus carries comes near
/// it: `audio.transcript` is 16 of the 22.
///
/// The search always finds a width: `topics` are the keys of a map, so at
/// the longest topic's own length nothing is clipped and every label is its
/// whole distinct topic.
///
/// PRINTED labels are compared, never the topics. Comparing topics would be
/// tautological — map keys are distinct, so the column would never grow —
/// and it would also miss a clipped label colliding with a WHOLE one, which
/// needs the shorter topic to end in the marker's own `...`. That second
/// case cannot reach a live tap: `validate_envelope` refuses an empty topic
/// segment, so no topic the broker accepts ends in two dots. It is covered
/// anyway, because nothing in `clip` or `TOPIC_COLUMNS` assumes an alphabet
/// and this should not be the one place that does.
fn table_topic_columns(topics: &[&str]) -> usize {
    let widest = topics.iter().map(|t| t.chars().count()).max().unwrap_or(0);
    (TOPIC_COLUMNS..=widest.max(TOPIC_COLUMNS))
        .find(|columns| {
            let mut seen = HashSet::new();
            topics.iter().all(|t| seen.insert(clip(t, *columns)))
        })
        .expect("unclipped topics are map keys and therefore distinct")
}

/// The widest a publisher's name prints inside one of those lines.
///
/// 13 is `jv-hud-bridge`, the longest `src` on this bus. Like the topic it
/// is CLIPPED rather than assumed, because `validate_envelope` bounds a
/// src's emptiness and never its length: both of these strings are chosen by
/// a remote process, and the one thing a report line may not do is let one
/// of those decide how wide it is.
pub const SRC_COLUMNS: usize = 13;

/// One frame, as `jv tap --latency` streams it above the two tables.
///
/// Here rather than in `bin/jv.rs` so the width test that covers every other
/// line the tap writes as a report can reach this one too (PLAN B23).
///
/// `seq` is signed because the tap reads it defensively — a frame the broker
/// would have rejected prints `-1` rather than being dropped from the
/// measurement silently.
pub fn hop_line(topic: &str, src: &str, seq: i64, ms: f64) -> String {
    format!(
        "{:<t$} {:<s$} seq={seq:<8} hop={ms:8.2}ms",
        clip(topic, TOPIC_COLUMNS),
        clip(src, SRC_COLUMNS),
        t = TOPIC_COLUMNS,
        s = SRC_COLUMNS,
    )
}

/// jv-ears, and the gauge on its heartbeat that says how long it sits in
/// silence before it calls an utterance finished.
///
/// `metrics` is free-form and service-local by schema, so this costs no
/// schema change (invariant 2) — jv-ears already states `wake_timeout_s`
/// there for the HUD (PLAN A14). This is the second reader of that section,
/// and the reason the gauge exists at all: without it the only number this
/// CLI can print about a turn is one that contains the user's own voice.
pub const EARS: &str = "jv-ears";
pub const EARS_HOLD_METRIC: &str = "vad_min_silence_s";

/// jv-ears' endpoint hold in seconds, off ONE `sys.health` frame, or None.
///
/// Refused on the four grounds in `service_metrics` (they belong to the topic,
/// not to either reader), plus a gauge that is not a finite, non-negative
/// duration.
pub fn ears_endpoint_hold_s(frame: &rmpv::Value) -> Option<f64> {
    let metrics = service_metrics(frame, EARS)?;
    get_f64(metrics, EARS_HOLD_METRIC).filter(|h| h.is_finite() && *h >= 0.0)
}

/// The gauge on jv-brain's heartbeat that says how much of `think` was the
/// model. (`BRAIN`, the service name, is declared with the health-report
/// reader further down — it is the same service and the same rule: gauges are
/// read from ITS heartbeat by name, not from whoever published one last.)
pub const BRAIN_FIRST_SAY_METRIC: &str = "llm_first_say_ms";
pub const BRAIN_FIRST_SAYS_METRIC: &str = "llm_first_says";

/// jv-brain's `(turn count, model ms)` off ONE `sys.health` frame, or None.
///
/// `think` (the final transcript -> the first `speech.say`) is the LLM AND a
/// bus hop each way AND whatever jv-brain's input worker was doing when the
/// transcript landed. Nothing on the bus says where inside it the completion
/// request went out, because only jv-brain knows — so jv-brain states it
/// (`TurnTiming` in services/jv-brain/jv_brain/service.py), and this reads it.
///
/// **The count is not decoration.** `sys.health` carries no `utterance_id`, so
/// the only thing tying this number to a turn is that jv-brain publishes the
/// gauge frame IMMEDIATELY after the `speech.say` it measures, on the same
/// connection — which fixes the order the two frames reach a subscriber in.
/// The gauge then stays on every later periodic heartbeat, so a reader that
/// looked only at the number would apply a stale one to the next turn. The
/// count rises once per measured turn and is how a fresh gauge is told from a
/// re-stated one (`TurnStats::brain_split`, and the tap loop in bin/jv.rs).
///
/// Refused on the same grounds as `ears_endpoint_hold_s` — they belong to the
/// topic, not to either reader — plus a count that is not a whole number at
/// least 1: a turn counter with a fraction in it is a frame disagreeing with
/// itself, and there is no reading of it that makes the pair trustworthy.
pub fn brain_first_say(frame: &rmpv::Value) -> Option<(u64, f64)> {
    first_say(frame, BRAIN)
}

/// The same reading, off any service's own heartbeat. `HealthCheck::observe`
/// takes frames from every service and only learns whose the brain's is from
/// the envelope, so it asks by `src`; `brain_first_say` is this with the
/// question already answered.
fn first_say(frame: &rmpv::Value, service: &str) -> Option<(u64, f64)> {
    let metrics = service_metrics(frame, service)?;
    let ms = get_f64(metrics, BRAIN_FIRST_SAY_METRIC).filter(|v| v.is_finite() && *v >= 0.0)?;
    let count = get_f64(metrics, BRAIN_FIRST_SAYS_METRIC)
        .filter(|c| c.is_finite() && *c >= 1.0 && c.fract() == 0.0)?;
    Some((count as u64, ms))
}

/// The `metrics` map of a `sys.health` frame this binary is entitled to read
/// as `service`'s, or None.
///
/// Four refusals, and they belong to the TOPIC rather than to any one reader,
/// which is why both gauges above share them: a schema version this binary was
/// not written against, a hedged `conf` on a state topic, a body naming a
/// service other than the one the broker saw publish it, and no `metrics` at
/// all.
///
/// There is deliberately NO fallback to a service's shipped default anywhere
/// above this. The HUD may fall back — it has to draw something — but this is
/// a measuring instrument, and an instrument that substitutes a constant for a
/// reading is how a number stops meaning what its label says.
fn service_metrics<'a>(frame: &'a rmpv::Value, service: &str) -> Option<&'a rmpv::Value> {
    if get_str(frame, "src").as_deref() != Some(service) {
        return None;
    }
    if get(frame, "v").and_then(|v| v.as_u64()) != Some(1) {
        return None;
    }
    if get_f64(frame, "conf") != Some(1.0) {
        return None;
    }
    let body = get(frame, "body").filter(|b| b.is_map())?;
    if get_str(body, "service").as_deref() != Some(service) {
        return None;
    }
    get(body, "metrics").filter(|m| m.is_map())
}

/// One voice turn, split at the boundaries jv-ears itself publishes.
///
/// ```text
/// speech_start    last speech  speech_end  final transcript first speech.say
///       |--- spoke ----|--- hold ---|---- hear ----|---- think ----|
///       |                                          |-wait-|--model-|
///       |                           |---------- respond -----------|
///       |------------------------- total --------------------------|
/// ```
///
/// Why this is not one number. The Phase 1 exit criterion is "< 2.5 s", and
/// what `jv tap --latency` used to print against it was VAD start -> first
/// speech.say: the user's own speaking time (2-3 s of a typical request)
/// plus everything the machine did. The 5.4 s measured on ares on
/// 2026-09-15 could not be compared to the budget at all, and nothing in
/// the output said so — PHASE1-STATUS carries "decide the measurement
/// anchor" as an open question because of it.
///
/// Each span here has exactly one owner:
///
///   * **spoke** — the user talking. Not the machine's to spend, and not
///     something a faster machine would shorten.
///   * **hold** — jv-ears' `vad_min_silence_ms`, deliberately spent to
///     bridge a mid-sentence pause. Machine time, and tunable.
///   * **respond** — ASR, the brain, and the bus hops between them:
///     everything after ears decided the utterance had ended. It is two
///     services, and the frame that divides them is already on the bus:
///     jv-ears runs whisper AFTER publishing `speech_end` and publishes the
///     `audio.transcript` **final** when it is done, so that frame is the
///     seam. `respond` therefore splits, with no new publisher and no
///     schema change, into:
///       * **hear** — `speech_end` -> the final transcript: jv-ears' ASR.
///       * **think** — the final transcript -> the first `speech.say`:
///         jv-brain, up to its first word, plus the bus hop each way.
///     PHASE1-STATUS names those two as separate open items (ASR fixed at
///     ~2.2 s; prefill fixed, generation not), and one number over both
///     cannot say which one a change moved.
///
/// `think` splits two ways, and the two are mutually exclusive per turn.
///
/// The first needs no new publisher at all. A turn that ran a TOOL spends
/// part of its `think` inside jv-act, and both ends of that are already on
/// the bus: jv-brain publishes `intent.action` and jv-act answers
/// `action.result`, threaded by `request_id`, with the input `utterance_id`
/// carried on the request. So:
///
///   * **tool** — of `think`: the time at least one `intent.action` was
///     outstanding. jv-act's execution AND, when the tool is a confirming
///     one, the whole confirmation window — which is 15 s by design and
///     today looks exactly like the LLM being slow.
///
/// It is the UNION of the round trips and not their sum, because two
/// requests outstanding at once are one moment of jv-act's time; and not
/// the bracket from the first request to the last result either, because
/// jv-brain runs a completion between serial calls and that time is not
/// jv-act's. What it does NOT contain: a tool call that never reached
/// jv-act — a hallucinated name, unparseable arguments, or one past the
/// per-turn cap — is answered inside jv-brain and publishes no
/// `intent.action`, so its time stays in the rest of `think`, where it
/// belongs.
///
/// The second split needs a PUBLISHER rather than a frame that was already
/// there, and applies to a turn that ran NO tool. It contains the LLM AND the bus hop each
/// way AND however long the transcript sat in jv-brain's input queue, and
/// the span PHASE1-STATUS wants to optimise is the model's alone. Nothing on
/// the bus marks the moment the completion request went out, because only
/// jv-brain can see it — so jv-brain states it on its own heartbeat and
/// `brain_first_say` reads it:
///
///   * **model** — the completion request -> the first `speech.say`: the
///     LLM's prefill and generation up to the first sentence closing.
///   * **wait** — `think` less `model`: the two bus hops, the input queue,
///     and jv-brain's own work before the model ran.
///
/// A turn that ran tools publishes no such gauge at all (jv-brain states it
/// only for a first word that came straight out of the first completion), so
/// `wait`/`model` and `tool` never describe the same turn.
///
/// Those two live on `TurnStats` and not on this type, because the gauge
/// arrives one frame AFTER the turn is reported — a turn is printed the
/// moment its first word lands, and is not held back waiting for a number
/// that may never come.
///
/// So the machine's share of a turn is `hold + respond`, and THAT is the
/// number a budget can be argued about. Which span the 2.5 s applies to is
/// a human's call; this type exists so the call can be made against data
/// instead of against one figure that mixes both.
///
/// Every field is optional because every one of them can genuinely be
/// unknown — a tap started mid-sentence never heard the start, and a tap
/// that has not heard jv-ears' heartbeat does not know the hold. None
/// prints as `?`; none of them is ever filled in with a plausible zero.
#[derive(Debug, Clone, PartialEq)]
pub struct Turn {
    /// speech_start -> first speech.say: what the user waited, start to end.
    pub total_ms: Option<f64>,
    /// speech_start -> speech_end: the whole segment, the user's voice AND
    /// the hold ears sat through at the end of it.
    pub speech_ms: Option<f64>,
    /// speech_end -> first speech.say: ASR + brain + bus.
    pub respond_ms: Option<f64>,
    /// jv-ears' endpoint hold, as jv-ears reported it.
    pub hold_ms: Option<f64>,
    /// speech_end -> the final `audio.transcript`: jv-ears' ASR. The first
    /// half of `respond`.
    pub hear_ms: Option<f64>,
    /// The final `audio.transcript` -> first speech.say: jv-brain to its
    /// first word. The second half of `respond`.
    pub think_ms: Option<f64>,
    /// Of `think`: how long at least one `intent.action` was outstanding —
    /// jv-act's share, confirmation window included. None when the turn ran
    /// no tool, and also when it ran one this tap could not time (see
    /// `tool_calls`).
    pub tool_ms: Option<f64>,
    /// How many `intent.action` frames this tap saw for the turn. Kept
    /// beside `tool_ms` because "no tool ran" and "a tool ran and could not
    /// be timed" are different facts and both print `tool=?`.
    pub tool_calls: usize,
    /// Of `tool`: how long at least one `action.confirm` question was open —
    /// YOUR time, not the machine's. None when no confirming tool ran, when
    /// one ran that this tap could not time (see `confirm_waits`), and when
    /// `tool` itself is unmeasured: a share of a whole nobody measured is
    /// not a share.
    pub confirm_ms: Option<f64>,
    /// How many `action.confirm` questions this tap saw opened for the turn.
    /// Beside `confirm_ms` for the same reason `tool_calls` is beside
    /// `tool_ms`: "you were never asked" and "you were asked and the wait
    /// could not be timed" are different facts.
    pub confirm_waits: usize,
}

/// Every line `jv tap` prints ABOUT a turn fits this many columns.
///
/// Not the frames — those are raw data and are as wide as they are — but
/// every line the tap writes as a REPORT: the `turn` ladder, the per-frame
/// hop line, the hop table, and the latency summary. 80 because it is the
/// floor every terminal has, and because the summary table was already built
/// to it.
///
/// Nothing enforces this at runtime; three tests enforce it at the widest
/// input that can reach each kind of line — `every_line_a_turn_prints_fits
/// _eighty_columns`, `the_summary_table_and_the_hop_table_fit_the_same
/// _eighty_columns`, `the_streamed_hop_line_fits_eighty_columns_whatever_a
/// _publisher_is_called` — and each names the bounds it assumes rather than
/// enforces.
pub const TAP_COLUMNS: usize = 80;

/// The widest an utterance id may print inside one of those lines.
///
/// jv-ears stamps a `uuid.uuid4()` on every utterance, so the live id is 36
/// characters — three of them on one line is the whole of the width problem
/// (`jv_ears/pipeline.py`). Eight characters of a UUID is 4.3e9 and this tap
/// holds a handful of turns at a time, so the prefix identifies the turn for
/// as long as anyone is reading; the `...` says out loud that it is a prefix
/// and not the id, and the frames printed alongside carry the whole thing.
pub const ID_COLUMNS: usize = 11;

/// An utterance id as a turn line carries it: verbatim when it already fits,
/// otherwise its first characters and `...` to say what happened.
///
/// Short ids are never touched, so an id that fits is never made longer by
/// being abbreviated — the same shape `echo_raw` uses for audit lines.
pub fn short_id(id: &str) -> String {
    clip(id, ID_COLUMNS)
}

/// A string as one of these lines carries it: verbatim when it already fits
/// `columns`, otherwise its first characters and `...` to say what happened.
///
/// Counts CHARACTERS, because the budget is columns and not bytes. `columns`
/// must leave room for the marker; every caller here passes a column from a
/// named constant, and the assertion is what would catch a future one that
/// does not.
fn clip(s: &str, columns: usize) -> String {
    debug_assert!(columns >= 4, "{columns} columns cannot hold a clipped string");
    if s.chars().count() <= columns {
        return s.to_string();
    }
    let mut out: String = s.chars().take(columns - 3).collect();
    out.push_str("...");
    out
}

/// A span as every one of these lines prints it. None is `?` and is never a
/// plausible zero.
fn ms(v: Option<f64>) -> String {
    match v {
        Some(v) => format!("{v:.0}ms"),
        None => "?".to_string(),
    }
}

impl Turn {
    /// The user's own speaking time: the segment less the silence ears sat
    /// through at the end of it.
    ///
    /// None when the hold is unknown, and also when it does not FIT — a hold
    /// longer than the segment it is supposed to be part of means the
    /// heartbeat and the utterance are describing different configurations
    /// (ears restarted mid-tap, say). Two numbers that disagree produce no
    /// third number.
    pub fn spoke_ms(&self) -> Option<f64> {
        let (speech, hold) = (self.speech_ms?, self.hold_ms?);
        (speech >= hold).then_some(speech - hold)
    }

    /// The turn's own line: what the user waited, and their two shares of it.
    ///
    /// `total` is `spoke + hold + respond`, and the third term lives on
    /// `respond_line` — the six numbers this line used to carry came to 133
    /// columns on a live utterance id and wrapped, which is worse than the
    /// one number they replaced (B17). See `TAP_COLUMNS`.
    pub fn line(&self, id: &str) -> String {
        format!(
            "turn {}: total={} spoke={} hold={}",
            short_id(id),
            ms(self.total_ms),
            ms(self.spoke_ms()),
            ms(self.hold_ms),
        )
    }

    /// The machine's half, split where jv-ears hands over to jv-brain.
    ///
    /// `X is A + B` for an exact partition, the same grammar
    /// `TurnStats::brain_split` and `confirm_line` use; `X includes Y` when
    /// the parts do not account for the whole.
    pub fn respond_line(&self, id: &str) -> String {
        format!(
            "turn {}: respond={} is hear={} + think={}",
            short_id(id),
            ms(self.respond_ms),
            ms(self.hear_ms),
            ms(self.think_ms),
        )
    }

    /// Every line this turn has to say, in the order `jv tap` prints them.
    ///
    /// The ladder is why this is one method and not four calls at the call
    /// site: each line after the first names a span the line above it gave a
    /// value for, so printing one without the ones over it would leave a
    /// name pointing at nothing.
    pub fn lines(&self, id: &str) -> Vec<String> {
        let mut out = vec![self.line(id), self.respond_line(id)];
        out.extend(self.tool_line(id));
        out.extend(self.confirm_line(id));
        out
    }

    /// Of `tool`: jv-act's OWN work, the confirmation window taken out.
    ///
    /// The half a faster machine could shorten. Its complement, `confirm_ms`,
    /// is 15 s by design and is you — which is the whole reason the two are
    /// worth separating, exactly as `spoke` is separated from `hold` one
    /// level up.
    ///
    /// The subtraction always fits and nothing here has to check that it
    /// does: `confirm_span` refuses a window that is not nested inside its
    /// own call's round trip, so the union of the windows is a subset of the
    /// union of the calls. Pinned by
    /// `a_confirmation_window_outside_its_own_round_trip_is_refused`.
    pub fn ran_ms(&self) -> Option<f64> {
        Some(self.tool_ms? - self.confirm_ms?)
    }

    /// The follow-up line for a turn whose `think` jv-act was inside, or
    /// None when there is nothing to say.
    ///
    /// Its own line rather than a seventh number on `line()`: that line is
    /// already six numbers wide and has to survive a terminal, and this one
    /// describes a minority of turns. Same shape as the `wait`/`model` split
    /// jv-brain's gauge prints, for the same reason.
    pub fn tool_line(&self, id: &str) -> Option<String> {
        let (think, tool) = (self.think_ms?, self.tool_ms?);
        let plural = if self.tool_calls == 1 { "" } else { "s" };
        Some(format!(
            "turn {}: think={think:.0}ms includes tool={tool:.0}ms ({} jv-act call{plural})",
            short_id(id),
            self.tool_calls
        ))
    }

    /// The follow-up line for a turn where jv-act stopped and asked you, or
    /// None when no confirmation was opened or none could be timed.
    ///
    /// Its own line again, under the `tool` line it divides, for the reason
    /// that line is its own: the widths have to survive a terminal, and this
    /// describes a minority of the minority of turns that ran a tool at all.
    pub fn confirm_line(&self, id: &str) -> Option<String> {
        // `think` is required for nothing this line prints, and required
        // anyway: without it there is no `tool_line`, and this line names
        // `tool` without restating its value. A name whose value was never
        // printed is worse than a longer line.
        let _think = self.think_ms?;
        let (you, ran) = (self.confirm_ms?, self.ran_ms()?);
        let plural = if self.confirm_waits == 1 { "" } else { "s" };
        Some(format!(
            "turn {}: tool is you={you:.0}ms + ran={ran:.0}ms ({} confirmation{plural})",
            short_id(id),
            self.confirm_waits
        ))
    }
}

/// How many `intent.action` frames one turn may record before this stops
/// counting.
///
/// jv-brain caps EXECUTIONS at 5 per turn, but its tool loop has no round
/// cap (optimization backlog #5), so a stuck model can publish requests for
/// as long as the turn lasts. `jv tap` is meant to be left running for
/// hours, and a vector that grows with a wedged turn is the one shape it
/// must not have. Past the cap the turn keeps its count and loses its
/// measurement: a number we stopped taking is not a short number.
pub const ACTS_PER_TURN: usize = 32;

/// One `intent.action` and the `action.result` answering it, if it came,
/// plus the `action.confirm` question inside it for a tool that needed one.
struct Act {
    request_id: String,
    sent: f64,
    done: Option<f64>,
    /// `action.confirm` kind=request: the moment jv-act asked YOU. None for
    /// a tool whose capability needs no confirmation, which is most of them.
    asked: Option<f64>,
    /// `action.confirm` kind=answer: the moment the question stopped being
    /// open, by an answer or by the window expiring.
    answered: Option<f64>,
}

/// Where one input utterance's boundaries are collected until its reply
/// arrives.
struct Utt {
    /// `audio.vad` speech_start, or None if the tap started mid-sentence.
    start: Option<f64>,
    /// `audio.vad` speech_end.
    end: Option<f64>,
    /// The final `audio.transcript` — the seam between ASR and the brain.
    heard: Option<f64>,
    /// The tools this turn asked jv-act for, in the order they were asked.
    acts: Vec<Act>,
    /// Set when `acts` hit `ACTS_PER_TURN` and recording stopped.
    acts_overflowed: bool,
    reported: bool,
}

/// Tracks each input utterance's boundaries so the first `speech.say` that
/// answers it can be reported as one decomposed `Turn`.
///
/// Three things this is careful about:
///
/// 1. **Only `audio.vad` defines a boundary.** An `audio.transcript` partial
///    used to be allowed to set the start, because it carries the same
///    `utterance_id` and might arrive first. But a partial is ASR output
///    emitted PART-WAY through the utterance, so using it as the start
///    silently shortened the turn by however much of the sentence had
///    already been said. Boundaries come from the service that decides them.
///    A FINAL transcript is different in kind: it is not a boundary either,
///    it is an ANCHOR INSIDE one turn, marking where jv-ears stopped and
///    jv-brain started. So it annotates an utterance `audio.vad` already
///    bounded and never conjures one — a seam with nothing around it would
///    otherwise print a `>>> turn` line for something no service ever said
///    was a turn.
/// 2. **Report once per utterance.** jv-brain streams a reply sentence by
///    sentence, so one utterance produces several `speech.say` frames. Only
///    the first is time-to-first-word; printing a bigger number for every
///    later sentence reads as latency getting worse and is simply the reply
///    being long.
/// 3. **Bounded.** `jv tap` is meant to be left running for hours, so the
///    map cannot grow one entry per utterance forever.
pub struct Utterances {
    utts: HashMap<String, Utt>,
    order: VecDeque<String>,
    cap: usize,
    /// `request_id` -> `utterance_id`, because `action.result` carries only
    /// the former. Swept when its utterance is evicted: it is the one map
    /// here not keyed by utterance, so nothing else bounds it.
    reqs: HashMap<String, String>,
}

impl Utterances {
    pub fn with_capacity(cap: usize) -> Self {
        Self {
            utts: HashMap::new(),
            order: VecDeque::new(),
            cap: cap.max(1),
            reqs: HashMap::new(),
        }
    }

    /// `audio.vad` `speech_start` for `id`, at envelope `ts`.
    pub fn started(&mut self, id: &str, ts: f64) {
        Self::keep_earliest(&mut self.entry(id).start, ts);
    }

    /// `audio.vad` `speech_end` for `id`, at envelope `ts`.
    pub fn ended(&mut self, id: &str, ts: f64) {
        Self::keep_earliest(&mut self.entry(id).end, ts);
    }

    /// The FINAL `audio.transcript` for `id`, at envelope `ts`: the moment
    /// jv-ears finished transcribing and jv-brain's share of the turn began.
    ///
    /// Unlike the two boundaries this does NOT create an utterance. Only
    /// `audio.vad` says a turn happened; this only divides one that did.
    pub fn heard(&mut self, id: &str, ts: f64) {
        if let Some(u) = self.utts.get_mut(id) {
            Self::keep_earliest(&mut u.heard, ts);
        }
    }

    /// An `intent.action` naming `utterance_id`, at envelope `ts`: jv-brain
    /// asking jv-act for a tool inside this turn.
    ///
    /// Like the ASR seam and unlike the two boundaries, this does NOT create
    /// an utterance — only `audio.vad` says a turn happened, and an action
    /// with no turn around it is jv-act serving something that was never a
    /// voice turn at all (`utterance_id` is optional on the schema for
    /// exactly that reason).
    pub fn acted(&mut self, utterance_id: &str, request_id: &str, ts: f64) {
        // An absent id and an empty one are the same fact — the frame named
        // nobody — and the guard lives HERE rather than only in the caller
        // that unwraps the field, so a reader cannot re-introduce it by
        // defaulting the Option away.
        if utterance_id.is_empty() || request_id.is_empty() {
            return;
        }
        let Some(u) = self.utts.get_mut(utterance_id) else { return };
        if let Some(a) = u.acts.iter_mut().find(|a| a.request_id == request_id) {
            // A re-delivered request is the same moment in the turn, not a
            // second tool call. The EARLIEST ts, like every other anchor
            // here: a request is when jv-brain asked, not when this process
            // got round to the frame.
            a.sent = a.sent.min(ts);
            return;
        }
        if u.acts.len() >= ACTS_PER_TURN {
            u.acts_overflowed = true;
            return;
        }
        u.acts.push(Act {
            request_id: request_id.to_string(),
            sent: ts,
            done: None,
            asked: None,
            answered: None,
        });
        self.reqs.insert(request_id.to_string(), utterance_id.to_string());
    }

    /// The `action.result` for `request_id`, at envelope `ts`.
    ///
    /// Joined through the `intent.action` that named the utterance, because
    /// the result frame names none. A result for a request this tap never
    /// saw belongs to no turn it can name, and is dropped rather than
    /// attached to whichever turn happens to be open.
    pub fn act_done(&mut self, request_id: &str, ts: f64) {
        if let Some(a) = self.act_mut(request_id) {
            Self::keep_earliest(&mut a.done, ts);
        }
    }

    /// The `action.confirm` kind=request for `request_id`, at envelope `ts`:
    /// jv-act stopped and asked the user, and everything until the answer is
    /// the user's time and not the machine's.
    ///
    /// Joined through the `intent.action` that named the utterance, like
    /// `action.result` and for the same reason — `action.confirm` carries a
    /// `request_id` and no `utterance_id`. A question for a request this tap
    /// never saw belongs to no turn it can name.
    pub fn confirm_asked(&mut self, request_id: &str, ts: f64) {
        if let Some(a) = self.act_mut(request_id) {
            Self::keep_earliest(&mut a.asked, ts);
        }
    }

    /// The `action.confirm` kind=answer for `request_id`, at envelope `ts`.
    ///
    /// The EARLIEST, and that matters here more than anywhere else: jv-act
    /// ECHOES the answer it acted on onto the same topic the `jv confirm`
    /// CLI publishes its answer on, so one decision produces two frames.
    /// The user stopped deciding at the first of them.
    pub fn confirm_answered(&mut self, request_id: &str, ts: f64) {
        if let Some(a) = self.act_mut(request_id) {
            Self::keep_earliest(&mut a.answered, ts);
        }
    }

    /// The recorded call for `request_id`, through the utterance the
    /// `intent.action` named. None for a request this tap never saw.
    fn act_mut(&mut self, request_id: &str) -> Option<&mut Act> {
        if request_id.is_empty() {
            return None;
        }
        let utt = self.reqs.get(request_id)?;
        let u = self.utts.get_mut(utt)?;
        u.acts.iter_mut().find(|a| a.request_id == request_id)
    }

    /// How many `request_id`s are still joined to a live utterance. Exists
    /// so a test can assert the sweep, and so the bound is checkable.
    pub fn pending_requests(&self) -> usize {
        self.reqs.len()
    }

    /// The EARLIEST ts seen for a boundary, not the first one delivered: the
    /// frames carrying an `utterance_id` need not arrive in ts order, and a
    /// boundary is a moment in the audio rather than a moment in this
    /// process's inbox.
    fn keep_earliest(slot: &mut Option<f64>, ts: f64) {
        match slot {
            Some(t) if *t <= ts => {}
            _ => *slot = Some(ts),
        }
    }

    fn entry(&mut self, id: &str) -> &mut Utt {
        if !self.utts.contains_key(id) {
            self.utts.insert(
                id.to_string(),
                Utt {
                    start: None,
                    end: None,
                    heard: None,
                    acts: Vec::new(),
                    acts_overflowed: false,
                    reported: false,
                },
            );
            self.order.push_back(id.to_string());
            while self.order.len() > self.cap {
                if let Some(old) = self.order.pop_front() {
                    if let Some(u) = self.utts.remove(&old) {
                        for a in u.acts {
                            self.reqs.remove(&a.request_id);
                        }
                    }
                }
            }
        }
        self.utts.get_mut(id).expect("just inserted")
    }

    /// The turn `id` took, given the ts of the FIRST `speech.say` answering
    /// it and jv-ears' endpoint hold if it has been heard. Only the first
    /// time it is asked for a given utterance. None if we heard no boundary
    /// for it at all, if it was already reported, or if it was evicted.
    pub fn reply(&mut self, id: &str, say_ts: f64, hold_s: Option<f64>) -> Option<Turn> {
        let u = self.utts.get_mut(id)?;
        if u.reported {
            return None;
        }
        u.reported = true;
        // The seam is only a seam while it sits inside the span it divides.
        // A final before its own speech_end, or after the first word that
        // answers it, means two frames disagree about the order the pipeline
        // ran in — and an anchor that is not trusted for one half is not
        // trusted for the other, so both halves go rather than one of them
        // being published as a negative.
        let seam = u
            .heard
            .filter(|h| *h <= say_ts && u.end.map_or(true, |t1| *h >= t1));
        let tool = seam.and_then(|h| Self::tool_span(&u.acts, u.acts_overflowed, h, say_ts));
        Some(Turn {
            total_ms: u.start.map(|t0| (say_ts - t0) * 1e3),
            speech_ms: match (u.start, u.end) {
                (Some(t0), Some(t1)) => Some((t1 - t0) * 1e3),
                _ => None,
            },
            respond_ms: u.end.map(|t1| (say_ts - t1) * 1e3),
            hold_ms: hold_s.map(|h| h * 1e3),
            hear_ms: match (u.end, seam) {
                (Some(t1), Some(h)) => Some((h - t1) * 1e3),
                _ => None,
            },
            think_ms: seam.map(|h| (say_ts - h) * 1e3),
            // `tool` is a share of `think`, so it needs the same seam: a
            // share of a whole nobody measured is not a share, and the
            // summary table indents it under the row it divides.
            tool_ms: tool,
            tool_calls: u.acts.len(),
            // And `confirm` is a share of `tool` by exactly the same rule,
            // one level further down: without a `tool` there is no whole for
            // the user's half to be a half OF.
            confirm_ms: tool.and(Self::confirm_span(&u.acts, u.acts_overflowed)),
            confirm_waits: u.acts.iter().filter(|a| a.asked.is_some()).count(),
        })
    }

    /// The time at least one of `acts` was outstanding, given the `think`
    /// span `[lo, hi]` it must lie inside.
    ///
    /// None — not zero, and not a partial total — when:
    ///
    ///   * **recording stopped** (`overflowed`): we know more tools ran than
    ///     we kept, so any sum is short by an unknown amount;
    ///   * **a request is unanswered**: it ran for a length nobody can state,
    ///     and reporting the answered ones alone would look complete;
    ///   * **a round trip runs backwards**, or falls outside the `think` it
    ///     is supposed to be a share of. Same rule as the ASR seam and as
    ///     jv-brain's own gauge: two frames that disagree about the order
    ///     the pipeline ran in produce no third number.
    ///
    /// Otherwise the UNION of the intervals — overlapping requests are one
    /// moment of jv-act's time, not two.
    fn tool_span(acts: &[Act], overflowed: bool, lo: f64, hi: f64) -> Option<f64> {
        if acts.is_empty() || overflowed {
            return None;
        }
        let mut spans: Vec<(f64, f64)> = Vec::with_capacity(acts.len());
        for a in acts {
            let done = a.done?;
            if !(a.sent <= done && a.sent >= lo && done <= hi) {
                return None;
            }
            spans.push((a.sent, done));
        }
        Some(Self::union_ms(spans))
    }

    /// Of `tool`: the time at least one `action.confirm` question was open —
    /// the part of jv-act's span that was the USER deciding.
    ///
    /// None — not zero — when:
    ///
    ///   * **no question was asked**: most tools are benign and confirm
    ///     nothing, and a window that never opened is not a 0 ms window;
    ///   * **recording stopped** (`overflowed`), for the same reason `tool`
    ///     refuses: we know more calls ran than we kept;
    ///   * **a question is still open**, or its call never came back: it was
    ///     open for a length nobody can state;
    ///   * **the window does not NEST inside its own call's round trip**.
    ///     A question asked before jv-brain requested the tool, or answered
    ///     after jv-act reported it done, means two frames disagree about
    ///     the order the pipeline ran in. That nesting is also what makes
    ///     this a genuine SHARE — it is what guarantees the union of the
    ///     windows cannot exceed the union of the calls, so `ran_ms` needs
    ///     no fit check of its own.
    ///
    /// Otherwise the UNION, like the calls around it: jv-act holds one
    /// confirmation open at a time today, but that is its rule and not this
    /// reader's, and two questions open at once are one moment of your time.
    fn confirm_span(acts: &[Act], overflowed: bool) -> Option<f64> {
        if overflowed {
            return None;
        }
        let mut spans: Vec<(f64, f64)> = Vec::new();
        for a in acts {
            let Some(asked) = a.asked else { continue };
            let (answered, done) = (a.answered?, a.done?);
            if !(a.sent <= asked && asked <= answered && answered <= done) {
                return None;
            }
            spans.push((asked, answered));
        }
        (!spans.is_empty()).then(|| Self::union_ms(spans))
    }

    /// The total length covered by `spans`, in ms, counting overlap once.
    /// Panics on an empty slice; both callers check.
    fn union_ms(mut spans: Vec<(f64, f64)>) -> f64 {
        spans.sort_by(|a, b| a.0.total_cmp(&b.0));
        let mut union = 0.0;
        let (mut open, mut close) = spans[0];
        for (s, e) in &spans[1..] {
            if *s > close {
                union += close - open;
                (open, close) = (*s, *e);
            } else if *e > close {
                close = *e;
            }
        }
        (union + close - open) * 1e3
    }

    pub fn len(&self) -> usize {
        self.utts.len()
    }

    pub fn is_empty(&self) -> bool {
        self.utts.is_empty()
    }
}

/// The measured turns, as four distributions instead of one.
///
/// A span is only in its row when it was actually measured for that turn, so
/// the `n` column says how many turns each number stands on — a `respond`
/// over twelve turns next to a `total` over nine is not a discrepancy, it is
/// three turns whose start this tap did not hear.
///
/// `spoke` and `hold` are pushed together or not at all: they are two halves
/// of one subtraction, and a spoke sample whose hold was refused would be an
/// average over turns measured two different ways.
///
/// `hear` and `think` are two subtractions sharing one anchor, not two halves
/// of one, so each is pushed on its own terms — `hear` needs a `speech_end`
/// and `think` does not, which is why a tap that joined mid-utterance can
/// have more thinks than hears. The `n` column is what says so.
#[derive(Default)]
pub struct TurnStats {
    turns: usize,
    spoke: Vec<f64>,
    hold: Vec<f64>,
    hear: Vec<f64>,
    think: Vec<f64>,
    wait: Vec<f64>,
    model: Vec<f64>,
    tool: Vec<f64>,
    /// Two halves of one subtraction, and unlike `spoke`/`hold` they cannot
    /// come apart: `ran` IS `tool - you`, so it exists exactly when `you`
    /// does. The pair is pushed in one statement to say so, not to enforce
    /// it — the enforcement is `Turn::ran_ms`, which cannot answer without a
    /// `confirm_ms` to subtract.
    you: Vec<f64>,
    ran: Vec<f64>,
    respond: Vec<f64>,
    total: Vec<f64>,
    /// The id and `think` of the most recently reported turn, until
    /// jv-brain's gauge for it lands (`brain_split`) or the next turn
    /// replaces it. At most one turn is ever waiting: jv-brain publishes the
    /// gauge before the next turn's first word can be read, because both
    /// frames leave jv-brain on the same connection.
    awaiting: Option<(String, f64)>,
}

impl TurnStats {
    pub fn push(&mut self, t: &Turn, id: &str) {
        self.turns += 1;
        self.awaiting = t.think_ms.map(|think| (id.to_string(), think));
        if let (Some(spoke), Some(hold)) = (t.spoke_ms(), t.hold_ms) {
            self.spoke.push(spoke);
            self.hold.push(hold);
        }
        if let Some(v) = t.hear_ms {
            self.hear.push(v);
        }
        if let Some(v) = t.think_ms {
            self.think.push(v);
        }
        if let Some(v) = t.tool_ms {
            self.tool.push(v);
        }
        if let (Some(you), Some(ran)) = (t.confirm_ms, t.ran_ms()) {
            self.you.push(you);
            self.ran.push(ran);
        }
        if let Some(v) = t.respond_ms {
            self.respond.push(v);
        }
        if let Some(v) = t.total_ms {
            self.total.push(v);
        }
    }

    /// jv-brain's own gauge for the turn just reported: how much of its
    /// `think` was the LLM. Splits that `think` into `wait` + `model` and
    /// returns the line to print, or None when the number cannot be placed.
    ///
    /// Three refusals:
    ///
    ///   * **No turn is waiting.** The gauge is bound to a turn by frame
    ///     order alone (see `brain_first_say`), so a gauge with nothing in
    ///     front of it describes a turn this tap did not report — one whose
    ///     boundaries it never heard, or one already split. It is dropped
    ///     rather than attached to whatever comes next.
    ///   * **`think` was unmeasured.** There is nothing to divide, and a
    ///     `model` sample with no `wait` beside it would leave two rows
    ///     standing on different turns while looking like two halves.
    ///   * **The gauge does not FIT.** A model span longer than the `think`
    ///     it is inside means jv-brain's clock and the bus timestamps
    ///     disagree about this turn. Two numbers that disagree produce no
    ///     third number — same rule as `spoke_ms`.
    pub fn brain_split(&mut self, model_ms: f64) -> Option<String> {
        let (id, think) = self.awaiting.take()?;
        if !(model_ms >= 0.0 && model_ms <= think) {
            return None;
        }
        let wait = think - model_ms;
        self.model.push(model_ms);
        self.wait.push(wait);
        Some(format!(
            "turn {}: think={think:.0}ms is wait={wait:.0}ms + model={model_ms:.0}ms",
            short_id(&id)
        ))
    }

    pub fn is_empty(&self) -> bool {
        self.turns == 0
    }

    pub fn summary(&self) -> String {
        if self.is_empty() {
            return String::new();
        }
        let plural = if self.turns == 1 { "" } else { "s" };
        let mut out = format!(
            "--- turn latency: {} turn{plural}, split at the boundaries jv-ears publishes\n",
            self.turns
        );
        out.push_str(&format!("{:<10} {:<31} {:>4} {:>9} {:>9} {:>9}\n", "span", "whose time it is", "n", "p50", "p95", "max"));
        let rows: [(&str, &str, &Vec<f64>); 11] = [
            ("spoke", "you, talking", &self.spoke),
            ("hold", "jv-ears' endpoint wait", &self.hold),
            ("hear", "jv-ears' ASR", &self.hear),
            ("think", "jv-brain, to its first word", &self.think),
            ("  wait", "of think: before the model ran", &self.wait),
            ("  model", "of think: the LLM itself", &self.model),
            ("  tool", "of think: jv-act ran the tool", &self.tool),
            ("    you", "of tool: you, deciding", &self.you),
            ("    ran", "of tool: jv-act's own work", &self.ran),
            ("respond", "hear + think: ASR + brain + bus", &self.respond),
            ("total", "speech start -> first word", &self.total),
        ];
        for (span, whose, v) in rows {
            if v.is_empty() {
                continue;
            }
            let mut s = v.clone();
            s.sort_by(f64::total_cmp);
            out.push_str(&format!(
                "{span:<10} {whose:<31} {:>4} {:>7.0}ms {:>7.0}ms {:>7.0}ms\n",
                s.len(),
                percentile(&s, 50.0),
                percentile(&s, 95.0),
                percentile(&s, 100.0),
            ));
        }
        if !self.respond.is_empty() && self.hear.is_empty() && self.think.is_empty() {
            out.push_str(
                "--- hear/think unmeasured: no `audio.transcript` final landed between a turn's\n    speech_end and its first word, so respond stays one span over two services.\n    (jv-ears publishes no final for an utterance its ASR read as empty.)\n",
            );
        }
        if !self.think.is_empty() && self.model.is_empty() {
            out.push_str(&format!(
                "--- think unsplit: no jv-brain heartbeat carried `{BRAIN_FIRST_SAY_METRIC}` for a\n    reported turn, so `think` stays the model plus the bus hops and the queueing\n    around it. (jv-brain states the gauge only for a turn whose first word came\n    straight out of the first completion — a turn that ran tools has tool time\n    inside `think`, and calling that the model would be a lie.)\n"
            ));
        }
        if !self.tool.is_empty() {
            out.push_str(
                "--- tool is `intent.action` -> `action.result`: jv-act running it AND, for a\n    confirming tool, the whole window it waited for your answer in — 15 s by\n    design and never spoken — which is why the `you`/`ran` rows sit under it.\n    It is the UNION of the round trips, so overlapping calls count once and the\n    completions jv-brain runs between serial calls are not in it. A call that\n    never reached jv-act (a name it invented, arguments it could not write, or\n    one past its own per-turn cap) publishes no `intent.action`, and that time\n    stays in the rest of `think`, where it was spent.\n",
            );
        }
        if !self.you.is_empty() {
            out.push_str(
                "--- of a confirming tool's `tool`, `you` is the window jv-act held open waiting\n    for your answer — `action.confirm` request -> answer, both already on the\n    bus — and `ran` is the rest. `you` is the half no faster machine shortens,\n    and a 15 s window inside `tool` is why the undivided number could not be\n    argued about against a budget. Both are refused rather than guessed when a\n    question was still open, so a tool row with no split under it is a turn\n    where nothing was asked or nothing could be timed.\n",
            );
        }
        if self.spoke.is_empty() {
            out.push_str(&format!(
                "--- spoke/hold unmeasured: no jv-ears heartbeat carried `{EARS_HOLD_METRIC}`, and a\n    measurement may not substitute a default for a reading. `total` therefore\n    still contains the user's own speaking time, and no budget applies to it.\n"
            ));
        } else {
            out.push_str(
                "--- the machine's share of a turn is hold+respond; spoke is the user, and no\n    faster machine shortens it.\n",
            );
        }
        out
    }
}

// ---------------------------------------------------------------- line formats

/// One `sys.health` body as a line. Missing fields print as `?` / `-` rather
/// than as a plausible zero: a health readout that invents an "ok" is worse
/// than one that admits it does not know.
pub fn health_line(body: &rmpv::Value) -> String {
    let service = get_str(body, "service").unwrap_or_else(|| "?".into());
    let state = get_str(body, "state").unwrap_or_else(|| "?".into());
    let uptime = match get_f64(body, "uptime_s") {
        Some(u) => format!("up={u:9.1}s"),
        None => format!("up={:>10}", "?"),
    };
    let drops = get(body, "drops").map(to_json).unwrap_or_else(|| "-".into());
    let notes = get_str(body, "notes").unwrap_or_default();
    format!("{service:<12} {state:<9} {uptime} drops={drops} {notes}").trim_end().to_string()
}

/// One jv-act audit entry as a line.
pub fn act_log_line(e: &serde_json::Value) -> String {
    let confirm = e
        .get("confirm")
        .map(|c| {
            format!(
                " confirm={}/{}",
                c["granted"].as_bool().unwrap_or(false),
                c["answered_by"].as_str().unwrap_or("?")
            )
        })
        .unwrap_or_default();
    format!(
        "{} {:<22} {:<11} {:<18} {:>7.0}ms{} args={}",
        e["ts"].as_str().unwrap_or("?"),
        e["tool"].as_str().unwrap_or("?"),
        e["capability"].as_str().unwrap_or("?"),
        e["outcome"].as_str().unwrap_or("?"),
        e["duration_ms"].as_f64().unwrap_or(0.0),
        confirm,
        e["args"]
    )
}

// ---------------------------------------------------------------- health check

/// How long `jv health --check` listens when `--for` does not say. Every
/// service in this repo heartbeats every 5 s, so one nominal period plus a
/// margin hears every RUNNING service at least once, and it is still short
/// enough to type at a terminal and wait for.
pub const HEALTH_CHECK_WINDOW_S: f64 = 6.0;

/// The service that owns the LLM. It is the only one that can see which rung
/// the ladder picked (invariant 6), so the gauges are read from ITS heartbeat
/// by name rather than from whoever published `llm_rung` last.
pub const BRAIN: &str = "jv-brain";

/// How well a service is, in the only words `--check` may print.
///
/// Five come off the wire (`schemas/sys.health.json`). Two are this reader's
/// own: `lost`, a heartbeat that outlived the two periods the schema grants
/// it, and `unknown`, a frame we are not entitled to interpret. Both rank
/// ABOVE `degraded` on purpose — a service that told us it is impaired is in
/// better shape than one we cannot hear, or cannot read.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Wellness {
    Ok,
    Starting,
    Stopping,
    Degraded,
    Unknown,
    Lost,
    Error,
}

impl Wellness {
    /// The frozen enum, and nothing else. A state word this binary does not
    /// know is not passed through as itself: it is a body we cannot read, and
    /// reading it aloud would dress an unknown up as a diagnosis.
    pub fn from_word(word: &str) -> Option<Wellness> {
        match word {
            "starting" => Some(Wellness::Starting),
            "ok" => Some(Wellness::Ok),
            "degraded" => Some(Wellness::Degraded),
            "error" => Some(Wellness::Error),
            "stopping" => Some(Wellness::Stopping),
            _ => None,
        }
    }

    pub fn word(self) -> &'static str {
        match self {
            Wellness::Ok => "ok",
            Wellness::Starting => "starting",
            Wellness::Stopping => "stopping",
            Wellness::Degraded => "degraded",
            Wellness::Unknown => "unknown",
            Wellness::Lost => "lost",
            Wellness::Error => "error",
        }
    }

    /// How loudly a state deserves to be read. `ok` is 0 and is the only
    /// state that is not a finding — which is also what decides the exit
    /// status, so this ranking IS the answer to "is the machine well".
    pub fn rank(self) -> u8 {
        match self {
            Wellness::Error => 5,
            Wellness::Lost => 4,
            Wellness::Unknown => 3,
            Wellness::Degraded => 2,
            Wellness::Starting | Wellness::Stopping => 1,
            Wellness::Ok => 0,
        }
    }
}

/// A heartbeat this reader is willing to believe. Anything rejected at the
/// door becomes `unknown` instead — see `HealthCheck::trust`.
#[derive(Debug, Clone)]
struct Trusted {
    ts: f64,
    period_s: f64,
    state: Wellness,
    notes: String,
    metrics: Option<rmpv::Value>,
}

/// jv-brain's `llm_first_say_ms` as a `--check` window saw it — the number
/// AND when the turn it measures happened.
///
/// The gauge is bound to a TURN, not to the heartbeat carrying it: jv-brain
/// states it once and then re-states the same number on every periodic beat
/// for the rest of the process's life. A reader that printed the number alone
/// would answer "is generation slow right now?" with a measurement that may
/// be an hour old — a brain nobody has spoken to since breakfast reading as
/// one that just took 412 ms. That is a number quietly stopping meaning what
/// its label says, which is the failure this whole CLI is written against.
///
/// What a window CAN establish is the age, and it establishes it from the
/// COUNT (`llm_first_says`), which rises once per measured turn:
///
///   * the count ROSE while we listened — the turn is the frame that raised
///     it, and its age is a measurement;
///   * the count never moved — the turn predates the first brain heartbeat we
///     read, and the only honest statement is a LOWER BOUND.
///
/// So the first count seen is recorded and never treated as fresh, which is
/// the same rule the tap loop follows (`brain_first_say`) for the same
/// reason: it may describe a turn from before this process connected.
///
/// One thing the age does NOT say: a turn that ran tools publishes no gauge
/// at all (jv-brain's `TurnTiming`), so "the last measured turn" can be older
/// than the last turn. That is why the field is `turn_age` and not `idle`.
#[derive(Debug, Clone)]
struct SayGauge {
    ms: f64,
    count: u64,
    /// `ts` of the first heartbeat this window read the gauge off.
    first_ts: f64,
    /// `ts` of the heartbeat that RAISED the count, once one has.
    raised_ts: Option<f64>,
}

impl SayGauge {
    fn seen(ts: f64, count: u64, ms: f64) -> Self {
        SayGauge { ms, count, first_ts: ts, raised_ts: None }
    }

    /// Fold a later reading in. A count that went BACKWARDS is jv-brain
    /// restarted — the counter begins at 1 again — so the window starts over
    /// on it rather than reading a smaller number as a newer turn.
    fn update(&mut self, ts: f64, count: u64, ms: f64) {
        if count < self.count {
            *self = SayGauge::seen(ts, count, ms);
            return;
        }
        if count > self.count {
            self.raised_ts = Some(ts);
        }
        self.count = count;
        self.ms = ms;
    }

    /// `first_say=412ms turn_age=1.5s` when the window watched the turn
    /// happen, `turn_age>=6.0s` when it did not. The `>=` is the whole point:
    /// it is the difference between a reading and a bound, and the reader
    /// deciding whether the number describes right now needs to see which
    /// one this is.
    fn phrase(&self, now: f64) -> String {
        match self.raised_ts {
            Some(ts) => format!("first_say={:.0}ms turn_age={:.1}s", self.ms, now - ts),
            None => format!("first_say={:.0}ms turn_age>={:.1}s", self.ms, now - self.first_ts),
        }
    }
}

/// One service's answer at the moment the window closed.
#[derive(Debug, Clone, PartialEq)]
pub struct Wellbeing {
    pub service: String,
    pub state: Wellness,
    /// The heartbeat's own `notes`, empty when it said none — and always
    /// empty for a `lost` service, whose notes described a moment that has
    /// passed.
    pub notes: String,
    /// Seconds between the heartbeat and the close of the window, or None
    /// when the frame carried no readable `ts`.
    pub age_s: Option<f64>,
}

/// The `sys.health` stream, collapsed into "is this machine well right now".
///
/// Three rules hold it to the truth, the same three the HUD's `HealthState`
/// is built on (`shell/jv-hud/core/HealthState.qml`) — they are properties of
/// the topic, not of either reader:
///
///   * **The roster is who has spoken.** Nothing on the bus says which
///     services are SUPPOSED to be running, so a service that never started
///     is absent from this report, not failed. Absence claims nothing; that
///     is the honest shape of not knowing, and the footer says how long we
///     listened so the reader can weigh it.
///   * **A heartbeat expires.** The schema says missing two consecutive
///     periods is presumed dead, so a frame speaks for two of its own periods
///     and no longer. Nothing publishes "jv-brain died".
///   * **Unreadable is not fine.** A body from a schema version this binary
///     was not written against, a hedged `conf`, a body naming a service
///     other than the one that published it, a state word outside the frozen
///     enum: all `unknown`, all reported, all non-zero exit. The failure that
///     matters is the quiet one — a clean report over a broken machine.
#[derive(Default)]
pub struct HealthCheck {
    latest: HashMap<String, Option<Trusted>>,
    /// Per service, the first-say gauge across the whole window rather than
    /// off the latest frame alone — the only way to date the turn it
    /// measures. In practice only jv-brain ever fills this in.
    says: HashMap<String, SayGauge>,
}

impl HealthCheck {
    /// Take one `sys.health` frame. Keyed by the envelope's `src`, because
    /// that is who the broker saw publish it; the body's own `service` is a
    /// claim, and a claim that disagrees is exactly what `trust` refuses.
    ///
    /// The LAST frame from a service wins, including when the last one is
    /// unreadable: "the newest thing this service said cannot be read" is a
    /// finding, not a reason to keep quoting an older frame that can.
    pub fn observe(&mut self, frame: &rmpv::Value) {
        let Some(src) = get_str(frame, "src").filter(|s| !s.is_empty()) else {
            // The broker refuses an envelope with no `src`, so this is
            // unreachable from a real bus — and a frame we cannot attribute
            // must not be attributed to a service we invent a name for.
            return;
        };
        let trusted = Self::trust(frame, &src);
        if let Some(t) = &trusted {
            match first_say(frame, &src) {
                Some((count, ms)) => {
                    self.says
                        .entry(src.clone())
                        .and_modify(|g| g.update(t.ts, count, ms))
                        .or_insert_with(|| SayGauge::seen(t.ts, count, ms));
                }
                // A readable heartbeat that carries no gauge is the newest
                // thing this service said, and it says nothing about a turn.
                // Keeping the older reading alive would be this reader
                // quoting a frame that has been superseded — the same rule
                // the report follows when the newest frame is unreadable.
                None => {
                    self.says.remove(&src);
                }
            }
        }
        self.latest.insert(src, trusted);
    }

    /// The frame, or None if it is not one this binary may read.
    fn trust(frame: &rmpv::Value, src: &str) -> Option<Trusted> {
        if get(frame, "v").and_then(|v| v.as_u64()) != Some(1) {
            return None;
        }
        if get_f64(frame, "conf") != Some(1.0) {
            return None;
        }
        let ts = get_f64(frame, "ts")?;
        let body = get(frame, "body").filter(|b| b.is_map())?;
        if get_str(body, "service").as_deref() != Some(src) {
            return None;
        }
        let period_s = get_f64(body, "period_s").filter(|p| *p > 0.0)?;
        let state = Wellness::from_word(&get_str(body, "state")?)?;
        Some(Trusted {
            ts,
            period_s,
            state,
            notes: get_str(body, "notes").unwrap_or_default(),
            metrics: get(body, "metrics").filter(|m| m.is_map()).cloned(),
        })
    }

    /// Has this heartbeat outlived the two periods the schema grants it?
    fn lost(t: &Trusted, now: f64) -> bool {
        now - t.ts > t.period_s * 2.0
    }

    /// Everyone heard from, worst first, ties broken by name so two equally
    /// bad findings do not reshuffle between runs.
    pub fn report(&self, now: f64) -> Vec<Wellbeing> {
        let mut out: Vec<Wellbeing> = self
            .latest
            .iter()
            .map(|(service, heard)| match heard {
                None => Wellbeing {
                    service: service.clone(),
                    state: Wellness::Unknown,
                    notes: String::new(),
                    age_s: None,
                },
                Some(t) if Self::lost(t, now) => Wellbeing {
                    service: service.clone(),
                    state: Wellness::Lost,
                    notes: String::new(),
                    age_s: Some(now - t.ts),
                },
                Some(t) => Wellbeing {
                    service: service.clone(),
                    state: t.state,
                    notes: t.notes.clone(),
                    age_s: Some(now - t.ts),
                },
            })
            .collect();
        out.sort_by(|a, b| b.state.rank().cmp(&a.state.rank()).then(a.service.cmp(&b.service)));
        out
    }

    /// What the brain has said about its own generation: which rung of the
    /// VRAM ladder it is on, and how long its last divisible turn took to
    /// the first word. None when it has said neither.
    ///
    /// Never rendered as "gpu" on a guess — a rung we cannot read is not a
    /// rung we may reassure anyone about — and never rendered at all off a
    /// heartbeat that has outlived the two periods the schema grants it: a
    /// gauge that outlived its own heartbeat is the stalest reading there
    /// is. `SayGauge` carries the rest of the care the timing half needs.
    pub fn llm_line(&self, now: f64, brain: &str) -> Option<String> {
        let t = self.latest.get(brain)?.as_ref()?;
        if Self::lost(t, now) {
            return None;
        }
        let metrics = t.metrics.as_ref()?;
        let rung = get_f64(metrics, "llm_rung");
        let backend = get_f64(metrics, "llm_gpu").map(|g| if g == 1.0 { "gpu" } else { "cpu" });
        let say = self.says.get(brain).map(|g| g.phrase(now));
        if rung.is_none() && backend.is_none() && say.is_none() {
            return None;
        }
        let rung = rung.map(|r| format!("{r:.0}")).unwrap_or_else(|| "?".into());
        let mut line = format!("llm rung={rung} backend={}", backend.unwrap_or("?"));
        if let Some(say) = say {
            line.push(' ');
            line.push_str(&say);
        }
        Some(line)
    }
}

/// One service's wellbeing as a line. A missing age prints as `?`, never as a
/// plausible zero.
pub fn wellbeing_line(w: &Wellbeing) -> String {
    let age = match w.age_s {
        Some(a) => format!("age={a:7.1}s"),
        None => format!("age={:>8}", "?"),
    };
    format!("{:<12} {:<9} {age} {}", w.service, w.state.word(), w.notes).trim_end().to_string()
}

/// The closing line: how many services spoke, over how long, and how many of
/// them are not well. It states the window because the window is the only
/// thing that makes "heard from 4 services" mean anything.
pub fn health_check_footer(report: &[Wellbeing], window_s: f64) -> String {
    if report.is_empty() {
        return format!("heard from no service in {window_s:.1}s");
    }
    let unwell = report.iter().filter(|w| w.state.rank() > 0).count();
    let plural = if report.len() == 1 { "" } else { "s" };
    let verdict = if unwell == 0 {
        "all well".to_string()
    } else {
        format!("{unwell} not well")
    };
    format!("heard from {} service{plural} in {window_s:.1}s; {verdict}", report.len())
}

/// Exit status for `jv health --check`, following the rule `jv act-log`
/// already set: the status IS the answer. 0 only when at least one service
/// spoke and every one of them is `ok` — silence is not an all-clear, so a
/// bus nobody heartbeats on fails, loudly, instead of reading as a calm
/// machine.
pub fn health_check_exit(report: &[Wellbeing]) -> i32 {
    if report.is_empty() || report.iter().any(|w| w.state.rank() > 0) {
        1
    } else {
        0
    }
}

// ---------------------------------------------------------------- act-log

/// How long a raw byte-for-byte echo of an unreadable audit line may be. Long
/// enough to recognise the entry, short enough that one junk line (or a file
/// that is not an audit log at all) cannot flood a terminal.
const RAW_ECHO_CHARS: usize = 100;

/// Where the jv-act audit log lives: `$JARVIS_ACT_AUDIT`, else the platform
/// default.
///
/// This MUST stay in step with jv-act's own `default_audit_path()`
/// (`services/jv-act/src/audit.rs`), which computes the same two paths. jv-act
/// is human-review-only under the Ralph guardrails, so the duplication cannot
/// be deleted here — see proposal **R2** in `docs/optimization-backlog.md` for
/// the one-line change that would make jv-act call this.
pub fn act_audit_path() -> std::path::PathBuf {
    act_audit_path_from(std::env::var("JARVIS_ACT_AUDIT").ok().as_deref())
}

/// `act_audit_path` with the environment injected, so the policy is testable.
/// A blank `JARVIS_ACT_AUDIT` is an UNSET one: an empty or whitespace value is
/// almost always a shell expansion that came out empty, and reading the file
/// named "" would report "no audit log at " — which reads as "jv-act has never
/// acted", the most misleading thing this command could say.
pub fn act_audit_path_from(env: Option<&str>) -> std::path::PathBuf {
    if let Some(p) = env.filter(|p| !p.trim().is_empty()) {
        return p.into();
    }
    if cfg!(unix) {
        "/var/lib/jarvis/act/audit.jsonl".into()
    } else {
        // Windows dev: repo-local state dir (gitignored).
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join(".state")
            .join("act-audit.jsonl")
    }
}

/// What `--failed` / `--outcome` asks of an entry's `outcome` word.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OutcomeFilter {
    /// `--failed`: anything jv-act did not record as `ok`.
    NotOk,
    /// `--outcome X [--outcome Y]`: exactly one of these words.
    ///
    /// The words are NOT validated against jv-act's enum. Doing so would be a
    /// second hand-copy of a human-review-only file (see `act_audit_path`),
    /// and an old `jv` would then refuse an outcome a newer jv-act had learnt
    /// to write — refusing to show a record because you do not recognise it is
    /// the wrong failure for an audit reader. A typo is caught by the other
    /// end instead: a filter that matches nothing exits 1.
    AnyOf(Vec<String>),
}

/// The question `jv act-log` was asked.
#[derive(Debug, Default, Clone)]
pub struct ActLogFilter {
    /// `--tail N`: the newest N of whatever answers the question.
    pub tail: Option<usize>,
    /// `--since`: epoch seconds; entries stamped before this are not shown.
    pub since: Option<f64>,
    /// `--failed` / `--outcome`.
    pub outcome: Option<OutcomeFilter>,
}

impl ActLogFilter {
    /// The whole log, in order — what `jv act-log` has always printed.
    pub fn all() -> Self {
        Self::default()
    }

    /// Was a QUESTION asked, as opposed to a window onto the answer?
    ///
    /// `--tail` is a window: it says how much to show, not what to look for,
    /// so `--tail 0` on a healthy log is not a failed search and must keep
    /// exiting 0 the way it always has.
    pub fn is_query(&self) -> bool {
        self.since.is_some() || self.outcome.is_some()
    }
}

/// Does one parsed entry answer the question?
///
/// **A filter narrows what is shown; it never hides what it could not
/// evaluate.** An entry with no readable `ts` cannot be proven older than the
/// cutoff, and one with no readable `outcome` cannot be proven to have
/// succeeded — so both are shown, with `?` in the column the filter was about,
/// which is the admission a human can see. The alternative is a filtered view
/// of the audit trail that is quietly missing exactly the entries something
/// went wrong with, which is the same lie `act_log_render` already refuses to
/// tell about a torn line.
fn entry_matches(e: &serde_json::Value, f: &ActLogFilter) -> bool {
    if let Some(cutoff) = f.since {
        if let Some(t) = e.get("ts").and_then(|v| v.as_str()).and_then(iso_to_epoch) {
            if t < cutoff {
                return false;
            }
        }
    }
    if let Some(want) = &f.outcome {
        if let Some(word) = e.get("outcome").and_then(|v| v.as_str()) {
            let hit = match want {
                OutcomeFilter::NotOk => word != "ok",
                OutcomeFilter::AnyOf(words) => words.iter().any(|w| w == word),
            };
            if !hit {
                return false;
            }
        }
    }
    true
}

/// A rendered `jv act-log` view: the lines to print, oldest last-written last.
pub struct ActLog {
    pub lines: Vec<String>,
    /// Lines in the rendered range that could not be read as audit entries.
    pub unreadable: usize,
    /// Entries that were readable AND answered the question, counted BEFORE
    /// `--tail` narrows the view: "did anything match" is about the filter,
    /// not about how many of the matches were asked for.
    pub matched: usize,
    /// Whether a question was asked at all (`ActLogFilter::is_query`).
    pub queried: bool,
}

/// Render an audit file for `jv act-log` — newest last, narrowed by `filter`.
///
/// **A line that will not parse is rendered, not skipped.** This is the record
/// of the one service allowed to change the machine, so a hole in it is news:
/// a reader that quietly drops what it cannot read shows a torn log as a clean
/// one, and the entry most likely to be torn is the last one written — the
/// action that was running when something went wrong. The marker carries the
/// file's own line number and a bounded echo of the raw bytes, and
/// `act_log_exit_code` makes the hole visible to a script too. An unreadable
/// line survives every filter for the same reason (see `entry_matches`).
///
/// Filters run BEFORE `--tail`, so `--failed --tail 1` is "the newest failure"
/// and not "the last line, if it happens to be a failure" — the second reading
/// makes `--tail` silently answer a different question than the one asked.
///
/// Blank lines are not entries and are not holes; they are skipped in silence.
pub fn act_log_render(text: &str, filter: &ActLogFilter) -> ActLog {
    // (line, is_unreadable), in file order, for everything the filter kept.
    let mut kept: Vec<(String, bool)> = Vec::new();
    let mut matched = 0usize;
    for (i, raw) in text.lines().enumerate() {
        if raw.trim().is_empty() {
            continue;
        }
        // An object is the only thing `act_log_line` can honestly render: fed a
        // JSON string or array it prints a plausible row of "?" that looks like
        // a real action with missing fields.
        match serde_json::from_str::<serde_json::Value>(raw) {
            Ok(e) if e.is_object() => {
                if !entry_matches(&e, filter) {
                    continue;
                }
                matched += 1;
                kept.push((act_log_line(&e), false));
            }
            _ => kept.push((format!("!! unreadable audit line {}: {}", i + 1, echo_raw(raw)), true)),
        }
    }
    let start = filter.tail.map(|n| kept.len().saturating_sub(n)).unwrap_or(0);
    let shown = &kept[start..];
    ActLog {
        lines: shown.iter().map(|(l, _)| l.clone()).collect(),
        unreadable: shown.iter().filter(|(_, bad)| *bad).count(),
        matched,
        queried: filter.is_query(),
    }
}

/// A bounded, char-boundary-safe echo of a raw line. A torn write can cut
/// mid-UTF-8, and slicing bytes there would panic and take the reader with it.
fn echo_raw(raw: &str) -> String {
    let mut s: String = raw.chars().take(RAW_ECHO_CHARS).collect();
    if s.chars().count() < raw.chars().count() {
        s.push_str("...");
    }
    s
}

/// Process exit status for `jv act-log`.
///
/// Two ways to fail, and both are about a caller being able to trust the
/// answer:
///
/// 1. **A line in the rendered range could not be read.** `jv act-log --tail 1
///    && ...` should not proceed on the strength of a line nobody could parse.
/// 2. **A question was asked and nothing answered it** — grep's rule. It is
///    what makes `jv act-log --failed || echo all clean` mean something, and
///    it is the only thing standing between a typo'd `--outcome denyed` and a
///    reassuring empty listing. `--tail` alone is not a question (see
///    `ActLogFilter::is_query`), so the old behaviour is unchanged.
///
/// Nothing is printed for an empty match, exactly as grep prints nothing: on a
/// healthy machine `--failed` matching nothing is the GOOD answer, and a
/// warning on stderr every time would train a human to ignore this command.
pub fn act_log_exit_code(log: &ActLog) -> i32 {
    if log.unreadable > 0 || (log.queried && log.matched == 0) {
        1
    } else {
        0
    }
}

// ---------------------------------------------------------------- act-log time

/// Wall-clock now, epoch seconds. Injected into `parse_since` rather than read
/// inside it, so the policy is testable without a clock.
pub fn now_epoch() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// `--since` as an absolute epoch second: either a duration back from `now`
/// (`10m`, `2h`, `90s`, `3d`, `1.5h`) or an absolute UTC timestamp
/// (`2026-09-24`, `2026-09-24T10:00:00Z`).
///
/// **Wall clock, not `ts_mono`.** Audit entries carry both, and `ts_mono` is
/// the better clock in every way except the one that matters here: "what
/// happened in the last ten minutes" is a question about the clock on the
/// wall, `ts_mono` restarts at every boot, and no human can type one.
///
/// An unreadable `--since` is an ERROR, never "since the beginning of time".
/// The failure mode this avoids is the bad one: a filter that silently widens
/// prints the whole log and looks like a lot of recent activity.
pub fn parse_since(s: &str, now: f64) -> Result<f64, String> {
    let t = s.trim();
    if let Some(secs) = parse_duration(t) {
        return Ok(now - secs);
    }
    if let Some(epoch) = iso_to_epoch(t) {
        return Ok(epoch);
    }
    Err(format!(
        "--since wants a duration back from now (10m, 2h, 90s, 3d) \
         or a UTC timestamp (2026-09-24, 2026-09-24T10:00:00Z), got '{s}'"
    ))
}

/// `<number><s|m|h|d>` as seconds. No sign and no exponent: `--since -10m` is
/// nonsense, and `1e3d` is a typo pretending to be a number.
fn parse_duration(s: &str) -> Option<f64> {
    let unit = s.chars().last()?;
    let mult = match unit {
        's' => 1.0,
        'm' => 60.0,
        'h' => 3600.0,
        'd' => 86_400.0,
        _ => return None,
    };
    let num = &s[..s.len() - unit.len_utf8()];
    if !plain_number(num) {
        return None;
    }
    Some(num.parse::<f64>().ok()? * mult)
}

/// ASCII digits with at most one decimal point, and at least one digit.
/// `str::parse::<f64>` also accepts `inf`, `+5` and `1e9`; none of those are
/// things a human means here, and all of them would read as a number.
fn plain_number(s: &str) -> bool {
    !s.is_empty()
        && s.chars().any(|c| c.is_ascii_digit())
        && s.chars().all(|c| c.is_ascii_digit() || c == '.')
        && s.matches('.').count() <= 1
}

/// `YYYY-MM-DD`, optionally `THH:MM[:SS[.fff]]`, optionally `Z`, as epoch
/// seconds. The inverse of the stamp jv-act writes (`audit::now_iso`).
///
/// Deliberately strict: anything else is `None`, which every caller reads as
/// "cannot tell" rather than as a date. In particular an offset (`+03:00`) is
/// REFUSED, not ignored — ignoring one shifts an entry by hours and then
/// answers the wrong question with complete confidence. jv-act writes UTC and
/// only UTC, so a stamp with an offset did not come from jv-act.
pub fn iso_to_epoch(s: &str) -> Option<f64> {
    let s = s.strip_suffix('Z').unwrap_or(s);
    let (date, time) = match s.split_once('T') {
        Some((d, t)) => (d, Some(t)),
        None => (s, None),
    };

    let mut parts = date.split('-');
    let (ys, mos, ds) = (parts.next()?, parts.next()?, parts.next()?);
    if parts.next().is_some() {
        return None;
    }
    // A 4-digit year, so `26-09-24` is refused rather than read as year 26.
    if ys.len() != 4 || !ys.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    let y: i64 = ys.parse().ok()?;
    let mo = small_int(mos)?;
    let d = small_int(ds)?;
    if !(1..=12).contains(&mo) || !(1..=31).contains(&d) {
        return None;
    }

    let (h, mi, sec) = match time {
        None => (0, 0, 0.0),
        Some(t) => {
            let mut tp = t.split(':');
            let h = small_int(tp.next()?)?;
            let mi = small_int(tp.next()?)?;
            let sec = match tp.next() {
                None => 0.0,
                Some(secs) => {
                    if !plain_number(secs) || secs.split('.').next()?.len() > 2 {
                        return None;
                    }
                    secs.parse::<f64>().ok()?
                }
            };
            if tp.next().is_some() {
                return None;
            }
            (h, mi, sec)
        }
    };
    // Upper bounds only: `small_int` and `plain_number` refuse a sign, so
    // nothing here can arrive negative and a `0 <=` check would be a branch no
    // input can reach. 60 is a leap second, which a stamp may carry and this
    // arithmetic need not treat specially.
    if h > 23 || mi > 59 || sec >= 61.0 {
        return None;
    }

    // days-from-civil (Howard Hinnant), the exact inverse of the
    // civil-from-days in jv-act's `now_iso`.
    let y = if mo <= 2 { y - 1 } else { y };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let mp = if mo > 2 { mo - 3 } else { mo + 9 };
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146_097 + doe - 719_468;

    Some(days as f64 * 86_400.0 + (h * 3600 + mi * 60) as f64 + sec)
}

/// One or two ASCII digits as an integer — the widths a date field has.
fn small_int(s: &str) -> Option<i64> {
    if s.is_empty() || s.len() > 2 || !s.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    s.parse().ok()
}

#[cfg(test)]
mod tests {

    use super::*;

    // ------------------------------------------------------------ act-log

    /// An `ActLogFilter` that only narrows the view.
    fn tail(n: usize) -> ActLogFilter {
        ActLogFilter { tail: Some(n), ..ActLogFilter::all() }
    }

    /// One audit line stamped and judged, in the shape jv-act writes it.
    fn entry_at(tool: &str, ts: &str, outcome: &str) -> String {
        serde_json::json!({
            "ts": ts, "ts_mono": 1.0, "request_id": "r1",
            "tool": tool, "args": {}, "capability": "observe",
            "outcome": outcome, "duration_ms": 1.0
        })
        .to_string()
    }

    fn entry(tool: &str) -> String {
        serde_json::json!({
            "ts": "2026-09-24T10:00:00Z", "ts_mono": 1.0, "request_id": "r1",
            "tool": tool, "args": {}, "capability": "observe",
            "outcome": "ok", "duration_ms": 1.0
        })
        .to_string()
    }

    #[test]
    fn act_log_renders_oldest_first_one_line_per_entry() {
        let text = format!("{}\n{}\n{}\n", entry("a.one"), entry("a.two"), entry("a.three"));
        let r = act_log_render(&text, &ActLogFilter::all());
        assert_eq!(r.unreadable, 0);
        assert_eq!(r.lines.len(), 3);
        assert!(r.lines[0].contains("a.one"), "{:?}", r.lines);
        assert!(r.lines[2].contains("a.three"), "newest last: {:?}", r.lines);
    }

    #[test]
    fn act_log_tail_takes_the_newest_n_and_tolerates_a_big_n() {
        let text = format!("{}\n{}\n{}\n", entry("a.one"), entry("a.two"), entry("a.three"));
        let r = act_log_render(&text, &tail(2));
        assert_eq!(r.lines.len(), 2);
        assert!(r.lines[0].contains("a.two"), "{:?}", r.lines);
        assert!(r.lines[1].contains("a.three"), "{:?}", r.lines);
        // More than there are is the whole log, not an error and not a panic.
        assert_eq!(act_log_render(&text, &tail(99)).lines.len(), 3);
        // Zero is zero — a caller that asks for nothing gets nothing.
        assert!(act_log_render(&text, &tail(0)).lines.is_empty());
    }

    #[test]
    fn act_log_of_an_empty_file_is_empty_and_clean() {
        for text in ["", "\n", "   \n\n"] {
            let r = act_log_render(text, &ActLogFilter::all());
            assert!(r.lines.is_empty(), "{text:?} -> {:?}", r.lines);
            assert_eq!(r.unreadable, 0, "blank lines are whitespace, not a lost entry");
        }
    }

    /// The audit trail is the record of the only service allowed to change the
    /// machine. A line we cannot read is a HOLE in that record, and a reader
    /// that skips it silently reports a torn log as a clean one.
    #[test]
    fn act_log_shows_a_line_it_cannot_read_instead_of_dropping_it() {
        let text = format!("{}\n{{\"tool\":\"a.torn\"\n{}\n", entry("a.one"), entry("a.two"));
        let r = act_log_render(&text, &ActLogFilter::all());
        assert_eq!(r.unreadable, 1);
        assert_eq!(r.lines.len(), 3, "the unreadable line still occupies its place: {:?}", r.lines);
        assert!(r.lines[1].starts_with("!! unreadable audit line 2"), "{:?}", r.lines[1]);
        assert!(r.lines[1].contains("a.torn"), "show the raw bytes: {:?}", r.lines[1]);
        assert_eq!(act_log_exit_code(&r), 1, "a torn log must be scriptable as a failure");
        
    }

    #[test]
    fn act_log_treats_valid_json_that_is_not_an_entry_as_unreadable() {
        // `act_log_line` would happily render this as "? ? ?" — a plausible
        // looking row invented out of a JSON string is worse than an admission.
        let r = act_log_render("\"just a string\"\n[1,2,3]\n42\n", &ActLogFilter::all());
        assert_eq!(r.unreadable, 3, "{:?}", r.lines);
        assert!(r.lines.iter().all(|l| l.starts_with("!! unreadable")), "{:?}", r.lines);
    }

    #[test]
    fn act_log_line_numbers_are_the_files_own_even_under_tail() {
        let text = format!("{}\nnot json\n{}\n", entry("a.one"), entry("a.two"));
        let r = act_log_render(&text, &tail(2));
        assert_eq!(r.lines.len(), 2);
        assert!(r.lines[0].contains("line 2"), "tail must not renumber: {:?}", r.lines[0]);
        assert_eq!(r.unreadable, 1, "only the lines shown are counted: {:?}", r.lines);
    }

    #[test]
    fn act_log_marker_is_bounded_so_one_junk_line_cannot_flood_a_terminal() {
        let text = format!("{}\n", "x".repeat(10_000));
        let r = act_log_render(&text, &ActLogFilter::all());
        assert_eq!(r.lines.len(), 1);
        assert!(r.lines[0].len() < 200, "marker was {} chars", r.lines[0].len());
        assert!(r.lines[0].ends_with("..."), "{:?}", r.lines[0]);
    }

    #[test]
    fn act_log_marker_never_splits_a_character() {
        // A torn write can cut mid-UTF-8; slicing bytes would panic and take
        // the whole reader with it. The odd leading byte puts the byte-index
        // cut INSIDE a two-byte char, which is what makes this bite.
        let text = format!("x{}\n", "é".repeat(300));
        let r = act_log_render(&text, &ActLogFilter::all());
        assert_eq!(r.lines.len(), 1);
        assert!(r.lines[0].contains('é'));
        // Exactly RAW_ECHO_CHARS characters of payload, counted in chars and
        // not in bytes.
        let echo = r.lines[0].rsplit(": ").next().unwrap();
        assert_eq!(echo.chars().count(), RAW_ECHO_CHARS + 3, "{echo:?}");
    }

    #[test]
    fn audit_path_prefers_the_env_var_and_ignores_an_empty_one() {
        assert_eq!(act_audit_path_from(Some("/tmp/x.jsonl")), std::path::PathBuf::from("/tmp/x.jsonl"));
        // An empty JARVIS_ACT_AUDIT is an unset one, not the file "".
        assert_eq!(act_audit_path_from(Some("")), act_audit_path_from(None));
        assert_eq!(act_audit_path_from(Some("  ")), act_audit_path_from(None));
        let d = act_audit_path_from(None);
        assert!(d.is_absolute(), "{d:?}");
        assert!(d.to_string_lossy().ends_with(".jsonl"), "{d:?}");
    }


    // -------------------------------------------------- act-log: the questions

    /// A three-entry day: an old success, a recent denial, a recent success.
    fn a_day() -> String {
        format!(
            "{}\n{}\n{}\n",
            entry_at("a.old", "2026-09-24T09:00:00Z", "ok"),
            entry_at("a.denied", "2026-09-24T11:30:00Z", "denied"),
            entry_at("a.new", "2026-09-24T11:45:00Z", "ok"),
        )
    }

    fn tools(r: &ActLog) -> Vec<String> {
        r.lines.iter().map(|l| l.split_whitespace().nth(1).unwrap_or("?").to_string()).collect()
    }

    #[test]
    fn since_keeps_entries_at_or_after_the_cutoff() {
        let f = ActLogFilter { since: Some(iso_to_epoch("2026-09-24T11:00:00Z").unwrap()), ..ActLogFilter::all() };
        let r = act_log_render(&a_day(), &f);
        assert_eq!(tools(&r), vec!["a.denied", "a.new"], "{:?}", r.lines);
        assert_eq!(r.matched, 2);
        assert_eq!(act_log_exit_code(&r), 0);

        // The boundary is inclusive: an entry stamped exactly at the cutoff is
        // in the window the caller asked about. jv-act stamps to the second,
        // so ties are common, and dropping one loses the entry a human is
        // most likely to be looking for ("since the moment X happened").
        let exact = ActLogFilter { since: Some(iso_to_epoch("2026-09-24T11:30:00Z").unwrap()), ..ActLogFilter::all() };
        assert_eq!(tools(&act_log_render(&a_day(), &exact)), vec!["a.denied", "a.new"]);
    }

    #[test]
    fn failed_is_everything_jv_act_did_not_record_as_ok() {
        let text = format!(
            "{}\n{}\n{}\n{}\n",
            entry_at("a.ok", "2026-09-24T10:00:00Z", "ok"),
            entry_at("a.denied", "2026-09-24T10:01:00Z", "denied"),
            entry_at("a.timeout", "2026-09-24T10:02:00Z", "confirm_timeout"),
            entry_at("a.boom", "2026-09-24T10:03:00Z", "execution_failed"),
        );
        let f = ActLogFilter { outcome: Some(OutcomeFilter::NotOk), ..ActLogFilter::all() };
        let r = act_log_render(&text, &f);
        assert_eq!(tools(&r), vec!["a.denied", "a.timeout", "a.boom"], "{:?}", r.lines);
        assert_eq!(r.matched, 3);
    }

    #[test]
    fn outcome_matches_any_of_the_words_asked_for_and_nothing_near_them() {
        let text = format!(
            "{}\n{}\n{}\n",
            entry_at("a.ok", "2026-09-24T10:00:00Z", "ok"),
            entry_at("a.denied", "2026-09-24T10:01:00Z", "denied"),
            entry_at("a.timeout", "2026-09-24T10:02:00Z", "timeout"),
        );
        let f = ActLogFilter {
            outcome: Some(OutcomeFilter::AnyOf(vec!["denied".into(), "timeout".into()])),
            ..ActLogFilter::all()
        };
        assert_eq!(tools(&act_log_render(&text, &f)), vec!["a.denied", "a.timeout"]);

        // Exact words only — `confirm_timeout` and `timeout` are different
        // outcomes and a substring match would conflate them.
        let one = ActLogFilter { outcome: Some(OutcomeFilter::AnyOf(vec!["timeout".into()])), ..ActLogFilter::all() };
        let text2 = format!("{}\n", entry_at("a.ct", "2026-09-24T10:00:00Z", "confirm_timeout"));
        assert!(act_log_render(&text2, &one).lines.is_empty());
    }

    #[test]
    fn filters_compose() {
        let f = ActLogFilter {
            since: Some(iso_to_epoch("2026-09-24T11:00:00Z").unwrap()),
            outcome: Some(OutcomeFilter::NotOk),
            ..ActLogFilter::all()
        };
        assert_eq!(tools(&act_log_render(&a_day(), &f)), vec!["a.denied"]);
    }

    /// The rule, stated once and tested every way it can be reached: a filter
    /// narrows what is shown, and never hides what it could not evaluate. A
    /// filtered view of the audit trail that is quietly missing exactly the
    /// damaged entries is the lie this command exists not to tell.
    #[test]
    fn a_filter_never_hides_what_it_could_not_evaluate() {
        let since = ActLogFilter { since: Some(iso_to_epoch("2026-09-24T11:00:00Z").unwrap()), ..ActLogFilter::all() };
        let failed = ActLogFilter { outcome: Some(OutcomeFilter::NotOk), ..ActLogFilter::all() };
        let named = ActLogFilter { outcome: Some(OutcomeFilter::AnyOf(vec!["denied".into()])), ..ActLogFilter::all() };

        // A line that will not parse at all: no ts, no outcome, no opinion.
        let torn = "{\"ts\":\"2026-09-24T09:00:00Z\",\"tool\":\"a.tr\n";
        for f in [&since, &failed, &named] {
            let r = act_log_render(torn, f);
            assert_eq!(r.lines.len(), 1, "a torn line survives every filter: {:?}", r.lines);
            assert_eq!(r.unreadable, 1);
            assert_eq!(r.matched, 0, "it is shown, but it is not an answer");
            assert_eq!(act_log_exit_code(&r), 1);
        }

        // A readable entry whose ts is missing or nonsense cannot be proven
        // older than the cutoff. It prints with `?` where its stamp would be.
        for ts in ["", "yesterday", "2026-13-45T99:99:99Z"] {
            let mut e: serde_json::Value = serde_json::from_str(&entry_at("a.undated", ts, "ok")).unwrap();
            if ts.is_empty() {
                e.as_object_mut().unwrap().remove("ts");
            }
            let r = act_log_render(&format!("{e}\n"), &since);
            assert_eq!(tools(&r), vec!["a.undated"], "ts {ts:?} is unreadable, not old");
            assert_eq!(r.matched, 1);
        }

        // Likewise an entry with no readable outcome has not been shown to
        // have succeeded, so `--failed` and `--outcome` both keep it.
        let mut e: serde_json::Value = serde_json::from_str(&entry_at("a.judgeless", "2026-09-24T12:00:00Z", "ok")).unwrap();
        e.as_object_mut().unwrap().insert("outcome".into(), serde_json::json!(7));
        for f in [&failed, &named] {
            let r = act_log_render(&format!("{e}\n"), f);
            assert_eq!(tools(&r), vec!["a.judgeless"], "an unreadable outcome is not an 'ok'");
            assert!(r.lines[0].contains('?'), "and it says so: {:?}", r.lines[0]);
        }
    }

    /// `--failed --tail 1` is "the newest failure", not "the last line of the
    /// file, if it happens to be a failure". The second reading makes `--tail`
    /// silently answer a different question than the one asked.
    #[test]
    fn tail_is_a_window_on_the_answer_not_on_the_file() {
        let text = format!(
            "{}\n{}\n{}\n",
            entry_at("a.denied", "2026-09-24T10:00:00Z", "denied"),
            entry_at("a.boom", "2026-09-24T10:01:00Z", "execution_failed"),
            entry_at("a.ok", "2026-09-24T10:02:00Z", "ok"),
        );
        let f = ActLogFilter { tail: Some(1), outcome: Some(OutcomeFilter::NotOk), ..ActLogFilter::all() };
        let r = act_log_render(&text, &f);
        assert_eq!(tools(&r), vec!["a.boom"], "{:?}", r.lines);
        // Counted before the window narrowed it: "did anything match" is about
        // the filter, not about how many of the matches were asked for.
        assert_eq!(r.matched, 2);
        assert_eq!(act_log_exit_code(&r), 0);
    }

    /// grep's rule. It is what makes `jv act-log --failed || echo all clean`
    /// mean something, and the only thing standing between a typo'd
    /// `--outcome denyed` and a reassuring empty listing.
    #[test]
    fn a_question_nothing_answers_is_a_failure_but_an_empty_log_is_not() {
        let clean = format!("{}\n", entry_at("a.ok", "2026-09-24T10:00:00Z", "ok"));
        let failed = ActLogFilter { outcome: Some(OutcomeFilter::NotOk), ..ActLogFilter::all() };
        let r = act_log_render(&clean, &failed);
        assert!(r.lines.is_empty());
        assert_eq!(r.matched, 0);
        assert!(r.queried);
        assert_eq!(act_log_exit_code(&r), 1, "nothing answered the question");

        // A typo asks a question nothing can answer, and gets the same 1.
        let typo = ActLogFilter { outcome: Some(OutcomeFilter::AnyOf(vec!["denyed".into()])), ..ActLogFilter::all() };
        assert_eq!(act_log_exit_code(&act_log_render(&clean, &typo)), 1);

        // But `--tail` is a window, not a question: it says how much to show,
        // not what to look for, so the old exit-0 behaviour is untouched.
        for f in [ActLogFilter::all(), tail(0), tail(99)] {
            assert!(!f.is_query(), "{f:?}");
            assert_eq!(act_log_exit_code(&act_log_render(&clean, &f)), 0, "{f:?}");
            assert_eq!(act_log_exit_code(&act_log_render("", &f)), 0, "an empty log is history, not a failed search");
        }
    }

    // -------------------------------------------------- act-log: --since parsing

    #[test]
    fn since_reads_a_duration_back_from_now() {
        let now = 1_000_000.0;
        assert_eq!(parse_since("90s", now), Ok(now - 90.0));
        assert_eq!(parse_since("10m", now), Ok(now - 600.0));
        assert_eq!(parse_since("2h", now), Ok(now - 7200.0));
        assert_eq!(parse_since("3d", now), Ok(now - 259_200.0));
        assert_eq!(parse_since("1.5h", now), Ok(now - 5400.0));
        assert_eq!(parse_since("  10m  ", now), Ok(now - 600.0), "a shell quoting artefact is not a syntax error");
    }

    #[test]
    fn since_reads_an_absolute_utc_timestamp() {
        assert_eq!(parse_since("2026-09-24T10:00:00Z", 0.0), Ok(1_790_244_000.0));
        // A bare date is midnight UTC — the natural reading of "--since 2026-09-24".
        assert_eq!(parse_since("2026-09-24", 0.0), Ok(1_790_208_000.0));
    }

    /// An unreadable `--since` must be an ERROR, never "since the beginning of
    /// time": a filter that silently widens prints the whole log and reads as
    /// a great deal of recent activity.
    #[test]
    fn since_refuses_what_it_cannot_read_rather_than_meaning_everything() {
        for bad in [
            "",
            "   ",
            "10",                    // no unit: minutes? seconds? say so.
            "m",                     // no number
            "10x",                   // not a unit we have
            "1e3s",                  // f64 would take this; a human would not write it
            "infs",
            "yesterday",
            "2026-09-24T10:00:00+03:00", // an offset we refuse rather than ignore
            "26-09-24",              // two-digit year is not year 26
            "2026-13-01",
            "2026-09-32",
            "2026-09-24T24:00:00Z",
            "2026-09-24T10:61:00Z",
            "2026/09/24",
            "2026-09-24T10:00:00:00Z",
            "2026-09-24-01",
            "2026-09-24T10:00:000Z", // three-digit seconds are not a stamp
            "2026-09-24T10:00:61Z",  // one past the leap second we do allow
        ] {
            let e = parse_since(bad, 1000.0);
            assert!(e.is_err(), "{bad:?} parsed as {e:?}");
            assert!(e.unwrap_err().contains(bad.trim()), "the error must quote what was typed: {bad:?}");
        }
    }

    /// The exact inverse of the stamp jv-act writes (`audit::now_iso`), which
    /// cannot be imported here: jv-act is human-review-only and depends on
    /// this crate, so the arithmetic is pinned against known epochs instead.
    #[test]
    fn iso_to_epoch_inverts_the_stamp_jv_act_writes() {
        assert_eq!(iso_to_epoch("1970-01-01T00:00:00Z"), Some(0.0));
        assert_eq!(iso_to_epoch("1970-01-02T00:00:00Z"), Some(86_400.0));
        assert_eq!(iso_to_epoch("2000-01-01T00:00:00Z"), Some(946_684_800.0));
        assert_eq!(iso_to_epoch("2026-09-24T10:00:00Z"), Some(1_790_244_000.0));
        // Leap day, and the end of a short February the year after.
        assert_eq!(iso_to_epoch("2024-02-29T12:00:00Z"), Some(1_709_208_000.0));
        assert_eq!(iso_to_epoch("2026-02-28T23:59:59Z"), Some(1_772_323_199.0));
        // Pre-epoch dates go negative rather than wrapping.
        assert_eq!(iso_to_epoch("1969-12-31T23:59:59Z"), Some(-1.0));
        // Sub-second precision jv-act does not write today, and a trailing Z
        // that is optional either way.
        assert_eq!(iso_to_epoch("2000-01-01T00:00:00.500Z"), Some(946_684_800.5));
        assert_eq!(iso_to_epoch("2000-01-01T00:00:00"), Some(946_684_800.0));
        assert_eq!(iso_to_epoch("2000-01-01T00:01"), Some(946_684_860.0), "seconds are optional");
        // A leap second is a stamp, not a bug.
        assert_eq!(iso_to_epoch("2016-12-31T23:59:60Z"), Some(1_483_228_800.0));
    }

    fn map(pairs: &[(&str, rmpv::Value)]) -> rmpv::Value {
        rmpv::Value::Map(pairs.iter().map(|(k, v)| ((*k).into(), v.clone())).collect())
    }

    #[test]
    fn get_f64_reads_every_msgpack_number_width() {
        let m = map(&[
            ("i", rmpv::Value::from(3)),
            ("f32", rmpv::Value::F32(1.5)),
            ("f64", rmpv::Value::F64(2.25)),
            ("s", rmpv::Value::from("nope")),
        ]);
        assert_eq!(get_f64(&m, "i"), Some(3.0));
        assert_eq!(get_f64(&m, "f32"), Some(1.5));
        assert_eq!(get_f64(&m, "f64"), Some(2.25));
        assert_eq!(get_f64(&m, "s"), None);
        assert_eq!(get_f64(&m, "absent"), None);
        assert_eq!(get_f64(&rmpv::Value::Nil, "i"), None);
    }

    #[test]
    fn percentile_is_nearest_rank() {
        let s: Vec<f64> = (1..=10).map(|i| i as f64).collect();
        assert_eq!(percentile(&s, 0.0), 1.0);
        assert_eq!(percentile(&s, 50.0), 5.0);
        assert_eq!(percentile(&s, 95.0), 10.0);
        assert_eq!(percentile(&s, 100.0), 10.0);
        assert_eq!(percentile(&[7.0], 50.0), 7.0);
        assert!(percentile(&[], 50.0).is_nan());
    }

    #[test]
    fn unmet_count_is_a_failure_every_way_it_can_end() {
        for outcome in [Outcome::Count, Outcome::Deadline, Outcome::Interrupted, Outcome::BusClosed] {
            assert_eq!(exit_code(outcome, Some(3), 2), 1, "{outcome:?} with 2 of 3");
            assert_eq!(exit_code(outcome, Some(3), 3), 0, "{outcome:?} with 3 of 3");
            // No --count: the caller never said how many, so any stop is fine.
            assert_eq!(exit_code(outcome, None, 0), 0, "{outcome:?} open-ended");
        }
    }

    #[test]
    fn hop_summary_is_worst_p95_first_and_stable() {
        let mut s = HopStats::default();
        for ms in [0.1, 0.2, 0.3] {
            s.hop("sys.health", ms);
        }
        s.hop("audio.vad", 9.0);
        s.hop("audio.vad", 11.0);
        let out = s.summary();
        let vad = out.find("audio.vad").expect("audio.vad row");
        let health = out.find("sys.health").expect("sys.health row");
        assert!(vad < health, "worst p95 first:\n{out}");
        assert!(out.contains("5 frames, 2 topics"), "{out}");
        // Nearest-rank p50 of [9,11] is 9; max is 11.
        assert!(out.contains("9.00ms"), "{out}");
        assert!(out.contains("11.00ms"), "{out}");
        // Hops only. Turns are a different measurement with a different
        // shape, and they have their own table (`TurnStats`).
        assert!(!out.contains("turn"), "{out}");
    }

    #[test]
    fn hop_summary_of_nothing_is_nothing() {
        assert!(HopStats::default().is_empty());
        assert_eq!(HopStats::default().summary(), "");
    }

    /// Milliseconds derived from float seconds land a few ulps off a round
    /// number; a latency test is not about the 13th decimal place.
    fn about(got: Option<f64>, want: f64) {
        match got {
            Some(v) => assert!((v - want).abs() < 1e-6, "got {v}, want {want}"),
            None => panic!("nothing measured, want {want}"),
        }
    }

    #[test]
    fn a_turn_is_split_at_the_boundaries_jv_ears_publishes() {
        let mut u = Utterances::with_capacity(8);
        u.started("utt-1", 10.0);
        u.ended("utt-1", 13.0); // ears waited out its hold and called it done
        let t = u.reply("utt-1", 14.2, Some(1.5)).expect("a reported turn");
        about(t.total_ms, 4200.0);
        about(t.speech_ms, 3000.0);
        about(t.respond_ms, 1200.0);
        about(t.hold_ms, 1500.0);
        // The user talked for the segment minus the silence ears sat through.
        about(t.spoke_ms(), 1500.0);
    }

    #[test]
    fn respond_splits_into_hear_and_think_at_the_final_transcript() {
        let mut u = Utterances::with_capacity(8);
        u.started("utt-1", 10.0);
        u.ended("utt-1", 13.0);
        // jv-ears runs whisper AFTER it publishes speech_end, then publishes
        // the final. That frame is the seam between the two services inside
        // `respond`, and it is already on the bus.
        u.heard("utt-1", 14.0);
        let t = u.reply("utt-1", 14.2, Some(1.5)).expect("a reported turn");
        about(t.respond_ms, 1200.0);
        about(t.hear_ms, 1000.0);
        about(t.think_ms, 200.0);
        // The split is a partition of respond, not an extra span beside it.
        about(Some(t.hear_ms.unwrap() + t.think_ms.unwrap()), t.respond_ms.unwrap());
    }

    #[test]
    fn without_a_final_transcript_respond_stays_one_span() {
        let mut u = Utterances::with_capacity(8);
        u.started("utt-1", 10.0);
        u.ended("utt-1", 13.0);
        // jv-ears publishes NO final for an utterance whisper read as empty
        // (`_emit_transcript` returns early on empty text), and a tap can
        // simply have missed the frame. Either way the seam is unknown.
        let t = u.reply("utt-1", 14.2, Some(1.5)).expect("a reported turn");
        about(t.respond_ms, 1200.0);
        assert_eq!(t.hear_ms, None);
        assert_eq!(t.think_ms, None);
        let line = t.respond_line("utt-1");
        assert!(line.contains("hear=?"), "{line}");
        assert!(line.contains("think=?"), "{line}");
    }

    #[test]
    fn a_seam_outside_the_span_it_is_supposed_to_divide_is_refused() {
        // A final that lands BEFORE the speech_end it should follow: the two
        // frames disagree about the order the pipeline ran in, and an anchor
        // that is not inside `respond` cannot divide it. Neither half is
        // published rather than one of them being negative.
        let mut u = Utterances::with_capacity(8);
        u.started("early", 10.0);
        u.ended("early", 13.0);
        u.heard("early", 12.5);
        let t = u.reply("early", 14.2, None).expect("a reported turn");
        about(t.respond_ms, 1200.0);
        assert_eq!(t.hear_ms, None, "a negative ASR span is not a measurement");
        assert_eq!(t.think_ms, None, "the anchor that produced it is not trusted either");

        // And a final that lands AFTER the first word answering it.
        let mut u = Utterances::with_capacity(8);
        u.started("late", 10.0);
        u.ended("late", 13.0);
        u.heard("late", 14.5);
        let t = u.reply("late", 14.2, None).expect("a reported turn");
        assert_eq!(t.hear_ms, None);
        assert_eq!(t.think_ms, None);
    }

    #[test]
    fn a_tap_that_missed_speech_end_can_still_time_the_brain() {
        let mut u = Utterances::with_capacity(8);
        u.started("utt-1", 10.0);
        // No speech_end heard, so nothing knows where ASR began...
        u.heard("utt-1", 14.0);
        let t = u.reply("utt-1", 14.2, None).expect("a reported turn");
        assert_eq!(t.respond_ms, None);
        assert_eq!(t.hear_ms, None);
        // ...but the seam to the first word is two frames this tap did hear.
        about(t.think_ms, 200.0);
    }

    #[test]
    fn a_final_transcript_is_an_anchor_inside_a_turn_and_never_a_turn() {
        let mut u = Utterances::with_capacity(8);
        // Only `audio.vad` says an utterance happened. A final transcript
        // with no boundaries around it is one span and no turn, and
        // reporting it would put a line under a `>>> turn` that nothing
        // bounded -- the same mistake the partial-as-a-start bug made.
        u.heard("utt-1", 14.0);
        assert!(u.is_empty(), "a transcript must not conjure an utterance");
        assert!(u.reply("utt-1", 14.2, None).is_none());
    }

    #[test]
    fn the_seam_keeps_the_earliest_ts_like_every_other_anchor() {
        // The schema promises exactly one final per utterance_id; if two ever
        // arrive, the anchor is a moment in the audio, not a moment in this
        // process's inbox. BOTH arrival orders, because "keep whichever came
        // last" gives the same answer as "keep the earliest" for one of them
        // and this test is about telling those two rules apart.
        for pair in [[14.0, 13.5], [13.5, 14.0]] {
            let mut u = Utterances::with_capacity(8);
            u.started("utt-1", 10.0);
            u.ended("utt-1", 13.0);
            u.heard("utt-1", pair[0]);
            u.heard("utt-1", pair[1]);
            let t = u.reply("utt-1", 14.2, None).expect("a reported turn");
            about(t.hear_ms, 500.0);
            about(t.think_ms, 700.0);
        }
    }

    #[test]
    fn without_ears_own_budget_the_spoken_part_is_unknown_not_zero() {
        let mut u = Utterances::with_capacity(8);
        u.started("utt-1", 10.0);
        u.ended("utt-1", 13.0);
        let t = u.reply("utt-1", 14.2, None).expect("a reported turn");
        // What was measured is still measured; what was not is not invented.
        about(t.total_ms, 4200.0);
        about(t.respond_ms, 1200.0);
        assert_eq!(t.hold_ms, None);
        assert_eq!(t.spoke_ms(), None);
        assert!(t.line("utt-1").contains("spoke=?"), "{}", t.line("utt-1"));
        assert!(t.line("utt-1").contains("hold=?"), "{}", t.line("utt-1"));
    }

    #[test]
    fn a_hold_longer_than_the_speech_it_sat_through_is_refused() {
        let mut u = Utterances::with_capacity(8);
        u.started("utt-1", 10.0);
        u.ended("utt-1", 10.9); // 0.9 s of segment
        let t = u.reply("utt-1", 11.5, Some(1.5)).expect("a reported turn");
        // A 1.5 s hold cannot fit inside a 0.9 s segment: the heartbeat and
        // the utterance disagree, so neither derived number is published.
        assert_eq!(t.spoke_ms(), None);
        about(t.speech_ms, 900.0);
    }

    #[test]
    fn an_utterance_whose_start_was_missed_still_reports_what_it_can() {
        let mut u = Utterances::with_capacity(8);
        // `jv tap` started mid-sentence: the speech_start was never seen.
        u.ended("utt-1", 13.0);
        let t = u.reply("utt-1", 14.2, Some(1.5)).expect("respond is knowable");
        about(t.respond_ms, 1200.0);
        assert_eq!(t.total_ms, None, "nothing may stand in for a start we never heard");
        assert_eq!(t.speech_ms, None);
        assert_eq!(t.spoke_ms(), None);
    }

    #[test]
    fn a_partial_transcript_is_not_a_speech_start() {
        let mut u = Utterances::with_capacity(8);
        // Only `audio.vad` says when speech began. A partial transcript at
        // 10.5 used to define the start; it is ASR output, not a boundary.
        let t = u.reply("utt-1", 12.0, None);
        assert!(t.is_none(), "an utterance nothing bounded has no turn to report");
    }

    #[test]
    fn boundaries_keep_the_earliest_ts_not_the_first_frame() {
        let mut u = Utterances::with_capacity(8);
        u.started("utt-1", 10.5);
        u.started("utt-1", 10.0);
        u.ended("utt-1", 13.5);
        u.ended("utt-1", 13.0);
        let t = u.reply("utt-1", 14.0, None).expect("a reported turn");
        about(t.total_ms, 4000.0);
        about(t.speech_ms, 3000.0);
    }

    #[test]
    fn a_turn_is_reported_once_however_many_sentences_it_takes() {
        let mut u = Utterances::with_capacity(8);
        u.started("utt-1", 100.0);
        u.ended("utt-1", 101.0);
        // A streamed reply is several speech.say frames for ONE utterance.
        about(u.reply("utt-1", 102.0, None).and_then(|t| t.total_ms), 2000.0);
        assert!(u.reply("utt-1", 103.0, None).is_none());
        assert!(u.reply("utt-1", 106.0, None).is_none());
        // An utterance we never heard at all has no turn to report.
        assert!(u.reply("never-seen", 106.0, None).is_none());
    }

    #[test]
    fn utterances_are_bounded_and_evict_oldest_first() {
        let mut u = Utterances::with_capacity(3);
        for i in 0..10 {
            u.started(&format!("utt-{i}"), i as f64);
        }
        assert_eq!(u.len(), 3, "a tap left running for hours must not grow");
        assert!(u.reply("utt-0", 100.0, None).is_none(), "oldest evicted");
        about(u.reply("utt-9", 100.0, None).and_then(|t| t.total_ms), (100.0 - 9.0) * 1e3);
    }

    #[test]
    fn utterances_capacity_zero_still_holds_one() {
        let mut u = Utterances::with_capacity(0);
        u.started("utt-1", 1.0);
        about(u.reply("utt-1", 2.0, None).and_then(|t| t.total_ms), 1000.0);
    }

    /// Build a turn the way `Utterances` would, for the summary tests.
    fn turn(start: f64, end: f64, say: f64, hold_s: Option<f64>) -> Turn {
        let mut u = Utterances::with_capacity(4);
        u.started("t", start);
        u.ended("t", end);
        u.reply("t", say, hold_s).expect("a turn")
    }


    /// Build a turn that ran tools, the way `Utterances` would.
    ///
    /// `acts` are `(request_id, sent, done)` — the `intent.action` ts and the
    /// `action.result` ts answering it. `done: None` is a request still
    /// outstanding when the first word arrived.
    fn turn_with_tools(
        start: f64,
        end: f64,
        heard: f64,
        say: f64,
        acts: &[(&str, f64, Option<f64>)],
    ) -> Turn {
        let mut u = Utterances::with_capacity(4);
        u.started("t", start);
        u.ended("t", end);
        u.heard("t", heard);
        for (rid, sent, done) in acts {
            u.acted("t", rid, *sent);
            if let Some(d) = done {
                u.act_done(rid, *d);
            }
        }
        u.reply("t", say, None).expect("a turn")
    }

    #[test]
    fn a_tool_turns_think_is_divided_by_the_round_trip_to_jv_act() {
        // `think` is the transcript -> the first word, and for a tool turn
        // it holds two completions with jv-act's work between them. Both
        // ends of that work are already on the bus: jv-brain publishes
        // `intent.action` and jv-act answers `action.result`.
        let t = turn_with_tools(10.0, 13.0, 14.0, 20.0, &[("r1", 15.0, Some(18.0))]);
        about(t.think_ms, 6000.0);
        about(t.tool_ms, 3000.0);
        assert_eq!(t.tool_calls, 1);
        // The span is INSIDE think, which is what lets it be read as a share.
        assert!(t.tool_ms.unwrap() <= t.think_ms.unwrap());
    }

    #[test]
    fn a_turn_that_ran_no_tool_has_no_tool_span_rather_than_a_zero() {
        let t = turn_with_seam(10.0, 13.0, 14.0, 14.2, Some(1.5));
        assert_eq!(t.tool_ms, None, "a span that did not happen is not 0 ms");
        assert_eq!(t.tool_calls, 0);
        assert_eq!(t.tool_line("t"), None);
    }

    #[test]
    fn two_tool_calls_are_the_time_jv_act_held_and_not_the_gap_between_them() {
        // jv-brain runs tool calls serially and thinks between them, so the
        // bracket from the first request to the last result would charge
        // jv-act for a completion it never saw.
        let t = turn_with_tools(
            10.0,
            13.0,
            14.0,
            30.0,
            &[("r1", 15.0, Some(17.0)), ("r2", 25.0, Some(26.0))],
        );
        about(t.think_ms, 16000.0);
        about(t.tool_ms, 3000.0);
        assert_eq!(t.tool_calls, 2);
    }

    #[test]
    fn overlapping_tool_calls_are_counted_once() {
        // The union, not the sum: two requests outstanding at the same
        // moment are one moment of jv-act's time, and summing them could
        // produce a `tool` larger than the `think` containing it.
        let t = turn_with_tools(
            10.0,
            13.0,
            14.0,
            30.0,
            &[("r1", 15.0, Some(20.0)), ("r2", 16.0, Some(22.0))],
        );
        about(t.tool_ms, 7000.0);
        assert_eq!(t.tool_calls, 2);
    }

    #[test]
    fn a_request_seen_twice_is_one_tool_call_at_its_earliest_ts() {
        for pair in [[15.0, 15.5], [15.5, 15.0]] {
            let t = turn_with_tools(
                10.0,
                13.0,
                14.0,
                20.0,
                &[("r1", pair[0], None), ("r1", pair[1], Some(18.0))],
            );
            assert_eq!(t.tool_calls, 1, "one request_id is one call");
            about(t.tool_ms, 3000.0);
        }
    }

    #[test]
    fn a_request_still_outstanding_when_the_reply_landed_is_refused() {
        // A tool whose result this tap never saw ran for an unknown length,
        // and reporting only the answered calls would understate jv-act's
        // share while looking like a complete measurement.
        let t = turn_with_tools(
            10.0,
            13.0,
            14.0,
            30.0,
            &[("r1", 15.0, Some(17.0)), ("r2", 25.0, None)],
        );
        assert_eq!(t.tool_ms, None);
        assert_eq!(t.tool_calls, 2, "we still know two tools ran");
        assert_eq!(t.tool_line("t"), None);
    }

    #[test]
    fn a_tool_span_outside_the_think_it_divides_is_refused() {
        // Same rule as the ASR seam and as jv-brain's own gauge: a sub-span
        // that does not fit inside the span it is a share of means two
        // clocks disagree, and two numbers that disagree produce no third.
        let before = turn_with_tools(10.0, 13.0, 14.0, 20.0, &[("r1", 13.5, Some(18.0))]);
        assert_eq!(before.tool_ms, None, "jv-act cannot have run before ears finished");
        let after = turn_with_tools(10.0, 13.0, 14.0, 20.0, &[("r1", 15.0, Some(20.5))]);
        assert_eq!(after.tool_ms, None, "nor after the first word answering it");
        // And a result that precedes its own request.
        let backwards = turn_with_tools(10.0, 13.0, 14.0, 20.0, &[("r1", 18.0, Some(15.0))]);
        assert_eq!(backwards.tool_ms, None);
    }

    #[test]
    fn a_tool_turn_whose_seam_is_unknown_has_nothing_to_divide() {
        // No final transcript, so `think` was never measured. The round trip
        // is still two frames this tap saw, but a share of an unknown whole
        // is not a share, and the table indents `tool` under `think`.
        let mut u = Utterances::with_capacity(4);
        u.started("t", 10.0);
        u.ended("t", 13.0);
        u.acted("t", "r1", 15.0);
        u.act_done("r1", 18.0);
        let t = u.reply("t", 20.0, None).expect("a turn");
        assert_eq!(t.think_ms, None);
        assert_eq!(t.tool_ms, None);
    }

    #[test]
    fn an_action_that_names_no_utterance_belongs_to_no_turn() {
        // `utterance_id` is optional on `intent.action` — a tool jv-act ran
        // for the CLI has no voice turn behind it. And like the ASR seam, an
        // action never CONJURES an utterance: only `audio.vad` says a turn
        // happened.
        let mut u = Utterances::with_capacity(4);
        u.acted("never-bounded", "r1", 15.0);
        u.act_done("r1", 18.0);
        assert!(u.is_empty(), "an action must not conjure an utterance");
        assert!(u.reply("never-bounded", 20.0, None).is_none());
    }

    #[test]
    fn a_frame_that_named_nobody_is_refused_even_where_a_turn_answers_to_it() {
        // An `intent.action` with no `utterance_id` belongs to no turn. The
        // caller reads the field as an Option and a missing one never gets
        // here — but a field PRESENT and empty does, and "" must not become
        // a key that an equally empty `audio.vad` could have created.
        let mut u = Utterances::with_capacity(4);
        u.started("", 10.0);
        u.ended("", 13.0);
        u.heard("", 14.0);
        u.acted("", "r1", 15.0);
        u.act_done("r1", 18.0);
        let t = u.reply("", 20.0, None).expect("a turn");
        assert_eq!(t.tool_calls, 0, "an action naming nobody named nobody");
        assert_eq!(t.tool_ms, None);

        // And the same for a request nothing can be threaded through.
        let mut u = Utterances::with_capacity(4);
        u.started("t", 10.0);
        u.ended("t", 13.0);
        u.heard("t", 14.0);
        u.acted("t", "", 15.0);
        assert_eq!(u.pending_requests(), 0);
        assert_eq!(u.reply("t", 20.0, None).expect("a turn").tool_calls, 0);
    }

    #[test]
    fn a_result_for_a_request_this_tap_never_saw_is_dropped() {
        // `action.result` carries only `request_id`, so the join runs
        // through the `intent.action` that named the utterance. A tap that
        // started mid-turn sees the result and not the request, and must not
        // attach it to whatever turn is open.
        let t = turn_with_tools(10.0, 13.0, 14.0, 20.0, &[]);
        assert_eq!(t.tool_calls, 0);
        let mut u = Utterances::with_capacity(4);
        u.started("t", 10.0);
        u.ended("t", 13.0);
        u.heard("t", 14.0);
        u.act_done("orphan", 18.0);
        let t = u.reply("t", 20.0, None).expect("a turn");
        assert_eq!(t.tool_calls, 0);
        assert_eq!(t.tool_ms, None);
    }

    #[test]
    fn the_tool_line_names_the_share_and_who_spent_it() {
        let t = turn_with_tools(10.0, 13.0, 14.0, 20.0, &[("r1", 15.0, Some(18.0))]);
        let line = t.tool_line("utt-7").expect("a tool line");
        assert!(line.contains("turn utt-7:"), "{line}");
        assert!(line.contains("think=6000ms"), "{line}");
        assert!(line.contains("tool=3000ms"), "{line}");
        assert!(line.contains("(1 jv-act call)"), "{line}");
        // Neither of the two lines over it grew a number.
        assert!(!t.line("utt-7").contains("tool="), "{}", t.line("utt-7"));
        assert!(!t.respond_line("utt-7").contains("tool="), "{}", t.respond_line("utt-7"));

        let two = turn_with_tools(10.0, 13.0, 14.0, 30.0, &[("r1", 15.0, Some(17.0)), ("r2", 25.0, Some(26.0))]);
        assert!(two.tool_line("utt-7").expect("a tool line").contains("(2 jv-act calls)"));
    }

    #[test]
    fn a_turn_that_never_stops_calling_tools_stops_being_measured() {
        // The runaway tool loop is a real, filed failure mode (optimization
        // backlog #5), and a tap left running for hours cannot grow a vector
        // per stuck turn. Past the cap we stop recording, and a measurement
        // we stopped taking is refused rather than reported short.
        let mut u = Utterances::with_capacity(4);
        u.started("t", 10.0);
        u.ended("t", 13.0);
        u.heard("t", 14.0);
        for i in 0..(ACTS_PER_TURN + 5) {
            let rid = format!("r{i}");
            u.acted("t", &rid, 15.0 + i as f64 * 1e-3);
            u.act_done(&rid, 15.0 + i as f64 * 1e-3 + 1e-4);
        }
        let t = u.reply("t", 20.0, None).expect("a turn");
        assert_eq!(t.tool_calls, ACTS_PER_TURN, "counting stopped at the cap");
        assert_eq!(t.tool_ms, None, "and a count that stopped measures nothing");
    }

    #[test]
    fn a_requests_join_dies_with_the_utterance_it_belonged_to() {
        // The request_id -> utterance map is the one structure here that is
        // not keyed by utterance, so it has to be swept when an utterance is
        // evicted or `jv tap` grows one entry per tool call, forever.
        let mut u = Utterances::with_capacity(2);
        for i in 0..6 {
            let utt = format!("utt-{i}");
            u.started(&utt, i as f64);
            u.acted(&utt, &format!("r{i}"), i as f64 + 0.1);
        }
        assert_eq!(u.len(), 2);
        assert_eq!(u.pending_requests(), 2, "evicted turns take their requests with them");
    }

    /// Build a turn that ran ONE confirming tool, the way `Utterances` would.
    ///
    /// `sent`/`done` bracket the `intent.action` -> `action.result` round
    /// trip; `window` is the `action.confirm` request -> answer pair inside
    /// it, or None for a tool that needed no confirmation.
    fn turn_with_confirm(
        say: f64,
        sent: f64,
        done: Option<f64>,
        window: Option<(f64, Option<f64>)>,
    ) -> Turn {
        let mut u = Utterances::with_capacity(4);
        u.started("t", 10.0);
        u.ended("t", 13.0);
        u.heard("t", 14.0);
        u.acted("t", "r1", sent);
        if let Some((asked, answered)) = window {
            u.confirm_asked("r1", asked);
            if let Some(a) = answered {
                u.confirm_answered("r1", a);
            }
        }
        if let Some(d) = done {
            u.act_done("r1", d);
        }
        u.reply("t", say, None).expect("a turn")
    }

    #[test]
    fn the_half_of_a_tool_that_was_you_deciding_separates_from_the_half_it_ran() {
        // `tool` is jv-act's span, and for a destructive tool most of it is
        // the 15 s window jv-act holds open waiting for an answer. No faster
        // machine shortens that half, so a number mixing it with execution
        // cannot be argued about against a budget — the same complaint
        // `spoke` answers one level up. Both ends are already on the bus:
        // `action.confirm` kind=request and kind=answer, threaded by the
        // request_id `intent.action` already named.
        let t = turn_with_confirm(40.0, 15.0, Some(31.0), Some((15.2, Some(30.2))));
        about(t.tool_ms, 16000.0);
        about(t.confirm_ms, 15000.0);
        about(t.ran_ms(), 1000.0);
        assert_eq!(t.confirm_waits, 1);
    }

    #[test]
    fn a_tool_that_asked_you_nothing_has_no_confirmation_to_subtract() {
        // Most tools are benign and never confirm. "No window" is not a 0 ms
        // window, and the split simply is not printed for them.
        let t = turn_with_confirm(20.0, 15.0, Some(18.0), None);
        about(t.tool_ms, 3000.0);
        assert_eq!(t.confirm_ms, None, "a window that did not open is not 0 ms");
        assert_eq!(t.confirm_waits, 0);
        assert_eq!(t.ran_ms(), None, "and there is nothing to split");
        assert_eq!(t.confirm_line("t"), None);
    }

    #[test]
    fn a_confirmation_still_open_when_the_reply_landed_is_not_timed() {
        // Same rule as an unanswered `intent.action`: a window whose close
        // this tap never saw lasted a length nobody can state. We still know
        // one was asked for, which is a different fact from none.
        let t = turn_with_confirm(40.0, 15.0, Some(31.0), Some((15.2, None)));
        assert_eq!(t.confirm_ms, None);
        assert_eq!(t.confirm_waits, 1, "we still know you were asked");
        assert_eq!(t.ran_ms(), None);
        assert_eq!(t.confirm_line("t"), None);
    }

    #[test]
    fn the_answer_that_counts_is_the_first_one_you_gave() {
        // jv-act ECHOES the answer it acted on (`kind=answer`,
        // answered_by=voice/cli/timeout) on the same topic the `jv confirm`
        // CLI publishes its answer on, so one decision can produce two
        // frames. The user stopped deciding at the FIRST of them; charging
        // them for jv-act's echo would inflate the half that is theirs.
        let mut u = Utterances::with_capacity(4);
        u.started("t", 10.0);
        u.ended("t", 13.0);
        u.heard("t", 14.0);
        u.acted("t", "r1", 15.0);
        u.confirm_asked("r1", 15.2);
        u.confirm_answered("r1", 20.2); // the CLI's answer
        u.confirm_answered("r1", 20.4); // jv-act's echo of it
        u.act_done("r1", 21.0);
        let t = u.reply("t", 40.0, None).expect("a turn");
        about(t.confirm_ms, 5000.0);
    }

    #[test]
    fn a_confirmation_window_outside_its_own_round_trip_is_refused() {
        // The window is a share of ONE tool call, so it has to sit inside
        // that call's own brackets. A window opening before jv-brain asked,
        // or closing after jv-act answered, means two frames disagree about
        // the order the pipeline ran in — and this nesting is also what
        // guarantees `confirm` can never exceed the `tool` it is part of.
        let before = turn_with_confirm(40.0, 15.0, Some(31.0), Some((14.9, Some(30.2))));
        assert_eq!(before.confirm_ms, None, "asked before jv-brain requested the tool");
        let after = turn_with_confirm(40.0, 15.0, Some(31.0), Some((15.2, Some(31.1))));
        assert_eq!(after.confirm_ms, None, "answered after jv-act was done");
        let backwards = turn_with_confirm(40.0, 15.0, Some(31.0), Some((20.0, Some(16.0))));
        assert_eq!(backwards.confirm_ms, None, "answered before it was asked");
    }

    #[test]
    fn two_confirmations_in_one_turn_are_the_union_like_the_calls_around_them() {
        let mut u = Utterances::with_capacity(4);
        u.started("t", 10.0);
        u.ended("t", 13.0);
        u.heard("t", 14.0);
        for (rid, sent, asked, answered, done) in [
            ("r1", 15.0, 15.2, 20.2, 21.0),
            ("r2", 25.0, 25.2, 27.2, 28.0),
        ] {
            u.acted("t", rid, sent);
            u.confirm_asked(rid, asked);
            u.confirm_answered(rid, answered);
            u.act_done(rid, done);
        }
        let t = u.reply("t", 40.0, None).expect("a turn");
        about(t.tool_ms, 9000.0);
        about(t.confirm_ms, 7000.0);
        about(t.ran_ms(), 2000.0);
        assert_eq!(t.confirm_waits, 2);
    }

    #[test]
    fn two_questions_open_at_once_are_one_moment_of_your_time() {
        // The UNION and not the sum. jv-act holds one confirmation open at a
        // time — that is ITS rule, enforced in its own single-outstanding
        // slot, and not something this reader is entitled to assume. Summing
        // two overlapping windows could produce a `you` larger than the
        // `tool` it is supposed to be part of.
        let mut u = Utterances::with_capacity(4);
        u.started("t", 10.0);
        u.ended("t", 13.0);
        u.heard("t", 14.0);
        for (rid, sent, asked, answered, done) in [
            ("r1", 15.0, 15.2, 25.2, 26.0),
            ("r2", 16.0, 20.2, 30.2, 31.0),
        ] {
            u.acted("t", rid, sent);
            u.confirm_asked(rid, asked);
            u.confirm_answered(rid, answered);
            u.act_done(rid, done);
        }
        let t = u.reply("t", 40.0, None).expect("a turn");
        about(t.tool_ms, 16000.0);
        about(t.confirm_ms, 15000.0);
        about(t.ran_ms(), 1000.0);
    }

    #[test]
    fn a_confirmation_for_a_request_this_tap_never_saw_belongs_to_no_turn() {
        // `action.confirm` carries a request_id and no utterance_id, so the
        // join runs through the `intent.action` that named one — exactly as
        // `action.result` does. A tap that started mid-turn sees the
        // question and not the request behind it.
        let mut u = Utterances::with_capacity(4);
        u.started("t", 10.0);
        u.ended("t", 13.0);
        u.heard("t", 14.0);
        u.confirm_asked("orphan", 15.2);
        u.confirm_answered("orphan", 30.2);
        u.acted("t", "r1", 15.0);
        u.act_done("r1", 18.0);
        let t = u.reply("t", 20.0, None).expect("a turn");
        assert_eq!(t.confirm_waits, 0);
        assert_eq!(t.confirm_ms, None);
        about(t.tool_ms, 3000.0);
    }

    #[test]
    fn a_confirmation_inside_a_tool_span_nobody_could_time_is_not_reported() {
        // `confirm` is a share of `tool` the way `tool` is a share of
        // `think`: a share of a whole nobody measured is not a share. Here
        // the window itself is perfectly well formed and the round trip
        // around it falls outside the `think` it claims to divide.
        let t = turn_with_confirm(20.0, 13.5, Some(18.0), Some((14.5, Some(17.0))));
        assert_eq!(t.tool_ms, None, "the round trip started before jv-ears finished");
        assert_eq!(t.confirm_ms, None, "so its share is not a share of anything");
        assert_eq!(t.confirm_waits, 1, "we still know you were asked");
    }

    #[test]
    fn the_confirm_line_names_the_half_no_machine_can_shorten() {
        let t = turn_with_confirm(40.0, 15.0, Some(31.0), Some((15.2, Some(30.2))));
        let line = t.confirm_line("utt-7").expect("a confirm line");
        assert!(line.contains("turn utt-7:"), "{line}");
        assert!(line.contains("you=15000ms"), "{line}");
        assert!(line.contains("ran=1000ms"), "{line}");
        assert!(line.contains("(1 confirmation)"), "{line}");
        // It names `tool` and does not restate it, because the line printed
        // directly above it gives the number — and `lines()` is what makes
        // "directly above" true rather than hopeful.
        assert!(line.contains("tool is you="), "{line}");
        let all = t.lines("utt-7");
        assert_eq!(all.len(), 4, "{all:?}");
        assert_eq!(all[3], line);
        assert!(all[2].contains("tool=16000ms"), "{:?}", all[2]);
        // Its own line, like the `tool` split above it: nothing over it grew
        // a number.
        assert!(!t.line("utt-7").contains("you="), "{}", t.line("utt-7"));
        assert!(!t.tool_line("utt-7").expect("a tool line").contains("you="), "{line}");

        let two = turn_with_confirm(40.0, 15.0, Some(31.0), Some((15.2, Some(30.2))));
        let mut two = two;
        two.confirm_waits = 2;
        assert!(two.confirm_line("utt-7").expect("a line").contains("(2 confirmations)"));
    }

    /// The worst case every turn line has to survive, built once.
    ///
    /// `jv_ears.pipeline` stamps `uuid.uuid4()` on every utterance, so a
    /// 36-character id is the LIVE case and not a pathological one.
    fn widest_turn() -> Turn {
        Turn {
            total_ms: Some(999_999.0),
            speech_ms: Some(999_999.0),
            respond_ms: Some(999_999.0),
            hold_ms: Some(0.0),
            hear_ms: Some(999_999.0),
            think_ms: Some(999_999.0),
            tool_ms: Some(999_999.0),
            tool_calls: ACTS_PER_TURN,
            confirm_ms: Some(999_999.0),
            confirm_waits: ACTS_PER_TURN,
        }
    }

    const WIDEST_ID: &str = "3f2a91c4-6d1e-4b7a-9c05-8ef23a41d9b7";

    /// Every line `jv tap` writes about a turn, at the widest it can be.
    ///
    /// Three of the four bounds this rests on are enforced somewhere else
    /// and one is not, which is the point of writing them down here:
    ///
    ///   * **the id** is capped by `short_id` at `ID_COLUMNS`, so no id can
    ///     break this line however long it is — the test below proves that
    ///     on an id twenty times too long;
    ///   * **both counts** are two digits because `ACTS_PER_TURN` stops the
    ///     recording at 32, and a confirmation cannot exist without an act;
    ///   * **every span is six digits**, and THIS is the bound that is
    ///     assumed rather than enforced. 999999 ms is 16.7 minutes — longer
    ///     than any turn that ends with somebody still listening — and a
    ///     seventh digit would add a column to four of these five lines.
    ///     Nothing stops a span that long from being measured; this test is
    ///     what would notice.
    #[test]
    fn every_line_a_turn_prints_fits_eighty_columns() {
        let t = widest_turn();
        let mut lines = t.lines(WIDEST_ID);
        // The `think` split arrives a frame later, off jv-brain's gauge, and
        // is the fifth line the same turn can produce.
        let mut stats = TurnStats::default();
        stats.push(&t, WIDEST_ID);
        lines.push(stats.brain_split(1.0).expect("a think split"));

        assert_eq!(lines.len(), 5, "the widest turn stopped producing every line: {lines:?}");
        for line in &lines {
            let w = line.chars().count() + ">>> ".len();
            assert!(w <= TAP_COLUMNS, "{w} columns, {} too many: {line}", w - TAP_COLUMNS);
            // The control: if a line came out far under the budget, this
            // test stopped building the worst case and stopped proving
            // anything. Every one of these is between 65 and 77 today.
            assert!(w >= 60, "{w} columns is not a worst case: {line}");
            // And every one of them carries the abbreviated id, so a line
            // added later cannot quietly print the raw one.
            assert!(line.contains("3f2a91c4..."), "the id is not abbreviated: {line}");
            assert!(!line.contains(WIDEST_ID), "the whole id reached a turn line: {line}");
        }
    }

    #[test]
    fn an_id_no_line_could_carry_is_abbreviated_rather_than_left_to_wrap() {
        assert_eq!(short_id("utt-7"), "utt-7", "an id that fits is never touched");
        assert_eq!(short_id(&"x".repeat(ID_COLUMNS)), "x".repeat(ID_COLUMNS));
        // One character past the cap is where abbreviating starts SAVING
        // something; abbreviating before that would make the id longer.
        let over = "x".repeat(ID_COLUMNS + 1);
        assert_eq!(short_id(&over).chars().count(), ID_COLUMNS);
        assert!(short_id(&over).ends_with("..."));
        // Twenty times too long, and a multi-byte id, which `chars` counts
        // and `len` would not: the cap is columns, not bytes.
        assert_eq!(short_id(&"é".repeat(220)).chars().count(), ID_COLUMNS);
        let t = widest_turn();
        for line in t.lines(&"z".repeat(220)) {
            assert!(line.chars().count() + 4 <= TAP_COLUMNS, "{line}");
        }
    }

    #[test]
    fn two_ids_that_start_alike_print_alike_and_that_is_the_price() {
        // The cost of abbreviating, written down where somebody looking for
        // it will find it: `jv tap` is read by a human watching turns go by,
        // and the whole id is on the frames printed beside these lines.
        let a = "3f2a91c4-6d1e-4b7a-9c05-8ef23a41d9b7";
        let b = "3f2a91c4-0000-0000-0000-000000000000";
        assert_ne!(a, b);
        assert_eq!(short_id(a), short_id(b));
    }

    #[test]
    fn no_line_names_a_span_whose_value_no_line_printed() {
        // The ladder's one rule: `tool_line` says `tool=` and `confirm_line`
        // says `tool` without restating it, so a confirm line printed
        // without a tool line above it would point at nothing. `reply`
        // cannot build that turn — `confirm_ms` is gated on `tool_ms` which
        // is gated on the seam — but the fields are public and this is the
        // guard that makes it true of the TYPE and not just of one caller.
        let mut t = widest_turn();
        t.think_ms = None;
        assert!(t.tool_line("t").is_none());
        assert!(t.confirm_line("t").is_none(), "a confirm line with no tool line over it");
        assert_eq!(t.lines("t").len(), 2, "the two lines every turn prints");
    }

    #[test]
    fn the_summary_table_and_the_hop_table_fit_the_same_eighty_columns() {
        // The turn lines are not the only thing `jv tap` prints as a report,
        // and a table that wraps is worse than a line that does: its columns
        // stop lining up with each other, which is the whole of its value.
        let mut stats = TurnStats::default();
        stats.push(&widest_turn(), WIDEST_ID);
        stats.brain_split(1.0);
        let mut hops = HopStats::default();
        // The widest real topic on the bus, and a hop that overflows the
        // column it is formatted into.
        hops.hop("context.window.changed", 999_999.99);
        for line in stats.summary().lines().chain(hops.summary().lines()) {
            let w = line.chars().count();
            assert!(w <= TAP_COLUMNS, "{w} columns: {line}");
        }
    }

    /// The per-frame line `jv tap --latency` writes above those tables, at
    /// inputs no publisher is stopped from producing.
    ///
    /// This is the one report line the CLI wrote from `jv.rs`, where the
    /// end-to-end width test could not reach it (B23), and the one whose
    /// width is set by a string a REMOTE process chose. `validate_envelope`
    /// bounds a topic's alphabet and a src's emptiness and neither one's
    /// LENGTH, so both are clipped here rather than assumed — the two rows
    /// below are `audio.transcript` (the longest topic any schema declares)
    /// and a topic and a src from a service that does not exist yet.
    ///
    /// What is assumed rather than enforced, said out loud: `seq` is eight
    /// digits and the hop is eight columns, which leaves this line 16 short
    /// of the budget. A 4.2-billion seq (ten digits) and a 99-second hop
    /// still fit; a hop wide enough to break this is a publisher stamping
    /// wall-clock `ts` on a monotonic bus, and printing that number whole is
    /// the report, not a formatting fault.
    #[test]
    fn the_streamed_hop_line_fits_eighty_columns_whatever_a_publisher_is_called() {
        let rows = [
            ("audio.transcript", "jv-ears", 12_345_678i64, 999_999.99f64),
            ("jv-hud-bridge is the longest src today", "jv-hud-bridge", 0, 0.0),
            (&"a.".repeat(60), &"s".repeat(120)[..], i64::MAX, -1.0),
        ];
        for (topic, src, seq, ms) in rows {
            let line = hop_line(topic, src, seq, ms);
            let w = line.chars().count();
            assert!(w <= TAP_COLUMNS, "{w} columns, {} too many: {line}", w - TAP_COLUMNS);
            // The control: a line far under the budget would mean this test
            // stopped building the worst case. Every one of these is 64+.
            assert!(w >= 60, "{w} columns is not a worst case: {line}");
        }
        // A topic too long to print is clipped and SAYS it was, with the same
        // `...` short_id uses; one that fits is never touched.
        let long = hop_line(&"a.".repeat(60), "jv-ears", 1, 1.0);
        assert!(long.starts_with("a.a.a.a.a.a.a.a.a.a..."), "the clip is not marked: {long}");
        assert!(hop_line("audio.vad", "jv-ears", 1, 1.0).starts_with("audio.vad  "));
        // All three views of a topic — the stream, the table's header and its
        // rows — end that column in the same place, which is the one cap
        // `TOPIC_COLUMNS` exists to serve and what lets a reader trace a
        // topic out of one view into the other. True for every topic set this
        // bus can produce; the table takes more columns when it needs them to
        // tell two rows apart, which is B24's own test.
        //
        // Each is checked at the first character PAST the column rather than
        // against a padded copy of the topic: the table's next field is right
        // aligned, so a narrower column and a wider pad are the same string
        // and only what follows them tells the two apart.
        let mut hops = HopStats::default();
        for _ in 0..3 {
            hops.hop("audio.transcript", 2.0);
        }
        let table = hops.summary();
        let head = table.lines().nth(1).expect("the table header");
        let row = table.lines().nth(2).expect("the table's one row");
        let stream = hop_line("audio.transcript", "jv-ears", 1, 2.0);
        let n_at = TOPIC_COLUMNS + 1 + 4; // `{:>5}`, so the value's last digit
        assert_eq!(head.as_bytes()[n_at], b'n', "the header's count column moved:\n{head}");
        assert_eq!(row.as_bytes()[n_at], b'3', "the row's count column moved:\n{row}");
        assert_eq!(stream.as_bytes()[TOPIC_COLUMNS], b' ', "no gap after the topic: {stream}");
        assert_eq!(stream.as_bytes()[TOPIC_COLUMNS + 1], b'j', "the src does not start there: {stream}");
    }

    /// Two topics, one label, two rows of numbers under it — the one thing a
    /// measurement table may not do (B24).
    ///
    /// `TOPIC_COLUMNS` buys alignment by clipping, and a clip is a promise
    /// that what it hid is one `jv sub '*'` away. That promise holds for the
    /// per-frame STREAM, where each line is about a frame that named itself.
    /// It does not hold for the table, where a row is about a topic and the
    /// label is the only thing that says WHICH — so here identity outranks
    /// alignment, and the column grows until every row carries its own name.
    #[test]
    fn two_topics_that_clip_alike_never_become_one_row_of_numbers() {
        let a = "context.window.changed.alpha";
        let b = "context.window.changed.beta";
        // The control: without it this test would pass on a pair the fixed
        // column already told apart, and prove nothing.
        assert_eq!(clip(a, TOPIC_COLUMNS), clip(b, TOPIC_COLUMNS), "not the case this is about");

        let mut hops = HopStats::default();
        hops.hop(a, 1.0);
        hops.hop(b, 2.0);
        let table = hops.summary();
        let rows: Vec<&str> = table.lines().skip(2).collect();
        assert_eq!(rows.len(), 2, "two topics are not two rows:\n{table}");

        let w = table_topic_columns(&[a, b]);
        let label = |line: &str| line.chars().take(w).collect::<String>();
        assert_ne!(label(rows[0]), label(rows[1]), "two topics, one label:\n{table}");

        // And the table is still a table: the header moved with the rows, so
        // every number is still under the heading that names it. Checked at
        // the first character PAST the column, for the reason the stream test
        // gives — the next field is right aligned, so a narrow column and a
        // wide pad are the same string.
        let n_at = w + 1 + 4;
        let head = table.lines().nth(1).expect("the table header");
        assert_eq!(head.as_bytes()[n_at], b'n', "the header did not move with the rows:\n{table}");
        for row in &rows {
            assert_eq!(row.as_bytes()[n_at], b'1', "a row's count column moved:\n{table}");
        }
    }

    /// The column grows as far as identity needs and not one column further.
    #[test]
    fn the_topic_column_grows_only_as_far_as_telling_the_rows_apart_needs() {
        // Nothing a schema declares reaches the cap, so a real bus never
        // moves this column at all — which is what keeps the table and the
        // stream above it lined up in every case that exists today.
        assert_eq!(
            table_topic_columns(&["audio.transcript", "sys.health", "speech.say", "action.confirm"]),
            TOPIC_COLUMNS,
        );
        // One column past the first character that tells the two apart.
        // `...alpha` / `...beta` diverge at index 23, and a clip keeps
        // `columns - 3` of them, so 27 is the first width that separates
        // them and 26 is not.
        let pair = ["context.window.changed.alpha", "context.window.changed.beta"];
        assert_eq!(table_topic_columns(&pair), 27);
        assert_eq!(clip(pair[0], 26), clip(pair[1], 26), "26 columns would have done");

        // A CLIPPED label and a whole one can collide too, so it is the
        // printed labels that are compared and never "the long ones". This
        // pair is a string pair and not a topic pair — `validate_envelope`
        // refuses an empty segment, so nothing ending in two dots reaches a
        // live tap — and it is covered because nothing else in this width
        // code assumes the topic alphabet.
        let dotted = format!("{}...", "a".repeat(19));
        let longer = format!("{}bcdef", "a".repeat(19));
        assert_eq!(clip(&longer, TOPIC_COLUMNS), dotted, "not the collision this is about");
        assert_eq!(table_topic_columns(&[&dotted, &longer]), 23);
    }

    /// The order of the two rules, pinned where it costs something.
    ///
    /// Every other report line this CLI writes fits `TAP_COLUMNS` at its
    /// worst input (B22/B23). This one does not, deliberately: when telling
    /// two rows apart needs more columns than the budget has, the table
    /// takes them. A wrapped row is a row a reader can still resolve; two
    /// identical labels over different numbers is a table that lies.
    ///
    /// Nothing on this bus can trigger it — `audio.transcript` is 16 of the
    /// 22 and the widest topic any schema declares — so this is a
    /// consequence pinned before it can bite, not a defect.
    #[test]
    fn the_table_goes_wider_than_the_budget_rather_than_collapse_two_rows() {
        let a = format!("{}alpha", "z.".repeat(25));
        let b = format!("{}beta", "z.".repeat(25));
        let mut hops = HopStats::default();
        hops.hop(&a, 1.0);
        hops.hop(&b, 2.0);
        let table = hops.summary();
        let rows: Vec<&str> = table.lines().skip(2).collect();

        let w = table_topic_columns(&[&a, &b]);
        assert!(w + 39 > TAP_COLUMNS, "{w} columns still fits the budget; no trade was made");
        assert!(
            rows.iter().all(|r| r.chars().count() > TAP_COLUMNS),
            "the rows fit, so nothing was traded:\n{table}",
        );
        let label = |line: &str| line.chars().take(w).collect::<String>();
        assert_ne!(label(rows[0]), label(rows[1]), "and it bought nothing:\n{table}");
    }

    #[test]
    fn turn_summary_splits_a_confirming_tool_into_you_and_jv_act() {
        let mut s = TurnStats::default();
        s.push(&turn_with_confirm(40.0, 15.0, Some(31.0), Some((15.2, Some(30.2)))), "t");
        let out = s.summary();
        let at = |w: &str| out.find(w).unwrap_or_else(|| panic!("no {w} row in\n{out}"));
        assert!(at("  tool") < at("    you"), "the halves sit under their whole:\n{out}");
        assert!(at("    you") < at("    ran"), "{out}");
        assert!(at("    ran") < at("respond"), "{out}");
        assert!(out.contains("15000ms"), "{out}");
        assert!(out.contains("action.confirm"), "and say where the number came from:\n{out}");
    }

    #[test]
    fn a_confirmation_nobody_could_time_leaves_neither_half_of_it() {
        // A `ran` row standing on turns a `you` row does not would be an
        // average over turns measured two different ways. It cannot happen
        // here — `ran_ms` is the subtraction and refuses without both — and
        // this is the turn that would expose it if it ever did: a question
        // this tap saw opened and never saw closed, inside a `tool` that was
        // measured perfectly well.
        let mut s = TurnStats::default();
        s.push(&turn_with_confirm(40.0, 15.0, Some(31.0), Some((15.2, None))), "t");
        let out = s.summary();
        assert!(!out.contains("\n    you"), "{out}");
        assert!(!out.contains("\n    ran"), "{out}");
        assert!(out.contains("\n  tool"), "tool is still measured:\n{out}");
    }

    #[test]
    fn a_summary_with_no_confirmation_in_it_has_no_confirmation_rows() {
        let mut s = TurnStats::default();
        s.push(&turn_with_confirm(20.0, 15.0, Some(18.0), None), "t");
        let out = s.summary();
        assert!(!out.contains("\n    you"), "{out}");
        assert!(!out.contains("\n    ran"), "{out}");
        assert!(!out.contains("action.confirm"), "{out}");
    }

    #[test]
    fn turn_summary_shows_jv_acts_share_of_a_tool_turn() {
        let mut s = TurnStats::default();
        s.push(&turn_with_tools(10.0, 13.0, 14.0, 20.0, &[("r1", 15.0, Some(18.0))]), "t");
        let out = s.summary();
        let at = |w: &str| out.find(w).unwrap_or_else(|| panic!("no {w} row in\n{out}"));
        assert!(at("think") < at("tool"), "a share is listed under its whole:\n{out}");
        assert!(at("tool") < at("respond"), "{out}");
        assert!(out.contains("3000ms"), "{out}");
        assert!(out.contains("jv-act"), "{out}");
        // A turn that ran tools publishes no first-say gauge, so the row it
        // would have filled must not appear instead.
        assert!(!out.contains("\n  model"), "{out}");
    }

    #[test]
    fn every_summary_row_stays_inside_the_columns_it_is_printed_in() {
        // The table is read in a terminal, and a `whose time it is` longer
        // than its column silently shoves the three numbers beside it out of
        // line for that row only — which reads as a broken number rather
        // than as a long label. This is the check the `tool` row's first
        // label failed, and it belongs to every row after it.
        let mut s = TurnStats::default();
        s.push(&turn_with_tools(10.0, 13.0, 14.0, 20.0, &[("r1", 15.0, Some(18.0))]), "a");
        s.push(&turn_with_seam(20.0, 23.0, 24.0, 24.3, Some(1.5)), "b");
        s.brain_split(210.0);
        s.push(&turn_with_confirm(40.0, 15.0, Some(31.0), Some((15.2, Some(30.2)))), "c");
        let out = s.summary();
        // The header and every row under it, stopping at the first footnote.
        // NOT "every line that is not indented": the deepest rows ARE
        // indented, by the same four spaces a footnote's continuation lines
        // use, and a filter that skipped them would exempt the rows most
        // likely to overflow from the check written for them.
        let rows: Vec<&str> = out
            .lines()
            .skip_while(|l| !l.starts_with("span "))
            .take_while(|l| !l.starts_with("---"))
            .collect();
        assert!(rows.len() > 8, "not every row is here:\n{out}");
        let header = rows[0].len();
        for r in &rows {
            assert_eq!(r.len(), header, "row is not the header's width:\n{out}");
        }
    }

    #[test]
    fn a_summary_with_no_tool_turn_in_it_has_no_tool_row() {
        let mut s = TurnStats::default();
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 14.2, Some(1.5)), "t");
        let out = s.summary();
        assert!(!out.contains("\n  tool"), "{out}");
        assert!(!out.contains("jv-act"), "{out}");
    }

    #[test]
    fn turn_summary_of_nothing_is_nothing() {
        assert!(TurnStats::default().is_empty());
        assert_eq!(TurnStats::default().summary(), "");
    }

    #[test]
    fn turn_summary_reads_in_the_order_the_turn_happened() {
        let mut s = TurnStats::default();
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 14.2, Some(1.5)), "t");
        s.push(&turn_with_seam(20.0, 24.0, 25.6, 26.0, Some(1.5)), "t");
        let out = s.summary();
        let at = |w: &str| out.find(w).unwrap_or_else(|| panic!("no {w} row in\n{out}"));
        assert!(at("spoke") < at("hold"), "{out}");
        assert!(at("hold") < at("respond"), "{out}");
        assert!(at("respond") < at("total"), "{out}");
        assert!(out.contains("2 turns"), "{out}");
        // Nearest-rank p50 of [1500, 2500] spoke is 1500; max is 2500.
        assert!(out.contains("1500ms"), "{out}");
        assert!(out.contains("2500ms"), "{out}");
        // The two numbers a reader has to keep apart are named, not implied.
        assert!(out.contains("hold+respond"), "{out}");
        assert!(!out.contains("unmeasured"), "everything was measured:\n{out}");
    }

    /// Build a turn with the ASR seam in it, for the summary tests.
    fn turn_with_seam(start: f64, end: f64, heard: f64, say: f64, hold_s: Option<f64>) -> Turn {
        let mut u = Utterances::with_capacity(4);
        u.started("t", start);
        u.ended("t", end);
        u.heard("t", heard);
        u.reply("t", say, hold_s).expect("a turn")
    }

    #[test]
    fn turn_summary_shows_the_two_halves_of_respond_in_the_order_they_ran() {
        let mut s = TurnStats::default();
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 14.2, Some(1.5)), "t");
        s.push(&turn_with_seam(20.0, 24.0, 26.0, 26.4, Some(1.5)), "t");
        let out = s.summary();
        let at = |w: &str| out.find(w).unwrap_or_else(|| panic!("no {w} row in\n{out}"));
        assert!(at("hold") < at("hear"), "{out}");
        assert!(at("hear") < at("think"), "{out}");
        assert!(at("think") < at("respond"), "{out}");
        assert!(at("respond") < at("total"), "{out}");
        // Nearest-rank p50 of the two hears is the smaller, 1000 ms; the two
        // thinks are 200 and 400.
        assert!(out.contains("1000ms"), "{out}");
        assert!(out.contains("400ms"), "{out}");
        // The table must say respond is these two and not a third thing
        // beside them, or a reader adds all three together.
        assert!(out.contains("hear + think"), "respond must name its halves:\n{out}");
        assert!(!out.contains("no `audio.transcript` final"), "{out}");
    }

    #[test]
    fn turn_summary_omits_the_asr_seam_it_never_saw_and_says_why() {
        let mut s = TurnStats::default();
        s.push(&turn(10.0, 13.0, 14.2, Some(1.5)), "t");
        let out = s.summary();
        assert!(out.contains("\nrespond   "), "{out}");
        assert!(!out.contains("\nhear  "), "no hear row without a final to divide at:\n{out}");
        assert!(!out.contains("\nthink "), "{out}");
        assert!(out.contains("audio.transcript"), "the reason must name the frame:\n{out}");
    }

    #[test]
    fn turn_summary_omits_the_spans_it_could_not_measure_and_says_why() {
        let mut s = TurnStats::default();
        s.push(&turn(10.0, 13.0, 14.2, None), "t");
        let out = s.summary();
        assert!(out.contains("respond"), "{out}");
        assert!(out.contains("total"), "{out}");
        assert!(!out.contains("spoke  "), "no spoke row without a hold to subtract:\n{out}");
        assert!(out.contains(EARS_HOLD_METRIC), "the reason must name the gauge:\n{out}");
        // And the total must not be offered as the machine's number, because
        // it still has the user's voice in it.
        assert!(!out.contains("hold+respond"), "{out}");
    }

    #[test]
    fn a_hold_that_did_not_fit_takes_its_own_row_down_with_it() {
        let mut s = TurnStats::default();
        // 1.5 s of hold cannot have happened inside a 0.9 s segment.
        s.push(&turn(10.0, 10.9, 11.5, Some(1.5)), "t");
        let out = s.summary();
        // `spoke` and `hold` are two halves of one subtraction. Printing the
        // hold on its own would put a number in the table for a turn whose
        // other half was refused, and the row above it would be an average
        // over a different set of turns.
        assert!(!out.contains("\nhold  "), "{out}");
        assert!(!out.contains("\nspoke "), "{out}");
        assert!(out.contains("unmeasured"), "{out}");
    }

    #[test]
    fn a_turn_with_no_start_still_earns_a_respond_row() {
        let mut s = TurnStats::default();
        let mut u = Utterances::with_capacity(4);
        u.ended("t", 13.0);
        s.push(&u.reply("t", 14.2, Some(1.5)).expect("a turn"), "t");
        let out = s.summary();
        assert!(out.contains("respond"), "{out}");
        assert!(!out.contains("total "), "a total we could not measure is not a row:\n{out}");
    }

    // --- reading jv-ears' endpoint hold off its own heartbeat -------------

    /// A `sys.health` frame as jv-ears publishes it, with `metrics` under the
    /// caller's control.
    fn ears_health(src: &str, service: &str, v: u64, conf: f64, metrics: rmpv::Value) -> rmpv::Value {
        map(&[
            ("topic", rmpv::Value::from("sys.health")),
            ("src", rmpv::Value::from(src)),
            ("v", rmpv::Value::from(v)),
            ("conf", rmpv::Value::from(conf)),
            ("ts", rmpv::Value::from(1.0)),
            (
                "body",
                map(&[
                    ("service", rmpv::Value::from(service)),
                    ("state", rmpv::Value::from("ok")),
                    ("period_s", rmpv::Value::from(5.0)),
                    ("metrics", metrics),
                ]),
            ),
        ])
    }

    fn hold_metrics(v: rmpv::Value) -> rmpv::Value {
        map(&[("mic_open", rmpv::Value::from(1.0)), (EARS_HOLD_METRIC, v)])
    }

    #[test]
    fn the_endpoint_hold_is_read_off_jv_ears_own_heartbeat() {
        let f = ears_health(EARS, EARS, 1, 1.0, hold_metrics(1.5.into()));
        assert_eq!(ears_endpoint_hold_s(&f), Some(1.5));
    }

    #[test]
    fn an_endpoint_hold_is_refused_unless_jv_ears_itself_said_it() {
        let ok = hold_metrics(1.5.into());
        // Someone else's heartbeat, whatever it claims to be.
        assert_eq!(ears_endpoint_hold_s(&ears_health("jv-voice", EARS, 1, 1.0, ok.clone())), None);
        // jv-ears' connection carrying a body that names another service.
        assert_eq!(ears_endpoint_hold_s(&ears_health(EARS, "jv-voice", 1, 1.0, ok.clone())), None);
        // A schema version this binary was not written against.
        assert_eq!(ears_endpoint_hold_s(&ears_health(EARS, EARS, 2, 1.0, ok.clone())), None);
        // A state topic hedging its confidence disagrees with itself.
        assert_eq!(ears_endpoint_hold_s(&ears_health(EARS, EARS, 1, 0.9, ok)), None);
    }

    #[test]
    fn a_hold_that_is_not_a_duration_is_not_a_hold() {
        for bad in [
            rmpv::Value::from("1.5"),
            rmpv::Value::from(-0.1),
            rmpv::Value::from(f64::NAN),
            rmpv::Value::from(f64::INFINITY),
        ] {
            let f = ears_health(EARS, EARS, 1, 1.0, hold_metrics(bad.clone()));
            assert_eq!(ears_endpoint_hold_s(&f), None, "{bad:?}");
        }
        // A heartbeat that simply does not carry the gauge.
        let f = ears_health(EARS, EARS, 1, 1.0, map(&[("mic_open", rmpv::Value::from(1.0))]));
        assert_eq!(ears_endpoint_hold_s(&f), None);
    }

    fn say_metrics(count: rmpv::Value, ms: rmpv::Value) -> rmpv::Value {
        map(&[
            ("llm_rung", rmpv::Value::from(1.0)),
            (BRAIN_FIRST_SAYS_METRIC, count),
            (BRAIN_FIRST_SAY_METRIC, ms),
        ])
    }

    #[test]
    fn the_models_share_of_think_is_read_off_jv_brains_own_heartbeat() {
        let f = ears_health(BRAIN, BRAIN, 1, 1.0, say_metrics(3.into(), 412.0.into()));
        assert_eq!(brain_first_say(&f), Some((3, 412.0)));
    }

    #[test]
    fn a_model_share_is_refused_unless_jv_brain_itself_said_it() {
        let ok = say_metrics(1.into(), 412.0.into());
        assert_eq!(brain_first_say(&ears_health(EARS, BRAIN, 1, 1.0, ok.clone())), None);
        assert_eq!(brain_first_say(&ears_health(BRAIN, EARS, 1, 1.0, ok.clone())), None);
        assert_eq!(brain_first_say(&ears_health(BRAIN, BRAIN, 2, 1.0, ok.clone())), None);
        assert_eq!(brain_first_say(&ears_health(BRAIN, BRAIN, 1, 0.9, ok)), None);
    }

    #[test]
    fn a_model_share_without_a_trustworthy_turn_count_is_refused() {
        // The count is what tells a fresh gauge from a re-stated one. A frame
        // that cannot supply one leaves the number unplaceable, not usable.
        for bad in [
            rmpv::Value::from(0),            // no turn has been measured yet
            rmpv::Value::from(-1),
            rmpv::Value::from(1.5),          // a turn counter with a fraction in it
            rmpv::Value::from("2"),
            rmpv::Value::from(f64::NAN),
            rmpv::Value::from(f64::INFINITY),
        ] {
            let f = ears_health(BRAIN, BRAIN, 1, 1.0, say_metrics(bad.clone(), 412.0.into()));
            assert_eq!(brain_first_say(&f), None, "{bad:?}");
        }
        // And a gauge that is not a duration.
        for bad in [
            rmpv::Value::from("412"),
            rmpv::Value::from(-0.1),
            rmpv::Value::from(f64::NAN),
        ] {
            let f = ears_health(BRAIN, BRAIN, 1, 1.0, say_metrics(2.into(), bad.clone()));
            assert_eq!(brain_first_say(&f), None, "{bad:?}");
        }
        // A heartbeat carrying one half of the pair is carrying neither.
        let only_count = map(&[(BRAIN_FIRST_SAYS_METRIC, rmpv::Value::from(2))]);
        assert_eq!(brain_first_say(&ears_health(BRAIN, BRAIN, 1, 1.0, only_count)), None);
        let only_ms = map(&[(BRAIN_FIRST_SAY_METRIC, rmpv::Value::from(412.0))]);
        assert_eq!(brain_first_say(&ears_health(BRAIN, BRAIN, 1, 1.0, only_ms)), None);
    }

    #[test]
    fn a_gauge_splits_the_think_of_the_turn_it_followed() {
        let mut s = TurnStats::default();
        // think = 26.0 - 14.0 = 2000ms
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 16.0, Some(1.5)), "utt-1");
        let line = s.brain_split(1600.0).expect("the gauge fits");
        assert_eq!(line, "turn utt-1: think=2000ms is wait=400ms + model=1600ms");
        let table = s.summary();
        assert!(table.contains("wait "), "{table}");
        assert!(table.contains("model "), "{table}");
        // and the footer stops apologising for an unsplit think
        assert!(!table.contains("think unsplit"), "{table}");
    }

    #[test]
    fn one_gauge_splits_one_turn_and_a_restated_one_splits_nothing() {
        let mut s = TurnStats::default();
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 16.0, Some(1.5)), "utt-1");
        assert!(s.brain_split(1600.0).is_some());
        // The same number again (a later periodic heartbeat that slipped the
        // counter check) must not double-count the turn it already split.
        assert_eq!(s.brain_split(1600.0), None);
    }

    #[test]
    fn a_gauge_longer_than_the_think_it_divides_produces_no_numbers() {
        let mut s = TurnStats::default();
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 16.0, Some(1.5)), "utt-1");
        assert_eq!(s.brain_split(2400.0), None, "a model span outside its own think");
        let table = s.summary();
        assert!(table.contains("think unsplit"), "{table}");
    }

    #[test]
    fn a_turn_whose_think_was_unmeasured_cannot_be_split() {
        let mut s = TurnStats::default();
        // no final transcript: no seam, so no think to divide
        s.push(&turn(10.0, 13.0, 16.0, Some(1.5)), "utt-1");
        assert_eq!(s.brain_split(1600.0), None);
    }

    #[test]
    fn a_gauge_with_no_turn_in_front_of_it_is_dropped() {
        let mut s = TurnStats::default();
        assert_eq!(s.brain_split(1600.0), None, "nothing reported yet");
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 16.0, Some(1.5)), "utt-1");
        // The gauge for an EARLIER turn must not be attached to this one just
        // because this one is the next thing in the queue. Only a counter rise
        // gets this far (bin/jv.rs), and this is the one turn it may split.
        assert!(s.brain_split(1600.0).is_some());
    }

    #[test]
    fn a_turn_that_replaces_the_waiting_one_replaces_it_even_unsplittable() {
        // Turn 2's `think` was unmeasured, so there is nothing for a gauge to
        // divide — and the gauge belongs to turn 2, not to turn 1. Leaving
        // turn 1 waiting would split IT with turn 2's number, which is the
        // same error the counter in bin/jv.rs exists to prevent, one layer in.
        let mut s = TurnStats::default();
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 16.0, Some(1.5)), "utt-1");
        s.push(&turn(20.0, 23.0, 26.0, Some(1.5)), "utt-2");
        assert_eq!(s.brain_split(1600.0), None);
    }

    #[test]
    fn a_negative_model_span_divides_nothing() {
        // `brain_first_say` refuses one off the wire, but this is a public
        // entry point and the rule is its own: a `wait` longer than the
        // `think` it is part of would be arithmetic, not a measurement.
        let mut s = TurnStats::default();
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 16.0, Some(1.5)), "utt-1");
        assert_eq!(s.brain_split(-1.0), None);
    }

    #[test]
    fn only_the_most_recent_turn_waits_for_a_gauge() {
        let mut s = TurnStats::default();
        s.push(&turn_with_seam(10.0, 13.0, 14.0, 16.0, Some(1.5)), "utt-1");
        s.push(&turn_with_seam(20.0, 23.0, 24.0, 26.0, Some(1.5)), "utt-2");
        let line = s.brain_split(1600.0).expect("the gauge fits");
        assert!(line.starts_with("turn utt-2:"), "{line}");
    }

    #[test]
    fn health_line_renders_a_full_body() {
        let body = map(&[
            ("service", rmpv::Value::from("jv-ears")),
            ("state", rmpv::Value::from("ok")),
            ("uptime_s", rmpv::Value::from(12.5)),
            ("drops", map(&[("audio.vad", rmpv::Value::from(2))])),
            ("notes", rmpv::Value::from("asr warm")),
        ]);
        let line = health_line(&body);
        assert!(line.starts_with("jv-ears      ok    "), "{line:?}");
        assert!(line.contains("up=     12.5s"), "{line:?}");
        assert!(line.contains(r#"drops={"audio.vad":2}"#), "{line:?}");
        assert!(line.ends_with("asr warm"), "{line:?}");
    }

    #[test]
    fn health_line_never_invents_a_state_it_was_not_told() {
        let line = health_line(&map(&[("service", rmpv::Value::from("jv-ears"))]));
        assert!(line.contains('?'), "unknown state must read as unknown: {line:?}");
        assert!(!line.contains("0.0s"), "a missing uptime must not print as zero: {line:?}");
        assert!(line.contains("drops=-"), "{line:?}");
    }

    #[test]
    fn act_log_line_renders_confirm_and_args() {
        let e: serde_json::Value = serde_json::from_str(
            r#"{"ts":"2026-09-24T10:00:00Z","tool":"window.focus","capability":"observe",
                "outcome":"ok","duration_ms":4.2,"args":{"id":7},
                "confirm":{"granted":true,"answered_by":"voice"}}"#,
        )
        .unwrap();
        let line = act_log_line(&e);
        assert!(line.contains("window.focus"), "{line}");
        assert!(line.contains("confirm=true/voice"), "{line}");
        assert!(line.contains(r#"args={"id":7}"#), "{line}");
    }

    // ------------------------------------------------------- health check

    /// A heartbeat frame in the shape a service really publishes one.
    fn beat(src: &str, state: &str, ts: f64) -> rmpv::Value {
        beat_body(
            src,
            ts,
            1.0,
            1,
            map(&[
                ("service", rmpv::Value::from(src)),
                ("state", rmpv::Value::from(state)),
                ("uptime_s", rmpv::Value::from(12.0)),
                ("period_s", rmpv::Value::from(5.0)),
            ]),
        )
    }

    fn beat_body(src: &str, ts: f64, conf: f64, v: u64, body: rmpv::Value) -> rmpv::Value {
        map(&[
            ("topic", rmpv::Value::from("sys.health")),
            ("ts", rmpv::Value::from(ts)),
            ("seq", rmpv::Value::from(0u64)),
            ("src", rmpv::Value::from(src)),
            ("conf", rmpv::Value::from(conf)),
            ("v", rmpv::Value::from(v)),
            ("body", body),
        ])
    }

    fn checked(frames: &[rmpv::Value], now: f64) -> Vec<Wellbeing> {
        let mut hc = HealthCheck::default();
        for f in frames {
            hc.observe(f);
        }
        hc.report(now)
    }

    fn words(report: &[Wellbeing]) -> Vec<(String, &'static str)> {
        report.iter().map(|w| (w.service.clone(), w.state.word())).collect()
    }

    #[test]
    fn a_machine_where_everyone_says_ok_is_well() {
        let report = checked(&[beat("jarvisd", "ok", 100.0), beat("jv-ears", "ok", 100.5)], 101.0);
        assert_eq!(words(&report), [("jarvisd".into(), "ok"), ("jv-ears".into(), "ok")]);
        assert_eq!(health_check_exit(&report), 0);
        assert!(health_check_footer(&report, 6.0).ends_with("in 6.0s; all well"));
    }

    #[test]
    fn silence_is_not_an_all_clear() {
        let report = checked(&[], 101.0);
        assert!(report.is_empty());
        assert_eq!(health_check_exit(&report), 1, "a bus nobody heartbeats on is not a well machine");
        assert_eq!(health_check_footer(&report, 6.0), "heard from no service in 6.0s");
    }

    #[test]
    fn findings_come_worst_first_and_ties_break_by_name() {
        let report = checked(
            &[
                beat("jv-voice", "ok", 100.0),
                beat("jv-ears", "degraded", 100.0),
                beat("jv-brain", "error", 100.0),
                beat("jv-act", "starting", 100.0),
                beat("jv-context", "degraded", 100.0),
            ],
            101.0,
        );
        assert_eq!(
            words(&report),
            [
                ("jv-brain".into(), "error"),
                ("jv-context".into(), "degraded"),
                ("jv-ears".into(), "degraded"),
                ("jv-act".into(), "starting"),
                ("jv-voice".into(), "ok"),
            ]
        );
        assert_eq!(health_check_exit(&report), 1);
        assert!(health_check_footer(&report, 6.0).contains("5 services"), "{report:?}");
        assert!(health_check_footer(&report, 6.0).ends_with("4 not well"));
    }

    #[test]
    fn a_heartbeat_speaks_for_two_of_its_own_periods_and_no_longer() {
        // period_s is 5, so 10 s is the last moment it still means anything.
        let fresh = checked(&[beat("jv-ears", "ok", 100.0)], 110.0);
        assert_eq!(words(&fresh), [("jv-ears".into(), "ok")]);
        assert_eq!(health_check_exit(&fresh), 0);

        let stale = checked(&[beat("jv-ears", "ok", 100.0)], 110.01);
        assert_eq!(words(&stale), [("jv-ears".into(), "lost")]);
        assert_eq!(health_check_exit(&stale), 1);
    }

    #[test]
    fn a_lost_service_stops_quoting_notes_about_a_moment_that_has_passed() {
        let body = map(&[
            ("service", rmpv::Value::from("jv-brain")),
            ("state", rmpv::Value::from("degraded")),
            ("period_s", rmpv::Value::from(5.0)),
            ("notes", rmpv::Value::from("fell back to CPU")),
        ]);
        let frame = beat_body("jv-brain", 100.0, 1.0, 1, body);
        let now = checked(std::slice::from_ref(&frame), 101.0);
        assert_eq!(now[0].notes, "fell back to CPU");
        let later = checked(std::slice::from_ref(&frame), 200.0);
        assert_eq!(later[0].state, Wellness::Lost);
        assert_eq!(later[0].notes, "", "a lost service has one true thing left to say");
    }

    #[test]
    fn a_heartbeat_this_binary_may_not_read_is_unknown_and_is_reported() {
        let good = map(&[
            ("service", rmpv::Value::from("jv-ears")),
            ("state", rmpv::Value::from("ok")),
            ("period_s", rmpv::Value::from(5.0)),
        ]);
        let cases: Vec<(&str, rmpv::Value)> = vec![
            ("a body from a version we were not written against", beat_body("jv-ears", 100.0, 1.0, 2, good.clone())),
            ("a heartbeat hedging its own confidence", beat_body("jv-ears", 100.0, 0.5, 1, good.clone())),
            (
                "a body naming a different service than published it",
                beat_body(
                    "jv-ears",
                    100.0,
                    1.0,
                    1,
                    map(&[
                        ("service", rmpv::Value::from("jv-voice")),
                        ("state", rmpv::Value::from("ok")),
                        ("period_s", rmpv::Value::from(5.0)),
                    ]),
                ),
            ),
            (
                "no period, so no idea how long to believe it",
                beat_body(
                    "jv-ears",
                    100.0,
                    1.0,
                    1,
                    map(&[("service", rmpv::Value::from("jv-ears")), ("state", rmpv::Value::from("ok"))]),
                ),
            ),
            (
                "a state word outside the frozen enum",
                beat_body(
                    "jv-ears",
                    100.0,
                    1.0,
                    1,
                    map(&[
                        ("service", rmpv::Value::from("jv-ears")),
                        ("state", rmpv::Value::from("fine")),
                        ("period_s", rmpv::Value::from(5.0)),
                    ]),
                ),
            ),
            ("no body at all", beat_body("jv-ears", 100.0, 1.0, 1, rmpv::Value::Nil)),
        ];
        for (why, frame) in cases {
            let report = checked(&[frame], 101.0);
            assert_eq!(words(&report), [("jv-ears".into(), "unknown")], "{why}");
            assert_eq!(report[0].age_s, None, "{why}: an unreadable frame has no age we may print");
            assert_eq!(health_check_exit(&report), 1, "{why}");
        }
    }

    #[test]
    fn a_service_not_yet_up_is_not_yet_well() {
        // The only finding is `starting`. Right after boot that is the whole
        // answer a caller wants — "not ready yet" is not "ready".
        for word in ["starting", "stopping"] {
            let report = checked(&[beat("jarvisd", "ok", 100.0), beat("jv-brain", word, 100.0)], 101.0);
            assert_eq!(words(&report), [("jv-brain".into(), word), ("jarvisd".into(), "ok")]);
            assert_eq!(health_check_exit(&report), 1, "{word} is not ok");
            assert!(health_check_footer(&report, 6.0).ends_with("1 not well"), "{word}");
        }
    }

    #[test]
    fn a_period_of_zero_is_a_body_we_cannot_read_not_a_service_that_went_quiet() {
        // `period_s` is how long we may believe a heartbeat (schema:
        // exclusiveMinimum 0). Zero is not "believe it for no time at all" —
        // it is a body that never said, and calling that `lost` would report
        // a service as having gone quiet when it is talking perfectly well.
        for period in [rmpv::Value::from(0.0), rmpv::Value::from(-5.0)] {
            let frame = beat_body(
                "jv-ears",
                100.0,
                1.0,
                1,
                map(&[
                    ("service", rmpv::Value::from("jv-ears")),
                    ("state", rmpv::Value::from("ok")),
                    ("period_s", period.clone()),
                ]),
            );
            let report = checked(&[frame], 101.0);
            assert_eq!(words(&report), [("jv-ears".into(), "unknown")], "period_s={period:?}");
            assert_eq!(report[0].age_s, None, "period_s={period:?}");
        }
    }

    #[test]
    fn an_unreadable_frame_outranks_a_service_that_admits_it_is_impaired() {
        assert!(Wellness::Unknown.rank() > Wellness::Degraded.rank());
        assert!(Wellness::Lost.rank() > Wellness::Unknown.rank());
        assert!(Wellness::Error.rank() > Wellness::Lost.rank());
        assert_eq!(Wellness::Ok.rank(), 0, "ok is the only state that is not a finding");
    }

    #[test]
    fn the_newest_thing_a_service_said_wins_even_when_it_cannot_be_read() {
        let unreadable = beat_body("jv-ears", 101.0, 1.0, 9, map(&[("service", rmpv::Value::from("jv-ears"))]));
        let report = checked(&[beat("jv-ears", "ok", 100.0), unreadable], 101.5);
        assert_eq!(words(&report), [("jv-ears".into(), "unknown")]);
    }

    #[test]
    fn a_service_that_recovers_is_reported_as_recovered() {
        let report = checked(&[beat("jv-ears", "error", 100.0), beat("jv-ears", "ok", 101.0)], 101.5);
        assert_eq!(words(&report), [("jv-ears".into(), "ok")]);
        assert_eq!(health_check_exit(&report), 0);
    }

    #[test]
    fn a_frame_with_no_src_is_attributed_to_nobody() {
        let mut hc = HealthCheck::default();
        hc.observe(&map(&[("topic", rmpv::Value::from("sys.health"))]));
        hc.observe(&beat_body("", 100.0, 1.0, 1, rmpv::Value::Nil));
        assert!(hc.report(101.0).is_empty(), "a frame we cannot attribute must not invent a service");
    }

    fn brain_with(metrics: &[(&str, rmpv::Value)], ts: f64) -> rmpv::Value {
        beat_body(
            BRAIN,
            ts,
            1.0,
            1,
            map(&[
                ("service", rmpv::Value::from(BRAIN)),
                ("state", rmpv::Value::from("ok")),
                ("period_s", rmpv::Value::from(5.0)),
                ("metrics", map(metrics)),
            ]),
        )
    }

    fn llm_of(frames: &[rmpv::Value], now: f64) -> Option<String> {
        let mut hc = HealthCheck::default();
        for f in frames {
            hc.observe(f);
        }
        hc.llm_line(now, BRAIN)
    }

    #[test]
    fn the_llm_rung_is_read_off_the_brains_own_heartbeat() {
        let frame = brain_with(&[("llm_rung", 4.into()), ("llm_gpu", 0.into())], 100.0);
        assert_eq!(llm_of(&[frame], 101.0).as_deref(), Some("llm rung=4 backend=cpu"));
        let gpu = brain_with(&[("llm_rung", 0.into()), ("llm_gpu", 1.into())], 100.0);
        assert_eq!(llm_of(&[gpu], 101.0).as_deref(), Some("llm rung=0 backend=gpu"));
    }

    #[test]
    fn a_rung_nobody_can_read_is_never_rendered_as_a_gpu() {
        // No brain at all, a brain with no gauges, and a brain whose
        // heartbeat is too old to describe the process running now.
        assert_eq!(llm_of(&[beat("jv-ears", "ok", 100.0)], 101.0), None);
        assert_eq!(llm_of(&[brain_with(&[], 100.0)], 101.0), None);
        assert_eq!(llm_of(&[brain_with(&[("queue", 2.into())], 100.0)], 101.0), None);
        assert_eq!(llm_of(&[brain_with(&[("llm_rung", 4.into()), ("llm_gpu", 1.into())], 100.0)], 200.0), None);
        // Half known is still said, with the unknown half spelled `?`.
        assert_eq!(
            llm_of(&[brain_with(&[("llm_rung", 4.into())], 100.0)], 101.0).as_deref(),
            Some("llm rung=4 backend=?")
        );
    }

    /// A brain heartbeat carrying the rung AND the first-say gauge — the
    /// shape jv-brain actually publishes once a divisible turn has run.
    fn brain_saying(count: i64, ms: f64, ts: f64) -> rmpv::Value {
        brain_with(
            &[
                ("llm_rung", 4.into()),
                ("llm_gpu", 1.into()),
                (BRAIN_FIRST_SAY_METRIC, ms.into()),
                (BRAIN_FIRST_SAYS_METRIC, (count as f64).into()),
            ],
            ts,
        )
    }

    #[test]
    fn a_turn_the_window_watched_happen_is_dated_exactly() {
        // The count rose between two heartbeats, so the turn IS the frame
        // that raised it and its age is a measurement, not a guess.
        let line = llm_of(&[brain_saying(3, 900.0, 100.0), brain_saying(4, 412.0, 103.0)], 104.5);
        assert_eq!(line.as_deref(), Some("llm rung=4 backend=gpu first_say=412ms turn_age=1.5s"));
    }

    #[test]
    fn a_gauge_that_never_moved_is_only_ever_at_least_that_old() {
        // jv-brain re-states the same number on every periodic beat for the
        // rest of the process's life, so a count that did not move says the
        // turn predates the first heartbeat we read — and nothing more. A
        // brain idle since breakfast must not read as one that just took
        // 412 ms.
        let line = llm_of(&[brain_saying(4, 412.0, 100.0), brain_saying(4, 412.0, 105.0)], 106.0);
        assert_eq!(line.as_deref(), Some("llm rung=4 backend=gpu first_say=412ms turn_age>=6.0s"));
    }

    #[test]
    fn the_first_count_a_window_sees_is_never_treated_as_fresh() {
        // One heartbeat is one reading. The gauge on it may describe a turn
        // from long before `--check` connected, and there is no second
        // count to tell those apart.
        let line = llm_of(&[brain_saying(9, 412.0, 100.0)], 101.0);
        assert_eq!(line.as_deref(), Some("llm rung=4 backend=gpu first_say=412ms turn_age>=1.0s"));
    }

    #[test]
    fn a_brain_that_restarted_mid_window_stops_dating_the_turn() {
        // The counter starts at 1 again, so a count that went BACKWARDS is a
        // new process, not a new turn. The window starts over on it rather
        // than reporting a turn it never watched happen as fresh.
        let line = llm_of(
            &[brain_saying(9, 900.0, 100.0), brain_saying(2, 412.0, 103.0)],
            104.5,
        );
        assert_eq!(line.as_deref(), Some("llm rung=4 backend=gpu first_say=412ms turn_age>=1.5s"));
    }

    #[test]
    fn a_heartbeat_that_stopped_carrying_the_gauge_takes_the_number_with_it() {
        // The newest thing a service said wins here exactly as it does in
        // the report: a beat with no gauge says nothing about a turn, and
        // quoting the superseded frame would be this reader inventing a
        // measurement that is no longer on the wire.
        let quiet = brain_with(&[("llm_rung", 4.into()), ("llm_gpu", 1.into())], 103.0);
        assert_eq!(
            llm_of(&[brain_saying(4, 412.0, 100.0), quiet], 104.0).as_deref(),
            Some("llm rung=4 backend=gpu")
        );
    }

    #[test]
    fn a_gauge_the_reader_may_not_believe_never_reaches_the_line() {
        // One spot-check per half of the pair; `brain_first_say` owns the
        // full refusal list and is tested against it above.
        let fractional = brain_with(
            &[
                ("llm_rung", 4.into()),
                ("llm_gpu", 1.into()),
                (BRAIN_FIRST_SAY_METRIC, 412.0.into()),
                (BRAIN_FIRST_SAYS_METRIC, 2.5.into()),
            ],
            100.0,
        );
        assert_eq!(llm_of(&[fractional], 101.0).as_deref(), Some("llm rung=4 backend=gpu"));
        let negative = brain_with(
            &[
                ("llm_rung", 4.into()),
                ("llm_gpu", 1.into()),
                (BRAIN_FIRST_SAY_METRIC, (-1.0).into()),
                (BRAIN_FIRST_SAYS_METRIC, 2.0.into()),
            ],
            100.0,
        );
        assert_eq!(llm_of(&[negative], 101.0).as_deref(), Some("llm rung=4 backend=gpu"));
    }

    #[test]
    fn the_gauge_is_worth_a_line_on_its_own_and_a_lost_brain_is_worth_none() {
        // A brain that has not said which rung it picked has still said how
        // long its last divisible turn took, and that number answers a
        // question by itself.
        let only_say = brain_with(
            &[
                (BRAIN_FIRST_SAY_METRIC, 412.0.into()),
                (BRAIN_FIRST_SAYS_METRIC, 2.0.into()),
            ],
            100.0,
        );
        assert_eq!(
            llm_of(&[only_say.clone()], 101.0).as_deref(),
            Some("llm rung=? backend=? first_say=412ms turn_age>=1.0s")
        );
        // ... but only while the heartbeat still speaks for the process
        // running now. A gauge outliving its heartbeat is the stalest
        // reading there is.
        assert_eq!(llm_of(&[only_say], 200.0), None);
    }

    #[test]
    fn a_wellbeing_line_never_prints_a_missing_age_as_zero() {
        let line = wellbeing_line(&Wellbeing {
            service: "jv-ears".into(),
            state: Wellness::Unknown,
            notes: String::new(),
            age_s: None,
        });
        assert!(line.starts_with("jv-ears      unknown  "), "{line:?}");
        assert!(line.contains('?'), "{line:?}");
        assert!(!line.contains("0.0"), "{line:?}");
        let aged = wellbeing_line(&Wellbeing {
            service: "jv-brain".into(),
            state: Wellness::Degraded,
            notes: "fell back to CPU".into(),
            age_s: Some(1.25),
        });
        assert!(aged.contains("age=    1.2s"), "{aged:?}");
        assert!(aged.ends_with("fell back to CPU"), "{aged:?}");
    }

    #[test]
    fn act_log_line_tolerates_a_truncated_entry() {
        let e: serde_json::Value = serde_json::from_str(r#"{"tool":"fs.read"}"#).unwrap();
        let line = act_log_line(&e);
        assert!(line.contains("fs.read"), "{line}");
        assert!(line.contains('?'), "{line}");
    }
}
