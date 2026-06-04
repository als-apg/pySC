from __future__ import annotations
from typing import Literal, Tuple, Optional, Annotated, Union
from pydantic import BaseModel, model_validator, PositiveInt, PositiveFloat, NonNegativeInt, Field
import numpy as np

from .rng import RNG

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

    @property
    def max_length(self) -> PositiveInt:
        return max(len(self.an), len(self.bn))

    @model_validator(mode="after")
    def check_table_validity(self):
        if len(self.bn) != len(self.an):
            raise ValueError("bn and an must have the same length.")
        if len(self.bn) > len(factorial):
            raise NotImplementedError(
                "length of an or bn is larger than supported (which is equal to 21)."
            )
        return self

    def get_Kn_Ks_over_Kref(self, convention: Literal["xsuite", "at"] = "xsuite") -> Tuple[np.ndarray, np.ndarray]:
        N = len(self.bn)
        m = self.reference_order
        radius = self.reference_radius
        factor: np.ndarray =  np.power(radius, m - 1 - np.arange(N)) * factorial[:N] / factorial[m-1] / 10000
        Kn_Kref = np.array(self.bn) * factor
        Ks_Kref = np.array(self.an) * factor

        if convention not in ['xsuite', 'at']:
            raise NotImplementedError(f"Unknown convention {convention}.")

        if convention == 'at':
            Kn_Kref /= factorial[:N] / factorial[m-1]
            Ks_Kref /= factorial[:N] / factorial[m-1]

        return Kn_Kref, Ks_Kref

    def get_Kn_Ks(self, Kn_in: np.ndarray, Ks_in: np.ndarray, Brho: Optional[PositiveFloat] = None,
                  convention: Literal["xsuite", "at"] = "xsuite") -> Tuple[np.ndarray, np.ndarray]:
        Kn_Kref, Ks_Kref = self.get_Kn_Ks_over_Kref(convention=convention)
        if self.reference_component == "B":
            Kref = Kn_in[self.reference_order - 1]
        elif self.reference_component == "A":
            Kref = Ks_in[self.reference_order - 1]
        else:
            raise ValueError(f"Unknown reference component: {self.reference_component}.")
        Kn = Kn_Kref * Kref
        Ks = Ks_Kref * Kref
        return Kn, Ks

