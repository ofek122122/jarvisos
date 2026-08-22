//! The jv-act service loop.
//!
//! Flow per intent.action:
//!   validate tool → validate args → re-derive capability from the
//!   registry (mismatch = reject) → confirm if destructive+ (blocks the
//!   REQUEST, never the service) → execute with timeout → action.result
//!   → audit line. Denials and rejections are audited too.
//!
//! Confirmation: publish action.confirm{kind=request} + dialog.listen
//! (scoped no-wake window, reason=confirm), then wait for the first of:
//! a yes/no-class transcript final, an action.confirm{kind=answer} from
//! the CLI, or the timeout (=> denied, answered_by=timeout).

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use jarvisd::broker::to_value_named;
use jarvisd::client::BusClient;
use jarvisd::time::mono_now;
use tokio::sync::{oneshot, Mutex};

use crate::audit::{AuditEntry, AuditLog, ConfirmAudit, now_iso};
use crate::exec::{ExecError, Executor};
use crate::registry::Registry;

pub struct ActConfig {
    pub confirm_window_s: f64,
    pub health_period_s: f64,
}

impl Default for ActConfig {
    fn default() -> Self {
        Self { confirm_window_s: 15.0, health_period_s: 5.0 }
    }
}

const YES: &[&str] = &["yes", "yeah", "yep", "sure", "go ahead", "do it", "confirm", "affirmative"];
const NO: &[&str] = &["no", "nope", "cancel", "stop", "dont", "don't", "negative", "deny"];

/// Whole-utterance yes/no classification for the confirm window.
/// Anything ambiguous is ignored (the window keeps listening).
pub fn classify_answer(text: &str) -> Option<bool> {
    let norm: String = text
        .to_lowercase()
        .chars()
        .filter(|c| c.is_alphanumeric() || c.is_whitespace() || *c == '\'')
        .collect();
    let norm = norm.split_whitespace().collect::<Vec<_>>().join(" ");
    if YES.contains(&norm.as_str()) {
        return Some(true);
    }
    if NO.contains(&norm.as_str()) {
        return Some(false);
    }
    None
}

struct Pending {
    tx: oneshot::Sender<(bool, &'static str)>, // (granted, answered_by)
}

pub struct ActService {
    registry: Registry,
    executor: Arc<dyn Executor>,
    audit: Arc<AuditLog>,
    cfg: ActConfig,
    pending: Arc<Mutex<HashMap<String, Pending>>>,
}

fn get<'a>(frame: &'a rmpv::Value, key: &str) -> Option<&'a rmpv::Value> {
    frame.as_map()?.iter().find(|(k, _)| k.as_str() == Some(key)).map(|(_, v)| v)
}

fn body_json(frame: &rmpv::Value) -> serde_json::Value {
    get(frame, "body")
        .and_then(|b| serde_json::to_value(b).ok())
        .unwrap_or(serde_json::Value::Null)
}

