---
name: verify-and-record
description: Close a work session by running the gate and recording the result. Use before saying work is done, before asking for a merge, and at the end of a session.
---

# Verify and record

1. `git status --short`. Check that every changed or deleted file is one you
   meant to change. Stage files by name, never a whole folder.
2. Run `make verify`. If Docker does not start or any step fails, **stop**:
   say so, paste the failing output, and do not call the work done or ask
   for a merge.
3. For a change that will be merged, run `make fresh-verify` on the
   committed revision.
4. Look at the screenshots in `artifacts/` when the page changed.
5. Record in the session log (`notes/`): the commit, each command run and
   its result line (for example `67 passed`, `Browser checks passed`), any
   check shown failing first, and what was **not** verified.
6. Commit the log. Use the real commit hashes, checked with `git log`.
