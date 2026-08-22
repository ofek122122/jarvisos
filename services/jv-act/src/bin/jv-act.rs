//! jv-act daemon entrypoint.

use std::sync::Arc;

use clap::Parser;
use jarvisd::broker::BusAddr;
use jarvisd::client::BusClient;
use jv_act::audit::{default_audit_path, AuditLog};
use jv_act::exec::RealExecutor;
use jv_act::registry::Registry;
use jv_act::service::{ActConfig, ActService};

#[derive(Parser)]
#[command(name = "jv-act", about = "JarvisOS act — the privileged one")]
struct Args {
    #[arg(long)]
    bus: Option<String>,
    /// Registry TOML. Default: /etc/jarvis/tools.toml, else the in-repo copy.
    #[arg(long)]
    registry: Option<std::path::PathBuf>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .init();
    let args = Args::parse();

    let registry_path = args
        .registry
        .or_else(|| {
            let etc = std::path::PathBuf::from("/etc/jarvis/tools.toml");
            etc.exists().then_some(etc)
        })
        .unwrap_or_else(|| {
            std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tools.toml")
        });
    let registry = Registry::from_toml(&std::fs::read_to_string(&registry_path)?)?;
    tracing::info!("registry: {} ({} tools)", registry_path.display(), registry.tools().count());

    let addr = match &args.bus {
        Some(s) => BusAddr::parse(s)?,
        None => BusAddr::from_env()?,
    };
    let subscriber = BusClient::connect(&addr, "jv-act").await?;
    let publisher = BusClient::connect(&addr, "jv-act").await?;

    let svc = ActService::new(
        registry,
        Arc::new(RealExecutor),
        AuditLog::new(default_audit_path()),
        ActConfig::default(),
    );
    svc.run(subscriber, publisher).await
}
