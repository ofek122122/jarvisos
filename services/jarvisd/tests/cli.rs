//! End-to-end tests for the `jv` debug CLI: the real binary, as a child
//! process, against a real broker on a real socket.
//!
//! What these pin down is the part `jarvisd::cli`'s unit tests cannot — that
//! the stop bounds are honoured by an actual process and that its exit status
//! is usable from a script. A CLI that only ever streams forever cannot be
//! asserted on at all, which is why it had no tests before.
//!
//! **On synchronising with the child.** Whether the child has finished
//! subscribing is not observable from here, and sleeping a guessed amount then
//! publishing once is exactly the flake that would make an unattended gate
//! useless. So every test that needs traffic re-publishes its frames on a tick
//! for the whole window and asserts something that is TRUE UNDER REPEATS:
//! `-n 1` prints one line however many frames arrive, and an end-to-end report
//! fires once per utterance by construction.

mod common;

use common::{body, next_frame_of, start, subscribe_live, TestBus};
use jarvisd::broker::{BusAddr, Config};
use jarvisd::client::BusClient;
use jarvisd::schema::{ActionConfirm, ActionConfirmAnsweredBy, ActionConfirmKind};
use std::io::Read;
use std::time::Duration;

struct Out {
    code: i32,
    stdout: String,
    stderr: String,
}

impl Out {
    fn lines(&self) -> Vec<&str> {
        self.stdout.lines().filter(|l| !l.is_empty()).collect()
    }
}

fn spawn_jv(bus: &str, args: &[&str]) -> std::process::Child {
    spawn_jv_env(bus, args, &[])
}

fn spawn_jv_env(bus: &str, args: &[&str], env: &[(&str, &str)]) -> std::process::Child {
    let mut cmd = std::process::Command::new(env!("CARGO_BIN_EXE_jv"));
    cmd.arg("--bus").arg(bus).args(args);
    for (k, v) in env {
        cmd.env(k, v);
    }
    cmd.stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .expect("spawn jv")
}

