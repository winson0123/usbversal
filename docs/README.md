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
| [`architecture/`](architecture/) | System design |
| [`adapters/`](adapters/) | Rekordbox and Serato adapter specs |
| [`storage/`](storage/) | USB detection and host paths |
| [`decisions/`](decisions/) | Architecture Decision Records |
| [`tasks/`](tasks/) | Current task and backlog |
| [`schemas/`](schemas/) | Vendor schema notes for writers |
| [`workflows/`](workflows/) | Release, verification, write-path procedures |
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
| [0001](decisions/0001-use-python.md) | Python |
| [0002](decisions/0002-use-asyncio.md) | asyncio + Rekordbox thread |
| [0003](decisions/0003-use-pyinstaller.md) | PyInstaller packaging |
| [0004](decisions/0004-use-rbox-rekordbox-reader.md) | rbox for One Library |
| [0005](decisions/0005-use-serato-tools.md) | serato-tools for crates |
| [0008](decisions/0008-beatgrid-and-cue-sync-validated-in-serato.md) | Beatgrid and cue writes |
| [0009](decisions/0009-use-textual-for-the-tui.md) | Textual TUI |
| [0010](decisions/0010-tolerate-leftover-markers2-base64.md) | Leftover Markers2 base64 |
