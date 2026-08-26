# ADR 0009: Use Textual for the interactive TUI

**Status:** accepted
**Date:** 2026-08-27
**Related:** [docs/planning/interactive-tui.md](../planning/interactive-tui.md),
[ADR 0001](0001-use-python-cli.md), [ADR 0003](0003-use-pyinstaller.md)

## Context

The argparse CLI under `app/cli/` is a test harness for the service layer, not
the shipped product — `docs/planning/interactive-tui.md` has said so since it
was written, and every service-layer task since (playlist sync state, the
playlist tree and its sync-state rollup, mount polling, progress rate/ETA) was
built specifically to feed a TUI that did not exist yet. All of that groundwork
(TASK-200 through TASK-205) is now done, so it does.

Four candidates fit the constraints (arrow/space/enter/esc key handling,
coloured text, a progress bar, and PyInstaller one-file packaging on Windows,
macOS, and Linux — ADR 0003):

| | Tree/list widget | Testing | Packaging weight | Maturity |
|---|---|---|---|---|
| `textual` | `Tree`, `ProgressBar` built in | `Pilot`/`run_test()` simulates keypresses in pytest | pulls in `rich`; needs one `--collect-data` flag for its `.tcss` resources | younger, but widely adopted (Harlequin, Posting) |
| `prompt_toolkit` | none — hand-built | no built-in app-testing harness | one dependency (`wcwidth`), extremely PyInstaller-proven | stable since ~2015 |
| `rich` + manual keys | none, and no input loop either | none | clean, but no input handling at all | `rich` itself is mature; the input layer would be new code |
| `curses` | none | none | stdlib on Linux/macOS; **not on Windows** — needs `windows-curses`, which has a history of PyInstaller one-file DLL-bundling issues | stdlib-old, but the Windows gap is the blocker |

## Decision

**Use `textual`.**

The screen this tool actually needs — screen 3 of the target flow, a playlist
folder tree with a red/yellow/green state per node — maps directly onto
`Tree`, which draws the guide lines, handles expand/collapse, and takes
keyboard navigation for free. `prompt_toolkit` would need that same rendering,
scrolling, and selection-cursor logic hand-written and hand-tested against
`app.core.playlist_tree.PlaylistNode` instead. `curses`'s Windows gap
(`windows-curses` plus its PyInstaller one-file history) is disqualifying on
its own, given ADR 0003 targets Windows, macOS, and Linux from one codebase.

`textual`'s `Pilot`/`run_test()` harness also matters for this specific
codebase: every task this project has done has been driven by real,
executable pytest coverage, not manual verification, and `textual` is the
only candidate that lets TUI screens be tested the same way — simulated
keypresses and assertions on rendered output — rather than requiring a human
at a terminal.

## Consequences

### Positive

- `Tree` and `ProgressBar` cover most of the target flow's screens 3 and 4
  directly, on top of the service-layer work already done for them
  (`playlist_tree_sync_states`, `ProgressRateTracker`).
- TUI screens get real automated test coverage via `Pilot`, matching how
  every other layer in this codebase is tested.
- `app/tui/` follows the same layer discipline as `app/cli/` — it depends on
  `services`/`jobs`/`core` only, never `storage`/`adapters` directly,
  enforced by the same `test_architecture.py` check.

### Negative

- Larger dependency than the alternatives: `textual` pulls in `rich`
  (`rich>=15.0.0` as installed) plus its own codebase. **Measured**: the
  Linux one-file binary grew from ~16 MB (TASK-060, CLI only) to **43 MB**
  with `textual` and its widget set bundled.
- `.tcss` stylesheet resources and `textual`'s dynamically-loaded submodules
  are not visible to PyInstaller's static import analysis and must be
  collected explicitly (`collect_data_files("textual")`,
  `collect_submodules("textual")` in `packaging/usbversal.spec`) or a themed
  screen silently falls back to defaults in the packaged binary even though
  it works from source. **Verified**: a real `pyinstaller` build with these
  additions produces a binary whose `tui` subcommand actually renders —
  confirmed by running it headless and capturing its ANSI output.
- Younger project than `prompt_toolkit`; less multi-year production history
  to lean on if something obscure breaks.

### Neutral

- The CLI stays exactly as it is — a test harness for the service layer,
  reachable via `python -m app.cli` / `usbversal <subcommand>`. The TUI is
  additive, reachable via `python -m app.tui` / `usbversal tui`, not yet the
  packaged binary's default action; making it the default is a separate,
  later decision once more of the target flow exists.
