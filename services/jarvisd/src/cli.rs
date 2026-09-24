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

    /// The one number that explains why Jarvis got slow, or None when the
    /// brain has not said. Never rendered as "gpu" on a guess: a rung we
    /// cannot read is not a rung we may reassure anyone about.
    pub fn llm_line(&self, now: f64, brain: &str) -> Option<String> {
        let t = self.latest.get(brain)?.as_ref()?;
        if Self::lost(t, now) {
            return None;
        }
        let metrics = t.metrics.as_ref()?;
        let rung = get_f64(metrics, "llm_rung");
        let backend = get_f64(metrics, "llm_gpu").map(|g| if g == 1.0 { "gpu" } else { "cpu" });
        if rung.is_none() && backend.is_none() {
            return None;
        }
        let rung = rung.map(|r| format!("{r:.0}")).unwrap_or_else(|| "?".into());
        Some(format!("llm rung={rung} backend={}", backend.unwrap_or("?")))
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
