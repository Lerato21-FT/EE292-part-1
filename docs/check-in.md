# Capstone check-in

**Plan:** [`PROMPT.md`](https://github.com/Lerato21-FT/EE292-part-1/blob/2b5d02a/PROMPT.md)
and [`README.md`](https://github.com/Lerato21-FT/EE292-part-1/blob/2b5d02a/README.md)
at `2b5d02a`, the commit peer-reviewed as the plan on 13 October. This
check-in describes `main` at `8527d4a`. The open referee follow-up is on
`fix/referee-2026-11-16` (`88a8f7e`) and is **not yet verified**, so none of
it is listed under "What works".

## Update, 2026-11-19 (peer review round 6)

The sections below describe `main` at `8527d4a`, as first written. Since
then, the referee branch was merged into `main` as `4c4b30b` without a
`make verify` run, and 2 of its 56 tests failed there (Helena Guan, round 6).
Both failures are fixed on `fix/round1-feedback`, where `make verify` and
`make fresh-verify` pass with 67 tests. That branch is what the claims below
now refer to, once it is merged.

Two caveats change the claims:
- **The in-plane mirror solution.** A film with negative Beff,⊥ used to be
  fitted by its mirror pair with R² = 1 and no warning, so every check
  passed. The app now names the mirror whenever the data cannot rule it out.
- **Damping on the bundled data is not established.** α = 0.0049 ± 0.0022
  comes from a linewidth fit with R² = 0.096. Abhiraj Gupta (round 6) traced
  this to five sweeps (5.5, 26.5, 27, 28 and 29 GHz). Excluding them gives
  α = 0.00125 ± 0.000035 with linewidth R² = 0.968 (checked 2026-11-19).
  The app flags α as **not established**, and leaves the exclusion to the
  researcher.

The cut items "typeset equations and an intro for non-specialists" were
done in round 1. The golden values marked "throw away" were re-pinned
tightly in round 4.

## What works

- **Full gate from a fresh clone:** `make fresh-verify` passed at `dcae08c`.
  That run covered Ruff lint, all 29 numerical and API tests, the API smoke
  check, and the Chromium browser checks (recorded in `TASKS.md`).
- **In-plane analysis of the bundled data:** the 49 sweeps in `broadband_100/`
  give g ≈ 1.996, Beff,⊥ ≈ 0.949 T, B4 ≈ −0.020 T and α ≈ 0.0049, with
  Kittel R² > 0.99 (`make test TEST_PATHS=tests/test_pipeline.py`).
- **Out-of-plane analysis:** synthetic sweeps built from g = 2.12,
  Beff,⊥ = −0.4 T and α = 0.0002 come back as g = 2.12 ± 0.001 and
  α = 0.0002 ± 1 %, through both the pipeline and the HTTP API
  (`make test TEST_PATHS=tests/test_out_of_plane.py`).
- **Linked exclusions and recovery:** points excluded from either plot leave
  both fits. Restoring them gives back the original results, and mixed-sign
  or unfittable sweeps stay inspectable (`make browser`, at `dcae08c`).

## What failed, and what I learned

I expected `make verify` to catch a broken fit, but its smoke check could
not fail. It ran `grep -q '"kittel_fit"'`, and that key is always in the
response, set to `null` when the fit fails (`Makefile:66` at `8527d4a`). A
failed fit still printed "Kittel fit returned". The 2026-11-16 referee
review found this, along with physics tests that took their expected values
from the same constant and formulas as the code. On `fix/referee-2026-11-16`
the smoke check now requires a numeric g factor and damping and
`"fit_error":null`, and the tests use CODATA-derived constants and
hand-calculated anchors. What I learned: a check has to be shown failing
before I trust it to pass.

## What I am cutting, and why

- **Angle-dependent sweeps to validate the four-fold term:** I have no data
  at other azimuths, so B4 stays conditional on the aligned-axis model.
- **Intrinsic anisotropy Ku:** this needs an independently measured Ms,
  which I do not have. The app reports the effective field Beff,⊥ only.
- **Typeset equations and an intro for non-specialists** (peer feedback):
  deferred behind the CSV export unless time remains.

The 30 November draft will still claim: *from a folder of field-swept
lock-in sweeps, the app extracts g, Beff,⊥ and Gilbert damping, with 1σ
uncertainties and flagged fit quality, computed in the backend and checked
against known-answer data.*

## Built to throw away, and built to last

- **Throw away:** the golden values in
  `test_broadband_dataset_analysis_returns_all_sweeps`. They are the app's
  own earlier output with loose tolerances (±20 % on α). That is fine as a
  tripwire for unintended changes, but it is not evidence of correctness.
  They will be re-recorded with justified tolerances.
- **Keep:** the analysis pipeline (`src/app/pipeline.py`) and its answer key.
  The answer key is the known-answer synthetic datasets, built from physical
  values stated in advance: `tests/test_out_of_plane.py`, plus
  `tests/test_in_plane.py` on the PR branch. The CODATA constants and
  hand-calculated anchors in `tests/codata.py` and `tests/test_pipeline.py`
  are also on the PR branch. The pipeline is tested by `make verify` and
  documented in `docs/fmr-model.md`, `ARCHITECTURE.md` and the thresholds
  table in `PROMPT.md`.
