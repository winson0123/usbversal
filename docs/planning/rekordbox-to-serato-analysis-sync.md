# Rekordbox → Serato Analysis Sync (Future Work)

**Status:** deferred — not implemented; playlist migration only  
**Related:** [rekordbox-to-serato-playlist-migration.md](rekordbox-to-serato-playlist-migration.md), [ADR 0006](../decisions/0006-serato-analyzed-and-beatgrid-tags.md)

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

## If revisited later (TASK-034)

Hard problems to solve before any revival:

1. Reproduce Serato’s **analyzed** state without native analyze (Markers2 cues, Offsets_, Overview quality).
2. Variable-tempo beatgrid export from Rekordbox ANLZ with Serato-compatible marker spacing.
3. Hot cue / memory cue mapping (Rekordbox extended cues vs Serato Markers_ / Markers2).
4. Per-format tag containers (FLAC, WAV, MP4).
5. Idempotent sync that does not clobber existing Serato analysis on partially analyzed libraries.

Reference implementation was removed from the codebase; ADR 0006 retains test-stick measurements for future attempts.
