# Current task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-09-07

## Recently completed

- TASK-342: Fix residual quit/preview bugs from review

## Verification

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
```

Pass: 348 passed, 3 skipped.

Next id is `TASK-343`.