/// Wait for jv to exit, polling so this test's runtime keeps serving the
/// broker. Panics rather than hanging if the CLI overruns the bound it was
/// given — "it stops when told" is the thing under test.
async fn wait_out(mut child: std::process::Child, limit_s: f64) -> Out {
    let t0 = tokio::time::Instant::now();
    loop {
        if let Some(st) = child.try_wait().expect("try_wait") {
            let mut stdout = String::new();
            let mut stderr = String::new();
            child.stdout.take().unwrap().read_to_string(&mut stdout).unwrap();
            child.stderr.take().unwrap().read_to_string(&mut stderr).unwrap();
            return Out { code: st.code().unwrap_or(-1), stdout, stderr };
        }
        if t0.elapsed().as_secs_f64() > limit_s {
            let _ = child.kill();
            panic!("jv did not exit within {limit_s}s — its stop bound did not hold");
        }
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
}

/// Publish `frames` in order, every `every_ms`, until aborted. See the module
/// note on why this repeats.
fn pump(bus: &TestBus, frames: Vec<(&'static str, rmpv::Value)>, every_ms: u64) -> tokio::task::JoinHandle<()> {
    let addr: BusAddr = bus.addr.clone();
    tokio::spawn(async move {
        let mut c = BusClient::connect(&addr, "pump").await.expect("pump connect");
        loop {
            for (topic, b) in &frames {
                if c.publish(topic, 1.0, 1, b.clone()).await.is_err() {
                    return;
                }
            }
            tokio::time::sleep(Duration::from_millis(every_ms)).await;
        }
    })
}

#[tokio::test]
async fn sub_with_count_one_prints_exactly_one_frame_and_exits_clean() {
    let bus = start(Config::default()).await;
    let p = pump(&bus, vec![("jv.test", body(&[("n", 1.into())]))], 50);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["sub", "jv.test", "-n", "1", "--for", "5"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 1, "-n 1 must print exactly one frame, got {lines:?}");
    let f: serde_json::Value = serde_json::from_str(lines[0]).expect("a JSON line");
    assert_eq!(f["topic"], "jv.test");
    assert_eq!(f["src"], "pump");
}

#[tokio::test]
async fn an_unmet_count_exits_non_zero() {
    let bus = start(Config::default()).await;
    // Nothing is published, so --for wins and the count is never met.
    let out = wait_out(spawn_jv(&bus.bus_arg(), &["sub", "jv.quiet", "-n", "2", "--for", "0.4"]), 8.0).await;
    assert_eq!(out.code, 1, "asking for 2 frames and getting 0 is a failure; stderr: {}", out.stderr);
    assert!(out.lines().is_empty(), "{:?}", out.lines());
}

#[tokio::test]
async fn for_bounds_an_idle_stream_and_that_is_a_success() {
    let bus = start(Config::default()).await;
    let out = wait_out(spawn_jv(&bus.bus_arg(), &["sub", "jv.quiet", "--for", "0.4"]), 8.0).await;
    assert_eq!(out.code, 0, "no --count means any stop is fine; stderr: {}", out.stderr);
    assert!(out.lines().is_empty(), "{:?}", out.lines());
}

#[tokio::test]
async fn a_bus_that_is_not_there_is_an_error_not_a_silent_success() {
    let out = wait_out(
        spawn_jv("/nonexistent/jarvis-ralph-test/bus.sock", &["sub", "jv.test", "-n", "1", "--for", "1"]),
        8.0,
    )
    .await;
    assert_ne!(out.code, 0);
    assert!(!out.stderr.is_empty(), "a failure to connect must say so");
}

#[tokio::test]
async fn tap_latency_prints_a_percentile_summary_when_it_stops() {
    let bus = start(Config::default()).await;
    let p = pump(&bus, vec![("jv.test", body(&[("n", 1.into())]))], 50);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "-n", "3", "--for", "5"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    assert!(out.stdout.contains("--- hop latency: 3 frames, 1 topics"), "{}", out.stdout);
    assert!(out.stdout.contains("jv.test"), "{}", out.stdout);
    // Three per-frame lines, a header, a column header and one row.
    assert_eq!(out.lines().len(), 6, "{:?}", out.lines());
    // No utterances were tracked, so there is no end-to-end section to invent.
    assert!(!out.stdout.contains("end-to-end"), "{}", out.stdout);
}

#[tokio::test]
async fn health_reads_the_brokers_own_heartbeat() {
    let bus = start(Config { health_period: Duration::from_millis(50), ..Config::default() }).await;
    let out = wait_out(spawn_jv(&bus.bus_arg(), &["health", "-n", "1", "--for", "5"]), 8.0).await;

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 1, "{lines:?}");
    assert!(lines[0].starts_with("jarvisd "), "{:?}", lines[0]);
    assert!(lines[0].contains(" ok "), "{:?}", lines[0]);
    assert!(lines[0].contains("up="), "{:?}", lines[0]);
    // The broker reports no drops on an idle bus, and "no drops" must read as
    // absent, not as a fabricated zero.
    assert!(lines[0].contains("drops=-"), "{:?}", lines[0]);
}

#[tokio::test]
async fn a_streamed_reply_reports_end_to_end_exactly_once() {
    let bus = start(Config::default()).await;
    // One utterance, then three reply sentences — what jv-brain's streaming
    // reply actually looks like on the bus.
    let utt = "utt-ralph-1";
    let say = body(&[("text", "hi".into()), ("in_reply_to_utterance", utt.into())]);
    let p = pump(
        &bus,
        vec![
            ("audio.vad", body(&[("kind", "speech_start".into()), ("utterance_id", utt.into())])),
            ("speech.say", say.clone()),
            ("speech.say", say.clone()),
            ("speech.say", say),
        ],
        60,
    );

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--for", "2"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let reports: Vec<&str> = out.stdout.lines().filter(|l| l.starts_with(">>> end-to-end")).collect();
    assert_eq!(
        reports.len(),
        1,
        "a streamed reply is many speech.say frames for ONE utterance; only the \
         first is time-to-first-word. got {reports:?}"
    );
    assert!(reports[0].contains(utt), "{:?}", reports[0]);
    assert!(reports[0].contains("(VAD start -> first speech.say)"), "{:?}", reports[0]);
    // Cross-process CLOCK_MONOTONIC: the pump's ts and jv's now are comparable,
    // so the number must be a small positive latency, not a negative or a
    // wall-clock-sized nonsense.
    let ms: f64 = reports[0]
        .split("ms ")
        .next()
        .and_then(|s| s.rsplit(": ").next())
        .and_then(|s| s.parse().ok())
        .unwrap_or_else(|| panic!("no latency in {:?}", reports[0]));
    assert!((0.0..10_000.0).contains(&ms), "implausible end-to-end {ms}ms in {:?}", reports[0]);
}

/// Ctrl-C is how an interactive `jv tap --latency` asks for its summary, so it
/// has to be a clean stop rather than a killed process.
#[cfg(unix)]
#[tokio::test]
async fn ctrl_c_stops_cleanly_and_still_prints_the_summary() {
    let bus = start(Config::default()).await;
    let p = pump(&bus, vec![("jv.test", body(&[("n", 1.into())]))], 30);

    // --for 30 so only the signal can end this; the 8 s wait_out bound is the
    // assertion that it did.
    let child = spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "30"]);
    let pid = child.id() as i32;
    tokio::time::sleep(Duration::from_millis(500)).await;
    // Safety: SIGINT to a child we spawned and have not reaped.
    assert_eq!(unsafe { libc::kill(pid, libc::SIGINT) }, 0, "kill -INT failed");

    let out = wait_out(child, 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "an interrupted open-ended tap is a success; stderr: {}", out.stderr);
    assert!(out.stdout.contains("--- hop latency:"), "summary missing:\n{}", out.stdout);
    assert!(out.stdout.contains("jv.test"), "{}", out.stdout);
}


