import pypsa

import pandas as pd

def constr_bus_self_sufficiency(
        network : pypsa.Network,
        min_self_sufficiency : float = 0.5,
        bus : list = None,
):
    '''
    
    ###################################
    SELF-SUFFICIENCY CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that each bus in the network is self-sufficient to a certain degree. That is,
        it generates at least a certain percentage of its own electricity demand. In other words, it constraints
        the maximum amount of electricity that can be imported to a bus. 

    Inputs:
    -----------------------------------
    
        network : pypsa.Network

        min_self_sufficiency : float
            The minimum self-sufficiency of each bus in the network. Default is 0.5 (i.e., 50% self-sufficiency).
        
        bus : list
            A list of buses to apply the constraint to. Default is None, which applies the constraint to all buses in the network.

    Returns:
    -----------------------------------
    
        None
    
    '''

    # get total renewable generation
    lp_model = network.optimize.create_model()

    if not buses:
        buses = network.buses.index
    else:
        pass

    for bus in buses:
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


def constr_annual_matching(
        network : pypsa.Network,
        lhs_generators : list,
        rhs_min_generation : float,
        sign : str = '>=',
        name : str = None,
):
    '''
    
    ###################################
    ANNUAL MATCHING CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual generation of a set of generators is greater than or equal to a certain value.
        It is particularly useful for setting renewable generation targets. For example, one can use this constraint to ensure that 
        a certain proportion of demand is met by renewable generation.

    Inputs:
    -----------------------------------
    
        network : pypsa.Network

        lhs_generators : list
            A list of generators to apply the constraint to (e.g., all renewable generators).
        
        rhs_min_generation : float
            The minimum total annual generation of the set of generators (e.g., 0.5 = 50%).
        
        sign : str
            The sign of the constraint. Default is '>='.
        
        name : str
            The name of the constraint. Default is None.

    Returns:
    -----------------------------------
    
        None
    
    '''

    # get total annual renewable generation (additional)
    lp_model = network.optimize.create_model()

    lhs_total_generation = (
        lp_model
        .variables['Generator-p']
        .sel(Generator=lhs_generators)
        .sum()
    )

    network.model.add_constraints(
        lhs = lhs_total_generation,
        sign = sign,
        rhs = rhs_min_generation,
        name = name,
    )


def constr_hourly_matching(
        network : pypsa.Network,
        lhs_generators : list,
        rhs_min_generation : float,
        sign : str = '>=',
        name : str = None,
):
    '''
    
    ###################################
    HOURLY MATCHING (CFE) CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total hourly generation of a set of generators is greater than or equal to a certain value.
        It is particularly useful for setting renewable generation targets under a 24/7 CFE procurement strategy. For example, one can
        use this constraint to ensure that a certain load is met by renewable generation in each hour of the year.

    Inputs:
    -----------------------------------
    
        network : pypsa.Network

        lhs_generators : list
            A list of generators to apply the constraint to (e.g., all renewable generators).
        
        rhs_min_generation : float
            The minimum total annual generation of the set of generators (e.g., 0.5 = 50%).
        
        sign : str
            The sign of the constraint. Default is '>='.
        
        name : str
            The name of the constraint. Default is None.
            
    Returns:
    -----------------------------------
    
        None
    
    '''

    # get total annual renewable generation (additional)
    lp_model = network.optimize.create_model()

    lhs_total_generation = (
        lp_model
        .variables['Generator-p']
        .sel(Generator=lhs_generators)
        #.sum() TODO
    )

    network.model.add_constraints(
        lhs = lhs_total_generation,
        sign = sign,
        rhs = rhs_min_generation,
        name = name,
    )