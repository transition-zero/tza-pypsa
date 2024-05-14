import yaml
import pypsa
import pandas as pd

def load_yaml():
    # Load nodes yaml
    with open("../models/ASEAN/nodes.yaml", "r") as file:
        nodes = yaml.safe_load(file)
        nodes = nodes['nodes']

    # Load links yaml
    with open("../models/ASEAN/links.yaml", "r") as file:
        links = yaml.safe_load(file)
        links = links['links']

    # Load time definitions yaml
    with open("../models/ASEAN/time_definitions.yaml", "r") as file:
        time_definition = yaml.safe_load(file)
        time_definition = time_definition['time_definition']

    # Load generators yaml
    with open("../models/ASEAN/generators.yaml", "r") as file:
        generators = yaml.safe_load(file)
        generators = generators['generators']
    
    return nodes, links, time_definition, generators

def build_network():
    '''Construct pypsa network from yaml files
    '''

    # ---
    # get yaml data
    nodes, links, time_definition, generators = load_yaml()

    # ---
    # initialize network
    network = pypsa.Network()

    # ---
    # set time index (snapshots)
    year = time_definition['year']

    snapshot = (
        pd.date_range(
            start=f'{year}-01-01 00:00:00', 
            end= f'{year}-12-31 00:00:00', 
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

            # add generators one-by-one
            network.add(
                'Generator', # PyPSA component
                bus + '-' + technology['id'], # generator name
                type = technology['id'], # technology type (e.g., solar, gas-ccgt etc.)
                bus = bus, # region/bus/balancing zone

                # ---
                # unique technology parameters by bus
                p_nom = technology['initial_capacity'][bus], # starting capacity (MW)
                p_nom_extendable = technology['extendable'][bus], # can the model build more?
                capital_cost = technology['capital_cost'][bus], # currency/MW
                marginal_cost = technology['marginal_cost'][bus], # currency/MWh

                # ---
                # universal technology parameters
                carrier = technology['carrier'], # commodity/carrier
                lifetime = technology['lifetime'], # years
                efficiency = technology['efficiency'], # efficiency
                start_up_cost = technology['start_up_cost'], # currency/MW
                shut_down_cost = technology['shut_down_cost'], # currency/MW
                ramp_limit_up = technology['ramp_limit_up'], # per unit
                ramp_limit_down = technology['ramp_limit_up'], # per unit
                committable = technology['committable'], # for unit commitment
            )

    # ---
    # add load

    # ---
    # plot

    network.plot(
        bus_sizes=0.4,
    )