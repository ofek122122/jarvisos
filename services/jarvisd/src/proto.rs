//! Wire protocol: length-prefixed (u32 BE) MessagePack messages over the
//! bus socket. Client→broker: ClientMsg. Broker→client: ServerMsg.
//! Envelope frames themselves follow schemas/envelope.json.

use serde::{Deserialize, Serialize};
use tokio::io::{AsyncRead, AsyncReadExt};

/// Hard cap per protocol message. Raw sensor frames never ride the bus
/// (invariant 5 — no serialization of raw frames), so this is generous.
pub const MAX_FRAME: u32 = 16 * 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum ClientMsg {
    /// Add subscription patterns (exact topic, prefix `ns.*`, or lone `*`).
    Sub { patterns: Vec<String> },
    /// Remove previously added patterns (exact string match).
    Unsub { patterns: Vec<String> },
    /// Publish one envelope frame.
    Pub { frame: rmpv::Value },
    Ping,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum ServerMsg {
    /// A frame matching one of the connection's subscriptions.
    Frame { frame: rmpv::Value },
    Pong,
    /// A rejected publish (invalid envelope). The frame was not routed.
    Err { msg: String },
}

/// Serialize a protocol message with its length prefix.
pub fn encode<T: Serialize>(msg: &T) -> anyhow::Result<Vec<u8>> {
    let body = rmp_serde::to_vec_named(msg)?;
    anyhow::ensure!(body.len() as u64 <= MAX_FRAME as u64, "message too large");
    let mut out = Vec::with_capacity(body.len() + 4);
    out.extend_from_slice(&(body.len() as u32).to_be_bytes());
    out.extend_from_slice(&body);
    Ok(out)
}

/// Read one protocol message. Ok(None) on clean EOF at a frame boundary.
pub async fn read_msg<T, R>(r: &mut R) -> anyhow::Result<Option<T>>
where
    T: for<'de> Deserialize<'de>,
    R: AsyncRead + Unpin,
{
    let mut len = [0u8; 4];
    match r.read_exact(&mut len).await {
        Ok(_) => {}
        Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => return Ok(None),
        Err(e) => return Err(e.into()),
    }
    let n = u32::from_be_bytes(len);
    anyhow::ensure!(n <= MAX_FRAME, "frame too large: {n} bytes");
    let mut buf = vec![0u8; n as usize];
    r.read_exact(&mut buf).await?;
    Ok(Some(rmp_serde::from_slice(&buf)?))
}

/// Subscription matching (schemas/README.md): exact topic, prefix `ns.*`,
/// or the lone `*` (everything — debug tooling).
pub fn topic_matches(pattern: &str, topic: &str) -> bool {
    if pattern == "*" {
        return true;
    }
    if let Some(prefix) = pattern.strip_suffix(".*") {
        return topic.len() > prefix.len() + 1
            && topic.starts_with(prefix)
            && topic.as_bytes()[prefix.len()] == b'.';
    }
    pattern == topic
}

fn map_get<'a>(m: &'a [(rmpv::Value, rmpv::Value)], key: &str) -> Option<&'a rmpv::Value> {
    m.iter()
        .find(|(k, _)| k.as_str() == Some(key))
        .map(|(_, v)| v)
}

fn as_num(v: &rmpv::Value) -> Option<f64> {
    match v {
        rmpv::Value::Integer(i) => i.as_f64(),
        rmpv::Value::F32(f) => Some(*f as f64),
        rmpv::Value::F64(f) => Some(*f),
        _ => None,
    }
}

/// Structural envelope check (schemas/envelope.json). Full body validation
/// is the endpoints' job via the generated bindings; the broker only
/// guards the envelope so routing and `jv tap` never see garbage.
/// Returns (topic, ts).
pub fn validate_envelope(v: &rmpv::Value) -> Result<(String, f64), String> {
    let m = v.as_map().ok_or("envelope: must be a map")?;
    let topic = map_get(m, "topic")
        .and_then(|v| v.as_str())
        .ok_or("envelope.topic: string required")?;
    let dotted_ok = topic.contains('.')
        && !topic.contains('*')
        && topic
            .split('.')
            .all(|s| {
                !s.is_empty()
                    && s.chars().next().is_some_and(|c| c.is_ascii_lowercase())
                    && s.chars().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_')
            });
    if !dotted_ok {
        return Err(format!("envelope.topic: invalid topic '{topic}'"));
    }
    let ts = map_get(m, "ts")
        .and_then(as_num)
        .ok_or("envelope.ts: number required")?;
    map_get(m, "seq")
        .and_then(|v| v.as_u64())
        .ok_or("envelope.seq: unsigned integer required")?;
    let src = map_get(m, "src")
        .and_then(|v| v.as_str())
        .ok_or("envelope.src: string required")?;
    if src.is_empty() {
        return Err("envelope.src: must be non-empty".into());
    }
    let conf = map_get(m, "conf")
        .and_then(as_num)
        .ok_or("envelope.conf: number required")?;
    if !(0.0..=1.0).contains(&conf) {
        return Err(format!("envelope.conf: {conf} outside [0,1]"));
    }
    let ver = map_get(m, "v")
        .and_then(|v| v.as_u64())
        .ok_or("envelope.v: unsigned integer required")?;
    if ver < 1 {
        return Err("envelope.v: must be >= 1".into());
    }
    if !map_get(m, "body").ok_or("envelope.body: required")?.is_map() {
        return Err("envelope.body: must be a map".into());
    }
    Ok((topic.to_string(), ts))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matching() {
        assert!(topic_matches("*", "audio.wake"));
        assert!(topic_matches("audio.*", "audio.wake"));
        assert!(topic_matches("audio.*", "audio.transcript.partial"));
        assert!(topic_matches("audio.wake", "audio.wake"));
        assert!(!topic_matches("audio.*", "audiofoo.wake"));
        assert!(!topic_matches("audio.*", "audio"));
        assert!(!topic_matches("audio.wake", "audio.vad"));
        assert!(!topic_matches("speech.*", "audio.wake"));
    }

    fn env(topic: &str) -> rmpv::Value {
        rmpv::Value::Map(vec![
            ("topic".into(), topic.into()),
            ("ts".into(), rmpv::Value::F64(1.5)),
            ("seq".into(), rmpv::Value::from(0u64)),
            ("src".into(), "test".into()),
            ("conf".into(), rmpv::Value::F64(1.0)),
            ("v".into(), rmpv::Value::from(1u64)),
            ("body".into(), rmpv::Value::Map(vec![])),
        ])
    }

    #[test]
    fn envelope_validation() {
        assert!(validate_envelope(&env("audio.wake")).is_ok());
        assert!(validate_envelope(&env("nodots")).is_err());
        assert!(validate_envelope(&env("audio.*")).is_err());
        assert!(validate_envelope(&env("Audio.Wake")).is_err());
        assert!(validate_envelope(&rmpv::Value::Nil).is_err());
        // integer ts is accepted (msgpack encoders may compact 12.0 -> 12)
        let mut m = env("audio.wake");
        if let rmpv::Value::Map(pairs) = &mut m {
            pairs[1].1 = rmpv::Value::from(12u64);
        }
        assert!(validate_envelope(&m).is_ok());
    }
}
