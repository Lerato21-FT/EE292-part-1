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
this is the same effective-field sign convention used by the in-plane model.
The implementation initializes Beff,⊥ at −0.4 T and derivative peak-to-peak
linewidth at 10 Oe. Both are adjustable seeds; fitted values come from data.
The API returns `fourfold_field_t: null` because this model cannot infer an
in-plane four-fold term. The common linewidth equation above uses the
g factor from the selected geometry to calculate damping.

Reference: [Gopman et al., perpendicular FMR measurements](https://pmc.ncbi.nlm.nih.gov/articles/PMC7580010/).
