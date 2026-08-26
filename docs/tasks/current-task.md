# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-206` |
| Objective | Decide and record the TUI framework, then scaffold a real, working app shell — not just an ADR, a shell that actually launches and does step 1-2 of the target flow |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `docs/decisions/0009-use-textual-for-the-tui.md` (new) — the framework
  decision, with a real comparison table and measured (not guessed) packaging
  cost
- `pyproject.toml` — `textual>=8.0.0` added as a runtime dependency
- `app/tui/` (new package) — `app.py` (`UsbversalApp`), `__main__.py`
  (`python -m app.tui`), `screens/home.py` (`HomeScreen`: steps 1-2, Waiting
  and Detect, polling via `MountWatcher` and probing via `probe_mount`,
  opening the library off the event loop thread via `asyncio.to_thread`
  inside a Textual worker)
- `app/services/library.py` — re-exports `MountWatcher`/`MountChange`/
  `MountChangeKind` from `app.storage.mount_watch`, so `app/tui/` (like
  `app/cli/`) never imports `storage` directly
- `app/cli/main.py` — new `tui` subcommand, a one-line delegation to
  `app.tui.app.run()`
- `tests/test_architecture.py`, `docs/state/architecture-state.json` — `tui`
  registered as a layer permitted `{jobs, services, core}`, same as `cli`;
  `cli`'s dependency on `tui` is the one explicit exception (a single
  delegation, not general access)
- `packaging/usbversal.spec` — `collect_submodules("textual")` and
  `collect_data_files("textual")` (its `.tcss` stylesheets are package
  resources PyInstaller's static analysis does not see on its own)
- `tests/test_tui_home.py` (new) — five tests via Textual's `Pilot`/
  `run_test()`: searching state with nothing mounted, "did not detect" for an
  invalid mount, a valid mount opens the library and reports readiness, an
  open failure (a race between probe and open) is reported rather than
  crashing the app, and a second poll after opening does not re-probe
- `tests/test_packaging_smoke.py` — fixed a stale assertion (`"apply" in
  result.stdout`) discovered while validating the real build; `apply` was
  removed from the CLI back in TASK-109 and this test had been silently
  skip-passing ever since because `dist/usbversal` is gitignored and not
  normally present
- `ARCHITECTURE.md`, `README.md`, `docs/planning/interactive-tui.md`,
  `docs/tasks/backlog.md`, `docs/state/repository-state.json`

### Design decisions

- **Decomposed the original one-line backlog item.** "TUI framework ADR +
  shell" was too large for one commit per AGENT.md's decomposition rule.
  Split into TASK-206 (this: decision + working shell + Home screen),
  TASK-207 (Library screen), TASK-208 (Progress/Done screens) — added to
  `backlog.md` in the same pass so the remaining scope isn't lost.
- **Verified the packaging risk for real, not assumed it.** Ran an actual
  `pyinstaller` build with the spec changes, then executed the resulting
  binary's `tui` subcommand headless and confirmed it emits real ANSI screen
  output ("Searching for valid DJ USBs…"). Binary grew from ~16 MB to 43 MB —
  measured, not estimated — recorded in the ADR and `repository-state.json`.
  Build artifacts were cleaned up afterward (gitignored, not committed).
- **`tui` gets the same layer discipline as `cli`.** Home screen imports
  `MountWatcher` through `app.services.library`, not
  `app.storage.mount_watch` directly — `services` re-exports it, mirroring
  how `services.errors` already re-exports adapter/storage error types for
  frontend consumption. `cli`'s one new edge to `tui` is registered as a
  named exception in `test_architecture.py`'s comments, not a general
  broadening of what CLI may import.
- **`open_library` runs off the event loop thread.** It opens the Rekordbox
  database, which HANDOFF.md and TASK-110 both note "dominates load time" —
  calling it directly from a Textual timer callback would freeze the UI.
  `self.run_worker(self._open(...), exclusive=True)` wraps an
  `asyncio.to_thread(open_library, mount)` call instead.
- **The CLI's default entry point is unchanged.** `usbversal` with no
  subcommand still shows CLI help; `tui` is additive. Making the TUI the
  packaged binary's default action is a separate, later decision once more
  of the target flow exists (noted as "Neutral" in ADR 0009).
- **A pre-existing bug, fixed on discovery, not left for later.**
  `test_packaging_smoke.py` asserted on a CLI subcommand (`apply`) removed
  three tasks ago; it was invisible because the binary it needs isn't built
  by default. Building the binary for real to validate textual surfaced it.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 204 passed, 4 skipped (no stick mounted, no `dist/usbversal` built after cleanup; a real build was run and verified during this task) |
| `.venv/bin/python -m app.cli --help` | lists `tui` alongside the existing subcommands |
| Real PyInstaller build | `43M dist/usbversal`; `--help` lists `tui`; `dist/usbversal tui < /dev/null` (headless) rendered the Home screen's real ANSI output |

## Next

`TASK-207` (TUI Library screen) — screen 3 of the target flow: the playlist
folder tree from `app.core.playlist_tree` with per-node red/yellow/green
state from `sync_service.playlist_tree_sync_states`, using `textual.widgets.Tree`.
