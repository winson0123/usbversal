#[cfg(test)]
mod tests {
    use super::*;
    use crate::mount::PlatformMountScanner;
    use tempfile::TempDir;
    use usbversal_core::domain::DatabaseKind;

    #[tokio::test]
    async fn discovers_rekordbox_and_serato_layout() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path();
        let rb_dir = root.join("PIONEER/rekordbox");
        std::fs::create_dir_all(&rb_dir).unwrap();
        std::fs::write(rb_dir.join("export.pdb"), b"SQLite format 3\x00").unwrap();
        std::fs::create_dir_all(root.join("_Serato_")).unwrap();
        std::fs::write(root.join("_Serato_/database V2"), b"serato-stub").unwrap();

        let discovery = LibraryDiscovery::new(PlatformMountScanner::default());
        let report = discovery.scan_paths(&[root.to_path_buf()]).await.unwrap();

        assert_eq!(report.libraries.len(), 2);
        assert!(report
            .libraries
            .iter()
            .any(|l| l.kind == DatabaseKind::Rekordbox));
        assert!(report
            .libraries
            .iter()
            .any(|l| l.kind == DatabaseKind::Serato));
    }

    #[tokio::test]
    async fn platform_scanner_includes_mnt_usb_candidate() {
        let scanner = PlatformMountScanner::default();
        let roots = scanner.candidate_roots();
        assert!(roots.iter().any(|p| p == std::path::Path::new("/mnt/usb")));
    }
}
