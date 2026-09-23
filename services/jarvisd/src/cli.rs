//! The pure core of the `jv` debug CLI — latency accounting, utterance
//! tracking, line formatting and exit-status policy.
//!
//! "This CLI is how we debug everything forever", so it is worth testing. All
//! of it lives here rather than in `bin/jv.rs` because an integration test can
//! only observe the binary's stdout; these pieces are where the reasoning is,
//! and they are cheap to pin down directly. `bin/jv.rs` keeps only argument
//! parsing and the async stream loop.

use std::collections::{HashMap, VecDeque};

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

/// Per-topic hop latency (`ts` on the frame -> now in this process) plus the
/// end-to-end numbers, accumulated so `jv tap --latency` can print a summary
/// instead of only a firehose. Invariant 5 says measure, don't assume; a
/// scrolling column of per-frame numbers is not a measurement.
#[derive(Default)]
pub struct HopStats {
    per_topic: HashMap<String, Vec<f64>>,
    e2e: Vec<f64>,
}

impl HopStats {
    pub fn hop(&mut self, topic: &str, ms: f64) {
        self.per_topic.entry(topic.to_string()).or_default().push(ms);
    }

    pub fn e2e(&mut self, ms: f64) {
        self.e2e.push(ms);
    }

    pub fn is_empty(&self) -> bool {
        self.per_topic.is_empty() && self.e2e.is_empty()
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
        let mut out = format!("--- hop latency: {frames} frames, {} topics\n", rows.len());
        out.push_str(&format!("{:<22} {:>5} {:>10} {:>10} {:>10}\n", "topic", "n", "p50", "p95", "max"));
        for (topic, n, p50, p95, max) in &rows {
            out.push_str(&format!("{topic:<22} {n:>5} {p50:>8.2}ms {p95:>8.2}ms {max:>8.2}ms\n"));
        }
        if !self.e2e.is_empty() {
            let mut s = self.e2e.clone();
            s.sort_by(f64::total_cmp);
            out.push_str(&format!(
                "--- end-to-end (VAD start -> first speech.say): n={} p50={:.0}ms p95={:.0}ms max={:.0}ms\n",
                s.len(),
                percentile(&s, 50.0),
                percentile(&s, 95.0),
                percentile(&s, 100.0),
            ));
        }
        out
    }
}

/// Tracks when each input utterance was first heard so a later `speech.say`
/// can be reported as one end-to-end latency.
///
/// Two things this is careful about:
///
/// 1. **Report once per utterance.** jv-brain streams a reply sentence by
///    sentence, so one utterance produces several `speech.say` frames. Only
///    the first is the latency that matters (time to first word, the Phase 1
///    budget); printing a bigger number for every later sentence reads as
///    latency getting worse and is simply the reply being long.
/// 2. **Bounded.** `jv tap` is meant to be left running for hours, so the map
///    cannot grow one entry per utterance forever.
pub struct Utterances {
    first_seen: HashMap<String, f64>,
    reported: HashMap<String, bool>,
    order: VecDeque<String>,
    cap: usize,
}

impl Utterances {
    pub fn with_capacity(cap: usize) -> Self {
        Self {
            first_seen: HashMap::new(),
            reported: HashMap::new(),
            order: VecDeque::new(),
            cap: cap.max(1),
        }
    }

    /// Note that utterance `id` existed at `ts`. Keeps the EARLIEST ts seen,
    /// not the first one delivered: the frames that carry an utterance_id
    /// (`audio.vad`, partial and final `audio.transcript`) need not arrive in
    /// ts order, and the number we want is when the speech started.
    pub fn saw(&mut self, id: &str, ts: f64) {
        match self.first_seen.get_mut(id) {
            Some(t0) => {
                if ts < *t0 {
                    *t0 = ts;
                }
            }
            None => {
                self.first_seen.insert(id.to_string(), ts);
                self.reported.insert(id.to_string(), false);
                self.order.push_back(id.to_string());
                while self.order.len() > self.cap {
                    if let Some(old) = self.order.pop_front() {
                        self.first_seen.remove(&old);
                        self.reported.remove(&old);
                    }
                }
            }
        }
    }

