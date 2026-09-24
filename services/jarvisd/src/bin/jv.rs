//! jv — the bus debug CLI. "This CLI is how we debug everything forever."
//!
//! Every streaming subcommand is bounded: `-n/--count` stops after N frames,
//! `--for` after a wall-clock budget, Ctrl-C at any time. Unbounded streams are
//! fine to watch but impossible to script or assert on, and an unmet `--count`
//! exits non-zero so a caller can tell "here is the frame" from "the bus went
//! away". The reasoning (latency accounting, utterance tracking, formatting,
//! exit policy) lives in `jarvisd::cli` where it is unit-tested; this file is
//! argument parsing and one select loop.

use clap::{Parser, Subcommand};
use jarvisd::broker::BusAddr;
use jarvisd::cli::{self, HopStats, Outcome, Utterances};
use jarvisd::client::BusClient;
use jarvisd::proto::ServerMsg;
use jarvisd::time::mono_now;
use std::io::Write;
use std::time::Duration;

/// How many input utterances a tap remembers. Far past any plausible
/// conversational overlap, and bounded because `jv tap` is meant to be left
/// running for hours.
const UTTERANCE_MEMORY: usize = 256;

#[derive(Parser)]
#[command(name = "jv", about = "JarvisOS bus debug CLI")]
struct Args {
    /// Bus address. Default: $JARVIS_BUS, else the platform default.
    #[arg(long, global = true)]
    bus: Option<String>,

    /// Stop after N frames (sub/tap/health). Exits non-zero if the stream ends
    /// with fewer than N delivered.
    #[arg(short = 'n', long, global = true, value_name = "N")]
    count: Option<usize>,

    /// Stop after SECS seconds (sub/tap/health).
    #[arg(long = "for", global = true, value_name = "SECS")]
    for_secs: Option<f64>,

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
    /// Watch everything; with --latency print per-hop latency, the end-to-end
    /// time to first word for each tracked utterance, and a percentile summary
    /// when the stream stops.
    Tap {
        #[arg(long)]
        latency: bool,
    },
    /// Follow sys.health heartbeats; with --check, answer once whether this
    /// machine is well.
    Health {
        /// Listen for one window (--for SECS, default 6 — a heartbeat period
        /// plus a margin), then print one line per service HEARD FROM, worst
        /// first, and exit 0 only if every one of them is `ok`. Nothing on
        /// the bus says which services are supposed to be running, so a
        /// service that never started is absent from the report, not failed;
        /// the footer states the window so absence can be weighed.
        #[arg(long, conflicts_with = "count")]
        check: bool,
    },
    /// Read the jv-act audit log (newest last). Path: $JARVIS_ACT_AUDIT
    /// or the platform default. Exits non-zero if the log is missing, if any
    /// line in it could not be read as an audit entry, or if --since/--failed/
    /// --outcome were given and nothing matched (grep's rule, so
    /// `jv act-log --failed || echo all clean` means something).
    ActLog {
        /// Only show the last N of whatever matched.
        #[arg(long, value_name = "N")]
        tail: Option<usize>,

        /// Only entries at or after this: a duration back from now (10m, 2h,
        /// 90s, 3d) or a UTC timestamp (2026-09-24, 2026-09-24T10:00:00Z).
        #[arg(long, value_name = "WHEN")]
        since: Option<String>,

        /// Only entries jv-act did not record as 'ok'.
        #[arg(long, conflicts_with = "outcome")]
        failed: bool,

        /// Only entries with this outcome; repeatable. jv-act writes ok,
        /// denied, confirm_timeout, unknown_tool, invalid_args,
        /// capability_mismatch, execution_failed, timeout.
        #[arg(long, value_name = "WORD")]
        outcome: Vec<String>,
    },
    /// Answer a pending confirmation request.
    Confirm {
        request_id: String,
        /// 'yes' or 'no'
        answer: String,
    },
}

/// How a stream stopped, and how many frames it delivered.
struct Run {
    outcome: Outcome,
    seen: usize,
}

/// A deadline as a future. `None` never fires.
async fn at(deadline: Option<tokio::time::Instant>) {
    match deadline {
        Some(t) => tokio::time::sleep_until(t).await,
        None => std::future::pending().await,
    }
}

