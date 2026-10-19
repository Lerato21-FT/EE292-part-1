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
upload must pass validation and analysis before it replaces the active dataset.
An invalid upload leaves the currently active dataset and geometry unchanged. Data files
are never modified.

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
  fitted resonance curve. Optional `initial_linewidth_pp_oe` overrides the
  active dataset's initialization for that trace.
- `POST /api/datasets?geometry=out_of_plane` accepts multipart `files` and
  validates the complete dataset using the selected geometry. Optional
  `initial_perpendicular_field_t` and `initial_linewidth_pp_oe` initialize
  the fits and are retained with the accepted dataset. Geometry defaults
  to `in_plane` for compatibility.
- `GET /api/analysis?initial_perpendicular_field_t=0.9` returns extracted
  resonance points, Kittel parameters/curve, linewidth parameters/curve, and
  damping.
- `GET /api/analysis?geometry=out_of_plane&initial_perpendicular_field_t=-0.4&initial_linewidth_pp_oe=10`
  explicitly selects the perpendicular model. Omitting settings uses the
  active upload's geometry and initialization. The response includes
  `geometry` and the initial field/linewidth used for that analysis (a `null`
  initial linewidth means adaptive initialization); invalid settings return HTTP 422.
- `GET /docs` provides the interactive OpenAPI contract.

## Verification and implementation notes

`make browser` checks actual folder uploads, geometry selection, refitting,
reload persistence, rejected-upload recovery, and PNG downloads in Chromium.
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
