import sys
sys.path.append('..')
sys.path.append('../..')
sys.path.append('.')

import os
import yaml
import platypus
import helpers
import pandas as pd

from models.loader import ASEAN

# load config
config_path = os.path.join( os.path.dirname(os.path.realpath(__file__)), 'run-config.yaml' )
with open(config_path, "r") as file:
    config = yaml.safe_load(file)


def evaluate_beam(vars):
    """
    A version of the cantilever beam model to optimize with an MOEA in Platypus
 
    :param vars:        a vector with decision variables element [0] is length, [1] is diameter
    :return:
        - a vector of objectives [weight, deflection]
        - a vector of constraints, [stress, deflection]
 
    """
    l = vars[0]
    d = vars[1]
 
    weight = (7800.0 * (3.14159 * d ** 2) / 4 * l)/1000000000
    deflection = (64.0*1.0 * l**3)/(3.0*207.0*3.14159*d**4)
    stress = (32.0 * 1.0 * l)/(3.14159*d**3)
 
    return [weight, deflection] , [stress - 300, deflection - 5]


def get_beam_problem():
    problem = platypus.Problem(2, 2, 2)
    problem.types[:] = [platypus.Real(200, 1000), platypus.Real(10, 50)]
    problem.function = evaluate_beam
    return problem


def get_cfe_score(
        network,
        local_bus, 
        fossil_generators,
        cfe_min,
):

    generators_clean_rest_of_system = (
        (
            network.generators.loc[
                (~network.generators.type.isin(fossil_generators)) &
                (~network.generators.bus.str.contains(local_bus))
            ]
        )
        .index
    )

    generators_all_rest_of_system = (
        (
            network.generators.loc[
                (~network.generators.bus.str.contains(local_bus))
            ]
        )
        .index
    )

    generators_clean_local_system = (
        (
            network.generators.loc[
                (~network.generators.type.isin(fossil_generators)) &
                (network.generators.bus.str.contains(local_bus))
            ]
        )
        .index
    )

    generators_all_local_system = (
        (
            network.generators.loc[
                (network.generators.bus.str.contains(local_bus))
            ]
        )
        .index
    )

    # ---
    # EQUATIONS

    imported_cfe = (
        network.generators_t.p[generators_clean_rest_of_system].sum(axis=1)
        / network.generators_t.p[generators_all_rest_of_system].sum(axis=1)
    )

    imported_electricity = (
        network.links_t.p0.filter(regex=f'-{local_bus}').sum(axis=1)
    )

    cfe_t = (
        (network.generators_t.p[generators_clean_local_system].sum(axis=1) + imported_cfe * imported_electricity)
        / (network.generators_t.p[generators_all_local_system].sum(axis=1) + imported_electricity)
    )

    cfe = pd.DataFrame({
        'cfe_t' : cfe_t.values
    })

    cfe.loc[cfe.cfe_t >= cfe_min, 'cfe_count'] = 1
    cfe.loc[cfe.cfe_t < cfe_min, 'cfe_count'] = 0

    return cfe.cfe_count.sum()


def evaluate_pypsa_model(variables):
    """
    A function to solve the PyPSA-ASEAN model with an MOEA algorithm
 
    :param vars: a vector with decision variables element [0] is length, [1] is diameter

    :returns:
        - a vector of objectives, [total_system_cost, total_system_emissions]
        - a vector of constraints, [industrial_cfe_score]
 
    """

    network = (
        ASEAN(
            countries=config['ASEAN']['countries']
        )
        .create_model()
    )

    # ---------------------------------
    # DECISION VARIABLES
    # ---------------------------------

    # Set the network parameters based on the decision variables
    for i, v in enumerate(variables):
        try:
            network.generators.iloc[0, network.generators.columns.get_loc('p_nom')] = variables[i]
        except:
            network.links.iloc[0, network.links.columns.get_loc('p_nom')] = variables[i]
    
    # solve
    network.optimize(
        solver_name='highs',
        solver_options={
            "solver": "pdlp",
        }
    )

    # ---------------------------------
    # OBJECTIVES
    # ---------------------------------
    
    # Check if the optimization was successful
    try:

        # --------
        # OBJECTIVE 1: TOTAL SYSTEM COST

        objective_1 = (
            (
                network.statistics()['Capital Expenditure'] + 
                network.statistics()['Operational Expenditure']

            )
            .sum()
        )

        # --------
        # OBJECTIVE 2: TOTAL SYSTEM EMISSIONS

        objective_2 = (
            (
                network.generators_t.p 
                / network.generators.efficiency
                * network.generators.type.map(network.carriers.co2_emissions)
            )
            .sum()
            .sum()
        )

        # --------
        # CONSTRAINT 1: CFE SCORE

        cfe_score = (
            get_cfe_score(
                network,
                local_bus=config['ASEAN']['local_bus'],
                fossil_generators=config['ASEAN']['fossil_generators'],
                cfe_min=config['ASEAN']['cfe_score'],
            )
        )

        cfe_score = cfe_score / 8760 * 100
    
    # If the model was infeasible, set the objectives to a high value to push the solution into the dominated region
    except:
        objective_1 = float( config['MOEA']['infeasible_objective_penalty'] )
        objective_2 = float( config['MOEA']['infeasible_objective_penalty'] )
        cfe_score = config['MOEA']['infeasible_cfe_penalty']
    
    return [objective_1, objective_2], [cfe_score]


def get_pypsa_problem():

    # Get model network
    network = (
        ASEAN(
            countries=config['ASEAN']['countries']
        )
        .create_model()
    )

    decision_vars_generators = network.generators.index.to_list() 
    decision_vars_links = network.links.index.to_list()
    decision_vars_storage = network.storage_units.index.to_list()
    total_decision_variables = len(decision_vars_generators + decision_vars_links + decision_vars_storage)

    # Define the problem
    problem = (
        platypus.Problem(
            total_decision_variables, # number of decision variables
            config['MOEA']['number_of_objectives'], # number of objectives
            config['MOEA']['number_of_constraints'], # number of constraints
        )
    ) 

    # specify the decision variable ranges
    p_nom_max = config['ASEAN']['p_nom_max']
    problem.types[:] = (
        [
            platypus.Real( 
                network.generators.at[i, 'p_nom'], 
                p_nom_max
            ) for i in decision_vars_generators
        ] \
            + \
        [
            platypus.Real( 
                network.links.at[i, 'p_nom'], 
                p_nom_max
            ) for i in decision_vars_links
        ]
            + \
        [
            platypus.Real( 
                network.storage_units.at[i, 'p_nom'], 
                p_nom_max
            ) for i in decision_vars_storage
        ]
    )

    # specify the type of constraint
    cfe_score = config['ASEAN']['cfe_score']
    problem.constraints[:] = '>=50'

    problem.directions[0] = platypus.Problem.MINIMIZE # minimize the first objective [TOTAL SYSTEM COST]
    problem.directions[1] = platypus.Problem.MINIMIZE # minimize the second objective [TOTAL SYSTEM EMISSIONS]

    problem.function = evaluate_pypsa_model

    return problem