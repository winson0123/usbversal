# USB Detection

**Status:** implemented (read-only discovery).

## Auto-detect

The TUI scans for a DJ USB on the platform's usual removable-media roots:

| OS | Roots |
|----|-------|
| Linux | `/media/$USER` |
| macOS | `/Volumes` |
| Windows | Drive letters |

`USBVERSAL_MOUNT` is a silent escape hatch when the scanner misses a path
(WSL, unusual mounts). Integration tests use `USBVERSAL_TEST_MOUNT` the same
way — there is no hardcoded default.

Use a real stick only when a task explicitly requires it. Do not assume a
stick exists in CI.

## Target Behavior

| Step | Detail |
|------|--------|
| Auto-detect | Enumerate removable mounts (OS-specific, above) |
| Library scan | Walk for Rekordbox and Serato signatures |
| Emit warnings | DJ software running, lock files present |

## Rekordbox Signatures (Assumed)

| Path pattern | Confidence |
|--------------|------------|
| `**/export.pdb` | assumed |
| `**/PIONEER/**` | assumed |

## Serato Signatures (Assumed)

| Path pattern | Confidence |
|--------------|------------|
| `**/_Serato_/**` | assumed |
| `**/database V2` | assumed |

## Warnings (Planned)

| Condition | Action |
|-----------|--------|
| Rekordbox/Serato process running | emit warning; no hard block initially |
| DB lock / WAL active | warn; prefer read-only |

## Validation Requirement

When a DJ USB is available:

- Record discovered paths in `docs/schemas/` notes
- Do not replace integration tests with mocks only

## Related

- [../adapters/rekordbox.md](../adapters/rekordbox.md)
- [../adapters/serato.md](../adapters/serato.md)
