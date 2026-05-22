# ADR 0003: Use PyInstaller for Packaging

**Status:** accepted  
**Date:** 2026-05-22

## Context

End users (DJs) may not have Python installed. Distribution targets Windows and Linux with a single executable per platform.

Alternatives: `pip install` only, Nuitka, cx_Freeze, Rust rewrite for binary size.

## Decision

Package the CLI using **PyInstaller** to produce platform-specific executables named `usbversal`.

## Consequences

### Positive

- Familiar path for Python CLI tools
- One-file or one-folder bundles supported
- Aligns with Python CLI decision (ADR 0001)

### Negative

- Larger binary size than native Rust
- Hidden import discovery can be fragile — requires CI smoke on built artifacts
- Build matrix needed (Windows + Linux)

### Neutral

- Development still uses editable install (`pip install -e .`); PyInstaller only for release builds
