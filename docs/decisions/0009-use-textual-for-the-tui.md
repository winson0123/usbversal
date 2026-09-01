# ADR 0009: Use Textual

**Status:** accepted
**Date:** 2026-08-27
**Related:** [ADR 0001](0001-use-python.md), [ADR 0003](0003-use-pyinstaller.md)

## Context

Usbversal is a TUI: Home → Library → Progress → Done. Library is a
playlist folder tree with a red / yellow / green state per node.
Progress needs a bar and an ETA. Packaging is PyInstaller one-file on
Windows, macOS, and Linux.

| | Tree | Tests | Weight | Age |
|---|---|---|---|---|
| `textual` | `Tree`, `ProgressBar` | `Pilot` / `run_test()` | pulls in `rich`, needs `.tcss` collected | younger, widely used |
| `prompt_toolkit` | none, usbversal would draw it | no app test helper | one dependency | stable since about 2015 |
| `rich` plus keys | no input loop | none | small, no input | `rich` is mature |
| `curses` | none | none | missing on Windows without `windows-curses` | the Windows gap kills it |

## Decision

Use Textual.

`Tree` draws guides, expands, and takes keys. `Pilot` presses keys
in pytest. Do not hand-roll a tree widget for this.

`app/tui/` imports `services` and `core` only. Never `storage` or
`adapters`. `test_architecture.py` enforces that.

## Consequences

Library and Progress map onto widgets Textual already ships. Screens get the
same pytest treatment as the rest of the code.

The Linux one-file binary is about 43 MB. `packaging/usbversal.spec`
must collect `.tcss` and Textual's dynamic modules or a screen falls
back to defaults.

The packaged binary launches the TUI. There is no command list.
