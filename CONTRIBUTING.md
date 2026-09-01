# Contributing

One task at a time, whether you are a person or an agent. That rule
exists because two open tasks in this repo step on the same USB
formats.

## Before you start

1. Read [`AGENT.md`](AGENT.md).
2. Read [`ARCHITECTURE.md`](ARCHITECTURE.md).
3. Check [`docs/tasks/current-task.md`](docs/tasks/current-task.md) and
   [`docs/state/task-state.json`](docs/state/task-state.json). Only one
   task may be active.

## Code

| Area | Rule |
|------|------|
| Language | Python 3.11+ |
| Style | PEP 8, `ruff` |
| Format | `ruff format` |
| Types | On public APIs |
| Docstrings | On every function: what it does, inputs, outputs |
| Names | `snake_case` modules and functions, `PascalCase` classes |
| Imports | stdlib, then third-party, then local. Absolute inside `app/`. |

## Tasks

Pick one item from `docs/tasks/backlog.md` or assign it in
`task-state.json`. Write the scope in `current-task.md` with exact
file paths before you edit. Split anything that will take more than a
day. Do not start a second task until the first is committed.

```
Read state → Scope → Smallest change → Verify → Update docs/state → One commit
```

## Tests

| Kind | Where |
|------|-------|
| Unit | `pytest` on domain, storage, adapter helpers |
| Integration | Files under `tests/fixtures/` |
| Live USB | Only when the task says so |

All tests must pass before you mark the task complete. Paste the
commands into `current-task.md`.

## Commits

Exactly one commit per finished task. Message: `[TASK-XXX] Short
imperative summary`. Do not mix a refactor with a feature. Do not
commit secrets or a real DJ database.

## TUI

`app/tui/` draws screens and handles keys. It calls services. It does
not contain sync logic and it does not import vendor parsers.

That work sits in `app/core/`, `app/adapters/`, `app/services/`, and
`app/storage/`.

## USB and vendor files

Never write under `PIONEER/`. Restore the Rekordbox USB if you need
the old state. Do not assume Rekordbox or Serato schemas stay still.
Do not create or insert into `location.sqlite`. Keep unknown fields.
Add fixture tests before you open a new write path.

## Docs

If behavior or architecture changed, update `docs/`, add or edit an
ADR for a real choice, and refresh `docs/state/*.json`.

## Pull requests

One task per PR. Put the task ID in the description. CI is `ruff` and
`pytest`. Reviewers check that writes never touch `PIONEER/`.
