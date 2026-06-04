import logging
from .load_config import load_yaml
from ..core.multipolar_imperfections import ImperfectionsModelFactory

logger = logging.getLogger(__name__)

def expand_multipolar_imperfection_models(config_dict: dict):
    models = config_dict['multipolar_imperfection_models']

    for model_name, model_spec in models.items():
        if isinstance(model_spec, str):
            logger.info(
                f"Loading multipolar imperfection model {model_name} from {model_spec}."
            )
            model_object = load_yaml(model_spec)
        else:
            model_object = model_spec

        if not isinstance(model_object, list):
            raise TypeError(
                f"Multipolar imperfection model {model_name} must be a list of "
                f"table/curve entries or a filename pointing to such a list. "
                f"Got {type(model_object)}."
            )

        # Pre-validate models to catch errors just after loading.
        # Validation will be redone later.
        ImperfectionsModelFactory.model_validate({"factories": model_object})
        models[model_name] = model_object
