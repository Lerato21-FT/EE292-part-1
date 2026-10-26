Tasks are specified here. When done with a task, label it as complete. Execute the tasks in order of the priority. 
# Tasks

- [x] Add linked dataset exclusions after plotting FMR frequency vs linewidth and FMR frequency vs field.
  - Let the user select plotted data points whose underlying raw-data fits are unreliable and apply an exclusion.
  - Link exclusions by dataset: excluding a dataset from either plot excludes its corresponding point from both plots and both magnetic-property fits.
  - Recompute the affected fits and extracted magnetic properties in the backend using only included datasets, and return updated results through the API.
  - Preserve original raw data and allow users to restore excluded datasets and recalculate the results.
  - Clearly identify excluded datasets and handle insufficient remaining data with an explanatory message instead of reporting invalid fits.
  - Validate dataset selections at the API boundary. Test that an exclusion made from either plot affects both analyses, that restoration restores the original results, and that insufficient-data cases are handled. Demonstrate the regression test failing before implementation, then passing.
  - Completed 2026-10-26: regression run demonstrated four failures before implementation; all 21 numerical/API tests now pass. `make verify` passed in a fresh clone at revision `59254a7`, including lint, API smoke, and Chromium checks for both geometries, linked selection from either plot, restoration, insufficient-data recovery, responsive layouts, and PNG export.
  - Exclusions survive refits in the current page and reset on reload or successful replacement upload. Safari and Firefox were not verified.
