//! Integration tests for the broker: routing, fanout, disconnects, the
//! drop-oldest slow-consumer policy, and envelope rejection.
//! On unix they run over a real Unix socket; elsewhere over loopback TCP.

mod common;

use common::{body, start};
use jarvisd::broker::Config;
use jarvisd::client::BusClient;
use jarvisd::proto::ServerMsg;
use std::time::Duration;

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

/// Receive frames until one carries `topic`, skipping others (e.g.
/// jarvisd's own sys.health on wildcard subscriptions).
async fn recv_topic(c: &mut BusClient, topic: &str, ms: u64) -> Option<rmpv::Value> {
    let deadline = tokio::time::Instant::now() + Duration::from_millis(ms);
    while tokio::time::Instant::now() < deadline {
        let f = recv_frame(c, ms).await?;
        if topic_of(&f) == topic {
            return Some(f);
        }
    }
    None
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

    // The wildcard subscriber may legitimately see jarvisd's own
    // sys.health heartbeats interleaved — skip to the frame under test.
    assert_eq!(
        topic_of(&recv_topic(&mut a, "brain.response", 2000).await.unwrap()),
        "brain.response"
    );
    assert_eq!(topic_of(&recv_frame(&mut b, 1000).await.unwrap()), "brain.response");
}

/// jarvisd's own frames (sys.health) must be well-formed named-map
/// envelopes — regression test for rmpv::ext::to_value's array-encoded
/// structs leaking onto the bus.
#[tokio::test]
async fn broker_health_frame_is_valid_envelope() {
    let cfg = Config {
        health_period: Duration::from_millis(50),
        ..Config::default()
    };
    let bus = start(cfg).await;
    let mut c = BusClient::connect(&bus.addr, "health-watch").await.unwrap();
    c.subscribe(&["sys.health"]).await.unwrap();

    let f = recv_frame(&mut c, 2000).await.expect("heartbeat expected");
    jarvisd::proto::validate_envelope(&f).expect("health frame must be a valid envelope");
    assert_eq!(topic_of(&f), "sys.health");
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

/// The wire convention goes both ways. `to_value_named` is how every service
/// puts a generated binding on the bus; `from_value_named` is how a consumer
/// reads one back, and it has to survive the part the obvious route does not:
/// the bus spells an enum as its snake_case STRING.
#[test]
fn a_schema_binding_round_trips_through_the_wire_convention() {
    use jarvisd::broker::{from_value_named, to_value_named};
    use jarvisd::schema::{ActionConfirm, ActionConfirmAnsweredBy, ActionConfirmKind};

    let answer = ActionConfirm {
        kind: ActionConfirmKind::Answer,
        request_id: "req-1".into(),
        tool: None,
        summary: None,
        window_s: None,
        granted: Some(true),
        answered_by: Some(ActionConfirmAnsweredBy::Cli),
    };
    let wire = to_value_named(&answer).unwrap();
    // The enums really are strings on the wire — that is the thing the rmpv
    // deserializer chokes on, so assert it rather than trusting it.
    assert_eq!(jarvisd::cli::get_str(&wire, "kind").as_deref(), Some("answer"));
    assert_eq!(jarvisd::cli::get_str(&wire, "answered_by").as_deref(), Some("cli"));
    assert_eq!(from_value_named::<ActionConfirm>(&wire).unwrap(), answer);

    // A body with a field the schema does not have is refused, not ignored:
    // the bindings are generated with deny_unknown_fields for exactly that.
    let mut extra = wire.as_map().unwrap().clone();
    extra.push(("granted_maybe".into(), true.into()));
    assert!(from_value_named::<ActionConfirm>(&rmpv::Value::Map(extra)).is_err());
}
