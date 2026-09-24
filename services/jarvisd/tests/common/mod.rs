//! Shared fixture for the integration tests: a real `Broker` on a real socket
//! (a Unix socket on the machine, loopback TCP elsewhere), torn down with the
//! value.
#![allow(dead_code)]

use jarvisd::broker::{Broker, BusAddr, Config, Listener};
use jarvisd::client::BusClient;
use std::sync::Arc;

pub struct TestBus {
    pub addr: BusAddr,
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

impl TestBus {
    /// The address spelled the way `jv --bus` takes it.
    pub fn bus_arg(&self) -> String {
        self.addr.to_string()
    }
}

pub async fn start(cfg: Config) -> TestBus {
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

/// A msgpack map body from key/value pairs.
pub fn body(pairs: &[(&str, rmpv::Value)]) -> rmpv::Value {
    rmpv::Value::Map(pairs.iter().map(|(k, v)| ((*k).into(), v.clone())).collect())
}

/// Topic used only to prove a subscription is live. See `subscribe_live`.
pub const PROBE_TOPIC: &str = "jv.probe.sub";

/// Subscribe, and PROVE the subscription is live before returning.
///
/// The broker does not ack a `Sub`, so "subscribe, then start a one-shot
/// publisher" is a race: `jv confirm` publishes once and exits, and a test that
/// lost that race would be a flake in an unattended gate. Probing with frames
/// of our own until one comes back is the only observable that the patterns are
/// registered — later probe echoes are skipped by `next_frame_of`.
pub async fn subscribe_live(bus: &TestBus, c: &mut BusClient, patterns: &[&str]) {
    let mut pats = patterns.to_vec();
    pats.push(PROBE_TOPIC);
    c.subscribe(&pats).await.expect("subscribe");
    let mut probe = BusClient::connect(&bus.addr, "probe").await.expect("probe connect");
    let t0 = tokio::time::Instant::now();
    loop {
        assert!(t0.elapsed().as_secs_f64() < 5.0, "subscription never went live");
        probe.publish(PROBE_TOPIC, 1.0, 1, body(&[])).await.expect("probe publish");
        if let Ok(Ok(Some(f))) =
            tokio::time::timeout(std::time::Duration::from_millis(50), c.next_frame()).await
        {
            if jarvisd::cli::get_str(&f, "topic").as_deref() == Some(PROBE_TOPIC) {
                return;
            }
        }
    }
}

/// The next frame on `topic`, skipping everything else (probe echoes, the
/// broker's own heartbeat). None if `limit_s` passes without one — "nothing was
/// published" has to be assertable, not a hang.
pub async fn next_frame_of(c: &mut BusClient, topic: &str, limit_s: f64) -> Option<rmpv::Value> {
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs_f64(limit_s);
    loop {
        let left = deadline.saturating_duration_since(tokio::time::Instant::now());
        if left.is_zero() {
            return None;
        }
        match tokio::time::timeout(left, c.next_frame()).await {
            Ok(Ok(Some(f))) => {
                if jarvisd::cli::get_str(&f, "topic").as_deref() == Some(topic) {
                    return Some(f);
                }
            }
            Ok(Ok(None)) | Ok(Err(_)) => return None,
            Err(_) => return None,
        }
    }
}
