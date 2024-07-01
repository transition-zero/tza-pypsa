import yaml
import pypsa

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


def get_model_subset_by_countries(
        network : pypsa.Network,
        countries : list,
):
    '''Get subset of network by countries
    '''
    # adjust generators
    network.generators = (
        network.generators[
            network.generators.bus.str[0:3].isin(countries)
        ]
    )

    # adjust buses
    network.buses = (
        network.buses[ 
            network.buses.index.str[0:3].isin(countries) 
        ]
    )

    # adjust timeseries data
    network.loads = (
        network.loads[ 
            network.loads.bus.str[0:3].isin(countries) 
        ]
    )

    # adjust loads (time series)
    network.loads_t.p_set = (
        network.loads_t.p_set[ network.loads.bus.to_list() ]
    )

    # adjust links
    network.links = (
        network.links[
            (network.links.bus0.isin( network.buses.index.to_list() )) &
            (network.links.bus1.isin( network.buses.index.to_list() ))
        ]
    )

    # adjust capacity factors
    network.generators_t.p_max_pu = \
        network.generators_t.p_max_pu[
            [i for i in network.generators.index if i in network.generators_t.p_max_pu]
        ]
    
    # adjust storage units
    network.storage_units = (
        network.storage_units[
            network.storage_units.bus.str[0:3].isin(countries)
        ]
    )

    # return adjusted network
    return network


