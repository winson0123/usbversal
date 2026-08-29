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
| ~~`TASK-053`~~ | ~~`apply` with plan file~~ | Removed in TASK-109; superseded by `sync_playlists` |

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
| ~~`TASK-071`~~ | ~~Add `neworder.pref` to the Serato backup set~~ | Done — TASK-114 added it to `serato_files_on_mount` |
| ~~`TASK-073`~~ | ~~`database V2` append writer~~ | Done — TASK-112. A Rekordbox-to-`otrk` field mapper is still outstanding and moves to TASK-113. |
| ~~`TASK-113`~~ | ~~Rekordbox metadata → `otrk` fields~~ | Done — TASK-113, formats derived by diffing 793 records Lexicon wrote |
| ~~`TASK-074`~~ | ~~`neworder.pref` merge/write~~ | Done — TASK-114, `adapters/serato/neworder.py` |
| ~~`TASK-075`~~ | ~~Nested playlist folders → `Parent%%Child.crate`~~ | Done — `crate_name_for()` walks ancestor folders, joined with `%%`. Confirmed in Serato (TASK-245): `Gigs → Played → safety day` shows as a three-level crate. No empty parent crate files required. |
| ~~`TASK-076`~~ | ~~Bootstrap `_Serato_` on a rekordbox-only stick~~ | Done — `services/bootstrap_service.py`'s `bootstrap_serato_library()` creates `_Serato_/`, `Subcrates/`, an empty `database V2`, and `neworder.pref` only when none exist yet; backs up the Rekordbox files first (proven byte-identical after, by test) and is a no-op — never a merge or regenerate — on a stick that already has a Serato library. Wired into the TUI's `HomeScreen` so a plain rekordbox stick can reach the Library screen and sync instead of dead-ending on `SeratoLibraryRequiredError`. Also fixed, incidentally: `create_backup`'s auto id collided when two backup-gated operations landed in the same wall-clock second, which chaining bootstrap straight into a sync exposed. |

## M9 — Analysis Tag Sync (Stage 2)

Writes hot cues and beatgrids into the **audio files**. Requires
[ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md);
supersedes the abandoned TASK-034. **Mutates user audio — explicit confirmation
plus per-file backup required.** Sequenced strictly after M8.

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-080`~~ | ~~ANLZ reader — `PQTZ` beatgrid, `PCO2` hot cues~~ | Done — TASK-115, `adapters/rekordbox/anlz.py` |
| ~~`TASK-081`~~ | ~~Rekordbox → Serato cue colour table~~ | Dropped — Rekordbox stores RGB in the ANLZ entry, so no table is needed |
| ~~`TASK-082`~~ | ~~`Serato Markers2` GEOB writer (hot cues)~~ | Done — TASK-115, byte-exact against the fixture pair |
| ~~`TASK-083`~~ | ~~`Serato BeatGrid` + `Autotags` GEOB writer~~ | Done — TASK-117/119; `Autotags` deliberately not written |
| ~~`TASK-084`~~ | ~~Container tag I/O — MP3 / WAV / FLAC~~ | Done — WAV fixtures, ID3v2.3/v2.4 MP3 unit tests (TASK-241), FLAC Vorbis comments (TASK-242). MP4 out of scope. Live Serato confirmation still outstanding. |
| ~~`TASK-085`~~ | ~~`sync-analysis` CLI (re-introduce)~~ | Dropped — CLI removed in TASK-240. Analysis already runs from the TUI. |
| ~~`TASK-249`~~ | ~~Do not abort sync on leftover Markers2 base64~~ | Done — drop one `4n+1` character; remaining decode errors skip the track. Findings in ADR 0010. |

## M10 — Deferred

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-090`~~ | ~~`export.pdb` DeviceSQL reader~~ | Dropped — Pioneer CDJ-era DeviceSQL exports only. We ship against One Library (`exportLibrary.db`). Not maintaining a second Rekordbox parser. |
| ~~`TASK-091`~~ | ~~Reconcile `ruff format` drift~~ | Done |

## M10.5 — Finish the analysis port

