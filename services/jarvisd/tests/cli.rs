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
    // No utterances were tracked, so there is no turn table to invent.
    assert!(!out.stdout.contains("turn latency"), "{}", out.stdout);
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

// ------------------------------------------------------------- health --check

/// Publish `frames` as `src`, every `every_ms`, until aborted. `pump` cannot
/// serve here: a `sys.health` body naming a service other than the one the
/// broker saw publish it is exactly what `--check` refuses to read.
fn pump_as(
    bus: &TestBus,
    src: &'static str,
    frames: Vec<(&'static str, rmpv::Value)>,
    every_ms: u64,
) -> tokio::task::JoinHandle<()> {
    let addr: BusAddr = bus.addr.clone();
    tokio::spawn(async move {
        let mut c = BusClient::connect(&addr, src).await.expect("pump connect");
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

fn heartbeat(service: &str, state: &str, notes: Option<&str>) -> rmpv::Value {
    let mut pairs: Vec<(&str, rmpv::Value)> = vec![
        ("service", service.into()),
        ("state", state.into()),
        ("uptime_s", 12.0.into()),
        ("period_s", 5.0.into()),
    ];
    if let Some(n) = notes {
        pairs.push(("notes", n.into()));
    }
    body(&pairs)
}

/// A broker whose own heartbeat will not land inside a short window — the
/// only way to ask what `--check` says about a bus nobody is heartbeating on.
fn silent_broker() -> Config {
    Config { health_period: Duration::from_secs(3600), ..Config::default() }
}

#[tokio::test]
async fn health_check_reports_the_brokers_own_heartbeat_and_exits_clean() {
    let bus = start(Config { health_period: Duration::from_millis(50), ..Config::default() }).await;
    let out = wait_out(spawn_jv(&bus.bus_arg(), &["health", "--check", "--for", "0.6"]), 8.0).await;

    assert_eq!(out.code, 0, "a machine whose only service says ok is well; stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 2, "one service and the footer: {lines:?}");
    assert!(lines[0].starts_with("jarvisd      ok    "), "{:?}", lines[0]);
    assert!(lines[0].contains("age="), "{:?}", lines[0]);
    assert_eq!(lines[1], "heard from 1 service in 0.6s; all well");
}

#[tokio::test]
async fn health_check_says_a_silent_bus_is_not_a_well_machine() {
    let bus = start(silent_broker()).await;
    let out = wait_out(spawn_jv(&bus.bus_arg(), &["health", "--check", "--for", "0.4"]), 8.0).await;

    assert_eq!(out.code, 1, "silence is not an all-clear; stderr: {}", out.stderr);
    assert_eq!(out.lines(), ["heard from no service in 0.4s"]);
}

#[tokio::test]
async fn health_check_puts_the_worst_finding_first_and_fails() {
    let bus = start(silent_broker()).await;
    let ears = pump_as(&bus, "jv-ears", vec![("sys.health", heartbeat("jv-ears", "ok", None))], 50);
    let brain = pump_as(
        &bus,
        "jv-brain",
        vec![("sys.health", heartbeat("jv-brain", "degraded", Some("fell back to CPU")))],
        50,
    );

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["health", "--check", "--for", "0.6"]), 8.0).await;
    ears.abort();
    brain.abort();

    assert_eq!(out.code, 1, "one impaired service is not a well machine; stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 3, "{lines:?}");
    assert!(lines[0].starts_with("jv-brain     degraded "), "{:?}", lines[0]);
    assert!(lines[0].ends_with("fell back to CPU"), "{:?}", lines[0]);
    assert!(lines[1].starts_with("jv-ears      ok "), "{:?}", lines[1]);
    assert_eq!(lines[2], "heard from 2 services in 0.6s; 1 not well");
}

#[tokio::test]
async fn health_check_reports_a_heartbeat_it_is_not_entitled_to_read() {
    let bus = start(silent_broker()).await;
    // The body names a service other than the one the broker saw publish it.
    let liar = pump_as(&bus, "jv-ears", vec![("sys.health", heartbeat("jv-voice", "ok", None))], 50);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["health", "--check", "--for", "0.6"]), 8.0).await;
    liar.abort();

    assert_eq!(out.code, 1, "an unreadable heartbeat is a finding; stderr: {}", out.stderr);
    let lines = out.lines();
    assert!(lines[0].starts_with("jv-ears      unknown "), "{:?}", lines[0]);
    assert!(lines[0].contains('?'), "no age may be invented for it: {:?}", lines[0]);
    assert_eq!(lines[1], "heard from 1 service in 0.6s; 1 not well");
}

#[tokio::test]
async fn health_check_prints_the_rung_the_brain_reports() {
    let bus = start(silent_broker()).await;
    let mut beat = heartbeat("jv-brain", "ok", None);
    if let rmpv::Value::Map(pairs) = &mut beat {
        pairs.push((
            "metrics".into(),
            body(&[("llm_rung", 4.into()), ("llm_gpu", 0.into())]),
        ));
    }
    let brain = pump_as(&bus, "jv-brain", vec![("sys.health", beat)], 50);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["health", "--check", "--for", "0.6"]), 8.0).await;
    brain.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 3, "{lines:?}");
    assert_eq!(lines[1], "llm rung=4 backend=cpu");
}

/// jv-brain heartbeating with a first-say gauge whose turn counter rises
/// exactly once, `rise_after` beats in — the only shape from which `--check`
/// may date the turn the number measures.
///
/// The steady beats before the rise are not padding. `--check` records the
/// FIRST count it reads and never treats it as fresh, because that gauge may
/// describe a turn from before it connected; the rise has to land while it is
/// listening or there is nothing to date. Starting the pump and the reader at
/// the same moment proves the opposite of what this test wants.
fn pump_brain_measuring_a_turn(
    bus: &TestBus,
    every_ms: u64,
    rise_after: u32,
) -> tokio::task::JoinHandle<()> {
    let addr: BusAddr = bus.addr.clone();
    tokio::spawn(async move {
        let mut c = BusClient::connect(&addr, "jv-brain").await.expect("pump connect");
        let mut beats = 0u32;
        loop {
            let count = if beats < rise_after { 1 } else { 2 };
            if c.publish("sys.health", 1.0, 1, brain_heartbeat(count, 412.0)).await.is_err() {
                return;
            }
            beats += 1;
            tokio::time::sleep(Duration::from_millis(every_ms)).await;
        }
    })
}

