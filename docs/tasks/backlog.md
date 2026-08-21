# Task Backlog

Queued work. **Only one task may be active** — see [`AGENT.md`](../../AGENT.md).

Priority order (top first). Decompose before starting if scope exceeds one commit.

---

## M1 — Project Foundation

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-001`~~ | ~~Add `pyproject.toml` and package skeleton~~ | Done |
| ~~`TASK-002`~~ | ~~Configure ruff, pytest, dev dependencies~~ | Done — `pyproject.toml` |
| ~~`TASK-003`~~ | ~~CLI entrypoint stub~~ | Done — `app/cli/main.py` |

## M2 — Storage Layer

| ID | Title | Notes |
|----|-------|-------|
| `TASK-010` | Mount path validation utilities | No auto-detect yet |
| ~~`TASK-011`~~ | ~~Backup copy + manifest.json~~ | Done |
| ~~`TASK-012`~~ | ~~Rollback from manifest~~ | Done — `rollback` CLI |

## M3 — Core Domain

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-020`~~ | ~~Domain models (Library, Playlist, Track)~~ | Done — `app/core/domain.py` |
| ~~`TASK-021`~~ | ~~Adapter protocol + WriteContext~~ | Done |
| ~~`TASK-022`~~ | ~~Event types and bus skeleton~~ | Done |

## M4 — Adapters

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-030`~~ | ~~Rekordbox detect + read-only list~~ | Done |
| ~~`TASK-031`~~ | ~~Serato detect + read-only crates~~ | Done |
| `TASK-032` | Rekordbox write path | Requires backup integration. **Not started** |

## M5 — Jobs

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-040`~~ | ~~JobRunner + registry~~ | Done |
| ~~`TASK-041`~~ | ~~Scan job~~ | Done |
| ~~`TASK-042`~~ | ~~Cancel + resume metadata~~ | Done |

## M6 — CLI Commands

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-050`~~ | ~~`scan` command~~ | Done |
| ~~`TASK-051`~~ | ~~`list-playlists` / `list-crates`~~ | Done |
| ~~`TASK-052`~~ | ~~`backup` / `rollback`~~ | Done |
| ~~`TASK-053`~~ | ~~`apply` with plan file~~ | Done — [apply-plan-format.md](../planning/apply-plan-format.md) |

## M7 — Packaging & Validation

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-060`~~ | ~~PyInstaller spec + smoke test~~ | Done |
| ~~`TASK-061`~~ | ~~`/mnt/usb` integration validation~~ | Done |
| ~~`TASK-070`~~ | ~~Capture verified Serato write formats; re-plan Stage 1/2~~ | Done — this backlog |

---

## M8 — Serato Index Authoring (Stage 1)

Makes a **rekordbox-only stick readable by Serato**. Writes only inside
`_Serato_/`; never touches `PIONEER/` or the audio under `Contents/`.
Plan: [serato-index-bootstrap.md](../planning/serato-index-bootstrap.md).
Formats: [serato-schema-notes.md](../schemas/serato-schema-notes.md).

| ID | Title | Notes |
|----|-------|-------|
| `TASK-071` | Add `neworder.pref` to the Serato backup set | **Safety gap.** `serato_files_on_mount` covers `database V2` + `.crate` only, so rollback cannot restore crate ordering. Do this before any Stage 1 write. |
| `TASK-072` | Serato TLV codec in the adapter | Encode/decode tag + u32 BE length + payload; type from tag prefix; **preserve unrecognized tags verbatim**. Round-trip tests against fixtures. Precondition: check whether `serato-tools` can append an `otrk` without dropping unknown fields (open question 1). |
| `TASK-073` | `database V2` merge/append writer | Read existing `otrk`, key by `pfil`, add or update. Author records from Rekordbox metadata using the verified minimal field set. **Never regenerate.** |
| `TASK-074` | `neworder.pref` merge/write | UTF-16BE `[begin record]` / `[crate]<name>` / `[end record]`. Preserve existing crate order, append new. |
| `TASK-075` | Nested playlist folders → `Parent%%Child.crate` | Current code flattens to the leaf name, so same-named playlists in different folders collide. Convention is [assumed], not verified — validate in Serato. |
| `TASK-076` | Bootstrap `_Serato_` on a rekordbox-only stick | Create `_Serato_/`, `Subcrates/`, `database V2`, `neworder.pref` where absent. Removes `SeratoLibraryRequiredError` as a dead end. Backup-gated; verify `PIONEER/` hash is unchanged. |

## M9 — Analysis Tag Sync (Stage 2)

Writes hot cues and beatgrids into the **audio files**. Requires
[ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md);
supersedes the abandoned TASK-034. **Mutates user audio — explicit confirmation
plus per-file backup required.** Sequenced strictly after M8.

| ID | Title | Notes |
|----|-------|-------|
| `TASK-080` | ANLZ reader — `PQTZ` beatgrid, `PCO2` hot cues | Resolve via track `analyze_path`. Format is [assumed] from public docs, **never parsed on a real stick** — validate before building on it. Distinguish hot cues from memory cues. |
| `TASK-081` | Rekordbox → Serato cue colour table | **Only 2 of N mappings known** (`magenta_red`→`#CC0044`, `blue_light`→`#0088CC`). Derive from rekordbox colour IDs or generate more Lexicon samples. Blocks TASK-082 from being correct, not from running. |
| `TASK-082` | `Serato Markers2` GEOB writer (hot cues) | Verified layout. Round-trip target: applying AFTER's cue list to `Techno1.BEFORE.wav` must reproduce `Techno1.AFTER.wav`'s payload byte-for-byte. This is the tag that satisfies Serato's analyzed gate. |
| `TASK-083` | `Serato BeatGrid` + `Autotags` GEOB writer | **Lowest confidence in M9** — Lexicon does not write beatgrids, so there is no reference. Only single-marker grids observed; ADR 0006's 2 BPM first-bar bug is a live hazard for variable tempo. Ship behind a flag separate from cue sync. |
| `TASK-084` | Container tag I/O — MP3 and WAV | **MP3 is untested and is the one that matters** (a rekordbox USB is all MP3). WAV needs RIFF `id3 ` chunk rewrite + RIFF size fixup; fixtures cover WAV only. Must preserve GEOB frames it does not own. FLAC/MP4 out of scope. |
| `TASK-085` | `sync-analysis` CLI (re-introduce) | Backup-gated, idempotent, must not clobber existing Serato analysis on partially analyzed libraries. Confirm with the user before writing. |

## M10 — Deferred

| ID | Title | Notes |
|----|-------|-------|
| `TASK-090` | `export.pdb` DeviceSQL reader | Spec captured in [rekordbox-schema-notes.md](../schemas/rekordbox-schema-notes.md) but **never parsed**. Not needed while `exportLibrary.db` is present — only for older sticks that ship `export.pdb` alone. Validate by dumping the playlist tree and checking names are readable. |
| `TASK-091` | Reconcile `ruff format` drift | 4 files fail `ruff format --check` (2 app, 2 tests), predating this work. Isolated commit — do not batch. |

---

## Cross-cutting notes

- **`serato_tools.usb_export.copy_crates_to_usb` `rmtree`s the destination
  `_Serato_`.** Never call it. Its own source carries a `TODO: merge with
  existing, instead of replacing`.
- Sticks in the wild already carry a real `database V2` (522 KB / 793 tracks on
  the reference stick) written by Serato or Lexicon. **Merge, never regenerate.**
- Stage 1 is independently shippable and touches no audio. Stage 2 is the risky
  half; do not let them share a commit.
