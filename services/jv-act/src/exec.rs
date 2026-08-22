//! Tool executors. The Executor trait is the test seam: MockExecutor
//! scripts outcomes; RealExecutor shells out to the machine.
//!
//! REVIEW NOTE (invariant 3): `plan_commands` is the COMPLETE list of
//! ways jv-act can touch the system in v0, expressed as pure data
//! (argv vectors) so it can be unit-tested without spawning anything.
//! Every argv is fixed-shape — no shell, ever — and every user-supplied
//! positional string is guarded against flag injection with a `--`
//! terminator (or, for the xdg-open wrapper which doesn't honor `--`, a
//! leading-dash rejection). No uinput, no shell tool (Phase 3+).

use std::process::Stdio;
use std::time::Duration;

use serde_json::Value;
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

fn arg_str<'a>(args: &'a Value, key: &str) -> &'a str {
    args.get(key).and_then(|v| v.as_str()).unwrap_or("")
}

fn arg_f64(args: &Value, key: &str) -> f64 {
    args.get(key).and_then(|v| v.as_f64()).unwrap_or(0.0)
}

fn arg_u64(args: &Value, key: &str) -> u64 {
    args.get(key).and_then(|v| v.as_u64()).unwrap_or(0)
}

fn s(v: &str) -> String {
    v.to_string()
}

/// Build the argv command(s) for a tool. Returns one or more argv
/// vectors to run IN SEQUENCE (window.move_workspace is focus-then-move).
/// Pure and total: the only side effect is deciding what would run, so
/// tests assert on it directly. Flag-injection defenses live here.
pub fn plan_commands(tool: &str, args: &Value) -> Result<Vec<Vec<String>>, ExecError> {
    let cmds: Vec<Vec<String>> = match tool {
        "app.launch" => {
            let app = arg_str(args, "app");
            // gtk-launch parses GOption; `--` ends flags.
            vec![vec![s("gtk-launch"), s("--"), s(app)]]
        }
        "window.focus" => vec![vec![
            s("niri"), s("msg"), s("action"), s("focus-window"),
            s("--id"), arg_u64(args, "window_id").to_string(),
        ]],
        "window.close" => vec![vec![
            s("niri"), s("msg"), s("action"), s("close-window"),
            s("--id"), arg_u64(args, "window_id").to_string(),
        ]],
        "window.move_workspace" => {
            // Fix: the window_id must not be dropped. Some niri versions
            // target move-window-to-workspace by id, some don't; focus
            // the named window first, then move it — atomic from the
            // brain's perspective (one action.result).
            let wid = arg_u64(args, "window_id").to_string();
            let ws = arg_str(args, "workspace");
            vec![
                vec![s("niri"), s("msg"), s("action"), s("focus-window"), s("--id"), wid],
                vec![
                    s("niri"), s("msg"), s("action"),
                    s("move-window-to-workspace"), s("--"), s(ws),
                ],
            ]
        }
        "volume.set" => {
            let level = arg_f64(args, "level").clamp(0.0, 1.5);
            vec![vec![
                s("wpctl"), s("set-volume"), s("@DEFAULT_AUDIO_SINK@"), format!("{level}"),
            ]]
        }
        "volume.adjust" => {
            let delta = arg_f64(args, "delta").clamp(-1.0, 1.0);
            let spec = if delta >= 0.0 {
                format!("{}%+", (delta * 100.0).round() as i64)
            } else {
                format!("{}%-", (-delta * 100.0).round() as i64)
            };
            vec![vec![
                s("wpctl"), s("set-volume"), s("-l"), s("1.5"),
                s("@DEFAULT_AUDIO_SINK@"), spec,
            ]]
        }
        "media.control" => {
            let cmd = match arg_str(args, "command") {
                "play_pause" => "play-pause",
                "next" => "next",
                "previous" => "previous",
                other => return Err(ExecError::Failed(format!("bad command {other}"))),
            };
            vec![vec![s("playerctl"), s(cmd)]]
        }
        "file.search" => {
            // read-only by construction (fd/rg only list). `--` guards
            // the user pattern/dir from being parsed as flags — rg's
            // --pre and friends can execute, so this matters.
            let pattern = arg_str(args, "pattern");
            let dir = arg_str(args, "dir");
            let mut argv = if args.get("content").and_then(|v| v.as_bool()).unwrap_or(false) {
                vec![s("rg"), s("--files-with-matches"), s("--max-count"), s("1"), s("--"), s(pattern)]
            } else {
                vec![s("fd"), s("--max-results"), s("20"), s("--"), s(pattern)]
            };
            if !dir.is_empty() {
                argv.push(s(dir));
            }
            vec![argv]
        }
        "open.item" => {
            let target = arg_str(args, "target");
            // xdg-open is a shell wrapper that does not honor `--`, so
            // the defense here is an explicit leading-dash rejection.
            if target.is_empty() || target.starts_with('-') {
                return Err(ExecError::Failed(
                    "refusing a target that is empty or looks like a flag".into(),
                ));
            }
            vec![vec![s("xdg-open"), s(target)]]
        }
        "unit.status" => vec![vec![
            s("systemctl"), s("status"), s("--no-pager"), s("--lines"), s("0"),
            s("--"), s(arg_str(args, "unit")),
        ]],
        other => return Err(ExecError::Failed(format!("no executor for {other}"))),
    };
    Ok(cmds)
}

