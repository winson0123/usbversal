# Verification

Run these before you mark a task complete.

From the repo root, using `.venv` from `./scripts/setup-dev.sh`:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -v
```

After `source .venv/bin/activate`, `ruff`, `pytest`, and `python` work
without the prefix.

## TUI smoke

```bash
.venv/bin/python -m app.tui
```

## Live USB

Only when the task asks for a real stick. Auto-detect, or set
`USBVERSAL_MOUNT`. Do not run this in CI.

Paste command output into `docs/tasks/current-task.md`. Update
`repository-state.json` `test_status`.

See [../../AGENT.md](../../AGENT.md) and
[../../CONTRIBUTING.md](../../CONTRIBUTING.md).