// ---------------------------------------------------------------- act-log
//
// `jv act-log` is the only way a human reads back what jv-act — the one service
// allowed to change the machine — actually did. It had no test at all: not that
// it can read the file jv-act writes, not that `--tail` shows the newest
// entries, not that a missing log is distinguishable from an empty one.

/// One audit line in the shape jv-act writes it. The field set mirrors
/// `AuditEntry` in `services/jv-act/src/audit.rs` (human-review-only, so it
/// cannot be imported from here — and jv-act depends on this crate, so the
/// dependency could not go the other way either).
fn audit_entry(tool: &str, outcome: &str, confirm: Option<(bool, &str)>) -> String {
    let mut e = serde_json::json!({
        "ts": "2026-09-24T10:00:00Z",
        "ts_mono": 12.5,
        "request_id": "req-1",
        "tool": tool,
        "args": {"path": "/tmp/x"},
        "capability": "destructive",
        "outcome": outcome,
        "duration_ms": 7.0,
    });
    if let Some((granted, by)) = confirm {
        e["confirm"] = serde_json::json!({"granted": granted, "answered_by": by});
    }
    e.to_string()
}

/// An audit file, and the `--bus` argument for a command that needs no bus.
fn audit_file(lines: &[String]) -> (tempfile::TempDir, std::path::PathBuf) {
    let tmp = tempfile::tempdir().unwrap();
    let path = tmp.path().join("audit.jsonl");
    let mut text = String::new();
    for l in lines {
        text.push_str(l);
        text.push('\n');
    }
    std::fs::write(&path, text).unwrap();
    (tmp, path)
}

