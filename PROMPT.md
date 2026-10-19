Follow AGENTS.md.

Let us build a visualization plotter for ferromagnetic resonance measurements for thin films of magnetic insulator. Let us assume that this was a thin film with in magnetic anisotropy that is as high as 0.9 T. 

The way we did the experiment - we applied an in-plane static magnetic field and then applied a modulation field to allow us to detect the signal using a lock-in amplifier since we did not have a microwave signal detectors like a VNA. 
We did magnetic field sweeps at different frequencies. Each file has the frequency on the file name and the data inside the file is such that the first column is the magnetic field in Oe and the second column is the signal from the lock-in.

I would like to visual the FMR frequency vs field on one plot and then linewidth vs frequency on another plot. 

For the FMR frequency vs field - we should fit the kittel equation for a thin film with in-plane magnetic anisotropy. We want to extract the uniaxial out of plane anisotropy and four fold in-plane magnetic anisotropy as well as the Lande G factor. 

Then use the Lane g factor to extract damping from the linewidth vs frequency fitting. SHow the equations you fit in the plots. 

We want to build a webapp that we can visualize only on the computer which means you are to build a fastAPI exposing the localhost port. 

## Progress so far

We have built a local-only FastAPI web app for field-swept FMR measurements
recorded with a lock-in amplifier. It starts with bundled example data and
allows users to upload a folder of CSV sweeps, with frequency read from each
filename, magnetic field in Oe in the first column, and lock-in signal in the
second column. Uploads are validated before replacing the active dataset and
are stored temporarily in the container.

The backend fits each trace to a derivative Lorentzian with a linear
background to extract resonance field and peak-to-peak linewidth. It then
produces frequency-versus-resonance-field plots with an aligned in-plane
Kittel fit, and linewidth-versus-frequency plots with a damping fit using the
fitted Landé g factor. The fitted perpendicular field is an effective field,
not an independently determined uniaxial anisotropy constant; the four-fold
term assumes an aligned in-plane axis and cannot establish angular symmetry
from a single azimuth.

The browser displays backend results, raw traces and fitted curves, shows
the model equations, and supports PNG plot downloads. Dependencies are built
into Docker images, the app is published only on 127.0.0.1, and the repository
provides automated tests and a `make verify` gate.

## Next step: out-of-plane magnetic anisotropy plots

Extend the app to support out-of-plane FMR measurements alongside the
existing in-plane workflow. Add a button or toggle labeled **In-plane** /
**Out-of-plane** so users can choose the measurement geometry, upload their
folder of sweeps, and generate the corresponding plots.

For the out-of-plane workflow, use an approximate linewidth of **10 Oe** and
an out-of-plane anisotropy field of **−0.4 T** as initial assumptions for
fitting, rather than fixed measured results. Keep the existing CSV input
format. Generate frequency versus resonance field with the appropriate
out-of-plane Kittel fit, and linewidth versus frequency with the damping fit,
showing the fitted equations and parameters on the plots.

The selected geometry must be passed to the API so the backend performs the
appropriate scientific analysis and returns plot data and fit curves. Before
implementing the out-of-plane model, define the sign convention for the
−0.4 T anisotropy field and its relationship to the effective perpendicular
field used in the existing model, and specify whether the 10 Oe estimate is
peak-to-peak linewidth or another linewidth convention.
