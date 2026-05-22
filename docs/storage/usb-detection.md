# USB Detection

**Status:** placeholder — not implemented.

## Test Environment

Primary validation mount for WSL development:

```text
/mnt/usb
```

Use only when a task explicitly requires real USB validation. Do not assume the mount exists in CI.

## Target Behavior (Planned)

| Step | Detail |
|------|--------|
| Accept `--mount` | User-supplied root (required for explicit operations) |
| Optional auto-detect | Enumerate removable mounts (OS-specific, future) |
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

When `/mnt/usb` is available:

- Record discovered paths in `docs/schemas/` notes
- Do not replace integration tests with mocks only

## Related

- [backup-strategy.md](backup-strategy.md)
- [../adapters/rekordbox.md](../adapters/rekordbox.md)
- [../adapters/serato.md](../adapters/serato.md)