#[tokio::test]
async fn health_check_dates_the_turn_it_watched_the_brain_measure() {
    let bus = start(silent_broker()).await;
    // The counter rises 0.6 s in, comfortably after the reader has connected
    // and comfortably before its 1.2 s window closes.
    let brain = pump_brain_measuring_a_turn(&bus, 50, 12);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["health", "--check", "--for", "1.2"]), 8.0).await;
    brain.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 3, "{lines:?}");
    assert!(
        lines[1].starts_with("llm rung=1 backend=? first_say=412ms turn_age="),
        "the counter rose while we listened, so the age is a measurement: {:?}",
        lines[1]
    );
    assert!(!lines[1].contains(">="), "and not a bound: {:?}", lines[1]);
}

#[tokio::test]
async fn health_check_will_not_pass_a_restated_gauge_off_as_a_current_condition() {
    // The same counter on every beat: jv-brain has measured a turn at some
    // point and has not measured one since we connected. The number is still
    // worth printing; presenting it as how long generation is taking RIGHT
    // NOW is not, so the age comes out as a lower bound.
    let bus = start(silent_broker()).await;
    let brain = pump_as(&bus, "jv-brain", vec![("sys.health", brain_heartbeat(3, 412.0))], 50);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["health", "--check", "--for", "0.6"]), 8.0).await;
    brain.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 3, "{lines:?}");
    assert!(
        lines[1].starts_with("llm rung=1 backend=? first_say=412ms turn_age>="),
        "{:?}",
        lines[1]
    );
}

#[tokio::test]
async fn check_and_count_are_two_different_questions_and_cannot_both_be_asked() {
    let bus = start(silent_broker()).await;
    let out = wait_out(spawn_jv(&bus.bus_arg(), &["health", "--check", "-n", "1"]), 8.0).await;

    assert_eq!(out.code, 2, "a usage error must not be mistaken for 'not well'; stdout: {}", out.stdout);
    assert!(out.stdout.is_empty(), "{:?}", out.stdout);
    assert!(out.stderr.contains("--check"), "{}", out.stderr);
}

/// jv-ears' heartbeat carrying the one gauge `jv tap` reads off it.
fn ears_heartbeat(hold_s: f64) -> rmpv::Value {
    body(&[
        ("service", "jv-ears".into()),
        ("state", "ok".into()),
        ("uptime_s", 12.0.into()),
        ("period_s", 5.0.into()),
        ("metrics", body(&[("mic_open", 1.0.into()), ("vad_min_silence_s", hold_s.into())])),
    ])
}

fn vad(event: &str, utt: &str) -> rmpv::Value {
    body(&[("event", event.into()), ("utterance_id", utt.into())])
}

fn transcript(kind: &str, utt: &str) -> rmpv::Value {
    body(&[
        ("kind", kind.into()),
        ("utterance_id", utt.into()),
        ("text", "what time is it".into()),
        ("lang", "en".into()),
    ])
}

/// Publish one voice turn per cycle, forever, with a FRESH utterance id each
/// time, as the real services publish it: `before` is what leads up to the
/// reply — each entry naming the service whose connection publishes it —
/// and jv-brain then sends three sentences, which is what a streamed reply
/// looks like on the bus.
///
/// A new id per cycle is what makes the assertions true under repeats. A turn
/// reports once, so with a fixed id the only turn ever reported would be the
/// one straddling the moment the child's subscription took effect — which is
/// exactly the cycle that may be missing its leading frames. With fresh ids,
/// every later cycle is a whole turn.
fn pump_turns<F>(bus: &TestBus, every_ms: u64, before: F) -> tokio::task::JoinHandle<()>
where
    F: Fn(&str) -> Vec<(&'static str, &'static str, rmpv::Value)> + Send + 'static,
{
    let addr: BusAddr = bus.addr.clone();
    tokio::spawn(async move {
        let mut ears = BusClient::connect(&addr, "jv-ears").await.expect("ears connect");
        let mut brain = BusClient::connect(&addr, "jv-brain").await.expect("brain connect");
        let mut n = 0u32;
        loop {
            n += 1;
            let utt = format!("utt-ralph-{n}");
            for (src, topic, b) in before(&utt) {
                let c = if src == "jv-ears" { &mut ears } else { &mut brain };
                if c.publish(topic, 1.0, 1, b).await.is_err() {
                    return;
                }
                // Long enough that a hold measured in tens of ms fits inside
                // the segment, so `spoke` is a real subtraction.
                tokio::time::sleep(Duration::from_millis(every_ms)).await;
            }
            let say = body(&[("text", "hi".into()), ("in_reply_to_utterance", utt.as_str().into())]);
            for _ in 0..3 {
                if brain.publish("speech.say", 1.0, 1, say.clone()).await.is_err() {
                    return;
                }
            }
            tokio::time::sleep(Duration::from_millis(every_ms)).await;
        }
    })
}

/// The whole turn as jv-ears publishes it: its budgets, both boundaries, and
/// then — because whisper runs after the endpoint decision — the final
/// transcript that divides ASR from the brain.
fn whole_turn(utt: &str) -> Vec<(&'static str, &'static str, rmpv::Value)> {
    vec![
        ("jv-ears", "sys.health", ears_heartbeat(0.02)),
        ("jv-ears", "audio.vad", vad("speech_start", utt)),
        ("jv-ears", "audio.vad", vad("speech_end", utt)),
        ("jv-ears", "audio.transcript", transcript("final", utt)),
    ]
}

/// jv-brain's heartbeat carrying the gauge that divides `think`: how much of
/// it was the LLM, and the turn counter that says whether the number is new.
fn brain_heartbeat(count: u32, model_ms: f64) -> rmpv::Value {
    body(&[
        ("service", "jv-brain".into()),
        ("state", "ok".into()),
        ("uptime_s", 30.0.into()),
        ("period_s", 5.0.into()),
        (
            "metrics",
            body(&[
                ("llm_rung", 1.0.into()),
                ("llm_first_says", count.into()),
                ("llm_first_say_ms", model_ms.into()),
            ]),
        ),
    ])
}

