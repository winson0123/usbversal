# Rekordbox → Serato Analysis Sync (Stage 2)

**Status:** planned (Stage 2) — sequenced behind [Serato index bootstrap](serato-index-bootstrap.md)  
**Related:** [ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md), [ADR 0006](../decisions/0006-serato-analyzed-and-beatgrid-tags.md), [playlist migration](rekordbox-to-serato-playlist-migration.md)

> **Update 2026-08-21.** This work is **no longer abandoned**. A controlled
> Lexicon experiment decoded the `Serato Markers2` cue format from a
> byte-exact before/after pair and showed the analyzed gate is satisfied by
> writing a track's *real* hot cues. The section below records why the first
> attempt failed; the plan that replaces it is in
> [ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md).

## Full analysis surface

A study of every analysis field — cues, beatgrid, BPM, key, gain — against the
fixture pair and the real stick is in
[analysis-data-study.md](../schemas/analysis-data-study.md). Headline findings:

- A Lexicon sync changes **only** `Serato Markers2`. Audio is untouched,
  `BeatGrid` and `Autotags` are byte-identical.
- BPM appears in four places that all agree; key passes through unchanged;
  gain has no Rekordbox source.
- 93% of the library is constant tempo, so beatgrid mapping would be a single
  terminal marker — but nothing writes beatgrids, so there is no oracle.
- **36 of 40 sampled MP3s are ID3v2.3** while the only fixtures are v2.4, and
  29 of 40 already carry `Serato Markers2`, so writes are updates.

## Current scope

Usbversal copies **Rekordbox playlists to Serato crates** (`migrate-playlist`). It does **not** copy BPM, key, beatgrid, hot cues, or waveform analysis into Serato tags.

After migration, **run Analyze Files in Serato DJ** (offline mode) so Serato writes its own GEOB tags on each audio file.

```bash
python -m app.cli migrate-playlist --mount /mnt/usb --playlist-name "Pocket"
# Then in Serato: Analyze Files on the library / crate
```

## Why we stopped pursuing tag sync

An experimental `sync-analysis` path was implemented and tested on a Pocket playlist USB stick (80 tracks). Serato did not reliably treat Rekordbox-ported metadata as native analysis. Findings are recorded in [ADR 0006](../decisions/0006-serato-analyzed-and-beatgrid-tags.md).

### Summary of incompatibilities

| Issue | What we observed |
|-------|------------------|
| **“Analyzed” gate** | Serato’s analyzed count matched **Markers2 cue entries**, not presence of Analysis/Overview/BeatGrid tags. Tracks with only COLOR/BPMLOCK in Markers2 stayed unanalyzed. |
| **Anchor cue workaround** | Native Serato analyze leaves cue index 0 near the first beat; injecting a synthetic cue helped some tracks but is undocumented and fragile. |
| **Beatgrid encoding** | Serato derives segment BPM from marker spacing. A compact grid with a hard-coded +120 s terminal produced **~2 BPM for the first bar** and a bar jump at 2:00. Full ANLZ downbeat export fixed math but did not resolve the analyzed gate alone. |
| **Format split** | Serato uses ID3 GEOB on MP3/AIFF/WAV, Vorbis comments on FLAC, atoms on MP4 — one writer does not cover a mixed library. |
| **`Serato Offsets_`** | ~16 KB MP3-only tag from native analyze; undocumented; not implemented. |
| **Library cache** | Serato may require **Rescan ID3 Tags** after external tag writes; behavior is inconsistent. |

### Conclusion

Porting Rekordbox USBANLZ / exportLibrary analysis into Serato GEOB tags is **possible in theory** (see [Holzhaus/serato-tags](https://github.com/Holzhaus/serato-tags)) but **not reliable enough** for production without reverse-engineering more of Serato’s private format and analyzed-state rules. **Re-analyzing in Serato after playlist migration** is the supported workflow.

## Hard problems, restated against the 2026-08-21 evidence

1. Reproduce Serato’s **analyzed** state without native analyze (Markers2 cues, Offsets_, Overview quality).
2. Variable-tempo beatgrid export from Rekordbox ANLZ with Serato-compatible marker spacing.
3. Hot cue / memory cue mapping (Rekordbox extended cues vs Serato Markers_ / Markers2).
4. Per-format tag containers (FLAC, WAV, MP4).
5. Idempotent sync that does not clobber existing Serato analysis on partially analyzed libraries.

Reference implementation was removed from the codebase; ADR 0006 retains test-stick measurements.

### Status of each against current evidence

| # | Problem | Now |
|---|---------|-----|
| 1 | Reproduce Serato's analyzed state | **Explained.** Write the track's real hot cues from ANLZ `PCO2` into `Serato Markers2`; that is what Lexicon does. TASK-082 |
| 2 | Variable-tempo beatgrid export | **Still open.** Only single-marker grids observed; ADR 0006's 2 BPM first-bar bug remains a live hazard. TASK-083 |
| 3 | Hot cue / memory cue mapping | **Partly solved.** Slot = rekordbox cue `position`, position = ms as u32 BE. Only hot cues map; memory cues do not. Colour table is 2 entries deep. TASK-081 |
| 4 | Per-format tag containers | **Still open.** WAV (RIFF `id3 ` chunk) is the only container with a fixture; **MP3 — the one that matters — is untested.** FLAC/MP4 unaddressed. TASK-084 |
| 5 | Idempotent sync | **Still open.** Must preserve GEOB frames it does not own, and not clobber existing Serato analysis. TASK-085 |

Decoded formats: [serato-schema-notes.md](../schemas/serato-schema-notes.md). Ground-truth fixtures: [`tests/fixtures/serato/`](../../tests/fixtures/serato/).
