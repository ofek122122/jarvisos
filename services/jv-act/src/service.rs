//! The jv-act service loop.
//!
//! Flow per intent.action:
//!   validate tool → validate args → re-derive capability from the
//!   registry (mismatch = reject) → confirm if destructive+ (blocks the
//!   REQUEST, never the service) → AUDIT INTENT (refuse if it can't be
//!   logged) → execute with timeout → action.result → audit outcome.
//!
//! Confirmation (destructive+): at most ONE confirmation is outstanding
//! at a time — a second destructive intent while one pends is denied.
//! We publish action.confirm{kind=request} + dialog.listen (scoped
//! no-wake window, reason=confirm), then wait for the first of: a
//! yes/no-class transcript final WHOSE ENVELOPE ts FALLS INSIDE THE OPEN
//! WINDOW, an action.confirm{kind=answer} from the CLI, or the timeout
//! (=> denied). A stray "no" from ordinary conversation cannot resolve a
//! confirm: there is at most one window, and the transcript must land
//! inside its [start, start+window_s]. (The airtight fix — a listen_id
//! on audio.transcript — is logged in DECISIONS for the next schema bump.)

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use jarvisd::broker::to_value_named;
use jarvisd::client::BusClient;
use jarvisd::time::mono_now;
use tokio::sync::{oneshot, Mutex};

use crate::audit::{now_iso, AuditEntry, AuditLog, ConfirmAudit};
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
    window_start: f64,
    window_end: f64,
}

pub struct ActService {
    registry: Registry,
    executor: Arc<dyn Executor>,
    audit: Arc<AuditLog>,
    cfg: ActConfig,
    // At most one entry (single-outstanding-confirmation invariant), but a
    // map keeps request_id correlation explicit for the CLI answer path.
    pending: Arc<Mutex<HashMap<String, Pending>>>,
}

fn get<'a>(frame: &'a rmpv::Value, key: &str) -> Option<&'a rmpv::Value> {
    frame.as_map()?.iter().find(|(k, _)| k.as_str() == Some(key)).map(|(_, v)| v)
}

