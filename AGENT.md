# Agent rules

Read this before you touch code. I mean the whole thing.

Usbversal is a Python TUI that copies Rekordbox metadata onto Serato on
a USB stick. Stay inside the layers in `ARCHITECTURE.md`. Keep
`docs/state/` honest after every task.

## One task at a time

Only one task may be active. Do not implement two features in parallel.
If the job is too big, split it in `docs/tasks/backlog.md` first.

Before you start, `docs/state/task-state.json` must show
`active_task.status` as `idle`, or already set to your task ID.

## Loop

Do these in order. Skip none of them.

### 1. Read state

- `docs/state/task-state.json`
- `docs/tasks/current-task.md`
- `docs/state/repository-state.json`
- `docs/state/architecture-state.json`

### 2. Scope

Fill in `docs/tasks/current-task.md`:

| Field | Required |
|-------|----------|
| Task ID | `TASK-001` style |
| Objective | One sentence |
| Files touched | Exact paths |
| Verification | Commands and what pass looks like |

### 3. Change as little as you can

Match the style of the files you touch. The TUI renders and calls
services. It does not parse vendor formats. Stay inside the files you
scoped.

### 4. Verify

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

Write the results into `current-task.md`.

### 5. Update docs and JSON

- Docs under `docs/` that your change made wrong
- `docs/state/task-state.json`
- `docs/state/repository-state.json`
- `docs/state/architecture-state.json` if layers or constraints changed

### 6. One commit

One commit per finished task. Mention the task ID in the message.
Do not lump unrelated work. Do not amend unless a pre-commit hook
rewrote files you then need to include.

## Safety

| Rule | What I expect |
|------|----------------|
| Rekordbox files | Never write under `PIONEER/` |
| Schema | Do not assume a vendor schema stays still |
| Schema rebuild | Do not DROP or CREATE a vendor schema wholesale |
| Unknown fields | Keep them. Do not drop them on rewrite. |
| Recovery | Restore the Rekordbox USB. No host backup path. |
| `location.sqlite` | UPDATE existing rows only. Never create the file. Never insert. |

## Tasks

A task should finish in one sitting with one commit. Split bigger work
in `docs/tasks/backlog.md`. Blocked work goes in `blocked_tasks` with a
reason. Finished IDs live in `task-state.json` only.

## State files

After every task, these three must match reality:

| File | What it holds |
|------|----------------|
| `docs/state/task-state.json` | Active, pending, completed, blocked |
| `docs/state/repository-state.json` | Modules, features, packaging, tests |
| `docs/state/architecture-state.json` | Allowed and forbidden patterns |

Readable copies: `docs/tasks/current-task.md`, `docs/tasks/backlog.md`.

## Leave these alone unless the task says otherwise

- Anything under `PIONEER/`
- Creating or inserting into `location.sqlite`
- New dependencies that no ADR or task asked for

## Where to read more

| Topic | Path |
|-------|------|
| Architecture | `ARCHITECTURE.md`, `docs/architecture/` |
| Adapters | `docs/adapters/` |
| USB | `docs/storage/` |
| ADRs | `docs/decisions/` |
| Workflows | `docs/workflows/` |
| Schemas | `docs/schemas/` |

## Done when

- [ ] Scoped in `current-task.md`
- [ ] Diff is small and inside that scope
- [ ] `ruff` and `pytest` pass, or you wrote why not
- [ ] JSON state is updated
- [ ] Task is marked complete in `task-state.json`
- [ ] One git commit exists