class MultipolarImperfectionCurve(BaseModel, extra="forbid"):
    """
    Class to hold multipolar imperfections curve. Uses MAD-X, XSuite, PALS conventions. 
    """
    reference_radius: PositiveFloat
    reference_type: Tuple[Literal["B", "A"], PositiveInt]
    source_type: Tuple[Literal["B", "A"], PositiveInt]
    target_type: Tuple[Literal["b", "a"], PositiveInt]
    source: list[float]
    target: list[float]

    @property
    def reference_component(self) -> Literal["B", "A"]:
        return self.reference_type[0]

    @property
    def reference_order(self) -> PositiveInt:
        return self.reference_type[1]

    @property
    def reference_field(self) -> str:
        return f"{self.reference_component}{self.reference_order}"

    @property
    def source_component(self) -> Literal["B", "A"]:
        return self.source_type[0]

    @property
    def source_order(self) -> PositiveInt:
        return self.source_type[1]

    @property
    def source_field(self) -> str:
        return f"{self.source_component}{self.source_order}"

    @property
    def target_component(self) -> Literal["b", "a"]:
        return self.target_type[0]

    @property
    def target_order(self) -> PositiveInt:
        return self.target_type[1]

    @property
    def target_field(self) -> str:
        return f"{self.target_component}{self.target_order}"

    @property
    def max_length(self) -> PositiveInt:
        return max(self.source_order, self.target_order, self.reference_order)

    @model_validator(mode="after")
    def check_table_validity(self):
        if len(self.source) != len(self.target):
            raise ValueError("source and target must have the same length.")
        if not np.all(np.array(self.source) > 0):
            raise ValueError("source in MultipolarImperfectionCurve is not all positive. If the curve is truly not symmetric w.r.t. zero please contact support.")
        if not np.all(np.diff(self.source) > 0):
            raise ValueError("source in MultipolarImperfectionCurve is not monotonic in ascending order.")
        return self

    def get_harmonic_from_K(self, Kn_in: np.ndarray, Ks_in: np.ndarray, 
                            order: PositiveInt, component: Literal['A','B'], Brho: PositiveFloat,
                            convention: Literal["xsuite", "at"] = "xsuite") -> float:
        if component == "B":
            lattice_value = Kn_in[order - 1]
        elif component == "A":
            lattice_value = Ks_in[order - 1]
        else:
            raise ValueError(f"Unknown source component: {component}. (Should be equal to B or A.)")

        if convention == 'at':
            # convert to MADX/XSuite convention.
            lattice_value *= factorial[order - 1] 

        # convert to harmonic
        harmonic = Brho * ( self.reference_radius ** (order - 1) ) / factorial[order - 1] * lattice_value
        return harmonic

    def get_Kn_Ks(self, Kn_in: np.ndarray, Ks_in: np.ndarray, Brho: PositiveFloat,
                  convention: Literal["xsuite", "at"] = "xsuite") -> Tuple[np.ndarray, np.ndarray]:

        source_value = self.get_harmonic_from_K(Kn_in=Kn_in, Ks_in=Ks_in, order=self.source_order,
                                                component=self.source_component, Brho=Brho,
                                                convention=convention)
 
        # Here we assume the "source array" will be all positive. We take the absolute value for the calculation of the target an or bn.
        # The correct sign will be carried to the real field when converting an/bn -> An/Bn -> Kn, Ks
        source_value = abs(source_value)

        if source_value < self.source[0] or source_value > self.source[-1]:
            raise ValueError('source_value is outside source array from the configuration!')

        # interpolate to get target
        target_ab = np.interp(source_value, self.source, self.target)

        # get Bref reference for conversion
        Bref = self.get_harmonic_from_K(Kn_in=Kn_in, Ks_in=Ks_in, order=self.reference_order,
                                        component=self.reference_component, Brho=Brho, 
                                        convention=convention)

        # convert bm/am to Bm/Am
        target_AB = target_ab / 10000 * Bref

        target_KnKs = target_AB / Brho / ( self.reference_radius ** (self.target_order - 1) ) * factorial[self.target_order - 1]

        if convention == 'at':
            # convert to MADX/XSuite convention.
            target_KnKs /= factorial[self.target_order - 1] 

        max_length = self.max_length
        Kn = np.zeros(max_length)
        Ks = np.zeros(max_length)

        if self.target_component == "b":
            Kn[self.target_order - 1] = target_KnKs
        elif self.target_component == "a":
            Ks[self.target_order - 1] = target_KnKs
        else:
            raise ValueError(f"Unknown target component: {self.target_component}. (Should be equal to b or a.)")

        return Kn, Ks

IMPERFECTION_TYPES = Union[MultipolarImperfectionTable, MultipolarImperfectionCurve]

class ImperfectionsModel(BaseModel, extra="forbid"):
    list_of_imperfections: Annotated[list[IMPERFECTION_TYPES], Field(min_length=1)]

    @property
    def max_order(self) -> NonNegativeInt:
        return max([mit.max_length for mit in self.list_of_imperfections]) - 1

    def apply(self, Kn: list, Ks: list, Brho: PositiveFloat, convention: Literal["xsuite", "at"] = "xsuite"):
        Kn_in = np.array(Kn)
        Ks_in = np.array(Ks)
        max_table_length = max([mit.max_length for mit in self.list_of_imperfections])
        max_length = max(len(Kn_in), len(Ks_in), max_table_length)
        Kn_out = np.zeros(max_length)
        Ks_out = np.zeros(max_length)
        Kn_out[:len(Kn_in)] += Kn_in
        Ks_out[:len(Ks_in)] += Ks_in
        for table in self.list_of_imperfections:
            Kn_temp, Ks_temp = table.get_Kn_Ks(Kn_in=Kn_in, Ks_in=Ks_in, Brho=Brho, convention=convention)
            Kn_out[:len(Kn_temp)] += Kn_temp
            Ks_out[:len(Ks_temp)] += Ks_temp
        return list(Kn_out), list(Ks_out)

