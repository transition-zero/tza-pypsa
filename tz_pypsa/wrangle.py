import pypsa
import pandas as pd
import numpy as np
import re
import os
import glob
from pathlib import Path
import gc



def get_backstop_generation_by_bus(
        network : pypsa.Network
    ) -> pd.DataFrame:
    
    '''
    Get the backstop generation by bus for a given network.

    Parameters:
        network (pypsa.Network): The PyPSA network object.

    Returns:
        pd.DataFrame: A DataFrame containing the backstop generation by bus.
        
    '''
    return (
        network
        .generators_t
        .p
        .filter(regex='Backstop')
        .sum()
        .reset_index()
        .rename(columns={0: 'MW'})
        .query(' MW > 0' )
        .set_index('Generator')
    )


def get_load_by_bus(
        network : pypsa.Network,
        resample : str = 'YE',
        period : int = 2023,
        mul : float = 1e3,
    ) -> pd.DataFrame:

    '''
    Get the load by bus for a given network and time period.

    Parameters:
        network (pypsa.Network): The PyPSA network object.
        resample (str, optional): The resampling frequency for the load data. Defaults to 'YE' (yearly).
        period (int, optional): The time period for which to retrieve the load data. Defaults to 2023.
        mul (float, optional): The multiplier to apply to the load data. Defaults to 1e3.

    Returns:
        pd.DataFrame: A DataFrame containing the load data by bus, resampled and scaled.

    '''
    return (
        network
        .loads_t
        .p_set
        .loc[period]
        # .droplevel(0)
        .resample(resample)
        .sum()
        .div(mul)
        .reset_index()
        .melt(id_vars='snapshot', var_name='bus', value_name='load')
    )


def export_to_excel(
        network, 
        filename
    ) -> None:

    '''
    Export network components and statistics to an Excel file.

    Parameters:
        network (pypsa.Network): The PyPSA network object.
        filename (str): The name of the Excel file to be created.

    Returns:
        None
    
    '''
    
    # Convert network components to DataFrames
    nodes = network.buses
    generators = network.generators
    links = network.links
    generation_hourly = network.generators_t.p
    generation_monthly = network.generators_t.p.resample('ME').sum()
    storage_hourly = network.storage_units_t.p_dispatch
    storage_monthly = network.storage_units_t.p_dispatch.resample('ME').sum()
    p_by_carrier = network.generators_t.p.groupby(network.generators.type, axis=1).sum()
    p_by_carrier_monthly = network.generators_t.p.groupby(network.generators.type, axis=1).sum().resample('ME').sum()
    interconnector_hourly = network.links_t.p0
    interconnector_monthly = network.links_t.p0.resample('ME').sum()
    statistics = network.statistics()
    loads = network.loads_t.p.resample('ME').sum()
    energy_balance = (network.statistics.energy_balance() / 1e6).round(2)
    curtailment = network.statistics.curtailment()
    installed_capacity = network.statistics.installed_capacity()
    expanded_capacity = network.statistics.expanded_capacity()

    # Create a Pandas Excel writer using XlsxWriter as the engine
    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:

        # Write each DataFrame to a different worksheet
        pd.DataFrame({}).to_excel(writer, sheet_name='Inputs >>>')
        nodes.to_excel(writer, sheet_name='Buses')
        generators.to_excel(writer, sheet_name='Generators')
        links.to_excel(writer, sheet_name='Links')
        loads.to_excel(writer, sheet_name='Loads')

        pd.DataFrame({}).to_excel(writer, sheet_name='Summary >>>')
        statistics.to_excel(writer, sheet_name='Statistics')
        installed_capacity.to_excel(writer, sheet_name='Installed capacity')
        expanded_capacity.to_excel(writer, sheet_name='Expanded capacity')
        energy_balance.to_excel(writer, sheet_name='Energy balance')
        curtailment.to_excel(writer, sheet_name='Curtailment')

        pd.DataFrame({}).to_excel(writer, sheet_name='Results >>>')
        generation_hourly.to_excel(writer, sheet_name='Generation by node (hr)')
        generation_monthly.to_excel(writer, sheet_name='Generation by node (m)')
        storage_hourly.to_excel(writer, sheet_name='Storage dispatch by node (hr)')
        storage_monthly.to_excel(writer, sheet_name='Storage dispatch by node (m)')
        p_by_carrier.to_excel(writer, sheet_name='Generation by carrier (hr)')
        p_by_carrier_monthly.to_excel(writer, sheet_name='Generation by carrier (m)')
        interconnector_hourly.to_excel(writer, sheet_name='Interconnector flow (hr)')
        interconnector_monthly.to_excel(writer, sheet_name='Interconnector flow (m)')

