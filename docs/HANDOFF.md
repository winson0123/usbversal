# Handoff — 2026-08-27

**Read [`AGENT.md`](../AGENT.md) first.** One task at a time, one commit per
task, state files updated after each. Then read the pending task directly
below — that's what a session picking this up should do next.

| | |
|---|---|
| Tests | 273 passed, 4 skipped (`ruff` and `ruff format` clean) |
| Last done | `TASK-219` — Progress screen verbose per-track log, green/red colour |
| Branch | `main`, clean, **no remote** |
| Stick (this dev sandbox) | `USBVERSAL_MOUNT=/mnt/usb` — TASK-217 removed the automatic `/mnt` scan; see the mount trap below, it's unchanged |

The interactive TUI (M11, TASK-200–219) is the actual deliverable now — the
whole Waiting → Detect → Library → Progress → Done flow is reachable, and the
CLI is a thin test harness underneath it. Everything below the pending-task
section is the pre-TUI Rekordbox → Serato analysis-porting handoff; it's still
accurate and worth reading before touching that code, just no longer the
first thing to work on.

---

## Pending: Library screen redesign (not started)

The user asked for this in one message, verbatim:

> instead of not synced, partial, synced string, colour the sync number.
> remove the - character in front of all playlists.
>
> i want left side like the image, but instead of Collections, it'll be
> "Playlists" and the bottom left be the colour indication, short
> explanation of traffic colours
>
> right side to be preview of the tracks found in the playlists, in order
> sequential no, showing title, genre, key, bpm with allowing user to edit
> the preference in settings to see more metadata. able to click on the
> table header to sort by that column.
>
> traffic colour on those tracks that are synced within this display as well

The reference image was a screenshot of **Posting** (a terminal HTTP client):
a bordered left panel titled "Collection" holding a request tree, a bordered
right panel titled "Request"/"Response" holding tabbed detail content, both
inside the same window. The ask is that shape, not that content.

