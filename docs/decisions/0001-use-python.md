# ADR 0001: Use Python

**Status:** accepted
**Date:** 2026-05-22

## Context

Usbversal edits DJ library metadata on USB drives on Windows, Linux,
and macOS. The job needs fast adapter work, stdlib SQLite for Rekordbox,
and a one-file build DJs can run without installing Python.

Rust would be a smaller binary. Go would deploy easily. Node's SQLite
story is worse for this. None of those beat the iteration speed here.

## Decision

Usbversal is a Python 3.11+ TUI in `app/`, tested with `pytest`,
linted with `ruff`.

## Consequences

Python lets an agent poke a schema and have a test in the same hour.
`sqlite3` is in the stdlib. Agents already know this layout.

The cost is PyInstaller (ADR 0003) and the GIL. Rekordbox work sits on
one dedicated thread. Analysis writes use a small pool. Dependencies
stay listed in `pyproject.toml`.

Metadata work does not need native speed. Usbversal does not process audio.
