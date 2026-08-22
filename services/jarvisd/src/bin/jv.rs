//! jv — the bus debug CLI. "This CLI is how we debug everything forever."

use clap::{Parser, Subcommand};
use jarvisd::broker::BusAddr;
use jarvisd::client::BusClient;
use jarvisd::proto::ServerMsg;
use jarvisd::time::mono_now;
use std::collections::HashMap;

#[derive(Parser)]
#[command(name = "jv", about = "JarvisOS bus debug CLI")]
struct Args {
    /// Bus address. Default: $JARVIS_BUS, else the platform default.
    #[arg(long, global = true)]
    bus: Option<String>,

    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Print frames matching the given patterns as JSON lines.
    Sub {
        /// Patterns: exact topic, prefix like 'audio.*', or '*'.
        #[arg(required = true)]
        patterns: Vec<String>,
    },
    /// Publish one frame.
    Pub {
        topic: String,
        /// Body as JSON (default: {}).
        #[arg(long, default_value = "{}")]
        body: String,
        #[arg(long, default_value = "jv-cli")]
        src: String,
        #[arg(long, default_value_t = 1.0)]
        conf: f64,
        /// Body schema version.
        #[arg(long, default_value_t = 1)]
        schema_v: u64,
    },
    /// Watch everything; print per-hop latency, and end-to-end latency
    /// when a speech.say answers a tracked input utterance.
    Tap {
        #[arg(long)]
        latency: bool,
    },
    /// Follow sys.health heartbeats.
    Health,
    /// Read the jv-act audit log (newest last). Path: $JARVIS_ACT_AUDIT
    /// or the platform default.
    ActLog {
        /// Only show the last N entries.
        #[arg(long)]
        tail: Option<usize>,
    },
    /// Answer a pending confirmation request.
    Confirm {
        request_id: String,
        /// 'yes' or 'no'
        answer: String,
    },
}

fn act_audit_path() -> std::path::PathBuf {
    if let Ok(p) = std::env::var("JARVIS_ACT_AUDIT") {
        return p.into();
    }
    if cfg!(unix) {
        "/var/lib/jarvis/act/audit.jsonl".into()
    } else {
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join(".state")
            .join("act-audit.jsonl")
    }
}

fn get<'a>(frame: &'a rmpv::Value, key: &str) -> Option<&'a rmpv::Value> {
    frame.as_map()?.iter().find(|(k, _)| k.as_str() == Some(key)).map(|(_, v)| v)
}

fn get_str(frame: &rmpv::Value, key: &str) -> Option<String> {
    get(frame, key)?.as_str().map(|s| s.to_string())
}

fn get_f64(frame: &rmpv::Value, key: &str) -> Option<f64> {
    match get(frame, key)? {
        rmpv::Value::Integer(i) => i.as_f64(),
        rmpv::Value::F32(f) => Some(*f as f64),
        rmpv::Value::F64(f) => Some(*f),
        _ => None,
    }
}

