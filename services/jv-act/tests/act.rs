//! jv-act integration tests: real broker (jarvisd lib), mock executor.
//! Covers the whole validation gauntlet, the confirmation flow in all
//! three endings (yes / no / timeout), and the audit trail.

use std::sync::{Arc, Mutex};
use std::time::Duration;

use jarvisd::broker::{Broker, BusAddr, Config, Listener};
use jarvisd::client::BusClient;
use jarvisd::time::mono_now;
use jv_act::audit::AuditLog;
use jv_act::exec::{ExecError, ExecOutput, Executor};
use jv_act::registry::Registry;
use jv_act::service::{classify_answer, ActConfig, ActService};

const TEST_REGISTRY: &str = r#"
    [[tool]]
    name = "volume.set"
    description = "Set the volume"
    capability = "benign"
    [tool.args.level]
    type = "number"
    required = true

    [[tool]]
    name = "trash.empty"
    description = "Empty the trash"
    capability = "destructive"
"#;

struct MockExec {
    calls: Arc<Mutex<Vec<(String, serde_json::Value)>>>,
}

#[async_trait::async_trait]
impl Executor for MockExec {
    async fn execute(
        &self,
        tool: &str,
        args: &serde_json::Value,
        _timeout: Duration,
    ) -> Result<ExecOutput, ExecError> {
        self.calls.lock().unwrap().push((tool.to_string(), args.clone()));
        Ok(ExecOutput { output: format!("{tool} done"), data: None })
    }
}

struct Rig {
    addr: BusAddr,
    calls: Arc<Mutex<Vec<(String, serde_json::Value)>>>,
    audit_path: std::path::PathBuf,
    _tmp: tempfile::TempDir,
    _task: tokio::task::JoinHandle<()>,
}

async fn rig(confirm_window_s: f64) -> Rig {
    let tmp = tempfile::tempdir().unwrap();
    #[cfg(unix)]
    let addr = BusAddr::Unix(tmp.path().join("bus.sock"));
    #[cfg(not(unix))]
    let addr = BusAddr::Tcp("127.0.0.1:0".to_string());
    let (listener, actual) = Listener::bind(&addr).await.unwrap();
    let broker = Broker::new(Config::default());
    let _task = broker.spawn(listener);

    let calls = Arc::new(Mutex::new(Vec::new()));
    let audit_path = tmp.path().join("audit.jsonl");
    let svc = ActService::new(
        Registry::from_toml(TEST_REGISTRY).unwrap(),
        Arc::new(MockExec { calls: calls.clone() }),
        AuditLog::new(audit_path.clone()),
        ActConfig { confirm_window_s, health_period_s: 5.0 },
    );
    let sub = BusClient::connect(&actual, "jv-act").await.unwrap();
    let publ = BusClient::connect(&actual, "jv-act").await.unwrap();
    tokio::spawn(async move {
        let _ = svc.run(sub, publ).await;
    });
    tokio::time::sleep(Duration::from_millis(100)).await;
    Rig { addr: actual, calls, audit_path, _tmp: tmp, _task }
}

fn body(json: serde_json::Value) -> rmpv::Value {
    jarvisd::broker::to_value_named(&json).unwrap()
}

fn get<'a>(frame: &'a rmpv::Value, key: &str) -> Option<&'a rmpv::Value> {
    frame.as_map()?.iter().find(|(k, _)| k.as_str() == Some(key)).map(|(_, v)| v)
}

fn body_of(frame: &rmpv::Value) -> serde_json::Value {
    serde_json::to_value(get(frame, "body").unwrap()).unwrap()
}

async fn next_on(c: &mut BusClient, topic: &str) -> serde_json::Value {
    loop {
        let f = tokio::time::timeout(Duration::from_secs(5), c.next_frame())
            .await
            .expect("timeout")
            .unwrap()
            .expect("eof");
        if get(&f, "topic").and_then(|v| v.as_str()) == Some(topic) {
            return body_of(&f);
        }
    }
}

async fn send_intent(c: &mut BusClient, rid: &str, tool: &str, args: serde_json::Value) {
    c.publish(
        "intent.action",
        1.0,
        1,
        body(serde_json::json!({
            "request_id": rid, "tool": tool, "args": args, "capability": "",
        })),
    )
    .await
    .unwrap();
}

