import pypsa

import pandas as pd


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
        .melt(id_vars='timestep', var_name='bus', value_name='load')
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

def prompt_market():
    """
    Prompts the user to enter a market/country/region for this Pypsa run.
    Returns:
        str: The user-entered market/country/region.
    """
    prompt_message = (
        "Please enter the market/country/region for this Pypsa run.\n"
        "Examples: 'ASEAN, Japan, Taiwan, Indonesia, etc'\n"
    )

    print(prompt_message, end='')
    market = input(prompt_message)
    print(f"You entered: {market}")
    return market

def prompt_pypsa_run_identifier():
    """
    Prompts the user to enter a run identifier.
    Returns:
        str: The user-entered run number or any relevant comments.
    """
    prompt_message = (
        "Please enter the run identifier.\n"
        "Examples: '1, first-run, run-with-policy-constraint, etc'\n"
    )

    print(prompt_message, end='')
    run_identifier = input()
    print(f"You entered: {run_identifier}")
    return run_identifier

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

def transform_visualiser_hourly_output(
        network: pypsa.Network
    ):
    """
    Extracts hourly generation, storage, interconnector, and load data from a
    PyPSA network object, converts them to a long (tidy) format, splits identifier
    columns into Node, Type and Tech where applicable, adds time columns (Hour8760, day, Month, Year),
    sorts the data, and exports the merged DataFrame to CSV.
    
    Parameters
    ----------
    network : pypsa.Network
        A PyPSA network object.
    filename : str
        The name of the file to save the merged DataFrame; must end with .csv.
    
    Returns
    -------
    csv file
        The merged long format DataFrame saved as a CSV file.
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
    generation = pd.merge(
        generation,
        generator_lookup,
        on='Generator',
        how='left'
        ).drop(columns='Generator')

    if storage is not None:
        storage = pd.merge(
            storage,
            storage_lookup,
            on='StorageUnit',
            how='left'
        ).drop(columns='StorageUnit')
    
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

    # --- Assign Type column for standardization ---
    generation['Type'] = 'Generation'
    if storage is not None:
        storage['Type'] = 'Storage'
    if interconnector is not None:
        interconnector['Type'] = 'Interconnector'
    loads['Type'] = 'Demand'
    prices['Type'] = 'Price'

    # --- Assign Tech column for interconnector ---
    if interconnector is not None:
        interconnector['Tech'] = 'Interconnector'

    # Assign demand to tech column for loads
    loads['Tech'] = 'Demand'

    # --- Concatenate all DataFrames ---
    dataframes = [generation, loads, prices]
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

    # --- Add run identifier and market column ---
    merged_df['Market'] = prompt_market()
    merged_df['Pypsa_Run_Id'] = prompt_pypsa_run_identifier()

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
    try:    
        buses_long_name = network.buses.long_name
        merged_df = merged_df.merge(
            buses_long_name, 
            how='left', 
            left_on='Node', 
            right_index=True
        )
    
    except Exception as e:
        print(f"Bus long names not found: {e}")
        
    return merged_df

def transform_visualiser_yearly_output(
        network: pypsa.Network
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
                   'level_2': 'Bus_Tech_Vintage', # Non-standardised format across different market thus include it as full name for now
                   'level_3': 'Tech',
                   }
                   )
    )

    # Convert the df from wide to long format
    df = pd.melt(
        df,
        id_vars=['Type', 'Bus', 'Bus_Tech_Vintage', 'Tech'],
        var_name='Metric',
        value_name='Value'
    )

    # Add the run identifier and market column
    df['Market'] = prompt_market()
    df['Pypsa_Run_Id'] = prompt_pypsa_run_identifier()
    df['Year'] = year

    return df