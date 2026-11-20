# Agent setup, and the response to peer review round 6

Written 2026-11-19 with Claude Code, for the round 6 "safety nets" reviews
by Abhiraj Gupta (abgup05) and Helena Guan (wgguan). The facts in the table
were checked during the session. For example, `~/.claude/settings.json`
sets only a theme, git uses the macOS Keychain credential helper, and there
is no `gh` CLI and no `~/.ssh`. Where something could not be checked, the
table says so.

## 1. Agent setup

The three legs are **private data** (the agent can read something secret
or personal), **untrusted content** (it reads text written by someone
else, which could carry instructions), and **a way out** (it can send data
somewhere). An agent with all three can be turned against its owner by
the text it reads.

| Component | Where it runs | What it can write | Network it reaches | Credentials it holds | Private data | Untrusted content | A way out |
|---|---|---|---|---|---|---|---|
| **Claude Code, main session** (the agent that wrote this branch) | Directly on the owner's Mac, as the owner's user. **No container**, and no sandbox or permission rules configured in `~/.claude/settings.json`; this session ran in auto mode | Anything the user account can write. By the AGENTS.md rules it wrote only inside this repository and through `make` targets, but nothing technical enforces that | The Anthropic API; Docker registries during `make build`; GitHub over HTTPS via git; web search and fetch tools; claude.ai connectors (Docs, Artifacts). Other connectors (Gmail, Drive, Slack, …) were listed but not signed in | **git push** to `origin` through the Keychain helper; the **Docker daemon**; the claude.ai session. Readable `.env` files exist in the parent folders (not opened this session) | **Yes**: the home folder, other course repos, `.env` files | **Yes**: peer-review files in `feedback/`, written by other people and read this session | **Yes**: git push, web requests, publishing tools |
| **`referee` subagent** (`.claude/agents/referee.md`) | Inside the main session, on the same Mac | Nothing: its tools are `Read`, `Grep`, `Glob` | None of its own | None of its own | **Yes**: `Read` is not limited to the repo | **Yes**: it reads feedback, notes and CSVs; its prompt says to treat them as data | **No direct way.** Its report returns to the main session, which has a way out |
| **App container** (`make up`, `make test`) | Docker on the Mac: read-only root, `/tmp` tmpfs, the host user's UID | Only `/tmp`, which vanishes on stop | Published on `127.0.0.1:8765` only. Outbound access is Docker's default and was not restricted | None | The bundled CSVs and uploads | Uploaded CSVs, parsed as numbers only | Not by design, but outbound network is not blocked |
| **Browser-check container** (`make browser`) | Docker on the Mac, same limits | `/tmp` and the `artifacts/` mount | Its own copy of the API inside the container. Outbound access was not restricted | None | The bundled data only | Pages it serves itself | Not by design |
| **CI runner** (`.github/workflows/verify.yml`, new and **not yet run**) | A GitHub-hosted Ubuntu VM, discarded after each job | Its own workspace | The internet, for image pulls | A `GITHUB_TOKEN` restricted to `contents: read` | The repository only | The code of the pull request it tests | Only what a read-only token allows |

**What this means.** The main session has all three legs. The risk is
real, because this project feeds it text from other people: every round
starts by reading `feedback/`. The protections today are rules, not walls:
- AGENTS.md: everything stays in the repo, and powerful commands run only
  through `make`;
- the review skill treats reviews as data;
- the owner approves each plan.

Cheap ways to remove a leg:
- run Claude Code in a dev container that mounts only this repository and
  holds no Keychain access, which removes most of the private data;
- add `deny` rules for `**/.env` and for `git push` in the project's
  `.claude/settings.json`, which narrows the way out;
- keep using read-only subagents such as `referee` for reading untrusted
  text.

## 2. The criticism I accepted, and the one I rejected

**Accepted: "a safety net that does not depend on remembering" (Helena
Guan).** On 18 November the referee fixes reached `main` while Docker
Desktop was down, so `make verify` never ran. Two of the 56 tests were
failing there. AGENTS.md already said that "done" means a green
`make verify`, so the rule existed, but nothing enforced it. One of those
failures was a real physics bug: a film with negative Beff,⊥ fitted by its
mirror solution with R² = 1 and no warning. That is exactly the kind of
error a person reading the results would not catch. I accepted all three
parts of the suggestion:
- a GitHub Actions workflow that runs `make verify` on every pull request;
- branch protection on `main` requiring that check, which only I can turn
  on, so it is a task in `TASKS.md`;
- a new AGENTS.md line telling the agent to stop, not continue, when Docker
  will not start.

The reasoning is simple. A check that depends on someone remembering to
run it fails on exactly the day something else goes wrong.

**Rejected: "the sweeps with low R² can just be removed from both fits"
(Abhiraj Gupta).** I agree with the diagnosis but not the remedy. Abhiraj
found that five sweeps (5.5, 26.5, 27, 28 and 29 GHz) pull the damping
from α = 0.00125 ± 0.000035 (linewidth R² = 0.968) up to 0.0049 ± 0.0022
(R² = 0.096). I re-ran that and confirmed it. But an automatic R² rule
would not remove those five sweeps; it would remove a different and much
larger set. 36 of the 49 demo sweeps have a resonance R² below the 0.98
flag, so the rule would discard 73 % of the measurements and still not
target the linewidth outliers. On 18 November I decided that low R² is
flagged and not excluded. Chris (round 4) also pointed out that whether
to exclude a sweep is the researcher's judgement, which no test can make.
So the app keeps every sweep. It flags each poor one, marks α as **not
established** when the linewidth fit is poor, and lets me exclude the five
sweeps by hand, which recovers the clean value. The check-in now records
this as the worked example of why the flag exists.
