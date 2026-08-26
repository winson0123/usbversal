# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-26

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-204` |
| Objective | A rate and ETA for job progress, and wire it into the one progress renderer that exists so it's reachable now, not just a tested utility waiting for the TUI |
| Completed | 2026-08-26 |

### Scope

Files touched:

- `app/jobs/progress_rate.py` (new) — `ProgressEstimate`, `ProgressRateTracker`:
  `observe()` takes a `current`/`total`/timestamp sample and returns the
  whole-run rate and ETA so far
- `app/cli/progress.py` — `CliProgressRenderer` now keeps one
  `ProgressRateTracker` per `job_id` and appends `(N.N/s, eta Xs)` to a
  progress line once that job has two samples
- `tests/test_progress_rate.py` (new) — single-sample yields no estimate,
  rate is units-over-elapsed, ETA is remaining-over-rate, the rate averages
  over the whole run rather than just the latest step, no total yields a rate
  but no ETA, no progress yet (only elapsed time) yields no estimate rather
  than a false zero, reaching the total gives a zero ETA rather than a
  division by zero, and a second tracker starts with no memory of the first
- `tests/test_cli_progress.py` — three new tests: rate/ETA appear on a
  second sample, are absent on the first, and two interleaved job ids don't
  pollute each other's estimate
- `docs/planning/interactive-tui.md`, `docs/tasks/backlog.md`, `docs/state/*.json`

### Design decisions

- **Averages over the whole run, not the most recent interval.** A sync
  job's per-track cost varies (a large MP3's tag rewrite next to a small
  WAV's), so a most-recent-interval rate would swing on every step; anchoring
  on the first sample and dividing by total elapsed time is steadier. Has a
  test proving a slow first step doesn't get erased by comparing against
  what a most-recent-interval computation would have shown.
- **"No progress yet" is `None`, not a zero rate.** Time passing with
  `current` unchanged is a stalled or not-yet-started job, not a
  mathematically valid zero-rate estimate — reporting `None` lets a renderer
  distinguish "still figuring out the rate" from "the rate is genuinely
  zero," which the type never actually returns.
- **Lives in `app/jobs/`, not `core`.** It's a rate/ETA concept tied to
  `JobProgress`, consumed by the CLI/TUI layers per the layer rule
  (`cli: [jobs, services, core]`), not a core domain type.
- **Wired into `CliProgressRenderer` immediately**, per this session's
  running lesson (TASK-130's handoff: adapters existed and were tested but
  nothing called them) — a tracker sitting untested-in-production would
  repeat that mistake at a smaller scale. A future TUI progress bar would use
  `ProgressRateTracker` directly rather than parsing the CLI's text lines.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 200 passed, 3 skipped (no stick mounted; skips are the two `/mnt/usb` integration tests and the PyInstaller build) |
| `.venv/bin/python -m app.cli --help` | all commands listed (unchanged) |

## Next

Every M11 groundwork item (TASK-200 through TASK-205) is now done. The one
item left in that block is `TASK-206` (TUI framework ADR + shell) — a choice
among `textual`, `prompt_toolkit`, `rich` + manual key handling, or `curses`,
constrained by PyInstaller one-file packaging (ADR 0003). That's a framework
decision flagged as needing the user's sign-off, not something to pick
unilaterally.
