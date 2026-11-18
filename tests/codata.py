"""Physical constants for tests, taken from CODATA 2018 and not from the code under test.

The Bohr magneton over Planck's constant is derived from the elementary charge and
the electron mass, μB/h = e / (4π mₑ), so a typo or unit mix-up in
`app.pipeline.BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T` cannot also leak into the tests.
"""

import math

ELEMENTARY_CHARGE_C = 1.602176634e-19  # exact since the 2019 SI redefinition
ELECTRON_MASS_KG = 9.1093837015e-31  # CODATA 2018
BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T = ELEMENTARY_CHARGE_C / (4 * math.pi * ELECTRON_MASS_KG) / 1e9
OE_TO_TESLA = 1e-4  # 1 Oe corresponds to μ0 H = 1e-4 T
