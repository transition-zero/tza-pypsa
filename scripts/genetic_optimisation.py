import numpy as np
import pandas as pd

import sys
sys.path.append('..')
from models.loader import ASEAN

from platypus import (
    NSGAII, 
    Problem, 
    Real, 
    Integer,
    nondominated
)

from platypus.operators import PCX

# Define the evaluation function for the optimization
def evaluate(variables):

    network = ASEAN(countries=['SGP']).create_model()

    # ---------------------------------
    # DECISION VARIABLES
    # ---------------------------------

    # Set the network parameters based on the decision variables
    for i, v in enumerate(variables):
        try:
            network.generators.iloc[0, network.generators.columns.get_loc('p_nom')] = variables[i]
        except:
            network.links.iloc[0, network.links.columns.get_loc('p_nom')] = variables[i]
    
    # # Perform the optimization
    # lp_model = network.optimize.create_model()

    # hourly_new_renewable_generation = \
    #     lp_model.variables['Generator-p'].sel(Generator=['SGP_solar_new']) + \
    #         lp_model.variables['Generator-p'].sel(Generator=['SGP_wind_new']) #+ \
    #             #lp_model.variables['StorageUnit-p_dispatch'].sel(StorageUnit='sgp_battery')

    # # add constraint
    # lp_model.add_constraints(
    #     hourly_new_renewable_generation >= cfe_min * network.loads_t.p_set['SGP_industrial_load'],
    # )

    # solve
    network.optimize(solver_name='gurobi')

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
        # OBJECTIVE 3: CFE SCORE
        # TODO
    
    # If the model was infeasible, set the objectives to a high value to push the solution into the dominated region
    except:
        objective_1 = 1e999
        objective_2 = 1e999
    
    return [objective_1, objective_2]


def process_results(network, algorithm):

    # get decision variables
    decision_vars_generators = network.generators.index.to_list() 
    decision_vars_links = network.links.index.to_list()
    d_vars = decision_vars_generators + decision_vars_links

    # get mapping of type
    mapping = network.generators.type.to_dict()
    mapping.update(network.links.type.to_dict())

    feasible_solutions = [s for s in algorithm.result if s.feasible]
    nondominated_solutions = nondominated(algorithm.result)

    feasible = []
    for i, s in enumerate(feasible_solutions):
        feasible.append(
            pd.DataFrame(
                {
                    'variable': d_vars,
                    'solution_number' : i+1,
                    'solution_type' : 'feasible',
                    'value': s.variables
                }
            )
        )

    nondom = []
    for i, s in enumerate(nondominated_solutions):
        nondom.append(
            pd.DataFrame(
                {
                    'variable': d_vars,
                    'solution_number' : i+1,
                    'solution_type' : 'non-dominated',
                    'value': s.variables
                }
            )
        )

    solutions = pd.concat(
        [pd.concat(feasible), pd.concat(nondom)], axis=0, ignore_index=True
    )

    solutions['type'] = solutions['variable'].map(mapping)

    return solutions


def run_genetic_optimisation(
    n_generations: int #= 100
):

    # Get model network
    network = ASEAN(countries=['SGP']).create_model()

    decision_vars_generators = network.generators.index.to_list() 
    decision_vars_links = network.links.index.to_list()

    total_decision_variables = len(decision_vars_generators + decision_vars_links)

    # Define the problem
    problem = (
        Problem(
            total_decision_variables, # number of decision variables
            2, # number of objectives
        )
    ) 

    # specify the decision variable ranges
    problem.types[:] = (
        [
            Real( 
                network.generators.at[i, 'p_nom'], 
                1e6
            ) for i in decision_vars_generators
        ] \
            + \
        [
            Real( 
                network.links.at[i, 'p_nom'], 
                1e6
            ) for i in decision_vars_links
        ]
    )

    # specify the type of constraint
    #problem.constraints[:] = "<=0"

    problem.directions[0] = Problem.MINIMIZE # minimize the first objective [TOTAL SYSTEM COST]
    problem.directions[1] = Problem.MINIMIZE # minimize the second objective [TOTAL SYSTEM EMISSIONS]

    problem.function = evaluate

    # Initialize the algorithm
    algorithm = NSGAII(problem)

    # Run the algorithm
    algorithm.run(n_generations)

    # get the results
    results = process_results(network, algorithm)
    results.to_csv(f'../outputs/genetic_optimisation_results.csv')

    return algorithm, problem


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Run genetic optimisation script.")
    parser.add_argument('arg', type=int, help='An argument for the genetic optimisation function')
    args = parser.parse_args()
    run_genetic_optimisation(args.arg)