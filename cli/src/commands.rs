//! Clap command definitions (placeholders only).

use std::path::PathBuf;

use clap::{Parser, Subcommand};

/// Usbversal — DJ library database tool for USB-mounted Rekordbox and Serato libraries.
#[derive(Debug, Parser)]
#[command(name = "usbversal", version, about)]
pub struct Cli {
    /// Enable debug logging (`RUST_LOG` still applies).
    #[arg(long, global = true)]
    pub debug: bool,

    /// Workspace or mount path for backups and job state.
    #[arg(long, global = true, default_value = ".")]
    pub workspace: PathBuf,

    #[command(subcommand)]
    pub command: Commands,
}

/// Available subcommands (wired to jobs in `app.rs`).
#[derive(Debug, Subcommand)]
pub enum Commands {
    /// Scan playlists from a database on a USB mount.
    Scan {
        #[arg(long)]
        mount: PathBuf,
        #[arg(long)]
        database: PathBuf,
        #[arg(long, default_value = "rekordbox")]
        vendor: String,
    },
    /// List playlists (read-only job).
    ListPlaylists {
        #[arg(long)]
        mount: PathBuf,
        #[arg(long)]
        database: PathBuf,
    },
    /// Sync operation placeholder.
    Sync {
        #[arg(long)]
        mount: PathBuf,
        #[arg(long)]
        database: PathBuf,
    },
    /// Resume a previously interrupted job by id.
    Resume {
        job_id: String,
    },
    /// Cancel a running job by id.
    Cancel {
        job_id: String,
    },
}
