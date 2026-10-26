# FMR / Field Analysis

A local-only web app for analyzing field-swept ferromagnetic resonance
measurements recorded with a lock-in amplifier. The FastAPI backend reads CSV
sweeps, fits each derivative resonance, extracts its peak-to-peak linewidth,
and fits the dispersion and damping models. The browser only displays API
results and raw traces; it does not perform scientific calculations.

## Run it

Requirements on the host: Docker, Make, and Git. No host Python or Node
installation is used.

```sh
cp .env.example .env   # optional; sets FMR_PORT (default 8765)
make build
make up
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) on the computer running
Docker. API documentation is at [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs).
Stop the app with `make down`. `make help` lists all available targets;
`make verify` runs lint, numerical/API tests, a real API analysis smoke check,
and Chromium browser checks. The browser check builds a separate test image
with its own browser dependencies; the first run downloads Chromium and its
system libraries into that image. Nothing is installed on the host.

Dependencies are installed in the image from `docker/uv.lock` and
`docker/package-lock.json`. Application code, tests, and the `broadband_100/`
demo CSVs are copied into the image at build time. The running app does not
mount your repository. After changing local code or demo data, run `make up`
again to rebuild the image and recreate the container with the changes.
`make build` rebuilds without starting the app. `make test` and `make lint`
also rebuild before checking the code inside Docker. To select test files,
use, for example, `make test TEST_PATHS=tests/test_pipeline.py`.
After editing either dependency manifest, run
`make lock` and commit the updated manifest and lock together. The CSV folder
is never modified.

## Input data

The app starts with bundled **in-plane** demo data. To analyze your own measurements,
select **In-plane** or **Out-of-plane**, then choose a folder in the web app;
its CSV sweeps are uploaded to the local
container and replace the active dataset after validation. The upload is
temporary, is not written into the repository or a host folder, and is removed
when the app container stops. Restarting the app restores the bundled demo.
Uploads are limited to 100 MB and 1000 files.

Each `.csv` filename must contain a frequency such as `-10000MHz-`. The
backend interprets the first column as field in Oe and the second as lock-in
signal; later columns are ignored. Blank lines are allowed, but rows with
missing, non-numeric, or non-finite values are reported as errors. The entire
upload must pass CSV and fit-setting validation before it replaces the active
dataset. Scientific fit success is evaluated afterwards and does not block a
valid upload. An invalid upload leaves the active dataset and geometry unchanged.
Data files are never modified.

Changing geometry hides the previous plots and asks for a matching folder;
it does not reinterpret the demo or the last uploaded dataset automatically.
The selected geometry is used to validate an upload before activation, and
survives a browser reload with the active dataset. Only one dataset is active
at a time. To switch back after uploading a replacement, upload the matching
folder again. Restarting the container restores the in-plane demo.

For **Out-of-plane**, the initial effective perpendicular field is **−0.4 T**
and the initial derivative peak-to-peak linewidth is **10 Oe**. Both are
editable starting estimates, not fixed results. Use **Re-fit dataset** after
changing them. In-plane fits retain the **0.9 T** field initialization and
an adaptive linewidth initialization based on the sweep spacing and span.

Use the **Save PNG** button beside each chart to download a high-resolution
image of that plot in the browser.
Plots include the equations and fitted parameters, including on PNG exports.
Their legends and axis titles have reserved space, and the chart layout
resizes to the available width on desktop and mobile screens. Exported PNGs
are 2000 × 1400 pixels with an opaque dark background.

### Exclude unreliable sweeps

After plotting, click points on either scientific plot to select datasets.
Selected points turn cyan in both plots. You can also select datasets in the
list above the plots, using Ctrl/Command or Shift for multiple selections.
Choose **Exclude selected** to recalculate both fits and their magnetic
properties using the remaining sweeps. Exclusions are linked because both
analyses depend on the same resonance fits, including the g factor used for damping.

Excluded points remain visible as gray crosses, with their status in the
hover label, dataset list, and raw-trace selector. Their raw files are preserved.
Select excluded points and choose **Restore selected**, or use **Restore all
excluded**. At least four included sweeps are required for property fits.
When the selected subset cannot be fitted, its points remain visible and an
explanation appears; unavailable parameters and fit curves are cleared. Restore
datasets or adjust exclusions to recover both fits. The sweep count shows
the number included in the fits. Exclusions survive **Re-fit dataset** in
the current page, and reset on page reload or successful replacement upload.
PNG exports include the gray crosses and the recalculated fit parameters.

### Inspect data before fits succeed

Folders may contain both negative and positive applied fields. The plots and
raw-trace selector remain available even if a negative fitted resonance makes
the current positive-branch perpendicular model unavailable. The page identifies
affected sweeps and preserves their signed field coordinates. Inspect and select
the relevant datasets, then exclude them from both fits to analyze the remaining
positive-branch points. No field magnitudes are substituted and no datasets are
silently dropped. Supporting negative-branch property fits requires a separate
model change.

If an individual resonance cannot be extracted, its raw samples remain
available and its dataset-list entry says **resonance fit unavailable**. It has
no extracted point to plot. Exclude that sweep explicitly before fitting the
remaining measurements. Both aggregate fits and their parameters stay unavailable
until the included measurements support both models. PNGs display an unavailable
fit annotation when no fit exists.

## Models and units

Each lock-in trace is fitted to a derivative Lorentzian with a linear
background:

```text
V(H) = V0 + m(H − Hr) + A · 2Γ²(H − Hr) / ((H − Hr)² + Γ²)²
ΔHpp = 2Γ / √3
```

The aligned in-plane Kittel fit uses the fitted resonance fields and
frequencies:

```text
f = (g μB / h) √[(Bres + B4)(Bres + B4 + Beff,⊥)]
```

The reported `Beff,⊥` is the effective perpendicular field, conventionally
`μ0 Ms − μ0 H2⊥`; it is not the uniaxial anisotropy constant by itself. An
independent saturation magnetization is required to recover that constant.
The four-fold term is conditional on the aligned `0°` axis and the stated
effective-field model. Since these files contain a single azimuth, they cannot
verify four-fold angular symmetry independently.

The frequency-dependent linewidth fit is:

```text
ΔHpp = ΔHpp,0 + (4π α / √3γ) f
```

where `γ = g μB / ħ`. Fields are converted from Oe to T for the Kittel fit and
from Oe/GHz to T/Hz for damping; the API returns plot axes in the original
experiment-facing units (Oe and GHz). The `0.9 T` setting is the initial
effective perpendicular field for the nonlinear fit, not a claimed measured
anisotropy value.

For a **saturated out-of-plane** measurement, with the static field normal
to the film, the backend instead fits:

```text
f = (g μB / h) (Bres − Beff,⊥)
Beff,⊥ = μ0 Ms − μ0 H2⊥
```

With this sign convention, a negative effective field means perpendicular
anisotropy exceeds the demagnetizing field. The **−0.4 T** starting value
refers to this effective field, not to intrinsic anisotropy by itself.
The model assumes magnetization is aligned with the applied field and uses
the nonnegative field branch, with `Bres − Beff,⊥ > 0`. It does not model
unsaturated, tilted, or multidomain states. A perpendicular sweep cannot
determine the in-plane four-fold term: the API returns `null`, and the page
shows **N/A**. The same peak-to-peak linewidth model yields damping using
the g factor fitted in the selected geometry.

Both dispersion fits need at least four resonance points. Out-of-plane
fits require distinct resonance fields and positive frequencies. The g-factor
bounds are 1–4; the signed out-of-plane effective field is bounded to −2–2 T
and constrained below the smallest resonance field. Fit quality is shown as
R²; fitting a curve alone does not establish that the saturation assumptions
hold for a real sample. The perpendicular equation and effective-field
convention follow [Gopman et al., perpendicular FMR measurements](https://pmc.ncbi.nlm.nih.gov/articles/PMC7580010/).

## API

- `GET /api/measurements` lists frequency sweeps.
- `GET /api/measurements/{measurement_id}` returns one raw trace and its
  fitted resonance curve. If extraction fails, fit parameters are `null`,
  `fit_signal` is empty, and `extraction_error` explains why; raw samples
  are still returned. Optional `initial_linewidth_pp_oe` overrides the
  active dataset's initialization for that trace.
- `POST /api/datasets?geometry=out_of_plane` accepts multipart `files` and
  validates all CSVs and fit settings without requiring successful fits. Optional
  `initial_perpendicular_field_t` and `initial_linewidth_pp_oe` initialize
  the fits and are retained with the accepted dataset. Geometry defaults
  to `in_plane` for compatibility.
- `GET /api/analysis?initial_perpendicular_field_t=0.9` returns extracted
  resonance points, Kittel parameters/curve, linewidth parameters/curve, and
  damping.
- Add repeated `excluded_measurement_ids` query parameters to exclude sweep
  IDs from both fits. All extracted measurements remain in the response with
  an `excluded` flag; `included_measurement_count` reports the fitted subset.
  Unknown, duplicate, empty, or overly long IDs return HTTP 422. Requests
  support up to 1000 IDs
  of at most 255 characters. Exclusions apply to that request only; omitting
  them restores the complete dataset. Raw-trace endpoints remain available.
- Valid analysis requests return HTTP 200 even when scientific fitting fails.
  `kittel_fit` and `linewidth_fit` are both `null` and `fit_error` explains the
  problem, including insufficient included points. Every measurement stays in
  the response; failed extractions have `null` resonance/linewidth/R² values
  and an `extraction_error`. Successful extraction and aggregate fits have
  `null` error fields. Invalid CSV data or settings still return HTTP 422.
- `GET /api/analysis?geometry=out_of_plane&initial_perpendicular_field_t=-0.4&initial_linewidth_pp_oe=10`
  explicitly selects the perpendicular model. Omitting settings uses the
  active upload's geometry and initialization. The response includes
  `geometry` and the initial field/linewidth used for that analysis (a `null`
  initial linewidth means adaptive initialization); invalid settings return HTTP 422.
- `GET /docs` provides the interactive OpenAPI contract.

## Verification and implementation notes

`make browser` checks actual folder uploads, geometry selection, refitting,
reload persistence, rejected-upload recovery, linked exclusions from either
plot, restoration, insufficient-data recovery, and PNG downloads in Chromium.
It also uploads mixed-sign data, inspects points before property fits exist,
recovers known fits through exclusions, and checks failed raw resonance fits.
It checks chart and label bounds at 1440, 1024, 768, 390, and 320 pixel widths
for perpendicular data, and desktop/mobile widths for in-plane data.
Screenshots and exported PNGs are saved under gitignored `artifacts/`.
`make review` checks patch whitespace and shows the working tree changes.
`make fresh-verify` checks the committed revision from a new clone inside
repository `.cache/`, without local `.env` or uncommitted files. It keeps the
checkout for inspection.
Docker builder metadata is kept in gitignored `.cache/buildx/` inside this repository.

Daily implementation records live in [`notes/`](notes/), using
`YYYY-MM-DD.md` filenames. Each record describes behavior, scientific
conventions, tests, and any verification limits. Start with
[`notes/2026-10-19.md`](notes/2026-10-19.md) for the perpendicular workflow.

# EE292-part-1
Herre is where I test some of the exercises from class
