# Apply Plan Format

**Status:** implemented (`apply` CLI, TASK-053)  
**Schema version:** 1

## Purpose

Run one or more USB operations from a JSON file instead of repeating CLI flags. v1 supports Rekordbox → Serato playlist migration only; more operation types can be added later.

## CLI

```bash
# Validate plan (no writes)
python -m app.cli apply --mount /mnt/usb --plan plans/pocket.json --dry-run

# Execute (backup-gated, same as migrate-playlist per op)
python -m app.cli apply --mount /mnt/usb --plan plans/pocket.json --json
```

## Schema (version 1)

```json
{
  "version": 1,
  "mount": "/mnt/usb",
  "operations": [
    {
      "op": "migrate_playlist",
      "playlist_name": "Pocket",
      "overwrite": false
    }
  ]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `version` | yes | Must be `1` |
| `mount` | no | When set, must match `--mount` exactly |
| `operations` | yes | Non-empty array of operation objects |

### Operation: `migrate_playlist`

| Field | Required | Description |
|-------|----------|-------------|
| `op` | yes | `"migrate_playlist"` |
| `playlist_id` | one of | Rekordbox playlist id |
| `playlist_name` | one of | Exact Rekordbox playlist name |
| `overwrite` | no | Replace existing crate (default `false`) |

Behavior matches `migrate-playlist`: each operation takes its own backup before writing `Subcrates/<name>.crate`.

## Example plans

- [tests/fixtures/migrate_pocket.plan.json](../../tests/fixtures/migrate_pocket.plan.json)

## After apply

Serato does not receive BPM/beatgrid/cues from Usbversal. Run **Analyze Files** in Serato DJ after migration ([usb-integration-validation.md](../workflows/usb-integration-validation.md)).

## Related

- [rekordbox-to-serato-playlist-migration.md](rekordbox-to-serato-playlist-migration.md)
- [../architecture/cli-flow.md](../architecture/cli-flow.md)
