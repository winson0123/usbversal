# Current Task

**Status:** `complete`
**Task ID:** `TASK-323`
**Last updated:** 2026-09-01

---

## Objective

Strip the tree to the TUI product as it ships: no unused jobs/events/CLI
services, no journal docs, no dry-run or JSON leftover paths.

## Files touched

- Dead modules under `app/jobs/`, `app/core/event_*.py`, unused services
- Callers and tests of those modules
- Production docs (`README.md`, `ARCHITECTURE.md`, `AGENT.md`, `docs/`)
- State JSON slimmed to the current product

## Verification

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

| Check | Result |
|-------|--------|
| ruff check | pass |
| ruff format | pass |
| pytest | 352 passed, 3 skipped |
