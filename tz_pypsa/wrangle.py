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


# def prompt_market():
#     """
#     Prompts the user to enter a market/country/region for this Pypsa run.
#     Returns:
#         str: The user-entered market/country/region.
#     """
#     prompt_message = (
#         "Please enter the market/country/region for this Pypsa run.\n"
#         "Examples: 'ASEAN, Japan, Taiwan, Indonesia, etc'\n"
#     )

#     print(prompt_message, end='')
#     market = input(prompt_message)
#     print(f"You entered: {market}")
#     return market

# def prompt_pypsa_run_identifier():
#     """
#     Prompts the user to enter a run identifier.
#     Returns:
#         str: The user-entered run number or any relevant comments.
#     """
#     prompt_message = (
#         "Please enter the run identifier.\n"
#         "Examples: '1, first-run, run-with-policy-constraint, etc'\n"
#     )

#     print(prompt_message, end='')
#     run_identifier = input()
#     print(f"You entered: {run_identifier}")
#     return run_identifier

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

def transform_visualiser_hourly_output(
        network: pypsa.Network,
        pypsa_run_id: str = 'Unspecified',
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
    generator_lookup = (network
                        .generators
                        .reset_index()[['Generator', 'bus', 'type']]
                        .rename(
                            columns={'bus': 'Node', 'type': 'Tech'})
                        )
    
    storage_lookup = (network
                      .storage_units
                      .reset_index()[['StorageUnit', 'bus', 'type']]
                      .rename(
                          columns={'bus': 'Node', 'type': 'Tech'})
                     )
    
    interconnector_lookup = (network
                             .links
                             .reset_index()[['Link', 'bus0', 'bus1']]
                             .rename(
                                 columns={'bus0': 'Node', 'bus1': 'Node_Destination'})
                            )


    # --- Extract hourly data and reset index ---
    # Hourly generation (required)
    generation = (
        network
        .generators_t
        .p
        .reset_index()
    )

    emissions = (
        (
            network.generators_t.p 
            / network.generators.efficiency 
            * network.generators.carrier.map(network.carriers.co2_emissions)
        )
        .dropna(axis=1, thresh=5)
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
        .reset_index()
    )

    # Hourly storage (optional)
    try:
        storage = (
            network
            .storage_units_t
            .p
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
    capacity_factor_storage['Value']  = abs(capacity_factor_storage['Value'] / capacity_factor_storage['OptimalCapacity'])
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
    dataframes = [generation, emissions, loads, prices, capacity_factor_generator, capacity_factor_storage, residual_demand]
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
        market: str = 'Unspecified'
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
    df = network.statistics(groupby=['bus', 'name', 'type'])

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
                        .expanded_capacity(groupby=['bus', 'name', 'type'])
                        .reset_index()
                        .rename(columns={'component': 'Type', 'bus': 'Bus', 'name': 'Name', 'type': 'Tech', 0: 'Value'})
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
        .rename(columns={'Generator': 'Name', 'bus': 'Bus', 'type': 'Tech', 'p_nom_max': 'Value'})
        [['Name', 'Bus', 'Tech', 'Value']]
    )

    storage_p_nom_max = (
                network
                .storage_units
                .loc[network.storage_units['p_nom_extendable']]
                .reset_index()
                .rename(columns={'StorageUnit': 'Name', 'bus': 'Bus', 'type': 'Tech', 'p_nom_max': 'Value'})
                [['Name', 'Bus', 'Tech', 'Value']]
    )


    storage_p_nom_max = storage_p_nom_max.where(~storage_p_nom_max.isin([float('inf'), -float('inf')]), 0)

    link_p_nom_max = (
                network
                .links
                .loc[network.links['p_nom_extendable']]
                .reset_index()
                .rename(columns={'Link': 'Name', 'bus0': 'Bus', 'type': 'Tech', 'p_nom_max': 'Value'})
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

    df = pd.concat([df, expanded_capacity, p_nom_max, newbuild_contraints_ratio], ignore_index=True)

    df['BusType'] = np.where(
    df['Bus'].str.contains('C&I', na=False),
    'Greenfield',
    'Brownfield'
    )

    # # Add the run identifier and market column
    df['Market'] = market
    df['Pypsa_Run_Id'] = pypsa_run_id
    df['Year'] = year

    df = df.dropna(subset=['Value'], ignore_index=True)

    return df

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

def save_processed_results(
        results: tuple[dict, dict],
        output_base_path: str,
        file_format: str = 'parquet'
    ) -> None:
    """
    Save the processed hourly and yearly results to files.

    Parameters
    ----------
    results : tuple[dict, dict]
        Tuple containing two dictionaries with the hourly and yearly DataFrames
    output_base_path : str
        Base path where to save the output files
    file_format : str, optional
        Format to save the files in ('parquet' or 'csv'), defaults to 'parquet'
    """
    os.makedirs(output_base_path, exist_ok=True)
    hourly_results, yearly_results = results
    
    # Save hourly results
    hourly_path = os.path.join(output_base_path, "hourly")
    os.makedirs(hourly_path, exist_ok=True)
    for name, df in hourly_results.items():
        output_path = os.path.join(hourly_path, name)
        if file_format.lower() == 'parquet':
            df.to_parquet(f"{output_path}.parquet")
        else:
            df.to_csv(f"{output_path}.csv", index=False)
        print(f"Saved hourly data for {name} to {output_path}.{file_format}")
    
    # Save yearly results
    yearly_path = os.path.join(output_base_path, "yearly")
    os.makedirs(yearly_path, exist_ok=True)
    for name, df in yearly_results.items():
        output_path = os.path.join(yearly_path, name)
        if file_format.lower() == 'parquet':
            df.to_parquet(f"{output_path}.parquet")
        else:
            df.to_csv(f"{output_path}.csv", index=False)
        print(f"Saved yearly data for {name} to {output_path}.{file_format}")

def process_and_save_networks_by_directory(
        base_path: str,
        output_base_path: str,
        pattern: str = "JPN_P1_JPN*",
        network_dir: str = "solved_networks"
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
    import os
    import glob
    from pathlib import Path
    import gc  # For garbage collection

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
            
            # Save to CSV
            hourly_output.to_csv(os.path.join(hourly_path, f"{dir_name}_hourly.csv"), index=False)
            yearly_output.to_csv(os.path.join(yearly_path, f"{dir_name}_yearly.csv"), index=False)
            
            print(f"Successfully processed and saved results for {dir_name}")
            
            # Clean up to free memory
            del hourly_dfs, yearly_dfs, hourly_output, yearly_output
            gc.collect()
        else:
            print(f"No valid data processed for {dir_name}")

