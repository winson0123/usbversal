# Agent Task Workflow

Standard workflow for autonomous agents — mirrors [`AGENT.md`](../../AGENT.md).

## Flow

```mermaid
flowchart TD
    A[Read task-state.json] --> B{Active task idle?}
    B -->|no| Z[Stop - conflict]
    B -->|yes| C[Pick task from backlog]
    C --> D[Update current-task.md + JSON active]
    D --> E[Scope: objective, files, verification]
    E --> F[Implement minimal diff]
    F --> G[ruff + pytest + smoke]
    G --> H{Pass?}
    H -->|no| F
    H -->|yes| I[Update docs + JSON state]
    I --> J[One git commit]
    J --> K[Mark task completed]
```

## Checklist

- [ ] `task-state.json` active_task set
- [ ] Scope table filled in `current-task.md`
- [ ] Only scoped files modified
- [ ] Verification log complete
- [ ] `repository-state.json` updated
- [ ] Task moved to completed history
- [ ] Single commit pushed (if remote workflow applies)

## Related

- [verification-workflow.md](verification-workflow.md)
- [../tasks/backlog.md](../tasks/backlog.md)