fn as_f64(v: &rmpv::Value) -> Option<f64> {
    match v {
        rmpv::Value::F64(f) => Some(*f),
        rmpv::Value::F32(f) => Some(*f as f64),
        rmpv::Value::Integer(i) => i.as_f64(),
        _ => None,
    }
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
                        // Only the CLI's OWN answers (answered_by=cli) are
                        // acted on; act's own request/answer echoes are
                        // ignored here (they set answered_by=voice/timeout).
                        if let (Some(rid), Some(granted), Some("cli")) = (
                            body.get("request_id").and_then(|v| v.as_str()),
                            body.get("granted").and_then(|v| v.as_bool()),
                            body.get("answered_by").and_then(|v| v.as_str()),
                        ) {
                            self.resolve_cli(rid, granted).await;
                        }
                    }
                }
                "audio.transcript" => {
                    // A yes/no final only counts if it lands inside the
                    // ONE open confirm window (envelope ts vs the window).
                    let ts = get(&frame, "ts").and_then(as_f64);
                    let body = body_json(&frame);
                    let is_final = body.get("kind").and_then(|v| v.as_str()) == Some("final");
                    if is_final {
                        if let (Some(text), Some(ts)) =
                            (body.get("text").and_then(|v| v.as_str()), ts)
                        {
                            if let Some(granted) = classify_answer(text) {
                                self.resolve_voice(granted, ts).await;
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

    /// CLI answer: explicit by request_id, so no time check needed.
    async fn resolve_cli(&self, request_id: &str, granted: bool) {
        if let Some(p) = self.pending.lock().await.remove(request_id) {
            let _ = p.tx.send((granted, "cli"));
        }
    }

    /// Voice answer: accept only if the single pending confirm's window
    /// is open at the transcript's timestamp. A yes/no with no window
    /// open, or one landing outside the window, is ignored.
    async fn resolve_voice(&self, granted: bool, ts: f64) {
        let mut g = self.pending.lock().await;
        let hit = g
            .iter()
            .find(|(_, p)| p.window_start <= ts && ts <= p.window_end)
            .map(|(rid, _)| rid.clone());
        if let Some(rid) = hit {
            if let Some(p) = g.remove(&rid) {
                let _ = p.tx.send((granted, "voice"));
            }
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

            // Audit helper: log-on-error for non-critical (rejection /
            // outcome) lines. The CRITICAL intent line is handled inline
            // and refuses execution on failure.
            let audit_soft = |entry: AuditEntry| {
                if let Err(e) = audit.append(&entry) {
                    tracing::error!("audit write failed: {e}");
                }
            };

            let mk = |outcome: &str, cap: &str, confirm: Option<ConfirmAudit>, detail: Option<String>| AuditEntry {
                ts: now_iso(), ts_mono: t0, request_id: rid.clone(), tool: tool.clone(),
                args: args.clone(), capability: cap.to_string(), outcome: outcome.to_string(),
                duration_ms: (mono_now() - t0) * 1e3, confirm, detail,
            };

            let mut confirm_audit: Option<ConfirmAudit> = None;

            // -------- validation gauntlet
            let spec = match registry.get(&tool) {
                Some(s) => s.clone(),
                None => {
                    send("action.result", serde_json::json!({
                        "request_id": rid, "ok": false, "duration_ms": (mono_now()-t0)*1e3,
                        "error": "unknown_tool",
                        "detail": format!("no tool named '{tool}' in the registry"),
                    }), &out).await;
                    audit_soft(mk("unknown_tool", "unknown", None, None));
                    return;
                }
            };
            let cap = spec.capability.as_str();

            if let Err(msg) = Registry::validate_args(&spec, &args) {
                send("action.result", serde_json::json!({
                    "request_id": rid, "ok": false, "duration_ms": (mono_now()-t0)*1e3,
                    "error": "invalid_args", "detail": msg,
                }), &out).await;
                audit_soft(mk("invalid_args", cap, None, None));
                return;
            }

            if !claimed_cap.is_empty() && claimed_cap != cap {
                send("action.result", serde_json::json!({
                    "request_id": rid, "ok": false, "duration_ms": (mono_now()-t0)*1e3,
                    "error": "capability_mismatch",
                    "detail": format!("claimed {claimed_cap}, registry says {cap}"),
                }), &out).await;
                audit_soft(mk("capability_mismatch", cap, None, None));
                return;
            }

            // -------- confirmation (destructive+, structural rule)
            if spec.capability.needs_confirmation() {
                // Single-outstanding: reserve the sole confirm slot, or
                // deny if one is already pending. Reusing the `denied`
                // error keeps the frozen v1 action.result body unchanged.
                let rx = {
                    let mut g = pending.lock().await;
                    if !g.is_empty() {
                        None
                    } else {
                        let (tx, rx) = oneshot::channel();
                        let ws = mono_now();
                        g.insert(rid.clone(), Pending {
                            tx, window_start: ws, window_end: ws + confirm_window,
                        });
                        Some(rx)
                    }
                };
                let rx = match rx {
                    Some(rx) => rx,
                    None => {
                        send("action.result", serde_json::json!({
                            "request_id": rid, "ok": false,
                            "duration_ms": (mono_now()-t0)*1e3, "error": "denied",
                            "detail": "another confirmation is already pending",
                        }), &out).await;
                        audit_soft(mk("denied", cap, None,
                            Some("another confirmation pending".into())));
                        return;
                    }
                };

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
                    audit_soft(mk(error, cap, confirm_audit, None));
                    return;
                }
            }

            // -------- AUDIT INTENT BEFORE EXECUTION (invariant 3 doctrine:
            // a service that cannot log must not act). If this write
            // fails, refuse to execute — nothing touches the machine
            // without a durable record that it was about to.
            if let Err(e) = audit.append(&mk("intent", cap, confirm_audit.clone(), None)) {
                tracing::error!("intent audit write failed, refusing to act: {e}");
                send("action.result", serde_json::json!({
                    "request_id": rid, "ok": false, "duration_ms": (mono_now()-t0)*1e3,
                    "error": "execution_failed",
                    "detail": "audit log unavailable; refusing to act",
                }), &out).await;
                return;
            }

            // -------- execute
            // speak.notify is bus-internal: its effect IS a bus frame.
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
                audit_soft(mk("ok", cap, confirm_audit, None));
                return;
            }

            let timeout = Duration::from_millis(spec.timeout_ms);
            let (outcome, result_body, detail) = match executor.execute(&tool, &args, timeout).await {
                Ok(o) => {
                    let mut rb = serde_json::json!({
                        "request_id": rid, "ok": true,
                        "duration_ms": (mono_now()-t0)*1e3, "output": o.output,
                    });
                    if let Some(d) = o.data {
                        rb["data"] = d;
                    }
                    ("ok".to_string(), rb, None)
                }
                Err(ExecError::Timeout) => ("timeout".into(), serde_json::json!({
                    "request_id": rid, "ok": false,
                    "duration_ms": (mono_now()-t0)*1e3, "error": "timeout",
                }), None),
                Err(ExecError::Failed(msg)) => ("execution_failed".into(), serde_json::json!({
                    "request_id": rid, "ok": false,
                    "duration_ms": (mono_now()-t0)*1e3,
                    "error": "execution_failed", "detail": msg.clone(),
                }), Some(msg)),
            };
            send("action.result", result_body, &out).await;
            audit_soft(mk(&outcome, cap, confirm_audit, detail));
        });
    }
}
