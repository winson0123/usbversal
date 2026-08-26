# Handoff — 2026-08-26

Rekordbox → Serato analysis porting is **working and confirmed in Serato**, and
as of TASK-130 `sync_playlists()` now writes it: every synced track with
Rekordbox analysis gets its beatgrid and hot cues, and `location.sqlite` is
updated for any track that got a grid. Read this before touching either.

**Read [`AGENT.md`](../AGENT.md) first.** One task at a time, one commit per
task, state files updated after each.

| | |
|---|---|
| Tests | 164 passed, 3 skipped (`ruff` and `ruff format` clean) |
| Size | app 5,152 lines, tests 2,972 |
| Branch | `main`, clean, **no remote** |
| Stick | `/mnt/usb`, bind-mounted to `/mnt/wsl/usb` — see the mount trap below |

---

## The thing to understand first: Serato keeps two libraries

`database V2` is **legacy**. `_Serato_/Library/location.sqlite` is what Serato
actually reads. The sqlite even tracks the old file by name and MD5 in
`last_seen_dbv2_library`, with import/export revisions in `dbv2_status` — it
imports `database V2`, then works from itself.

The split that matters:

- **The deck reads the audio file's tags.** Beatgrid, cues, and BPM all come
  from `Serato BeatGrid` and `Serato Markers2`.
- **The library list reads `location.sqlite`.** Its `asset` table holds `bpm`,
  `key`, `analysis_flags`, `is_stale`, and a per-row `revision`.

So a synced track can load on the deck with the correct Rekordbox grid while the
list still shows Serato's own BPM. That is not a bug, it is two sources.

Worse, our own writes are invisible to Serato's staleness check: tag writes are
size-preserving (needed to stop the waveform glitching), `asset.file_size` never
changes, and `is_stale` stays 0. Serato never re-reads. Updating the index is
therefore mandatory, not cosmetic.

---

## What works, and what is still unvalidated by the tool

**Confirmed working in Serato**, on the Pocket crate: the crate appears, tracks
carry Rekordbox beatgrids and hot cues, and the deck shows Rekordbox's BPM.
That was done by hand in the terminal.

**As of TASK-130, `sync_playlists()` reproduces it.** For every track in a
synced playlist that has Rekordbox analysis data, it now writes the beatgrid
and hot cues into the audio tags and, when a grid was written, updates
`location.sqlite` so the list agrees with the deck:

| Module | Does |
|--------|------|
| `adapters/rekordbox/anlz.py` | reads hot cues (`PCO2`) and beats (`PQTZ`) |
| `adapters/serato/beatgrid.py` | encodes `Serato BeatGrid` |
| `adapters/serato/markers2.py` | encodes/decodes `Serato Markers2` |
| `adapters/serato/tags.py` | reads/writes GEOB frames in MP3 and WAV, verifying size, audio hash, and frame read-back before any byte reaches disk |
| `adapters/serato/library_db.py` | reads/updates `location.sqlite` |

`sync_playlists()` now writes crates, `database V2` records, `neworder.pref`,
grids, cues, and the index in one backup-gated pass. A track whose audio or
ANLZ data cannot be read is skipped and recorded in `SyncReport.analysis_errors`
rather than aborting the run. What it does **not** yet do:

- **Correct the index for tracks it does not touch.** Index BPM only updates
  for a track that got a fresh grid in this pass; the ~70 already-wrong
  constant-tempo rows from before this tool existed stay wrong until a
  dedicated correction pass runs (TASK-132).
- **Guard against clobbering Mixed In Key or Sound Forge frames.** Nothing
  currently writes to those files, but nothing tests that either (TASK-133).
- **Reach the CLI or TUI.** `sync_playlists()` is callable and tested; no
  command invokes it yet, same as before this task.

This has been exercised against synthetic fixtures (a real WAV carrying real
Serato frames, and hand-built ANLZ containers), not yet re-run against the test
stick end to end. Re-validate on `/mnt/usb` before trusting it there.

---

## State of the test stick

It has been modified by hand, not by the tool. Anyone testing against it should
know what is already there.

| What | State |
|------|-------|
| Pocket crate, 80 tracks | `Serato BeatGrid` and `Serato Markers2` written from Rekordbox |
| `Apt X Blue` | 4-marker ramped grid (the only multi-marker track written) |
| `location.sqlite` | ~22 rows corrected by hand: 7 Pocket BPMs, 14 variable-tempo tracks set to their first beat's tempo, plus `Apt X Blue` |
| Everything else (~717 tracks) | untouched by us; Serato's own analysis only |
| 5 files | restored from a pre-wipe backup, so they still carry old Serato and Mixed In Key frames while the other 75 do not |
| `FOUND.000`, `FOUND.001` | 120 MB of clusters `chkdsk` salvaged during the corruption. Nothing needed came from them; safe to delete. |

Because only Pocket has had tags written, the 14 index rows corrected outside it
now show Rekordbox BPM in the list while the deck still reads Serato's analysis
from untouched files. Those two views disagree until a full tag sync runs.

Backups on the stick, newest last:

