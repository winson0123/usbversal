//! Normalized domain models shared across Rekordbox and Serato adapters.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Identifies which vendor database format is in use.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum DatabaseKind {
    Rekordbox,
    Serato,
}

/// A discovered DJ library on a mount (USB or local path).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Library {
    pub kind: DatabaseKind,
    pub mount_root: std::path::PathBuf,
    pub database_path: std::path::PathBuf,
    /// Human-readable label (vendor + relative path).
    pub label: String,
}

/// Opaque playlist identifier within the normalized model.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct PlaylistId(pub String);

/// Opaque track identifier within the normalized model.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TrackId(pub String);

/// Detected schema metadata; never hardcode version assumptions in callers.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SchemaInfo {
    pub vendor: DatabaseKind,
    pub version_label: String,
    pub detected_at: DateTime<Utc>,
    pub raw_hints: Vec<String>,
}

/// A playlist in the normalized internal model.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Playlist {
    pub id: PlaylistId,
    pub name: String,
    pub track_ids: Vec<TrackId>,
    pub parent_id: Option<PlaylistId>,
}

/// Serato crate equivalent in the normalized model.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Crate {
    pub id: String,
    pub name: String,
    pub track_ids: Vec<TrackId>,
}

/// Database-only track metadata. No audio decoding or file content reads.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TrackMetadata {
    pub id: TrackId,
    pub title: Option<String>,
    pub artist: Option<String>,
    pub album: Option<String>,
    pub genre: Option<String>,
    pub bpm: Option<f64>,
    pub musical_key: Option<String>,
    pub duration_ms: Option<u64>,
    /// Path as stored in the vendor DB (may be relative to USB mount).
    pub library_path: Option<String>,
    pub rating: Option<u8>,
    pub comment: Option<String>,
    pub date_added: Option<DateTime<Utc>>,
}

/// Unified database entity abstraction for cross-vendor operations.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum DatabaseEntity {
    Track(TrackMetadata),
    Playlist(Playlist),
    Crate(Crate),
}

impl DatabaseEntity {
    /// Returns a stable string identifier for this entity.
    pub fn entity_id(&self) -> String {
        match self {
            DatabaseEntity::Track(t) => t.id.0.clone(),
            DatabaseEntity::Playlist(p) => p.id.0.clone(),
            DatabaseEntity::Crate(c) => c.id.clone(),
        }
    }
}

/// Generates a new job correlation id.
pub fn new_correlation_id() -> Uuid {
    Uuid::new_v4()
}

#[cfg(test)]
mod tests;
