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
        .droplevel(0).resample(resample)
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
    generation_monthly = network.generators_t.p.droplevel(0).resample('ME').sum()
    p_by_carrier = network.generators_t.p.groupby(network.generators.type, axis=1).sum()
    p_by_carrier_monthly = network.generators_t.p.groupby(network.generators.type, axis=1).sum().droplevel(0).resample('ME').sum()
    interconnector_hourly = network.links_t.p0
    interconnector_monthly = network.links_t.p0.droplevel(0).resample('ME').sum()
    statistics = network.statistics()
    loads = network.loads_t.p.droplevel(0).resample('ME').sum()
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
        p_by_carrier.to_excel(writer, sheet_name='Generation by carrier (hr)')
        p_by_carrier_monthly.to_excel(writer, sheet_name='Generation by carrier (m)')
        interconnector_hourly.to_excel(writer, sheet_name='Interconnector flow (hr)')
        interconnector_monthly.to_excel(writer, sheet_name='Interconnector flow (m)')

def split_and_assign(df, column, new_columns, indices, num_splits=2, delimiter="-"):
    """
    Splits the specified column in the DataFrame by a delimiter and assigns
    selected parts to new columns.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame containing the column to be split.
    column : str
        The name of the column to split.
    new_columns : list of str
        The list of new column names to be created.
    indices : list of int
        The indices corresponding to the split parts to assign to each new column.
        For example, if you want to assign the first and second parts, use [0, 1].
    num_splits : int, optional
        The maximum number of splits to perform (default is 2).
    delimiter : str, optional
        The delimiter to use for splitting (default is "-").

    Returns
    -------
    pandas.DataFrame
        The DataFrame with the new columns added.
    """
    splits = df[column].str.split(delimiter, n=num_splits, expand=True)
    for new_col, idx in zip(new_columns, indices):
        df[new_col] = splits[idx]
    df = df.drop(columns=[column])
    return df

def export_long_format(n, output_file, file_format):
    """
    Extracts hourly generation, storage, interconnector, and load data from a
    PyPSA network object, converts them to a long (tidy) format, splits identifier
    columns into node and tech where applicable, adds time columns (Hour, Month, Year),
    sorts the data, and exports the merged DataFrame to Excel or CSV.

    Parameters
    ----------
    n : pypsa.Network
        A PyPSA network object.
    output_file : str, optional
        The file path to export the data. Default is 'sampleoutput.xlsx'.
    file_format : str, optional
        The file format to export ('excel' or 'csv'). Default is 'excel'.

    Returns
    -------
    pandas.DataFrame
        The merged long format DataFrame.
    """
    # Extract hourly data and reset index
    generation_hourly = n.generators_t.p.droplevel(0).reset_index()
    storage_hourly = n.storage_units_t.p.droplevel(0).reset_index()
    interconnector_hourly = n.links_t.p0.droplevel(0).reset_index()
    loads_hourly = n.loads_t.p.droplevel(0).reset_index()

    # Convert wide to long format
    generation_long = pd.melt(generation_hourly, id_vars='timestep', 
                              var_name='Generator', value_name='Value')
    storage_long = pd.melt(storage_hourly, id_vars='timestep', 
                           var_name='StorageUnit', value_name='Value')
    interconnector_long = pd.melt(interconnector_hourly, id_vars='timestep', 
                                  var_name='Link', value_name='Value')
    loads_long = pd.melt(loads_hourly, id_vars='timestep', 
                         var_name='Load', value_name='Value')

    # Assign type column
    generation_long['type'] = 'Generation'
    storage_long['type'] = 'Storage'
    interconnector_long['type'] = 'Interconnector'
    loads_long['type'] = 'Demand'

    # Split 'Generator' and 'StorageUnit' columns into 'node' and 'tech'
    generation_long = split_and_assign(generation_long, "Generator", ["node", "tech"], [0, 1], num_splits=2, delimiter="-")
    storage_long = split_and_assign(storage_long, "StorageUnit", ["node", "tech"], [0, 1], num_splits=2, delimiter="-")

    # For loads, rename the column to 'node' since that's the identifier
    loads_long.rename(columns={"Load": "node"}, inplace=True)

    # Concatenate the long DataFrames (excluding interconnector if not needed; add as desired)
    merged_df = pd.concat([generation_long, storage_long, loads_long], ignore_index=True)

    # Add time columns
    merged_df['Hour'] = merged_df['timestep'].dt.hour
    merged_df['Month'] = merged_df['timestep'].dt.month
    merged_df['Year'] = merged_df['timestep'].dt.year

    # Sort the DataFrame
    merged_df.sort_values(by=['timestep', 'type', 'node'], inplace=True)

    # Export to Excel or CSV
    if file_format.lower() == 'excel':
        merged_df.to_excel(output_file, index=False)
    elif file_format.lower() == 'csv':
        merged_df.to_csv(output_file, index=False)
    else:
        raise ValueError("Unsupported file_format. Please use 'excel' or 'csv'.")

    return merged_df