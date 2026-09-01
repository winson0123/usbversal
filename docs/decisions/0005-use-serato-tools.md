# ADR 0005: Use serato-tools for Serato crate and database V2 I/O

**Status:** accepted
**Date:** 2026-05-25

## Context

Serato on USB uses `database V2` (binary library index) and
`Subcrates/*.crate` (playlist files). Hand-parsing `otrk` chunks is
high-risk. PyPI package **serato-tools** supports read/write for both.

## Decision

Use **serato-tools** (`DatabaseV2`, `Crate`) behind `app/adapters/serato/`
for crate listing, crate writes, and `database V2` appends.

`location.sqlite` and audio tags are handled by our own adapters, not
serato-tools.

## Consequences

### Positive

- Correct parsing of `database V2` and `.crate`
- Aligns with ADR 0004 (vendor library behind a thin adapter)

### Negative

- Additional dependency; requires Python 3.12+ per upstream

### Neutral

- Smart crates (`.smartcrate`) are out of scope until observed on a USB export
