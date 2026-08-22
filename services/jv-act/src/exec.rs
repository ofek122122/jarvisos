//! Tool executors. The Executor trait is the test seam: MockExecutor
//! scripts outcomes; RealExecutor shells out to the machine.
//!
//! REVIEW NOTE (invariant 3): RealExecutor is the complete list of ways
//! jv-act can touch the system in v0. Every arm is a fixed argv — no
//! shell interpolation anywhere, args always passed as discrete argv
//! elements. No uinput, no shell tool (Phase 3+ by design).

use std::process::Stdio;
use std::time::Duration;

use tokio::process::Command;

#[derive(Debug, Clone)]
pub struct ExecOutput {
    pub output: String,
    pub data: Option<serde_json::Value>,
}

#[derive(Debug)]
pub enum ExecError {
    Failed(String),
    Timeout,
}

#[async_trait::async_trait]
pub trait Executor: Send + Sync {
    async fn execute(
        &self,
        tool: &str,
        args: &serde_json::Value,
        timeout: Duration,
    ) -> Result<ExecOutput, ExecError>;
}

fn arg_str<'a>(args: &'a serde_json::Value, key: &str) -> &'a str {
    args.get(key).and_then(|v| v.as_str()).unwrap_or("")
}

fn arg_f64(args: &serde_json::Value, key: &str) -> f64 {
    args.get(key).and_then(|v| v.as_f64()).unwrap_or(0.0)
}

fn arg_u64(args: &serde_json::Value, key: &str) -> u64 {
    args.get(key).and_then(|v| v.as_u64()).unwrap_or(0)
}

async fn run(mut cmd: Command, timeout: Duration) -> Result<ExecOutput, ExecError> {
    cmd.stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    let fut = async {
        let out = cmd.output().await.map_err(|e| ExecError::Failed(e.to_string()))?;
        let stdout = String::from_utf8_lossy(&out.stdout).trim().to_string();
        let stderr = String::from_utf8_lossy(&out.stderr).trim().to_string();
        if out.status.success() {
            Ok(ExecOutput { output: stdout, data: None })
        } else {
            Err(ExecError::Failed(if stderr.is_empty() { stdout } else { stderr }))
        }
    };
    tokio::time::timeout(timeout, fut).await.map_err(|_| ExecError::Timeout)?
}

/// The real thing. TODO(machine): every arm exercised on ares only;
/// exit-checklist items 1–3 and 7 run through here.
pub struct RealExecutor;

#[async_trait::async_trait]
impl Executor for RealExecutor {
    async fn execute(
        &self,
        tool: &str,
        args: &serde_json::Value,
        timeout: Duration,
    ) -> Result<ExecOutput, ExecError> {
        match tool {
            "app.launch" => {
                let mut c = Command::new("gtk-launch");
                c.arg(arg_str(args, "app"));
                run(c, timeout).await.map(|mut o| {
                    o.output = format!("launched {}", arg_str(args, "app"));
                    o
                })
            }
            "window.focus" | "window.close" | "window.move_workspace" => {
                let mut c = Command::new("niri");
                c.arg("msg").arg("action");
                match tool {
                    "window.focus" => {
                        c.arg("focus-window").arg("--id").arg(arg_u64(args, "window_id").to_string());
                    }
                    "window.close" => {
                        c.arg("close-window").arg("--id").arg(arg_u64(args, "window_id").to_string());
                    }
                    _ => {
                        c.arg("move-window-to-workspace").arg(arg_str(args, "workspace"));
                    }
                }
                run(c, timeout).await
            }
            "volume.set" => {
                let level = arg_f64(args, "level").clamp(0.0, 1.5);
                let mut c = Command::new("wpctl");
                c.arg("set-volume").arg("@DEFAULT_AUDIO_SINK@").arg(format!("{level}"));
                run(c, timeout).await
            }
            "volume.adjust" => {
                let delta = arg_f64(args, "delta").clamp(-1.0, 1.0);
                let spec = if delta >= 0.0 {
                    format!("{}%+", (delta * 100.0).round() as i64)
                } else {
                    format!("{}%-", (-delta * 100.0).round() as i64)
                };
                let mut c = Command::new("wpctl");
                c.arg("set-volume").arg("-l").arg("1.5").arg("@DEFAULT_AUDIO_SINK@").arg(spec);
                run(c, timeout).await
            }
            "media.control" => {
                let mut c = Command::new("playerctl");
                c.arg(match arg_str(args, "command") {
                    "play_pause" => "play-pause",
                    "next" => "next",
                    "previous" => "previous",
                    other => return Err(ExecError::Failed(format!("bad command {other}"))),
                });
                run(c, timeout).await
            }
            "file.search" => {
                // read-only by construction: fd/rg only ever list
                let mut c = if args.get("content").and_then(|v| v.as_bool()).unwrap_or(false) {
                    let mut c = Command::new("rg");
                    c.arg("--files-with-matches").arg("--max-count").arg("1");
                    c.arg(arg_str(args, "pattern"));
                    c
                } else {
                    let mut c = Command::new("fd");
                    c.arg("--max-results").arg("20");
                    c.arg(arg_str(args, "pattern"));
                    c
                };
                if !arg_str(args, "dir").is_empty() {
                    c.arg(arg_str(args, "dir"));
                }
                run(c, timeout).await
            }
            "open.item" => {
                let mut c = Command::new("xdg-open");
                c.arg(arg_str(args, "target"));
                run(c, timeout).await
            }
            "unit.status" => {
                let mut c = Command::new("systemctl");
                c.arg("status").arg("--no-pager").arg("--lines").arg("0");
                c.arg(arg_str(args, "unit"));
                run(c, timeout).await
            }
            other => Err(ExecError::Failed(format!("no executor for {other}"))),
        }
    }
}