fn to_json(v: &rmpv::Value) -> String {
    serde_json::to_string(v).unwrap_or_else(|e| format!("<unprintable: {e}>"))
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    let addr = match &args.bus {
        Some(s) => BusAddr::parse(s)?,
        None => BusAddr::from_env()?,
    };

    match args.cmd {
        Cmd::Sub { patterns } => {
            let mut c = BusClient::connect(&addr, "jv-cli").await?;
            let pats: Vec<&str> = patterns.iter().map(|s| s.as_str()).collect();
            c.subscribe(&pats).await?;
            while let Some(frame) = c.next_frame().await? {
                println!("{}", to_json(&frame));
            }
        }

        Cmd::Pub { topic, body, src, conf, schema_v } => {
            let json: serde_json::Value = serde_json::from_str(&body)?;
            let body = rmpv::ext::to_value(&json)?;
            let mut c = BusClient::connect(&addr, &src).await?;
            let seq = c.publish(&topic, conf, schema_v, body).await?;
            // Give the broker a beat to reject an invalid envelope.
            match tokio::time::timeout(std::time::Duration::from_millis(150), c.next_event()).await
            {
                Ok(Ok(Some(ServerMsg::Err { msg }))) => anyhow::bail!("rejected: {msg}"),
                _ => println!("published {topic} seq={seq}"),
            }
        }

        Cmd::Tap { latency } => {
            let mut c = BusClient::connect(&addr, "jv-tap").await?;
            c.subscribe(&["*"]).await?;
            // input utterance_id -> ts first seen (audio.vad speech_start
            // or first transcript frame)
            let mut utt_start: HashMap<String, f64> = HashMap::new();
            while let Some(frame) = c.next_frame().await? {
                let topic = get_str(&frame, "topic").unwrap_or_default();
                let src = get_str(&frame, "src").unwrap_or_default();
                let seq = get_f64(&frame, "seq").unwrap_or(-1.0) as i64;
                let ts = get_f64(&frame, "ts").unwrap_or(0.0);
                let now = mono_now();
                if latency {
                    let hop_ms = (now - ts) * 1e3;
                    println!("{topic:<20} {src:<12} seq={seq:<8} hop={hop_ms:8.2}ms");
                } else {
                    println!("{}", to_json(&frame));
                }
                let body = match get(&frame, "body") {
                    Some(b) => b.clone(),
                    None => continue,
                };
                match topic.as_str() {
                    "audio.vad" | "audio.transcript" => {
                        if let Some(id) = get_str(&body, "utterance_id") {
                            utt_start.entry(id).or_insert(ts);
                        }
                    }
                    "speech.say" => {
                        if let Some(id) = get_str(&body, "in_reply_to_utterance") {
                            if let Some(t0) = utt_start.get(&id) {
                                let e2e_ms = (now - t0) * 1e3;
                                println!(">>> end-to-end {id}: {e2e_ms:.0}ms (VAD start -> speech.say)");
                            }
                        }
                    }
                    _ => {}
                }
            }
        }

        Cmd::ActLog { tail } => {
            let path = act_audit_path();
            let text = std::fs::read_to_string(&path)
                .map_err(|e| anyhow::anyhow!("no audit log at {}: {e}", path.display()))?;
            let lines: Vec<&str> = text.lines().collect();
            let start = tail.map(|n| lines.len().saturating_sub(n)).unwrap_or(0);
            for line in &lines[start..] {
                let Ok(e) = serde_json::from_str::<serde_json::Value>(line) else {
                    continue;
                };
                let confirm = e
                    .get("confirm")
                    .map(|c| {
                        format!(
                            " confirm={}/{}",
                            c["granted"].as_bool().unwrap_or(false),
                            c["answered_by"].as_str().unwrap_or("?")
                        )
                    })
                    .unwrap_or_default();
                println!(
                    "{} {:<22} {:<11} {:<18} {:>7.0}ms{} args={}",
                    e["ts"].as_str().unwrap_or("?"),
                    e["tool"].as_str().unwrap_or("?"),
                    e["capability"].as_str().unwrap_or("?"),
                    e["outcome"].as_str().unwrap_or("?"),
                    e["duration_ms"].as_f64().unwrap_or(0.0),
                    confirm,
                    e["args"]
                );
            }
        }

        Cmd::Confirm { request_id, answer } => {
            let granted = match answer.as_str() {
                "yes" | "y" => true,
                "no" | "n" => false,
                other => anyhow::bail!("answer must be yes or no, got '{other}'"),
            };
            let mut c = BusClient::connect(&addr, "jv-cli").await?;
            let body = rmpv::Value::Map(vec![
                ("kind".into(), "answer".into()),
                ("request_id".into(), request_id.as_str().into()),
                ("granted".into(), granted.into()),
                ("answered_by".into(), "cli".into()),
            ]);
            c.publish("action.confirm", 1.0, 1, body).await?;
            println!("answer sent: {request_id} -> {}", if granted { "yes" } else { "no" });
        }

        Cmd::Health => {
            let mut c = BusClient::connect(&addr, "jv-health").await?;
            c.subscribe(&["sys.health"]).await?;
            while let Some(frame) = c.next_frame().await? {
                let body = get(&frame, "body").cloned().unwrap_or(rmpv::Value::Nil);
                let service = get_str(&body, "service").unwrap_or_default();
                let state = get_str(&body, "state").unwrap_or_default();
                let uptime = get_f64(&body, "uptime_s").unwrap_or(0.0);
                let drops = get(&body, "drops").map(to_json).unwrap_or_else(|| "-".into());
                let notes = get_str(&body, "notes").unwrap_or_default();
                println!("{service:<12} {state:<9} up={uptime:9.1}s drops={drops} {notes}");
            }
        }
    }
    Ok(())
}
