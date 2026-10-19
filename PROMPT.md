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

## Out-of-plane magnetic anisotropy plots (implemented 2026-10-19)

The app now supports out-of-plane FMR measurements alongside the
existing in-plane workflow. A toggle labeled **In-plane** /
**Out-of-plane** lets users choose the measurement geometry, upload their
folder of sweeps, and generate the corresponding plots.

The out-of-plane workflow uses an approximate linewidth of **10 Oe** and an
effective perpendicular field of **−0.4 T** as initial fitting assumptions.
It keeps the existing CSV input format and generates frequency versus
resonance field with the saturated perpendicular Kittel fit, and linewidth
versus frequency with the damping fit, showing equations and fitted parameters.

The selected geometry is passed to the API so the backend performs the
appropriate scientific analysis and returns plot data and fit curves.
The approved convention is `Beff,⊥ = μ0 Ms − μ0 H2⊥`, with −0.4 T as its
initial value; the saturated perpendicular model is
`f = (g μB/h)(Bres − Beff,⊥)`. The 10 Oe estimate means derivative
peak-to-peak linewidth. These initialize the fits rather than fix the results.
The perpendicular fit does not infer a four-fold in-plane term.

Charts resize to their containers, reserve space for equations and legends,
and export PNGs with fitted values and an opaque background. Switching
geometry asks for a matching folder; validated uploads retain their geometry
and initialization across a browser reload. Daily implementation and
verification records live in `notes/YYYY-MM-DD.md`, beginning with
`notes/2026-10-19.md`.
