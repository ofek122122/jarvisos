//! Integration tests for the broker: routing, fanout, disconnects, the
//! drop-oldest slow-consumer policy, and envelope rejection.
//! On unix they run over a real Unix socket; elsewhere over loopback TCP.

use jarvisd::broker::{Broker, BusAddr, Config, Listener};
use jarvisd::client::BusClient;
use jarvisd::proto::ServerMsg;
use std::sync::Arc;
use std::time::Duration;

struct TestBus {
    addr: BusAddr,
    _broker: Arc<Broker>,
    task: tokio::task::JoinHandle<()>,
    #[cfg(unix)]
    _tmp: tempfile::TempDir,
}

impl Drop for TestBus {
    fn drop(&mut self) {
        self.task.abort();
    }
}

async fn start(cfg: Config) -> TestBus {
    #[cfg(unix)]
    {
        let tmp = tempfile::tempdir().unwrap();
        let addr = BusAddr::Unix(tmp.path().join("bus.sock"));
        let (listener, actual) = Listener::bind(&addr).await.unwrap();
        let broker = Broker::new(cfg);
        let task = broker.spawn(listener);
        TestBus { addr: actual, _broker: broker, task, _tmp: tmp }
    }
    #[cfg(not(unix))]
    {
        let addr = BusAddr::Tcp("127.0.0.1:0".to_string());
        let (listener, actual) = Listener::bind(&addr).await.unwrap();
        let broker = Broker::new(cfg);
        let task = broker.spawn(listener);
        TestBus { addr: actual, _broker: broker, task }
    }
}

fn body(pairs: &[(&str, rmpv::Value)]) -> rmpv::Value {
    rmpv::Value::Map(pairs.iter().map(|(k, v)| ((*k).into(), v.clone())).collect())
}

fn topic_of(frame: &rmpv::Value) -> String {
    frame
        .as_map()
        .unwrap()
        .iter()
        .find(|(k, _)| k.as_str() == Some("topic"))
        .and_then(|(_, v)| v.as_str())
        .unwrap()
        .to_string()
}

fn seq_of(frame: &rmpv::Value) -> u64 {
    frame
        .as_map()
        .unwrap()
        .iter()
        .find(|(k, _)| k.as_str() == Some("seq"))
        .and_then(|(_, v)| v.as_u64())
        .unwrap()
}

async fn recv_frame(c: &mut BusClient, ms: u64) -> Option<rmpv::Value> {
    tokio::time::timeout(Duration::from_millis(ms), c.next_frame())
        .await
        .ok()?
        .unwrap()
}

