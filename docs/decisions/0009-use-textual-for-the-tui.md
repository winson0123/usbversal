# ADR 0009: Use Textual for the interactive TUI

**Status:** accepted
**Date:** 2026-08-27
**Related:** [ADR 0001](0001-use-python.md), [ADR 0003](0003-use-pyinstaller.md)

## Context

Usbversal ships as an interactive terminal UI: Home → Library →
Progress → Done. The Library screen is a playlist folder tree with a
red/yellow/green state per node. The Progress screen needs a bar and
an ETA. Packaging is PyInstaller one-file on Windows, macOS, and Linux.

| | Tree/list widget | Testing | Packaging weight | Maturity |
|---|---|---|---|---|
| `textual` | `Tree`, `ProgressBar` built in | `Pilot` / `run_test()` in pytest | pulls in `rich`; needs `--collect-data` for `.tcss` | widely adopted |
| `prompt_toolkit` | none — hand-built | no built-in app-testing harness | one dependency | stable since ~2015 |
| `rich` + manual keys | none, and no input loop | none | clean, but no input handling | `rich` is mature |
| `curses` | none | none | **not on Windows** without `windows-curses` | Windows gap is the blocker |

## Decision

**Use `textual`.**

`Tree` draws guide lines, handles expand/collapse, and takes keyboard
navigation. `Pilot` lets screens be tested with simulated keypresses.

`app/tui/` depends on `services` and `core` only, never `storage` or
`adapters` directly, enforced by `test_architecture.py`.

## Consequences

### Positive

- `Tree` and `ProgressBar` cover Library and Progress
- TUI screens get the same pytest coverage as the rest of the codebase

### Negative

- Larger dependency: Linux one-file binary is about 43 MB
- `.tcss` resources and dynamic submodules must be collected explicitly
  in `packaging/usbversal.spec`

### Neutral

- The packaged binary launches the TUI. There is no argparse command list.
