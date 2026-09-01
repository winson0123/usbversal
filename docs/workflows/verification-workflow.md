# Verification Workflow

Commands to run before marking any task complete.

## Standard Checks

Run from repo root using **`.venv`** (create via `./scripts/setup-dev.sh`):

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -v
```

Or after `source .venv/bin/activate`, use `ruff`, `pytest`, and `python` directly.

## TUI smoke

```bash
.venv/bin/python -m app.tui
```

## Integration (scoped tasks only)

Requires a live DJ USB on an auto-detected mount (or `USBVERSAL_MOUNT` as
an escape hatch). Do not run in CI by default.

## Recording Results

Copy command outputs into `docs/tasks/current-task.md` verification log.

Update `repository-state.json` `test_status`.

## Related

- [../../AGENT.md](../../AGENT.md)
- [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
