# 2026-11-18: Session log

A record of today's working session with Claude Code, in order. The
technical detail of the code changes is in [`2026-11-18.md`](2026-11-18.md).
The capstone check-in written today is [`docs/check-in.md`](../docs/check-in.md).

## 1. Project review

- Read the repository, `TASKS.md`, the peer reviews (luyunqi 2026-10-13,
  allenduh 2026-10-14), `notes/`, the half-week summaries, and the unmerged
  `review/2026-11-16-referee` branch.
- Finding: both `TASKS.md` tasks were complete, but about one of the
  eight peer-review suggestions had been addressed, and none of them, nor the
  referee's findings, were tracked in `TASKS.md`. `docs/check-in.md` was an
  empty template.

## 2. Plan and decisions

- Agreed to address the referee review in one PR. As a one-time exception,
  the agent opens the PR; the owner reviews and merges it.
- Owner's decisions:
  - Quality threshold: R² < 0.98, flag only.
  - One PR rather than two.
  - Branch from the referee branch so the review ships with the fixes.
- Out of scope, owner only: rotating the API key in history (`3fee3a2`) and
  setting a git identity.

## 3. Work on `fix/referee-2026-11-16`

| Commit | What |
|---|---|
| `574a964` | Stop tracking `.DS_Store` |
| `da1c2d0` | Backend: uncertainties, separate linewidth fit, R² flag, modulation check, in-plane negative-field message, at-bound warnings, CODATA 2018 constant, cleanups; new and stricter tests |
| `42a02ee` | Frontend: value ± σ, warnings list, flagged sweeps |
| `838b611` | Makefile: smoke check fails on a failed fit; `clean` is complete |
| `540e489` | Docs: README, ARCHITECTURE, `docs/fmr-model.md`, PROMPT thresholds |
| `3801ab8` | `TASKS.md` and `notes/2026-11-18.md` |
| `88a8f7e` | Line-length fixes in tests |

- The branch was pushed. The PR could not be opened from here because the
  GitHub CLI is not installed, and installing it is not allowed. The owner
  opens it at
  <https://github.com/Lerato21-FT/EE292-part-1/pull/new/fix/referee-2026-11-16>.

## 4. Check-in

- Wrote `docs/check-in.md` from the course template. "What works" lists only
  results that were actually run (at `dcae08c`). Today's unverified work is
  marked as such.
- The owner said they had left suggestions in the file. When it was read,
  it held only the template, so nothing of theirs was found to merge.

## 5. Deviations from AGENTS.md and the plan

- **No tests were run.** Docker Desktop failed to start ("Docker Desktop is
  unable to start") and the owner chose to skip testing. Nothing ran:
  pytest, lint, smoke, browser, `make verify` or `make fresh-verify`. The
  fail-first demonstration did not happen. "Done means" is therefore not
  met.
- Early in the session, one file edit used the host's `python3` instead of
  the editor tools. One temporary CSS snippet was written to the agent's
  scratch directory, outside the repository. Neither installed anything or
  changed project behaviour.
- The golden tolerances in the broadband regression test were not tightened.
  That needs one test run.

## 6. Next steps

1. Start Docker and run `make verify` on `fix/referee-2026-11-16`. Fix what
   fails, then run `make fresh-verify`.
2. Open the PR, review it and merge it.
3. Rotate the course API key.
4. Re-record the broadband golden values with justified tolerances.
5. CSV export of plotted data and fits (open in `TASKS.md`).
6. Update `docs/check-in.md` once the PR is verified, before the review
   session. The draft is due Monday 30 November.
