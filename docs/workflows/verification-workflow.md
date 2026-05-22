# Verification Workflow

Commands to run before marking any task complete.

## Standard Checks

```bash
# Lint
ruff check .

# Format
ruff format --check .

# Tests
pytest -v

# Type check (when mypy configured)
# mypy src/usbversal
```

## CLI Smoke (when CLI exists)

```bash
python -m usbversal --help
python -m usbversal scan --help
```

## Integration (scoped tasks only)

```bash
# Requires /mnt/usb mounted — do not run in CI by default
python -m usbversal scan --mount /mnt/usb --json
```

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
