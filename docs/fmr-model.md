# FMR fit convention and limits

The supplied measurement names identify `0°` in-plane sweeps only. The
analysis therefore uses an aligned-axis in-plane Kittel effective-field form:

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
