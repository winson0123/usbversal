use std::path::{Path, PathBuf};

use chrono::Utc;
use tracing::{info, instrument};

use crate::error::StorageError;

/// Default subdirectory name when the manager root is the workspace (not the backups folder itself).
pub const BACKUPS_DIR: &str = "backups";

/// Metadata about a single backup copy.
#[derive(Debug, Clone)]
pub struct BackupRecord {
    pub source: PathBuf,
    pub backup_path: PathBuf,
    pub created_at: chrono::DateTime<Utc>,
}

/// Creates full file copies of DJ databases before any write.
#[derive(Debug, Clone)]
pub struct BackupManager {
    /// Base directory under which `backups/<timestamp>/` trees are created.
    pub backups_root: PathBuf,
}

impl BackupManager {
    /// Creates a manager that stores backups under `backups_root`.
    ///
    /// # Arguments
    ///
    /// * `backups_root` - Typically `<workspace>/backups` or `<usb_mount>/backups`
    pub fn new(backups_root: impl Into<PathBuf>) -> Self {
        Self {
            backups_root: backups_root.into(),
        }
    }

    /// Copies `database_path` into `backups/<timestamp>/<filename>`.
    ///
    /// # Returns
    ///
    /// `BackupRecord` with the path to the copy for rollback.
    ///
    /// # Errors
    ///
    /// Returns `StorageError::BackupFailed` if the copy cannot be created.
    #[instrument(skip(self), fields(db = %database_path.display()))]
    pub async fn create_backup(&self, database_path: &Path) -> Result<BackupRecord, StorageError> {
        let timestamp = Utc::now().format("%Y%m%dT%H%M%S%.3fZ");
        let dest_dir = self.backups_root.join(timestamp.to_string());

        tokio::fs::create_dir_all(&dest_dir)
            .await
            .map_err(|e| StorageError::Io {
                path: dest_dir.clone(),
                source: e,
            })?;

        let file_name = database_path
            .file_name()
            .ok_or_else(|| StorageError::BackupFailed {
                database: database_path.to_path_buf(),
                reason: "database path has no file name".into(),
            })?;

        let backup_path = dest_dir.join(file_name);
        tokio::fs::copy(database_path, &backup_path)
            .await
            .map_err(|e| StorageError::BackupFailed {
                database: database_path.to_path_buf(),
                reason: e.to_string(),
            })?;

        info!(backup_path = %backup_path.display(), "database backup created");

        Ok(BackupRecord {
            source: database_path.to_path_buf(),
            backup_path,
            created_at: Utc::now(),
        })
    }

    /// Restores `record.source` from `record.backup_path` (rollback).
    ///
    /// # Errors
    ///
    /// Returns `StorageError::RollbackFailed` if restore fails.
    pub async fn rollback(&self, record: &BackupRecord) -> Result<(), StorageError> {
        tokio::fs::copy(&record.backup_path, &record.source)
            .await
            .map_err(|e| StorageError::RollbackFailed(e.to_string()))?;
        info!(db = %record.source.display(), "database rolled back from backup");
        Ok(())
    }
}

#[cfg(test)]
mod tests;
