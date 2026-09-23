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

use common::{body, start, TestBus};
use jarvisd::broker::{BusAddr, Config};
use jarvisd::client::BusClient;
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
    std::process::Command::new(env!("CARGO_BIN_EXE_jv"))
        .arg("--bus")
        .arg(bus)
        .args(args)
        .stdout(std::process::Stdio::piped())
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