/// The model-share gauge, on a real broker, as jv-brain publishes it: one
/// FRESH gauge per turn, right after that turn's words, on jv-brain's own
/// connection — and, before it, a heartbeat whose counter has NOT risen.
///
/// That restatement is the thing the counter exists for. jv-brain keeps the
/// last turn's gauge on every later periodic heartbeat, so a reader that
/// looked only at the number would divide this turn's `think` with the
/// previous turn's model span. Here the two are told apart by value —
/// `STALE_MODEL_MS` could only ever appear in a split line if the counter
/// check were gone — which is the one way a test outside the process can see
/// the rule hold.
const FRESH_MODEL_MS: f64 = 12.0;
const STALE_MODEL_MS: f64 = 1.0;

fn pump_turns_with_model_gauge(bus: &TestBus, every_ms: u64) -> tokio::task::JoinHandle<()> {
    let addr: BusAddr = bus.addr.clone();
    tokio::spawn(async move {
        let mut ears = BusClient::connect(&addr, "jv-ears").await.expect("ears connect");
        let mut brain = BusClient::connect(&addr, "jv-brain").await.expect("brain connect");
        let mut n = 0u32;
        loop {
            n += 1;
            let utt = format!("utt-model-{n}");
            for (_, topic, b) in whole_turn(&utt) {
                if ears.publish(topic, 1.0, 1, b).await.is_err() {
                    return;
                }
                tokio::time::sleep(Duration::from_millis(every_ms)).await;
            }
            let say = body(&[("text", "hi".into()), ("in_reply_to_utterance", utt.as_str().into())]);
            for _ in 0..3 {
                if brain.publish("speech.say", 1.0, 1, say.clone()).await.is_err() {
                    return;
                }
            }
            // A periodic heartbeat still carrying the PREVIOUS turn's gauge,
            // landing after this turn's words. Must divide nothing.
            if n > 1 {
                let stale = brain_heartbeat(n - 1, STALE_MODEL_MS);
                if brain.publish("sys.health", 1.0, 1, stale).await.is_err() {
                    return;
                }
            }
            let fresh = brain_heartbeat(n, FRESH_MODEL_MS);
            if brain.publish("sys.health", 1.0, 1, fresh).await.is_err() {
                return;
            }
            tokio::time::sleep(Duration::from_millis(every_ms)).await;
        }
    })
}

/// How long jv-act is made to hold a tool call in `pump_tool_turns`. Far
/// enough above the bus hops around it that the measured span can only be
/// the round trip and not the noise beside it.
const TOOL_HOLD_MS: u64 = 150;