impl ActService {
    pub fn new(
        registry: Registry,
        executor: Arc<dyn Executor>,
        audit: AuditLog,
        cfg: ActConfig,
    ) -> Self {
        Self {
            registry,
            executor,
            audit: Arc::new(audit),
            cfg,
            pending: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub async fn run(self, mut bus: BusClient, mut publisher: BusClient) -> anyhow::Result<()> {
        bus.subscribe(&["intent.action", "action.confirm", "audio.transcript"]).await?;
        let (tx_out, mut rx_out) = tokio::sync::mpsc::channel::<(String, rmpv::Value)>(64);

        // Single writer task owns the publishing connection.
        let writer = tokio::spawn(async move {
            let started = std::time::Instant::now();
            let mut health = tokio::time::interval(Duration::from_secs_f64(5.0));
            loop {
                tokio::select! {
                    Some((topic, body)) = rx_out.recv() => {
                        let _ = publisher.publish(&topic, 1.0, 1, body).await;
                    }
                    _ = health.tick() => {
                        let body = serde_json::json!({
                            "service": "jv-act",
                            "state": "ok",
                            "uptime_s": started.elapsed().as_secs_f64(),
                            "period_s": 5.0,
                        });
                        if let Ok(v) = to_value_named(&body) {
                            let _ = publisher.publish("sys.health", 1.0, 1, v).await;
                        }
                    }
                }
            }
        });

        loop {
            let frame = match bus.next_frame().await? {
                Some(f) => f,
                None => break,
            };
            let topic = get(&frame, "topic").and_then(|v| v.as_str()).unwrap_or("");
            match topic {
                "intent.action" => {
                    let body = body_json(&frame);
                    self.spawn_request(body, tx_out.clone());
                }
                "action.confirm" => {
                    let body = body_json(&frame);
                    if body.get("kind").and_then(|v| v.as_str()) == Some("answer") {
                        // CLI-sourced answer; ours carry answered_by we set.
                        if let (Some(rid), Some(granted)) = (
                            body.get("request_id").and_then(|v| v.as_str()),
                            body.get("granted").and_then(|v| v.as_bool()),
                        ) {
                            let by = body.get("answered_by").and_then(|v| v.as_str());
                            if by == Some("cli") {
                                self.resolve(rid, granted, "cli").await;
                            }
                        }
                    }
                }
                "audio.transcript" => {
                    let body = body_json(&frame);
                    let is_final = body.get("kind").and_then(|v| v.as_str()) == Some("final");
                    if is_final {
                        if let Some(text) = body.get("text").and_then(|v| v.as_str()) {
                            if let Some(granted) = classify_answer(text) {
                                // First pending request wins; v0 has at
                                // most one confirm outstanding in practice.
                                let rid = {
                                    let g = self.pending.lock().await;
                                    g.keys().next().cloned()
                                };
                                if let Some(rid) = rid {
                                    self.resolve(&rid, granted, "voice").await;
                                }
                            }
                        }
                    }
                }
                _ => {}
            }
        }
        writer.abort();
        Ok(())
    }

    async fn resolve(&self, request_id: &str, granted: bool, by: &'static str) {
        if let Some(p) = self.pending.lock().await.remove(request_id) {
            let _ = p.tx.send((granted, by));
        }
    }

    fn spawn_request(
        &self,
        body: serde_json::Value,
        out: tokio::sync::mpsc::Sender<(String, rmpv::Value)>,
    ) {
        let registry = self.registry.clone();
        let executor = self.executor.clone();
        let audit = self.audit.clone();
        let pending = self.pending.clone();
        let confirm_window = self.cfg.confirm_window_s;

        tokio::spawn(async move {
            let t0 = mono_now();
            let rid = body.get("request_id").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let tool = body.get("tool").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let args = body.get("args").cloned().unwrap_or(serde_json::json!({}));
            let claimed_cap = body.get("capability").and_then(|v| v.as_str()).unwrap_or("");

            let send = |topic: &str, val: serde_json::Value, out: &tokio::sync::mpsc::Sender<(String, rmpv::Value)>| {
                let topic = topic.to_string();
                let out = out.clone();
                async move {
                    if let Ok(v) = to_value_named(&val) {
                        let _ = out.send((topic, v)).await;
                    }
                }
            };

            let mut confirm_audit: Option<ConfirmAudit> = None;

            // -------- validation gauntlet
            let spec = match registry.get(&tool) {
                Some(s) => s.clone(),
                None => {
                    // hallucinated tool: reject, audit, done
                    send("action.result", serde_json::json!({
                        "request_id": rid, "ok": false, "duration_ms": (mono_now()-t0)*1e3,
                        "error": "unknown_tool",
                        "detail": format!("no tool named '{tool}' in the registry"),
                    }), &out).await;
                    let _ = audit.append(&AuditEntry {
                        ts: now_iso(), ts_mono: t0, request_id: rid, tool, args,
                        capability: "unknown".into(), outcome: "unknown_tool".into(),
                        duration_ms: (mono_now() - t0) * 1e3, confirm: None, detail: None,
                    });
                    return;
                }
            };

            if let Err(msg) = Registry::validate_args(&spec, &args) {
                send("action.result", serde_json::json!({
                    "request_id": rid, "ok": false, "duration_ms": (mono_now()-t0)*1e3,
                    "error": "invalid_args", "detail": msg,
                }), &out).await;
                let _ = audit.append(&AuditEntry {
                    ts: now_iso(), ts_mono: t0, request_id: rid, tool, args,
                    capability: spec.capability.as_str().into(), outcome: "invalid_args".into(),
                    duration_ms: (mono_now() - t0) * 1e3, confirm: None, detail: None,
                });
                return;
            }

            if !claimed_cap.is_empty() && claimed_cap != spec.capability.as_str() {
                send("action.result", serde_json::json!({
                    "request_id": rid, "ok": false, "duration_ms": (mono_now()-t0)*1e3,
                    "error": "capability_mismatch",
                    "detail": format!("claimed {claimed_cap}, registry says {}", spec.capability.as_str()),
                }), &out).await;
                let _ = audit.append(&AuditEntry {
                    ts: now_iso(), ts_mono: t0, request_id: rid, tool, args,
                    capability: spec.capability.as_str().into(),
                    outcome: "capability_mismatch".into(),
                    duration_ms: (mono_now() - t0) * 1e3, confirm: None, detail: None,
                });
                return;
            }

            // -------- confirmation (destructive+, structural rule)
            if spec.capability.needs_confirmation() {
                let (tx, rx) = oneshot::channel();
                pending.lock().await.insert(rid.clone(), Pending { tx });

                send("action.confirm", serde_json::json!({
                    "kind": "request", "request_id": rid, "tool": tool,
                    "summary": format!("{} — yes or no?", spec.description),
                    "window_s": confirm_window,
                }), &out).await;
                send("dialog.listen", serde_json::json!({
                    "listen_id": rid, "window_s": confirm_window, "reason": "confirm",
                }), &out).await;

                let (granted, by) = match tokio::time::timeout(
                    Duration::from_secs_f64(confirm_window),
                    rx,
                ).await {
                    Ok(Ok(ans)) => ans,
                    _ => {
                        pending.lock().await.remove(&rid);
                        (false, "timeout")
                    }
                };
                // publish the answer for observability (incl. timeout)
                send("action.confirm", serde_json::json!({
                    "kind": "answer", "request_id": rid,
                    "granted": granted, "answered_by": by,
                }), &out).await;
                confirm_audit = Some(ConfirmAudit { granted, answered_by: by.into() });

                if !granted {
                    let error = if by == "timeout" { "confirm_timeout" } else { "denied" };
                    send("action.result", serde_json::json!({
                        "request_id": rid, "ok": false, "duration_ms": (mono_now()-t0)*1e3,
                        "error": error,
                    }), &out).await;
                    let _ = audit.append(&AuditEntry {
                        ts: now_iso(), ts_mono: t0, request_id: rid, tool, args,
                        capability: spec.capability.as_str().into(), outcome: error.into(),
                        duration_ms: (mono_now() - t0) * 1e3, confirm: confirm_audit, detail: None,
                    });
                    return;
                }
            }

            // -------- execute
            // speak.notify is bus-internal: it publishes speech.say
            // rather than spawning anything (the one tool whose effect
            // IS a bus frame).
            if tool == "speak.notify" {
                let text = args.get("text").and_then(|v| v.as_str()).unwrap_or("").to_string();
                send("speech.say", serde_json::json!({
                    "text": text, "say_id": uuid::Uuid::new_v4().to_string(),
                    "in_reply_to_utterance": null,
                }), &out).await;
                send("action.result", serde_json::json!({
                    "request_id": rid, "ok": true,
                    "duration_ms": (mono_now()-t0)*1e3, "output": "spoken",
                }), &out).await;
                let _ = audit.append(&AuditEntry {
                    ts: now_iso(), ts_mono: t0, request_id: rid, tool, args,
                    capability: spec.capability.as_str().into(), outcome: "ok".into(),
                    duration_ms: (mono_now() - t0) * 1e3, confirm: confirm_audit, detail: None,
                });
                return;
            }

            let timeout = Duration::from_millis(spec.timeout_ms);
            let (outcome, result_body) = match executor.execute(&tool, &args, timeout).await {
                Ok(o) => {
                    let mut rb = serde_json::json!({
                        "request_id": rid, "ok": true,
                        "duration_ms": (mono_now()-t0)*1e3, "output": o.output,
                    });
                    if let Some(d) = o.data {
                        rb["data"] = d;
                    }
                    ("ok".to_string(), rb)
                }
                Err(ExecError::Timeout) => ("timeout".into(), serde_json::json!({
                    "request_id": rid, "ok": false,
                    "duration_ms": (mono_now()-t0)*1e3, "error": "timeout",
                })),
                Err(ExecError::Failed(msg)) => ("execution_failed".into(), serde_json::json!({
                    "request_id": rid, "ok": false,
                    "duration_ms": (mono_now()-t0)*1e3,
                    "error": "execution_failed", "detail": msg,
                })),
            };
            send("action.result", result_body, &out).await;
            let _ = audit.append(&AuditEntry {
                ts: now_iso(), ts_mono: t0, request_id: rid, tool, args,
                capability: spec.capability.as_str().into(), outcome,
                duration_ms: (mono_now() - t0) * 1e3, confirm: confirm_audit, detail: None,
            });
        });
    }
}