/// Drive a subscription until `--count` frames, `--for` seconds, Ctrl-C, or the
/// broker closing — whichever comes first.
async fn drive(
    c: &mut BusClient,
    count: Option<usize>,
    for_secs: Option<f64>,
    mut on_frame: impl FnMut(rmpv::Value),
) -> anyhow::Result<Run> {
    if count == Some(0) {
        return Ok(Run { outcome: Outcome::Count, seen: 0 });
    }
    let deadline = for_secs.map(|s| tokio::time::Instant::now() + Duration::from_secs_f64(s.max(0.0)));
    // Registered ONCE and polled across every iteration: a fresh ctrl_c()
    // future per iteration can drop a signal that lands while we are printing,
    // and Ctrl-C is how an interactive tap asks for its summary.
    let ctrl_c = tokio::signal::ctrl_c();
    tokio::pin!(ctrl_c);
    let mut seen = 0usize;
    loop {
        // biased: an elapsed deadline or a pending Ctrl-C wins over a frame
        // that happens to be ready, so --for is a real bound under load.
        let frame = tokio::select! {
            biased;
            _ = &mut ctrl_c => return Ok(Run { outcome: Outcome::Interrupted, seen }),
            _ = at(deadline) => return Ok(Run { outcome: Outcome::Deadline, seen }),
            f = c.next_frame() => f?,
        };
        let Some(frame) = frame else {
            return Ok(Run { outcome: Outcome::BusClosed, seen });
        };
        seen += 1;
        on_frame(frame);
        if count.is_some_and(|n| seen >= n) {
            return Ok(Run { outcome: Outcome::Count, seen });
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let Args { bus, count, for_secs, cmd } = Args::parse();
    let addr = match &bus {
        Some(s) => BusAddr::parse(s)?,
        None => BusAddr::from_env()?,
    };

    let code = match cmd {
        Cmd::Sub { patterns } => {
            let mut c = BusClient::connect(&addr, "jv-cli").await?;
            let pats: Vec<&str> = patterns.iter().map(|s| s.as_str()).collect();
            c.subscribe(&pats).await?;
            let run = drive(&mut c, count, for_secs, |frame| {
                println!("{}", cli::to_json(&frame));
            })
            .await?;
            cli::exit_code(run.outcome, count, run.seen)
        }

        Cmd::Pub { topic, body, src, conf, schema_v } => {
            let json: serde_json::Value = serde_json::from_str(&body)?;
            let body = rmpv::ext::to_value(&json)?;
            let mut c = BusClient::connect(&addr, &src).await?;
            let seq = c.publish(&topic, conf, schema_v, body).await?;
            // Give the broker a beat to reject an invalid envelope.
            match tokio::time::timeout(Duration::from_millis(150), c.next_event()).await {
                Ok(Ok(Some(ServerMsg::Err { msg }))) => anyhow::bail!("rejected: {msg}"),
                _ => println!("published {topic} seq={seq}"),
            }
            0
        }

        Cmd::Tap { latency } => {
            let mut c = BusClient::connect(&addr, "jv-tap").await?;
            c.subscribe(&["*"]).await?;
            let mut stats = HopStats::default();
            let mut utts = Utterances::with_capacity(UTTERANCE_MEMORY);
            let run = drive(&mut c, count, for_secs, |frame| {
                let topic = cli::get_str(&frame, "topic").unwrap_or_default();
                let ts = cli::get_f64(&frame, "ts").unwrap_or(0.0);
                let now = mono_now();
                if latency {
                    let src = cli::get_str(&frame, "src").unwrap_or_default();
                    let seq = cli::get_f64(&frame, "seq").unwrap_or(-1.0) as i64;
                    let hop_ms = (now - ts) * 1e3;
                    println!("{topic:<20} {src:<12} seq={seq:<8} hop={hop_ms:8.2}ms");
                    stats.hop(&topic, hop_ms);
                } else {
                    println!("{}", cli::to_json(&frame));
                }
                let Some(body) = cli::get(&frame, "body") else { return };
                match topic.as_str() {
                    "audio.vad" | "audio.transcript" => {
                        if let Some(id) = cli::get_str(body, "utterance_id") {
                            utts.saw(&id, ts);
                        }
                    }
                    "speech.say" => {
                        if let Some(id) = cli::get_str(body, "in_reply_to_utterance") {
                            // Only the FIRST reply frame: a streamed reply is
                            // many speech.say frames for one utterance, and
                            // only the first is time-to-first-word.
                            if let Some(ms) = utts.first_reply_ms(&id, now) {
                                println!(">>> end-to-end {id}: {ms:.0}ms (VAD start -> first speech.say)");
                                stats.e2e(ms);
                            }
                        }
                    }
                    _ => {}
                }
            })
            .await?;
            if latency {
                print!("{}", stats.summary());
            }
            cli::exit_code(run.outcome, count, run.seen)
        }

        Cmd::ActLog { tail, since, failed, outcome } => {
            let filter = cli::ActLogFilter {
                tail,
                // Parsed BEFORE the file is opened: a malformed --since is the
                // caller's mistake, and printing a log first would bury it.
                since: since.map(|s| cli::parse_since(&s, cli::now_epoch())).transpose().map_err(anyhow::Error::msg)?,
                outcome: if failed {
                    Some(cli::OutcomeFilter::NotOk)
                } else if outcome.is_empty() {
                    None
                } else {
                    Some(cli::OutcomeFilter::AnyOf(outcome))
                },
            };
            let path = cli::act_audit_path();
            let text = std::fs::read_to_string(&path)
                .map_err(|e| anyhow::anyhow!("no audit log at {}: {e}", path.display()))?;
            let log = cli::act_log_render(&text, &filter);
            for line in &log.lines {
                println!("{line}");
            }
            if log.unreadable > 0 {
                eprintln!(
                    "warning: {} line(s) of {} could not be read as audit entries",
                    log.unreadable,
                    path.display()
                );
            }
            // Nothing is said about an empty match: on a healthy machine
            // `--failed` matching nothing is the GOOD answer, and a warning
            // every time would train a human to ignore this command.
            cli::act_log_exit_code(&log)
        }

        Cmd::Confirm { request_id, answer } => {
            let granted = match answer.as_str() {
                "yes" | "y" => true,
                "no" | "n" => false,
                other => anyhow::bail!("answer must be yes or no, got '{other}'"),
            };
            let mut c = BusClient::connect(&addr, "jv-cli").await?;
            // The shape jv-act acts on: kind=answer + request_id + granted +
            // answered_by="cli" (services/jv-act/src/service.rs ignores an
            // answer that is not the CLI's own, since it echoes its own
            // voice/timeout answers on this same topic). Pinned by
            // `confirm_publishes_the_answer_jv_act_resolves` in tests/cli.rs.
            let body = rmpv::Value::Map(vec![
                ("kind".into(), "answer".into()),
                ("request_id".into(), request_id.as_str().into()),
                ("granted".into(), granted.into()),
                ("answered_by".into(), "cli".into()),
            ]);
            c.publish("action.confirm", 1.0, 1, body).await?;
            println!("answer sent: {request_id} -> {}", if granted { "yes" } else { "no" });
            0
        }

        Cmd::Health { check: false } => {
            let mut c = BusClient::connect(&addr, "jv-health").await?;
            c.subscribe(&["sys.health"]).await?;
            let run = drive(&mut c, count, for_secs, |frame| {
                let body = cli::get(&frame, "body").cloned().unwrap_or(rmpv::Value::Nil);
                println!("{}", cli::health_line(&body));
            })
            .await?;
            cli::exit_code(run.outcome, count, run.seen)
        }

        Cmd::Health { check: true } => {
            let window = for_secs.unwrap_or(cli::HEALTH_CHECK_WINDOW_S);
            let mut c = BusClient::connect(&addr, "jv-health").await?;
            c.subscribe(&["sys.health"]).await?;
            let mut heard = cli::HealthCheck::default();
            // Ctrl-C ends the window early and still answers: an impatient
            // reader gets the report for as long as we listened, which the
            // footer states, rather than nothing at all.
            drive(&mut c, None, Some(window), |frame| heard.observe(&frame)).await?;
            // ONE reading of the clock for the whole report, so two lines of
            // the same answer cannot disagree about when "now" was.
            let now = mono_now();
            let report = heard.report(now);
            for w in &report {
                println!("{}", cli::wellbeing_line(w));
            }
            if let Some(line) = heard.llm_line(now, cli::BRAIN) {
                println!("{line}");
            }
            println!("{}", cli::health_check_footer(&report, window));
            cli::health_check_exit(&report)
        }
    };

    std::io::stdout().flush().ok();
    std::process::exit(code)
}