/// Publish an audio.transcript final with an EXPLICIT envelope ts, so
/// tests can place an answer inside or outside a confirm window.
async fn publish_transcript(c: &mut BusClient, text: &str, ts: f64) {
    let frame = rmpv::Value::Map(vec![
        ("topic".into(), "audio.transcript".into()),
        ("ts".into(), rmpv::Value::F64(ts)),
        ("seq".into(), rmpv::Value::from(0u64)),
        ("src".into(), "jv-ears".into()),
        ("conf".into(), rmpv::Value::F64(0.9)),
        ("v".into(), rmpv::Value::from(1u64)),
        (
            "body".into(),
            body(serde_json::json!({
                "kind": "final", "utterance_id": "u", "text": text, "lang": "en",
            })),
        ),
    ]);
    c.publish_env(frame).await.unwrap();
}

#[tokio::test]
async fn benign_tool_executes_and_audits() {
    let rig = rig(15.0).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.result"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    send_intent(&mut c, "r1", "volume.set", serde_json::json!({"level": 0.4})).await;
    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["ok"], true);
    assert_eq!(res["request_id"], "r1");
    assert_eq!(rig.calls.lock().unwrap().len(), 1);

    // Audit doctrine: an INTENT line is written BEFORE execution, then
    // the outcome line after. Both present, in that order.
    let audit = std::fs::read_to_string(&rig.audit_path).unwrap();
    let lines: Vec<serde_json::Value> = audit
        .lines()
        .map(|l| serde_json::from_str(l).unwrap())
        .collect();
    assert_eq!(lines.len(), 2, "intent + outcome");
    assert_eq!(lines[0]["outcome"], "intent");
    assert_eq!(lines[0]["tool"], "volume.set");
    assert_eq!(lines[1]["outcome"], "ok");
}

#[tokio::test]
async fn hallucinated_tool_rejected() {
    let rig = rig(15.0).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.result"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    send_intent(&mut c, "r2", "files.delete_everything", serde_json::json!({})).await;
    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["ok"], false);
    assert_eq!(res["error"], "unknown_tool");
    assert!(rig.calls.lock().unwrap().is_empty(), "must never reach an executor");
}

#[tokio::test]
async fn invalid_args_rejected() {
    let rig = rig(15.0).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.result"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    send_intent(&mut c, "r3", "volume.set", serde_json::json!({"level": "loud"})).await;
    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["error"], "invalid_args");
}

#[tokio::test]
async fn capability_mismatch_rejected() {
    let rig = rig(15.0).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.result"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    // brain claims trash.empty is benign — registry says destructive
    c.publish("intent.action", 1.0, 1, body(serde_json::json!({
        "request_id": "r4", "tool": "trash.empty", "args": {}, "capability": "benign",
    }))).await.unwrap();
    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["error"], "capability_mismatch");
    assert!(rig.calls.lock().unwrap().is_empty());
}

#[tokio::test]
async fn destructive_confirmed_by_voice_yes() {
    let rig = rig(15.0).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.*", "dialog.listen"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    send_intent(&mut c, "r5", "trash.empty", serde_json::json!({})).await;
    let req = next_on(&mut c, "action.confirm").await;
    assert_eq!(req["kind"], "request");
    let listen = next_on(&mut c, "dialog.listen").await;
    assert_eq!(listen["reason"], "confirm");

    // the user says yes (a transcript final, as ears would publish)
    c.publish("audio.transcript", 0.9, 1, body(serde_json::json!({
        "kind": "final", "utterance_id": "u-yes", "text": "Yes.", "lang": "en",
    }))).await.unwrap();

    let ans = next_on(&mut c, "action.confirm").await;
    assert_eq!(ans["granted"], true);
    assert_eq!(ans["answered_by"], "voice");
    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["ok"], true);
    assert_eq!(rig.calls.lock().unwrap().len(), 1);

    let audit = std::fs::read_to_string(&rig.audit_path).unwrap();
    assert!(audit.contains("\"granted\":true"));
}

#[tokio::test]
async fn destructive_denied_by_voice_no() {
    let rig = rig(15.0).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.*"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    send_intent(&mut c, "r6", "trash.empty", serde_json::json!({})).await;
    next_on(&mut c, "action.confirm").await; // the request
    c.publish("audio.transcript", 0.9, 1, body(serde_json::json!({
        "kind": "final", "utterance_id": "u-no", "text": "no", "lang": "en",
    }))).await.unwrap();

    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["error"], "denied");
    assert!(rig.calls.lock().unwrap().is_empty(), "denied must not execute");
}

#[tokio::test]
async fn destructive_times_out_to_denied() {
    // BRIEF-phase2 exit item 4: silence = denied.
    let rig = rig(0.5).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.*"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    send_intent(&mut c, "r7", "trash.empty", serde_json::json!({})).await;
    next_on(&mut c, "action.confirm").await; // request
    let ans = next_on(&mut c, "action.confirm").await; // timeout answer
    assert_eq!(ans["granted"], false);
    assert_eq!(ans["answered_by"], "timeout");
    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["error"], "confirm_timeout");
    assert!(rig.calls.lock().unwrap().is_empty());
}

