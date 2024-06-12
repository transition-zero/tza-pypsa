import sys
sys.path.append('../..')
from models.loader import ASEAN

import pandas as pd

from platypus import (
    nondominated
)


def process_results(
        results,
        path,
):

    network = ASEAN(countries=['SGP']).create_model()
    decision_vars_generators = network.generators.index.to_list() 
    decision_vars_links = network.links.index.to_list()
    d_vars = decision_vars_generators + decision_vars_links

    df_rows = []
    for c_seed, seed in enumerate(results['NSGAII']['Problem']):
        # get non-dominated solutions from seed
        nondominated_solutions = nondominated(seed)

        for c_solution, solution in enumerate(seed):

            if solution not in nondominated_solutions:
                solution_class = 'feasible'
            else:
                solution_class = 'non-dominated'

            sln = {
                'seed' : [c_seed + 1],
                'solution' : c_solution + 1,
                'objective_1' : solution.objectives[0],
                'objective_2' : solution.objectives[1],
                'type' : solution_class,
            }

            # d_var = {}
            # for c, v in enumerate(d_vars):
            #     d_var[v] = solution.variables[c] 

            # sln.update(d_var)
        
            df = pd.DataFrame(sln)

            df_rows.append(df)

    solutions = (
        pd
        .concat(df_rows, ignore_index=True)
    )

    solutions.to_csv(path, index=False)