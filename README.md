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
`make verify` runs lint, tests, and a real API analysis smoke check.

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

The app starts with the bundled demo data. To analyze your own measurements,
choose a folder in the web app; its CSV sweeps are uploaded to the local
container and replace the active dataset after validation. The upload is
temporary, is not written into the repository or a host folder, and is removed
when the app container stops. Restarting the app restores the bundled demo.
Uploads are limited to 100 MB and 1000 files.

Each `.csv` filename must contain a frequency such as `-10000MHz-`. The
backend interprets the first column as field in Oe and the second as lock-in
signal; later columns are ignored. Blank lines are allowed, but rows with
missing, non-numeric, or non-finite values are reported as errors. The entire
upload must pass validation and analysis before it replaces the active dataset.
An invalid upload leaves the currently active dataset unchanged. Data files
are never modified.

Use the **Save PNG** button beside each chart to download a high-resolution
image of that plot in the browser.

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

## API

- `GET /api/measurements` lists frequency sweeps.
- `GET /api/measurements/{measurement_id}` returns one raw trace and its
  fitted resonance curve.
- `GET /api/analysis?initial_perpendicular_field_t=0.9` returns extracted
  resonance points, Kittel parameters/curve, linewidth parameters/curve, and
  damping.
- `GET /docs` provides the interactive OpenAPI contract.

# EE292-part-1
Herre is where I test some of the exercises from class
