//! Minimal async bus client — used by the `jv` CLI and the integration
//! tests. Python services get their own client in services/pylib.

use crate::broker::{BusAddr, Conn};
use crate::proto::{self, ClientMsg, ServerMsg};
use crate::time::mono_now;
use tokio::io::{AsyncWriteExt, ReadHalf, WriteHalf};

pub struct BusClient {
    r: ReadHalf<Box<dyn Conn>>,
    w: WriteHalf<Box<dyn Conn>>,
    src: String,
    seq: u64,
}

impl BusClient {
    pub async fn connect(addr: &BusAddr, src: &str) -> anyhow::Result<Self> {
        let stream: Box<dyn Conn> = match addr {
            #[cfg(unix)]
            BusAddr::Unix(p) => Box::new(tokio::net::UnixStream::connect(p).await?),
            BusAddr::Tcp(a) => {
                let s = tokio::net::TcpStream::connect(a).await?;
                s.set_nodelay(true).ok();
                Box::new(s)
            }
        };
        let (r, w) = tokio::io::split(stream);
        Ok(Self {
            r,
            w,
            src: src.to_string(),
            seq: 0,
        })
    }

    async fn send(&mut self, msg: &ClientMsg) -> anyhow::Result<()> {
        let wire = proto::encode(msg)?;
        self.w.write_all(&wire).await?;
        Ok(())
    }

    pub async fn subscribe(&mut self, patterns: &[&str]) -> anyhow::Result<()> {
        self.send(&ClientMsg::Sub {
            patterns: patterns.iter().map(|s| s.to_string()).collect(),
        })
        .await
    }

    /// Publish a body on a topic, building the envelope (ts = mono now,
    /// per-client seq). Returns the seq used.
    pub async fn publish(
        &mut self,
        topic: &str,
        conf: f64,
        v: u64,
        body: rmpv::Value,
    ) -> anyhow::Result<u64> {
        let seq = self.seq;
        self.seq += 1;
        let frame = rmpv::Value::Map(vec![
            ("topic".into(), topic.into()),
            ("ts".into(), rmpv::Value::F64(mono_now())),
            ("seq".into(), rmpv::Value::from(seq)),
            ("src".into(), self.src.as_str().into()),
            ("conf".into(), rmpv::Value::F64(conf)),
            ("v".into(), rmpv::Value::from(v)),
            ("body".into(), body),
        ]);
        self.publish_env(frame).await?;
        Ok(seq)
    }

    /// Publish a pre-built envelope frame verbatim.
    pub async fn publish_env(&mut self, frame: rmpv::Value) -> anyhow::Result<()> {
        self.send(&ClientMsg::Pub { frame }).await
    }

    /// Next protocol message from the broker. None on EOF.
    pub async fn next_event(&mut self) -> anyhow::Result<Option<ServerMsg>> {
        proto::read_msg(&mut self.r).await
    }

    /// Next frame, skipping Pong; a broker Err becomes an error.
    pub async fn next_frame(&mut self) -> anyhow::Result<Option<rmpv::Value>> {
        loop {
            match self.next_event().await? {
                None => return Ok(None),
                Some(ServerMsg::Frame { frame }) => return Ok(Some(frame)),
                Some(ServerMsg::Pong) => continue,
                Some(ServerMsg::Err { msg }) => anyhow::bail!("broker rejected publish: {msg}"),
            }
        }
    }
}
