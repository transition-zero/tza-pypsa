import os
import sys
import time
import yaml
import pickle

from platypus import *

if __name__ == "__main__":

    # local dir imports
    import model
    import helpers

    # load config
    config_path = os.path.join( os.path.dirname(os.path.realpath(__file__)), 'run-config.yaml' )
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)

    # Record the start time
    start_time = time.time()

    # make the problem
    algorithms = [NSGAII] 

    import model
    problem = model.get_pypsa_problem()
    problems = [ problem ] 
 
    with ProcessPoolEvaluator( config['MOEA']['number_of_cores'] ) as evaluator:

        results = (
            experiment(
                algorithms,
                problems, 
                nfe=config['MOEA']['number_of_generations'],  
                evaluator=evaluator,
                display_stats=True,
                seeds=config['MOEA']['number_of_seeds'],
            )
        )
    
    # Save the results
    ngen = config['MOEA']['number_of_generations']
    cfe_score = config['ASEAN']['cfe_score']
    nseed = config['MOEA']['number_of_seeds']

    fname = (
        f'solution_seed{nseed}_gen{ngen}_cfe{cfe_score}.csv'
    )

    (helpers
        .process_results(
            results,
            path=os.path.join(
                os.path.dirname(os.path.realpath(__file__)), f'results/{fname}' 
            )
        )
    )

    # Record the end time
    end_time = time.time()
    # Calculate the elapsed time
    elapsed_time = end_time - start_time
    print("*************************************************************************")
    print('')
    print(f"The script took {elapsed_time:.2f} seconds to complete.")
    print('')
    print("*************************************************************************")