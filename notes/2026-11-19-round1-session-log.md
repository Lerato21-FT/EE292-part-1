# 2026-11-19: Peer review round 1, session log

A record of today's session with Claude Code, addressing the two reviews
written on the `ee292m_round1` form:

- Yi-Shiou Duh (allenduh), 2026-10-14, commit `2b5d02a`, score 3 of 5:
  `feedback/20261014_allenduh_l6134546.md`
- Helena Guan (wgguan), 2026-11-19, commit `4c4b30b`, score 5 of 5:
  `feedback/20261119_wgguan_l6134546_3a.md`

Branch: `fix/round1-feedback`, from `main` at `5d66592`. Committed locally;
not pushed yet, by the owner's choice.

## 1. Suggestions

| # | Reviewer | Suggestion | Outcome |
|---|---|---|---|
| 1 | wgguan | Name the in-plane mirror solution in the warnings, say which one the bounds picked, and rewrite `test_parameter_pinned_at_a_bound_is_reported` | Done |
| 2 | wgguan | Set the damping test tolerance to about 1e-9, with the reason | Done, and the cause was found (see 3) |
| 3 | wgguan | Mark α "not established" on its card when the linewidth fit is poor | Done, with the owner's rule |
| 4 | allenduh | A basic intro button for readers outside the field | Done: "New to FMR? Start here" |
| 5 | allenduh | Equations, including the aligned-axis Kittel model, shown in a good form | Done: MathML, and subscripts on plot labels |
| 6 | allenduh | The saved linewidth PNG is ugly | Done: print-style export for all charts |
| 7 | allenduh | Model scope not pretty; make the "so what" clear | Done: scope is a list, and the significance is in the README and the intro dialog |

## 2. Owner's decisions

- α is not established when **ΔH0 + 2σ < 0** (not just ΔH0 < 0), so a
  negative but zero-consistent intercept like the demo's −14.5 ± 17 Oe does
  not trigger it. The linewidth **R² < 0.5** condition from the plan was kept,
  and an unresolved slope also counts.
- Delete the old half-week summaries in `feedback/` (`2026-09-30_wed-sat.md`
  through `2026-11-11_wed-sat.md`).
- Commit locally; push at the end.

## 3. Findings

- **μB/h typo.** `pipeline.py` had `13.99624493361`, one extra `3` compared
  with its own comment and CODATA 2018 (`13.9962449361`). That is 1.8e-10
  relative, exactly the damping test's miss (`0.005999999998904` vs `0.006`).
  The constant test only checked to 1e-9, so it never saw the typo. That
  test is now 2e-11, and the damping test uses Helena's 1e-9 with the reason
  written next to it.
- **Mirror solution.** `(Beff,⊥, B4) → (−Beff,⊥, B4 + Beff,⊥)` leaves the
  in-plane model unchanged. The PMA test case (Beff,⊥ = −0.1 T) fits as
  +0.1 T / B4 = −0.1 T with R² = 1, so nothing hits a bound and the old test
  could never pass. The pipeline now reports the mirror when its B4 is
  inside the B4 fit range (≤ 0.5 T). On the demo data the mirror needs
  B4 ≈ 0.93 T, so it is ruled out and no warning appears, as Helena expected.
- **Demo α.** With linewidth R² = 0.096, the demo's α is now shown as NOT
  ESTABLISHED, unhighlighted, with the reason in the warnings.

## 4. Commits

| Commit | What |
|---|---|
| `89ff8c8` | Remove the superseded half-week feedback summaries |
| `fc1dcd3` | Keep `feedback/2026-11-16_review.md`, which was also deleted in the working tree but is linked from `TASKS.md` and was not in the approved list |
| `22ff571` | Backend: constant fix, mirror solution, damping concerns, tests |
| `70297bd` | Frontend: intro dialog, MathML, print-style PNG, α status, browser checks |
| `aaea2d8` | Docs: README "Why it matters", mirror and damping rules, API fields, PNG export; ARCHITECTURE, `docs/fmr-model.md`, PROMPT thresholds, TASKS |
| this | This log |

## 5. Verification

- **Before any change:** `make test` gave 2 failed and 54 passed. The two
  failures were the ones in Helena's review.
- **Fail-first:** the 7 new and tightened tests were run against the old
  backend. All 7 failed: the mirror (2), the constant (1) and damping
  established (4).
- **After:** `make test` gave 61 passed, and `make lint` was clean.
- `make verify` passed: lint, 61 tests, the API smoke check, and the
  Chromium checks. The new browser checks cover the intro dialog, MathML
  presence, NOT ESTABLISHED on the demo α, the model-scope list, and a
  2400 × 1700 PNG export.
- `make fresh-verify` passed on the committed docs revision.
- The screenshots and the exported linewidth PNG were inspected by eye.

During the work, the browser check caught two bugs that are now fixed. The
export passed `line: undefined` to Plotly, and the "(not established)"
annotation clipped at 320 px. A malformed MathML subscript in ΔHpp was
caught on screenshot review and fixed too.

## 6. Not verified

- Safari and Firefox were not tested. MathML rendering and the `<dialog>`
  element were checked in Chromium only.
- The intro text's physics was written by the agent and has not been
  reviewed by a domain expert. In particular, the "So what?" device claims
  are general statements, not citations.
- Helena's broadband golden values (±20 % on α) were not tightened. That
  item from `TASKS.md` is still open.
- Neither reviewer has seen the changes. Helena asked for answers on the PR.
