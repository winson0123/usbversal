# ADR 0005: Use serato-tools for crates and database V2

**Status:** accepted
**Date:** 2026-05-25

## Context

Serato on USB uses `database V2` and `Subcrates/*.crate`. Hand-parsing
`otrk` chunks is a good way to corrupt a library. serato-tools already
reads and writes both.

## Decision

Use serato-tools (`DatabaseV2`, `Crate`) behind `app/adapters/serato/`
for crate listing, crate writes, and `database V2` appends.

`location.sqlite` and audio tags are our code, not serato-tools.

## Consequences

`database V2` and `.crate` parse correctly. Same idea as ADR 0004:
vendor library behind a thin adapter.

The extra dependency wants Python 3.12+.

`.smartcrate` stays out of scope until I see one on a USB export.
