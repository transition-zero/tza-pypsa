import sys
sys.path.append('..')

import platypus

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from models.loader import ASEAN

from platypus import (
    NSGAII, 
    Problem, 
    Real, 
)

model = ASEAN(countries=['PHL'],years=2022)
network = model.create_model(load_multiplier=1.0)

def pypsa_problem(variables):
    
    for count, node in enumerate(nodes_to_test):
        network.generators.loc[node, 'p_min_pu'] = variables[count]

    network.optimize(
        solver_name='gurobi',
        solver_options={
            'OutputFlag': 0,
        }
    )

    try:
        # coal gen
        coal_gen = (network.statistics.energy_balance() / 1e6).loc[('Generator','coal','AC')]
        # gas gen
        gas_gen = (network.statistics.energy_balance() / 1e6).loc[('Generator','gas','AC')]
        return [network.objective], [coal_gen, gas_gen]
    except:
        return [1e999], [1e999, 1e999]

 
params_to_test = {
    #'efficiency' : (0, 1),
    #'ramp_limit_up' : (0, 1),
    #'ramp_limit_down' : (0, 1),
    'p_min_pu' : (0, 0.8),
}

nodes_to_test = [
    # 'PHLLU-bioenergy-unspecified-ext-2022',
    # 'PHLMI-bioenergy-unspecified-ext-2022',
    # 'PHLVI-bioenergy-unspecified-ext-2022',
    'PHLLU-combined-cycle-ext-2022',
    'PHLLU-coal-unspecified-ext-2022',
    'PHLMI-coal-unspecified-ext-2022',
    'PHLVI-coal-unspecified-ext-2022',
    # 'PHLLU-geothermal-unspecified-ext-2022',
    # 'PHLMI-geothermal-unspecified-ext-2022',
    # 'PHLVI-geothermal-unspecified-ext-2022',
    # 'PHLLU-hydro-unspecified',
    # 'PHLMI-hydro-unspecified',
    'PHLLU-open-cycle-gas-turbine-ext-2022',
    # 'PHLLU-oil-unspecified',
    # 'PHLMI-oil-unspecified',
    # 'PHLVI-oil-unspecified'
]

pbounds = {}
for param in params_to_test.keys():
    for gen in nodes_to_test:
        pbounds[f'{gen}|{param}'] = params_to_test[param]

# set up the Platypus problem (2 decision variables, 2 objectives, 2 constraints)
problem = Problem(
    len(pbounds), 
    1, 
    2
)

# specify the decision variable ranges 
problem.types[:] = [ Real( pbounds[k][0], pbounds[k][1]) for k in pbounds  ]
 
# specify the type of constraint
problem.constraints[0] = "==67"
problem.constraints[1] = "==19"
 
# tell Platypus what function to optimize
problem.function = pypsa_problem

# minimize
problem.directions[0] = platypus.Problem.MINIMIZE # MINIMIZE delta
 
# set NSGA II to optimize the problem
algorithm = NSGAII(problem, population_size=100)
 
# run the optimization for 1000 generations
algorithm.run(1000)

from platypus import unique

# Retrieve and print the results
solutions = unique(algorithm.result)
# for solution in algorithm.result:
#     print("Parameters:", solution.variables)
#     print("Objectives:", solution.objectives)

# Convert solutions to a DataFrame
solution_data  = [solution.variables for solution in solutions] 
objective_data = [solution.objectives[0] / 1e6 for solution in solutions]
coal_constraint = [solution.constraints[0] for solution in solutions]
gas_constraint = [solution.constraints[1] for solution in solutions]

results = pd.concat(
    [
        pd.DataFrame(solution_data, columns=[k.replace('|','-') for k in pbounds.keys()]),
        pd.DataFrame(objective_data, columns=['objective']),
        pd.DataFrame(coal_constraint, columns=['coal_gen']),
        pd.DataFrame(gas_constraint, columns=['gas_constraint']),
    ],
    axis=1,
)

results.to_csv('../PHL_CALIBRATION.csv', index=False)