#[tokio::test]
async fn cli_answer_works() {
    let rig = rig(15.0).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.*"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    send_intent(&mut c, "r8", "trash.empty", serde_json::json!({})).await;
    next_on(&mut c, "action.confirm").await;
    c.publish("action.confirm", 1.0, 1, body(serde_json::json!({
        "kind": "answer", "request_id": "r8", "granted": true, "answered_by": "cli",
    }))).await.unwrap();

    // next_on skips the interleaved confirm echoes and lands on the result
    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["ok"], true);
}

#[tokio::test]
async fn stray_yes_no_with_no_window_open_is_ignored() {
    // Fix 1: a yes/no from ordinary conversation must not resolve a
    // confirm that opens later. We fire a stray "yes" with nothing
    // pending, THEN a destructive intent: it must still ask, proving the
    // stray answer was not consumed.
    let rig = rig(15.0).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.*"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    // stray yes — no window is open
    publish_transcript(&mut c, "yes", mono_now()).await;
    tokio::time::sleep(Duration::from_millis(100)).await;
    assert!(rig.calls.lock().unwrap().is_empty(), "stray yes must do nothing");

    // now a real destructive request: it must still request confirmation
    send_intent(&mut c, "s1", "trash.empty", serde_json::json!({})).await;
    let req = next_on(&mut c, "action.confirm").await;
    assert_eq!(req["kind"], "request");

    // a proper in-window yes now executes it
    publish_transcript(&mut c, "yes", mono_now()).await;
    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["ok"], true);
    assert_eq!(rig.calls.lock().unwrap().len(), 1);
}

#[tokio::test]
async fn voice_answer_outside_the_window_is_ignored() {
    // Fix 1: an answer whose envelope ts predates the open window does
    // not count — the confirm proceeds to time out.
    let rig = rig(0.6).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.*"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    let before = mono_now() - 100.0; // long before the window opens
    send_intent(&mut c, "s2", "trash.empty", serde_json::json!({})).await;
    next_on(&mut c, "action.confirm").await; // request

    // a yes stamped in the past must be rejected by the window check
    publish_transcript(&mut c, "yes", before).await;

    let ans = next_on(&mut c, "action.confirm").await; // must be the timeout
    assert_eq!(ans["answered_by"], "timeout");
    let res = next_on(&mut c, "action.result").await;
    assert_eq!(res["error"], "confirm_timeout");
    assert!(rig.calls.lock().unwrap().is_empty());
}

#[tokio::test]
async fn second_destructive_denied_while_one_pends() {
    // Fix 1: at most one confirmation outstanding. The second is denied
    // (reusing the frozen-v1 `denied` error) without a second window.
    let rig = rig(15.0).await;
    let mut c = BusClient::connect(&rig.addr, "t").await.unwrap();
    c.subscribe(&["action.*"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    send_intent(&mut c, "p1", "trash.empty", serde_json::json!({})).await;
    let req = next_on(&mut c, "action.confirm").await;
    assert_eq!(req["request_id"], "p1");

    // second destructive while p1 pends -> denied, no new confirm request
    send_intent(&mut c, "p2", "trash.empty", serde_json::json!({})).await;
    let res2 = next_on(&mut c, "action.result").await;
    assert_eq!(res2["request_id"], "p2");
    assert_eq!(res2["error"], "denied");
    assert!(res2["detail"].as_str().unwrap().contains("pending"));

    // p1 can still be answered and executes
    publish_transcript(&mut c, "yes", mono_now()).await;
    loop {
        let res = next_on(&mut c, "action.result").await;
        if res["request_id"] == "p1" {
            assert_eq!(res["ok"], true);
            break;
        }
    }
    assert_eq!(rig.calls.lock().unwrap().len(), 1);
}

#[test]
fn yes_no_lexicon() {
    assert_eq!(classify_answer("Yes."), Some(true));
    assert_eq!(classify_answer("yeah"), Some(true));
    assert_eq!(classify_answer("go ahead"), Some(true));
    assert_eq!(classify_answer("No"), Some(false));
    assert_eq!(classify_answer("don't"), Some(false));
    assert_eq!(classify_answer("cancel"), Some(false));
    // ambiguity is ignored, not guessed
    assert_eq!(classify_answer("yes but actually no"), None);
    assert_eq!(classify_answer("what time is it"), None);
}