#[tokio::test]
async fn act_log_renders_every_field_of_a_real_entry_oldest_first() {
    let (_tmp, path) = audit_file(&[
        audit_entry("window.focus", "ok", None),
        audit_entry("fs.trash", "ok", Some((true, "voice"))),
    ]);
    let out = wait_out(
        spawn_jv_env("/nonexistent/no-bus-needed.sock", &["act-log"], &[("JARVIS_ACT_AUDIT", path.to_str().unwrap())]),
        8.0,
    )
    .await;

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 2, "{lines:?}");
    assert!(lines[0].contains("window.focus"), "{:?}", lines[0]);
    assert!(lines[1].contains("fs.trash"), "newest last: {:?}", lines[1]);
    assert!(lines[1].contains("confirm=true/voice"), "{:?}", lines[1]);
    assert!(lines[1].contains("destructive"), "{:?}", lines[1]);
    assert!(lines[1].contains(r#"args={"path":"/tmp/x"}"#), "{:?}", lines[1]);
    // A complete entry must render with nothing unknown in it: a '?' here means
    // jv-act writes a field under a name this reader does not look for.
    assert!(!lines[1].contains('?'), "a full jv-act entry rendered as unknown: {:?}", lines[1]);
    assert!(out.stderr.is_empty(), "a clean log must not warn: {}", out.stderr);
}

#[tokio::test]
async fn act_log_tail_shows_the_newest_entries() {
    let (_tmp, path) = audit_file(&[
        audit_entry("a.one", "ok", None),
        audit_entry("a.two", "denied", None),
        audit_entry("a.three", "ok", None),
    ]);
    let out = wait_out(
        spawn_jv_env(
            "/nonexistent/no-bus-needed.sock",
            &["act-log", "--tail", "2"],
            &[("JARVIS_ACT_AUDIT", path.to_str().unwrap())],
        ),
        8.0,
    )
    .await;

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 2, "{lines:?}");
    assert!(lines[0].contains("a.two") && lines[0].contains("denied"), "{:?}", lines[0]);
    assert!(lines[1].contains("a.three"), "{:?}", lines[1]);
}

/// "jv-act has never acted" and "I cannot find the record" must not look the
/// same. An empty exit-0 listing for a missing file would be a lie about the
/// most safety-relevant file on the machine.
#[tokio::test]
async fn a_missing_audit_log_is_an_error_not_an_empty_history() {
    let tmp = tempfile::tempdir().unwrap();
    let missing = tmp.path().join("nope").join("audit.jsonl");
    let out = wait_out(
        spawn_jv_env(
            "/nonexistent/no-bus-needed.sock",
            &["act-log"],
            &[("JARVIS_ACT_AUDIT", missing.to_str().unwrap())],
        ),
        8.0,
    )
    .await;

    assert_ne!(out.code, 0, "stdout: {}", out.stdout);
    assert!(out.stdout.is_empty(), "{}", out.stdout);
    assert!(out.stderr.contains("no audit log at"), "{}", out.stderr);
    assert!(out.stderr.contains("audit.jsonl"), "say WHICH file: {}", out.stderr);
}

/// The entry most likely to be half-written is the last one — the action that
/// was running when the machine went down. Dropping it silently turns a torn
/// record into a clean one.
#[tokio::test]
async fn a_torn_audit_line_is_reported_and_fails_the_command() {
    let (_tmp, path) = audit_file(&[
        audit_entry("a.one", "ok", None),
        r#"{"ts":"2026-09-24T10:00:01Z","tool":"fs.tr"#.to_string(),
    ]);
    let out = wait_out(
        spawn_jv_env("/nonexistent/no-bus-needed.sock", &["act-log"], &[("JARVIS_ACT_AUDIT", path.to_str().unwrap())]),
        8.0,
    )
    .await;

    assert_eq!(out.code, 1, "a hole in the audit trail must be scriptable: {}", out.stdout);
    let lines = out.lines();
    assert_eq!(lines.len(), 2, "the readable entry is still printed: {lines:?}");
    assert!(lines[0].contains("a.one"), "{:?}", lines[0]);
    assert!(lines[1].starts_with("!! unreadable audit line 2"), "{:?}", lines[1]);
    assert!(out.stderr.contains("could not be read"), "{}", out.stderr);
}

