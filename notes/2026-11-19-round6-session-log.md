# 2026-11-19: Peer review round 6, session log

A record of the session with Claude Code that addressed the two reviews on
the `ee292m_round6` form, the safety-nets review ("where does the capstone
stand, what does the agent know, and what catches a wrong result?"). Both
scored 5 of 5:

- Abhiraj Gupta (abgup05), commit `6bf9395`: `feedback/20261119_abgup05_l6134546.md`
- Helena Guan (wgguan), commit `4c4b30b`: `feedback/20261119_wgguan_l6134546_8a.md`

Branch: `fix/round1-feedback`, the same branch as rounds 1–5. Committed
locally; not pushed yet. The companion document requested for this round
is [`docs/agent-setup-and-review-response.md`](../docs/agent-setup-and-review-response.md):
the agent-setup table, and the criticism accepted and rejected.

## 1. Suggestions and outcome

| # | Reviewer | Suggestion | Outcome |
|---|---|---|---|
| 1 | wgguan | CI running `make verify` on every PR, plus branch protection on `main` | **Accepted.** `.github/workflows/verify.yml` added. Branch protection is an owner-only task in `TASKS.md` |
| 2 | wgguan | AGENTS.md: never merge until `make verify` passed; if Docker won't start, stop and say so | **Accepted**, added under Git |
| 3 | wgguan | A skill that turns a feedback file into `TASKS.md` items | **Accepted**: `.claude/skills/review-to-tasks/` |
| 4 | abgup05 | A skill for "make verify and record the results" | **Accepted**: `.claude/skills/verify-and-record/` |
| 5 | wgguan | The check-in should name the commit behind "What works" and add the damping caveat | **Accepted**: dated update section in `docs/check-in.md` |
| 6 | abgup05 | Remove low-R² sweeps from both fits automatically | **Rejected** (owner). The reasons are in the companion document |
| — | wgguan | The mirror solution slips past every check | Already fixed in round 1 |
| — | wgguan | Where the originals are, and an offline copy | Already answered in round 5 (cloud drive) |

## 2. Owner's decisions

- Reject the automatic removal of low-R² sweeps.
- Add the CI workflow even though it cannot be run before the push.

## 3. Checks made for the documents

- **Abhiraj's damping claim** was re-run with a temporary test, which was
  deleted afterwards. Excluding the 5.5, 26.5, 27, 28 and 29 GHz sweeps
  gives α = 0.00125 ± 0.000035, linewidth R² = 0.968, damping established,
  and g = 2.012. That confirms his "0.0013 without".
- **Agent setup facts:**
  - `~/.claude/settings.json` holds only `{"theme": "dark"}`, so there are
    no permission rules and no sandbox configuration.
  - The git credential helper is `osxkeychain`.
  - No `gh` CLI and no `~/.ssh` directory.
  - `.env` files exist in the parent course folders. They were listed but
    not opened.
  - The repository has no `.claude/settings.json`.

## 4. Changes

| File | What |
|---|---|
| `.github/workflows/verify.yml` | `make verify` on PRs and pushes to `main`, `contents: read`, a 30-min timeout, and uploads `artifacts/` |
| `AGENTS.md` | A new Git rule: no merge, or request for one, without a passing `make verify`; stop if Docker is down |
| `.claude/skills/review-to-tasks/SKILL.md` | The review → table → owner decision → `TASKS.md` procedure used all session |
| `.claude/skills/verify-and-record/SKILL.md` | Stage by name, run the gate, stop on failure, record the results and what was not verified |
| `docs/check-in.md` | Update section naming the commits, the mirror fix and the damping caveat with Abhiraj's numbers |
| `docs/agent-setup-and-review-response.md` | New: the setup table and the half page on accepted and rejected criticism |
| `README.md` | A "Safety nets" passage: the layers, CI, branch protection, skills, and a link to the new document |
| `ARCHITECTURE.md` | The layout lists `.github/workflows/`, `.claude/agents/` and `.claude/skills/` |
| `TASKS.md` | The round 6 item ticked, plus an open owner task: branch protection |

The skill in item 4 includes "stage files by name, never a whole folder".
That rule comes from this session's round 1 mistake, when `git add notes`
committed six deletions.

## 5. Verification

- `make verify` passed with the changes above: lint, 67 tests, the API
  smoke check and the Chromium checks. No app code changed in this round.

## 6. Not verified

- **The CI workflow has never run.** It runs only after the push. GitHub
  may also refuse to accept a workflow file if the Keychain token lacks the
  `workflow` scope. The browser stage builds Chromium on the runner, and
  that has not been tried on GitHub's Ubuntu images.
- **Branch protection is not on**; only the owner can enable it.
- **The two skills have not been invoked yet.** They were written from the
  procedure used in this session.
- The agent-setup table describes this machine and session. Whether the
  Claude Code harness applied any OS-level sandbox beyond the settings file
  could not be confirmed from inside the session.
