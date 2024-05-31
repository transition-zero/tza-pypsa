import pypsa

import pandas as pd

def constr_bus_self_sufficiency(
        network,
        min_self_sufficiency,
):
    # get total renewable generation
    lp_model = network.optimize.create_model()

    for bus in network.buses.index:

        # get all generators at bus
        network.generators.query( f' bus == "{bus}" ').index

        # get total generation by bus
        total_gen_by_bus = ( 
            lp_model
            .variables['Generator-p']
            .sel(
                Generator=network.generators.query( f' bus == "{bus}" ').index
            )
            .sum()
            .sum()
        )

        # get demand at bus
        total_demand_by_bus = network.loads_t.p_set[bus].sum(axis=0)

        # set expression
        constraint_expression = total_gen_by_bus >= total_demand_by_bus * min_self_sufficiency

        # set constraint
        lp_model.add_constraints(
            constraint_expression,
            name=f'min_gen_by_{bus}',
        )