//! Application wiring: parses CLI, delegates to `usbversal-jobs` (no domain logic).

use std::sync::Arc;

use anyhow::Context;
use tokio::signal;
use usbversal_core::job::JobId;
use usbversal_jobs::resume::FileStateStore;
use usbversal_jobs::JobExecutor;
use usbversal_storage::backup::BackupManager;

use crate::commands::{Cli, Commands};
use crate::output::JsonLineEventSink;

/// Runs the parsed CLI command.
pub async fn run(cli: Cli) -> anyhow::Result<()> {
    let events: Arc<dyn usbversal_core::EventSink> = Arc::new(JsonLineEventSink);
    let state_dir = cli.workspace.join(".usbversal").join("jobs");
    let state_store = FileStateStore::new(state_dir);
    let executor = JobExecutor::new(state_store, events);

    let _backup_manager = BackupManager::new(cli.workspace.join("backups"));

    match cli.command {
        Commands::Scan { mount: _, database: _, vendor } => {
            tracing::info!(vendor = %vendor, "scan requested (placeholder)");
            let (job_id, handle) = executor.start_playlist_scan(3);
            tracing::info!(job_id = %job_id.0, "job started");
            tokio::select! {
                res = handle => res??,
                _ = signal::ctrl_c() => {
                    executor.cancel(&job_id).await.ok();
                    anyhow::bail!("interrupted");
                }
            }
        }
        Commands::ListPlaylists { mount, database } => {
            tracing::info!(mount = %mount.display(), database = %database.display(), "list playlists (placeholder)");
        }
        Commands::Sync { mount, database } => {
            tracing::info!(mount = %mount.display(), database = %database.display(), "sync (placeholder)");
        }
        Commands::Resume { job_id } => {
            let id = parse_job_id(&job_id)?;
            let task = Box::new(usbversal_jobs::tasks::ScanTask::new(
                usbversal_core::job::JobKind::PlaylistScan,
                3,
            ));
            executor.resume_job(&id, task).await?;
        }
        Commands::Cancel { job_id } => {
            let id = parse_job_id(&job_id)?;
            executor.cancel(&id).await.context("cancel job")?;
        }
    }

    Ok(())
}

fn parse_job_id(s: &str) -> anyhow::Result<JobId> {
    let uuid = uuid::Uuid::parse_str(s).context("invalid job UUID")?;
    Ok(JobId(uuid))
}
