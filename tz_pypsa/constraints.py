import pypsa

import numpy as np
import pandas as pd


def constr_bus_self_sufficiency(
        network : pypsa.Network,
        min_self_sufficiency : float = 0.5,
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


# def constr_annual_matching(
#         network : pypsa.Network,
#         lhs_generators : list,
#         rhs_min_generation : float,
#         sign : str = '>=',
#         name : str = None,
# ):
#     '''
    
#     ###################################
#     ANNUAL MATCHING CONSTRAINT
#     ###################################

#     Description:
#     -----------------------------------
#         This constraint ensures that the total annual generation of a set of generators is greater than or equal to a certain value.
#         It is particularly useful for setting renewable generation targets. For example, one can use this constraint to ensure that 
#         a certain proportion of demand is met by renewable generation.
    
#     Example user story:
#     -----------------------------------
#         "I want to ensure that my demand is met by renewable generation across the year."

#     Inputs:
#     -----------------------------------
    
#         network : pypsa.Network

#         lhs_generators : list
#             A list of generators to apply the constraint to (e.g., all renewable generators).
        
#         rhs_min_generation : float
#             The minimum total annual generation of the set of generators (e.g., 100 = 100MW).
        
#         sign : str
#             The sign of the constraint. Default is '>='.
        
#         name : str
#             The name of the constraint. Default is None.

#     Returns:
#     -----------------------------------
    
#         None
    
#     '''

#     # get total annual renewable generation (additional)
#     lp_model = network.optimize.create_model()

#     lhs_total_generation = (
#         lp_model
#         .variables['Generator-p']
#         .sel(Generator=lhs_generators)
#         .sum()
#     )

#     lp_model.add_constraints(
#         lhs = lhs_total_generation,
#         sign = sign,
#         rhs = rhs_min_generation,
#         name = name,
#     )


# def constr_hourly_matching(
#         lp_model,
#         lhs_generators : list,
#         lhs_storages : list,
#         rhs_load : float,
#         sign : str = '>=',
#         cfe_score : float = 1.,
#         name : str = None,
# ):
#     '''
    
#     ###################################
#     HOURLY MATCHING (CFE) CONSTRAINT
#     ###################################

#     Description:
#     -----------------------------------
#         This constraint ensures that the total hourly generation of a set of generators is greater than or equal to a certain value.
#         It is particularly useful for setting renewable generation targets under a 24/7 CFE procurement strategy. For example, one can
#         use this constraint to ensure that a certain load is met by renewable generation in each hour of the year.
    
#     Example user story:
#     -----------------------------------
#         "I want to ensure that my demand is met by renewable generation in each hour of the year."

#     Inputs:
#     -----------------------------------
    
#         network : pypsa.Network

#         lhs_generators : list
#             A list of generators to apply the constraint to (e.g., all renewable generators).
        
#         rhs_min_generation : float
#             The minimum total annual generation of the set of generators (e.g., 0.5 = 50%).
        
#         sign : str
#             The sign of the constraint. Default is '>='.
        
#         name : str
#             The name of the constraint. Default is None.
            
#     Returns:
#     -----------------------------------
    
#         None
    
#     '''

#     # get hourly dispatch from clean generators
#     lhs_total_hourly_generation = (
#         lp_model
#         .variables['Generator-p']
#         .sel(Generator=lhs_generators)
#     )

#     # get hourly dispatch from storage
#     lhs_total_hourly_storage_discharge = (
#         lp_model
#         .variables['StorageUnit-p_dispatch']
#         .sel(StorageUnit=lhs_storages)
#     )

#     lhs_dispatch = lhs_total_hourly_generation + lhs_total_hourly_storage_discharge

#     lp_model.add_constraints(
#         lhs = lhs_dispatch,
#         sign = sign,
#         rhs = cfe_score * rhs_load,
#         #name = name,
#     )

def constr_cofiring_ccs_generation_join_plant(
    network: pypsa.Network,
    clean_generator : list = None,
    fossil_generator: list = None,
    model_frequency: int = 1,
):
    """

    ###################################
    COFIRING CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total output of two power plants (representing
        a single cofiring/blended fuel plant) is equal to the share of generation from the clean and 
        fossil components. For example, if in a gas-hydrogen blended plant the hydrogen (0 g CO2/kWh)
        represents 10% of the total generation output, the clean component will be limited to 10% of output 
        and the fossil share will be 90%.

    Example user story:
    -----------------------------------
        "I want to ensure that a blended or cofiring plant is constrained that if it is operating then 
        the correct shares of clean and fossil components are output"

    Inputs:
    -----------------------------------

        network : pypsa.Network

        clean_generator: List
            List of clean generators

        fossil_generators: List
            List of fossil generators

        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------

        None

    """
    for generator_year in network.investment_periods:
        target_generators = network.generators.loc[
            (network.generators.is_blend_or_ccs == True)
            & (network.generators.build_year <= generator_year)
        ].index.tolist()
        print(target_generators)

        production_fossil_force_blend = network.model.variables['Generator-p'].sel(Generator=clean_generator) / ((network.generators.loc[clean_generator].generation_blend_share) / (1 - network.generators.loc[clean_generator].generation_blend_share))
        production_fossil = network.model.variables['Generator-p'].sel(Generator=fossil_generator)
        

    network.model.add_constraints(
    lhs=production_fossil / model_frequency,
    sign="==",
    rhs = production_fossil_force_blend / model_frequency,
    name = "cofiring_constrain_generation_from_fossil_component",
            )
