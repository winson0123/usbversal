# Agent Execution Contract

This document is the **mandatory execution harness** for all autonomous coding agents working on Usbversal. Read it completely before any implementation work.

## Project Context

Usbversal is a **Python TUI** for safe, metadata-only Rekordbox → Serato library sync on USB-mounted media. Agents must respect scaffolding boundaries defined in `ARCHITECTURE.md` and machine-readable state under `docs/state/`.

---

## Single Task Rule

- **Only ONE task may be active at any time.**
- **No parallel implementation work** across modules, adapters, or screens.
- If a task is too large, **decompose it** into atomic subtasks in `docs/tasks/backlog.md` before starting the first subtask.
- Before starting work, confirm `docs/state/task-state.json` shows `active_task.status` is `idle` or matches your assigned task ID.

---

## Mandatory Execution Loop

Every task MUST follow this loop in order. Do not skip steps.

### 1. Read Current Task State

- `docs/state/task-state.json`
- `docs/tasks/current-task.md`
- `docs/state/repository-state.json`
- `docs/state/architecture-state.json`

### 2. Scope the Task

Document in `docs/tasks/current-task.md`:

| Field | Required |
|-------|----------|
| Task ID | Unique identifier (e.g. `TASK-001`) |
| Objective | One sentence outcome |
| Files touched | Explicit paths only |
| Verification criteria | Commands and expected results |

### 3. Implement Minimal Solution

- Smallest diff that satisfies the objective.
- Match existing conventions in touched modules.
- **TUI layer must remain thin** — delegate to domain, adapters, and services.
- Do not expand scope beyond the scoped files.

### 4. Verify

Run all applicable checks before marking complete:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

Record results in the verification log section of `current-task.md`.

### 5. Update Docs + JSON State

- Update affected documentation under `docs/`.
- Update `docs/state/task-state.json`.
- Update `docs/state/repository-state.json` (modules, features, test status).
- Update `docs/state/architecture-state.json` if patterns or constraints change.

### 6. Commit Exactly ONE Git Commit Per Task

- One atomic commit per completed task.
- Commit message references task ID and objective.
- Do not batch unrelated changes.
- Do not amend unless pre-commit hook auto-fixed files (see project git rules).

---

## Safety Rules (Non-Negotiable)

| Rule | Requirement |
|------|-------------|
| Rekordbox files | **Never** write under `PIONEER/` |
| Schema stability | **Never** assume vendor schema is stable across versions |
| Schema rebuild | **Never** rebuild or drop schemas wholesale |
| Unknown fields | Preserve and track unknown fields; do not discard silently |
| Recovery | Restore the Rekordbox USB; do not keep a host backup/rollback path |
| `location.sqlite` | **Never** create the file or insert rows; UPDATE existing rows only |

---

## Task Discipline

- Tasks must be **atomic**: completable in one session with one commit.
- Large features must be split in `docs/tasks/backlog.md` before execution.
- Blocked tasks go to `blocked_tasks` in `task-state.json` with `blocked_reason`.
- Completed tasks are recorded in `task-state.json` only.

---

## State Management

Agents **must** keep these files consistent after every task:

| File | Purpose |
|------|---------|
| `docs/state/task-state.json` | Active, pending, completed, blocked tasks |
| `docs/state/repository-state.json` | Modules, features, packaging, test status |
| `docs/state/architecture-state.json` | Allowed/forbidden patterns and constraints |

Human-readable mirrors:

| File | Purpose |
|------|---------|
| `docs/tasks/current-task.md` | Active task detail and verification log |
| `docs/tasks/backlog.md` | Queued work |

---

## Forbidden Unless Explicitly Scoped

- Writing under `PIONEER/` or regenerating a vendor index
- Creating or inserting into `location.sqlite`
- Adding dependencies not justified in an ADR or task scope

---

## Reference Documentation

| Topic | Location |
|-------|----------|
| System architecture | `ARCHITECTURE.md`, `docs/architecture/` |
| Adapters | `docs/adapters/` |
| Storage / USB | `docs/storage/` |
| ADRs | `docs/decisions/` |
| Workflows | `docs/workflows/` |
| Schemas | `docs/schemas/` |

---

## Completion Checklist (Per Task)

- [ ] Scoped in `current-task.md`
- [ ] Implementation minimal and within scope
- [ ] `ruff` and `pytest` pass (or documented N/A)
- [ ] JSON state files updated
- [ ] Task marked complete in `task-state.json`
- [ ] Exactly one git commit created
