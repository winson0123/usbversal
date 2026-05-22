use std::path::PathBuf;

use async_trait::async_trait;

use crate::error::StorageError;

/// Represents a discovered USB or removable mount.
#[derive(Debug, Clone)]
pub struct MountPoint {
    pub root: PathBuf,
    pub label: Option<String>,
}

/// Scans for removable media mounts (platform-specific impls to follow).
#[async_trait]
pub trait MountScanner: Send + Sync {
    /// Returns currently available mount points.
    async fn list_mounts(&self) -> Result<Vec<MountPoint>, StorageError>;
}

/// Stub scanner for scaffolding; returns empty until OS integration exists.
#[derive(Debug, Default)]
pub struct StubMountScanner;

#[async_trait]
impl MountScanner for StubMountScanner {
    async fn list_mounts(&self) -> Result<Vec<MountPoint>, StorageError> {
        Ok(Vec::new())
    }
}
