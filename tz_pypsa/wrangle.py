import pypsa

import pandas as pd



def get_backstop_generation_by_bus(
        network : pypsa.Network
):
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

    """
    Get the load by bus for a given network and time period.

    Parameters:
        network (pypsa.Network): The PyPSA network object.
        resample (str, optional): The resampling frequency for the load data. Defaults to 'YE' (yearly).
        period (int, optional): The time period for which to retrieve the load data. Defaults to 2023.
        mul (float, optional): The multiplier to apply to the load data. Defaults to 1e3.

    Returns:
        pd.DataFrame: A DataFrame containing the load data by bus, resampled and scaled.

    """
    return (
        network
        .loads_t
        .p_set
        .loc[period]
        .resample(resample)
        .sum()
        .div(mul)
        .reset_index()
        .melt(id_vars='timestep', var_name='bus', value_name='load')
    )


def export_to_excel(network, filename):
    """
    Export network components and statistics to an Excel file.

    Parameters:
        network (pypsa.Network): The PyPSA network object.
        filename (str): The name of the Excel file to be created.

    Returns:
        None
    """
    
    # Convert network components to DataFrames
    nodes = network.buses
    generators = network.generators
    links = network.links
    generation_hourly = network.generators_t.p
    generation_monthly = network.generators_t.p.resample('ME').sum()
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
        p_by_carrier.to_excel(writer, sheet_name='Generation by carrier (hr)')
        p_by_carrier_monthly.to_excel(writer, sheet_name='Generation by carrier (m)')
        interconnector_hourly.to_excel(writer, sheet_name='Interconnector flow (hr)')
        interconnector_monthly.to_excel(writer, sheet_name='Interconnector flow (m)')