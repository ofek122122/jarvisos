//! The broker core: topic pub/sub with a strict never-block-the-publisher
//! policy (CLAUDE.md invariant 5). Slow consumers get drop-oldest on their
//! private out-queue; drops are reported on `sys.health`.

use std::collections::{BTreeMap, HashMap, VecDeque};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tokio::io::{AsyncRead, AsyncWrite, AsyncWriteExt};
use tokio::sync::{broadcast, Notify, RwLock};

use crate::proto::{self, ClientMsg, ServerMsg};
use crate::schema::{Envelope, SysHealth, SysHealthState, TOPIC_SYS_HEALTH, V_SYS_HEALTH};
use crate::time::mono_now;

/// Anything a connection can ride on (UnixStream on the machine,
/// TcpStream for Windows-side development).
pub trait Conn: AsyncRead + AsyncWrite + Send + Unpin {}
impl<T: AsyncRead + AsyncWrite + Send + Unpin> Conn for T {}

#[derive(Clone, Debug)]
pub struct Config {
    /// Per-subscriber out-queue capacity; overflow drops the OLDEST frame.
    pub subscriber_queue: usize,
    /// Shared broadcast ring; a receiver lagging past this is force-skipped
    /// (counted as drops under "_lagged").
    pub channel_capacity: usize,
    /// sys.health heartbeat period.
    pub health_period: Duration,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            subscriber_queue: 1024,
            channel_capacity: 4096,
            health_period: Duration::from_secs(5),
        }
    }
}

/// One routed frame, encoded once at publish time and shared by all
/// subscribers (publishers never pay per-subscriber costs).
pub struct Delivery {
    pub topic: String,
    pub wire: Vec<u8>,
}

#[derive(Default)]
struct ConnDrops {
    per_topic: Mutex<HashMap<String, u64>>,
}

impl ConnDrops {
    fn add(&self, topic: &str, n: u64) {
        *self.per_topic.lock().unwrap().entry(topic.to_string()).or_default() += n;
    }
    fn drain(&self) -> HashMap<String, u64> {
        std::mem::take(&mut self.per_topic.lock().unwrap())
    }
}

enum QItem {
    Frame(Arc<Delivery>),
    Ctl(Vec<u8>),
}

/// Bounded per-connection out-queue with drop-oldest overflow.
struct OutQueue {
    cap: usize,
    inner: Mutex<QInner>,
    notify: Notify,
    drops: Arc<ConnDrops>,
}

struct QInner {
    q: VecDeque<QItem>,
    closed: bool,
}

impl OutQueue {
    fn new(cap: usize, drops: Arc<ConnDrops>) -> Self {
        Self {
            cap: cap.max(1),
            inner: Mutex::new(QInner {
                q: VecDeque::new(),
                closed: false,
            }),
            notify: Notify::new(),
            drops,
        }
    }

    fn push(&self, item: QItem) {
        {
            let mut g = self.inner.lock().unwrap();
            if g.closed {
                return;
            }
            if g.q.len() >= self.cap {
                match g.q.pop_front() {
                    Some(QItem::Frame(d)) => self.drops.add(&d.topic, 1),
                    Some(QItem::Ctl(_)) => self.drops.add("_ctl", 1),
                    None => {}
                }
            }
            g.q.push_back(item);
        }
        self.notify.notify_one();
    }

    async fn pop(&self) -> Option<QItem> {
        loop {
            {
                let mut g = self.inner.lock().unwrap();
                if let Some(x) = g.q.pop_front() {
                    return Some(x);
                }
                if g.closed {
                    return None;
                }
            }
            self.notify.notified().await;
        }
    }

    fn close(&self) {
        self.inner.lock().unwrap().closed = true;
        self.notify.notify_one();
    }
}

pub struct Broker {
    cfg: Config,
    tx: broadcast::Sender<Arc<Delivery>>,
    conns: Mutex<HashMap<u64, Arc<ConnDrops>>>,
    next_conn: AtomicU64,
    own_seq: AtomicU64,
    started: std::time::Instant,
}

impl Broker {
    pub fn new(cfg: Config) -> Arc<Self> {
        let (tx, _) = broadcast::channel(cfg.channel_capacity);
        Arc::new(Self {
            cfg,
            tx,
            conns: Mutex::new(HashMap::new()),
            next_conn: AtomicU64::new(0),
            own_seq: AtomicU64::new(0),
            started: std::time::Instant::now(),
        })
    }

