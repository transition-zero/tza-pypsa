import sys
import os
import yaml
import re
import pandas as pd
import numpy as np
import pypsa
import logging
from pathlib import Path

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, '/home/jy/tza-pypsa')
from tz_pypsa.constraints import (
    constr_max_annual_utilisation_generator, 
    constr_min_annual_utilisation_generator,
    constr_max_annual_utilisation_links,
    constr_min_annual_utilisation_links,
    constr_min_annual_utilisation_storage_discharge, 
    constr_max_annual_utilisation_storage_charge,      
    constr_soc_intraday_profile,
    constr_soc_weekly_profile,
    constr_production_target_max,
    constr_production_target_min,
    apply_ramping_cost
)

# Set Gurobi License
os.environ['GRB_LICENSE_FILE'] = '/home/jy/opt/gurobi/gurobi.lic'


def load_config(
    config_path: str
    ) -> dict:
    """Reads YAML and manually resolves ${variable} syntax."""
    with open(config_path, 'r') as f:
        config_str = f.read()
    
    # Load
    config = yaml.safe_load(config_str)
    
    # Extract variables available for substitution
    mapping = {}
    if 'paths' in config:
        mapping.update(config['paths'])
    
    # Regex substitution
    pattern = re.compile(r'\$\{([^}^{]+)\}')

    def replace_env_var(match):
        var_name = match.group(1)
        return str(mapping.get(var_name, f"${{{var_name}}}")) 

    config_str_resolved = pattern.sub(replace_env_var, config_str)
    return yaml.safe_load(config_str_resolved)

def add_missing_carriers(
    n: pypsa.Network
    ) -> None:
    """Adds missing carriers to the network."""
    all_carriers = (
        n.generators.carrier.unique().tolist()
        + n.storage_units.carrier.unique().tolist()
        + n.links.carrier.unique().tolist()
    )
    all_carriers = [c for c in all_carriers if isinstance(c, str)]
    existing_carriers = set(n.carriers.index)
    missing_carriers = set(all_carriers) - existing_carriers
    if missing_carriers:
        n.add("Carrier", list(missing_carriers))

def add_build_year(
    n: pypsa.Network, 
    build_year: int
    ) -> None:
    """Adds build year to the network."""
    if not n.generators.empty: n.generators.build_year = build_year
    if not n.storage_units.empty: n.storage_units.build_year = build_year
    if not n.links.empty: n.links.build_year = build_year

def constraint_implementation(
    n: pypsa.Network, 
    config: dict,
    dispatch_run: bool
    ) -> None:
    """Applies constraints to the network safely based on config availability."""
    logger.info("Applying constraints...")
    n.optimize.create_model()

    # Apply annual utilisation limits if in config
    lim_cfg = config.get('run', {}).get('limit_carriers')
    
    if lim_cfg:
        logger.info("Applying Annual Utilisation Limits...")
        if 'gens' in lim_cfg:
            constr_max_annual_utilisation_generator(n, carriers=lim_cfg['gens'])
            constr_min_annual_utilisation_generator(n, carriers=lim_cfg['gens'])
        else: 
            logger.info("Skipping Annual Utilisation Limits for Generators (not in config).")
        
        if 'links' in lim_cfg:
            constr_max_annual_utilisation_links(n, carriers=lim_cfg['links'])
            constr_min_annual_utilisation_links(n, carriers=lim_cfg['links'])
        else: 
            logger.info("Skipping Annual Utilisation Limits for Links (not in config).")
            
        if 'storage' in lim_cfg:
            constr_min_annual_utilisation_storage_discharge(n, carriers=lim_cfg['storage'])
            constr_max_annual_utilisation_storage_charge(n, carriers=lim_cfg['storage'])
        else: 
            logger.info("Skipping Annual Utilisation Limits for Storage (not in config).")
    else:
        logger.info("Skipping Annual Utilisation Limits (not in config).")

    # Apply SoC profiles if in config
    c_files = config.get('paths', {}).get('constraints', {})
    
    if 'max_intraday' in c_files and 'min_intraday' in c_files:
        logger.info("Applying Intraday SoC Profile...")
        constr_soc_intraday_profile(
            n, 
            max_csv=c_files['max_intraday'],
            min_csv=c_files['min_intraday']
        )
    else:
        logger.info("Skipping Intraday SoC Profile (not in config).")
    
    if 'max_weekly' in c_files and 'min_weekly' in c_files:
        logger.info("Applying Weekly SoC Profile...")
        constr_soc_weekly_profile(
            n, 
            max_csv=c_files['max_weekly'],
            min_csv=c_files['min_weekly'],
            day_shift=2
        )
    else:
        logger.info("Skipping Weekly SoC Profile (not in config).")

    # Apply production targets if in config
    prod_targets = config.get('run', {}).get('production_targets')
    
    if prod_targets:
        if not dispatch_run:
            logger.info("Applying Production Targets...")
            regions = [
                'GRIDREGION-JPN-SH', 'GRIDREGION-JPN-HR', 'GRIDREGION-JPN-CB', 
                'GRIDREGION-JPN-HK', 'GRIDREGION-JPN-KA', 'GRIDREGION-JPN-CG', 
                'GRIDREGION-JPN-TK', 'GRIDREGION-JPN-TH', 'GRIDREGION-JPN-KY'
            ]
            carriers_target = [
                'wind-offshore-unspecified','photovoltaic-unspecified', 'wind-onshore', 
                'geothermal-unspecified', 'biomass', 'hydro-reservoir-and-run-of-river'
            ]

            if 'min' in prod_targets:
                constr_production_target_min(n, regions, carriers_target, prod_targets['min'])
            if 'max' in prod_targets:
                constr_production_target_max(n, regions, carriers_target, prod_targets['max'])
        else:
            logger.info("Skipping Production Targets (dispatch run).")
    else:
        logger.info("Skipping Production Targets (not in config).")

    # Apply ramping costs if in config
    ramping_costs = config.get('ramping_costs')
    
    if ramping_costs:
        logger.info("Applying Ramping Costs...")
        apply_ramping_cost(n, ramping_costs)
    else:
        logger.info("Skipping Ramping Costs (not in config).")

