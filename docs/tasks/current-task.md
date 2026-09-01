# Current Task

**Status:** `complete`
**Task ID:** `TASK-325`
**Last updated:** 2026-09-01

---

## Objective

Define the git workflow that cuts a v1 release and builds Windows, macOS, and Linux binaries.

## Files touched

- `.github/workflows/release.yml`
- `docs/workflows/release-workflow.md`
- `scripts/build-release.sh`
- `README.md`
- `docs/state/task-state.json`
- `docs/state/repository-state.json`
- `docs/tasks/backlog.md`

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
| pytest | 332 passed, 3 skipped |