#[async_trait::async_trait]
pub trait Executor: Send + Sync {
    async fn execute(
        &self,
        tool: &str,
        args: &Value,
        timeout: Duration,
    ) -> Result<ExecOutput, ExecError>;
}

async fn run_argv(argv: &[String], timeout: Duration) -> Result<ExecOutput, ExecError> {
    let (prog, rest) = argv.split_first().ok_or(ExecError::Failed("empty argv".into()))?;
    let mut cmd = Command::new(prog);
    cmd.args(rest);
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
        args: &Value,
        timeout: Duration,
    ) -> Result<ExecOutput, ExecError> {
        let plans = plan_commands(tool, args)?;
        let mut last = ExecOutput { output: String::new(), data: None };
        for argv in &plans {
            last = run_argv(argv, timeout).await?;
        }
        Ok(last)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn move_workspace_keeps_the_window_id() {
        let cmds = plan_commands(
            "window.move_workspace",
            &json!({"window_id": 42, "workspace": "web"}),
        )
        .unwrap();
        assert_eq!(cmds.len(), 2, "focus then move");
        assert!(cmds[0].contains(&"42".to_string()), "focus targets the id: {:?}", cmds[0]);
        assert!(cmds[0].contains(&"focus-window".to_string()));
        assert!(cmds[1].contains(&"move-window-to-workspace".to_string()));
        assert!(cmds[1].contains(&"web".to_string()));
    }

    #[test]
    fn user_positionals_are_flag_guarded() {
        // every arm that takes a user string terminates flags with `--`
        let fd = &plan_commands("file.search", &json!({"pattern": "-x"})).unwrap()[0];
        assert!(fd.contains(&"--".to_string()));
        assert_eq!(fd.last().unwrap(), "-x"); // the dangerous pattern is a positional

        let rg = &plan_commands(
            "file.search", &json!({"pattern": "--pre=evil", "content": true}),
        ).unwrap()[0];
        let dd = rg.iter().position(|a| a == "--").unwrap();
        assert!(rg[dd + 1] == "--pre=evil"); // after the terminator, inert

        let launch = &plan_commands("app.launch", &json!({"app": "-foo"})).unwrap()[0];
        assert!(launch.contains(&"--".to_string()));

        let unit = &plan_commands("unit.status", &json!({"unit": "-h"})).unwrap()[0];
        assert!(unit.contains(&"--".to_string()));
    }

    #[test]
    fn open_item_rejects_flag_targets() {
        assert!(plan_commands("open.item", &json!({"target": "-h"})).is_err());
        assert!(plan_commands("open.item", &json!({"target": "--version"})).is_err());
        assert!(plan_commands("open.item", &json!({"target": ""})).is_err());
        assert!(plan_commands("open.item", &json!({"target": "https://ok"})).is_ok());
    }

    #[test]
    fn media_rejects_unknown_command() {
        assert!(plan_commands("media.control", &json!({"command": "rm -rf"})).is_err());
        assert!(plan_commands("media.control", &json!({"command": "next"})).is_ok());
    }
}
