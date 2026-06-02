from __future__ import annotations
from typing import Literal, Tuple
from pydantic import BaseModel, model_validator, PositiveInt, PositiveFloat
import numpy as np

## factorial[n] = n!
factorial = np.array([
1,
1,
2,
6,
24,
120,
720,
5040,
40320,
362880,
3628800,
39916800,
479001600,
6227020800,
87178291200,
1307674368000,
20922789888000,
355687428096000,
6402373705728000,
121645100408832000,
2432902008176640000,
])

class MultipolarImperfectionTable(BaseModel, extra="forbid"):
    """
    Class to hold multipolar imperfections table. Uses MAD-X, XSuite, PALS conventions. 
    """
    reference_radius: PositiveFloat
    reference_type: Tuple[Literal["B", "A"], PositiveInt]
    bn: list[float]
    an: list[float]

    @property
    def reference_component(self) -> Literal["B", "A"]:
        return self.reference_type[0]

    @property
    def reference_order(self) -> PositiveInt:
        return self.reference_type[1]

    @property
    def reference_field(self) -> str:
        return f"{self.reference_component}{self.reference_order}"

    @model_validator(mode="after")
    def check_table_validity(self):
        if self.reference_component == "B":
            if not self.reference_order <= len(self.bn):
                raise ValueError("Reference order is larger than length of bn")
            if not self.bn[self.reference_order - 1] == 10000:
                raise ValueError("Reference field (bn) in MultipolarImperfectionTable should be set to 10000.")
        elif self.reference_component == "A":
            if not self.reference_order <= len(self.an):
                raise ValueError("Reference order is larger than length of an")
            if not self.an[self.reference_order - 1] == 10000:
                raise ValueError("Reference field (an) in MultipolarImperfectionTable should be set to 10000.")
        else:
            raise ValueError("Bug, this should not happen!")

        max_length = max(len(self.an), len(self.bn))
        while len(self.an) < max_length:
            self.an.append(0)
        while len(self.bn) < max_length:
            self.bn.append(0)

        if max_length > len(factorial):
            raise NotImplementedError("length of an or bn is larger than supported (which is equal to 21).")

        return self

    def get_Kn_Ks_over_Kref(self, convention: Literal['xsuite', 'at'] = 'xsuite'):
        N = len(self.bn)
        m = self.reference_order
        radius = self.reference_radius
        factor =  np.power(radius, m - 1 - np.arange(N)) * factorial[:N] / factorial[m-1] / 10000
        Kn_Kref = np.array(self.bn) * factor
        Ks_Kref = np.array(self.an) * factor

        if self.reference_component == "B":
            if not np.isclose(Kn_Kref[m-1], 1, atol=1e-15):
                raise ValueError("BUG: Kref/Kref not equal to 1.")
            Kn_Kref[m-1] = 0
        elif self.reference_component == "A":
            if not np.isclose(Ks_Kref[m-1], 1, atol=1e-15):
                raise ValueError("BUG: Kref/Kref not equal to 1.")
            Ks_Kref[m-1] = 0
        else:
            raise Exception("Bug, this should not happen!")

        if convention not in ['xsuite', 'at']:
            raise NotImplementedError(f"Unknown convention {convention}.")

        if convention == 'at':
            Kn_Kref /= factorial[:N] / factorial[m-1]
            Ks_Kref /= factorial[:N] / factorial[m-1]

        return Kn_Kref, Ks_Kref
