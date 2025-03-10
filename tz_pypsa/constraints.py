import pypsa

import numpy as np
import pandas as pd


def constr_bus_self_sufficiency(
        network : pypsa.Network,
        min_self_sufficiency : float = 0.85,
        buses : list = None,
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
    
    Example user story:
    -----------------------------------
        "I want to ensure each region is at least 50% self-sufficient across the year. This prevents any region
        from being too dependent on imports and ensures that each region has a certain level of energy security."

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


def constr_cumulative_p_nom(
        network : pypsa.Network,
):
    '''
    ###################################
    CUMULATIVE CAPACITY CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that p_nom_max can be applied cumulatively across a multi-year investment problem.
    
    Example user story:
    -----------------------------------
        "I want to ensure total solar capacity is less than or equal to a theoretical maximum at each bus."

    Inputs:
    -----------------------------------
    
        network : pypsa.Network
            
    Returns:
    -----------------------------------
    
        None
    
    '''

    lp_model = network.optimize.create_model()

    x = np.inf
    y = network.investment_periods[1:].to_list()

    for i in network.generators.groupby(['bus','type']).first().query(' p_nom_max != @x ').index:
        
        # get common generators across years
        generators = (
            network
            .generators
            .query(" bus == @i[0] ")
            .query(" type == @i[1] ")
            .query(" build_year.isin(@y) ")
            .index
            .tolist()
        )

        # get linopy var
        total_generation_capacity =( 
            lp_model
            .variables['Generator-p_nom']
            .sel({'Generator-ext' : generators})
            .sum()
        )

        # get p_nom_max of all common generators
        max_capacity = (
            network
            .generators
            .query(" bus == @i[0] ")
            .query(" type == @i[1] ")
            .query(" build_year.isin(@y) ")
            .p_nom_max
            .max()
            #.tolist()
        )

        # set expression
        constraint_expression = total_generation_capacity <= max_capacity 
        # set constraint
        lp_model.add_constraints(
            constraint_expression,
            name=f'cumu_p_nom_{generators[0]}',
        )


def constr_min_annual_generation(
        network : pypsa.Network,
        lhs_generator : str,
        rhs_min_generation : float,
        sign : str = '>=',
        name : str = None,
):
    '''
    ###################################
    MINIMUM ANNUAL GENERATION 
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual generation by a specific unit is greater than or equal to a certain value.
    
    Example user story:
    -----------------------------------
        "I want to ensure my gas power plant produces at least 70% of its theoretical annual generation."

    Inputs:
    -----------------------------------
    
        network : pypsa.Network

        lhs_generator : str
            The generator to apply the constraint to.
        
        rhs_min_generation : float
            The minimum total generation as a proportion of the theoretical annual maximum (e.g., 0.7 = 70%).
        
        sign : str
            The sign of the constraint. Default is '>='.
        
        name : str
            The name of the constraint. Default is None.
            
    Returns:
    -----------------------------------
    
        None
    
    '''
    lp_model = network.optimize.create_model()

    lhs_total_generation = lp_model['Generator-p'].sel(Generator=lhs_generator).sum()

    rhs_total_theoretical_generation = (
        lp_model['Generator-p_nom'].sel({'Generator-ext' : lhs_generator}) * 8760 * rhs_min_generation
    )

    lp_model.add_constraints(
        lhs = lhs_total_generation,
        sign = sign,
        rhs = rhs_total_theoretical_generation,
        name = name,
    )


def constr_max_annual_utilisation(
        network : pypsa.Network,
        lp_model,
        max_utilisation_rate : float = 0.85,
        carriers : list = None,
        model_frequency : int = 1,
):
    '''
    
    ###################################
    MAXIMUM ANNUAL UTILISATION CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual utilisation rate of a technology or carrier 
        equals to a certain percentage value.
    
    Example user story:
    -----------------------------------
        "I want to ensure that coal utilisation rate is only 85% annually, not 100%"

    Inputs:
    -----------------------------------
    
        network : pypsa.Network
        
        lp_model : linopy model with variables and constraints

        max_utilisation_rate : float
            The maximum annual utilisation rate of a technology type in the network. Default is 0.85 (i.e., 85% max utlisation rate annually).
        
        carriers : list
            A list of carriers to apply the constraint to. Default is None, which does not apply the constraint to any carriers in the network.
            
        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------
    
        None
    
    '''

    # ----- constr: coal and gas max utilisation rates ----- #

    # lp_model = network.optimize.create_model()
    
    for generator_year in network.investment_periods:
        target_generators = (
            network
            .generators
            .loc[
            (network.generators.carrier.str.contains('|'.join(carriers))) &
            (network.generators.build_year <= generator_year)
            ]
            .index
            .tolist())
        print(target_generators)

        for each_generator in target_generators:

            # The generation by coal plant in the generation year
            target_generation = (
                    lp_model.variables['Generator-p']
                    .sel(
                            period=generator_year,
                            Generator=each_generator
                        )
                        .sum()
            )

            if str(network.investment_periods[0]) in each_generator:
                target_capacity = network.generators.loc[each_generator].p_nom
            else:
                target_capacity = (
                    lp_model.variables['Generator-p_nom']
                    .sel({'Generator-ext': each_generator})
                    .sum()
                )
            
            # set constraint
            lp_model.add_constraints(
                lhs = target_generation,
                sign = '<=',
                rhs =  max_utilisation_rate * target_capacity * 8760 / model_frequency,
                name=str(generator_year) + str(each_generator) + '_max_utilisation_rate',
            )
