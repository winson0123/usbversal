# USB Detection

**Status:** implemented.

## Auto-detect

The TUI scans for a DJ USB on the platform's usual removable-media roots:

| OS | Roots |
|----|-------|
| Linux | `/media/$USER` |
| macOS | `/Volumes` |
| Windows | Drive letters |

`USBVERSAL_MOUNT` is a silent escape hatch when the scanner misses a path
(WSL, unusual mounts). Integration tests use `USBVERSAL_TEST_MOUNT`.
There is no hardcoded default mount.

## Signatures

| Path | Meaning |
|------|---------|
| `PIONEER/rekordbox/exportLibrary.db` | Rekordbox One Library (required) |
| `PIONEER/rekordbox/export.pdb` | DeviceSQL only — unsupported |
| `_Serato_/database V2` | Existing Serato library |

A Rekordbox-only stick is bootstrapped with an empty `_Serato_` before
sync. `export.pdb` without `exportLibrary.db` is rejected.

## Host logs

Failed sync items are written under `~/.local/share/usbversal/<volume>/`.
Do not keep a host backup or rollback path; recovery is restoring the
Rekordbox USB.