The adapters work and are confirmed in Serato, but no service or command calls
them. See [HANDOFF.md](../HANDOFF.md).

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-130`~~ | ~~Wire grids, cues and the library index into `sync_playlists`~~ | Done — every synced track with Rekordbox analysis now gets its beatgrid and hot cues written, and `location.sqlite` is updated for any track that got a grid. Backs up each audio file it is about to touch. No index BPM correction pass yet for the ~70 already-wrong rows (TASK-132). |
| ~~`TASK-131`~~ | ~~Move write verification into `write_geob`~~ | Done — `verify_geob_rewrite()` checks size, audio-stream hash, and frame read-back before any byte reaches disk; a failure raises `TagFormatError` and the original file is untouched. |
| ~~`TASK-132`~~ | ~~Codify the index BPM rules~~ | Done — `correct_index_bpm()` in `sync_service.py` sets every indexed track's BPM to its first beat's tempo, library-wide (not just tracks in a playlist being synced), and never inserts a row Serato does not already have. Not yet run against the real stick's ~70 wrong rows — see HANDOFF.md. |
| ~~`TASK-133`~~ | ~~Never-clobber regression test~~ | Done — `tests/test_never_clobber.py` proves `write_geob` leaves `Key`, `Energy`, `CuePoints`, and Mixed In Key's own unprefixed `BeatGrid` byte-identical across a beatgrid write, a cue write, and a removal of our own frame, and refuses (rather than evicting a foreign frame) when a write would not fit. |
| ~~`TASK-134`~~ | ~~Correct the retracted claims in `docs/`~~ | Done — TASK-126, `analysis-data-study.md` and `serato-schema-notes.md` |
| ~~`TASK-127`~~ | ~~Cover the ANLZ reader with tests~~ | Done — not originally backlogged; the reader had no direct test coverage until this pass, `tests/test_anlz.py` |

## M11 — Interactive TUI (the shipped product)

> IDs renumbered to the 200s on 2026-08-21: 110-116 had been reused by the
> write-path work and collided.

The argparse CLI is a **test harness**, not the deliverable. Plan:
[interactive-tui.md](../planning/interactive-tui.md). These gate the real tool
and none of them exist yet.

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-200`~~ | ~~Per-playlist sync state~~ | Done — TASK-111, `playlist_sync_states()` |
| ~~`TASK-201`~~ | ~~Playlist tree model~~ | Done — `core/playlist_tree.py` (`build_playlist_tree`) nests the flat list; `sync_service.playlist_tree_sync_states` adds the per-folder rollup (green only if every descendant is synced, red only if none are, yellow otherwise; an empty folder reads red, not vacuously green). |
| ~~`TASK-202`~~ | ~~Single "valid DJ USB?" readiness verdict~~ | Done — TASK-110, `probe_mount()` returns None for an empty mount point |
| ~~`TASK-203`~~ | ~~Removable-media polling~~ | Done — `storage/mount_watch.py`'s `MountWatcher.poll()` diffs `MountScanner.list_mounts()` against the previous poll's set; one directory listing per poll, no library detection or database opens. Callers run `services.library.probe_mount` (also stat-only) on an appeared mount to check DJ USB validity. |
| ~~`TASK-204`~~ | ~~Progress rate + ETA~~ | Done — `jobs/progress_rate.py`'s `ProgressRateTracker` averages rate over the whole run (steadier than a most-recent-interval rate for variable-cost steps like tag writes) and derives an ETA when `total` is known. Wired into `CliProgressRenderer`, which now appends `(N.N/s, eta Xs)` once a job has two samples, tracked per `job_id`. |
| ~~`TASK-205`~~ | ~~Batch sync over selected playlists~~ | Done — TASK-114, `sync_playlists()` takes one backup per run |
| ~~`TASK-206`~~ | ~~TUI framework ADR + shell~~ | Done — [ADR 0009](../decisions/0009-use-textual-for-the-tui.md) picked `textual`. `app/tui/` scaffolded with `UsbversalApp` and the Home screen (steps 1-2, Waiting/Detect), reachable via `usbversal tui` / `python -m app.tui`. Verified with a real PyInstaller build whose `tui` subcommand renders headless. Decomposed from the original one-line item — see TASK-207/208 below, added at the same time so the remaining screens aren't lost to scope creep. |
| ~~`TASK-207`~~ | ~~TUI Library screen~~ | Done — `app/tui/screens/library.py`. `playlist_tree_sync_states()` feeds a `textual.widgets.Tree`; space (a **priority** binding — Tree's own default binds space to expand/collapse, which a priority binding on the Screen overrides) toggles a leaf or, on a folder, every descendant playlist at once; enter reports the selection (running the sync is TASK-208). `HomeScreen` now pushes this screen once a valid library opens. |
| ~~`TASK-208`~~ | ~~TUI Progress + Done screens~~ | Done — `app/tui/screens/progress.py`. `sync_playlists()` gained an optional `on_progress` callback (called per analysis track — the slow part of a sync); `ProgressScreen` runs it in a worker and renders `textual.widgets.ProgressBar` plus rate/ETA text from `jobs.progress_rate.ProgressRateTracker`; `DoneScreen` shows the summary (enter returns to Library, escape quits). This is the first point `sync_playlists` is reachable from the TUI at all. (Ran via `asyncio.to_thread` originally — corrected in TASK-209, first real-hardware run crashed the process.) |
| ~~`TASK-209`~~ | ~~Fix rbox thread-affinity crash on real hardware~~ | Done — first run against a real stick aborted the process: `rbox`'s `PyOneLibrary` (pyo3) is not `Send` and panics if touched from any thread but the one that created it, and `asyncio.to_thread`'s shared default executor gives no such guarantee across calls. `RekordboxThreadMixin` (`app/tui/app.py`) pins every `open_library`/`list_playlists`/`playlist_tree_sync_states`/`sync_playlists` call to one dedicated single-worker thread for the app's whole lifetime via `run_rekordbox()`. Found, along the way: Textual dispatches `on_mount` (and other lifecycle messages) to *every* class in the MRO that defines one, not just the most-derived override — a test harness subclassing `UsbversalApp` and overriding `on_mount` pushed both screens; fixed by mixing `RekordboxThreadMixin` into a bare `App` instead of inheriting from `UsbversalApp`. Entirely unverifiable against mocked libraries (a `MagicMock` has no thread affinity to violate), which is exactly why every prior TUI task's tests passed while the real thing crashed — noted as a real gap in this project's own test coverage, not just bad luck. |
| ~~`TASK-210`~~ | ~~Library screen: refresh on resume, show synced/total counts~~ | Done — two real-hardware findings from the same session. (1) A synced playlist still showed "not synced" until the whole app restarted: `LibraryScreen` built its tree once in `on_mount` and never again, so popping back from Progress/Done landed on stale data. `on_screen_resume` (fires on first activation too, confirmed empirically, so it's the only place the tree is built now) rebuilds the whole tree from disk every time this screen becomes active. (2) User asked for visible `x/x` counts, not just the state word. `PlaylistTreeSyncState` gained `synced`/`total` fields (a leaf's own `in_crate`/`total`; a folder's, the sum of its children's — composes through nesting the same way `state` already did), and `LibraryScreen._label()` renders name/count/state as fixed-width columns (`Tree` has no real column model, so this is the closest a label string gets without giving up the folder hierarchy a `DataTable` can't show). |
| ~~`TASK-211`~~ | ~~Library screen: true column alignment, "All playlists" node~~ | Done — user reported the count/state columns still looked jagged, and asked for an "All" option. The jaggedness was real: Tree's guide lines and expand icon eat a *different* number of cells per row depending on nesting depth and folder-vs-leaf, so fixed-width padding on the label text alone drifts — measured against `Tree.render_line()` output directly (`▼ `/`├── `/`│   └── ` etc.) to derive the exact formula (`depth * guide_depth + icon_width`), now in `_prefix_width()`; verified afterward that the count column lands on the identical character column across every depth/kind combination tested. Switched the checkbox glyphs from unicode (✓/·/~, ambiguous terminal cell width depending on font) to plain ASCII (x/-/~) for the same reason. "All playlists" is a real collapsible folder node (`e` toggles expand/collapse on the highlighted folder — Tree's own default was on space, which TASK-207 already redirected to selection) containing every top-level playlist/folder as children, not a sibling summary row, so collapsing it hides the whole library and toggling it selects everything. `combine_sync_states` (renamed from the private `_rollup_state`) computes its aggregate state, reused rather than duplicated. |
| ~~`TASK-212`~~ | ~~Fix rbox thread-affinity crash on TUI exit~~ | Done — user hit a new crash every time they quit: `PyOneLibrary is unsendable, but is being dropped on another thread`. Same pyo3 rule TASK-209 fixed for *use*, but this time for *drop*: `HomeScreen.library`/`LibraryScreen._library`/`ProgressScreen._library` all reference the same opened library, and during normal navigation that's harmless (earlier screens stay on the stack), but on quit Textual tears down the *whole* screen stack from the main thread, and whichever screen holds the last live reference triggers the Rust-side Drop there instead of on the thread that created it. `UsbversalApp.action_quit` now nulls every screen's reference itself first, in one call pinned to the dedicated rekordbox thread, before handing off to Textual's own teardown — whichever null assignment turns out to be the deciding one now runs in the right place. Same test-coverage gap as TASK-209: never reproduced in this environment, since the TUI test suite mocks the rekordbox adapter. |
| ~~`TASK-213`~~ | ~~Home screen: centered ASCII banner, spinner, error state~~ | Done — user asked for a centered "usbversal" ASCII banner, a spinning glyph under it while detecting, and an error message replacing the spinner (not the banner) on scan failure, with no custom theme — native terminal colours, Rich colour markup only where it adds information. Banner art is the user's own (picked over three figlet-generated candidates offered first); `_Spinner` is a hand-rolled `Static` subclass rather than Textual's stock `LoadingIndicator`, specifically because that widget's CSS reaches into theme variables (`$primary`/`$boost`) the user didn't want. Each of banner/spinner/status needed its own `Center` wrapper inside the outer `CenterMiddle` — Textual's `align: center middle` centers the whole child *group's* bounding box (sized to the widest child) as one block rather than each child independently, found by reading `.region` on each widget before and after. |
| ~~`TASK-214`~~ | ~~TUI: use native terminal colours instead of Textual's dark theme~~ | Done — user reported the whole TUI "turned black". Textual's own default theme paints `App`/`Screen` background as a fixed near-black hex (`#121212`) no matter what the terminal's actual colours are — the exact thing TASK-213 was supposed to avoid, just not actually switched off yet. Fixed with `App(ansi_color=True)`, which flips on Textual's `:ansi` CSS mode (`background: ansi_default` resolves to Rich's `ColorType.DEFAULT`, i.e. "no override, whatever the terminal already has"), confirmed via direct `Style` inspection on rendered segments. Two stock widgets still leaked a fixed dark colour even in ansi mode — `Footer` has no `:ansi` rule of its own at all, and `Tree`'s only covers text/guides, not its own background — both neutralized with a small app-level CSS override. Functional highlight colours (the tree's selection cursor, the progress bar's fill) were deliberately left alone — they convey real information, not a theme. |
| ~~`TASK-215`~~ | ~~Home screen: retry-on-enter and manual path entry with Tab completion~~ | Done — user asked to be able to insert a stick and press enter to retry scanning, and optionally type a path directly, with Tab completion. A `_PathInput` (an `Input` subclass) sits under the spinner/status slot, auto-focused on mount; submitting it empty calls `poll_mounts()` immediately rather than waiting for the 1s timer tick (the "insert it now, hit enter" case), and submitting it with text opens that path directly through the same `_open()` bootstrap/open/hand-off path a watcher-discovered mount uses, disabling the input while that's in flight and re-enabling it (with focus restored) if it fails. Tab completion (`_complete_path`) is shell-style: completes to the longest common prefix among matching directory entries, adds a trailing slash for a single unambiguous directory match, and no-ops when nothing new can be added. A plain (non-priority) `tab` binding on `_PathInput` itself was enough to beat `Screen`'s own default `tab` → `app.focus_next` binding, since Textual checks a focused widget's own bindings before its ancestors'. |
| ~~`TASK-216`~~ | ~~Detect USB sticks under /media/$USER, show the mount on the Library screen~~ | Done — the Linux mount scanner only ever checked `/mnt/*` (this project's own WSL dev environment's bind-mount setup); a real desktop Linux session auto-mounts removable media under `/media/$USER/<device>` via udisks2/gvfs instead, and nothing scanned that. New `LinuxMediaScanner` covers it (`getpass.getuser()` for `$USER`, same directory-listing shape as `LinuxMntScanner`); `get_mount_scanner()` now returns a `_CompositeScanner` merging both on Linux rather than picking one, since a box could plausibly have mounts in either place. `LibraryScreen` now shows `Mounted: <path>` (dim text-style, no colour) above the tree, from `UsbLibrary.mount` — whichever path actually got opened, whether auto-detected from either scanner or typed manually via TASK-215's input. |
| ~~`TASK-217`~~ | ~~Remove WSL-only /mnt scanning, add a real macOS scanner and USBVERSAL_MOUNT override~~ | Done — user pointed out real deployment is Windows/Linux/macOS, not WSL, so `LinuxMntScanner` (the `/mnt/*` scan, with its `{"wsl", "wslg", "c"}` exclusion list — meaningless outside this project's own WSL dev sandbox) is gone entirely; `LinuxMediaScanner` (`/media/$USER`) is now the sole Linux auto-detect path. New `MacVolumesScanner` scans `/Volumes/*` (excluding the `Macintosh HD` boot volume) — macOS was previously only a `_stub` flag in `repository-state.json` with no actual implementation; `get_mount_scanner()` now branches three ways (`Windows`/`Darwin`/else) instead of two. New `EnvMountScanner` reads a `USBVERSAL_MOUNT` env var as an escape hatch for whatever the automatic scanner doesn't cover, composed alongside the platform scanner on every OS — this is also how this project's own dev sandbox now reaches its `/mnt/usb` test stick (`USBVERSAL_MOUNT=/mnt/usb`), replacing the removed automatic `/mnt` scan. Doc/CLI-help examples that said "e.g. /mnt/usb" throughout the app were updated to "e.g. /media/$USER/MY_USB", since the old example was really this dev sandbox's own path, not a representative one for real users. |
| ~~`TASK-218`~~ | ~~Home screen: only show manual path entry after auto-scan fails~~ | Done — TASK-215's path input was always visible and auto-focused from the moment the screen mounted; user asked for it to appear only once auto-scanning has actually failed at something, with the screen defaulting to just the spinner quietly searching until then. `_hide_input()`/`_reveal_input()` tie the input's visibility to the same spinner/error toggle `_show_spinner()`/`_show_error()` already drove — hidden inputs are also explicitly `disabled`, not just `display: none`, since Textual still auto-focuses a hidden-but-enabled widget when it's the only focusable one on screen (confirmed empirically — without this, a user could type into an invisible field). `_reveal_input()` only focuses on the actual hidden -> visible transition, not on every later poll tick that re-confirms the same failure, so it doesn't steal focus back from wherever the user clicked. Placeholder text: "Press enter to retry auto-scan, or enter an absolute path". |
| ~~`TASK-219`~~ | ~~Progress screen: verbose per-track log, green/red colour instead of theme~~ | Done — user couldn't tell what the Progress screen was actually doing beyond a single overwriting counter line, and asked for verbose output: green for normal progress, red on error. `sync_playlists`'/`_sync_analysis`'s `on_progress` callback gained two arguments (`track: str`, `error: str | None`) — the track path and its own failure message when it has one, captured per-iteration in `_sync_analysis`'s existing per-track loop rather than only surfacing errors in the final report. `ProgressScreen` gained a `RichLog` under the existing bar, appending one line per track: `Text(..., style="green")` on success, `style="red"` on failure — `rich.text.Text` objects, not markup strings, since a track path or exception message is arbitrary data that could itself contain `[...]` and corrupt markup parsing (the same fix applied to `HomeScreen._show_error`, found while touching adjacent code). `DoneScreen`'s summary is coloured the same way: green when nothing failed, red on a hard failure or any per-track analysis error. `RichLog` itself needed the same `ansi_color` neutralization Footer/Tree got in TASK-214 — its own `DEFAULT_CSS` has no `:ansi` rule at all and defaults to a themed near-black background and grey text. |
| ~~`TASK-220`~~ | ~~Home screen: scanning caption + a more noticeable pulsing-dot spinner~~ | Done — user reported seeing only the spinning circle on first launch, no message. TASK-213 had deliberately reduced the searching state to spinner-only (previously a "Searching for valid DJ USBs…" line); that left a real user with no confirmation the tool was doing anything. Landed as a fixed caption, "Automatically detecting for a DJ USB…" (dim, not red -- routine information, not a problem), shown alongside the spinner via `HomeScreen._show_spinner()`; `on_mount` now calls `_show_spinner()` directly instead of separately hiding the status line, so the caption is visible from the very first frame. A platform-aware version (naming `/media/$USER`/`/Volumes`/drive letters and the `USBVERSAL_MOUNT` override) was built and tested first, then deliberately replaced with the fixed wording once the user saw where it was headed and asked for something simpler — removed again rather than left as unused code. Also swapped the spinner glyphs from a rotating quarter-circle (`◐◓◑◒`) to a pulsing dot (`· • ● •`) at a slightly slower tick, per the user's own "pulsing dot" description and complaint that the old spinner was "quite small". |
| ~~`TASK-221`~~ | ~~Home screen: sweeping scan-bar spinner instead of a pulsing dot~~ | Done — user asked to replace the single pulsing dot with a `[···••●]`-style bar, bright point sweeping left to right, repeating. `_scan_bar_frame(head)` renders a fixed-width bar with `●` at the head, `•` one step behind, and `·` everywhere else (both the not-yet-reached run ahead of the head and the fully faded trail behind it) — refined three more times in the same sitting: the resting fill was initially blank space, changed to `·` on request so the bar never looks like it has empty gaps; the bar width went 8 → 6 on request to match the user's own example, then the user directly edited it down to 4 themselves. `_Spinner`'s public shape (id, CSS, mount lifecycle) never changed across any of this, only what it renders each tick. |
| ~~`TASK-222`~~ | ~~Home screen: scan timeout so nothing plugged in does not spin forever~~ | Done — user reported the screen getting "stuck" with nothing plugged in, asked for a retry/timeout. `poll_mounts()` previously only ever set `_seen_invalid` (the flag that reveals the manual-path input and stops looking hopeful) when a mount *appeared and was rejected* — if nothing ever appeared at all, the screen spun quietly forever with no way to reach the input. New `SCAN_TIMEOUT_S` class attribute (15.0 initially, then 3.0 — see TASK-223) and `self._searching_since` (a `time.monotonic()` timestamp from `__init__`); once the timeout passes with nothing having appeared, `_seen_invalid` is set exactly as if a rejection had happened, reusing the same `_show_error(_NONE_FOUND)` path and message rather than adding a second, parallel "timed out" state and string. |
| ~~`TASK-223`~~ | ~~Home screen: shorten the scan timeout to 3 seconds~~ | Done — user: "can you change to 3 seconds? don't need that long." `SCAN_TIMEOUT_S` 15.0 -> 3.0; every test referencing it already read `home.SCAN_TIMEOUT_S` off the instance rather than a hardcoded number, so nothing else needed to change. |
| ~~`TASK-224`~~ | ~~Home screen: retry actually resumes scanning instead of re-printing the same error~~ | Done — user reported pressing enter to retry didn't do anything visible, found immediately after TASK-223's shorter timeout made hand-testing retry practical. Root cause: `_seen_invalid` is set once and never reset elsewhere (that's what stops hopeful auto-checking after a real rejection) — `on_input_submitted`'s empty-input branch called `poll_mounts()` without first resetting it, so a retry with nothing new to find just fell straight back into `_show_error(_NONE_FOUND)`, re-printing the identical message with no visible change, indistinguishable from Enter doing nothing. Fix: reset `_seen_invalid = False` and `_searching_since = time.monotonic()` right before calling `poll_mounts()` on an explicit retry, so the screen visibly flips back to the spinner for a fresh `SCAN_TIMEOUT_S` window before failing again if nothing's actually there. |
| ~~`TASK-225`~~ | ~~Home screen: fix truncated placeholder, real Tab-cycling through directories~~ | Done — two related complaints. (1) The input's fixed `width: 46` box was truncating its own placeholder text ("Press enter to retry auto-scan, or enter an absolute path"), visible as "... or enter (absolute path)." The retry hint moved out of the placeholder entirely and into the red error message (`_show_error` now appends a `_RETRY_HINT` constant to whatever message it's given) — the status line spans the whole screen width, not a fixed 46 cells, and the input's placeholder shrank to just "or enter an absolute path…", which fits. (2) `_complete_path`'s shell-style common-prefix completion never actually let a user step through the individual candidates it found — asked for real Tab-cycling instead. Replaced with `_match_candidates()` (lists every matching *directory* -- a file can never be a mount root, so files are excluded now, not just incidentally handled) and `_PathInput._cycle` state: each Tab press advances to the next match, wrapping around; typing anything that doesn't match where the cycle left off starts a fresh cycle from the new value, detected by comparing `self.value` against the candidate the previous Tab press set, with no separate "value changed" hook needed. |
| ~~`TASK-226`~~ | ~~Move TUI session-open into `prepare_library`~~ | Done — Home no longer orchestrates `bootstrap_serato_library` + `open_library` + a discarded `list_playlists()` itself. `services.library.prepare_library()` is the session-open path: bootstrap if needed, open, then list playlists so a database that cannot be read fails before Library takes over. `open_library` is unchanged so the CLI does not create `_Serato_`. |
| ~~`TASK-227`~~ | ~~Home screen: explicit `HomePhase` instead of `_seen_invalid`~~ | Done — one overloaded boolean (rejected / timed out / open failed / stop-hopeful-scan) replaced with `SEARCHING | FAILED | OPENING | READY`. `poll_mounts` only decides transitions; widgets update on phase change. |
| ~~`TASK-228`~~ | ~~Extract PathInput widget from the Home screen~~ | Done — Tab-cycle path field lives in `app/tui/widgets/path_input.py`. The scan bar stays in `home.py`. |
| ~~`TASK-229`~~ | ~~Unify TUI screen library attribute name~~ | Done — Home/Library/Progress all use `library`. Quit clears `getattr(screen, "library", _MISSING)`. |
| ~~`TASK-230`~~ | ~~Replace Linux/macOS mount scanner twins with `ChildDirectoryScanner`~~ | Done — same child-directory listing, different root/exclude. Windows and `EnvMountScanner` unchanged. |
| ~~`TASK-231`~~ | ~~Library labels as `Text`; `leaf_ids` on `PlaylistTreeSyncState`~~ | Done — playlist names no longer go through markup; leaf playlist ids are computed when the tree is built, not re-walked in the TUI. |
| ~~`TASK-232`~~ | ~~Quit feels instant: park library handles, Drop after the UI is gone~~ | Done — `q` used to await `gc.collect()` (and the PyOneLibrary Drop it forces) *before* Textual left the alt screen, so the last frame sat there for about a second. Now `action_quit` only re-points each screen's `library` onto the app (`_held_libraries`) and `exit()`s; `on_unmount` Drops those parked handles on the rekordbox thread after the terminal is already restored. Same thread-affinity rule as TASK-212; the wait is just no longer on screen. |
| ~~`TASK-233`~~ | ~~Skip the alt screen on ConPTY so quit is not a 1s buffer swap~~ | Done — the pause left after TASK-232 was Windows Terminal / WSL ConPTY leaving `CSI ? 1049`. That host waits to sync the cursor across buffers (~1s); we cannot make that call faster. On WSL (`microsoft`/`wsl` in `platform.release()`) or when `WT_SESSION` is set, the driver write path replaces 1049 h/l with a viewport clear so we never enter the alt screen. Linux/macOS desktops keep it (their restore is instant). |
| ~~`TASK-234`~~ | ~~Split `sync_playlists` and the other CC>11 functions in sync_service~~ | Done — McCabe 27 / 13 / 11 (`sync_playlists`, `_sync_analysis`, nested `_walk`) split into named steps. Public signatures unchanged. File 995 lines. |
| ~~`TASK-235`~~ | ~~Split `write_geob`, `build_track_record`, and `_find_playlist`~~ | Done — last three CC 11+ functions in `app/`. Public signatures unchanged. No function left at 11+. |
| ~~`TASK-236`~~ | ~~Bring remaining `app/` functions under CC 6~~ | Done — every remaining CC 6–10 function split into named steps. Analysis write / BPM correction live in `sync_analysis.py`. `sync_service.py` is 725 lines. Public signatures unchanged. No function left at 6+. |
| ~~`TASK-237`~~ | ~~Flatten the TASK-236 helper explosion~~ | Done — one-off CC helpers inlined back into their callers. Kept `_COMMANDS` / `_emit_json`, `sync_analysis.py`, shared backup helpers, and the TASK-234/235 named steps. |
| ~~`TASK-238`~~ | ~~Fold `sync_analysis.py` back into `sync_service.py`~~ | Done — TASK-235 (`ddcb66c`) was the best state along 233–237: named steps that earn their keep, no extra module. Folded analysis write / BPM correction back into `sync_service.py`. Kept `_COMMANDS` / `_emit_json` and shared backup helpers. File under 1000 lines. |
| ~~`TASK-239`~~ | ~~Commit the leftover test trim~~ | Done — overlapping Home searching / Enter-retry / count-label tests folded; unique coverage (mid-timeout, stop-polling, Home bootstrap, `e` on a leaf, custom env var) kept. |
| ~~`TASK-240`~~ | ~~Remove the CLI~~ | Done — `app/cli/` and CLI-only tests gone. `usbversal` / `python -m app.tui` launch the TUI. |
| ~~`TASK-241`~~ | ~~Confirm ID3v2.3 and v2.4 MP3 GEOB writes~~ | Done — `tests/test_mp3_tags.py` round-trips BeatGrid/Markers2 on hand-built MP3s; audio after the tag unchanged. Not yet confirmed live in Serato. |
| ~~`TASK-242`~~ | ~~FLAC Vorbis-comment Serato tags~~ | Done — `SERATO_BEATGRID` / `SERATO_MARKERS_V2` via base64-wrapped payloads. STREAMINFO and audio frames stay byte-identical. MP4 still out of scope. |
| ~~`TASK-243`~~ | ~~Progress covers index and crate writes~~ | Done — `SyncProgress` with `index` / `analysis` / `crates`. Progress screen labels each phase; backup is the opening status line. |
| ~~`TASK-250`~~ | ~~Run `correct_index_bpm` on a real stick~~ | Done — WONSIN 2026-08-28: 7 of 1286 rows written, backup `20260828T072224Z`. Still not in the TUI. Findings in `docs/workflows/index-bpm-wonsin.md`. |
| ~~`TASK-251`~~ | ~~Confirm a variable-tempo grid in Serato~~ | Done — 2026-08-29 deck load: four-marker 149→140 grid follows. Last marker was 140.9, not 140 (TASK-257). |
| ~~`TASK-253`~~ | ~~Hot cue colours are black in Serato~~ | Done — RGB at PCP2 offset 28. Findings in `docs/workflows/cue-colour-offset.md`. |
| ~~`TASK-254`~~ | ~~Keep `/` in crate names~~ | Done — `/` becomes U+FF0F fullwidth solidus. See `docs/workflows/crate-slash.md`. |
| ~~`TASK-255`~~ | ~~Parent crate named after the volume~~ | Done — `crate_name_for(..., volume=)` prefixes the mount folder name. No empty parent `.crate`. See `docs/workflows/volume-crate.md`. |
| ~~`TASK-256`~~ | ~~Omit Rekordbox "CUE Analysis Playlist"~~ | Done — `include_playlist()` drops it (any casing) from `list_playlists`, so the tree and sync never see it. |
| ~~`TASK-257`~~ | ~~Terminal beatgrid BPM is the settled last section~~ | Done — median of downbeats from the last anchor, not the first mid-ramp reading. Apt X Blue 140.87 → 140. |
| ~~`TASK-258`~~ | ~~Quit is Ctrl+Q only~~ | Done — app binding is `ctrl+q` with footer `^Q`. Bare `q` does nothing. |
| ~~`TASK-267`~~ | ~~Bare q shows a use-^Q-to-quit popup~~ | Done — `q` pushes `QuitHintScreen`; Enter / Esc / `q` dismisses; `^Q` still quits. |
| ~~`TASK-259`~~ | ~~Backup bar, then sync bar~~ | Done — backup bar is bytes + ETA. Sync bar is index+analysis+crates as one total. Not one bar across both. |
| ~~`TASK-260`~~ | ~~One run-wide bar and ETA~~ | Folded into TASK-259. |
| ~~`TASK-261`~~ | ~~Progress screen: playlist + titles~~ | Done — bar centered, playlist `Name  x/x`, log is the filename. |
| ~~`TASK-264`~~ | ~~Progress bar sits in the middle of the screen~~ | Done — `CenterMiddle` + nested `Center`, like Home. Log hidden until the first track. |
| ~~`TASK-265`~~ | ~~Keep the bar mid-screen when the log appears~~ | Done — log docks at the bottom so it does not pull the bar up. |
| ~~`TASK-266`~~ | ~~Center the progress bar horizontally~~ | Done — bar row is full width so the 60% bar sits in the middle, not a short strip on the left. |
| `TASK-262` | Done screen lists failures + `error.log` | Scrollable per-track errors (title + path + reason). Write the same lines to a host `error.log` when anything failed. |
| `TASK-263` | AIFF / AIF Serato tags | `write_geob` / `read_geob` for `.aif` / `.aiff` (ID3 GEOB, same family as WAV/MP3). Tests like TASK-241. MP4 still out of scope. |
| `TASK-252` | Library two-pane window | Last in this wave. Colour `x/y` (green only in the numerator), drop `-`, playlists left / tracks right. Per-track red/yellow/green. Spec in HANDOFF.md. Do after 258–263 so AIF tracks and analysis colour are honest. |

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
