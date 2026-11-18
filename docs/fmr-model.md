# FMR fit convention and limits

The supplied measurement names identify `0°` in-plane sweeps only. The
bundled demo therefore uses an aligned-axis in-plane Kittel effective-field form:

`f = (g μB/h) √[(Bres + B4)(Bres + B4 + Beff,⊥)]`.

`Beff,⊥` is the demagnetization-adjusted perpendicular effective field, not a
standalone uniaxial anisotropy constant. A measured saturation magnetization
is required to infer the uniaxial anisotropy field/energy from this effective
quantity. Likewise, a fit to only one azimuth cannot independently establish
four-fold angular symmetry; `B4` is reported conditionally under the assumed
aligned-axis model. Additional angular sweeps or independent magnetic
characterization are needed to validate those physical interpretations.

For field modulation, the lock-in response is fitted as the first derivative
of a Lorentzian absorption line plus a linear baseline. Its peak-to-peak
linewidth is `ΔHpp = 2Γ/√3`, where `Γ` is the absorption half-width at half
maximum. The linear fit uses
`ΔHpp = ΔHpp,0 + (4π α / √3γ) f`, with `γ = g μB/ħ`.

## Saturated perpendicular measurements

Uploaded data can instead select `out_of_plane`. Its model is

`f = (g μB/h)(Bres − Beff,⊥)`, with `Beff,⊥ = μ0 Ms − μ0 H2⊥`.

This assumes saturation with magnetization aligned along a nonnegative
applied field normal to the film. It requires `Bres − Beff,⊥ > 0` and does
not describe unsaturated, tilted or multidomain states. A negative effective
field means the perpendicular anisotropy field exceeds demagnetization;
Beff,⊥ is defined the same way in-plane, but the in-plane fit only allows
Beff,⊥ ≥ 1e-5 T (see "Limits of the in-plane fit" below).
The implementation initializes Beff,⊥ at −0.4 T and derivative peak-to-peak
linewidth at 10 Oe. Both are adjustable seeds; fitted values come from data.
The API returns `fourfold_field_t: null` because this model cannot infer an
in-plane four-fold term. The common linewidth equation above uses the
g factor from the selected geometry to calculate damping.

Reference: [Gopman et al., perpendicular FMR measurements](https://pmc.ncbi.nlm.nih.gov/articles/PMC7580010/).

## Limits of the in-plane fit

The in-plane fit bounds Beff,⊥ to 1e-5–2 T and requires positive resonance
fields. A film whose perpendicular anisotropy exceeds its demagnetizing
field (Beff,⊥ < 0) cannot be represented in-plane: the fit stops at the lower
bound, and the API names the parameter in `at_bound` and in `warnings`.
Zero or negative in-plane resonances produce an explanatory `fit_error`.
Exclude those sweeps to fit the rest.

## Uncertainties

Kittel parameter errors are the square roots of the diagonal of the
`curve_fit` covariance, scaled by the residual variance because the
measurement noise is not known independently. Linewidth slope and intercept
errors come from ordinary least squares with s² = SSR/(n − 2). The damping
error is σ_α = k·√((g σ_slope)² + (slope σ_g)²), with k = (√3/2)·10⁻⁴·μB/h.
This treats the slope and g errors as independent. All of these are 1σ
statistical errors. They exclude systematic errors such as field
calibration, frequency-dependent background, or choosing the wrong model.
Damping is marked unresolved when the slope is less than 2σ_slope.

## Modulation broadening

Field modulation of RMS amplitude H_rms has a peak-to-peak amplitude
H_m = 2√2·H_rms. The derivative-Lorentzian model assumes H_m is small
compared with the line. A common rule of thumb in field-modulated resonance
is H_m ≲ ΔHpp/3; larger modulation broadens the measured ΔHpp and distorts
the line shape. That biases ΔH0 and can bias α, because the broadening
depends on ΔHpp and so varies with frequency.

The pipeline reads H_rms from filenames containing `N.NOeRMS`. It reports
H_rms and H_m for each sweep and warns when H_m > ΔHpp/3. The bundled files
record 2.0 Oe RMS, or H_m ≈ 5.66 Oe, so sweeps narrower than about 17 Oe
are flagged. No correction is applied: the warning only says where the
measured linewidth may be modulation-limited.

## Fit quality threshold

Sweeps whose resonance fit has R² < 0.98 are flagged (`low_quality`) for
inspection and are not excluded automatically. The reasoning is in
`PROMPT.md`.