**Explicitly deferred by the user mid-implementation** ("nevermind, write the
handover file for this tasking, we'll continue with your tests until your
intended finish path first") after one clarifying question was asked and not
finished — see "Open question" below. Nothing in `app/tui/screens/library.py`
has been changed for this yet.

### Breaking it into pieces, in a sensible order

1. **Colour the sync number, not the state word; drop the `-` prefix.**
   Smallest, most self-contained piece — touches only
   `LibraryScreen._label()`'s existing `_MARKER`/formatting logic in
   `app/tui/screens/library.py`. Currently: `f"{checkbox} {row.name}"` then
   a right-aligned `{colour}{word}{/colour}` state column. New: the `x/y`
   count column itself takes the colour (red/yellow/green) instead of a
   separate coloured word column, and the checkbox glyph is blank (not
   `-`) when nothing in that row is selected -- only `x`/`~` render, never
   `-`. Use `rich.text.Text` with explicit styles per segment (per
   TASK-219's finding), not markup strings, since playlist names are
   arbitrary user data.
2. **Two-pane bordered layout.** Wrap the existing tree in a bordered
   `Container` titled "Playlists" (Textual: `border-title` CSS property,
   or a docked title `Static`), with a color-legend line docked to the
   bottom of that same left pane (e.g. "green = synced  yellow = partial
   red = not synced" -- plain text, no theme colour beyond the same
   red/yellow/green already used elsewhere). Right pane is new (see next
   point). Two `Container`s side by side under a `Horizontal`, most likely
   -- check how much of TASK-206's ADR 0009 discussion already covers
   Textual layout primitives before reinventing anything.
3. **Track-preview table, right pane.** New `DataTable` (Textual has one
   built in, with a `.sort()` method and a `HeaderSelected` message fired
   on a header click -- exactly what "click header to sort" needs; no
   custom sort-click handling required, just `on_data_table_header_selected`
   toggling ascending/descending and calling `.sort(column_key,
   reverse=...)`). Populated from whichever playlist is currently
   highlighted in the tree (`Tree.cursor_node`/on-highlight event, not
   just on toggle-select). Default columns: Title, Genre, Key, BPM.
   Per-track sync colour (same red/yellow/green rule) needs its own
   column or coloured cell -- `playlist_sync_states()` in
   `app/services/sync_service.py` already computes this per playlist;
   check whether it exposes (or would need to expose) a per-track,
   not just per-playlist, verdict.
4. **Settings for extra metadata columns.** Genuinely open, see below.
   Do this last -- it's additive (more optional columns on top of the
   fixed four), so nothing else needs to wait for it.

### Data already available for the table

`library.rekordbox.database.get_contents()` returns one row per track with
(among others) `.title`, `.artist_id`, `.album_id`, `.genre_id`, `.key_id`,
`.bpmx100` (÷100 for real BPM), `.length`, `.file_size`, `.bitrate`,
`.sampling_rate`, `.release_year`, `.release_date`, `.date_added`, `.path`.
`app/services/track_records.py`'s `load_lookups()` resolves
`artist_id`/`album_id`/`genre_id`/`key_id` to names via `RekordboxLookups`.
`sync_service.py`'s existing `by_path = {c.path: c for c in
library.rekordbox.database.get_contents()}` pattern (used in
`sync_playlists`) is the precedent for cross-referencing a playlist's track
paths against these rows -- reuse it rather than re-deriving.

### Open question: how do metadata-column preferences persist?

Asked once via `AskUserQuestion`, not answered before the user deferred the
whole task. Three options were on the table, and the user should pick
before this part is built (the rest of the redesign does not depend on the
answer):

1. **Settings screen + config file** (was the recommended default) -- a new
   screen, bound to some key (`s`?), with checkboxes for optional columns
   (Artist, Album, Duration, Year, ...); saved to a small JSON file under a
   user config directory (e.g. `~/.config/usbversal/settings.json`) so the
   choice survives restarts. Needs: a settings screen, a tiny config
   read/write module (nothing like it exists in `app/` yet -- check
   `platformdirs` or similar before hand-rolling an OS-specific config
   path), and `LibraryScreen`/the new table reading it on mount.
2. **In-session only** -- same screen and toggles, resets to the default
   four columns every restart. No new file I/O or format to maintain.
3. **Skip settings for now** -- ship the fixed four columns
   (Title/Genre/Key/BPM), sortable and colour-coded; defer configurable
   columns to a later task entirely.

### What "in order sequential no" in the original message means

Read as: "[Does track order need a] sequential [number column]? No[, it
doesn't] -- [just] show title, genre, key, bpm." I.e. no explicit
track-number/order column is needed; row order can default to whatever the
playlist's natural order is and be overridden by the click-to-sort feature
regardless. Reasonably confident in this reading but it was never confirmed
-- worth a quick check with the user before the table ships if anything
about ordering looks off once built.

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
rather than aborting the run. `correct_index_bpm()` (TASK-132) does the same
first-beat-tempo correction library-wide, not only for tracks in a playlist
being synced. `write_geob` (TASK-131) verifies size, audio hash, and frame
read-back before any byte reaches disk, and `tests/test_never_clobber.py`
(TASK-133) proves that verification, and the writer generally, never disturbs
a Mixed In Key or other foreign vendor frame. What none of this has done yet:

- ~~**Reach the CLI or TUI.**~~ Done since this was written: `sync_playlists()`
  is reachable end to end from the TUI's Progress screen (TASK-208,
  verbose per-track output added in TASK-219). `correct_index_bpm()` is
  still not wired into either the CLI or the TUI.
- **Run against the real stick.** Exercised against synthetic fixtures only —
  a real WAV carrying real Serato frames, hand-built ANLZ containers, and a
  hand-built MP3 carrying foreign vendor frames. The ~70 known-wrong index
  rows on `/mnt/usb` are still wrong until `correct_index_bpm()` actually runs
  there. Re-validate before trusting any of this on real hardware.

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

### Re-validate `sync_playlists` and `correct_index_bpm` on the real stick

TASK-130 wired grids, cues, and the index into `sync_playlists`; TASK-132
added `correct_index_bpm()` for rows outside a synced playlist. Both have only
run against synthetic fixtures so far. Run `correct_index_bpm()` against
`/mnt/usb` to actually fix the **~70 constant-tempo tracks still at half or
double tempo in the index** and re-check the four `Drake - NOKIA` variants
(indexed at 106 when the track opens at 126 for its first hundred seconds),
then confirm in Serato before trusting either path generally.

Everything else from the original post-porting punch list (write verification,
codifying the BPM rules, the never-clobber regression test, correcting this
document) is done — TASK-131, TASK-132, TASK-133, TASK-126. What remains
before the analysis path can be called finished is validating it on real
hardware, plus the pre-existing M9/M11 backlog (MP3 tag writes untested, no
CLI/TUI entry point for either function) that was never specific to this
handoff. See `docs/tasks/backlog.md`.

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