    /// Route a validated envelope. Never blocks: broadcast + per-conn
    /// drop-oldest absorb any slow consumer.
    pub fn publish_value(&self, topic: String, frame: rmpv::Value) {
        let wire = match proto::encode(&ServerMsg::Frame { frame }) {
            Ok(w) => w,
            Err(e) => {
                tracing::error!("encode failed for {topic}: {e}");
                return;
            }
        };
        // Err only means "no subscribers right now" — fine.
        let _ = self.tx.send(Arc::new(Delivery { topic, wire }));
    }

    fn publish_own<T: serde::Serialize>(&self, topic: &str, v: u32, body: &T) {
        let body = match rmpv::ext::to_value(body) {
            Ok(b) => b,
            Err(e) => {
                tracing::error!("health body encode: {e}");
                return;
            }
        };
        let env = Envelope {
            topic: topic.to_string(),
            ts: mono_now(),
            seq: self.own_seq.fetch_add(1, Ordering::SeqCst),
            src: "jarvisd".to_string(),
            conf: 1.0,
            v: v as u64,
            body,
        };
        match rmpv::ext::to_value(&env) {
            Ok(frame) => self.publish_value(topic.to_string(), frame),
            Err(e) => tracing::error!("health envelope encode: {e}"),
        }
    }

    fn publish_health(&self) {
        let mut drops: BTreeMap<String, u64> = BTreeMap::new();
        for c in self.conns.lock().unwrap().values() {
            for (t, n) in c.drain() {
                *drops.entry(t).or_default() += n;
            }
        }
        let body = SysHealth {
            service: "jarvisd".to_string(),
            state: SysHealthState::Ok,
            uptime_s: self.started.elapsed().as_secs_f64(),
            period_s: self.cfg.health_period.as_secs_f64(),
            drops: if drops.is_empty() { None } else { Some(drops) },
            metrics: None,
            notes: None,
        };
        self.publish_own(TOPIC_SYS_HEALTH, V_SYS_HEALTH, &body);
    }

    /// Accept loop + health heartbeat. Runs until the task is aborted.
    pub fn spawn(self: &Arc<Self>, listener: Listener) -> tokio::task::JoinHandle<()> {
        let broker = self.clone();
        tokio::spawn(async move {
            let health = {
                let b = broker.clone();
                tokio::spawn(async move {
                    let mut iv = tokio::time::interval(b.cfg.health_period);
                    iv.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
                    loop {
                        iv.tick().await;
                        b.publish_health();
                    }
                })
            };
            loop {
                match listener.accept().await {
                    Ok(stream) => {
                        let b = broker.clone();
                        tokio::spawn(async move { handle_conn(b, stream).await });
                    }
                    Err(e) => {
                        tracing::error!("accept: {e}");
                        break;
                    }
                }
            }
            health.abort();
        })
    }
}

async fn handle_conn(broker: Arc<Broker>, stream: Box<dyn Conn>) {
    let (mut r, mut w) = tokio::io::split(stream);

    let drops = Arc::new(ConnDrops::default());
    let id = broker.next_conn.fetch_add(1, Ordering::SeqCst);
    broker.conns.lock().unwrap().insert(id, drops.clone());

    let patterns: Arc<RwLock<Vec<String>>> = Arc::new(RwLock::new(Vec::new()));
    let queue = Arc::new(OutQueue::new(broker.cfg.subscriber_queue, drops.clone()));

    // broadcast -> (filter) -> out-queue. Always fast: the slow part
    // (the socket write) lives behind the drop-oldest queue.
    let forward = {
        let mut rx = broker.tx.subscribe();
        let patterns = patterns.clone();
        let queue = queue.clone();
        let drops = drops.clone();
        tokio::spawn(async move {
            loop {
                match rx.recv().await {
                    Ok(d) => {
                        let pats = patterns.read().await;
                        if pats.iter().any(|p| proto::topic_matches(p, &d.topic)) {
                            queue.push(QItem::Frame(d));
                        }
                    }
                    Err(broadcast::error::RecvError::Lagged(n)) => drops.add("_lagged", n),
                    Err(broadcast::error::RecvError::Closed) => break,
                }
            }
        })
    };

    // out-queue -> socket
    let writer = {
        let queue = queue.clone();
        tokio::spawn(async move {
            while let Some(item) = queue.pop().await {
                let bytes = match &item {
                    QItem::Frame(d) => &d.wire,
                    QItem::Ctl(b) => b,
                };
                if w.write_all(bytes).await.is_err() {
                    break;
                }
            }
        })
    };

    // read loop
    loop {
        match proto::read_msg::<ClientMsg, _>(&mut r).await {
            Ok(Some(ClientMsg::Sub { patterns: ps })) => {
                let mut g = patterns.write().await;
                for p in ps {
                    if !g.contains(&p) {
                        g.push(p);
                    }
                }
            }
            Ok(Some(ClientMsg::Unsub { patterns: ps })) => {
                patterns.write().await.retain(|p| !ps.contains(p));
            }
            Ok(Some(ClientMsg::Pub { frame })) => match proto::validate_envelope(&frame) {
                Ok((topic, _ts)) => broker.publish_value(topic, frame),
                Err(msg) => {
                    if let Ok(wire) = proto::encode(&ServerMsg::Err { msg }) {
                        queue.push(QItem::Ctl(wire));
                    }
                }
            },
            Ok(Some(ClientMsg::Ping)) => {
                if let Ok(wire) = proto::encode(&ServerMsg::Pong) {
                    queue.push(QItem::Ctl(wire));
                }
            }
            Ok(None) => break,
            Err(e) => {
                tracing::debug!("conn {id}: {e}");
                break;
            }
        }
    }

    forward.abort();
    queue.close();
    let _ = writer.await;
    broker.conns.lock().unwrap().remove(&id);
}

