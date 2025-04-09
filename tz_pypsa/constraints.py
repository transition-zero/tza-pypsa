import pypsa

import numpy as np
import pandas as pd


def constr_bus_self_sufficiency(
        network : pypsa.Network,
        # lp_model,
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
    # lp_model = network.optimize.create_model()

    if not buses:
        buses = (
            network
            .buses
            .loc[~network.buses.index.str.contains('C&I')] # exclude CFE related buses
            .index)
    else:
        pass

    for bus in buses:
        # get all generators at bus
        network.generators.query( f' bus == "{bus}" ').index
        # get total generation by bus
        total_gen_by_bus = ( 
            # lp_model
            network.model
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
        network.model.add_constraints(
            constraint_expression,
            name=f'min_gen_by_{bus}',
        )


def constr_cumulative_p_nom(
        network : pypsa.Network,
        # lp_model
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

    # lp_model = network.optimize.create_model()

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
            network.model
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
        network.model.add_constraints(
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
    # lp_model = network.optimize.create_model()

    lhs_total_generation = network.model.variables['Generator-p'].sel(Generator=lhs_generator).sum()

    rhs_total_theoretical_generation = (
        network.model.variables['Generator-p_nom'].sel({'Generator-ext' : lhs_generator}) * 8760 * rhs_min_generation
    )

    network.model.add_constraints(
        lhs = lhs_total_generation,
        sign = sign,
        rhs = rhs_total_theoretical_generation,
        name = name,
    )


def constr_policy_targets(
        network : pypsa.Network,
        # lp_model,
        stock_model : str
):
    '''
    ###########################################
    CONSTRAINTS FROM TARGETS AND POLICIES SHEET
    ###########################################

    Description:
    -----------------------------------
        This constraint creates custom constraints based on user-defined policies and targets.
    
    Example user story:
    -----------------------------------
        "I want to ensure total solar generation is 30% at given bus in a specific year."

    Inputs:
    -----------------------------------
    
        network : pypsa.Network
        
        lp_model : linopy model with variables and constraints
        
        stock_model : PyPSA model for a selected country / region
            
    Returns:
    -----------------------------------
    
        None
    
    '''
    # lp_model = network.optimize.create_model()

    # --- get model years --- #
    # single year investment problem        
    if network.investment_periods.empty: 
        years = network.snapshots.year.unique().tolist()
    # multi-year investment problem
    else:
        years = network.investment_periods.to_list()

    
    master_targets = pd.read_csv('stock_models/' + stock_model + '/power_sector_targets.csv')
    indices = []

    # ----- constr: absolute capacity targets ----- #
    #       This block sets absolute capacity targets. For example:
    #           - CAP_SOLAR[VNM, 2035] >= 100 MW

    countries = [i[:3] for i in network.buses.index.to_list()]

    for investment_period in years:
        
        targets_cap_abs = (
            master_targets
            #.query(" year >= @investment_period ")
            .query(" absolute == True ")
            .query(" target_type == 'capacity' ")
            .query(" nodes.str.contains('|'.join(@countries)) ")
        )

        indices += targets_cap_abs.index.to_list()

    for _, row in targets_cap_abs.iterrows():
        for generator_year in years:
            if generator_year >= row['year']:
                if network.investment_periods.empty:
                    generators_investment_years = ( 
                        network
                        .generators
                        .loc[
                            ( network.generators.bus.str.contains(row['nodes']) ) &
                            ~( network.generators.bus.str.contains('C&I') ) &
                            ( network.generators.carrier.str.contains('|'.join(row['carrier'].split(','))) ) &
                            ( network.generators.build_year <= generator_year) # &
                            # ( network.generators.build_year > years[0])
                            #( network.generators.p_nom_extendable == True)
                            ]
                        .index
                        .tolist()
                    )
                else:
                    generators_investment_years = ( 
                        network
                        .generators
                        .loc[
                            ( network.generators.bus.str.contains(row['nodes']) ) &
                            ~( network.generators.bus.str.contains('C&I') ) &
                            ( network.generators.carrier.str.contains('|'.join(row['carrier'].split(','))) ) &
                            ( network.generators.build_year <= generator_year) &
                            ( network.generators.build_year > years[0])
                            #( network.generators.p_nom_extendable == True)
                            ]
                        .index
                        .tolist()
                    )

                total_capacity_investment_years = (
                    network.model
                    .variables['Generator-p_nom']
                    .sel(
                        {
                            "Generator-ext" : generators_investment_years
                        }
                    )
                    .sum()
                    .sum()
                )
                
                total_capacity_base_year = (
                    network.generators
                    .p_nom
                    .loc[
                        (network.generators.bus.str.contains(row['nodes'])) &
                        (network.generators.carrier.str.contains('|'.join(row['carrier'].split(',')))) &
                        (network.generators.build_year == years[0])
                        ]
                    .sum()
                    )
                
                # set constraint
                network.model.add_constraints(
                    lhs = (total_capacity_investment_years 
                            + total_capacity_base_year
                            ),
                    sign = row['sense'],
                    rhs = row['value'],
                    name=str(generator_year) + str(row['year']) + '_' + row['target_type'] + '_' + row['nodes'] + '_' + row['description'].replace(' ', '_').lower(),
                )

    # ----- constr: capacity share targets ----- #
    #       This block sets capacity share targets. For example:
    #           - CAP_SOLAR[VNM, 2035] >= 35% of total capacity

    for investment_period in years:

        targets_cap_pct = (
            master_targets
            #.query(" year >= @investment_period ")
            .query(" absolute == False ")
            .query(" target_type == 'capacity' ")
            .query(" nodes.str.contains('|'.join(@countries)) ")
        )

        indices += targets_cap_pct.index.to_list()

    for _, row in targets_cap_pct.iterrows():
        for generator_year in years:
            if generator_year >= row['year']:
                if network.investment_periods.empty:
                    target_generators = (
                        network
                        .generators
                        .loc[
                            ( network.generators.bus.str.contains( row['nodes'] ) ) &
                            ~( network.generators.bus.str.contains('C&I') ) &
                            ( network.generators.carrier.str.contains('|'.join(row['carrier'].split(','))) ) &
                            ( network.generators.build_year <= generator_year) #&
                            # ( network.generators.build_year > years[0])
                            # ( network.generators.p_nom_extendable == True)
                            ]
                        .index
                        .tolist()
                        )
                else:
                    target_generators = (
                        network
                        .generators
                        .loc[
                            ( network.generators.bus.str.contains( row['nodes'] ) ) &
                            ~( network.generators.bus.str.contains('C&I') ) &
                            ( network.generators.carrier.str.contains('|'.join(row['carrier'].split(','))) ) &
                            ( network.generators.build_year <= generator_year) &
                            ( network.generators.build_year > years[0])
                            # ( network.generators.p_nom_extendable == True)
                            ]
                        .index
                        .tolist()
                    )
        
                if network.investment_periods.empty:
                    all_generators = (
                        network
                        .generators
                        .loc[
                            ( network.generators.bus.str.contains( row['nodes'] ) ) &
                            ~( network.generators.bus.str.contains('C&I') ) &
                            ( network.generators.build_year <= generator_year) #&
                            # ( network.generators.build_year > years[0])
                            # ( network.generators.p_nom_extendable == True)
                            ]
                        .index
                        .tolist()
                    )
                else:
                    all_generators = (
                        network
                        .generators
                        .loc[
                            ( network.generators.bus.str.contains( row['nodes'] ) ) &
                            ~( network.generators.bus.str.contains('C&I') ) &
                            ( network.generators.build_year <= generator_year) &
                            ( network.generators.build_year > years[0])
                            # ( network.generators.p_nom_extendable == True)
                        ]
                        .index
                        .tolist()
                    )
                
                target_capacity_base_year = (
                    network.generators
                    .p_nom
                    .loc[
                        (network.generators.bus.str.contains(row['nodes'])) &
                        (network.generators.carrier.str.contains('|'.join(row['carrier'].split(',')))) &
                        (network.generators.build_year == years[0])
                        ]
                    .sum()
                    )
                
                all_capacity_base_year = (
                    network.generators
                    .p_nom
                    .loc[
                        (network.generators.bus.str.contains(row['nodes'])) &
                        (network.generators.build_year == years[0])
                        ]
                    .sum()
                    )
        
                target_capacity = (network.model.variables['Generator-p_nom'].sel({'Generator-ext': target_generators}).sum()
                                + target_capacity_base_year
                                )
                total_capacity = (network.model.variables['Generator-p_nom'].sel({'Generator-ext': all_generators}).sum()
                                + all_capacity_base_year
                                )

                # set constraint
                network.model.add_constraints(
                    lhs = target_capacity - ((row['value']/100)*total_capacity),
                    sign = row['sense'],
                    rhs = 0,
                    name=str(generator_year) + str(row['year']) + '_' + row['target_type'] + '_' + row['nodes'] + '_' + row['description'].replace(' ', '_').lower(),
                )

    # ----- constr: generation share targets ----- #
    #       This block sets generation share targets. For example:
    #           - %_SOLAR[VNM, 2035] >= 20% of total generation

    for investment_period in years:

        targets = (
            master_targets
            #.query(" year >= @investment_period ")
            .query(" absolute == False ")
            .query(" target_type == 'generation' ")
            .query(" nodes.str.contains('|'.join(@countries)) ")
        )

        indices += targets.index.to_list()

    for _, row in targets.iterrows():
        for generator_year in years:
            if generator_year >= row['year']:

                target_generators = (
                    network
                    .generators
                    .loc[
                        (network.generators.carrier.str.contains('|'.join(row['carrier'].split(',')))) &
                        (network.generators.bus.str.contains(row['nodes'])) &
                        (network.generators.build_year <= generator_year)
                    ]
                    .index
                    .tolist()
                )

                all_generators = (
                    network
                    .generators
                    .loc[
                        (network.generators.bus.str.contains(row['nodes'])) & 
                        (network.generators.build_year <= generator_year)
                    ]
                    .index
                    .tolist()
                )

                # single year investment problem
                if network.investment_periods.empty:
                    target_generation = network.model.variables['Generator-p'].sel(Generator=target_generators).sum()
                    total_generation = network.model.variables['Generator-p'].sel(Generator=all_generators).sum()
                # multi-year investment problem
                else:
                    target_generation = network.model.variables['Generator-p'].sel(period=generator_year,
                                                                                Generator=target_generators).sum()
                    total_generation = network.model.variables['Generator-p'].sel(period=generator_year, 
                                                                                Generator=all_generators).sum()
                
                # set constraint
                network.model.add_constraints(
                    lhs = target_generation - ((row['value']/100)*total_generation),
                    sign = row['sense'],
                    rhs =  0,
                    name=str(generator_year) + str(row['year']) + '_' + row['target_type'] + '_' + row['nodes'] + '_' + row['description'].replace(' ', '_').lower(),
                )

    # ----- constr: absolute emissions targets ----- #

    emissions = network.carriers.co2_emissions[lambda ds: ds != 0]

    for investment_period in years:

        targets = (
            master_targets
            #.query(" year >= @investment_period ")
            .query(" absolute == True ")
            .query(" target_type == 'emissions' ")
            .query(" nodes.str.contains('|'.join(@countries)) ")
        )

        indices += targets.index.to_list()

    for _, row in targets.iterrows():
        for generator_year in years:
            if generator_year >= row['year']:
                
                target_generators = (
                    network
                    .generators
                    .loc[
                        (network.generators.carrier.isin(emissions.index)) &
                        (network.generators.bus.str.contains(row['nodes'])) &
                        (network.generators.build_year <= generator_year)
                    ]
                    )

                generator_efficiency = network.generators.efficiency

                emission_factor = (target_generators.carrier.map(emissions) / generator_efficiency).dropna()

                target_generators_list = target_generators.index.to_list()

                # single year investment problem
                if network.investment_periods.empty: 
                    total_emissions = (
                        (network.model.variables['Generator-p'].sel(Generator=target_generators_list) 
                                    * emission_factor)
                                    .sum()
                                    )
                # multi-year investment problem
                else: 
                    total_emissions = (
                        (network.model.variables['Generator-p'].sel(period=generator_year,Generator=target_generators_list) 
                                        * emission_factor)
                                        .sum()
                                        )
                
                # set constraint
                network.model.add_constraints(
                    lhs = total_emissions,
                    sign = row['sense'],
                    rhs =  row['value'],
                    name=str(generator_year) + str(row['year']) + '_' + row['target_type'] + '_' + row['nodes'] + '_' + row['description'].replace(' ', '_').lower(),
                )


def constr_max_annual_utilisation(
    network: pypsa.Network,
    max_utilisation_rate: float = 0.85,
    carriers: list = None,
    model_frequency: int = 1,
):
    """

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

    """

    # ----- constr: coal and gas max utilisation rates ----- #

    #network.optimize.create_model()

    # --- get model years --- #
    # single year investment problem        
    if network.investment_periods.empty: 
        years = network.snapshots.year.unique().tolist()
    # multi-year investment problem
    else:
        years = network.investment_periods.to_list()

    for generator_carrier in carriers:

        for generator_year in years:
            target_generators = network.generators.loc[
                (network.generators.carrier.str.contains(generator_carrier))
                & (network.generators.build_year <= generator_year)
            ].index.tolist()
            # print(target_generators)

            for each_generator in target_generators:

                # The generation by coal plant in the generation year
                target_generation = (
                    network.model.variables["Generator-p"].sel(Generator=each_generator).sum()
                )

                # if str(network.investment_periods[0]) in each_generator:
                #     target_capacity = network.generators.loc[each_generator].p_nom
                # else:
                
                if network.generators.p_nom_extendable[each_generator] == True:

                    target_capacity = (
                        network.model.variables["Generator-p_nom"]
                        .sel({"Generator-ext": each_generator})
                        .sum()
                )
                    
                else: 

                    target_capacity = network.generators.loc[each_generator].p_nom

                # set constraint
                network.model.add_constraints(
                    lhs=target_generation,
                    sign="<=",
                    rhs=max_utilisation_rate * target_capacity * 8760 / model_frequency,
                    name=str(generator_year)
                    + str(each_generator)
                    + "_max_utilisation_rate",
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