```
20260823T094303Z   Pocket, 80 files, before grids and cues
20260825T064623Z   location.sqlite, before the first index edit
20260826T031325Z   Apt X Blue, before the ramped grid
20260826T034357Z   Apt X Blue + index
20260826T034834Z   index, before the variable-tempo pass
```

## Do this next

### 1. Re-validate `sync_playlists` on the real stick

TASK-130 wired grids, cues, and the index into `sync_playlists`, but it has
only run against synthetic fixtures so far. Run it against a real playlist on
`/mnt/usb` and confirm in Serato before trusting the wiring generally.

### 2. Codify the rules that currently live only in this document

- **Index BPM for a variable-tempo track is the first beat's tempo**, not
  Rekordbox's headline average and not Serato's pick. Serato consistently
  chooses the wrong section: all four `Drake - NOKIA` variants were indexed at
  106 when the track opens at 126 for its first hundred seconds. `sync_playlists`
  now applies this rule for any track it writes a fresh grid for (TASK-130),
  but does not correct rows outside that pass.
- Roughly **70 constant-tempo tracks** are still at half or double tempo in the
  index and have not been corrected.
- Skip index rows Serato does not know; never insert. (Already true —
  `update_track_analysis` only updates existing rows.)
- Marker threshold is 2.0 BPM (already in `beatgrid.py`).

### 3. A never-clobber regression test

About a fifth of the library carries Mixed In Key frames (`Key`, `Energy`,
`CuePoints`, and its own `BeatGrid`), and one file carries Sound Forge frames.
Nothing we write touches them, and nothing enforces that.

---

## Retracted — claims in this repo that are wrong

| Claim | Reality |
|-------|---------|
| The "+120 second" two-marker grid is a bug producing 2 BPM | It is not. Files displaying correct grids carry it. `beats_to_next` is a bar length, not a count to the next marker, so the arithmetic never applied. |
| `Serato Offsets_` caused the glitched waveform | A stale `Serato Overview` did. Only Serato regenerates it. `Offsets_` is present on ~11% of files and absent from fresh analysis. |
| Variable tempo cannot be expressed | Serato itself wrote a 63-marker grid, and a 113-marker grid displayed correctly. |
| Beatgrids should be written for constant-tempo tracks only | Serato writes a single marker for variable-tempo tracks too; skipping them left ~7% of the library with nothing. |
| Serato's key notation differs from Rekordbox's | Both mix Camelot and musical notation. Normalised, 552 of 797 agree. |

---

## Safety — read before writing to a stick

**Five audio files were destroyed during this work.** Repeated in-place rewrites
of whole multi-megabyte MP3s on vfat over a USB passthrough corrupted their FAT
cluster chains; the filesystem remounted read-only and `chkdsk` moved the
remains to `FOUND.000`. They were recovered only because an earlier full backup
verified clean — **the targeted backup taken for that very operation had a
zero-byte manifest**, written into the same failure.

Consequences that should shape the code:

- Verify backups *after* writing, not only before.
- Do not rewrite whole audio files repeatedly. One pass per file, per run.
- "Audio stream byte-identical" does not prove the write was safe; all five
  verified clean by content and were still structurally damaged on disk.
- Prefer working on a copy of the stick.

### The WSL mount trap

This shell runs in a private mount namespace, so a stick mounted afterwards in
the host namespace is invisible — `/mnt/usb` looks like an empty directory.
Bind-mount under `/mnt/wsl`, a shared peer group:

```bash
sudo mount -t vfat /dev/sde1 /mnt/usb -o uid=1000,gid=1000,utf8
sudo mkdir -p /mnt/wsl/usb && sudo mount --bind /mnt/usb /mnt/wsl/usb
```

Both are lost on reboot, and the device letter changes between replugs. An empty
mount point means *no stick*, not a valid path.

---

## Formats, with the evidence

- [serato-schema-notes.md](schemas/serato-schema-notes.md) — TLV container,
  crates, `database V2`, `neworder.pref`, `Markers2`, `BeatGrid`
- [analysis-data-study.md](schemas/analysis-data-study.md) — what a Lexicon sync
  changes, and how cues, grids, BPM, key and gain correspond
- [rekordbox-schema-notes.md](schemas/rekordbox-schema-notes.md) — ANLZ, and the
  `export.pdb` spec, never parsed

`tests/fixtures/serato/` holds the before/after WAV pair proving the cue
encoding: applying the cues to `BEFORE` reproduces `AFTER` byte for byte. Both
came from Lexicon, so it is an oracle rather than a restatement of our own
encoding. Keep it.

### Facts worth not rediscovering

- Serato's canonical beatgrid is **14 bytes**: one terminal marker, position and
  BPM, no trailing byte. All 72 freshly analysed tracks, without exception.
- A **malformed** grid is worse than none — Serato draws nothing and does not
  fall back to its own analysis.
- `serato-tools` cannot append to `database V2` through its public API. `save()`
  writes `raw_data`, which only the private `_dump()` refreshes.
- `Crate.DEFAULT_ENTRIES` is class-level and `add_track` mutates it, so crates
  written in one process inherit each other's tracks.
- Rekordbox measures tempo per bar, and readings wobble ±0.1 BPM. Counting
  distinct tempos overstates how much the tempo actually moves.
