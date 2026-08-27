# Documentation Index

Entry point for humans and autonomous agents.

## Start Here

| Role | Document |
|------|----------|
| Agent | [`../AGENT.md`](../AGENT.md) |
| Architecture | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| Current task | [`tasks/current-task.md`](tasks/current-task.md) |
| Machine state | [`state/`](state/) |

## Structure

| Directory | Contents |
|-----------|----------|
| [`architecture/`](architecture/) | System design, async, events |
| [`adapters/`](adapters/) | Rekordbox and Serato adapter specs |
| [`jobs/`](jobs/) | Job lifecycle, cancel, resume, progress |
| [`storage/`](storage/) | USB detection, backup, rollback |
| [`decisions/`](decisions/) | Architecture Decision Records |
| [`tasks/`](tasks/) | Backlog, current, completed |
| [`schemas/`](schemas/) | Vendor schema research notes |
| [`workflows/`](workflows/) | Agent, verification, release procedures |
| [`state/`](state/) | JSON machine-readable state |

## State Files

| File | Tracks |
|------|--------|
| [`state/task-state.json`](state/task-state.json) | Active and queued tasks |
| [`state/repository-state.json`](state/repository-state.json) | Modules, features, tests |
| [`state/architecture-state.json`](state/architecture-state.json) | Patterns and constraints |

## ADRs

| ADR | Decision |
|-----|----------|
| [0001](decisions/0001-use-python-cli.md) | Python CLI |
| [0002](decisions/0002-use-asyncio.md) | asyncio jobs |
| [0003](decisions/0003-use-pyinstaller.md) | PyInstaller packaging |
