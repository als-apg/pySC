"""Tests for pySC.core.multipolar_imperfections."""
import numpy as np
import pytest
from pydantic import ValidationError

from pySC.core.multipolar_imperfections import (
    ImperfectionsModelFactory,
    MultipolarImperfectionCurve,
    MultipolarImperfectionCurveFactory,
    MultipolarImperfectionTable,
    MultipolarImperfectionTableFactory,
)
from pySC.core.rng import RNG


def _table_factory_data():
    """Return a deterministic table factory configuration."""
    return {
        "reference_radius": 0.0065,
        "reference_type": ["B", 2],
        "mean_bn": [0, 0, 10],
        "mean_an": [0, 0, 0],
    }


def _curve_factory_data():
    """Return a deterministic curve factory configuration."""
    return {
        "reference_radius": 0.0065,
        "reference_type": ["B", 2],
        "source_type": ["B", 2],
        "target_type": ["b", 6],
        "source": [0.4435, 0.6192, 0.6996, 0.7623, 0.7954, 0.8069],
        "target": [1.740, 1.360, 0.820, 0.000, -0.610, -0.840],
    }


# ---------------------------------------------------------------------------
# MultipolarImperfectionTable
# ---------------------------------------------------------------------------

def test_multipolar_imperfection_table_rejects_unequal_lengths():
    """Direct table construction rejects mismatched bn/an lengths."""
    with pytest.raises(ValidationError, match="bn and an"):
        MultipolarImperfectionTable(
            reference_radius=0.0065,
            reference_type=("B", 2),
            bn=[0, 0, 10],
            an=[0, 0],
        )


def test_multipolar_imperfection_table_factory_creates_table():
    """Table factory creates a deterministic table when std components are omitted."""
    factory = MultipolarImperfectionTableFactory.model_validate(_table_factory_data())

    table = factory.create(RNG(seed=1))

    assert isinstance(table, MultipolarImperfectionTable)
    assert table.reference_type == ("B", 2)
    assert table.bn == [0.0, 0.0, 10.0]
    assert table.an == [0.0, 0.0, 0.0]


def test_multipolar_imperfection_table_factory_applies_std_bn():
    """Table factory samples random bn components from std_bn."""
    data = {
        "reference_radius": 0.0065,
        "reference_type": ["B", 2],
        "mean_bn": [0.0, 1.0, 0.0],
        "std_bn": [0.0, 0.0, 0.5],
    }
    factory = MultipolarImperfectionTableFactory.model_validate(data)

    table = factory.create(RNG(seed=3))
    repeated = factory.create(RNG(seed=3))

    assert table.bn[0] == pytest.approx(0.0)
    assert table.bn[1] == pytest.approx(1.0)
    assert table.bn[2] != pytest.approx(0.0)
    assert table.bn == pytest.approx(repeated.bn)
    assert table.an == [0.0, 0.0, 0.0]


def test_multipolar_imperfection_table_factory_applies_std_an():
    """Table factory samples random an components from std_an."""
    data = {
        "reference_radius": 0.0065,
        "reference_type": ["A", 2],
        "mean_an": [0.0, 1.0],
        "std_an": [0.0, 0.25, 0.5],
    }
    factory = MultipolarImperfectionTableFactory.model_validate(data)

    table = factory.create(RNG(seed=4))

    assert table.an[0] == pytest.approx(0.0)
    assert table.an[1] != pytest.approx(1.0)
    assert table.an[2] != pytest.approx(0.0)
    assert table.bn == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# MultipolarImperfectionCurve
# ---------------------------------------------------------------------------

def test_multipolar_imperfection_curve_factory_creates_curve():
    """Curve factory creates a deterministic curve from source/target arrays."""
    factory = MultipolarImperfectionCurveFactory.model_validate(_curve_factory_data())

    curve = factory.create()

    assert isinstance(curve, MultipolarImperfectionCurve)
    assert curve.reference_type == ("B", 2)
    assert curve.source_type == ("B", 2)
    assert curve.target_type == ("b", 6)
    assert curve.max_length == 6


def test_multipolar_imperfection_curve_factory_rejects_nonmonotonic_source():
    """Curve source values must be strictly increasing for interpolation."""
    data = _curve_factory_data()
    data["source"] = [0.5, 0.4]
    data["target"] = [1.0, 2.0]

    with pytest.raises(ValidationError, match="strictly increasing"):
        MultipolarImperfectionCurveFactory.model_validate(data)


def test_multipolar_imperfection_curve_get_kn_ks_extends_to_target_order():
    """A b6 curve returns arrays long enough to hold the target component."""
    curve = MultipolarImperfectionCurveFactory.model_validate(_curve_factory_data()).create()

    Kn, Ks = curve.get_Kn_Ks(
        Kn_in=np.array([0.0, 100.0]),
        Ks_in=np.array([0.0, 0.0]),
        Brho=1.0,
        convention="xsuite",
    )

    assert len(Kn) == 6
    assert len(Ks) == 6
    assert Kn[5] != pytest.approx(0.0)
    np.testing.assert_allclose(Ks, np.zeros(6))


# ---------------------------------------------------------------------------
# ImperfectionsModelFactory
# ---------------------------------------------------------------------------

def test_imperfections_model_factory_accepts_mixed_factories():
    """Model factory accepts an ordered mix of table and curve definitions."""
    factory = ImperfectionsModelFactory.model_validate(
        {"factories": [_table_factory_data(), _curve_factory_data()]}
    )

    model = factory.create(RNG(seed=1))

    assert [type(item).__name__ for item in model.list_of_imperfections] == [
        "MultipolarImperfectionTable",
        "MultipolarImperfectionCurve",
    ]
    assert model.max_order == 5


def test_imperfections_model_apply_combines_table_and_curve_contributions():
    """Mixed models add table and curve contributions to the incoming strengths."""
    factory = ImperfectionsModelFactory.model_validate(
        {"factories": [_table_factory_data(), _curve_factory_data()]}
    )
    model = factory.create(RNG(seed=1))

    Kn, Ks = model.apply([0.0, 100.0], [0.0, 0.0], Brho=1.0, convention="xsuite")

    assert len(Kn) == 6
    assert len(Ks) == 6
    assert Kn[1] == pytest.approx(100.0)
    assert Kn[2] == pytest.approx(30.769230769230766)
    assert Kn[5] != pytest.approx(0.0)
    np.testing.assert_allclose(Ks, np.zeros(6))
