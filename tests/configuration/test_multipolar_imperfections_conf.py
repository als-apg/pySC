"""Tests for pySC.configuration.multipolar_imperfections_conf."""
import pytest
import yaml

from pySC.configuration.multipolar_imperfections_conf import (
    expand_multipolar_imperfection_models,
)
from pySC.core.multipolar_imperfections import ImperfectionsModelFactory


def _model_entries():
    """Return a mixed table/curve imperfection model configuration."""
    return [
        {
            "reference_radius": 0.0065,
            "reference_type": ["B", 2],
            "mean_bn": [0, 0, 10],
            "mean_an": [0, 0, 0],
        },
        {
            "reference_radius": 0.0065,
            "reference_type": ["B", 2],
            "source_type": ["B", 2],
            "target_type": ["b", 6],
            "source": [0.4435, 0.6192, 0.6996, 0.7623, 0.7954, 0.8069],
            "target": [1.740, 1.360, 0.820, 0.000, -0.610, -0.840],
        },
    ]


def test_expand_multipolar_imperfection_models_loads_file(tmp_path):
    """Model entries can be loaded from a YAML file."""
    model_file = tmp_path / "multipolar_model.yaml"
    with open(model_file, "w") as f:
        yaml.dump(_model_entries(), f)
    config = {"multipolar_imperfection_models": {"mixed_model": str(model_file)}}

    expand_multipolar_imperfection_models(config)

    model_object = config["multipolar_imperfection_models"]["mixed_model"]
    factory = ImperfectionsModelFactory.model_validate({"factories": model_object})
    assert [type(item).__name__ for item in factory.factories] == [
        "MultipolarImperfectionTableFactory",
        "MultipolarImperfectionCurveFactory",
    ]


def test_expand_multipolar_imperfection_models_accepts_inline_definitions():
    """Model entries can be provided inline in the configuration dict."""
    config = {"multipolar_imperfection_models": {"mixed_model": _model_entries()}}

    expand_multipolar_imperfection_models(config)

    model_object = config["multipolar_imperfection_models"]["mixed_model"]
    factory = ImperfectionsModelFactory.model_validate({"factories": model_object})
    assert [type(item).__name__ for item in factory.factories] == [
        "MultipolarImperfectionTableFactory",
        "MultipolarImperfectionCurveFactory",
    ]


def test_expand_multipolar_imperfection_models_rejects_non_list_model():
    """Each model must expand to a list of table/curve entries."""
    config = {"multipolar_imperfection_models": {"bad_model": {"reference_radius": 0.0065}}}

    with pytest.raises(TypeError, match="must be a list"):
        expand_multipolar_imperfection_models(config)