// ---------------------------------------------------------------- confirm
//
// `jv confirm` is the one CLI path that can cause a real action to happen —
// answering a destructive tool's confirmation. Nothing asserted the frame it
// publishes is the frame jv-act resolves on, and every field of it matters:
// jv-act ignores an answer whose kind is not "answer", whose granted is not a
// bool, or whose answered_by is not exactly "cli" (it echoes its own
// voice/timeout answers on this same topic, and must not re-resolve them).

#[tokio::test]
async fn confirm_publishes_the_answer_jv_act_resolves() {
    let bus = start(Config::default()).await;
    let mut watch = BusClient::connect(&bus.addr, "watch").await.unwrap();
    subscribe_live(&bus, &mut watch, &["action.confirm"]).await;

    for (spelling, granted) in [("yes", true), ("y", true), ("no", false), ("n", false)] {
        let rid = format!("req-{spelling}");
        let out = wait_out(spawn_jv(&bus.bus_arg(), &["confirm", &rid, spelling]), 8.0).await;
        assert_eq!(out.code, 0, "'{spelling}' stderr: {}", out.stderr);
        assert!(
            out.stdout.contains(&format!("answer sent: {rid} -> {}", if granted { "yes" } else { "no" })),
            "{}",
            out.stdout
        );

        let frame = next_frame_of(&mut watch, "action.confirm", 5.0)
            .await
            .unwrap_or_else(|| panic!("'{spelling}' published no action.confirm frame"));

        // Envelope: invariant 4 — ts, seq, src, conf on every frame. The schema
        // pins conf = 1.0 for this topic: a confirmation is not a guess.
        assert_eq!(jarvisd::cli::get_str(&frame, "src").as_deref(), Some("jv-cli"));
        assert_eq!(jarvisd::cli::get_f64(&frame, "conf"), Some(1.0));
        assert_eq!(jarvisd::cli::get_f64(&frame, "v"), Some(1.0), "body schema v");
        assert!(jarvisd::cli::get_f64(&frame, "ts").is_some_and(|t| t > 0.0));

        // Body, through the FROZEN schema binding (deny_unknown_fields), so a
        // field the CLI invents or misspells fails here rather than being
        // ignored in silence by jv-act.
        let body = jarvisd::cli::get(&frame, "body").cloned().expect("body");
        let ac: ActionConfirm =
            jarvisd::broker::from_value_named(&body).expect("action.confirm v1 must accept it");
        assert_eq!(ac.kind, ActionConfirmKind::Answer);
        assert_eq!(ac.request_id, rid);
        assert_eq!(ac.granted, Some(granted));
        assert_eq!(ac.answered_by, Some(ActionConfirmAnsweredBy::Cli), "jv-act acts only on answered_by=cli");
        // request-only fields stay absent on an answer.
        assert_eq!(ac.tool, None);
        assert_eq!(ac.summary, None);
        assert_eq!(ac.window_s, None);
    }
}

/// An answer nobody can read must not become a grant — and must not become a
/// denial either. It must not reach the bus at all.
#[tokio::test]
async fn confirm_refuses_an_unreadable_answer_and_publishes_nothing() {
    let bus = start(Config::default()).await;
    let mut watch = BusClient::connect(&bus.addr, "watch").await.unwrap();
    subscribe_live(&bus, &mut watch, &["action.confirm"]).await;

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["confirm", "req-9", "maybe"]), 8.0).await;
    assert_ne!(out.code, 0, "stdout: {}", out.stdout);
    assert!(out.stderr.contains("yes or no"), "{}", out.stderr);
    assert!(out.stdout.is_empty(), "{}", out.stdout);
    assert!(
        next_frame_of(&mut watch, "action.confirm", 0.5).await.is_none(),
        "an unparsed answer must never reach the bus"
    );
}
