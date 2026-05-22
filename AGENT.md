# Agent Execution Contract

This document is the **mandatory execution harness** for all autonomous coding agents working on Usbversal. Read it completely before any implementation work.

## Project Context

Usbversal is a **Python CLI** for safe, metadata-only manipulation of DJ library databases (Rekordbox, Serato) on USB-mounted media. Agents must respect scaffolding boundaries defined in `ARCHITECTURE.md` and machine-readable state under `docs/state/`.

---

## Single Task Rule

- **Only ONE task may be active at any time.**
- **No parallel implementation work** across modules, adapters, or CLI commands.
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
- **CLI layer must remain thin** — delegate to domain, adapters, and jobs.
- Do not expand scope beyond the scoped files.

### 4. Verify

Run all applicable checks before marking complete:

```bash
ruff check .
ruff format --check .
pytest
# CLI smoke (when CLI exists):
# python -m usbversal --help
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
| Database writes | **Never** write to DJ databases without a verified backup |
| Schema stability | **Never** assume vendor schema is stable across versions |
| Schema rebuild | **Never** rebuild or drop schemas wholesale |
| Unknown fields | Preserve and track unknown fields; do not discard silently |
| Rollback | Every write path must support rollback via backup metadata |

---

## Task Discipline

- Tasks must be **atomic**: completable in one session with one commit.
- Large features must be split in `docs/tasks/backlog.md` before execution.
- Blocked tasks go to `blocked_tasks` in `task-state.json` with `blocked_reason`.
- Completed tasks move to `docs/tasks/completed-tasks.md` and task history in JSON.

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
| `docs/tasks/completed-tasks.md` | Historical record |

---

## Forbidden During Scaffolding / Unless Explicitly Scoped

- Implementing Rekordbox/Serato parsing beyond documented placeholders
- Implementing job runner business logic without a scoped task
- Writing to real DJ databases on `/mnt/usb` without backup task approval
- Adding dependencies not justified in an ADR or task scope

---

## Reference Documentation

| Topic | Location |
|-------|----------|
| System architecture | `ARCHITECTURE.md`, `docs/architecture/` |
| Adapters | `docs/adapters/` |
| Jobs | `docs/jobs/` |
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
- [ ] Task moved to completed in JSON + markdown
- [ ] Exactly one git commit created