/// One turn that ran a TOOL, as the three services publish it.
///
/// The order is the real one and it is the whole point: jv-brain holds its
/// sentences back while a tool call is open (`on_sentence` is suppressed
/// while tool fragments are present), so `action.result` lands BEFORE the
/// first `speech.say` and jv-act's time is genuinely inside `think`. The
/// confirmation window — 15 s by design, and never spoken — sits in exactly
/// this gap, which is why the span is worth naming.
fn pump_tool_turns(bus: &TestBus, hold_ms: u64) -> tokio::task::JoinHandle<()> {
    let addr: BusAddr = bus.addr.clone();
    tokio::spawn(async move {
        let mut ears = BusClient::connect(&addr, "jv-ears").await.expect("ears connect");
        let mut brain = BusClient::connect(&addr, "jv-brain").await.expect("brain connect");
        let mut act = BusClient::connect(&addr, "jv-act").await.expect("act connect");
        let mut n = 0u32;
        loop {
            n += 1;
            let utt = format!("utt-tool-{n}");
            let rid = format!("req-{n}");
            for (_, topic, b) in whole_turn(&utt) {
                if ears.publish(topic, 1.0, 1, b).await.is_err() {
                    return;
                }
            }
            let req = body(&[
                ("request_id", rid.as_str().into()),
                ("tool", "app.launch".into()),
                ("args", body(&[]).into()),
                ("capability", "benign".into()),
                ("utterance_id", utt.as_str().into()),
            ]);
            if brain.publish("intent.action", 1.0, 1, req).await.is_err() {
                return;
            }
            tokio::time::sleep(Duration::from_millis(hold_ms)).await;
            let res = body(&[
                ("request_id", rid.as_str().into()),
                ("ok", true.into()),
                ("duration_ms", (hold_ms as f64).into()),
            ]);
            if act.publish("action.result", 1.0, 1, res).await.is_err() {
                return;
            }
            let say = body(&[("text", "done".into()), ("in_reply_to_utterance", utt.as_str().into())]);
            for _ in 0..2 {
                if brain.publish("speech.say", 1.0, 1, say.clone()).await.is_err() {
                    return;
                }
            }
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
    })
}

/// How long the confirmation question in `pump_confirm_turns` stays open,
/// and how long jv-act then takes to run the tool. The window is the bigger
/// of the two on purpose: it is what the real 15 s looks like beside a tool
/// that runs in a moment, and it is what makes an undivided `tool` unarguable.
const CONFIRM_WINDOW_MS: u64 = 200;
const CONFIRM_RUN_MS: u64 = 60;

/// One turn that ran a CONFIRMING tool, as the four frames put it on the bus.
///
/// The real order, from `services/jv-act/src/service.rs`: jv-brain publishes
/// `intent.action`; jv-act answers with `action.confirm{kind=request}` and
/// waits; the answer arrives (here as the CLI's `kind=answer`, which jv-act
/// then ECHOES — both frames are published, as they are live); jv-act runs
/// the tool and publishes `action.result`.
fn pump_confirm_turns(bus: &TestBus) -> tokio::task::JoinHandle<()> {
    let addr: BusAddr = bus.addr.clone();
    tokio::spawn(async move {
        let mut ears = BusClient::connect(&addr, "jv-ears").await.expect("ears connect");
        let mut brain = BusClient::connect(&addr, "jv-brain").await.expect("brain connect");
        let mut act = BusClient::connect(&addr, "jv-act").await.expect("act connect");
        let mut cli = BusClient::connect(&addr, "jv-cli").await.expect("cli connect");
        let mut n = 0u32;
        loop {
            n += 1;
            // jv-ears stamps `uuid.uuid4()` on every utterance
            // (`jv_ears/pipeline.py`), and this is the widest ladder any
            // turn prints, so the live id shape belongs here: four lines,
            // each carrying an id `short_id` has to cut down.
            let utt = format!("{n:08x}-6d1e-4b7a-9c05-8ef23a41d9b7");
            let rid = format!("req-{n}");
            for (_, topic, b) in whole_turn(&utt) {
                if ears.publish(topic, 1.0, 1, b).await.is_err() {
                    return;
                }
            }
            let req = body(&[
                ("request_id", rid.as_str().into()),
                ("tool", "fs.delete".into()),
                ("args", body(&[]).into()),
                ("capability", "destructive".into()),
                ("utterance_id", utt.as_str().into()),
            ]);
            if brain.publish("intent.action", 1.0, 1, req).await.is_err() {
                return;
            }
            let ask = body(&[
                ("kind", "request".into()),
                ("request_id", rid.as_str().into()),
                ("tool", "fs.delete".into()),
                ("summary", "Delete 3 files — yes or no?".into()),
                ("window_s", 15.0.into()),
            ]);
            if act.publish("action.confirm", 1.0, 1, ask).await.is_err() {
                return;
            }
            tokio::time::sleep(Duration::from_millis(CONFIRM_WINDOW_MS)).await;
            let answer = body(&[
                ("kind", "answer".into()),
                ("request_id", rid.as_str().into()),
                ("granted", true.into()),
                ("answered_by", "cli".into()),
            ]);
            if cli.publish("action.confirm", 1.0, 1, answer.clone()).await.is_err() {
                return;
            }
            // jv-act echoes the answer it acted on, on the same topic.
            if act.publish("action.confirm", 1.0, 1, answer).await.is_err() {
                return;
            }
            tokio::time::sleep(Duration::from_millis(CONFIRM_RUN_MS)).await;
            let res = body(&[
                ("request_id", rid.as_str().into()),
                ("ok", true.into()),
                ("duration_ms", ((CONFIRM_WINDOW_MS + CONFIRM_RUN_MS) as f64).into()),
            ]);
            if act.publish("action.result", 1.0, 1, res).await.is_err() {
                return;
            }
            let say = body(&[("text", "done".into()), ("in_reply_to_utterance", utt.as_str().into())]);
            if brain.publish("speech.say", 1.0, 1, say).await.is_err() {
                return;
            }
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
    })
}

/// Every `>>> turn` line the child printed.
fn turn_lines(out: &Out) -> Vec<&str> {
    out.stdout.lines().filter(|l| l.starts_with(">>> turn ")).collect()
}

/// Those lines gathered per turn, in the order the turns were reported.
///
/// A turn is a LADDER of lines now and not one line (B22): the turn, the
/// machine's half of it, jv-act's share, your share of jv-act's — and the
/// `think` split, which arrives later off jv-brain's next heartbeat and is
/// not adjacent to the rest. The id every line carries is what ties them
/// together, which is also why it is on every line.
fn turn_ladders(out: &Out) -> Vec<Vec<&str>> {
    let mut order: Vec<&str> = Vec::new();
    let mut by_id: std::collections::HashMap<&str, Vec<&str>> = std::collections::HashMap::new();
    for l in turn_lines(out) {
        let id = l.split_whitespace().nth(2).unwrap_or_default().trim_end_matches(':');
        if !by_id.contains_key(id) {
            order.push(id);
        }
        by_id.entry(id).or_default().push(l);
    }
    order.into_iter().map(|id| by_id.remove(id).expect("an id we just recorded")).collect()
}

/// Every column `jv tap` may use for a line it writes as a REPORT.
///
/// `cli::TAP_COLUMNS`, restated here because a test that imported the number
/// it is checking would pass on any number at all.
const TERMINAL_COLUMNS: usize = 80;

/// Where a hop line's columns fall: `cli::TOPIC_COLUMNS` and the offset of
/// the `seq=` label past `cli::SRC_COLUMNS` behind it.
///
/// Restated here for the same reason `TERMINAL_COLUMNS` is, and load-bearing
/// for a second one: a width test alone passes on `bin/jv.rs` keeping its own
/// narrower `format!`, because every topic on a real bus is short enough to
/// fit either. This is what says the binary is printing `cli::hop_line` and
/// not a copy of it.
const TOPIC_COLUMNS: usize = 22;
const SEQ_AT: usize = TOPIC_COLUMNS + 1 + 13 + 1;

/// Every line this output writes as a REPORT, at a real terminal's width.
///
/// The `>>> ` turn ladder, and — under `--latency` — the per-frame hop line,
/// which used to be formatted in `bin/jv.rs` where this test could not see it
/// (PLAN B23). It is `cli::hop_line` now, covered by a unit test at inputs no
/// publisher is stopped from producing; this is the half that proves the
/// binary still calls it.
fn every_reported_line_fits(out: &Out) {
    let reported: Vec<&str> = out
        .stdout
        .lines()
        .filter(|l| l.starts_with(">>> ") || l.contains(" hop="))
        .collect();
    assert!(!reported.is_empty(), "nothing was reported:\n{}", out.stdout);
    for l in reported {
        let w = l.chars().count();
        assert!(w <= TERMINAL_COLUMNS, "{w} columns, {} too many: {l}", w - TERMINAL_COLUMNS);
    }
}

#[tokio::test]
async fn a_streamed_reply_reports_its_turn_exactly_once() {
    let bus = start(Config::default()).await;
    let p = pump_turns(&bus, 30, whole_turn);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--for", "1.2"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let ladders = turn_ladders(&out);
    assert!(!ladders.is_empty(), "no turn was reported:\n{}", out.stdout);
    // Three speech.say frames per utterance, one report each: only the first
    // sentence is time-to-first-word. A turn reported twice would put two
    // headlines under one id.
    for l in &ladders {
        let heads = l.iter().filter(|x| x.contains("total=")).count();
        assert_eq!(heads, 1, "a turn was reported more than once: {l:?}");
    }
    every_reported_line_fits(&out);
}

#[tokio::test]
async fn a_turn_is_reported_split_at_the_boundaries_jv_ears_published() {
    let bus = start(Config::default()).await;
    // 20 ms of endpoint hold inside a ~40 ms segment: small enough for a test
    // to wait out, and it is jv-ears' own gauge that carries it.
    let p = pump_turns(&bus, 30, whole_turn);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.2"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    // At least one turn measured every span: the hold was read off jv-ears'
    // heartbeat, not assumed.
    let full: Vec<Vec<&str>> = turn_ladders(&out)
        .into_iter()
        .filter(|l| !l.iter().any(|x| x.contains('?')))
        .collect();
    assert!(!full.is_empty(), "no fully-measured turn:\n{}", out.stdout);
    let (head, respond_line) = (full[0][0], full[0][1]);
    assert!(head.contains("hold=20ms"), "the hold must be the one ears published: {head:?}");

    let s = &out.stdout;
    // The per-frame stream really is in this output, so the width filter
    // above is not quietly matching nothing in the only mode that emits it.
    let hops: Vec<&str> = s.lines().filter(|l| l.contains(" hop=")).collect();
    assert!(!hops.is_empty(), "no per-frame hop line was streamed:\n{s}");
    for l in &hops {
        assert!(l.ends_with("ms"), "a hop line does not end in its number: {l}");
        assert_eq!(l.as_bytes()[TOPIC_COLUMNS], b' ', "the topic column is not {TOPIC_COLUMNS} wide: {l}");
        assert!(l[TOPIC_COLUMNS..].starts_with(" jv-"), "no publisher after the topic: {l}");
        assert_eq!(&l[SEQ_AT..SEQ_AT + 4], "seq=", "the src column moved: {l}");
    }
    assert!(s.contains("--- turn latency:"), "{s}");
    for span in ["spoke", "hold", "hear", "think", "respond", "total"] {
        assert!(s.contains(&format!("\n{span:<10} ")), "no {span} row:\n{s}");
    }
    assert!(s.contains("hold+respond"), "the machine's share must be named:\n{s}");
    // hear and think are a PARTITION of respond, measured on real frames
    // through a real broker: the two halves must add up to the whole.
    let n = numbers_in(respond_line);
    let (respond, hear, think) = (n[0], n[1], n[2]);
    assert!(
        (hear + think - respond).abs() <= 1.0,
        "hear {hear} + think {think} != respond {respond} in {respond_line:?}"
    );
    // Cross-process CLOCK_MONOTONIC: every number is a small positive latency,
    // not a negative or a wall-clock-sized nonsense.
    for line in &full[0] {
        for ms in numbers_in(line) {
            assert!((0.0..10_000.0).contains(&ms), "implausible {ms}ms in {line:?}");
        }
    }
    every_reported_line_fits(&out);
}

#[tokio::test]
async fn think_splits_into_the_llm_and_everything_around_it() {
    let bus = start(Config::default()).await;
    let p = pump_turns_with_model_gauge(&bus, 30);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.5"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let splits: Vec<&str> = out
        .stdout
        .lines()
        .filter(|l| l.starts_with(">>> turn ") && l.contains("model="))
        .collect();
    assert!(!splits.is_empty(), "no think was ever split:\n{}", out.stdout);
    // Only the fresh gauge ever divided anything: a heartbeat whose counter
    // had not risen is the previous turn's number, and this turn is not it.
    for line in &splits {
        assert!(
            line.contains(&format!("model={FRESH_MODEL_MS:.0}ms")),
            "a stale gauge divided a turn: {line:?}"
        );
    }
    // wait + model is exactly the think it divided, on real frames through a
    // real broker — the same partition rule hear + think = respond obeys.
    let n = numbers_in(splits[0]);
    let (think, wait, model) = (n[0], n[1], n[2]);
    assert!((wait + model - think).abs() <= 1.0, "wait {wait} + model {model} != think {think}");
    assert!(model > 0.0 && wait > 0.0, "{:?}", splits[0]);

    // The first gauge this tap saw was recorded and NOT consumed: it could
    // have been restating a turn from before the tap connected, and a
    // measurement may not guess. So the first turn reported here is split by
    // nothing, and there is always at least one more turn line than split.
    let reported = turn_lines(&out).len() - splits.len();
    assert!(reported > splits.len(), "every turn was split:\n{}", out.stdout);

    let s = &out.stdout;
    for span in ["wait", "model"] {
        assert!(s.contains(&format!("\n  {span:<8} ")), "no {span} row:\n{s}");
    }
    assert!(!s.contains("think unsplit"), "the table apologises for a split think:\n{s}");
}

#[tokio::test]
async fn a_think_nobody_divided_says_so_rather_than_guessing() {
    let bus = start(Config::default()).await;
    // jv-brain publishes the words and no gauge — an older jv-brain, or a
    // turn that ran tools.
    let p = pump_turns(&bus, 30, whole_turn);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.2"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let s = &out.stdout;
    assert!(s.contains("\nthink      "), "think must still be measured:\n{s}");
    assert!(!s.contains("\n  wait "), "a wait row with no gauge behind it:\n{s}");
    assert!(!s.contains("\n  model "), "a model row with no gauge behind it:\n{s}");
    assert!(s.contains("think unsplit"), "the table must say why:\n{s}");
    assert!(s.contains("llm_first_say_ms"), "and name the gauge it wanted:\n{s}");
}

#[tokio::test]
async fn without_jv_ears_own_budget_the_spoken_share_is_a_question_mark() {
    let bus = start(Config::default()).await;
    let p = pump_turns(&bus, 30, |utt| {
        vec![
            ("jv-ears", "audio.vad", vad("speech_start", utt)),
            ("jv-ears", "audio.vad", vad("speech_end", utt)),
        ]
    });

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.2"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let ladders = turn_ladders(&out);
    assert!(!ladders.is_empty(), "no turn was reported:\n{}", out.stdout);
    assert!(ladders[0][0].contains("spoke=? hold=?"), "{:?}", ladders[0][0]);
    assert!(
        ladders[0][1].contains("respond="),
        "what WAS measured is still printed: {:?}",
        ladders[0][1]
    );

    let s = &out.stdout;
    // The two spans that need the gauge are absent from the table, and the
    // table says which gauge and why — never a zero, never ears' default.
    assert!(!s.contains("\nspoke     "), "a span nothing measured is not a row:\n{s}");
    assert!(s.contains("vad_min_silence_s"), "{s}");
    assert!(s.contains("\nrespond   "), "{s}");
}

#[tokio::test]
async fn a_transcript_is_not_a_boundary_and_cannot_stand_in_for_one() {
    let bus = start(Config::default()).await;
    // A partial transcript carries the same utterance_id and is emitted
    // PART-WAY through the utterance. It used to be allowed to define the
    // start, which silently measured every such turn short. With no
    // `audio.vad` on the bus there is nothing to bound this utterance, so
    // there is nothing to report about it.
    let p = pump_turns(&bus, 30, |utt| {
        vec![(
            "jv-ears",
            "audio.transcript",
            body(&[
                ("kind", "partial".into()),
                ("utterance_id", utt.into()),
                ("text", "what time".into()),
                ("lang", "en".into()),
            ]),
        )]
    });

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.2"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    assert!(turn_lines(&out).is_empty(), "{:?}", turn_lines(&out));
    assert!(!out.stdout.contains("--- turn latency:"), "{}", out.stdout);
    // The transcripts themselves are still taken as frames, so this is an
    // absence of a MEASUREMENT and not an absence of traffic.
    assert!(out.stdout.contains("audio.transcript"), "{}", out.stdout);
}

#[tokio::test]
async fn a_partial_transcript_is_not_the_seam_even_where_the_seam_would_be() {
    let bus = start(Config::default()).await;
    // Partials are provisional ASR output; taking one as the moment ASR
    // finished would measure `hear` short and `think` long — a brain blamed
    // for time whisper spent. jv-ears happens to emit every partial BEFORE
    // its speech_end, so the out-of-order guard would refuse them anyway and
    // the `kind` check would look unnecessary while doing all the work. So
    // this puts a partial exactly where a seam belongs, between speech_end
    // and the first word, where nothing but its `kind` can disqualify it.
    let p = pump_turns(&bus, 30, |utt| {
        vec![
            ("jv-ears", "sys.health", ears_heartbeat(0.02)),
            ("jv-ears", "audio.vad", vad("speech_start", utt)),
            ("jv-ears", "audio.vad", vad("speech_end", utt)),
            ("jv-ears", "audio.transcript", transcript("partial", utt)),
        ]
    });

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.2"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let ladders = turn_ladders(&out);
    assert!(!ladders.is_empty(), "no turn was reported:\n{}", out.stdout);
    let respond_line = ladders[0][1];
    assert!(respond_line.contains("hear=? + think=?"), "{respond_line:?}");
    assert!(!respond_line.contains("respond=?"), "the whole is still measured: {respond_line:?}");

    let s = &out.stdout;
    assert!(s.contains("\nrespond   "), "{s}");
    assert!(!s.contains("\nhear      "), "a span nothing measured is not a row:\n{s}");
    assert!(!s.contains("\nthink     "), "{s}");
    assert!(s.contains("audio.transcript"), "the table must say what was missing:\n{s}");
}

#[tokio::test]
async fn a_tap_that_joined_mid_utterance_reports_the_span_it_heard_and_no_other() {
    let bus = start(Config::default()).await;
    // speech_end but no speech_start: `jv tap` was started while the user
    // was already talking. `respond` is knowable; `total` is not, and a
    // speech_end standing in for the start would be a turn measured from
    // the wrong end.
    let p = pump_turns(&bus, 30, |utt| {
        vec![
            ("jv-ears", "sys.health", ears_heartbeat(0.02)),
            ("jv-ears", "audio.vad", vad("speech_end", utt)),
        ]
    });

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.2"]), 8.0).await;
    p.abort();

    let lines = turn_lines(&out);
    assert!(!lines.is_empty(), "no turn was reported:\n{}", out.stdout);
    assert!(lines[0].contains("total=?"), "{:?}", lines[0]);
    assert!(lines[0].contains("spoke=?"), "{:?}", lines[0]);
    assert!(!lines[0].contains("respond=?"), "{:?}", lines[0]);
    assert!(out.stdout.contains("\nrespond   "), "{}", out.stdout);
    assert!(!out.stdout.contains("\ntotal     "), "{}", out.stdout);
}

#[tokio::test]
async fn a_tool_turn_says_how_much_of_its_think_was_jv_act() {
    let bus = start(Config::default()).await;
    let p = pump_tool_turns(&bus, TOOL_HOLD_MS);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.5"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let tool: Vec<&str> = out.stdout.lines().filter(|l| l.contains("tool=")).collect();
    assert!(!tool.is_empty(), "no tool split was reported:\n{}", out.stdout);
    assert!(tool[0].contains("(1 jv-act call)"), "{:?}", tool[0]);

    // The round trip we made jv-act hold, measured off the two frames that
    // bracket it — not the sleep, but within reach of it from above.
    let ns = numbers_in(tool[0]);
    assert_eq!(ns.len(), 2, "think and tool: {:?}", tool[0]);
    let (think, held) = (ns[0], ns[1]);
    assert!(held >= TOOL_HOLD_MS as f64, "{held}ms < the {TOOL_HOLD_MS}ms jv-act held");
    assert!(held < TOOL_HOLD_MS as f64 + 400.0, "{held}ms is not a round trip: {:?}", tool[0]);
    assert!(held <= think, "a share cannot exceed its whole: {:?}", tool[0]);

    // Neither of the two lines it follows grew a number.
    let l = &turn_ladders(&out)[0];
    assert!(l[0].starts_with(">>> turn utt-tool-"), "{:?}", l[0]);
    assert!(!l[0].contains("tool="), "{:?}", l[0]);
    assert!(!l[1].contains("tool="), "{:?}", l[1]);
    every_reported_line_fits(&out);

    let s = &out.stdout;
    assert!(s.contains("\n  tool "), "the summary must carry the row:\n{s}");
    assert!(s.contains("the whole window it waited for your answer in"), "and say what is in it:\n{s}");
    // A turn that ran tools publishes no first-say gauge, so the OTHER split
    // of think must not appear standing on these turns.
    assert!(!s.contains("\n  model "), "{s}");
}

#[tokio::test]
async fn a_confirming_tool_says_which_half_of_its_span_was_you() {
    let bus = start(Config::default()).await;
    let p = pump_confirm_turns(&bus);

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.5"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    // The whole ladder, on the id shape jv-ears really stamps: four lines,
    // each one dividing a span the line above it valued.
    let full: Vec<Vec<&str>> = turn_ladders(&out).into_iter().filter(|l| l.len() == 4).collect();
    assert!(!full.is_empty(), "no confirmation split was reported:\n{}", out.stdout);
    let (head, tool_line, split) = (full[0][0], full[0][2], full[0][3]);
    assert!(split.contains("(1 confirmation)"), "{split:?}");

    // tool = you + ran, each measured off the frames that bracket it. The
    // window we held is the bulk of it, which is the whole point: undivided,
    // this turn reads as a slow machine.
    let ns = numbers_in(split);
    assert_eq!(ns.len(), 2, "you and ran: {split:?}");
    let (you, ran) = (ns[0], ns[1]);
    let tool = numbers_in(tool_line)[1];
    // `<=` and not `<`: `ran` IS `tool - you` to the float, but the three
    // are rounded to whole milliseconds INDEPENDENTLY for printing, so the
    // two halves of a 262.4 ms tool can print as 202 + 61. One is the whole
    // of the error and anything larger is a real disagreement. (This has
    // always been true of these three numbers; the tolerance was `<` and
    // the test flaked about one run in three under load.)
    assert!((tool - (you + ran)).abs() <= 1.0, "the halves must add up: {:?}", full[0]);
    assert!(you >= CONFIRM_WINDOW_MS as f64, "{you}ms < the {CONFIRM_WINDOW_MS}ms we held");
    assert!(you < CONFIRM_WINDOW_MS as f64 + 400.0, "{you}ms is not the window: {split:?}");
    assert!(ran < you, "the machine's half must be the smaller one here: {split:?}");

    // Its own line, under the `tool` line, under the two the turn always
    // prints — and none of the ones above it grew a number.
    assert!(!head.contains("you="), "{head:?}");
    assert!(!full[0][1].contains("you="), "{:?}", full[0][1]);
    assert!(tool_line.contains("includes tool="), "{tool_line:?}");
    assert!(!tool_line.contains("you="), "{tool_line:?}");

    // The live utterance id is a UUID and no line carries one: every rung
    // shows the same abbreviated id, and every rung fits a terminal. This
    // is B22 on real output rather than on a constructed `Turn`.
    let shown = head.split_whitespace().nth(2).expect("an id").trim_end_matches(':');
    assert_eq!(shown.chars().count(), 11, "the id is not the width it is capped at: {shown}");
    assert!(shown.ends_with("..."), "an abbreviated id must say so: {shown}");
    for l in &full[0] {
        assert!(l.contains(shown), "a rung carries a different id: {l:?}");
        assert!(!l.contains("-6d1e-"), "the whole uuid reached a turn line: {l:?}");
    }
    every_reported_line_fits(&out);

    let s = &out.stdout;
    assert!(s.contains("\n    you "), "the summary must carry the row:\n{s}");
    assert!(s.contains("\n    ran "), "and its other half:\n{s}");
    assert!(s.contains("action.confirm"), "and say where the number came from:\n{s}");
}

#[tokio::test]
async fn an_action_no_result_answered_leaves_the_turn_unsplit() {
    let bus = start(Config::default()).await;
    // jv-act never answers. The turn is still a turn and `think` is still
    // measured — it simply contains a tool call of unknown length, and a
    // share that cannot be stated is not stated.
    let addr = bus.addr.clone();
    let p = tokio::spawn(async move {
        let mut ears = BusClient::connect(&addr, "jv-ears").await.expect("ears");
        let mut brain = BusClient::connect(&addr, "jv-brain").await.expect("brain");
        let mut n = 0u32;
        loop {
            n += 1;
            let utt = format!("utt-open-{n}");
            for (_, topic, b) in whole_turn(&utt) {
                if ears.publish(topic, 1.0, 1, b).await.is_err() {
                    return;
                }
            }
            let req = body(&[
                ("request_id", format!("req-{n}").as_str().into()),
                ("tool", "app.launch".into()),
                ("args", body(&[]).into()),
                ("capability", "benign".into()),
                ("utterance_id", utt.as_str().into()),
            ]);
            if brain.publish("intent.action", 1.0, 1, req).await.is_err() {
                return;
            }
            let say = body(&[("text", "ok".into()), ("in_reply_to_utterance", utt.as_str().into())]);
            if brain.publish("speech.say", 1.0, 1, say).await.is_err() {
                return;
            }
            tokio::time::sleep(Duration::from_millis(30)).await;
        }
    });

    let out = wait_out(spawn_jv(&bus.bus_arg(), &["tap", "--latency", "--for", "1.2"]), 8.0).await;
    p.abort();

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = turn_lines(&out);
    assert!(!lines.is_empty(), "no turn was reported:\n{}", out.stdout);
    assert!(!out.stdout.contains("tool="), "{}", out.stdout);
    assert!(out.stdout.contains("\nthink     "), "think is still measured:\n{}", out.stdout);
    assert!(!out.stdout.contains("\n  tool "), "{}", out.stdout);
}

/// Every `<digits>ms` in a line, as f64.
fn numbers_in(line: &str) -> Vec<f64> {
    line.split('=')
        .skip(1)
        .filter_map(|s| s.split("ms").next().and_then(|n| n.trim().parse().ok()))
        .collect()
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


// ---------------------------------------------------------------- act-log filters
//
// The two questions a human actually has after something happened: "what did
// jv-act do in the last ten minutes" and "show me everything that was not ok".
// Unit tests in `jarvisd::cli` pin the filtering itself; these pin the wiring
// no unit test can see — that the flags reach it, and that the exit codes a
// script depends on come out of the real binary.

/// One audit line stamped when the caller says.
fn audit_entry_at(tool: &str, ts: &str, outcome: &str) -> String {
    let mut e: serde_json::Value = serde_json::from_str(&audit_entry(tool, outcome, None)).unwrap();
    e["ts"] = serde_json::json!(ts);
    e.to_string()
}

fn act_log(path: &std::path::Path, args: &[&str]) -> std::process::Child {
    let mut argv = vec!["act-log"];
    argv.extend_from_slice(args);
    spawn_jv_env("/nonexistent/no-bus-needed.sock", &argv, &[("JARVIS_ACT_AUDIT", path.to_str().unwrap())])
}

#[tokio::test]
async fn act_log_failed_shows_only_what_did_not_succeed() {
    let (_tmp, path) = audit_file(&[
        audit_entry("a.ok", "ok", None),
        audit_entry("a.denied", "denied", None),
        audit_entry("a.boom", "execution_failed", None),
    ]);
    let out = wait_out(act_log(&path, &["--failed"]), 8.0).await;

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 2, "{lines:?}");
    assert!(lines[0].contains("a.denied"), "{:?}", lines[0]);
    assert!(lines[1].contains("a.boom"), "{:?}", lines[1]);
    assert!(!out.stdout.contains("a.ok"), "{}", out.stdout);
}

/// grep's rule, and the reason a typo'd `--outcome denyed` cannot read as
/// reassurance. Nothing is PRINTED for it: on a healthy machine "nothing
/// failed" is the good answer, and a warning every time would train a human
/// to ignore this command.
#[tokio::test]
async fn a_question_nothing_answers_exits_one_and_says_nothing() {
    let (_tmp, path) = audit_file(&[audit_entry("a.ok", "ok", None)]);
    for args in [vec!["--failed"], vec!["--outcome", "denyed"]] {
        let out = wait_out(act_log(&path, &args), 8.0).await;
        assert_eq!(out.code, 1, "{args:?} -> stdout {:?}", out.stdout);
        assert!(out.stdout.trim().is_empty(), "{args:?} -> {:?}", out.stdout);
        assert!(out.stderr.trim().is_empty(), "{args:?} -> {:?}", out.stderr);
    }
    // The same log with no question asked is history, not a failed search.
    let out = wait_out(act_log(&path, &[]), 8.0).await;
    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
}

#[tokio::test]
async fn act_log_outcome_is_repeatable_and_exact() {
    let (_tmp, path) = audit_file(&[
        audit_entry("a.ok", "ok", None),
        audit_entry("a.denied", "denied", None),
        audit_entry("a.ct", "confirm_timeout", None),
        audit_entry("a.to", "timeout", None),
    ]);
    let out = wait_out(act_log(&path, &["--outcome", "denied", "--outcome", "timeout"]), 8.0).await;

    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    let lines = out.lines();
    assert_eq!(lines.len(), 2, "confirm_timeout is not timeout: {lines:?}");
    assert!(lines[0].contains("a.denied"), "{:?}", lines[0]);
    assert!(lines[1].contains("a.to"), "{:?}", lines[1]);
}

#[tokio::test]
async fn act_log_since_bounds_the_window_in_both_directions() {
    let (_tmp, path) = audit_file(&[
        audit_entry_at("a.old", "2020-01-01T00:00:00Z", "ok"),
        audit_entry_at("a.new", "2020-06-01T12:00:00Z", "ok"),
    ]);

    // An absolute stamp, and --tail applying to the ANSWER.
    let out = wait_out(act_log(&path, &["--since", "2020-03-01T00:00:00Z"]), 8.0).await;
    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    assert_eq!(out.lines().len(), 1, "{}", out.stdout);
    assert!(out.stdout.contains("a.new") && !out.stdout.contains("a.old"), "{}", out.stdout);

    // A duration back from a real wall clock. Both entries are years old, so
    // a long window holds them and a short one holds neither — which is the
    // arithmetic actually being asserted, without this test needing to know
    // what time it is.
    let out = wait_out(act_log(&path, &["--since", "100000d"]), 8.0).await;
    assert_eq!(out.code, 0, "stderr: {}", out.stderr);
    assert_eq!(out.lines().len(), 2, "{}", out.stdout);

    let out = wait_out(act_log(&path, &["--since", "10m"]), 8.0).await;
    assert_eq!(out.code, 1, "nothing happened in the last ten minutes: {}", out.stdout);
    assert!(out.stdout.trim().is_empty(), "{}", out.stdout);
}

/// A `--since` that cannot be read must be an ERROR, never "since the
/// beginning of time" — a filter that silently widens prints the whole log and
/// reads as a great deal of recent activity.
#[tokio::test]
async fn act_log_refuses_a_since_it_cannot_read_and_prints_no_log() {
    let (_tmp, path) = audit_file(&[audit_entry("a.ok", "ok", None)]);
    let out = wait_out(act_log(&path, &["--since", "yesterday"]), 8.0).await;

    assert_ne!(out.code, 0, "stdout: {}", out.stdout);
    assert!(out.stdout.trim().is_empty(), "the log must not be printed anyway: {}", out.stdout);
    assert!(out.stderr.contains("--since"), "say which flag: {}", out.stderr);
    assert!(out.stderr.contains("yesterday"), "and what was typed: {}", out.stderr);
}

/// `--failed` IS `--outcome` negated. Accepting both would have to invent a
/// meaning for their intersection, and every meaning is a guess at what the
/// caller wanted.
#[tokio::test]
async fn failed_and_outcome_cannot_both_be_asked() {
    let (_tmp, path) = audit_file(&[audit_entry("a.ok", "ok", None)]);
    let out = wait_out(act_log(&path, &["--failed", "--outcome", "denied"]), 8.0).await;

    assert_ne!(out.code, 0, "stdout: {}", out.stdout);
    assert!(out.stdout.trim().is_empty(), "{}", out.stdout);
    assert!(out.stderr.contains("cannot be used with"), "{}", out.stderr);
}

/// A line nobody can parse has no ts and no outcome, so no filter can prove it
/// does not belong in the answer. It stays, and it still fails the command.
#[tokio::test]
async fn a_filter_does_not_hide_a_torn_line() {
    let (_tmp, path) = audit_file(&[
        audit_entry("a.ok", "ok", None),
        r#"{"ts":"2026-09-24T10:00:01Z","tool":"fs.tr"#.to_string(),
    ]);
    let out = wait_out(act_log(&path, &["--failed"]), 8.0).await;

    assert_eq!(out.code, 1, "stdout: {}", out.stdout);
    let lines = out.lines();
    assert_eq!(lines.len(), 1, "the ok entry was filtered out, the hole was not: {lines:?}");
    assert!(lines[0].starts_with("!! unreadable audit line 2"), "{:?}", lines[0]);
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
