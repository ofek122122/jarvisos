//! Shared fixture for the integration tests: a real `Broker` on a real socket
//! (a Unix socket on the machine, loopback TCP elsewhere), torn down with the
//! value.
#![allow(dead_code)]

use jarvisd::broker::{Broker, BusAddr, Config, Listener};
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
