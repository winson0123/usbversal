//! Workspace integration tests: parsing, backups, writes, job resume.

use std::path::PathBuf;
use std::sync::Arc;

use chrono::Utc;
use tempfile::TempDir;
use usbversal_core::job::{JobId, JobKind, JobProgress, JobState, JobStatus};
use usbversal_core::EventSink;
use usbversal_jobs::resume::{FileStateStore, MemoryStateStore, StateStore};
use usbversal_jobs::{JobExecutor};
use usbversal_rekordbox::schema::RekordboxSchemaDetector;
use usbversal_storage::backup::BackupManager;

mod support;
use support::CliEventSink;

#[test]
fn rekordbox_schema_detects_minimal_sqlite_fixture() {
    let path = ensure_minimal_rekordbox_fixture();
    let detector = RekordboxSchemaDetector;
    let result = detector.detect(&path).expect("detect schema");
    assert_eq!(result.schema.version_label, "rekordbox-sqlite-djmd");
}

/// Creates a minimal on-disk Rekordbox-style SQLite DB when the fixture file is absent.
fn ensure_minimal_rekordbox_fixture() -> PathBuf {
    let path = fixture_path("rekordbox/v6/minimal/export.pdb");
    if path.exists() {
        return path;
    }
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).expect("fixture dir");
    }
    let conn = rusqlite::Connection::open(&path).expect("create fixture db");
    conn.execute(
        "CREATE TABLE djmdContent (ID INTEGER PRIMARY KEY)",
        [],
    )
    .expect("create table");
    path
}

#[tokio::test]
async fn backup_created_before_write_path() {
    let tmp = TempDir::new().unwrap();
    let db_path = tmp.path().join("library.db");
    tokio::fs::write(&db_path, b"fake db content").await.unwrap();

    let backups_root = tmp.path().join("backups");
    let manager = BackupManager::new(&backups_root);
    let record = manager.create_backup(&db_path).await.unwrap();

    assert!(record.backup_path.exists());
    let content = tokio::fs::read_to_string(&record.backup_path).await.unwrap();
    assert_eq!(content, "fake db content");
}

#[tokio::test]
async fn backup_rollback_restores_original() {
    let tmp = TempDir::new().unwrap();
    let db_path = tmp.path().join("library.db");
    tokio::fs::write(&db_path, b"original").await.unwrap();

    let manager = BackupManager::new(tmp.path().join("backups"));
    let record = manager.create_backup(&db_path).await.unwrap();
    tokio::fs::write(&db_path, b"corrupted").await.unwrap();
    manager.rollback(&record).await.unwrap();

    let content = tokio::fs::read(&db_path).await.unwrap();
    assert_eq!(content, b"original");
}

#[tokio::test]
async fn job_state_persists_to_disk_for_resume() {
    let tmp = TempDir::new().unwrap();
    let store = FileStateStore::new(tmp.path().join("job-state"));
    let job_id = JobId::new();
    let state = JobState {
        id: job_id.clone(),
        kind: JobKind::PlaylistScan,
        status: JobStatus::Paused,
        progress: JobProgress {
            current: 2,
            total: Some(10),
            message: Some("checkpoint".into()),
            eta_secs: None,
        },
        checkpoint: serde_json::json!({ "last_index": 1 }),
        updated_at: Utc::now(),
    };

    store.save(&state).await.unwrap();
    let loaded = store
        .load(&job_id.0.to_string())
        .await
        .unwrap()
        .expect("state on disk");
    assert_eq!(loaded.status, JobStatus::Paused);
    assert_eq!(loaded.checkpoint["last_index"], 1);
}

#[tokio::test]
async fn scan_job_completes_with_progress() {
    let store = MemoryStateStore::default();
    let events: Arc<dyn EventSink> = Arc::new(CliEventSink::default());
    let executor = JobExecutor::new(store, events);

    let (_id, handle) = executor.start_playlist_scan(2);
    handle.await.unwrap().expect("scan ok");
}

#[test]
fn corrupted_rekordbox_fixture_fails_detection() {
    let path = fixture_path("rekordbox/corrupted/truncated.pdb");
    if !path.exists() {
        return;
    }
    let detector = RekordboxSchemaDetector;
    assert!(detector.detect(&path).is_err());
}

fn fixture_path(rel: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("fixtures")
        .join(rel)
}