class MultipolarImperfectionTableFactory(BaseModel, extra="forbid"):
    reference_radius: PositiveFloat
    reference_type: Tuple[Literal["B", "A"], PositiveInt]
    mean_bn: Optional[list[float]] = None
    mean_an: Optional[list[float]] = None
    std_bn: Optional[list[float]] = None
    std_an: Optional[list[float]] = None

    @property
    def max_length(self) -> PositiveInt:
        lengths = [len(comp) for comp in [self.mean_bn, self.mean_an, self.std_bn, self.std_an] if comp is not None]
        return max(lengths)
    @property
    def reference_component(self) -> Literal["B", "A"]:
        return self.reference_type[0]

    @property
    def reference_order(self) -> PositiveInt:
        return self.reference_type[1]

    @model_validator(mode="after")
    def check_table_validity(self):
        if self.mean_bn is None and self.mean_an is None and self.std_bn is None and self.std_an is None:
            raise ValueError("At least one of mean_bn, mean_an, std_bn, std_an should be specified.")
        if self.reference_component == "B":
            if self.mean_bn is None and self.std_bn is None:
                raise ValueError("At least one of mean_bn, std_bn, should be specified, since the reference component is B.")
            if self.mean_bn is not None:
                if not self.reference_order <= len(self.mean_bn):
                    raise ValueError("Reference order is larger than length of systematic_bn")
            if self.std_bn is not None:
                if not self.reference_order <= len(self.std_bn):
                    raise ValueError("Reference order is larger than length of random_bn")
        elif self.reference_component == "A":
            if self.mean_an is None and self.std_an is None:
                raise ValueError("At least one of mean_an, std_an, should be specified, since the reference component is A.")
            if self.mean_an is not None:
                if not self.reference_order <= len(self.mean_an):
                    raise ValueError("Reference order is larger than length of systematic_an")
            if self.std_an is not None:
                if not self.reference_order <= len(self.std_an):
                    raise ValueError("Reference order is larger than length of random_an")
        else:
            raise ValueError("Bug, this should not happen!")

        max_length = self.max_length
        # create missing lists
        if self.mean_an is None:
            self.mean_an = [0] * max_length
        if self.mean_bn is None:
            self.mean_bn = [0] * max_length
        if self.std_bn is None:
            self.std_bn = [0] * max_length
        if self.std_an is None:
            self.std_an = [0] * max_length

        # make all lists the same length
        while len(self.mean_an) < max_length:
            self.mean_an.append(0)
        while len(self.mean_bn) < max_length:
            self.mean_bn.append(0)
        while len(self.std_an) < max_length:
            self.std_an.append(0)
        while len(self.std_bn) < max_length:
            self.std_bn.append(0)

        # reject tables that are all-zero
        total = np.sum(np.abs(self.mean_bn) + np.abs(self.mean_an) 
                       + np.abs(self.std_bn) + np.abs(self.std_an) )
        if np.isclose(total, 0, atol=1e-15):
            raise ValueError("MultipolarImperfectionTable is all-zero.")

        # remove trailing zeros in bn, an
        while (
            self.mean_bn[len(self.mean_bn) - 1] == 0
            and self.mean_an[len(self.mean_an) - 1] == 0
            and self.std_bn[len(self.std_bn) - 1] == 0
            and self.std_an[len(self.std_an) - 1] == 0
        ):
            del self.mean_bn[len(self.mean_bn) - 1]
            del self.mean_an[len(self.mean_an) - 1]
            del self.std_bn[len(self.std_bn) - 1]
            del self.std_an[len(self.std_an) - 1]

        if max_length > len(factorial):
            raise NotImplementedError("length of an or bn is larger than supported (which is equal to 21).")

        return self

    def create(self, rng: RNG) -> MultipolarImperfectionTable:
        total_bn = np.array(self.mean_bn) + rng.normal_trunc(size=self.max_length) * np.array(self.std_bn)
        total_an = np.array(self.mean_an) + rng.normal_trunc(size=self.max_length) * np.array(self.std_an)
        mit = MultipolarImperfectionTable(reference_radius=self.reference_radius,
                                          reference_type=self.reference_type,
                                          bn=total_bn,
                                          an=total_an,
                                          )
        return mit

class ImperfectionsModelFactory(BaseModel, extra="forbid"):
    factories: Annotated[list[MultipolarImperfectionTableFactory], Field(min_length=1)]

    def create(self, rng: RNG) -> ImperfectionsModel:
        list_of_tables = [factory.create(rng) for factory in self.factories]
        model = ImperfectionsModel(list_of_imperfections=list_of_tables)
        return model