// ---------------------------------------------------------------- listener

/// Bus address: a Unix socket path (the real thing, /run/jarvis/bus.sock)
/// or host:port TCP (Windows-side development and tests only).
#[derive(Clone, Debug)]
pub enum BusAddr {
    #[cfg(unix)]
    Unix(std::path::PathBuf),
    Tcp(String),
}

impl std::fmt::Display for BusAddr {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            #[cfg(unix)]
            BusAddr::Unix(p) => write!(f, "{}", p.display()),
            BusAddr::Tcp(a) => write!(f, "{a}"),
        }
    }
}

impl BusAddr {
    pub fn parse(s: &str) -> anyhow::Result<Self> {
        if s.parse::<std::net::SocketAddr>().is_ok() {
            return Ok(BusAddr::Tcp(s.to_string()));
        }
        #[cfg(unix)]
        {
            Ok(BusAddr::Unix(s.into()))
        }
        #[cfg(not(unix))]
        {
            anyhow::bail!("'{s}': on this platform the bus address must be host:port")
        }
    }

    /// $JARVIS_BUS, else the platform default.
    pub fn from_env() -> anyhow::Result<Self> {
        if let Ok(s) = std::env::var("JARVIS_BUS") {
            return Self::parse(&s);
        }
        #[cfg(unix)]
        {
            Ok(BusAddr::Unix("/run/jarvis/bus.sock".into()))
        }
        #[cfg(not(unix))]
        {
            Ok(BusAddr::Tcp("127.0.0.1:7451".to_string()))
        }
    }
}

pub enum Listener {
    #[cfg(unix)]
    Unix(tokio::net::UnixListener),
    Tcp(tokio::net::TcpListener),
}

impl Listener {
    /// Bind, returning the listener and the actual address (TCP port 0 is
    /// resolved to the assigned port — used by tests).
    pub async fn bind(addr: &BusAddr) -> anyhow::Result<(Self, BusAddr)> {
        match addr {
            #[cfg(unix)]
            BusAddr::Unix(path) => {
                if let Some(dir) = path.parent() {
                    std::fs::create_dir_all(dir)?;
                }
                // A stale socket file from a previous run blocks bind.
                let _ = std::fs::remove_file(path);
                let l = tokio::net::UnixListener::bind(path)?;
                Ok((Listener::Unix(l), BusAddr::Unix(path.clone())))
            }
            BusAddr::Tcp(a) => {
                let l = tokio::net::TcpListener::bind(a).await?;
                let actual = BusAddr::Tcp(l.local_addr()?.to_string());
                Ok((Listener::Tcp(l), actual))
            }
        }
    }

    pub async fn accept(&self) -> std::io::Result<Box<dyn Conn>> {
        match self {
            #[cfg(unix)]
            Listener::Unix(l) => {
                let (s, _) = l.accept().await?;
                Ok(Box::new(s))
            }
            Listener::Tcp(l) => {
                let (s, _) = l.accept().await?;
                s.set_nodelay(true).ok();
                Ok(Box::new(s))
            }
        }
    }
}
