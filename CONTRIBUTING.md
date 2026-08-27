# Contributing to Usbversal

Thank you for contributing. This project uses a **single-task execution model** designed for both human developers and autonomous agents.

## Before You Start

1. Read [`AGENT.md`](AGENT.md) — mandatory for all contributors.
2. Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for module boundaries.
3. Check [`docs/tasks/current-task.md`](docs/tasks/current-task.md) and [`docs/state/task-state.json`](docs/state/task-state.json) — only one task may be active.

## Coding Standards

| Area | Standard |
|------|----------|
| Language | Python 3.11+ |
| Style | PEP 8; enforced via `ruff` |
| Formatting | `ruff format` |
| Type hints | Required on public APIs |
| Docstrings | Required on all functions (description, inputs, outputs) |
| Naming | `snake_case` modules/functions; `PascalCase` classes |
| Imports | stdlib → third-party → local; absolute imports in package |

## Task Discipline

- Pick **one** task from `docs/tasks/backlog.md` or assign via `task-state.json`.
- Mark it active in `current-task.md` and JSON state before coding.
- Scope must list **exact files** to touch.
- Decompose tasks larger than ~1 day into atomic subtasks.
- Do not start a second task until the first is committed and state is updated.

## Single-Task Execution Model

```
Read state → Scope task → Minimal implement → Verify → Update docs/state → One commit
```

Parallel feature work across adapters, TUI, and jobs is **not allowed**.

## Testing Requirements

| Level | Requirement |
|-------|-------------|
| Unit | `pytest` for domain, storage, adapter helpers |
| Integration | Fixture-based DB files under `tests/fixtures/` |
| USB validation | Auto-detected mounts only when a task explicitly requires a live stick |

All tests must pass before marking a task complete. Record commands in `current-task.md` verification log.

## Commit Discipline

- **Exactly one commit per completed task.**
- Message format: `[TASK-XXX] Short imperative summary`
- Include task ID in body when helpful.
- Do not mix refactors with feature work in the same commit.
- Do not commit secrets or real DJ databases.

## TUI Thin-Layer Requirement

The TUI (`app/tui/`) must:

- Render screens and handle keys
- Dispatch to services — **no business logic in TUI modules**
- Stay off vendor parsers and backup internals

Parsing, schema mapping, backup logic, and job orchestration belong in `app/core/`, `app/adapters/`, `app/services/`, and `app/storage/`.

## Safety Requirements for Database Work

- Always create backup before write (see `docs/storage/backup-strategy.md`).
- Never assume Rekordbox/Serato schema stability.
- Track unknown fields (see adapter docs).
- Add integration tests with fixture DBs before enabling write commands.

## Documentation Updates

When changing behavior or architecture:

- Update relevant `docs/` pages
- Add or update ADRs in `docs/decisions/` for significant choices
- Update `docs/state/*.json` files

## Pull Requests

- One task per PR preferred
- Link task ID in PR description
- CI must pass: `ruff`, `pytest`
- Reviewers verify backup/rollback paths for any write-related change
