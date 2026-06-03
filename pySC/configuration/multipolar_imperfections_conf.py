import logging
from .load_config import load_yaml
from ..core.multipolar_imperfections import ImperfectionsModelFactory

logger = logging.getLogger(__name__)

def expand_multipolar_imperfections_tables(config_dict: dict):
    tables = config_dict['multipolar_imperfection_models']
    for table_name in tables:
        table_file = tables[table_name]
        logger.info(f"Loading MultipolarImperfectionTable in {table_file}.")
        tables[table_name] = load_yaml(table_file)

        # pre-validate tables to catch errors just after loading.
        # Validation will be redone again.
        ImperfectionsModelFactory.model_validate({'factories': tables[table_name]})
