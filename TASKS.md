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
  - Still open: tighten the golden tolerances in
    `test_broadband_dataset_analysis_returns_all_sweeps`, which needs one
    run to record current values. Rotating the API key from `3fee3a2` and
    setting a git identity need the owner.

- [ ] Export plotted data and fits as a text/CSV download, including the fits to
  the raw traces (`notes/2026-11-11.md`, luyunqi 2026-10-13).
