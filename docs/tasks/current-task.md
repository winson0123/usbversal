# Current Task

**Status:** `complete`
**Task ID:** `TASK-324`
**Last updated:** 2026-09-01

---

## Objective

Delete leftover tests and fold combinable cases so the suite matches the TUI product.

## Files touched

- `tests/test_architecture.py`
- `tests/test_packaging_smoke.py`
- `tests/test_tui_app.py`
- `tests/test_tui_home.py`
- `tests/test_tui_library.py`
- `tests/test_tui_progress.py`
- `tests/test_progress_rate.py`
- `tests/test_aiff_tags.py`
- `tests/test_m4a_tags.py`
- `tests/test_markers.py`
- `tests/test_naming.py`
- `tests/test_mounts.py`
- `tests/test_sync_analysis.py`
- `docs/workflows/release-workflow.md`
- `docs/state/task-state.json`
- `docs/state/repository-state.json`

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
