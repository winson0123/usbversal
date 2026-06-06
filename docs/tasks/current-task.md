# Current Task

**Status:** `idle`  
**Task ID:** none  
**Last updated:** 2026-06-06

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-060` |
| Objective | PyInstaller spec, build script, release smoke tests |
| Completed | 2026-06-06 |

### Verification log

| Check | Result |
|-------|--------|
| `./scripts/build-release.sh` | `dist/usbversal` ~16 MB |
| `./dist/usbversal --help` | all commands listed |
| `test_packaging_smoke.py` | 2 passed, 1 skipped |
| `pytest` | 57 passed, 1 skipped |

Deliverables: `packaging/usbversal.spec`, `scripts/build-release.sh`, [release-workflow.md](../workflows/release-workflow.md)
