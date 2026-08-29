# Rekordbox Schema Notes

Accumulated reverse-engineering. **Do not treat as complete.**

## Status legend

| Tag | Meaning |
|-----|---------|
| [confirmed] | Verified in fixture or test |
| [assumed] | Industry/docs hint, not verified on USB |
| [unknown] | Not yet observed |

## Observed tables

| Table | Source | Tag |
|-------|--------|-----|
| _none yet_ | awaiting fixtures | [unknown] |

## Detection heuristic (planned)

| Condition | `version_label` |
|-----------|-----------------|
| `djmdContent` present | `rekordbox-sqlite-djmd` |
| else | `rekordbox-sqlite-unknown` |

## Planned tables (assumed — verify on real DB)

| Table | Purpose | Tag |
|-------|---------|-----|
| `djmdPlaylist` | Playlists | [assumed] |
| `djmdSongPlaylist` | Playlist membership | [assumed] |
| `djmdArtist` | Artist metadata | [assumed] |
| `djmdContent` | Track rows | [assumed] |

## Relationships (inferred)

```text
djmdPlaylist ──< djmdSongPlaylist >── djmdContent
```

**Tag:** [assumed] — verify with `PRAGMA foreign_key_list` on real DB.

## Unknown fields policy

| Rule | Status |
|------|--------|
| SELECT known columns only | planned |
| Never write NULL to unknown columns | planned |
| Log unseen columns on read | planned |

## Mutation safety

| Operation | Notes |
|-----------|-------|
| INSERT playlist row | needs backup + transaction |
| UPDATE track metadata | preserve unmapped columns |
| DELETE | avoid unless explicit user op |

## One Library export (`exportLibrary.db`) [confirmed]

Read via `rbox.OneLibrary` on `/mnt/usb` (2026-05-25):

| Table (rbox) | Purpose |
|--------------|---------|
| `playlist` | Playlist/folder nodes (`attribute`, `parent_id`, `name`) |
| `playlist_content` | Track membership snapshot |

`playlist.attribute` (rbox `PlaylistType`): `List` (0), `Folder` (1), `SmartList` (4).

Observed on test USB: **64 List, 6 Folder, 0 SmartList**.

## Smart playlists vs normal playlists on USB [confirmed]

**Do not distinguish smart vs manual playlists for USB export workflows.**

Rekordbox’s intended export behavior is to ship a **snapshot** for the player:

- Tracks are materialized in `playlist_content`.
- The export `playlist` row has **no `smart_list` rules column** (unlike `master.db` / `djmdPlaylist`).
- Desktop “intelligent playlists” often appear as `List` (0) on the stick even when smart in the PC library.
- `SmartList` (4) may be absent entirely on export (true for `/mnt/usb`).

Usbversal treats exported nodes as **folder** vs **playlist (list)** only. Rule-based refresh belongs on `master.db`, not USB tooling.

## Real device validation (`/mnt/usb`)

| Item | Recorded |
|------|----------|
| exportLibrary.db | `/mnt/usb/PIONEER/rekordbox/exportLibrary.db` [confirmed, 70 playlist nodes] |
| export.pdb path | `/mnt/usb/PIONEER/rekordbox/export.pdb` [confirmed scan 2026-05-25, DeviceSQL] |
| PIONEER/rekordbox dir | `/mnt/usb/PIONEER/rekordbox` [confirmed] |
| Contents/rekordbox | `/mnt/usb/Contents/rekordbox` [confirmed, lower confidence] |
| rekordbox version | _pending_ |

---

## `export.pdb` — DeviceSQL [assumed — NOT parsed on this stick]

Sourced from public format documentation (Deep Symmetry's `crate-digger`, the
`rekordbox_pdb.ksy` Kaitai Struct spec), **not** from a real file on `/mnt/usb`.
usbversal currently rejects this format with `UnsupportedDatabaseError` and
requires One Library instead. TASK-090 (a DeviceSQL reader for older sticks)
was dropped — we are not maintaining a second Rekordbox parser.

**File header**: `u32 0`, `u32 page_size` (usually 4096), `u32 num_tables`,
`u32 next_unused_page`, `u32 unknown`, `u32 sequence`, `u32 gap`. Then
`num_tables` entries of 16 bytes: `type`, `empty_candidate`, `first_page`,
`last_page`.

**Table types**: `0`=tracks, `1`=genres, `2`=artists, `3`=albums, `4`=labels,
`5`=keys, `6`=colors, `7`=playlist_tree, `8`=playlist_entries, `13`=artwork,
`16`=columns.

