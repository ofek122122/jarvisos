//! Append-only audit log (BRIEF-phase2 §2): every action — executed,
//! denied, failed, rejected — leaves a JSONL line. `jv act-log` reads it.

use std::io::Write;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    /// Wall clock, ISO 8601 — audit is for humans reading history.
    pub ts: String,
    /// Monotonic seconds — correlates with bus frames of the same boot.
    pub ts_mono: f64,
    pub request_id: String,
    pub tool: String,
    pub args: serde_json::Value,
    pub capability: String,
    /// ok | denied | confirm_timeout | unknown_tool | invalid_args |
    /// capability_mismatch | execution_failed | timeout
    pub outcome: String,
    pub duration_ms: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub confirm: Option<ConfirmAudit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfirmAudit {
    pub granted: bool,
    pub answered_by: String, // voice | cli | timeout
}

pub fn default_audit_path() -> PathBuf {
    if let Ok(p) = std::env::var("JARVIS_ACT_AUDIT") {
        return p.into();
    }
    if cfg!(unix) {
        "/var/lib/jarvis/act/audit.jsonl".into()
    } else {
        // Windows dev: repo-local state dir (gitignored)
        let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        repo.parent().unwrap().parent().unwrap().join(".state").join("act-audit.jsonl")
    }
}

pub struct AuditLog {
    path: PathBuf,
}

impl AuditLog {
    pub fn new(path: PathBuf) -> Self {
        Self { path }
    }

    /// Append one entry. Failure to audit is a hard error — an action
    /// service that cannot log must not act.
    pub fn append(&self, entry: &AuditEntry) -> anyhow::Result<()> {
        if let Some(dir) = self.path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        let mut f = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(f, "{}", serde_json::to_string(entry)?)?;
        Ok(())
    }
}

pub fn now_iso() -> String {
    // Seconds precision is plenty for an audit trail.
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    let secs = now.as_secs();
    // chrono-free ISO 8601 (UTC)
    let days = secs / 86_400;
    let (h, m, s) = ((secs % 86_400) / 3600, (secs % 3600) / 60, secs % 60);
    // civil-from-days (Howard Hinnant's algorithm)
    let z = days as i64 + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let mth = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if mth <= 2 { y + 1 } else { y };
    format!("{y:04}-{mth:02}-{d:02}T{h:02}:{m:02}:{s:02}Z")
}