def build_pypsa_model(
        configs,
        nodes,
        links,
        generators,
        timeseries,
        year,
        costs,
        global_constraints,
        custom_constraints,
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
    snapshot = (
        pd.date_range(
            start=f'{year}-01-01 00:00:00', 
            end= f'{year}-12-31 23:00:00',
            freq='h'
        )
    )

    network.set_snapshots(snapshot)
    #network.set_snapshots(snapshot.tz_localize('UTC').tz_convert('Asia/Manila'))

    # ---
    # add carriers
    # TODO: think of a better way to do this

    network.madd(
        "Carrier",
        [
            'biomass',
            'bioenergy', 
            'gas', 
            'coal', 
            'diesel', 
            'geothermal', 
            'hydro',
            'oil', 
            'solar', 
            'waste', 
            'wind', 
        ],
        co2_emissions={
            'biomass' : 0.,
            'bioenergy' : 0., 
            'gas' : 0.20, 
            'coal' : 0.34, 
            'diesel' : 0.26, 
            'geothermal' : 0., 
            'hydro' : 0.,
            'oil' : 0.26, 
            'solar' : 0., 
            'waste' : 0., 
            'wind' : 0., 
        },
        nice_name=[
            'biomass',
            'bioenergy', 
            'gas', 
            'coal', 
            'diesel', 
            'geothermal', 
            'hydro',
            'oil', 
            'solar', 
            'waste', 
            'wind', 
        ],
        color=[
            "teal", 
            "teal", 
            "grey", 
            "black", 
            "darkgray", 
            "brown", 
            "deepskyblue", 
            "gainsboro", 
            "gold", 
            "peru", 
            "aquamarine", 
        ],
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
    # TODO: add line parameters from yaml
    for link in links:
        network.add(
            "Link", 
            name=link['id'],
            bus0=link['from_node'],
            bus1=link['to_node'],
            p_nom=link['initial_capacity'],
            p_nom_extendable=link['extendable'],
            carrier=link['carrier'],
            efficiency=0.97,
            lifetime=99,
        )

    # ---
    # add generators

    for technology in generators:
        for bus in technology['initial_capacity'].keys():

            # print('*******************************')
            # print(technology)
            # print(bus)
            # print('*******************************')
            
            # get capacity factors
            if technology['id'] == 'wind-onshore':
                cf = timeseries.sel(node=bus).cf_wind_onshore.to_numpy()
            elif technology['id'] == 'wind-offshore-unspecified':
                cf = timeseries.sel(node=bus).cf_wind_offshore.to_numpy()
            elif technology['id'] == 'photovoltaic-unspecified':
                cf = timeseries.sel(node=bus).cf_solar_pv.to_numpy()
            elif technology['id'] == 'hydro-unspecified':
                cf = timeseries.sel(node=bus).cf_hydro.to_numpy()
            else:
                cf = 1

            network.add(
                'Generator', # PyPSA component
                bus + '-' + technology['id'], # generator name
                type = technology['type'], # technology type (e.g., solar, gas-ccgt etc.)
                bus = bus, # region/bus/balancing zone
                # ---
                # unique technology parameters by bus
                p_nom = technology['initial_capacity'][bus], # starting capacity (MW)
                p_max_pu = cf, # capacity factor
                p_min_pu = technology['p_min_pu'][bus], # minimum capacity factor
                efficiency = technology['efficiency'][bus], # efficiency
                ramp_limit_up = technology['ramp_limit_up'][bus], # per unit
                ramp_limit_down = technology['ramp_limit_up'][bus], # per unit
                # ---
                # universal technology parameters
                p_nom_extendable = technology['extendable'], # can the model build more?
                capital_cost = costs.loc[ bus[0:3] ].loc[ technology['carrier'] ].AnnualCapitalCost, # currency/MW
                marginal_cost = costs.loc[ bus[0:3] ].loc[ technology['carrier'] ].MarginalCost, # currency/MWh
                carrier = technology['carrier'], # commodity/carrier
                lifetime = technology['lifetime'], # years
                start_up_cost = technology['start_up_cost'], # currency/MW
                shut_down_cost = technology['shut_down_cost'], # currency/MW
                committable = technology['committable'], # UNIT COMMITMENT
                ramp_limit_start_up = technology['ramp_limit_start_up'], # 
                ramp_limit_shut_down = technology['ramp_limit_shut_down'], # 
                min_up_time = technology['min_up_time'], # 
                min_down_time = technology['min_down_time'], # 
            )

    # ---
    # add storages
    # TODO: put storage into yaml file
    for bus in network.buses.index:
        network.add(
            'StorageUnit',
            f'{bus}-battery',
            bus=bus, 
            carrier='battery',
            p_nom=0, 
            p_nom_extendable=False,
            # p_nom_min=self.storage_units.loc[storage_unit].p_nom_min,
            # p_nom_max=self.storage_units.loc[storage_unit].p_nom_max,
            capital_cost=costs.loc[ bus[0:3] ].loc[ 'lithium-ion'].AnnualCapitalCost,
            marginal_cost=costs.loc[ bus[0:3] ].loc[ 'lithium-ion'].MarginalCost,
            #build_year=self.storage_units.loc[storage_unit].build_year,
            lifetime=15,
            #operational features
            state_of_charge_initial=0,
            max_hours=6,
            efficiency_store=0.95,
            efficiency_dispatch=0.95,
            standing_loss=0.01,
            cyclic_state_of_charge=True,
        )

    # ---
    # add load
    load_multiplier = kwargs.get('load_multiplier', 1)
    for bus in network.buses.index:
        network.add(
            "Load", # PyPSA component
            bus, # load name
            bus=bus, # region/bus/balancing zone
            p_set=timeseries.sel(node=bus).demand.to_pandas().mul(load_multiplier).to_numpy() # demand profile
        )
    
    # ---
    # get subset
    if not kwargs.get('countries', None):
        pass
    else:
        network = get_model_subset_by_countries(
            network = network,
            countries = kwargs.get('countries', None)
        )
    
    # # ---
    # # set global constraints
    # print('GlobalConstraints:')
    # for cstr in global_constraints:

    #     # emissions
    #     # TODO

    #     # bus self sufficiency
    #     if cstr['id'] == 'bus_self_sufficiency' and cstr['enabled'] == True:
    #         min_self_sufficiency = cstr['min_self_sufficiency']
    #         print(f' - bus_self_sufficiency >= {min_self_sufficiency}')
    #         constraints.constr_bus_self_sufficiency(network, min_self_sufficiency)
    
    # # ---
    # # set custom constraints
    # # TODO
    # print('')
    # print('CustomConstraints:')
    # print(' - None')

    return network