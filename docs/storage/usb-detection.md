# USB detection

The TUI looks for a DJ USB on the usual removable-media roots.

| OS | Roots |
|----|-------|
| Linux | `/media/$USER` |
| macOS | `/Volumes` |
| Windows | Drive letters |

`USBVERSAL_MOUNT` covers WSL and odd mounts the scanner misses.
Integration tests use `USBVERSAL_TEST_MOUNT`. There is no hardcoded
default.

## Signatures

| Path | Meaning |
|------|---------|
| `PIONEER/rekordbox/exportLibrary.db` | Rekordbox One Library. Required. |
| `PIONEER/rekordbox/export.pdb` | DeviceSQL only. Unsupported. |
| `_Serato_/database V2` | An existing Serato library |

A Rekordbox-only stick gets an empty `_Serato_` before sync.
`export.pdb` without `exportLibrary.db` is rejected.

## Host data

Per stick, under `~/.local/share/usbversal/<volume>/` (Windows:
`%LOCALAPPDATA%\usbversal\<volume>\`), or `USBVERSAL_DATA_ROOT`:

| File | Meaning |
|------|---------|
| `error.log` | Failed sync items from the last run that had failures |
| `analysis-cache.json` | Analysis-ported verdicts keyed by volume label |

`<volume>` is the Serato volume label (filesystem label on Windows,
mount folder name on Linux/macOS). Do not keep a host backup. Recovery
is restoring the Rekordbox USB.