**Page** at offset `page_index * page_size`, with a 0x28-byte header: `gap`,
`page_index`, `type`, `next_page`, `unknown1`, `unknown2`, `num_rows_small`
(u8), three more u8 including `page_flags`, `free_size` (u16), `used_size`
(u16), `unknown5`, `num_rows_large` (u16), `unknown6`, `unknown7`. Data page
test: `(page_flags & 0x40) == 0`. Row heap starts at page offset `0x28`.

```text
num_rows = (num_rows_large > num_rows_small && num_rows_large != 0x1fff)
           ? num_rows_large : num_rows_small
```

**The row index grows backwards from the end of the page**, in groups of 16.
For group `g` (0-based): `base = page_end - (g * 0x24)`; `row_present_flags` is
a u16 at `base - 4`; row `j` offset is a u16 at `base - (6 + 2*j)`, relative to
heap start. Row `g*16 + j` is present only if bit `j` of the flags is set.

**DeviceSQL string** — dispatch on the first byte:

| First byte | Encoding |
|------------|----------|
| `(b & 1) == 1` | short ASCII, length = `(b >> 1) - 1`, body follows |
| `b == 0x40` | long ASCII: `u2 length`, `u1 unknown`, body of `length - 4` |
| `b == 0x90` | long UTF-16**LE**: `u2 length`, `u1 unknown`, body of `length - 4` |

**Track row** field order: `u2 unknown1`, `u2 index_shift`, `u4 bitmask`,
`u4 sample_rate`, `u4 composer_id`, `u4 file_size`, `u4 unknown2`,
`u2 unknown3`, `u2 unknown4`, `u4 artwork_id`, `u4 key_id`, `u4 orig_artist_id`,
`u4 label_id`, `u4 remixer_id`, `u4 bitrate`, `u4 track_number`, `u4 tempo`
(**BPM × 100**), `u4 genre_id`, `u4 album_id`, `u4 artist_id`, `u4 id`,
`u2 disc_number`, `u2 play_count`, `u2 year`, `u2 sample_depth`, `u2 duration`,
`u2 unknown5`, `u1 color_id`, `u1 rating`, `u2 unknown6`, `u2 unknown7`, then
**21 × u2 string offsets** relative to row start.

String indices that matter: **13 = analyze_path**, **16 = title**,
**18 = filename**, **19 = file_path**.

**Playlist tree row** (type 7): `u4 parent_id`, `u4 unknown`, `u4 sort_order`,
`u4 id`, `u4 raw_is_folder` (nonzero = folder), then DeviceSQL string `name`.

**Playlist entry row** (type 8): `u4 entry_index`, `u4 track_id`,
`u4 playlist_id`.

**Validate any parser** by dumping the playlist tree and confirming the names
are readable strings. Garbage names mean the row-group arithmetic is wrong.

## ANLZ analysis files [assumed — NOT parsed]

Track row string index 13 (`analyze_path`) points at the ANLZ folder, e.g.
`/PIONEER/USBANLZ/P060/0001F812/ANLZ0000.DAT`. The `.EXT` sibling holds the
extended data. A rekordbox stick carries thousands of these (5,077 files on the
reference stick).

Tagged container: `PMAI` header, then sections each with a 4-char tag, header
length, and total length.

| Tag | File | Contents |
|-----|------|----------|
| `PQTZ` | `.DAT` | Beatgrid. Entries of `u2 beat_number` (1..4), `u2 tempo` (**BPM × 100**), `u4 time` (**milliseconds**). |
| `PCOB` | `.DAT` | Cue list, older format, **no colour**. |
| `PCO2` | `.EXT` | Extended cue list — includes colour and comment. **Prefer this one.** Carries hot cue number and time in ms. RGB is at PCP2 body offset 28, not the last 3 bytes (TASK-253). |

Cue entries distinguish memory cues from hot cues; **only hot cues map to Serato
cue slots**. Saved loops live in `PCO2` with an end time.

These are the source data for Stage 2 analysis sync — see
[ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md).

## Why One Library is preferred over `export.pdb`

| Source | Status |
|--------|--------|
| `exportLibrary.db` (One Library) | [confirmed] readable via `rbox` — 70 playlists / 1625 tracks on `/mnt/usb` |
| `master.db` (desktop) | SQLCipher-encrypted; header is random bytes, not `SQLite format 3`. **Not readable directly.** |
| `export.pdb` (DeviceSQL) | [assumed] spec above; unparsed |

Both `exportLibrary.db` and `export.pdb` are present on the test stick.
usbversal reads the former and does not need a DeviceSQL parser for rb7-class
exports. Older sticks that ship `export.pdb` only are out of scope (TASK-090
dropped).
