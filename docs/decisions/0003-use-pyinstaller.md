# ADR 0003: Use PyInstaller for Packaging

**Status:** accepted
**Date:** 2026-05-22

## Context

End users (DJs) may not have Python installed. Distribution targets
Windows, Linux, and macOS with a single executable per platform.

Alternatives: `pip install` only, Nuitka, cx_Freeze, Rust rewrite for
binary size.

## Decision

Package the TUI using **PyInstaller** to produce platform-specific
executables named `usbversal`. The binary launches the TUI; there is
no argparse command list.

## Consequences

### Positive

- One-file bundles for DJs who do not have Python
- Aligns with the Python TUI decision (ADR 0001)

### Negative

- Larger binary size than native Rust (~43 MB on Linux with Textual)
- Hidden import discovery can be fragile — requires a smoke test on
  the built artifact
- Build matrix needed (Windows, Linux, macOS)

### Neutral

- Development still uses the project venv (`python -m app.tui`);
  PyInstaller is for release builds
