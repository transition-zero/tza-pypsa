import yaml
import pypsa

import numpy as np
import pandas as pd

from . import constraints


def get_yaml(
        path : str,
):
    '''Load data from yaml
    '''
    # Load generators yaml
    with open(path, "r") as file:
        data = yaml.safe_load(file)
    return data


def build_pypsa_model(
        configs,
        nodes,
        generators,
        links,
        storages,
        carriers,
        timeseries,
        years,
        costs,
        backstop = False,
        *args,
        **kwargs,
):
    '''Construct pypsa network from yaml files
    '''

    # ---
    # initialize network
    network = pypsa.Network()

    # ---
    # set time index (snapshots)

    if configs['time_definition']['multi_year_investment'] == False and isinstance(years, int):

        snapshot = (
            pd.date_range(
                start=f'{years}-01-01 00:00:00', 
                end= f'{years}-12-31 23:00:00',
                freq=configs['time_definition']['frequency'],
            )
        )
        
        network.set_snapshots(snapshot)

    else:

        snapshots = pd.DatetimeIndex([])
        for year in years:
            period = pd.date_range(
                start=f"{year}-01-01 00:00",
                freq=configs['time_definition']['frequency'],
                periods= int(8760 / float( configs['time_definition']['frequency'].strip('h') )),
            )
            snapshots = snapshots.append(period)

        # convert to multiindex and assign to network
        network.snapshots = pd.MultiIndex.from_arrays([snapshots.year, snapshots])
        network.investment_periods = years

        network.investment_period_weightings["years"] = list(np.diff(years)) + [10]

        # Set the years and objective weighting per investment period. 
        # - The objective weighting is the sum of the discounted values of the years in the investment period.
        # - For each period we sum up all discounts rates of the corresponding years which gives us the effective objective weighting.
        r = configs['time_definition']['multi_year_discount_rate']
        T = 0
        for period, nyears in network.investment_period_weightings.years.items():
            discounts = [(1 / (1 + r) ** t) for t in range(T, T + nyears)]
            network.investment_period_weightings.at[period, "objective"] = sum(discounts)
            T += nyears

    #network.set_snapshots(snapshot.tz_localize('UTC').tz_convert('Asia/Manila'))

    # ---
    # add carriers
    
    for carrier in carriers:
        network.add(
            'Carrier',
            carrier['id'],
            co2_emissions=carrier['co2_emissions'],
            nice_name=carrier['nice_name'],
            color=carrier['color'],
        )

    # ---
    # add buses (nodes)

    for node in nodes:
        network.add(
            "Bus",  # PyPSA component
            node['id'], # bus name
            x = node['coords'][1], # longitude
            y = node['coords'][0] # latitude
        )

    # ---
    # add lines

    # make single year a list to enable iteration
    if isinstance(years,int):
        yyears = [years]
    else:
        yyears = years

    for year in yyears:
        for link in links:

            # we can extend assets unless base year
            if isinstance(years, list):
                if year > years[0]:
                    p_nom_extendable = True
                    p_nom = 0
                else:
                    p_nom_extendable = link['extendable']
                    p_nom = link['initial_capacity']
            else:
                p_nom_extendable = link['extendable']
                p_nom = link['initial_capacity']

            network.add(
                "Link", 
                name=link['id'] + '-ext-' + str(year),
                bus0=link['from_node'],
                bus1=link['to_node'],
                p_nom=p_nom,
                p_nom_extendable=p_nom_extendable,
                carrier=link['carrier'],
                efficiency=0.97,
                lifetime=99,
            )

    # ---
    # add generators
    for year in yyears:
        for technology in generators:
            for bus in technology['initial_capacity'].keys():

                if bus in network.buses.index:
                    # we can extend assets unless base year
                    if isinstance(years, list):
                        if year > years[0]:
                            p_nom_extendable = True
                            p_nom = 0
                        else:
                            p_nom_extendable = technology['extendable']
                            p_nom = technology['initial_capacity'][bus]
                    else:
                        p_nom_extendable = technology['extendable']
                        p_nom = technology['initial_capacity'][bus]
                    
                    # get capacity factors
                    if technology['id'] == 'wind-onshore':
                        cf = (
                            timeseries
                            .sel(node=bus)
                            .cf_wind_onshore
                            .resample(snapshot=configs['time_definition']['frequency'])
                            .mean()
                            .to_numpy()
                        )
                    elif technology['id'] == 'wind-offshore-unspecified':
                        cf = (
                            timeseries
                            .sel(node=bus)
                            .cf_wind_offshore
                            .resample(snapshot=configs['time_definition']['frequency'])
                            .mean()
                            .to_numpy()
                        )
                    elif technology['id'] == 'photovoltaic-unspecified':
                        cf = (
                            timeseries
                            .sel(node=bus)
                            .cf_solar_pv
                            .resample(snapshot=configs['time_definition']['frequency'])
                            .mean()
                            .to_numpy()
                        )
                    elif technology['id'] == 'hydro-unspecified':
                        cf = (
                            timeseries
                            .sel(node=bus)
                            .cf_hydro
                            .resample(snapshot=configs['time_definition']['frequency'])
                            .mean()
                            .to_numpy()
                        )
                    else:
                        cf = 1
                    
                    if isinstance(cf, np.ndarray):
                        cf = (
                            np
                            .tile(
                                cf, 
                                len( yyears )
                            )
                            .reshape(1, -1)
                            [0]
                        )

                    network.add(
                        'Generator', # PyPSA component
                        bus + '-' + technology['id'] + '-ext-' + str(year), # generator name
                        type = technology['type'], # technology type (e.g., solar, gas-ccgt etc.)
                        bus = bus, # region/bus/balancing zone
                        # ---
                        # unique technology parameters by bus
                        p_nom = p_nom, # starting capacity (MW)
                        p_max_pu = cf, # capacity factor
                        p_min_pu = technology['p_min_pu'][bus], # minimum capacity factor
                        efficiency = technology['efficiency'][bus], # efficiency
                        ramp_limit_up = technology['ramp_limit_up'][bus], # per unit
                        ramp_limit_down = technology['ramp_limit_up'][bus], # per unit
                        # ---
                        # universal technology parameters
                        p_nom_extendable = p_nom_extendable, # can the model build more?
                        capital_cost = costs.loc[ bus[0:3] ].loc[ technology['type'] ].AnnualCapitalCost, # currency/MW
                        marginal_cost = costs.loc[ bus[0:3] ].loc[ technology['type'] ].MarginalCost, # currency/MWh
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
                else:
                    continue

    # ---
    # add storages
    # TODO: put storage into yaml file

    for year in yyears:
        for storage in storages:
            for bus in storage['initial_capacity'].keys():
                
                if bus in network.buses.index:
                    # we can extend assets unless base year
                    if isinstance(years, list):
                        if year > years[0]:
                            p_nom_extendable = True
                            p_nom = 0
                        else:
                            p_nom_extendable = storage['extendable']
                            p_nom = storage['initial_capacity'][bus]
                    else:
                        p_nom_extendable = storage['extendable']
                        p_nom = storage['initial_capacity'][bus]

                    network.add(
                        'StorageUnit',
                        bus + '-' + storage['id'] + '-ext-' + str(year),
                        bus=bus, 
                        carrier=storage['carrier'],
                        p_nom=p_nom, 
                        p_nom_extendable=p_nom_extendable,
                        capital_cost=costs.loc[ bus[0:3] ].loc[ storage['id'] ].AnnualCapitalCost,
                        marginal_cost=costs.loc[ bus[0:3] ].loc[ storage['id'] ].MarginalCost,
                        build_year=year,
                        lifetime=storage['lifetime'],
                        state_of_charge_initial=storage['state_of_charge_initial'],
                        max_hours=storage['max_hours'],
                        efficiency_store=storage['efficiency_store'],
                        efficiency_dispatch=storage['efficiency_dispatch'],
                        standing_loss=storage['standing_loss'],
                        cyclic_state_of_charge=storage['cyclic_state_of_charge'],
                    )

    # ---
    # add load

    load_multiplier = kwargs.get('load_multiplier', 1)

    for bus in network.buses.index:

        demand = (
            timeseries
            .sel(node=bus)
            .demand
            .resample(snapshot=configs['time_definition']['frequency'])
            .mean()
            .to_pandas()
            .mul(load_multiplier)
            .to_numpy()
        )

        if isinstance(demand, np.ndarray):
            demand = (
                np
                .tile(
                    demand, 
                    len( yyears )
                )
                .reshape(1, -1)
                [0]
            )

        network.add(
            "Load", # PyPSA component
            bus, # load name
            bus=bus, # region/bus/balancing zone
            p_set=demand # demand profile
        )
    
    # ---
    # Adjust load for growth rates if multi-year investment

    if isinstance(yyears,list):

        for year in yyears:

            # get rate of change by bus
            load_rate_of_change = {}
            for n in nodes:
                load_rate_of_change[n['id']] = n['load_rate_of_change']

            base_year = yyears[0]

            for year in yyears[1:]:
                for bus in network.loads_t.p_set.columns:

                    network.loads_t.p_set.loc[year, bus] = (
                        network.loads_t.p_set.loc[year, bus].to_numpy() * (1 + load_rate_of_change[bus])**(year - base_year)
                    )

    # ---
    # add backstop

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
        
    
    # # ---
    # # set global constraints

    # for year in configs['time_definition']['years']:

    #     network.add(
    #         "GlobalConstraint",
    #         name=f"emission-limit-{year}",
    #         investment_period=year,
    #         carrier_attribute="co2_emissions",
    #         sense="<=",
    #         constant=configs['emissions_targets']['CO2'][year],
    #     )

    # print('GlobalConstraints:')
    # for cstr in global_constraints:

    #     # emissions
    #     # TODO

    #     # bus self sufficiency
    #     if cstr['id'] == 'bus_self_sufficiency' and cstr['enabled'] == True:
    #         min_self_sufficiency = cstr['min_self_sufficiency']
    #         print(f' - bus_self_sufficiency >= {min_self_sufficiency}')
    #         constraints.constr_bus_self_sufficiency(network, min_self_sufficiency)
    
    return network