    /// ms from the start of `id` to `now`, but only the FIRST time it is
    /// asked for a given utterance. None if unknown, already reported, or
    /// evicted.
    pub fn first_reply_ms(&mut self, id: &str, now: f64) -> Option<f64> {
        let t0 = *self.first_seen.get(id)?;
        let reported = self.reported.get_mut(id)?;
        if *reported {
            return None;
        }
        *reported = true;
        Some((now - t0) * 1e3)
    }

    pub fn len(&self) -> usize {
        self.first_seen.len()
    }

    pub fn is_empty(&self) -> bool {
        self.first_seen.is_empty()
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

#[cfg(test)]
mod tests {
    use super::*;

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
        // No end-to-end section when nothing was end-to-end.
        assert!(!out.contains("end-to-end"), "{out}");
    }

    #[test]
    fn hop_summary_of_nothing_is_nothing() {
        assert!(HopStats::default().is_empty());
        assert_eq!(HopStats::default().summary(), "");
    }

    #[test]
    fn hop_summary_reports_end_to_end_when_present() {
        let mut s = HopStats::default();
        s.hop("speech.say", 0.4);
        s.e2e(1800.0);
        s.e2e(2400.0);
        let out = s.summary();
        assert!(out.contains("end-to-end (VAD start -> first speech.say): n=2"), "{out}");
        assert!(out.contains("p50=1800ms"), "{out}");
        assert!(out.contains("max=2400ms"), "{out}");
    }

    #[test]
    fn utterance_start_is_the_earliest_ts_not_the_first_frame() {
        let mut u = Utterances::with_capacity(8);
        // A partial transcript (ts 10.5) can be routed ahead of the vad
        // speech_start (ts 10.0) it belongs to; the start is 10.0 either way.
        u.saw("utt-1", 10.5);
        u.saw("utt-1", 10.0);
        u.saw("utt-1", 11.0);
        assert_eq!(u.first_reply_ms("utt-1", 12.0), Some(2000.0));
    }

    #[test]
    fn end_to_end_is_reported_once_per_utterance() {
        let mut u = Utterances::with_capacity(8);
        u.saw("utt-1", 100.0);
        // A streamed reply is several speech.say frames for ONE utterance.
        assert_eq!(u.first_reply_ms("utt-1", 101.0), Some(1000.0));
        assert_eq!(u.first_reply_ms("utt-1", 103.0), None);
        assert_eq!(u.first_reply_ms("utt-1", 106.0), None);
        // An utterance we never heard start has no latency to report.
        assert_eq!(u.first_reply_ms("never-seen", 106.0), None);
    }

    #[test]
    fn utterances_are_bounded_and_evict_oldest_first() {
        let mut u = Utterances::with_capacity(3);
        for i in 0..10 {
            u.saw(&format!("utt-{i}"), i as f64);
        }
        assert_eq!(u.len(), 3, "a tap left running for hours must not grow");
        assert_eq!(u.first_reply_ms("utt-0", 100.0), None, "oldest evicted");
        assert_eq!(u.first_reply_ms("utt-9", 100.0), Some((100.0 - 9.0) * 1e3));
    }

    #[test]
    fn utterances_capacity_zero_still_holds_one() {
        let mut u = Utterances::with_capacity(0);
        u.saw("utt-1", 1.0);
        assert_eq!(u.first_reply_ms("utt-1", 2.0), Some(1000.0));
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

    #[test]
    fn act_log_line_tolerates_a_truncated_entry() {
        let e: serde_json::Value = serde_json::from_str(r#"{"tool":"fs.read"}"#).unwrap();
        let line = act_log_line(&e);
        assert!(line.contains("fs.read"), "{line}");
        assert!(line.contains('?'), "{line}");
    }
}
