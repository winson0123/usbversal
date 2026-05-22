# Serato Adapter

**Status:** placeholder — not implemented.

## Overview

Serato uses **proprietary on-disk formats** under `_Serato_` directories. This adapter is the only module allowed to interpret Serato binary/text database files.

## Schema Assumptions (Tentative)

| Assumption | Confidence | Notes |
|------------|------------|-------|
| Library root contains `_Serato_` | high | |
| `database V2` or successor files hold crate/track index | medium | Name may vary |
| Crate = playlist equivalent | medium | Mapping to domain TBD |
| Format changes without public schema docs | high risk | |

**All field layouts are unverified** until probed against fixtures and `/mnt/usb` samples.

## Unknown Fields Tracking

- Parse defensively; store unmapped binary sections or key-value pairs as opaque blobs.
- Never discard unrecognized records when rewriting.
- Document discoveries in `docs/schemas/serato-schema-notes.md`.

## Safety Constraints

| Constraint | Enforcement |
|------------|-------------|
| Backup before write | Full file copy of all touched Serato DB files |
| No in-place patch without backup | Storage layer gate |
| Read-only if parse confidence low | Adapter returns error, does not guess |
| No schema rebuild | Never regenerate entire database from scratch |

## Read Operations (Planned)

- Detect Serato library on mount
- List crates and track entries (metadata only)

## Write Operations (Planned)

- Apply limited plans once format is understood
- Prefer append-only or field-level edits over full rewrite

## Related

- [../schemas/serato-schema-notes.md](../schemas/serato-schema-notes.md)
- [../decisions/0001-use-python-cli.md](../decisions/0001-use-python-cli.md)
