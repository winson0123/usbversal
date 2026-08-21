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
| ~~`TASK-010`~~ | ~~Mount path validation utilities~~ | Done — `storage.mounts.resolve_mount_path`. The old note ("no auto-detect yet") was wrong; auto-detect shipped with TASK-050. |
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
| ~~`TASK-032`~~ | ~~Rekordbox write path~~ | **Dropped 2026-08-21.** Contradicts the mission: rekordbox owns `PIONEER/` and stays untouched, which is what makes the two-index approach lossless. No consumer, and building it would undermine the safety story. |

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
| ~~`TASK-073`~~ | ~~`database V2` append writer~~ | Done — TASK-112. A Rekordbox-to-`otrk` field mapper is still outstanding and moves to TASK-113. |
| `TASK-113` | Rekordbox metadata → `otrk` fields | Artist/album/genre/key arrive as ids needing `get_*_by_id` lookups. String formats are fussy (`tbpm` `"127.61"`, `tlen` `"03:34.99"`, `tsiz` `"8.2MB"`); wrong formats display oddly rather than failing. Diff against how Lexicon formatted the same tracks. |
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
| ~~`TASK-091`~~ | ~~Reconcile `ruff format` drift~~ | Done |

## M11 — Interactive TUI (the shipped product)

The argparse CLI is a **test harness**, not the deliverable. Plan:
[interactive-tui.md](../planning/interactive-tui.md). These gate the real tool
and none of them exist yet.

| ID | Title | Notes |
|----|-------|-------|
| `TASK-110` | Per-playlist sync state (red / yellow / green) | Diff each Rekordbox playlist's tracks against its Serato crate: none → red, some → yellow, all → green. Largest missing piece; gates the library screen. |
| `TASK-111` | Playlist tree model | `Playlist.parent_id` exists but every consumer flattens it. Needs real nesting plus aggregate sync state per folder. |
| `TASK-112` | Single "valid DJ USB?" readiness verdict | One call for the waiting/detect screens. Must treat an **empty mount point as no USB** — `/mnt/usb` survives unplugging as an empty dir and passes `resolve_mount_path`. |
| `TASK-113` | Removable-media polling | Detection is one-shot today. `LibraryDiscovery` walks up to 25,000 nodes — far too heavy for a UI loop. Needs a cheap mount-appeared/disappeared watch. |
| `TASK-114` | Progress rate + ETA | `JobProgress` has `current`/`total` but no rate or estimate. |
| `TASK-115` | Batch sync over selected playlists | `apply` takes **one backup per operation**; 40 playlists must take one backup up front. Build on the collect-and-report shape from TASK-102. |
| `TASK-116` | TUI framework ADR + shell | textual / prompt_toolkit / rich / curses. Must survive PyInstaller one-file packaging (ADR 0003). |

---

## Cross-cutting notes

- **`serato_tools.usb_export.copy_crates_to_usb` `rmtree`s the destination
  `_Serato_`.** Never call it. Its own source carries a `TODO: merge with
  existing, instead of replacing`.
- Sticks in the wild already carry a real `database V2` (522 KB / 793 tracks on
  the reference stick) written by Serato or Lexicon. **Merge, never regenerate.**
- Stage 1 is independently shippable and touches no audio. Stage 2 is the risky
  half; do not let them share a commit.
- **Code carries no historical reasoning.** Why a thing is shaped the way it is
  belongs in `docs/`; the source states only what it does now.