#[tokio::test]
async fn exact_and_prefix_routing() {
    let bus = start(Config::default()).await;
    let mut sub = BusClient::connect(&bus.addr, "sub").await.unwrap();
    sub.subscribe(&["audio.*", "speech.say"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await; // let Sub land

    let mut publ = BusClient::connect(&bus.addr, "pub").await.unwrap();
    publ.publish("audio.wake", 0.9, 1, body(&[("model", "hey_jarvis".into())]))
        .await
        .unwrap();
    let f = recv_frame(&mut sub, 1000).await.expect("audio.wake should arrive");
    assert_eq!(topic_of(&f), "audio.wake");

    // Non-matching topic must NOT arrive.
    publ.publish("speech.state", 1.0, 1, body(&[("state", "idle".into())]))
        .await
        .unwrap();
    // Matching one right after; if state had been routed we'd see it first.
    publ.publish("speech.say", 1.0, 1, body(&[("text", "hi".into())]))
        .await
        .unwrap();
    let f = recv_frame(&mut sub, 1000).await.expect("speech.say should arrive");
    assert_eq!(topic_of(&f), "speech.say");
}

#[tokio::test]
async fn fanout_and_wildcard() {
    let bus = start(Config::default()).await;
    let mut a = BusClient::connect(&bus.addr, "a").await.unwrap();
    let mut b = BusClient::connect(&bus.addr, "b").await.unwrap();
    a.subscribe(&["*"]).await.unwrap();
    b.subscribe(&["brain.response"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    let mut publ = BusClient::connect(&bus.addr, "pub").await.unwrap();
    publ.publish(
        "brain.response",
        1.0,
        1,
        body(&[("text", "hello".into()), ("finish_reason", "stop".into())]),
    )
    .await
    .unwrap();

    assert_eq!(topic_of(&recv_frame(&mut a, 1000).await.unwrap()), "brain.response");
    assert_eq!(topic_of(&recv_frame(&mut b, 1000).await.unwrap()), "brain.response");
}

#[tokio::test]
async fn subscriber_disconnect_leaves_others_running() {
    let bus = start(Config::default()).await;
    let mut gone = BusClient::connect(&bus.addr, "gone").await.unwrap();
    gone.subscribe(&["audio.*"]).await.unwrap();
    let mut stay = BusClient::connect(&bus.addr, "stay").await.unwrap();
    stay.subscribe(&["audio.*"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;
    drop(gone);

    let mut publ = BusClient::connect(&bus.addr, "pub").await.unwrap();
    for i in 0..3 {
        publ.publish("audio.vad", 1.0, 1, body(&[("event", "speech_start".into())]))
            .await
            .unwrap_or_else(|e| panic!("publish {i} failed after disconnect: {e}"));
    }
    // The remaining subscriber still gets frames; broker survived.
    assert!(recv_frame(&mut stay, 1000).await.is_some());
}

#[tokio::test]
async fn slow_consumer_drop_oldest_and_health_report() {
    let cfg = Config {
        subscriber_queue: 4,
        health_period: Duration::from_millis(200),
        ..Config::default()
    };
    let bus = start(cfg).await;

    // Health watcher first, so the drop report has somewhere to land.
    let mut health = BusClient::connect(&bus.addr, "health").await.unwrap();
    health.subscribe(&["sys.health"]).await.unwrap();

    // The slow one: subscribes, then never reads its socket.
    let mut slow = BusClient::connect(&bus.addr, "slow").await.unwrap();
    slow.subscribe(&["bulk.data"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;

    // Big frames so OS socket buffers can't hide the backlog.
    let payload = "x".repeat(32 * 1024);
    let mut publ = BusClient::connect(&bus.addr, "pub").await.unwrap();
    let total = 300u64;
    for _ in 0..total {
        publ.publish("bulk.data", 1.0, 1, body(&[("blob", payload.as_str().into())]))
            .await
            .expect("publisher must never block or fail");
    }

    // Let the writer drain what it can, then read what actually arrived.
    tokio::time::sleep(Duration::from_millis(300)).await;
    let mut got: Vec<u64> = Vec::new();
    while let Some(f) = recv_frame(&mut slow, 200).await {
        got.push(seq_of(&f));
    }
    assert!(
        (got.len() as u64) < total,
        "expected drops, but all {total} frames arrived"
    );
    assert!(!got.is_empty(), "some frames must survive");
    // Drop-OLDEST: the newest published frame survives at the tail.
    assert_eq!(*got.last().unwrap(), total - 1);
    // And the sequence numbers show a gap.
    let span = got.last().unwrap() - got.first().unwrap() + 1;
    assert!(span > got.len() as u64, "no seq gap despite drops");

    // jarvisd reports the drops on sys.health.
    let deadline = tokio::time::Instant::now() + Duration::from_secs(5);
    let mut reported = false;
    while tokio::time::Instant::now() < deadline {
        let Some(f) = recv_frame(&mut health, 1000).await else { continue };
        let s = serde_json::to_string(&f).unwrap();
        if s.contains("bulk.data") {
            reported = true;
            break;
        }
    }
    assert!(reported, "sys.health never reported drops for bulk.data");
}

#[tokio::test]
async fn invalid_envelope_rejected_broker_survives() {
    let bus = start(Config::default()).await;
    let mut c = BusClient::connect(&bus.addr, "bad").await.unwrap();

    // Missing everything but topic — must be rejected, not routed.
    let junk = rmpv::Value::Map(vec![("topic".into(), "audio.wake".into())]);
    c.publish_env(junk).await.unwrap();
    match tokio::time::timeout(Duration::from_secs(2), c.next_event())
        .await
        .expect("broker must answer")
        .unwrap()
    {
        Some(ServerMsg::Err { msg }) => assert!(msg.contains("ts"), "unexpected: {msg}"),
        other => panic!("expected Err, got {other:?}"),
    }

    // Same connection still works end to end.
    c.subscribe(&["audio.wake"]).await.unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;
    c.publish("audio.wake", 0.5, 1, body(&[("model", "hey_jarvis".into())]))
        .await
        .unwrap();
    assert!(recv_frame(&mut c, 1000).await.is_some());
}
