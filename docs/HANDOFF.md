# Handoff — 2026-08-21

State of Usbversal after a session that removed a third of the codebase, built
the Rekordbox → Serato write path, and validated it on a real stick.

**Read [`AGENT.md`](../AGENT.md) first.** One task at a time, one commit per
task, state files updated after each.

---

## Where things stand

| | |
|---|---|
| Tests | 132 passed, 3 skipped (`ruff` and `ruff format` clean) |
| Size | app 4,633 lines, tests 2,389 |
| Branch | `main`, clean, **no remote** |
| Test stick | `/mnt/usb`, bind-mounted to `/mnt/wsl/usb` — see below |

Run the suite against real hardware with:

```bash
USBVERSAL_TEST_MOUNT=/mnt/wsl/usb .venv/bin/pytest -q
```

### The WSL mount trap

This shell runs in a private mount namespace, so a stick mounted afterwards in
the host namespace is invisible to it — `/mnt/usb` looks like an empty
directory. Bind-mount under `/mnt/wsl`, which is a shared peer group:

```bash
sudo mount -t vfat /dev/sde1 /mnt/usb -o uid=1000,gid=1000,utf8
sudo mkdir -p /mnt/wsl/usb && sudo mount --bind /mnt/usb /mnt/wsl/usb
```

Both are lost on reboot. An empty mount point means *no stick*, not a valid path.

---

## What works

**Detection.** `probe_mount()` stats a few known paths and returns a verdict in
0.32 ms. `open_library()` opens the Rekordbox export once per session and hands
back a `UsbLibrary` that services take. Opening costs ~450 ms, so it is paid
once: a 66-playlist sync went from ~80 s of repeated reopening to about 3 s.

**Sync state.** `playlist_sync_states()` returns per-playlist counts for the
traffic-light tree. It is a three-way comparison — playlist against crate for
the colour, and against the Serato index for whether green is reachable at all.
Whole library in 61 ms.

**Playlist sync.** `sync_playlists()` takes one backup per run, adds missing
track records to `database V2` in a single pass, writes one crate per playlist,
then merges `neworder.pref`. Database first, so an interruption leaves
unreferenced records rather than crates pointing at unknown tracks.

**Analysis sync.** Hot cues and beatgrids read from ANLZ and written into audio
tags. **Confirmed working in Serato** on 2026-08-21 for the `test` playlist:
crate present, cues on the beat, beatgrids correct, tracks analysed.

Safety throughout: `WriteContext` cannot be constructed without a backup
directory whose manifest loads and whose files pass checksum verification.

---

## Do this next

### 1. Confirm the dense beatgrid in Serato — blocking

`TASK-119` replaced the beatgrid encoder. It now carries every Rekordbox beat
across directly instead of collapsing runs and letting Serato interpolate,
which is ~1000x more accurate (0.015 ms worst error against 115 ms) and much
simpler.

**Serato has not seen this form.** The earlier validation covered
single-marker grids. The `test` playlist was rewritten with dense grids under
backup `20260821T092614Z`; open Serato and check the grids still read correctly
and the tracks still show as analysed.

If it fails, roll back and reconsider:

```bash
python -m app.cli rollback --mount /mnt/wsl/usb --backup-id 20260821T092614Z
```

If it passes, **two documents are stale** and must be corrected: the
"constant-tempo only" recommendation in
[analysis-data-study.md](schemas/analysis-data-study.md) and the variable-tempo
caveat in [ADR 0008](decisions/0008-beatgrid-and-cue-sync-validated-in-serato.md).
Both were written when variable tempo looked hard; direct import makes it free.

### 2. Wire cue and beatgrid sync into `sync_playlists`

It exists only as a script run by hand. `sync_playlists()` writes crates and
database records but does not touch audio. Needs: audio files in the backup set
(currently added ad hoc), an explicit opt-in since it mutates music, and a skip
for tracks with no cues and no grid.

### 3. The MP3 path is untested

Everything validated is WAV. **36 of 40 sampled MP3s are ID3v2.3** while both
fixtures are v2.4, and the two size frames differently — a writer assuming v2.4
will corrupt v2.3. `write_geob` handles both on paper; neither is proven on MP3.
Validate on a copy before writing to a real MP3.

### 4. Then the TUI

The argparse CLI is a **test harness**, not the product. Target flow and the
remaining gaps are in [interactive-tui.md](planning/interactive-tui.md). The
service layer now covers detection, sync state, and sync; what is missing is the
playlist tree (`parent_id` exists but every consumer flattens it), progress with
an ETA, and cheap polling for a stick appearing.

---

## Known problems

**79 files carry a broken beatgrid.** Leftovers of an abandoned earlier attempt:
a terminal marker at exactly first beat + 120.000 s, implying 2.00 BPM for the
opening bar. That count matches the playlist used in that experiment. This tool
can regenerate them correctly; the repair has not been run, and was explicitly
deferred.

**Crate names are flat.** 59 of 66 playlists sit in folders, but crates use the
leaf name only, so folder structure is lost and same-named playlists in
different folders would collide. `find_crate_name_collisions()` reports the
clash; nothing prevents it. The `Parent%%Child` convention is documented but
unverified — a wrong guess puts literal `%%` in crate names.

**Cue colours are Rekordbox's, not Serato's.** Rekordbox stores RGB in the ANLZ
entry and it is passed through unchanged. Lexicon maps onto a Serato palette
(`#FF0017` becomes `#CC0044`). Serato displayed ours fine. Largely academic:
230 of 232 cues in this library have no colour at all.

---

## Things worth knowing before changing code

**`serato-tools` cannot append tracks through its public API.** `DatabaseV2`
exposes `entries`, but `save()` writes `raw_data`, which only the private
`_dump()` refreshes — appending to `entries` and saving writes nothing and
raises nothing. A test asserts `_dump` still exists so an upgrade fails loudly.

**`Crate.DEFAULT_ENTRIES` is class-level and `add_track` mutates it.** Every new
crate inherits tracks added to earlier ones in the same process. `write_crate`
starts from a private copy; a test covers it. Without that, syncing 66
playlists would put all 4,156 track references in the last crate.

**Never use `serato_tools.usb_export.copy_crates_to_usb`** — it `rmtree`s the
destination `_Serato_`.

**Layer rules are enforced by tests.** `tests/test_architecture.py` parses every
module and asserts the layer table plus vendor confinement: `rbox` and
`serato_tools` may only be imported under `app/adapters/`.

**Code carries no historical reasoning.** Why something is shaped the way it is
belongs in `docs/`; the source states only what it does now.

---

## Formats

Decoded and verified, with the evidence:

- [serato-schema-notes.md](schemas/serato-schema-notes.md) — TLV container,
  crates, `database V2`, `neworder.pref`, `Markers2`, `BeatGrid`
- [analysis-data-study.md](schemas/analysis-data-study.md) — what a Lexicon sync
  actually changes, and how cues, grids, BPM, key, and gain correspond
- [rekordbox-schema-notes.md](schemas/rekordbox-schema-notes.md) — ANLZ, and the
  `export.pdb` spec, which has never been parsed

`tests/fixtures/serato/` holds the before/after WAV pair that proves the cue
encoding: applying the cues to `BEFORE` reproduces `AFTER` byte for byte. Both
came from Lexicon, so it is an oracle rather than a restatement of our own
encoding. Keep it.
