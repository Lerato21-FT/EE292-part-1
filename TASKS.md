Tasks are specified here. When done with a task, label it as complete. Execute the tasks in order of the priority. 
# Tasks

- [x] Allow valid out-of-plane uploads to be plotted before magnetic-property fits succeed.
  - Validate CSV structure, finite samples, positive frequency metadata, and fit settings independently of scientific fitting.
  - Preserve signed resonance fields and raw traces. Report unavailable aggregate fits explicitly and allow linked exclusions to recover them.
  - Keep raw sweeps accessible when individual resonance extraction fails; require explicit exclusion before fitting the remaining measurements.
  - Clear stale properties and curves when the selected subset cannot be fitted. Test mixed-sign uploads, exclusion/restoration, malformed-upload rejection, and raw-trace access before marking complete.
  - Completed 2026-10-26: three regression tests demonstrated the original failure before implementation. `make fresh-verify` passed at revision `dcae08c`: lint, all 29 numerical/API tests, API smoke, and Chromium checks including signed points before fitting, exclusion recovery of known g/damping values, restoration, failed raw resonance fits, and narrow-screen layouts.
  - Verification used synthetic signed-field data; the user's actual folder, Safari, and Firefox were not tested. The perpendicular property model still uses the nonnegative resonance-field branch; signed raw data remains unchanged.

- [x] Add linked dataset exclusions after plotting FMR frequency vs linewidth and FMR frequency vs field.
  - Let the user select plotted data points whose underlying raw-data fits are unreliable and apply an exclusion.
  - Link exclusions by dataset: excluding a dataset from either plot excludes its corresponding point from both plots and both magnetic-property fits.
  - Recompute the affected fits and extracted magnetic properties in the backend using only included datasets, and return updated results through the API.
  - Preserve original raw data and allow users to restore excluded datasets and recalculate the results.
  - Clearly identify excluded datasets and handle insufficient remaining data with an explanatory message instead of reporting invalid fits.
  - Validate dataset selections at the API boundary. Test that an exclusion made from either plot affects both analyses, that restoration restores the original results, and that insufficient-data cases are handled. Demonstrate the regression test failing before implementation, then passing.
  - Completed 2026-10-26: regression run demonstrated four failures before implementation; all 21 numerical/API tests now pass. `make verify` passed in a fresh clone at revision `59254a7`, including lint, API smoke, and Chromium checks for both geometries, linked selection from either plot, restoration, insufficient-data recovery, responsive layouts, and PNG export.
  - Exclusions survive refits in the current page and reset on reload or successful replacement upload. Safari and Firefox were not verified.

- [x] Address the 2026-11-16 referee review (`feedback/2026-11-16_review.md`).
  - Done 2026-11-18 on `fix/referee-2026-11-16`. Physics tests use
    CODATA-derived constants and hand-calculated anchors, plus a known-answer
    in-plane dataset. Fits report 1σ errors. A failing linewidth fit no
    longer discards the Kittel fit. Sweeps with R² < 0.98 are flagged.
    Modulation broadening is checked. Non-positive in-plane resonances are
    explained, and parameters at a bound are named. The smoke check and
    `make clean` were fixed, upload-safety and 422 tests were added, and the
    docs were updated.
  - **Not verified:** none of the tests, `make verify` or `make fresh-verify`
    were run. Docker Desktop was unavailable, and the owner chose to skip
    the run. The fail-first demonstration was skipped too.
  - Golden tolerances tightened on 2026-11-19 (round 4). Still open:
    rotating the API key from `3fee3a2` and setting a git identity, both of
    which need the owner.

- [x] Address peer review round 1 (`feedback/20261014_allenduh_l6134546.md`,
  `feedback/20261119_wgguan_l6134546_3a.md`).
  - Done 2026-11-19 on `fix/round1-feedback`. Fixed a one-digit typo in μB/h.
    The damping test now uses a documented 1e-9 tolerance. The in-plane
    mirror solution is reported, and α is marked "not established" when
    R² < 0.5 or ΔH0 + 2σ < 0. Added an intro dialog with the "so what",
    MathML equations, print-style PNG export and a model-scope list.
  - Fail-first shown: 2 failures before any change, then 7 new tests that
    failed on the old code. Log: `notes/2026-11-19-round1-session-log.md`.

- [x] Add the milestones and top three risks to the README (peer review round 2,
  `feedback/20261013_luyunqi_l6134546.md`).
  - Done 2026-11-19 on `fix/round1-feedback`, in the README section "Milestones
    and risks". The owner confirmed the three risks. "Why the work matters" and the
    quantitative PROMPT.md were already done. Log:
    `notes/2026-11-19-round2-session-log.md`.

- [ ] Export plotted data and fits as a text/CSV download, including the fits to
  the raw traces (`notes/2026-11-11.md`, luyunqi 2026-10-13).
  - Postponed by the owner on 2026-11-19 (round 2 review); it is the next milestone.

- [x] Address peer review round 4 (`feedback/20261118_cd24_l6134546.md`,
  `feedback/20261119_sayragr_l6134546.md`).
  - Done 2026-11-19 on `fix/round1-feedback`. The bundled results are
    pinned as a tripwire. The page leads with the result and a backend
    `summary`. Colours have one meaning each, with violet for selected.
    There is a light theme (the default) and a dark toggle.
    Log: `notes/2026-11-19-round4-session-log.md`.

- [ ] Put each measurement geometry in one record (peer review round 3,
  `feedback/20261119_wgguan_l6134546_5a.md`). Staged 2026-11-19; not started.
  - In `pipeline.py`, one record per geometry holds the model function, the
    fitter, the parameter bounds, the default starting field and its allowed
    range, the equation, and the labels. The pipeline picks the record once by
    geometry, instead of the `if geometry == ...` branches in
    `resolve_analysis_settings` and `_fit_magnetic_properties`.
  - The API returns the bounds, the starting-field range, the equations and
    the labels with the result, so `app.js` only displays them and has no
    geometry branches. Adding a geometry, such as a tilted field, should be
    one new record.
  - Start with the values that are already copied. The starting-field range
    (−2 or 0 up to 2 T) is in `app.js`, `resolve_analysis_settings` and both
    Kittel fitters. The equation is in the API strings, the `app.js` plot
    annotations, and the `EQUATIONS` MathML added in round 1. The per-geometry
    `MODEL_SCOPE` text, also added in round 1, belongs in the record too.
  - Done means: the existing tests pass unchanged. A new test checks that
    every geometry record is complete and that the API returns it. A
    `grep` for `out_of_plane` in `app.js` finds only the geometry toggle.