def add_hour_of_year_column(
        df, 
        datetime_col, 
        new_col='hour_of_year'
    ) -> pd.DataFrame:
    """
    Adds a column to the DataFrame indicating the hour of the year for each datetime.
    
    Parameters:
    - df: pandas.DataFrame
    - datetime_col: str, name of the column containing datetime values
    - new_col: str, name of the new column to create (default: 'hour_of_year')
    
    Returns:
    - pandas.DataFrame with the new column added
    """
    if datetime_col not in df.columns:
        raise ValueError(f"Column '{datetime_col}' not found in DataFrame.")
    
    # Ensure datetime type
    df = df.copy()
    df[datetime_col] = pd.to_datetime(df[datetime_col])
    
    # Start of year for each row
    year_start = df[datetime_col].dt.to_period('Y').dt.start_time
    
    # Calculate hours since year start
    df[new_col] = ((df[datetime_col] - year_start).dt.total_seconds() // 3600).astype(int)
    
    return df

def interconnector_by_nodes(
        interconnector_p0: pd.DataFrame, # Export
        interconnector_p1: pd.DataFrame # Import
    )   -> pd.DataFrame:
        
    """
    Concatenate two DataFrames by 'snapshot' and 'Link' columns.

    Parameters
     ----------
    interconnector_p0 : pd.DataFrame
        DataFrame containing the export data.
    interconnector_p1 : pd.DataFrame
        DataFrame containing the import data.

    Returns
    -------
    pd.DataFrame
        Concatenated DataFrame with 'snapshot', 'Link', and 'Value' columns.
     """
    interconnector = pd.concat([interconnector_p0, interconnector_p1], ignore_index=True)
        
    return interconnector.groupby(['snapshot', 'Node', 'Node_Destination']).agg({'Value': 'sum'}).reset_index()

def get_ci_cost_summary(n : pypsa.Network) -> pd.DataFrame:
    '''Returns a summary of the costs for C&I generators, storage units and links
    '''
    ci_generator_costs = (
        n.generators.loc[
            n.generators.index.str.contains('C&I')
        ]
        [['carrier','p_nom','p_nom_opt','capital_cost','marginal_cost']]
    )

    ci_generator_p_max_pu = (
        n.generators_t.p_max_pu.transpose().loc[
            n.generators_t.p_max_pu.transpose().index.str.contains('C&I')
        ]
        .transpose()
    )

    ci_generator_costs['dispatch'] = n.generators_t.p[ ci_generator_costs.index ].sum()
    ci_generator_costs['potential_dispatch'] = (
        ci_generator_costs.p_nom_opt[ ci_generator_costs.index ] 
        * ci_generator_p_max_pu[ ci_generator_costs.index ] 
        ).sum()
    ci_generator_costs['curtailment'] = ci_generator_costs['potential_dispatch'] - ci_generator_costs['dispatch']
    ci_generator_costs['curtailment_perc'] = ci_generator_costs['curtailment']/ci_generator_costs['potential_dispatch']

    # storage
    ci_storage_costs = (
        n.storage_units.loc[
            n.storage_units.index.str.contains('C&I')
        ]
        [['carrier','p_nom','p_nom_opt','capital_cost','marginal_cost']]
    )

    # links
    ci_links_costs = (
        n.links.loc[
            n.links.index.str.contains('C&I')
        ]
        [['carrier','p_nom','p_nom_opt','capital_cost','marginal_cost']]
    )

    # zero link costs because they are virtual
    ci_links_costs['capital_cost'] = 0
    ci_links_costs['marginal_cost'] = 0

    ci_links_costs['dispatch'] = n.links_t.p0[ ci_links_costs.index ].sum()

    df = pd.concat([ci_generator_costs, ci_storage_costs, ci_links_costs]).round(3)

    df.loc[:, 'capex'] = df['p_nom_opt'] * df['capital_cost']
    df.loc[:, 'opex'] = df['dispatch'] * df['marginal_cost']

    # marginal price of the brownfield bus
    ci_brown_bus = n.buses[n.buses.index.str.contains('C&I')].index.str.split('C&I').str[0].str.strip()[0]

    # calculate import costs
    import_links_t = n.links_t.p0.filter(regex='C&I').filter(regex='Import').sum(axis=1)
    import_link_p = n.buses_t.marginal_price[ci_brown_bus]
    import_cost = ( import_links_t * import_link_p ).sum() 

    # append to df
    df.loc[ df.index.str.contains('Import'), 'import_cost' ] = import_cost

    # calculate export revenues
    export_links_t = n.links_t.p0.filter(regex='C&I').filter(regex='Export').sum(axis=1)
    export_link_p = n.buses_t.marginal_price[ci_brown_bus]
    export_revenue = -( export_links_t * export_link_p ).sum().sum()

    # append to df
    df.loc[ df.index.str.contains('Export'), 'export_revenue' ] = export_revenue

    # fillna
    df.fillna(0, inplace=True)

    return df

def get_ci_unit_cost(n: pypsa.Network) -> pd.DataFrame:
    """Calculate unit costs for C&I components in the network.
    
    Args:
        n: PyPSA Network object
        cost_summary: DataFrame containing cost summary from get_ci_cost_summary()
        
    Returns:
        DataFrame containing unit costs broken down by component and node
    """

    cost_summary = get_ci_cost_summary(n)
    unit_cost_denominator = (
        cost_summary[cost_summary.index.str.contains('Grid Imports|Grid Exports')]
        .assign(ci_load = n.loads_t.p.filter(regex='C&I').sum().sum())
        .loc[:, ['dispatch', 'ci_load']]
        .reset_index()
        .assign(
            Node=lambda df: df['index'].str.split('C&I').str[0].str.strip() + ' C&I', 
        )
        .rename(columns={'index': 'flow'})
        .pivot_table(index=['Node', 'ci_load'], columns='flow', values='dispatch')
        .reset_index()
        .rename(columns=lambda x: 'grid_exports' if 'Grid Exports' in str(x) else x)
        .rename(columns=lambda x: 'grid_imports' if 'Grid Imports' in str(x) else x)
        .rename_axis(columns=None)
        .assign(ppa_weighting=lambda df: (df['ci_load'] - df['grid_imports'])/df['ci_load'])
        .assign(import_weighting=lambda df: df['grid_imports'] / df['ci_load'])
    )

    unit_cost = (
        cost_summary[~cost_summary.index.str.contains('Charge|Discharge')]
        .assign(carrier=lambda df: df['carrier'].where(~df.index.str.contains('Grid Exports'), 'Grid Exports'))
        .assign(carrier=lambda df: df['carrier'].where(~df.index.str.contains('Grid Imports'), 'Grid Imports'))
        .assign(total_costs=lambda df: df[['capex', 'opex', 'import_cost', 'export_revenue']].sum(axis=1))
        .reset_index()
        .assign(
            Node=lambda df: df['index'].str.split('C&I').str[0].str.strip() + ' C&I',  # Gets "JPN08 C&I"
        )
        .merge(unit_cost_denominator, left_on = ['Node'], right_on = ['Node'])
        .assign(
            import_unit_cost=lambda df: np.where(
                df['carrier'] == 'Grid Imports',
                df['import_weighting'] * (1/df['grid_imports']) * df['import_cost'],
                0
            ),
            ppa_unit_cost=lambda df: np.where(
                df['carrier'] != 'Grid Imports',
                (1/(df['ci_load'] - df['grid_imports'] + df['grid_exports'])) * df['ppa_weighting'] * df['total_costs'],
                0
            ),
            export_unit_cost=lambda df: np.where(
                df['carrier'] == 'Grid Exports',
                (1/(df['ci_load'] - df['grid_imports'] + df['grid_exports'])) * df['ppa_weighting'] * df['export_revenue'],
                0
            )
        )
        .fillna(0)
        .assign(unit_cost_all_energy=lambda df: (df['capex'] + df['opex'] + df['import_cost'] + df['export_revenue'])/(df['ci_load'] + df['grid_exports'] + df['curtailment']))
        .assign(unit_cost_ci_energy=lambda df: (df['capex'] + df['opex'] + df['import_cost'] + df['export_revenue'])/df['ci_load'])
    )
        
    return unit_cost[['Node', 'carrier', 'capex', 'opex', 'import_cost', 'export_revenue', 'ppa_unit_cost', 'import_unit_cost', 'export_unit_cost', 'unit_cost_all_energy', 'unit_cost_ci_energy']]

def get_scenario_emission_intensity(n: pypsa.Network, bus: str, units='gCO2/kWh') -> float:
    """
    Calculate the overall emission intensity for a C&I scenario.
    
    Parameters:
    -----------
    n : pypsa.Network
        Solved PyPSA network
    bus : str
        Bus identifier (e.g., 'JPN01')
    units : str
        Units for emission intensity ('gCO2/kWh' or 'tCO2/MWh')
        
    Returns:
    --------
    float
        Emission intensity value
    """
    # Get grid emission intensity for each hour
    ci_parent_generators = n.generators[n.generators.index.str.contains(bus)]
    ci_parent_generators_t = n.generators_t.p[ci_parent_generators.index]
    ci_parent_load = 1/(n.loads_t.p.filter(regex=bus).filter(regex='^(?!.*C&I)'))
    
    # Calculate hourly grid emissions intensity (tCO2/MWh)
    grid_emissions = (
        (
            ci_parent_generators_t
            / ci_parent_generators.efficiency 
            * ci_parent_generators.carrier.map(n.carriers.co2_emissions)
        )
        .sum(axis=1)
    )
    grid_emissions_intensity = grid_emissions * ci_parent_load.squeeze()
    
    # Get C&I imports and calculate total emissions
    ci_imports = n.links_t.p0.filter(regex='C&I').filter(regex='Import').values.flatten()
    total_ci_emissions = (grid_emissions_intensity.values * ci_imports).sum()
    
    # Get total C&I load
    total_ci_load = n.loads_t.p.filter(regex='C&I').sum().sum()
    
    # Calculate emission intensity
    emission_intensity = total_ci_emissions / total_ci_load
    
    # Convert units if needed
    if units == 'gCO2/kWh':
        emission_intensity *= 1000  # tCO2/MWh -> gCO2/kWh
    
    return emission_intensity


def transform_visualiser_hourly_output(
        network: pypsa.Network,
        pypsa_run_id: str = 'Unspecified',
        scenario: str = 'Unspecified',
        market: str = 'Unspecified'
    ) -> pd.DataFrame:
    """
    Extracts hourly generation, storage, interconnector, and load data from a
    PyPSA network object, converts them to a long (tidy) format, splits identifier
    columns into Node, Type and Tech where applicable, adds time columns (Hour8760, day, Month, Year),
    sorts the data, and exports the merged DataFrame to CSV.
    
    Parameters
    ----------
    network : pypsa.Network
        A PyPSA network object.
    pypsa_run_id : str, optional
        Identifier for the PyPSA run. Defaults to 'Unspecified'.
    market : str, optional
        Market/region identifier. Defaults to 'Unspecified'.
    
    Returns
    -------
    pd.DataFrame
        The merged long format DataFrame with standardized columns.
    """
    # Get brownfield bus name
    ci_bus = network.buses[network.buses.index.str.contains('C&I')].index.str.split('C&I').str[0].str.strip()[0]

    generator_lookup = (network
                        .generators
                        .reset_index()[['Generator', 'bus', 'type']]
                        .rename(
                            columns={'bus': 'Node', 'type': 'Tech'})
                        )
    
    storage_lookup = (network
                      .storage_units
                      .reset_index()[['StorageUnit', 'bus', 'carrier']]
                      .rename(
                          columns={'bus': 'Node', 'carrier': 'Tech'})
                     )
    
    interconnector_lookup = (network
                             .links
                             .reset_index()[['Link', 'bus0', 'bus1']]
                             .rename(
                                 columns={'bus0': 'Node', 'bus1': 'Node_Destination'})
                            )


    # --- Extract hourly data and reset index ---
    # Hourly generation
    generation = (
        network
        .generators_t
        .p[network.generators[network.generators.p_nom_opt > 1e-2].index]
        .reset_index()
    )

    # Get a mask for carriers with nonzero and non-null CO2 emissions
    emitting_carriers = network.carriers.co2_emissions[network.carriers.co2_emissions != 0].dropna().index

    emitting_generators = network.generators[(network.generators.carrier.isin(emitting_carriers))
                                    & (network.generators.p_nom_opt > 1e-2)]

    emissions = (
        (
            network.generators_t.p[emitting_generators.index]
            / emitting_generators.efficiency
            * emitting_generators.carrier.map(network.carriers.co2_emissions)
        )
        .dropna(axis=1, thresh=5)
        .reset_index()
    )

    potential_dispatch = (
        (
            network.generators_t.p_max_pu
            * network.generators.p_nom_opt[network.generators[network.generators.p_nom_opt > 1e-2].index]
        )
    )

    # Hourly curtailment
    curtailment = potential_dispatch - network.generators_t.p[network.generators[network.generators.p_nom_opt > 1e-2].index]

    # Hourly curtailment percentage
    curtailment_percent = curtailment / potential_dispatch

    potential_dispatch = potential_dispatch.dropna(axis=1, thresh=1000).reset_index().fillna(0)
    curtailment = curtailment.dropna(axis=1, thresh=1000).reset_index().fillna(0)
    curtailment_percent = curtailment_percent.dropna(axis=1, thresh=1000).reset_index().fillna(0)

    # Hourly C&I import/export
    # Get average grid price
    grid_price = (
        network
        .buses_t
        .marginal_price
        [ci_bus]
                  )

    # Import/Export volumes and costs
    import_cost = (
        network
        .links_t
        .p0
        .filter(regex='C&I')
        .filter(regex='Import')
        .mul(grid_price, axis=0)
        .reset_index()
    )
    
    export_revenue = (
        network
        .links_t
        .p0
        .filter(regex='C&I')
        .filter(regex='Export')
        .mul(grid_price, axis=0)
        .mul(-1) # Negative because exports generate revenue
        .reset_index()
    )
    
    # Hourly loads (required)
    loads = (
        network
        .loads_t
        .p
        .reset_index()
    )

    # Hourly prices (required)
    prices = (
        network
        .buses_t
        .marginal_price
        .filter(regex='^(?!.*C&I)')
        .assign(ci_grid_price = lambda df: df.iloc[:, 1:].mean(axis=1))  
        .reset_index()
    )

    # Hourly storage (optional)
    try:
        storage = (
            network
            .storage_units_t
            .p[network.storage_units[network.storage_units.p_nom_opt > 1e-2].index]
            .reset_index()
        )
    except Exception as e:
        print(f"Storage component missing or failed to process: {e}")
        storage = None

    # Hourly interconnector flow (optional)
    try:
        interconnector_p0 = (
            network 
            .links_t
            .p0
            .reset_index()
        )
        interconnector_p1 = (
            network
            .links_t
            .p1
            .reset_index()
        )
    except Exception as e:
        print(f"Interconnector component missing or failed to process: {e}")
        interconnector_p0 = None
        interconnector_p1 = None

    # --- Convert wide to long format ---
    generation = pd.melt(
        generation,
        id_vars='snapshot',
        var_name='Generator', 
        value_name='Value'
    )

    potential_dispatch = pd.melt(
        potential_dispatch,
        id_vars='snapshot',
        var_name='Generator', 
        value_name='Value'
    )

    curtailment = pd.melt(
        curtailment,
        id_vars='snapshot',
        var_name='Generator', 
        value_name='Value'
    )
    
    curtailment_percent = pd.melt(
        curtailment_percent,
        id_vars='snapshot',
        var_name='Generator', 
        value_name='Value'
    )

    emissions = pd.melt(
        emissions,
        id_vars='snapshot',
        var_name='Generator', 
        value_name='Value'
    )


    if storage is not None:
        storage = pd.melt(
            storage, 
            id_vars='snapshot', 
            var_name='StorageUnit', 
            value_name='Value'
        )
    
    if interconnector_p0 is not None:
        interconnector_p0 = pd.melt(
            interconnector_p0, 
            id_vars='snapshot', 
            var_name='Link', 
            value_name='Value'
        )
    if interconnector_p1 is not None:
        interconnector_p1 = pd.melt(
            interconnector_p1, 
            id_vars='snapshot',
            var_name='Link', 
            value_name='Value'
        )

    loads = pd.melt(
        loads, 
        id_vars='snapshot', 
        var_name='Load', 
        value_name='Value'
    ).rename(columns={"Load": "Node"})

    prices = pd.melt(
        prices, 
        id_vars='snapshot', 
        var_name='Bus', 
        value_name='Value'
    ).rename(columns={"Bus": "Node"})

    import_cost = pd.melt(
        import_cost,
        id_vars='snapshot',
        var_name='Link', 
        value_name='Value'
    )

    export_revenue = pd.melt(
        export_revenue,
        id_vars='snapshot',
        var_name='Link', 
        value_name='Value'
    )
    
    # --- Create identifier columns: Node, Tech, Type ---
    generation = (pd.merge(
        generation,
        generator_lookup,
        on='Generator',
        how='left')
        .drop(columns='Generator')
        .groupby(['snapshot', 'Node', 'Tech'])
        .sum()
        .reset_index()
    )

    emissions = (pd.merge(
        emissions,
        generator_lookup,
        on='Generator',
        how='left')
        .drop(columns='Generator')
    )

    potential_dispatch = (pd.merge(
        potential_dispatch,
        generator_lookup,
        on='Generator',
        how='left')
        .drop(columns='Generator')
    )

    curtailment = (pd.merge(
        curtailment,
        generator_lookup,
        on='Generator',
        how='left')
        .drop(columns='Generator')
    )

    curtailment_percent = (pd.merge(
        curtailment_percent,
        generator_lookup,
        on='Generator',
        how='left')
        .drop(columns='Generator')
    )
    
    if storage is not None:
        storage = (pd.merge(
            storage,
            storage_lookup,
            on='StorageUnit',
            how='left')
            .drop(columns='StorageUnit')
            .groupby(['snapshot', 'Node', 'Tech'])
            .sum()
            .reset_index()
        )
    
    # Process interconnector flows if available
    if interconnector_p0 is not None:
        try:
            interconnector_p0 = pd.merge(
                interconnector_p0,
                interconnector_lookup,
                on='Link',
                how='left'
            )
        except Exception as e:
            print(f"Skipping interconnector_p0: {e}")
            interconnector_p0 = None

    if interconnector_p1 is not None:
        try:
            interconnector_p1 = pd.merge(
                interconnector_p1,
                interconnector_lookup,
                on='Link',
                how='left'
            ).rename(
                columns={'Node': 'Node_Destination', 'Node_Destination': 'Node'}
            )

        except Exception as e:
            print(f"Skipping interconnector_p1: {e}")
            interconnector_p1 = None

    # Concatenate interconnector DataFrames if at least one is available
    if interconnector_p0 is not None or interconnector_p1 is not None:
        interconnector = interconnector_by_nodes(interconnector_p0, interconnector_p1)
    else:
        interconnector = None

    # Update interconnector sign convention such export is negative and import is positive
    if interconnector is not None:
        interconnector['Value'] = interconnector['Value']*-1

    if import_cost is not None:
        try:
            import_cost = pd.merge(
                import_cost,
                interconnector_lookup,
                on='Link',
                how='left'
            ).rename(
                columns={'Node': 'Node_Destination', 'Node_Destination': 'Node'}
            ).drop(columns='Link')

        except Exception as e:
            print(f"Skipping import_cost: {e}")
            import_cost = None


    if export_revenue is not None:
        try:
            export_revenue = pd.merge(
                export_revenue,
                interconnector_lookup,
                on='Link',
                how='left'
            ).rename(
                columns={'Node': 'Node_Destination', 'Node_Destination': 'Node'}
            ).drop(columns='Link')

        except Exception as e:
            print(f"Skipping export_revenue: {e}")
            export_revenue = None

    # --- Calculate capacity factor ---
    optimal_capacity = (
        network
        .statistics
        .optimal_capacity(groupby=['bus', 'type'])
        .reset_index()
        .rename(columns={'bus':'Node', 'type': 'Tech',  0: 'OptimalCapacity'})
        .drop(columns='component')
    )

    capacity_factor_generator = pd.merge(
        generation,
        optimal_capacity,
        on=['Node', 'Tech'],
        how='left'
    )

    capacity_factor_storage = pd.merge(
        storage,
        optimal_capacity,
        on=['Node', 'Tech'],
        how='left'
    )

    capacity_factor_generator['Value']  = capacity_factor_generator['Value'] / capacity_factor_generator['OptimalCapacity']
    # Only consider positive values (discharge) for storage capacity factor
    capacity_factor_storage['Value']  = capacity_factor_storage['Value'].clip(lower=0) / capacity_factor_storage['OptimalCapacity']
    capacity_factor_generator = capacity_factor_generator[['snapshot', 'Node', 'Tech', 'Value']]
    capacity_factor_storage = capacity_factor_storage[['snapshot', 'Node', 'Tech', 'Value']]

    # --- Calculate residual demand ---

    # List of renewable technologies
    renewables = [
        'biomass-unspecified',
        'geothermal-unspecified',
        'hydro-unspecified',
        'offshorewind-unspecified',
        'onshorewind-unspecified',
        'solar-unspecified'
    ]

    # Filter the generation dataframe to keep only renewable tech
    renewable_generation = generation[generation['Tech'].isin(renewables)]

    renewable_generation = renewable_generation.drop(columns='Tech').groupby(['snapshot', 'Node']).sum().reset_index()

    residual_demand = pd.merge(
            loads,
            renewable_generation,
            on=['snapshot', 'Node'],
            how='left'
    )

    residual_demand['Value'] = residual_demand['Value_x'] - residual_demand['Value_y']
    residual_demand = residual_demand.drop(columns=['Value_x', 'Value_y'])

    # --- Assign Type column for standardization ---
    generation['Type'] = 'Generation'
    emissions['Type'] = 'Emissions'
    curtailment['Type'] = 'Curtailment'
    curtailment_percent['Type'] = 'CurtailmentPercent'
    potential_dispatch['Type'] = 'PotentialDispatch'
    import_cost['Type'] = 'ImportCost'
    export_revenue['Type'] = 'ExportRevenue'
    if storage is not None:
        storage['Type'] = 'Storage'
    if interconnector is not None:
        interconnector['Type'] = 'Interconnector'
    loads['Type'] = 'Demand'
    prices['Type'] = 'Price'
    capacity_factor_generator['Type'] = 'CapacityFactor'
    capacity_factor_storage['Type'] = 'CapacityFactor'
    residual_demand['Type'] = 'ResidualDemand'

    # --- Assign Tech column for interconnector ---
    if interconnector is not None:
        interconnector['Tech'] = 'Interconnector'

    # Assign demand to tech column for loads
    loads['Tech'] = 'Demand'

    # --- Concatenate all DataFrames ---
    dataframes = [generation, emissions, curtailment, curtailment_percent, potential_dispatch, import_cost, export_revenue,
                   loads, prices, capacity_factor_generator, capacity_factor_storage, residual_demand]
    if storage is not None:
        dataframes.append(storage)
    if interconnector is not None:
        dataframes.append(interconnector)
    
    merged_df = pd.concat(dataframes, ignore_index=True)

    # --- Add time columns ---
    merged_df['HourOfDay'] = merged_df['snapshot'].dt.hour
    merged_df['DayOfMonth'] = merged_df['snapshot'].dt.day   
    merged_df['Month'] = merged_df['snapshot'].dt.month
    merged_df['Year'] = merged_df['snapshot'].dt.year

    # # --- Add run identifier and market column ---
    merged_df['Market'] = market
    merged_df['Pypsa_Run_Id'] = pypsa_run_id
    merged_df['Scenario'] = scenario

    # --- Sort the DataFrame ---
    merged_df.sort_values(
        by=['snapshot', 'Node', 'Type'], 
        inplace=True, 
        ignore_index=True
    )

    # --- Add hour-of-year column (Hour8760) ---
    merged_df = add_hour_of_year_column(
        merged_df, 
        'snapshot', 
        'Hour8760'
    )

    # --- Map bus long names to the DataFrame ---
    buses_df = network.buses
    buses_df = buses_df.copy().dropna()[['long_name']].reset_index()
    all_codes = buses_df["Bus"].tolist()
    escaped_codes = [re.escape(code) for code in all_codes]
    pattern = "(" + "|".join(escaped_codes) + ")"
    merged_df['buscode'] = merged_df['Node'].str.extract(pattern, flags=re.IGNORECASE)
    merged_df['buscode'] = merged_df['buscode'].str.upper()

    merged_df = merged_df.merge(
        buses_df, 
        how='left', 
        left_on='buscode',
        right_on='Bus', 
    ).drop(columns=['buscode', 'Bus'])

    merged_df['BusType'] = np.where(
        merged_df['Node'].str.contains('C&I', na=False),
        'Greenfield',
        'Brownfield'
    )
    
    merged_df = merged_df.dropna(subset=['Value'], ignore_index=True)

    return merged_df

def transform_visualiser_yearly_output(
        network: pypsa.Network,
        pypsa_run_id: str = 'Unspecified',
        market: str = 'Unspecified',
        scenario: str = 'Unspecified'
    ) -> pd.DataFrame:
    """
    Extracts yearly statistics from a PyPSA network object, converts them to a long format,
    and adds run identifier and market columns.
    
    Parameters
    ----------
    network : pypsa.Network
        A PyPSA network object.
    
    Returns
    -------
    pd.DataFrame
        The merged long format DataFrame.
    """
    # Extract statistics output into a df
    df = network.statistics(groupby=['bus', 'name', 'carrier'])

    year = network.snapshots.year[0]

    # Reset the index to convert MultiIndex to columns
    df = (df
          .reset_index()
          .rename(columns=
                  {'level_0': 'Type',
                   'level_1': 'Bus',
                   'level_2': 'Name', # Non-standardised format across different market thus include it as full name for now
                   'level_3': 'Tech',
                   }
                   )
    )

    df['Vintage'] = np.where(
        df['Name'].str.contains('exo|endo', na=False),
        df['Name'].str.split('-', n=2).str[-1],
        np.nan
    )

    # Convert the df from wide to long format
    df = pd.melt(
        df,
        id_vars=['Type', 'Bus', 'Name', 'Tech', 'Vintage'],
        var_name='Metric',
        value_name='Value'
    )

    expanded_capacity = (network
                        .statistics
                        .expanded_capacity(groupby=['bus', 'name', 'carrier'])
                        .reset_index()
                        .rename(columns={'component': 'Type', 'bus': 'Bus', 'name': 'Name', 'carrier': 'Tech', 0: 'Value'})
    )

    expanded_capacity['Vintage'] = np.where(
        expanded_capacity['Name'].str.contains('exo|endo', na=False),
        expanded_capacity['Name'].str.split('-', n=2).str[-1],
        np.nan
    )

    expanded_capacity['Metric'] = 'Expanded Capacity'

    generator_p_nom_max = (
        network
        .generators
        .loc[network.generators['p_nom_extendable']]
        .reset_index()
        .replace(float('inf'), np.nan)
        .rename(columns={'Generator': 'Name', 'bus': 'Bus', 'carrier': 'Tech', 'p_nom_max': 'Value'})
        [['Name', 'Bus', 'Tech', 'Value']]
    )

    storage_p_nom_max = (
                network
                .storage_units
                .loc[network.storage_units['p_nom_extendable']]
                .reset_index()
                .replace(float('inf'), np.nan)
                .rename(columns={'StorageUnit': 'Name', 'bus': 'Bus', 'carrier': 'Tech', 'p_nom_max': 'Value'})
                [['Name', 'Bus', 'Tech', 'Value']]
    )


    storage_p_nom_max = storage_p_nom_max.where(~storage_p_nom_max.isin([float('inf'), -float('inf')]), 0)

    link_p_nom_max = (
                network
                .links
                .loc[network.links['p_nom_extendable']]
                .reset_index()
                .replace(float('inf'), np.nan)
                .rename(columns={'Link': 'Name', 'bus0': 'Bus', 'carrier': 'Tech', 'p_nom_max': 'Value'})
                [['Name', 'Bus', 'Tech', 'Value']]
    )

    link_p_nom_max = link_p_nom_max.where(~link_p_nom_max.isin([float('inf'), -float('inf')]), 0)

    generator_p_nom_max['Type'] = 'Generator'
    storage_p_nom_max['Type'] = 'StorageUnit'
    link_p_nom_max['Type'] = 'Link'

    p_nom_max = pd.concat([generator_p_nom_max, storage_p_nom_max, link_p_nom_max], ignore_index=True)

    p_nom_max['Vintage'] = np.where(
        p_nom_max['Name'].str.contains('exo|endo', na=False),
        p_nom_max['Name'].str.split('-', n=2).str[-1],
        np.nan
    )

    p_nom_max['Metric'] = 'p_nom_max'

    # Calculate ratio between expanded capacity and p_nom_max
    agg_p_nom_max = p_nom_max[['Type','Bus', 'Tech', 'Value']].groupby(['Type','Bus', 'Tech']).sum().reset_index()
    agg_expanded_capacity = expanded_capacity[['Type','Bus', 'Tech', 'Value']].groupby(['Type','Bus', 'Tech']).sum().reset_index()

    newbuild_contraints_ratio = pd.merge(agg_expanded_capacity, agg_p_nom_max, on=['Type','Bus', 'Tech'], how='left', suffixes=('_expanded_capacity', '_p_nom_max'))
    newbuild_contraints_ratio['Value'] = newbuild_contraints_ratio['Value_expanded_capacity'] / newbuild_contraints_ratio['Value_p_nom_max']
    newbuild_contraints_ratio = newbuild_contraints_ratio[['Type', 'Bus', 'Tech', 'Value']]
    
    newbuild_contraints_ratio['Metric'] = 'Newbuild Constraints Ratio'

    cost_breakdown = get_ci_unit_cost(network)

    cost_breakdown = pd.melt(
        cost_breakdown,
        id_vars=['Node', 'carrier'],
        var_name='Metric',
        value_name='Value'
    ).rename(columns={'Node': 'Bus', 'carrier': 'Tech'})
    
    df = pd.concat([df, expanded_capacity, p_nom_max, newbuild_contraints_ratio, cost_breakdown], ignore_index=True)

    df['BusType'] = np.where(
    df['Bus'].str.contains('C&I', na=False),
    'Greenfield',
    'Brownfield'
    )

    # # Add the run identifier and market column
    df['Market'] = market
    df['Pypsa_Run_Id'] = pypsa_run_id
    df['Scenario'] = scenario
    df['Year'] = year

    df = df.dropna(subset=['Value'], ignore_index=True)

    # Add emission intensity rows for buses with C&I loads
    ci_buses = network.loads.loc[network.loads.index.str.contains('C&I', na=False), 'bus'].unique()
    
    emission_intensity_rows = []
    for bus in ci_buses:
        # Extract the base bus name (e.g., 'JPN01' from 'JPN01 C&I Grid')
        base_bus = bus.replace(' C&I Grid', '').replace(' C&I', '')
        
        try:
            emission_intensity = get_scenario_emission_intensity(network, base_bus, units='gCO2/kWh')
            
            emission_intensity_rows.append({
                'Type': np.nan,
                'Bus': f'{base_bus} C&I',
                'Name': np.nan,
                'Tech': np.nan,
                'Vintage': np.nan,
                'Metric': 'EmissionIntensity',
                'Value': emission_intensity,
                'BusType': 'Greenfield',  # Since this relates to C&I
                'Market': market,
                'Pypsa_Run_Id': pypsa_run_id,
                'Scenario': scenario,
                'Year': year
            })
        except Exception as e:
            print(f"Warning: Could not calculate emission intensity for bus {base_bus}: {e}")
    
    # Add emission intensity rows to the dataframe
    if emission_intensity_rows:
        emission_intensity_df = pd.DataFrame(emission_intensity_rows)
        df = pd.concat([df, emission_intensity_df], ignore_index=True)

    return df

def compute_relative_costs(
        yearly_df: pd.DataFrame, 
        market: str, 
        pypsa_run_id: str,
    ) -> pd.DataFrame:
    """
    Compute relative CAPEX and OPEX values for each scenario and technology,
    using 'brownfield_2030' as baseline. Returns a DataFrame with columns:
    [Metric, Scenario, Tech, Value, Market, Pypsa_Run_Id], where Metric is
    renamed to RelativeSystemCapex/Opex.
    """
    # Filter and group
    sys_cost = (
        yearly_df[
            yearly_df['Metric'].isin(['Capital Expenditure', 'Operational Expenditure'])
        ]
        .groupby(['Metric', 'Scenario', 'Tech'])
        .sum()[['Value']]
    )

    # Extract baseline series for 'brownfield_2030'
    baseline = sys_cost.xs('brownfield_2030', level='Scenario')['Value']

    # Map baseline to each row and adjust
    metrics = sys_cost.index.get_level_values('Metric')
    techs   = sys_cost.index.get_level_values('Tech')
    adjusted = [baseline.loc[(m, t)] for m, t in zip(metrics, techs)]
    sys_cost['Value'] = sys_cost['Value'] - adjusted

    # Reset index, rename, and add metadata columns
    sys_cost = sys_cost.reset_index()
    sys_cost['Metric'] = sys_cost['Metric'].map({
        'Capital Expenditure': 'RelativeSystemCapex',
        'Operational Expenditure': 'RelativeSystemOpex'
    })
    sys_cost['Market'] = market
    sys_cost['Pypsa_Run_Id'] = pypsa_run_id

    yearly_df = pd.concat([yearly_df, sys_cost], ignore_index=True)

    return yearly_df


def process_solved_networks_directory(
        base_path: str,
        pattern: str = "JPN_P1_JPN*",
        network_dir: str = "solved_networks"
    ) -> tuple[dict, dict]:
    """
    Process all .nc files in the solved_networks directories matching the pattern
    and concatenate them into separate hourly and yearly dataframes per directory.

    Parameters
    ----------
    base_path : str
        Base directory path containing the run folders
    pattern : str, optional
        Pattern to match subdirectories, defaults to "JPN_P1_JPN*"
    network_dir : str, optional
        Name of directory containing network files, defaults to "solved_networks"

    Returns
    -------
    tuple[dict, dict]
        Two dictionaries containing the hourly and yearly DataFrames respectively,
        with directory names as keys
    """

    hourly_results = {}
    yearly_results = {}
    
    # Find all matching directories
    for dir_path in glob.glob(os.path.join(base_path, pattern)):
        dir_name = os.path.basename(dir_path)
        network_path = os.path.join(dir_path, network_dir)
        
        if not os.path.exists(network_path):
            print(f"Skipping {dir_name}: {network_dir} directory not found")
            continue
            
        # Find all .nc files in the solved_networks directory
        nc_files = glob.glob(os.path.join(network_path, "*.nc"))
        
        if not nc_files:
            print(f"No .nc files found in {network_path}")
            continue
            
        print(f"Processing {len(nc_files)} files in {dir_name}")
        
        # Process each .nc file and collect DataFrames
        hourly_dfs = []
        yearly_dfs = []
        
        for nc_file in nc_files:
            try:
                # Load network
                network = pypsa.Network()
                network.import_from_netcdf(nc_file)
                
                # Get filename without extension for run_id
                run_id = Path(nc_file).stem
                
                # Process hourly and yearly data
                hourly_df = transform_visualiser_hourly_output(
                    network=network,
                    pypsa_run_id=run_id,
                    market=dir_name
                )
                
                yearly_df = transform_visualiser_yearly_output(
                    network=network,
                    pypsa_run_id=run_id,
                    market=dir_name
                )
                
                hourly_dfs.append(hourly_df)
                yearly_dfs.append(yearly_df)
                
            except Exception as e:
                print(f"Error processing {nc_file}: {str(e)}")
                continue
        
        if hourly_dfs:
            # Store concatenated DataFrames separately for hourly and yearly data
            hourly_results[dir_name] = pd.concat(hourly_dfs, ignore_index=True)
            yearly_results[dir_name] = pd.concat(yearly_dfs, ignore_index=True)
            print(f"Successfully processed {dir_name}")
        else:
            print(f"No valid data processed for {dir_name}")
    
    return hourly_results, yearly_results

def process_and_save_networks_by_directory(
        base_path: str,
        output_base_path: str,
        pattern: str = "JPN_P1_JPN*",
        network_dir: str = "solved_networks",
        pypsa_run_id: str = 'Unspecified'
    ) -> None:
    """
    Process all .nc files in each solved_networks directory one at a time and
    save results to CSV immediately after processing each directory.

    Parameters
    ----------
    base_path : str
        Base directory path containing the run folders
    output_base_path : str
        Base path where to save the output CSV files
    pattern : str, optional
        Pattern to match subdirectories, defaults to "JPN_P1_JPN*"
    network_dir : str, optional
        Name of directory containing network files, defaults to "solved_networks"
    """

    # Create output directories
    hourly_path = os.path.join(output_base_path, "hourly")
    yearly_path = os.path.join(output_base_path, "yearly")
    os.makedirs(hourly_path, exist_ok=True)
    os.makedirs(yearly_path, exist_ok=True)
    
    # Process each directory one at a time
    for dir_path in glob.glob(os.path.join(base_path, pattern)):
        dir_name = os.path.basename(dir_path)
        network_path = os.path.join(dir_path, network_dir)
        
        if not os.path.exists(network_path):
            print(f"Skipping {dir_name}: {network_dir} directory not found")
            continue
            
        # Find all .nc files in the solved_networks directory
        nc_files = glob.glob(os.path.join(network_path, "*.nc"))
        
        if not nc_files:
            print(f"No .nc files found in {network_path}")
            continue
            
        print(f"Processing {len(nc_files)} files in {dir_name}")
        
        # Process each .nc file and collect DataFrames
        hourly_dfs = []
        yearly_dfs = []
        
        for nc_file in nc_files:
            try:
                # Load network
                network = pypsa.Network()
                network.import_from_netcdf(nc_file)
                
                # Get filename without extension for run_id
                scenario_id = Path(nc_file).stem
                
                # Process hourly and yearly data
                hourly_df = transform_visualiser_hourly_output(
                    network=network,
                    pypsa_run_id=pypsa_run_id,
                    scenario=scenario_id,
                    market=dir_name
                )
                
                yearly_df = transform_visualiser_yearly_output(
                    network=network,
                    pypsa_run_id=pypsa_run_id,
                    scenario=scenario_id,
                    market=dir_name
                )
                
                hourly_dfs.append(hourly_df)
                yearly_dfs.append(yearly_df)
                
                # Clean up to free memory
                del network
                gc.collect()
                
            except Exception as e:
                print(f"Error processing {nc_file}: {str(e)}")
                continue
        
        if hourly_dfs:
            # Concatenate and save results for this directory immediately
            hourly_output = pd.concat(hourly_dfs, ignore_index=True)
            yearly_output = pd.concat(yearly_dfs, ignore_index=True)

            # Compute relative costs and add to yearly output
            yearly_output = compute_relative_costs(yearly_output, market=dir_name, pypsa_run_id=pypsa_run_id)

            # Save to CSV
            hourly_output.to_csv(os.path.join(hourly_path, f"{dir_name}_hourly.csv"), index=False)
            yearly_output.to_csv(os.path.join(yearly_path, f"{dir_name}_yearly.csv"), index=False)
            
            print(f"Successfully processed and saved results for {dir_name}")
            
            # Clean up to free memory
            del hourly_dfs, yearly_dfs, hourly_output, yearly_output
            gc.collect()
        else:
            print(f"No valid data processed for {dir_name}")


# def process_and_save_networks_by_directory_emission_intensity(
#         base_path: str,
#         output_base_path: str,
#         pattern: str = "JPN_P1_JPN*",
#         network_dir: str = "solved_networks",
#     ) -> None:
#     """
#     Process all .nc files in each solved_networks directory one at a time and
#     save results to CSV immediately after processing each directory.

#     Parameters
#     ----------
#     base_path : str
#         Base directory path containing the run folders
#     output_base_path : str
#         Base path where to save the output CSV files
#     pattern : str, optional
#         Pattern to match subdirectories, defaults to "JPN_P1_JPN*"
#     network_dir : str, optional
#         Name of directory containing network files, defaults to "solved_networks"
#     """

#     # Create output directories
#     hourly_path = os.path.join(output_base_path, "hourly")
#     os.makedirs(hourly_path, exist_ok=True)
    
#     # Process each directory one at a time
#     for dir_path in glob.glob(os.path.join(base_path, pattern)):
#         dir_name = os.path.basename(dir_path)
#         network_path = os.path.join(dir_path, network_dir)
        
#         if not os.path.exists(network_path):
#             print(f"Skipping {dir_name}: {network_dir} directory not found")
#             continue
            
#         # Find all .nc files in the solved_networks directory
#         nc_files = glob.glob(os.path.join(network_path, "*.nc"))
        
#         if not nc_files:
#             print(f"No .nc files found in {network_path}")
#             continue
            
#         print(f"Processing {len(nc_files)} files in {dir_name}")
        
#         # Process each .nc file and collect DataFrames
#         emission_dfs = []
        
#         for nc_file in nc_files:
#             try:
#                 # Load network
#                 network = pypsa.Network()
#                 network.import_from_netcdf(nc_file)
                
#                 # Get filename without extension for run_id
#                 scenario_id = Path(nc_file).stem
                
#                 # Compute emissions intensity (hourly)
#                 # You may want to loop over all relevant CI nodes; here we use the last 5 chars as bus name
#                 bus_name = dir_name[-5:]  # e.g., 'JPN01'
#                 ci_emissions_intensity = get_scenario_emission_intensity(network, bus_name, units='tCO2/MWh')
#                 # If ci_emissions_intensity is a Series, convert to DataFrame
#                 import_series = network.links_t.p0.filter(regex='C&I').filter(regex='Import').sum(axis=1)
#                 ci_load_series = network.loads_t.p.filter(regex='C&I').sum(axis=1)
#                 # Build DataFrame with aligned time series
#                 df = pd.DataFrame({
#                     'snapshot': ci_emissions_intensity.index,
#                     'emissions_intensity': ci_emissions_intensity.values,
#                     'import': import_series.values,
#                     'ci_load': ci_load_series.values,
#                     'scenario': scenario_id,
#                 })
#                 emission_dfs.append(df)
                
#                 # Clean up
#                 del network
#                 gc.collect()
                
#             except Exception as e:
#                 print(f"Error processing {nc_file}: {str(e)}")
#                 continue
        
#         if emission_dfs:
#             # Concatenate and save results for this directory immediately
#             emission_output = pd.concat(emission_dfs, ignore_index=True)
#             emission_output.to_csv(os.path.join(hourly_path, f"{dir_name}_ci_emission_intensity.csv"), index=False)
#             print(f"Successfully processed and saved CI emission intensity for {dir_name}")
#             del emission_dfs, emission_output
#             gc.collect()
#         else:
#             print(f"No valid data processed for {dir_name}")

