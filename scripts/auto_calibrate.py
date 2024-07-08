import sys
sys.path.append('..')

import platypus
import pandas as pd
import matplotlib.pyplot as plt

from models.loader import ASEAN

from platypus import (
    NSGAII, 
    Problem, 
    Real, 
)

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

        # ---
        # WORKING

        # IDN
        idn_gas_gen     = network.generators_t.p.filter(regex='IDN').filter(regex='cycle').sum().sum() / 1e6
        idn_coal_gen    = network.generators_t.p.filter(regex='IDN').filter(regex='coal').sum().sum() / 1e6
        idn_oil_gen     = network.generators_t.p.filter(regex='IDN').filter(regex='oil').sum().sum() / 1e6

        # PHL
        phl_gas_gen     = network.generators_t.p.filter(regex='PHL').filter(regex='cycle').sum().sum() / 1e6
        phl_coal_gen    = network.generators_t.p.filter(regex='PHL').filter(regex='coal').sum().sum() / 1e6
        phl_oil_gen     = network.generators_t.p.filter(regex='PHL').filter(regex='oil').sum().sum() / 1e6

        # VNM
        vnm_gas_gen     = network.generators_t.p.filter(regex='VNM').filter(regex='cycle').sum().sum() / 1e6
        vnm_coal_gen    = network.generators_t.p.filter(regex='VNM').filter(regex='coal').sum().sum() / 1e6
        vnm_oil_gen     = network.generators_t.p.filter(regex='VNM').filter(regex='oil').sum().sum() / 1e6

        # LAO
        lao_coal_gen    = network.generators_t.p.filter(regex='LAO').filter(regex='coal').sum().sum() / 1e6

        # MMR
        mmr_gas_gen     = network.generators_t.p.filter(regex='MMR').filter(regex='cycle').sum().sum() / 1e6
        mmr_coal_gen    = network.generators_t.p.filter(regex='MMR').filter(regex='coal').sum().sum() / 1e6

        # ---
        # NOT WORKING
        
        # # MYS
        # mys_gas_gen     = network.generators_t.p.filter(regex='MYS').filter(regex='cycle').sum().sum() / 1e6
        # mys_coal_gen    = network.generators_t.p.filter(regex='MYS').filter(regex='coal').sum().sum() / 1e6
        # mys_oil_gen     = network.generators_t.p.filter(regex='MYS').filter(regex='oil').sum().sum() / 1e6

        # # SGP
        # sgp_gas_gen     = network.generators_t.p.filter(regex='SGP').filter(regex='cycle').sum().sum() / 1e6
        # sgp_coal_gen    = network.generators_t.p.filter(regex='SGP').filter(regex='coal').sum().sum() / 1e6
        # sgp_oil_gen     = network.generators_t.p.filter(regex='SGP').filter(regex='oil').sum().sum() / 1e6

        # # THA
        # tha_gas_gen     = network.generators_t.p.filter(regex='THA').filter(regex='cycle').sum().sum() / 1e6
        # tha_coal_gen    = network.generators_t.p.filter(regex='THA').filter(regex='coal').sum().sum() / 1e6
        # tha_oil_gen     = network.generators_t.p.filter(regex='THA').filter(regex='oil').sum().sum() / 1e6
        
        # # KHM
        # #####khm_gas_gen     = network.generators_t.p.filter(regex='KHM').filter(regex='cycle').sum().sum() / 1e6
        # khm_coal_gen    = network.generators_t.p.filter(regex='KHM').filter(regex='coal').sum().sum() / 1e6
        # khm_oil_gen     = network.generators_t.p.filter(regex='KHM').filter(regex='oil').sum().sum() / 1e6

        # # BRN
        # brn_gas_gen     = network.generators_t.p.filter(regex='BRN').filter(regex='cycle').sum().sum() / 1e6
        # brn_coal_gen    = network.generators_t.p.filter(regex='BRN').filter(regex='coal').sum().sum() / 1e6
        # brn_oil_gen     = network.generators_t.p.filter(regex='BRN').filter(regex='oil').sum().sum() / 1e6

        return \
            [
                network.objective
            ], \
            [ 
                # - working
                idn_gas_gen, idn_coal_gen, idn_oil_gen,
                phl_gas_gen, phl_coal_gen, phl_oil_gen,
                vnm_gas_gen, vnm_coal_gen, vnm_oil_gen,
                lao_coal_gen, 
                mmr_gas_gen, mmr_coal_gen, 
                # - not working
                # mys_gas_gen, mys_coal_gen, mys_oil_gen,
                # sgp_gas_gen, sgp_coal_gen, sgp_oil_gen,
                # tha_gas_gen, tha_coal_gen, tha_oil_gen,
                # khm_coal_gen, khm_oil_gen, 
                # brn_gas_gen, brn_coal_gen, #### brn_oil_gen,

            ]
    
    except:
        return \
            [
                1e99
            ], \
            [
                1e99 for i in range(0, number_of_constraints)
            ]


