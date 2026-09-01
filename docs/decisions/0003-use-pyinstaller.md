# ADR 0003: Use PyInstaller

**Status:** accepted
**Date:** 2026-05-22

## Context

DJs will not install Python. The release is one executable per OS:
Windows, Linux, macOS.

`pip install` is for development. Nuitka and cx_Freeze were options. A Rust
rewrite would shrink the binary and blow the schedule.

## Decision

Package the TUI with PyInstaller. The file is named `usbversal`. It
launches the TUI. There is no command list.

## Consequences

DJs get a one-file build. Linux with Textual is about 43 MB, which is
fat next to a native binary, but it works.

Hidden imports are flaky. Smoke-test the built file. You still need a
build on each OS.

Day to day, run `python -m app.tui` from the venv. PyInstaller is
for tags.
