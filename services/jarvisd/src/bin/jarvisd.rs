//! jarvisd — the bus broker daemon.

use clap::Parser;
use jarvisd::broker::{Broker, BusAddr, Config, Listener};

#[derive(Parser)]
#[command(name = "jarvisd", about = "JarvisOS bus broker")]
struct Args {
    /// Socket path (Linux) or host:port. Default: $JARVIS_BUS, else
    /// /run/jarvis/bus.sock (Linux) / 127.0.0.1:7451 (dev).
    #[arg(long)]
    bus: Option<String>,

    /// Per-subscriber out-queue capacity (overflow drops oldest).
    #[arg(long, default_value_t = 1024)]
    queue: usize,

    /// sys.health heartbeat period, seconds.
    #[arg(long, default_value_t = 5.0)]
    health_period: f64,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    let args = Args::parse();
    let addr = match &args.bus {
        Some(s) => BusAddr::parse(s)?,
        None => BusAddr::from_env()?,
    };
    let cfg = Config {
        subscriber_queue: args.queue,
        health_period: std::time::Duration::from_secs_f64(args.health_period),
        ..Config::default()
    };

    let (listener, actual) = Listener::bind(&addr).await?;
    tracing::info!("jarvisd listening on {actual}");

    let broker = Broker::new(cfg);
    let task = broker.spawn(listener);

    tokio::signal::ctrl_c().await?;
    tracing::info!("shutting down");
    task.abort();

    #[cfg(unix)]
    if let BusAddr::Unix(p) = &actual {
        let _ = std::fs::remove_file(p);
    }
    Ok(())
}
