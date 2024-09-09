import pypsa

import numpy as np
import pandas as pd
import xarray as xr

from .constraints import (
    constr_cumulative_p_nom,
    constr_bus_self_sufficiency,
)

from .helpers import (
    haversine,
)

import warnings
warnings.filterwarnings("ignore")

def build_pypsa_network(
        model : dict,
        timeseries : xr.Dataset,
        costs : pd.DataFrame,
        years : list = None,
        select_nodes : list = None,
        frequency : str = None,
        backstop : bool = False,
        set_global_constraints : bool = False,
        **kwargs,
):
    
    '''
    Build a PyPSA network from input data.
    
    Parameters
    ----------

    model : dict
        The model dictionary containing the network configuration.
    timeseries : xr.Dataset
        The time series data for the network.
    costs : pd.DataFrame
        The cost data for the network.
    years : list, optional
        The list of years for multi-year investment (default is None).
    select_nodes : list, optional
        The list of nodes to select for the network (default is None).
    frequency : str, optional
        The frequency of the time series data (default is None).
    backstop : bool, optional
        Add backstop generator to the network (default is False).
    set_global_constraints : bool, optional
        Set global constraints on the network (default is False).
    **kwargs : dict, optional
        Additional keyword arguments.
    
    Returns
    -------
    PyPSA object
        A PyPSA network object.
    '''

    # --- get model years and frequency --- #
    if not years:
        years = model['time_definition']['years']
    
    if not frequency:
        frequency = model['time_definition']['frequency']
    

    # --- check if single-year or multi-year investment problem --- #
    if isinstance(years, int):
        multi_year_investment = False
        years = [years]

    elif isinstance(years, list) and len(years) == 1:
        multi_year_investment = False

    elif isinstance(years, list) and len(years) > 1:
        multi_year_investment = True
    
    # --- get subset of model by countries --- #
    if not select_nodes:
        links       = model['links']
        nodes       = model['nodes']
    else:
        links       = [link for link in model['links'] if link['id'][0:5] in select_nodes and link['id'][6:11] in select_nodes]
        nodes       = [node for node in model['nodes'] if node['id'] in select_nodes]
        timeseries  = timeseries.sel(node=[n for n in timeseries.node.values if n in select_nodes])

    # --- initialise PyPSA network --- #
    network = pypsa.Network()

    # --- set snapshots --- #
    # if not multi_year_investment and isinstance(years, int):
    #     '''Single-year investment problem'''
    #     snapshot = (
    #         pd.date_range(
    #             start=f'{years}-01-01 00:00:00', 
    #             end= f'{years}-12-31 23:00:00',
    #             freq=frequency,
    #         )
    #     )
        
    #     network.set_snapshots(snapshot)

    # else:
    '''Multi-year investment problem'''
    # convert to multiindex and assign to network
    network.snapshots = (
        pd.MultiIndex.from_arrays(
            [
                timeseries.snapshot.to_series().dt.year, 
                timeseries.snapshot.to_series()
            ]
        )
    )
    
    network.investment_periods = years
    
    network.investment_period_weightings["years"] = list(np.diff(years)) + [10]

    # Set the years and objective weighting per investment period. 
    # - The objective weighting is the sum of the discounted values of the years in the investment period.
    # - For each period we sum up all discounts rates of the corresponding years which gives us the effective objective weighting.
    r = kwargs.get('multi_year_discount_rate', model['time_definition']['multi_year_discount_rate'])
    T = 0
    for period, nyears in network.investment_period_weightings.years.items():
        discounts = [(1 / (1 + r) ** t) for t in range(T, T + nyears)]
        network.investment_period_weightings.at[period, "objective"] = sum(discounts)
        T += nyears

    #network.set_snapshots(snapshot.tz_localize('UTC').tz_convert('Asia/Manila'))

    # --- add carriers to network --- #
    for carrier in model['carriers']:
        network.add(
            'Carrier',
            carrier['id'],
            co2_emissions=carrier['co2_emissions'],
            nice_name=carrier['nice_name'],
            color=carrier['color'],
        )

    # --- add buses to network --- #
    for node in nodes:
        network.add(
            "Bus",  # PyPSA component
            node['id'], # bus name
            x = node['coords'][1], # longitude
            y = node['coords'][0] # latitude
        )
    
    # --- add links to network --- #
    # make single year a list to enable iteration
    for year in years:
        for link in links:

            # we can extend assets unless base year
            if year > years[0]:
                p_nom_extendable = True
                p_nom = 0
            else:
                p_nom_extendable = link['extendable']
                p_nom = link['initial_capacity']
            
            # get planned expansions
            if 'planned_expansion' in link.keys() and any( year >= int(y) for y in list( link['planned_expansion'].keys() ) ):
                pe = link['planned_expansion']
                closest_year = min(pe.keys(), key=lambda d_year: abs(d_year - year))
                p_nom_min = pe[closest_year]
            else:
                p_nom_min = 0
            
            # get maximum capacity
            if 'maximum_capacity' in link.keys():
                p_nom_max = link['maximum_capacity']
            else:
                p_nom_max = np.inf

            network.add(
                "Link", 
                name=link['id'] + '-ext-' + str(year),
                bus0=link['from_node'],
                bus1=link['to_node'],
                build_year=year,
                p_nom=p_nom, # starting capacity (MW)
                p_nom_min=p_nom_min, # minimum capacity (MW)
                p_nom_max=p_nom_max, # maximum capacity (MW)
                p_nom_extendable=p_nom_extendable,
                carrier=link['carrier'],
                type=link['type'],
                efficiency=link['efficiency'],
                lifetime=link['lifetime'],
                capital_cost = costs.loc[ link['from_node'][0:3] ].loc[ link['carrier'] ].loc[ year ].AnnualCapitalCost, # currency/MW
                marginal_cost = costs.loc[ link['from_node'][0:3] ].loc[ link['carrier'] ].loc[ year ].MarginalCost, # currency/MWh
            )

            if link['bidirectional']:
                # add reverse link
                network.add(
                "Link", 
                name=link['id'].split('-')[1] + '-' + link['id'].split('-')[0] + '-ext-' + str(year),
                bus0=link['to_node'],
                bus1=link['from_node'],
                build_year=year,
                p_nom=p_nom,
                p_nom_min=p_nom_min,
                p_nom_extendable=p_nom_extendable,
                carrier=link['carrier'],
                type=link['type'],
                efficiency=link['efficiency'],
                lifetime=link['lifetime'],
                capital_cost = costs.loc[ link['from_node'][0:3] ].loc[ link['carrier'] ].loc[ year ].AnnualCapitalCost, # currency/MW
                marginal_cost = costs.loc[ link['from_node'][0:3] ].loc[ link['carrier'] ].loc[ year ].MarginalCost, # currency/MWh
            )
    
    # --- add lengths to links --- #
    for link in network.links.index:
        if network.links.loc[link].length == 0:
            # Get the nodes connected by the link
            bus0 = network.links.at[link, 'bus0']
            bus1 = network.links.at[link, 'bus1']
            
            # Get the coordinates of these nodes
            lat1 = network.buses.at[bus0, 'y']
            lon1 = network.buses.at[bus0, 'x']
            lat2 = network.buses.at[bus1, 'y']
            lon2 = network.buses.at[bus1, 'x']
            
            # Calculate the distance using the Haversine formula
            distance = haversine(lat1, lon1, lat2, lon2)
            
            # Assign the calculated length to the link
            network.links.at[link, 'length'] = distance

    # --- add generators to network --- #
    for year in years:
        for technology in model['generators']:
            for bus in technology['initial_capacity'].keys():

                if bus in network.buses.index:
                    # we can extend assets unless base year
                    if year > years[0]:
                        p_nom_extendable = True
                        p_nom = 0
                        p_nom_min = 0
                        p_nom_max = np.inf
                    else:
                        p_nom_extendable = technology['extendable']
                        p_nom = technology['initial_capacity'][bus]
                        p_nom_min = 0
                        p_nom_max = np.inf
                    
                    # get planned expansions
                    if 'planned_expansion' in technology.keys():
                        if bus in technology['planned_expansion'].keys():
                            pe = technology['planned_expansion'][bus]
                            if any( year >= int(y) for y in list( pe.keys() ) ):
                                closest_year = min(pe.keys(), key=lambda d_year: abs(d_year - year))
                                p_nom_min = pe[closest_year]
                    else:
                        p_nom_min = 0
                    
                    # get maximum capacity
                    if 'maximum_capacity' in technology.keys():
                        if bus in technology['maximum_capacity'].keys():
                            p_nom_max = technology['maximum_capacity'][bus]
                    else:
                        p_nom_max = np.inf
                    
                    # get capacity factors
                    if technology['id'] == 'wind-onshore':
                        cf = (
                            timeseries
                            .sel(
                                node=bus, 
                            )
                            .cf_wind_onshore
                            .to_pandas()
                            .values
                        )
                    elif technology['id'] == 'wind-offshore-unspecified':
                        cf = (
                            timeseries
                            .sel(
                                node=bus, 
                            )
                            .cf_wind_offshore
                            .to_pandas()
                            .values
                        )
                    elif technology['id'] == 'photovoltaic-unspecified':
                        cf = (
                            timeseries
                            .sel(
                                node=bus, 
                            )
                            .cf_solar_pv
                            .to_pandas()
                            .values
                        )
                    elif technology['id'] == 'hydro-unspecified':
                        cf = (
                            timeseries
                            .sel(
                                node=bus, 
                            )
                            .cf_hydro
                            .to_pandas()
                            .values
                        )
                    else:
                        cf = 1

                    network.add(
                        'Generator', # PyPSA component
                        bus + '-' + technology['id'] + '-ext-' + str(year), # generator name
                        type = technology['type'], # technology type (e.g., solar, gas-ccgt etc.)
                        bus = bus, # region/bus/balancing zone
                        # ---
                        # unique technology parameters by bus
                        p_nom = p_nom, # starting capacity (MW)
                        p_nom_min = p_nom_min, # minimum capacity (MW)
                        p_nom_max = p_nom_max, # maximum capacity (MW)
                        p_max_pu = cf, # capacity factor
                        p_min_pu = technology['p_min_pu'][bus], # minimum capacity factor
                        efficiency = technology['efficiency'][bus], # efficiency
                        ramp_limit_up = technology['ramp_limit_up'][bus], # per unit
                        ramp_limit_down = technology['ramp_limit_up'][bus], # per unit
                        # ---
                        # universal technology parameters
                        p_nom_extendable = p_nom_extendable, # can the model build more?
                        capital_cost = costs.loc[ bus[0:3] ].loc[ technology['type'] ].loc[ year ].AnnualCapitalCost, # currency/MW
                        marginal_cost = costs.loc[ bus[0:3] ].loc[ technology['type'] ].loc[ year ].MarginalCost, # currency/MWh
                        carrier = technology['carrier'], # commodity/carrier
                        build_year = year, # year available from
                        lifetime = technology['lifetime'], # years
                        start_up_cost = technology['start_up_cost'], # currency/MW
                        shut_down_cost = technology['shut_down_cost'], # currency/MW
                        committable = technology['committable'], # UNIT COMMITMENT
                        ramp_limit_start_up = technology['ramp_limit_start_up'], # 
                        ramp_limit_shut_down = technology['ramp_limit_shut_down'], # 
                        min_up_time = technology['min_up_time'], # 
                        min_down_time = technology['min_down_time'], # 
                    )
    
    # --- add storage units to network --- #
    for year in years:
        for storage in model['storages']:
            for bus in storage['initial_capacity'].keys():
                
                if bus in network.buses.index:
                    # we can extend assets unless base year
                    if year > years[0]:
                        p_nom_extendable = True
                        p_nom = 0
                    else:
                        p_nom_extendable = storage['extendable']
                        p_nom = storage['initial_capacity'][bus]
                    
                    # get planned expansions
                    if 'planned_expansion' in storage.keys():
                        if bus in storage['planned_expansion'].keys():
                            pe = storage['planned_expansion'][bus]
                            if any( year >= int(y) for y in list( pe.keys() ) ):
                                closest_year = min(pe.keys(), key=lambda d_year: abs(d_year - year))
                                p_nom_min = pe[closest_year]
                    else:
                        p_nom_min = 0
                    
                    # get maximum capacity
                    if 'maximum_capacity' in storage.keys():
                        if bus in storage['maximum_capacity'].keys():
                            p_nom_max = storage['maximum_capacity'][bus]
                        else:
                            p_nom_max = np.inf

                    network.add(
                        'StorageUnit',
                        bus + '-' + storage['id'] + '-ext-' + str(year),
                        bus=bus, 
                        carrier=storage['carrier'],
                        p_nom=p_nom, # starting capacity (MW)
                        p_nom_min=p_nom_min, # minimum capacity (MW)
                        p_nom_extendable=p_nom_extendable,
                        capital_cost=costs.loc[ bus[0:3] ].loc[ storage['id'] ].loc[ year ].AnnualCapitalCost,
                        marginal_cost=costs.loc[ bus[0:3] ].loc[ storage['id'] ].loc[ year ].MarginalCost,
                        build_year=year,
                        lifetime=storage['lifetime'],
                        state_of_charge_initial=storage['state_of_charge_initial'],
                        max_hours=storage['max_hours'],
                        efficiency_store=storage['efficiency_store'],
                        efficiency_dispatch=storage['efficiency_dispatch'],
                        standing_loss=storage['standing_loss'],
                        cyclic_state_of_charge=storage['cyclic_state_of_charge'],
                    )
    
    # --- add loads to network --- #
    load_multiplier = kwargs.get('load_multiplier', 1)

    for bus in network.buses.index:

        demand = (
            timeseries
            .sel(
                node=bus,
            )
            .demand
            .to_pandas()
            .mul(load_multiplier)
            .values
        )

        network.add(
            "Load", # PyPSA component
            bus, # load name
            bus=bus, # region/bus/balancing zone
            p_set=demand # demand profile
        )
    
    # # --- apply rate of change to load if multi-year investment problem --- #
    # if multi_year_investment:

    #     for year in years:

    #         # get rate of change by bus
    #         gradient = {}
    #         for n in nodes:
    #             gradient[n['id']] = kwargs.get('load_rate_of_change', n['load_rate_of_change'])

    #         base_year = years[0]

    #         for year in years[1:]:
    #             for bus in network.loads_t.p_set.columns:

    #                 network.loads_t.p_set.loc[year, bus] = (
    #                     network.loads_t.p_set.loc[base_year, bus].to_numpy() * (1 + gradient[bus])**(year - base_year)
    #                 )
    
    # --- add backstop --- #
    if backstop:

        for bus in network.buses.index:

            network.add(
                'Generator',
                f'Backstop-{bus}',
                bus=bus,
                carrier='backstop',
                p_nom=1e9,
                capital_cost=1e9,
                marginal_cost=1e9,
            )

    # --- set global constraints --- #
    if set_global_constraints:

        print('INFO: Global constraints enabled. Remember to solve using network.optimize.solve_model()')

        for cstr in model['global_constraints']:

            # cumulative p_nom_max
            if cstr['id'] == 'cumulative_p_nom_max' and cstr['enabled'] == True:

                print( 'GlobalConstraints: ' + cstr['id'])

                constr_cumulative_p_nom(network)

            # emissions budget
            if cstr['id'] == 'annual_co2_budget' and cstr['enabled'] == True:

                print( 'GlobalConstraints: ' + cstr['id'])

                emissions = {}
                for n in nodes:
                    emissions['year'] = list( n['co2_budget'].keys() )
                    emissions[n['id']] = list( n['co2_budget'].values() )

                emissions = pd.DataFrame(emissions).set_index('year')

                if network.investment_periods.empty:

                    network.add(
                        "GlobalConstraint",
                        name=f"co2-budget-{years}",
                        carrier_attribute="co2_emissions",
                        sense="<=",
                        constant=emissions.sum(axis=1).loc[years].values[0],
                    )
                
                else:

                    for year in years:

                        network.add(
                            "GlobalConstraint",
                            name=f"co2-budget-{year}",
                            investment_period=year,
                            carrier_attribute="co2_emissions",
                            sense="<=",
                            constant=emissions.sum(axis=1).loc[year],
                        )


    return network