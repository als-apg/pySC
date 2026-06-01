import logging
from .load_config import load_yaml
from ..core.multipolar_imperfections import MultipolarImperfectionTable

logger = logging.getLogger(__name__)

def expand_multipolar_imperfections_tables(config_dict: dict):
    tables = config_dict['multipolar_imperfection_tables']
    for table_name in tables:
        table_file = tables[table_name]
        logger.info(f"Loading MultipolarImperfectionTable in {table_file}.")
        tables[table_name] = load_yaml(table_file)

        # pre-validate tables to catch errors just after loading.
        # Validation will be redone again.
        for key in tables[table_name]:
            MultipolarImperfectionTable.model_validate(tables[table_name][key]) 