model = ASEAN(
    countries=['IDN', 'PHL', 'VNM', 'LAO','MMR'],  # MYS, SGP, THA, KHM, BRN
    years=2022,
)

network = model.create_model(load_multiplier=1.0)

fossil = ['gas','oil','coal']
nodes_to_test = network.generators.query(' carrier.isin(@fossil) ').index.unique().tolist()

params_to_test = {
    #'efficiency' : (0, 1),
    #'ramp_limit_up' : (0, 1),
    #'ramp_limit_down' : (0, 1),
    'p_min_pu' : (0., 0.01),
}

pbounds = {}
for param in params_to_test.keys():
    for gen in nodes_to_test:
        pbounds[f'{gen}|{param}'] = params_to_test[param]

gen_to_constrain = {
    'IDN' : {
        'gas' : 57,
        'coal' : 205,
        'oil' : 6,
    },
    'PHL' : {
        'gas' : 20,
        'coal' : 67,
        'oil' : 2,
    },
    'VNM' : {
        'gas' : 28,
        'coal' : 100,
        'oil' : 0.7,
    },
    'LAO' : {
        'coal' : 12,
    },
    'MMR' : {
        'gas' : 8,
        'coal' : 2,
    },
    # 'MYS' : {
    #     'gas' : 68,
    #     'coal' : 76,
    #     'oil' : 1.7,
    # },
    # 'SGP' : {
    #     'gas' : 53,
    #     'coal' : 0.5,
    #     'oil' : 1.5,
    # },
    # 'THA' : {
    #     'gas' : 115,
    #     'coal' : 35,
    #     'oil' : 1.7,
    # },
    # 'KHM' : {
    #     'coal' : 3.8,
    #     'oil' : 0.5,
    # },
    # 'BRN' : {
    #     'gas' : 4.5,
    #     'coal' : 1,
    # },
}

# calculate problem params
number_of_decision_vars = len(pbounds)
number_of_objectives = 1
number_of_constraints = sum(len(gen_to_constrain[k]) for k in gen_to_constrain)

# set up the Platypus problem (decision variables, objectives, constraints)
problem = Problem(
    number_of_decision_vars, 
    number_of_objectives, 
    number_of_constraints
)

# specify the decision variable ranges 
problem.types[:] = [ Real( pbounds[k][0], pbounds[k][1]) for k in pbounds  ]

# specify the type of constraint
# problem.constraints[0] = "==67"
# problem.constraints[1] = "==19"

count = 0
for country in gen_to_constrain:
    for technology in gen_to_constrain[country]:
        problem.constraints[count] = f'=={gen_to_constrain[country][technology]}'
        count += 1

# tell Platypus what function to optimize
problem.function = pypsa_problem

# minimize
problem.directions[0] = platypus.Problem.MINIMIZE # MINIMIZE delta
 
# set NSGA II to optimize the problem
algorithm = NSGAII(problem, population_size=250)
 
# run the optimization for 1000 generations
algorithm.run(5000)

from platypus import unique

# Retrieve and print the results
solutions = unique(algorithm.result)
# for solution in algorithm.result:
#     print("Parameters:", solution.variables)
#     print("Objectives:", solution.objectives)

# Convert solutions to a DataFrame
solution_data  = [solution.variables for solution in solutions] 
objective_data = [solution.objectives[0] / 1e6 for solution in solutions]
constraint_data = [list(solution.constraints)for solution in solutions]

results = (
    pd
    .concat(
        [
            pd.DataFrame(solution_data, columns=['dvar-' + k.replace('|','-') for k in pbounds.keys()]),
            pd.DataFrame(constraint_data, columns=[f"constr-{key}-{value}-gen" for key, values in gen_to_constrain.items() for value in values]),
            pd.DataFrame(objective_data, columns=['objective']),
        ],
        axis=1,
    )
    .reset_index()
    .rename(columns={'index': 'iteration'})
    .melt(id_vars='iteration')
)

results.to_csv('../ASEAN_CALIBRATION.csv', index=False)