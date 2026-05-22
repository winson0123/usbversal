//! Storage layer: mount discovery, timestamped backups, atomic writes.

pub mod atomic;
pub mod backup;
pub mod error;
pub mod mount;
pub mod write_guard;

pub use atomic::AtomicWriter;
pub use backup::{BackupManager, BackupRecord};
pub use error::StorageError;
pub use mount::{MountPoint, MountScanner};
pub use write_guard::WriteGuard;