def base_network_setup(
    config: dict
    ) -> pypsa.Network:
    """Sets up the base network."""
    logger.info("--- Starting Base Network Setup ---")
    
    platform_net_path = config['paths']['platform_network']
    data_dir = config['paths']['data_dir']
    
    n = pypsa.Network(platform_net_path)

    # Update generators, storage units, and links components
    for component in ["Generator", "Link", "StorageUnit"]:
        all_names = n.df(component).index
        if not all_names.empty:
            logger.info(f"Removing all existing {component}s ({len(all_names)} items)...")
            n.remove(component, all_names)

    # Import new detailed components
    comp_files = config['paths']['components']
    
    if 'generators' in comp_files:
        p = os.path.join(data_dir, comp_files['generators'])
        n.import_components_from_dataframe(pd.read_csv(p, index_col=0), "Generator")
        
    if 'links' in comp_files:
        p = os.path.join(data_dir, comp_files['links'])
        n.import_components_from_dataframe(pd.read_csv(p, index_col=0), "Link")
        
    if 'storage' in comp_files:
        p = os.path.join(data_dir, comp_files['storage'])
        n.import_components_from_dataframe(pd.read_csv(p, index_col=0), "StorageUnit")

    # Cleanup
    if not n.generators.empty and 'type' in n.generators.columns:
         n.generators['carrier'] = n.generators['type']
    
    if not n.links.empty and 'type' in n.links.columns:
         n.links['carrier'] = n.links['type']
    
    if not n.storage_units.empty and 'type' in n.storage_units.columns:
         n.storage_units['carrier'] = n.storage_units['type']

    add_missing_carriers(n)
    add_build_year(n, config['run']['year'])

    # Reload platform network to get p_max_pu and p_min_pu for renewables
    n_platform = pypsa.Network(platform_net_path)
    n.generators_t.p_max_pu = n_platform.generators_t.p_max_pu
    n.generators_t.p_min_pu = n.generators_t.p_max_pu.filter(regex='biomass|geothermal|hydro')

    out_path = config['paths']['results']['base_network']
    n.export_to_netcdf(out_path)
    logger.info(f"Base network solution saved to {out_path}")

    return n

