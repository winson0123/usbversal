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

## CLI Smoke

```bash
.venv/bin/python -m app.cli --help
.venv/bin/python -m app.cli scan --help
```

## Integration (scoped tasks only)

```bash
# Requires /mnt/usb mounted — do not run in CI by default
.venv/bin/python -m app.cli scan --mount /mnt/usb --json
```

Full checklist and recorded results: [usb-integration-validation.md](usb-integration-validation.md).

## Recording Results

Copy command outputs into `docs/tasks/current-task.md` verification log table.

Update `repository-state.json`:

```json
"test_status": {
  "ruff": "pass",
  "pytest": "pass",
  "last_run": "<iso-timestamp>"
}
```

## Related

- [agent-task-workflow.md](agent-task-workflow.md)
- [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
