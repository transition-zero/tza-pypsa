import yaml
import pypsa

import pandas as pd

def compute_load(
        path_to_annual_demand : str,
        path_to_demand_profile : str,
        year : int,
):
    '''Compute demand for a given year
    '''
    annual_demand = pd.read_csv(path_to_annual_demand)
    demand_profile = pd.read_csv(path_to_demand_profile)

    annual_demand = ( 
        pd
        .read_csv('../data/raw/ASEAN/specified_annual_demand.csv')
        .query(f"YEAR == {year}")
        .pivot_table(
            index='YEAR',
            columns='CUSTOM_NODE',
            values='VALUE',
            aggfunc='sum')
    )

    for n in annual_demand.columns:
        demand_profile[n] = demand_profile[n].mul(annual_demand[n].values[0])
    
    return demand_profile


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

    # adjust loads
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
    # return adjusted network
    return network


def build_pypsa_model(
        configs,
        nodes,
        links,
        generators,
        loads,
        year,
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
    for link in links:
        network.add(
            "Link", 
            name=link['id'],
            bus0=link['from_node'],
            bus1=link['to_node'],
            p_nom=link['initial_capacity'],
            p_nom_extendable=link['extendable'],
            carrier=link['carrier'],
            efficiency=1,
            lifetime=99,
        )

    # ---
    # add generators

    for technology in generators:
        for bus in technology['initial_capacity'].keys():

            network.add(
                'Generator', # PyPSA component
                bus + '-' + technology['id'], # generator name
                type = technology['id'], # technology type (e.g., solar, gas-ccgt etc.)
                bus = bus, # region/bus/balancing zone
                # ---
                # unique technology parameters by bus
                p_nom = technology['initial_capacity'][bus], # starting capacity (MW)
                # ---
                # universal technology parameters
                p_nom_extendable = technology['extendable'], # can the model build more?
                capital_cost = technology['capital_cost'], # currency/MW
                marginal_cost = technology['marginal_cost'], # currency/MWh
                carrier = technology['carrier'], # commodity/carrier
                lifetime = technology['lifetime'], # years
                efficiency = technology['efficiency'], # efficiency
                start_up_cost = technology['start_up_cost'], # currency/MW
                shut_down_cost = technology['shut_down_cost'], # currency/MW
                ramp_limit_up = technology['ramp_limit_up'], # per unit
                ramp_limit_down = technology['ramp_limit_up'], # per unit
                #committable = technology['committable'], # for unit commitment
            )

    # ---
    # add load
    for bus in network.buses.index:
        network.add(
            "Load", # PyPSA component
            bus, # load name
            bus=bus, # region/bus/balancing zone
            p_set=loads[bus].values # demand profile
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

    return network