def capacity_expansion_run(
    config: dict
    ) -> pypsa.Network:
    """Runs the capacity expansion."""
    logger.info("--- Starting Capacity Expansion Run ---")
    
    # Check if we should rebuild base or load existing
    if config['run']['workflow_control'].get('run_base_setup', True):
        n = base_network_setup(config)
    else:
        base_path = config['paths']['results']['base_network']
        if not os.path.exists(base_path):
            raise FileNotFoundError(f"Base network not found at {base_path}. Enable run_base_setup in config.")
        logger.info(f"Loading existing base network from {base_path}")
        n = pypsa.Network(base_path)

    # Constraints
    constraint_implementation(n, config, dispatch_run=False)

    # Solve
    solve_opts = config['solver']['options']
    solve_opts['LogFile'] = 'gurobi_cap_exp.log' 
    
    n.optimize.solve_model(
        solver_name=config['solver']['name'],
        solver_options=solve_opts,
        io_api="direct"
    )
    
    out_path = config['paths']['results']['capacity_expansion']
    n.export_to_netcdf(out_path)
    logger.info(f"Capacity expansion solution saved to {out_path}")
    return n

def dispatch_run(
    config: dict,
    ) -> pypsa.Network:
    """Runs the dispatch."""
    logger.info("--- Starting Dispatch Run ---")
    
    base_net_path = config['paths']['results']['base_network']
    cap_exp_path = config['paths']['results']['capacity_expansion']

    use_base_capacity = config['run']['workflow_control'].get('run_base_setup_capacity', False)

    if use_base_capacity:
        logger.info("Using base network capacity for dispatch.")

        if not os.path.exists(base_net_path):
            raise FileNotFoundError(f"Base network not found at {base_net_path}. Enable run_base_setup in config.")
        
        n = pypsa.Network(base_net_path)
        for component in ["Generator", "Link", "StorageUnit"]:
            df = n.df(component)
            df["p_nom_extendable"] = False

    else:
        logger.info("Using capacity expansion capacity for dispatch.")
        if not os.path.exists(cap_exp_path):
            raise FileNotFoundError(f"Capacity expansion results not found at {cap_exp_path}. Cannot run dispatch.")

        n = pypsa.Network(base_net_path)
        n_exp = pypsa.Network(cap_exp_path)
        
        # Transfer capacities & tracking data
        for component in ["Generator", "Link", "StorageUnit"]:
            df_base = n.df(component)
            df_exp = n_exp.df(component)
            
            # Import missing components
            missing_indices = df_exp.index.difference(df_base.index)
            if not missing_indices.empty:
                logger.info(f"Importing {len(missing_indices)} new {component}s from expansion.")
                n.import_components_from_dataframe(df_exp.loc[missing_indices], component)
            
            # RE-FETCH
            df_current = n.df(component)

            # Calculate expanded capacity
            df_exp["expanded_capacity"] = df_exp["p_nom_opt"] - df_exp["p_nom"]
            
            # Track extendability & optimal capacity
            df_current["was_extendable"] = df_exp["p_nom_extendable"].reindex(df_current.index, fill_value=False)
            df_current["p_nom_expansion_opt"] = df_exp["expanded_capacity"].reindex(df_current.index)
            
            # Update p_nom for dispatch
            ext_ids = df_exp.index[df_exp["p_nom_extendable"]]
            valid_ids = ext_ids.intersection(df_current.index)
            
            if not valid_ids.empty:
                df_current.loc[valid_ids, "p_nom"] = np.ceil(df_exp.loc[valid_ids, "p_nom_opt"])
            
            # Lock capacity
            df_current["p_nom_extendable"] = False

    # Constraints
    constraint_implementation(n, config, dispatch_run=True)

    # Solve
    solve_opts = config['solver']['options']
    solve_opts['LogFile'] = 'gurobi_dispatch.log'
    
    n.optimize.solve_model(
        solver_name=config['solver']['name'],
        solver_options=solve_opts,
        io_api="direct"
    )
    
    out_path = config['paths']['results']['dispatch']
    n.export_to_netcdf(out_path)
    logger.info(f"Dispatch solution saved to {out_path}")
    return n

if __name__ == "__main__":
    # Load configuration
    config = load_config("config.yaml")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(config['paths']['results']['capacity_expansion']), exist_ok=True)

    # --- Workflow Control ---
    run_base_setup = config['run']['workflow_control'].get('run_base_setup', True)
    run_cap_exp = config['run']['workflow_control'].get('run_capacity_expansion', True)

    if run_base_setup:
        base_network_setup(config)
    else:
        logger.info("Skipping Base Network Setup (as per config). Using existing solution.")

    if run_cap_exp:
        capacity_expansion_run(config)
    else:
        logger.info("Skipping Capacity Expansion Run (as per config). Using existing solution.")

    # Dispatch always runs
    dispatch_run(config)