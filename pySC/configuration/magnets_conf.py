from typing import Any
import numpy as np
import logging
from ..core.simulated_commissioning import SimulatedCommissioning
from ..core.lattice import ATLattice
from ..core.xsuite_lattice import XSuiteLattice
from ..core.magnet import MAGNET_NAME_TYPE, ControlMagnetLink
from ..core.control import LinearConv
from ..core.multipolar_imperfections import MultipolarImperfectionTable
from .general import get_error, get_indices_and_names
from .supports_conf import generate_element_misalignments

logger = logging.getLogger(__name__)

def generate_default_magnet_control(SC: SimulatedCommissioning, index: int, magnet_name: MAGNET_NAME_TYPE,
                                    magnet_category_conf: dict[str, Any], magnet_category_name: str, to_design: bool = False) -> list[str]:
    error_table = dict.get(SC.configuration, 'error_table', {}) # defaults to empty error_table if not declared
    new_control_list = []

    if to_design:
        magnet_settings = SC.design_magnet_settings
    else:
        magnet_settings = SC.magnet_settings

    components_to_invert = dict.get(magnet_category_conf, 'invert', []).copy() # defaults to empty list if not declared
    # we need to copy because we remove elements later to check for undeclared components to invert

    if 'components' in magnet_category_conf:
        components = []
        cal_errors = []
        for comp_dict in magnet_category_conf['components']:
            component, cal_error = comp_dict.copy().popitem()
            components.append(component)
            cal_errors.append(cal_error)

        magnet_length = SC.lattice.get_length(index)
        magnet_settings.add_individually_powered_magnet(
            sim_index=index, controlled_components=components,
            magnet_name=magnet_name, magnet_length=magnet_length,
            to_design=to_design)

        for component, cal_error in zip(components, cal_errors):
            control_name = f'{magnet_name}/{component}'
            link_name = f'{control_name}->{control_name}'

            new_control_list.append(control_name)
            if to_design:
                factor = 1
            else:
                sig = get_error(cal_error, error_table)
                factor = SC.rng.normal_trunc(1, sig)

            component_type, order = magnet_settings.validate_one_component(component)
            if type(SC.lattice) is ATLattice and component == 'B1' and SC.lattice.is_dipole(index):
                # in AT when we have a dipole with bending angle it is a special case,
                # setpoint points to bending angle, but B1 multipole (PolynomB[0]) should be changed
                # TODO: maybe put this on the side of ATLattice?? 
                #   when we do get we return BendingAngle/length + PolynomB[0],
                #   when we do set we subtract BendingAngle/length from setpoint and then set it to PolynomB[0]
                # in XSuite, h controls the reference frame and k0 the strength of the dipole. We can just act on k0.
                bending_angle = SC.lattice.get_bending_angle(index)
                offset = - bending_angle / magnet_length
                setpoint = bending_angle / magnet_length
            else:
                #otherwise it is just the multipole
                offset = 0
                setpoint = SC.lattice.get_magnet_component(index, component_type=component_type, order=order)
                if component[-1] == 'L':
                    length = SC.lattice.get_length(index)
                    setpoint = setpoint * length

            if component in components_to_invert:
                factor *= -1
                components_to_invert.remove(component) 

            magnet_settings.controls[control_name].setpoint = setpoint
            magnet_settings.links[link_name].error.factor = factor
            magnet_settings.links[link_name].error.offset = offset

    assert len(components_to_invert) == 0, f"Found undeclared components in components to invert: magnets/{magnet_category_name}/invert: {components_to_invert}."


    parameters_table = dict.get(SC.configuration, 'parameters', {}) # defaults to empty error_table if not declared
    if 'limits' in magnet_category_conf:
        for comp_dict in magnet_category_conf['limits']:
            component, limit_name = comp_dict.copy().popitem()
            if limit_name not in parameters_table:
                raise Exception(f'ERROR: limits {limit_name} were not found in error_table.')
            limit = float(parameters_table[limit_name])
            control_name = f'{magnet_name}/{component}'
            if control_name not in new_control_list:
                raise Exception('ERROR: Invalid limit.') ## TODO make more verbose
            magnet_settings.controls[control_name].limits = (-abs(limit), abs(limit))

    return new_control_list

def generate_multipolar_imperfection_table_links(SC: SimulatedCommissioning, magnet_names: list[MAGNET_NAME_TYPE],
                                           multipolar_imperfection_table: MultipolarImperfectionTable,
                                           available_controls: list[str], magnet_category_name: str,
                                           mode='random'):
    reference_field = multipolar_imperfection_table.reference_field #B1, B2 ...
    if isinstance(SC.lattice, ATLattice):
        Kn_Kref, Ks_Kref = multipolar_imperfection_table.get_Kn_Ks_over_Kref(convention='at')
    elif isinstance(SC.lattice, XSuiteLattice):
        Kn_Kref, Ks_Kref = multipolar_imperfection_table.get_Kn_Ks_over_Kref(convention='xsuite')
    else:
        raise ValueError("SC.lattice is neither ATLattice nor XSuiteLattice.")

    if reference_field in available_controls:
        suffix = ""
        is_integrated = False
    elif f"{reference_field}L" in available_controls:
        suffix = "L"
        is_integrated = True
    else:
        raise Exception(f"Reference field {reference_field} not found in available controls {available_controls} of {magnet_category_name}.")
    for magnet_name in magnet_names:
        control_name = f"{magnet_name}/{reference_field}{suffix}"
        original_control_link_name = f"{control_name}->{control_name}"
        original_control_link = SC.magnet_settings.links[original_control_link_name]
        if not isinstance(original_control_link.error, LinearConv):
            raise NotImplementedError
        factor0 = original_control_link.error.factor
        offset0 = original_control_link.error.offset
        for comp, K_Kref in zip(["B", "A"], [Kn_Kref, Ks_Kref]):
            for ii, K in enumerate(K_Kref):
                order = ii + 1
                if np.isclose(K, 0, 1e-15):
                    continue
                link = ControlMagnetLink(
                    link_name=f"{control_name}->{magnet_name}/{comp}{order}{suffix}",
                    magnet_name=magnet_name,
                    control_name=control_name,
                    component=comp,
                    order=order,
                    is_integrated=is_integrated
                )
                if mode == 'random':
                    factor = K * SC.rng.normal_trunc()
                elif mode == 'systematic':
                    factor = K
                else:
                    raise ValueError(f"Unknown mode for multipolar imperfection link: {mode}.")
                link.error.factor = factor * factor0
                link.error.offset = factor * offset0
                SC.magnet_settings.add_link(link)


def configure_magnets(SC: SimulatedCommissioning):
    # get magnets configuration, return empty dict if not there
    magnet_conf = dict.get(SC.configuration, 'magnets', {})

    if 'multipolar_imperfection_tables' in SC.configuration:
        multipolar_imperfection_tables = dict.get(SC.configuration, 'multipolar_imperfection_tables')
        MITs : dict[str, dict[str, MultipolarImperfectionTable]] = {}
        for table_name in multipolar_imperfection_tables:
            table_object = multipolar_imperfection_tables[table_name]
            MITs[table_name] = {key: MultipolarImperfectionTable.model_validate(table_object[key]) 
                                for key in table_object}

    for magnet_category_name in magnet_conf.keys():
        magnet_category_conf = magnet_conf[magnet_category_name]
        magnet_list = []
        control_list = []

        indices, magnet_names = get_indices_and_names(SC, magnet_category_name, magnet_category_conf)

        for index, magnet_name in zip(indices, magnet_names):
            magnet_list.append(magnet_name)
            # misalignments
            generate_element_misalignments(SC, index, magnet_category_conf)
            # calibration errors
            new_controls = generate_default_magnet_control(SC, index, magnet_name, magnet_category_conf, magnet_category_name=magnet_category_name)
            _ = generate_default_magnet_control(SC, index, magnet_name, magnet_category_conf, magnet_category_name=magnet_category_name, to_design=True)
            control_list = control_list + new_controls
        SC.magnet_arrays[magnet_category_name] = magnet_list
        SC.control_arrays[magnet_category_name] = control_list

        if 'imperfections' in magnet_category_conf:
            if 'multipolar_imperfection_tables' not in SC.configuration:
                raise Exception("'multipolar_imperfection_tables' not found in configuration.")

            imperfections_conf = magnet_category_conf['imperfections']

            # gather available controls for magnet
            comp_dict_list = magnet_category_conf['components']
            available_controls = []
            for comp_dict in comp_dict_list:
                component, _ = comp_dict.copy().popitem()
                available_controls.append(component)

            if 'random' in imperfections_conf:
                list_of_tables_random = imperfections_conf['random']
                for table in list_of_tables_random:
                    if table not in MITs:
                        raise ValueError(f"Random multipolar imperfection table '{table}' was not declared.")
                    MIT_list = list(MITs[table].values())
                    for MIT in MIT_list:
                        generate_multipolar_imperfection_table_links(SC, magnet_names, MIT,
                                                               available_controls,
                                                               magnet_category_name,
                                                               mode='random')

            if 'systematic' in imperfections_conf:
                list_of_tables_systematic = imperfections_conf['systematic']
                for table in list_of_tables_systematic:
                    if table not in MITs:
                        raise ValueError(f"Systematic multipolar imperfection table '{table}' was not declared.")
                    MIT_list = list(MITs[table].values())
                    for MIT in MIT_list:
                        generate_multipolar_imperfection_table_links(SC, magnet_names, MIT,
                                                               available_controls,
                                                               magnet_category_name,
                                                               mode='systematic')

    SC.magnet_settings.connect_links()
    SC.magnet_settings.sendall()
    SC.design_magnet_settings.connect_links()
    SC.design_magnet_settings.sendall()