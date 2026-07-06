import pypsa
import numpy as np
import pandas as pd
import xarray as xr
from tz_pypsa.helpers import load_soc_bounds_as_xarray


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

        min_self_sufficiency = network.buses.min_self_sufficiency
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
        if any(carrier in network.generators.carrier.to_list() for carrier in row['carrier'].split(',')):
            plant_type = "generators"
            model_variable = 'Generator-p_nom'
        elif any(carrier in network.storage_units.carrier.to_list() for carrier in row['carrier'].split(',')):
            plant_type = "storage_units"
            model_variable = 'StorageUnit-p_nom'
        for generator_year in years:
            if generator_year >= row['year']:
                if network.investment_periods.empty:
                    generators_investment_years = ( 
                        getattr(network, plant_type)
                        .loc[
                            ( getattr(network, plant_type).bus.str.contains(row['nodes']) ) &
                            ~( getattr(network, plant_type).bus.str.contains('C&I') ) &
                            ( getattr(network, plant_type).carrier.str.contains('|'.join(row['carrier'].split(','))) ) &
                            ( getattr(network, plant_type).build_year <= generator_year) &
                            # ( getattr(network, plant_type).build_year > years[0])
                            ( getattr(network, plant_type).p_nom_extendable == True)
                            ]
                        .index
                        .tolist()
                    )
                else:
                    generators_investment_years = ( 
                        getattr(network, plant_type)
                        .loc[
                            ( getattr(network, plant_type).bus.str.contains(row['nodes']) ) &
                            ~( getattr(network, plant_type).bus.str.contains('C&I') ) &
                            ( getattr(network, plant_type).carrier.str.contains('|'.join(row['carrier'].split(','))) ) &
                            ( getattr(network, plant_type).build_year <= generator_year) &
                            ( getattr(network, plant_type).build_year > years[0]) &
                            ( getattr(network, plant_type).p_nom_extendable == True)
                            ]
                        .index
                        .tolist()
                    )

                total_capacity_investment_years = (
                    network.model
                    .variables[model_variable]
                    .sel(
                        {
                            model_variable.replace('-p_nom', '') + "-ext": generators_investment_years
                        }
                    )
                    .sum()
                    .sum()
                )
                
                total_capacity_base_year = (
                    getattr(network, plant_type)
                    .p_nom
                    .loc[
                        (getattr(network, plant_type).bus.str.contains(row['nodes'])) &
                        ~( getattr(network, plant_type).bus.str.contains('C&I') ) &
                        (getattr(network, plant_type).carrier.str.contains('|'.join(row['carrier'].split(',')))) &
                        (getattr(network, plant_type).build_year <= years[0])
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
                            ( network.generators.build_year <= generator_year) &
                            # ( network.generators.build_year > years[0])
                            ( network.generators.p_nom_extendable == True)
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
                            ( network.generators.build_year > years[0]) &
                            ( network.generators.p_nom_extendable == True)
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
                            ( network.generators.build_year <= generator_year) &
                            # ( network.generators.build_year > years[0])
                            ( network.generators.p_nom_extendable == True)
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
                            ( network.generators.build_year > years[0]) &
                            ( network.generators.p_nom_extendable == True)
                        ]
                        .index
                        .tolist()
                    )
                
                target_capacity_base_year = (
                    network.generators
                    .p_nom
                    .loc[
                        (network.generators.bus.str.contains(row['nodes'])) &
                        ~( network.generators.bus.str.contains('C&I') ) &
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
                        ~( network.generators.bus.str.contains('C&I') ) &
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
                        ~( network.generators.bus.str.contains('C&I') ) &
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
                        ~( network.generators.bus.str.contains('C&I') ) &
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

    for generator_year in network.investment_periods:
        target_generators = network.generators.loc[
            (network.generators.carrier.str.contains(carriers))
            & (network.generators.build_year <= generator_year)
        ].index.tolist()
        print(target_generators)

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

def constr_min_annual_utilisation_links(
    network: pypsa.Network,
    carriers: str = None,
    model_frequency: int = 1,
):
    """

    ###################################
    MAXIMUM ANNUAL UTILISATION CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual utilisation rate of an interconnector
        is at least a certain, must run, percentage value.

    Example user story:
    -----------------------------------
        "I want to ensure that interconnector x is operating at least y% annually%"

    Inputs:
    -----------------------------------

        network : pypsa.Network

        carriers : list
            A list of carriers to apply the constraint to. Default is None, which does not apply the constraint to any carriers in the network.

        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------

        None

    """

    # ----- constr: interconnector min utilisation rates ----- #


    target_links = network.links.loc[
            (network.links.carrier.str.contains(carriers)) & (network.links.min_utilisation_rate.notna())
        ].index.tolist()
    print(target_links)

    for each_link in target_links:

            # The output by each interconnector in each year
            target_links_output = (
                network.model.variables["Link-p"].sel(Link=each_link).sum()
            )
            
            if network.links.p_nom_extendable[each_link] == True:

                target_capacity = (
                    network.model.variables["Link-p_nom"]
                    .sel({"Link-ext": each_link})
                    .sum()
                )

                # minimum utilisation rate set by user in network.links - means minimum rates can be set at a link level  
                min_utilisation_rate = (
                    network.links.loc[each_link].min_utilisation_rate
                )

                
            else: 

                target_capacity = network.links.loc[each_link].p_nom

                min_utilisation_rate = (
                    network.links.loc[each_link].min_utilisation_rate
                )

            # set constraint
            network.model.add_constraints(
                lhs=target_links_output,
                sign=">=",
                rhs=min_utilisation_rate * target_capacity * 8760 / model_frequency,
                name=str(carriers)
                + str(each_link)
                + "_min_utilisation_rate",
            )


def constr_bus_individual_self_sufficiency(
        network : pypsa.Network,
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

    buses = network.buses.index

    for bus in buses:
        # get all generators at bus
        network.generators.query( f' bus == "{bus}" ').index
        # get total generation by bus
        total_gen_by_bus = ( 
            network
            .model
            .variables['Generator-p']
            .sel(
                Generator=network.generators.query( f' bus == "{bus}" ').index
            )
            .sum()
            .sum()
        )

        min_self_sufficiency = network.buses.loc[bus].min_self_sufficiency
        # get demand at bus
        total_demand_by_bus = network.loads_t.p_set[bus].sum(axis=0)
        # set expression
        constraint_expression = total_gen_by_bus >= total_demand_by_bus * min_self_sufficiency
        # set constraint
        network.model.add_constraints(
            constraint_expression,
            name=f'min_gen_by_individual_{bus}',
        )

        
def constr_max_annual_utilisation_links(
    network: pypsa.Network,
    carriers: str = None,
    model_frequency: int = 1,
):
    """

    ###################################
    MAXIMUM ANNUAL UTILISATION CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual utilisation rate of an interconnector
        is at most a user-defined percentage value.

    Example user story:
    -----------------------------------
        "I want to ensure that interconnector x is operating at a maximum y% annually%"

    Inputs:
    -----------------------------------

        network : pypsa.Network

        carriers : list
            A list of carriers to apply the constraint to. Default is None, which does not apply the constraint to any carriers in the network.

        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------

        None

    """

    # ----- constr: interconnector max utilisation rates ----- #


    target_links = network.links.loc[
            (network.links.carrier.str.contains(carriers)) & (network.links.max_utilisation_rate.notna())
        ].index.tolist()
    print(target_links)

    for each_link in target_links:

            # The output by each interconnector in each year
            target_links_output = (
                network.model.variables["Link-p"].sel(Link=each_link).sum()
            )
            
            
            if network.links.p_nom_extendable[each_link] == True:

                target_capacity = (
                    network.model.variables["Link-p_nom"]
                    .sel({"Link-ext": each_link})
                    .sum()
                )

                # maximum utilisation rate set by user in network.links - means maximum rates can be set at a link level  
                max_utilisation_rate = (
                    network.links.loc[each_link].max_utilisation_rate
                )

                
            else: 

                target_capacity = network.links.loc[each_link].p_nom

                max_utilisation_rate = (
                    network.links.loc[each_link].max_utilisation_rate
                )

            # set constraint
            network.model.add_constraints(
                lhs=target_links_output,
                sign="<=",
                rhs=max_utilisation_rate * target_capacity * 8760 / model_frequency,
                name=str(carriers)
                + str(each_link)
                + "_max_utilisation_rate",
            )

            
def constr_min_annual_utilisation_generator(
    network: pypsa.Network,
    carriers: list = None,
    model_frequency: int = 1,
):
    """

    Inputs:
    -----------------------------------

        network : pypsa.Network

        carriers : list
            A list of carriers to apply the constraint to. Default is None, which does not apply the constraint to any carriers in the network.

        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------

        None

    """
        
    # ----- constr: generator min utilisation rates ----- #

    target_generators = network.generators.loc[
            (network.generators.carrier.str.contains(carriers)) & (network.generators.min_utilisation_rate.notna())
        ].index.tolist()
    print(target_generators)

    for each_generator in target_generators:

            # The output by each generator in each year
            target_generators_output = (
                network.model.variables["Generator-p"].sel(Generator=each_generator).sum()
            )
            
            if network.generators.p_nom_extendable[each_generator] == True:

                target_capacity = (
                    network.model.variables["Generator-p_nom"]
                    .sel({"Generator-ext": each_generator})
                    .sum()
                )

                # minimum utilisation rate set by user in network.generators - means minimum rates can be set at a generator level  
                min_utilisation_rate = (
                    network.generators.loc[each_generator].min_utilisation_rate
                )

                
            else: 

                target_capacity = network.generators.loc[each_generator].p_nom

                min_utilisation_rate = (
                    network.generators.loc[each_generator].min_utilisation_rate
                )

            # set constraint
            network.model.add_constraints(
                lhs=target_generators_output,
                sign=">=",
                rhs=min_utilisation_rate * target_capacity * 8760 / model_frequency,
                name=str(carriers)
                + str(each_generator)
                + "_min_utilisation_rate",
            )


def constr_max_annual_utilisation_generator(
    network: pypsa.Network,
    carriers: list = None,
    model_frequency: int = 1,
):
    """

    ###################################
    MAXIMUM ANNUAL UTILISATION CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual utilisation rate of a generator
        is a maximum of a percentage value.

    Example user story:
    -----------------------------------
        "I want to ensure that generator x is operating at a maximum of y% annually%"

    Inputs:
    -----------------------------------

        network : pypsa.Network

        carriers : list
            A list of carriers to apply the constraint to. Default is None, which does not apply the constraint to any carriers in the network.

        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------

        None

    """

    # ----- constr: generator max utilisation rates ----- #


    target_generators = network.generators.loc[
            (network.generators.carrier.str.contains(carriers)) & (network.generators.max_utilisation_rate.notna())
        ].index.tolist()
    print(target_generators)

    for each_generator in target_generators:

            # The output by each interconnector in each year
            target_generators_output = (
                network.model.variables["Generator-p"].sel(Generator=each_generator).sum()
            )
            
            if network.generators.p_nom_extendable[each_generator] == True:

                target_capacity = (
                    network.model.variables["Generator-p_nom"]
                    .sel({"Generator-ext": each_generator})
                    .sum()
                )

                # max utilisation rate set by user in network.generators - means max rates can be set at a generator level  
                max_utilisation_rate = (
                    network.generators.loc[each_generator].max_utilisation_rate
                )

                
            else: 

                target_capacity = network.generators.loc[each_generator].p_nom

                max_utilisation_rate = (
                    network.generators.loc[each_generator].max_utilisation_rate
                )

            # set constraint
            network.model.add_constraints(
                lhs=target_generators_output,
                sign="<=",
                rhs=max_utilisation_rate * target_capacity * 8760 / model_frequency,
                name=str(carriers)
                + str(each_generator)
                + "_max_utilisation_rate",
            )

def constr_max_annual_utilisation_storage_discharge(
    network: pypsa.Network,
    carriers: list = None,
    model_frequency: int = 1,
):
    """

    ###################################
    MAXIMUM ANNUAL UTILISATION CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual utilisation rate of a storage unit
        is a maximum of a percentage value.

    Example user story:
    -----------------------------------
        "I want to ensure that storage unit x is operating at a maximum of y% annually%"

    Inputs:
    -----------------------------------

        network : pypsa.Network

        carriers : list
            A list of carriers to apply the constraint to. Default is None, which does not apply the constraint to any carriers in the network.

        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------

        None

    """

    # ----- constr: storage unit max utilisation rates ----- #


    target_storage_units = network.storage_units.loc[
            (network.storage_units.carrier.str.contains(carriers)) & (network.storage_units.discharge_max_utilisation_rate.notna())
        ].index.tolist()
    print(target_storage_units)

    for each_storage_unit in target_storage_units:

            # The dispatch by each storage unit in each year
            target_storage_units_dispatch = (
                network.model.variables["StorageUnit-p_dispatch"].sel(StorageUnit=each_storage_unit).sum()
            )
            
            if network.storage_units.p_nom_extendable[each_storage_unit] == True:

                target_capacity = (
                    network.model.variables["StorageUnit-p_nom"]
                    .sel({"StorageUnit-ext": each_storage_unit})
                    .sum()
                )

                # max utilisation rate set by user in network.generators - means max rates can be set at a generator level  
                discharge_max_utilisation_rate = (
                    network.storage_units.loc[each_storage_unit].discharge_max_utilisation_rate
                )

                
            else: 

                target_capacity = network.storage_units.loc[each_storage_unit].p_nom

                discharge_max_utilisation_rate = (
                    network.storage_units.loc[each_storage_unit].discharge_max_utilisation_rate
                )

            # set constraint
            network.model.add_constraints(
                lhs=target_storage_units_dispatch,
                sign="<=",
                rhs=discharge_max_utilisation_rate * target_capacity * 8760 / model_frequency,
                name=str(carriers)
                + str(each_storage_unit)
                + "_discharge_max_utilisation_rate",
            )

def constr_max_annual_utilisation_storage_charge(
    network: pypsa.Network,
    carriers: list = None,
    model_frequency: int = 1,
):
    """

    ###################################
    MAXIMUM ANNUAL UTILISATION CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual utilisation rate of a storage unit
        is a maximum of a percentage value.

    Example user story:
    -----------------------------------
        "I want to ensure that storage unit x is operating at a maximum of y% annually%"

    Inputs:
    -----------------------------------

        network : pypsa.Network

        carriers : list
            A list of carriers to apply the constraint to. Default is None, which does not apply the constraint to any carriers in the network.

        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------

        None

    """

    # ----- constr: storage unit max utilisation rates ----- #


    target_storage_units = network.storage_units.loc[
            (network.storage_units.carrier.str.contains(carriers)) & (network.storage_units.charge_max_utilisation_rate.notna())
        ].index.tolist()
    print(target_storage_units)

    for each_storage_unit in target_storage_units:

            # The store by each storage unit in each year
            target_storage_units_store = (
                network.model.variables["StorageUnit-p_store"].sel(StorageUnit=each_storage_unit).sum()
            )
            
            if network.storage_units.p_nom_extendable[each_storage_unit] == True:

                target_capacity = (
                    network.model.variables["StorageUnit-p_nom"]
                    .sel({"StorageUnit-ext": each_storage_unit})
                    .sum()
                )

                # max utilisation rate set by user in network.generators - means max rates can be set at a generator level  
                charge_max_utilisation_rate = (
                    network.storage_units.loc[each_storage_unit].charge_max_utilisation_rate
                )

                
            else: 

                target_capacity = network.storage_units.loc[each_storage_unit].p_nom

                charge_max_utilisation_rate = (
                    network.storage_units.loc[each_storage_unit].charge_max_utilisation_rate
                )

            # set constraint
            network.model.add_constraints(
                lhs=target_storage_units_store,
                sign="<=",
                rhs=charge_max_utilisation_rate * target_capacity * 8760 / model_frequency,
                name=str(carriers)
                + str(each_storage_unit)
                + "_charge_max_utilisation_rate",
            )

def constr_min_annual_utilisation_storage_discharge(
    network: pypsa.Network,
    carriers: list = None,
    model_frequency: int = 1,
):
    """

    ###################################
    MAXIMUM ANNUAL UTILISATION CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual utilisation rate of a storage unit
        is a minimum of a percentage value.

    Example user story:
    -----------------------------------
        "I want to ensure that storage unit x is operating at a minimum of y% annually%"

    Inputs:
    -----------------------------------

        network : pypsa.Network

        carriers : list
            A list of carriers to apply the constraint to. Default is None, which does not apply the constraint to any carriers in the network.

        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------

        None

    """

    # ----- constr: storage unit min utilisation rates ----- #


    target_storage_units = network.storage_units.loc[
            (network.storage_units.carrier.str.contains(carriers)) & (network.storage_units.discharge_min_utilisation_rate.notna())
        ].index.tolist()
    print(target_storage_units)

    for each_storage_unit in target_storage_units:

            # The dispatch by each storage unit in each year
            target_storage_units_dispatch = (
                network.model.variables["StorageUnit-p_dispatch"].sel(StorageUnit=each_storage_unit).sum()
            )
            
            if network.storage_units.p_nom_extendable[each_storage_unit] == True:

                target_capacity = (
                    network.model.variables["StorageUnit-p_nom"]
                    .sel({"StorageUnit-ext": each_storage_unit})
                    .sum()
                )

                # minimum utilisation rate set by user in network.storage_units - means minimum rates can be set at a storage unit level  
                discharge_min_utilisation_rate = (
                    network.storage_units.loc[each_storage_unit].discharge_min_utilisation_rate
                )

                
            else: 

                target_capacity = network.storage_units.loc[each_storage_unit].p_nom

                discharge_min_utilisation_rate = (
                    network.storage_units.loc[each_storage_unit].discharge_min_utilisation_rate
                )

            # set constraint
            network.model.add_constraints(
                lhs=target_storage_units_dispatch,
                sign=">=",
                rhs=discharge_min_utilisation_rate * target_capacity * 8760 / model_frequency,
                name=str(carriers)
                + str(each_storage_unit)
                + "_discharge_min_utilisation_rate",
            )

def constr_min_annual_utilisation_storage_charge(
    network: pypsa.Network,
    carriers: list = None,
    model_frequency: int = 1,
):
    """

    ###################################
    MAXIMUM ANNUAL UTILISATION CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that the total annual utilisation rate of a storage unit
        is a minimum of a percentage value.

    Example user story:
    -----------------------------------
        "I want to ensure that storage unit x is operating at a minimum of y% annually%"

    Inputs:
    -----------------------------------

        network : pypsa.Network

        carriers : list
            A list of carriers to apply the constraint to. Default is None, which does not apply the constraint to any carriers in the network.

        model_frequency : int
            Integer representing the model frequency in hours. Default is 1.

    Returns:
    -----------------------------------

        None

    """

    # ----- constr: storage unit min utilisation rates ----- #


    target_storage_units = network.storage_units.loc[
            (network.storage_units.carrier.str.contains(carriers)) & (network.storage_units.charge_min_utilisation_rate.notna())
        ].index.tolist()
    print(target_storage_units)

    for each_storage_unit in target_storage_units:

            # The dispatch by each storage unit in each year
            target_storage_units_store = (
                network.model.variables["StorageUnit-p_store"].sel(StorageUnit=each_storage_unit).sum()
            )
            
            if network.storage_units.p_nom_extendable[each_storage_unit] == True:

                target_capacity = (
                    network.model.variables["StorageUnit-p_nom"]
                    .sel({"StorageUnit-ext": each_storage_unit})
                    .sum()
                )

                # minimum utilisation rate set by user in network.storage_units - means minimum rates can be set at a storage unit level  
                charge_min_utilisation_rate = (
                    network.storage_units.loc[each_storage_unit].charge_min_utilisation_rate
                )

                
            else: 

                target_capacity = network.storage_units.loc[each_storage_unit].p_nom

                charge_min_utilisation_rate = (
                    network.storage_units.loc[each_storage_unit].charge_min_utilisation_rate
                )

            # set constraint
            network.model.add_constraints(
                lhs=target_storage_units_store,
                sign=">=",
                rhs=charge_min_utilisation_rate * target_capacity * 8760 / model_frequency,
                name=str(carriers)
                + str(each_storage_unit)
                + "_charge_min_utilisation_rate",
            )


def constr_soc_intraday_profile(
    network: pypsa.Network, 
    min_csv: str, 
    max_csv: str, 
):

    bounds_ds = load_soc_bounds_as_xarray(min_csv, max_csv, 'hour')
    
    # Align StorageUnits
    common_units = list(set(bounds_ds.StorageUnit.values) & set(network.storage_units.index))
    
    if not common_units:
        print("No matching storage units found.")
        return

    # Slice the input dataset to matches
    targets = bounds_ds.sel(StorageUnit=common_units)
    
    # Process RHS
    # Vectorise capacity
    p_nom = network.storage_units.loc[common_units, 'p_nom']
    max_hours = network.storage_units.loc[common_units, 'max_hours']
    capacity = xr.DataArray(
        p_nom * max_hours, 
        dims="StorageUnit", 
        coords={"StorageUnit": common_units}
    )
    
    # Vectorise day_counts
    snapshot_counts = network.snapshots.get_level_values('timestep').hour.value_counts().sort_index()
    counts_array = snapshot_counts.values
    hours_array = snapshot_counts.index.values 
    days_count = xr.DataArray(
        counts_array, 
        dims="hour", 
        coords={"hour": hours_array} 
    )

    rhs_base = capacity * days_count

    # Process LHS
    soc_vars = network.model.variables["StorageUnit-state_of_charge"].sel(StorageUnit=common_units)
    soc_hourly_sum = soc_vars.groupby("timestep.hour").sum()

    # Min and Max constraints
    if 'min_frac' in targets:
        network.model.add_constraints(
            soc_hourly_sum >= targets['min_frac'] * rhs_base,
            name="StorageUnit-intraday_soc_min",
            mask=targets['min_frac'].notnull()
        )

    if 'max_frac' in targets:
        network.model.add_constraints(
            soc_hourly_sum <= targets['max_frac'] * rhs_base,
            name="StorageUnit-intraday_soc_max",
            mask=targets['max_frac'].notnull()
        )
        
    print(f"Intraday SOC constraints added for {len(common_units)} units.")


def constr_soc_weekly_profile(
    network: pypsa.Network, 
    min_csv: str, 
    max_csv: str, 
    day_shift: int = 0
):
    
    bounds_ds = load_soc_bounds_as_xarray(min_csv, max_csv, 'dayofweek')

    # Align StorageUnits
    common_units = list(set(bounds_ds.StorageUnit.values) & set(network.storage_units.index))
    if not common_units:
        print("No matching storage units found.")
        return

    targets = bounds_ds.sel(StorageUnit=common_units)

    # Vectorise capacity
    p_nom = network.storage_units.loc[common_units, 'p_nom']
    max_hours = network.storage_units.loc[common_units, 'max_hours']
    capacity = xr.DataArray(
        (p_nom * max_hours).values, 
        dims="StorageUnit", 
        coords={"StorageUnit": common_units}
    )
    
    # Process LHS
    soc_vars = network.model.variables["StorageUnit-state_of_charge"].sel(StorageUnit=common_units)
    
    # Extract MultiIndex to ensure safe alignment
    multi_index = soc_vars.indexes['snapshot']
    timestamps = multi_index.get_level_values(1) # Assumes level 1 is datetime
    
    # Calculate day integers (0=Mon, 6=Sun) with optional shift
    # If day_shift=0, this is standard dayofweek
    day_ints = (timestamps.dayofweek + day_shift) % 7
    
    grouper_name = "dayofweek" if day_shift == 0 else "shifted_dayofweek"

    # Create DataArray for custom grouping
    grouper = xr.DataArray(
        day_ints,
        dims="snapshot",              # Matches PyPSA variable dim
        coords={"snapshot": multi_index}, # Matches PyPSA variable coords
        name=grouper_name
    )
    
    # LHS: Sum SOC per day-bucket
    soc_sum = soc_vars.groupby(grouper).sum()
    counts_series = pd.Series(day_ints).value_counts().sort_index()
    
    days_count = xr.DataArray(
        counts_series.values,
        dims=grouper_name, 
        coords={grouper_name: counts_series.index.values} 
    )

    # Create RHS
    if grouper_name != "dayofweek" and "dayofweek" in targets.dims:
         targets = targets.rename({"dayofweek": grouper_name})

    rhs_base = capacity * days_count

    # Min and Max Constraints
    if 'min_frac' in targets:
        network.model.add_constraints(
            soc_sum >= targets['min_frac'] * rhs_base,
            name=f"StorageUnit-weekly_soc_min",
            mask=targets['min_frac'].notnull()
        )

    if 'max_frac' in targets:
        network.model.add_constraints(
            soc_sum <= targets['max_frac'] * rhs_base,
            name=f"StorageUnit-weekly_soc_max",
            mask=targets['max_frac'].notnull()
        )
    
    print(f"Weekly SOC constraints added for {len(common_units)} units.")
        
        
# def constr_max_ramps_daily(
#     network: pypsa.Network, 
#     carriers: str, 
#     ramp_threshold: float = 1
# ):
#     """
#     Constrain the maximum number of ramps per day for generators.
#     Specifying the integer limit for that specific generator.
#     Specifying ramp_threshold that like to be
#     """
    
#     # Filter for generators with the targeted carrier AND defined max daily ramp
#     target_gens = network.generators.index[
#         (network.generators.carrier.str.contains(carriers)) & 
#         (network.generators["max_ramps_per_day"].notna()) &
#         (network.generators.p_nom > 0)
#     ]

#     if target_gens.empty:
#         print(f"No generators found with carrier '{carriers}' and limits defined.")
#         return

#     # p_nom will be set equal to the big M constraint 
#     # Convert p_nom to xarray for automatic alignment
#     p_nom = xr.DataArray(
#         network.generators.loc[target_gens, 'p_nom'],
#         dims="Generator",
#         coords={"Generator": target_gens}
#     )
    
#     # Get limit values aligned by generator
#     daily_limits = xr.DataArray(
#         network.generators.loc[target_gens, "max_ramps_per_day"],
#         dims="Generator",
#         coords={"Generator": target_gens}
#     )

#     # Setup is_ramping variable
#     is_ramping = network.model.add_variables(
#         binary=True,
#         coords=[network.snapshots, target_gens],
#         name='is_ramping'
#     )

#     # Get dispatch variables & align
#     # p_curr: t=1 to end
#     # p_prev: t=0 to end-1
#     p = network.model.variables['Generator-p'].sel(Generator=target_gens)
#     p_curr = p.isel(snapshot=slice(1, None))
#     p_prev = p.shift(snapshot=1).isel(snapshot=slice(1, None))
#     ramping_curr = is_ramping.isel(snapshot=slice(1, None))

#     # Ramping Constraints (Big-M)
#     # (p_t - p_t-1) - ramp_threshold <= p_nom * is_ramping
#     # Suppose (p_t - p_t-1) = 100 and p_nom = 100:
#     # 100 - 1 = 99, 99 <= 100 * is_ramping [0,1]. Solver will have to set is_ramping = 1 to satisfy the constraint.
#     # Suppose (p_t - p_t-1) = 0 and p_nom = 100:
#     # 0 - 1 = -1, -1 <= 100 * is_ramping [0,1]. In this case, solver can set both 0 and 1 to satisfy the constraint. 
#     # To ensure solver choose 0, we will later add a small penalty to is_ramping to the objective function
#     network.model.add_constraints(
#         (p_curr - p_prev) - ramp_threshold <= ramping_curr * p_nom,
#         name='ramp_up_detect'
#     )

#     # (p_t-1 - p_t) - ramp_threshold <= p_nom * is_ramping
#     # Same logic as above applies to ramp_down_detect
#     network.model.add_constraints(
#         (p_prev - p_curr) - ramp_threshold <= ramping_curr * p_nom,
#         name='ramp_down_detect'
#     )

#     # Daily Limit Constraint
#     timestamps = network.snapshots.get_level_values("timestep")
#     day_grouper = xr.DataArray(
#         timestamps.floor("D"), 
#         coords={"snapshot": network.snapshots}, 
#         dims="snapshot"
#     )
#     daily_counts = is_ramping.groupby(day_grouper).sum()
#     network.model.add_constraints(
#         daily_counts <= daily_limits,
#         name='max_ramps_per_day'
#     )

#     # Prevents solver setting is_ramping = 1 when not needed
#     # Weight is small enough to not affect dispatch cost, but > 0
#     network.model.objective += 10 * is_ramping.sum()

#     print(f"Max ramp constraints added for {len(target_gens)} generators.")

# def constr_min_ramps_daily(
#     network: pypsa.Network, 
#     carriers: str, 
#     ramp_threshold: float = 1
# ):
#     """
#     Constrain the minimum number of ramps per day for generators.
#     Specifying the integer limit for that specific generator.
#     Specifying ramp_threshold that like to be
#     """
    
#     # Filter for generators with the targeted carrier AND defined min daily ramp
#     target_gens = network.generators.index[
#         (network.generators.carrier.str.contains(carriers)) & 
#         (network.generators["min_ramps_per_day"].notna())
#     ]

#     if target_gens.empty:
#         print(f"No generators found with carrier '{carriers}' and limits defined.")
#         return

#     # p_nom will be set equal to the big M constraint 
#     # Convert p_nom to xarray for automatic alignment
#     p_nom = xr.DataArray(
#         network.generators.loc[target_gens, 'p_nom'],
#         dims="Generator",
#         coords={"Generator": target_gens}
#     )
    
#     # Get limit values aligned by generator
#     daily_limits = xr.DataArray(
#         network.generators.loc[target_gens, "min_ramps_per_day"],
#         dims="Generator",
#         coords={"Generator": target_gens}
#     )

#     # Setup is_ramping variable
#     is_ramping = network.model.add_variables(
#         binary=True,
#         coords=[network.snapshots, target_gens],
#         name='is_ramping'
#     )

#     # Get dispatch variables & align
#     # p_curr: t=1 to end
#     # p_prev: t=0 to end-1
#     p = network.model.variables['Generator-p'].sel(Generator=target_gens)
#     p_curr = p.isel(snapshot=slice(1, None))
#     p_prev = p.shift(snapshot=1).isel(snapshot=slice(1, None))
#     ramping_curr = is_ramping.isel(snapshot=slice(1, None))

#     # Ramping Constraints (Big-M)
#     # (p_t - p_t-1) - ramp_threshold <= p_nom * is_ramping
#     # Suppose (p_t - p_t-1) = 100 and p_nom = 100:
#     # 100 - 1 = 99, 99 <= 100 * is_ramping [0,1]. Solver will have to set is_ramping = 1 to satisfy the constraint.
#     # Suppose (p_t - p_t-1) = 0 and p_nom = 100:
#     # 0 - 1 = -1, -1 <= 100 * is_ramping [0,1]. In this case, solver can set both 0 and 1 to satisfy the constraint. 
#     # To ensure solver choose 0, we will later add a small penalty to is_ramping to the objective function
#     network.model.add_constraints(
#         (p_curr - p_prev) - ramp_threshold <= ramping_curr * p_nom,
#         name='ramp_up_detect'
#     )

#     # (p_t-1 - p_t) - ramp_threshold <= p_nom * is_ramping
#     # Same logic as above applies to ramp_down_detect
#     network.model.add_constraints(
#         (p_prev - p_curr) - ramp_threshold <= ramping_curr * p_nom,
#         name='ramp_down_detect'
#     )

#     # Daily Limit Constraint
#     timestamps = network.snapshots.get_level_values("timestep")
#     day_grouper = xr.DataArray(
#         timestamps.floor("D"), 
#         coords={"snapshot": network.snapshots}, 
#         dims="snapshot"
#     )
#     daily_counts = is_ramping.groupby(day_grouper).sum()
#     network.model.add_constraints(
#         daily_counts >= daily_limits,
#         name='min_ramps_per_day'
#     )

#     # Prevents solver setting is_ramping = 1 when not needed
#     # Weight is small enough to not affect dispatch cost, but > 0
#     network.model.objective += 0.00001 * is_ramping.sum()

#     print(f"Min ramp constraints added for {len(target_gens)} generators.")


            
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

    production_fossil_force_blend = network.model.variables['Generator-p'].sel(Generator=clean_generator) / ((network.generators.loc[clean_generator].generation_blend_share) / (1 - network.generators.loc[clean_generator].generation_blend_share))
    production_fossil = network.model.variables['Generator-p'].sel(Generator=fossil_generator)
        

    network.model.add_constraints(
    lhs=production_fossil / model_frequency,
    sign="==",
    rhs = production_fossil_force_blend / model_frequency,
    name = "cofiring_constrain_generation_from_fossil_component",
            )

def constr_production_target_min(
    network: pypsa.Network,
    nodes: list[str],
    technologies: list[str],
    value: float
):
    """
    ###################################
    PRODUCTION TARGET MINIMUM CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that specific technologies generate at least
        a certain percentage of total generation in specified nodes.

    Example user story:
    -----------------------------------
        "I want to ensure that solar and wind together generate at least 30%
        of total generation in the Tokyo and Osaka regions."

    Inputs:
    -----------------------------------
        network : pypsa.Network

        nodes : list[str]
            List of node names (buses) to apply the constraint to.
            Example: ['GRIDREGION-JPN-TK', 'GRIDREGION-JPN-KA']

        technologies : list[str]
            List of technology types to target.
            Example: ['solar', 'wind-onshore']

        value : float
            Minimum share of generation (0.0 to 1.0).
            Example: 0.3 means "at least 30%"

    Returns:
    -----------------------------------
        None
    """
    
    if value > 1.0 or value < 0.0:
        raise ValueError("constr_production_target_min value must be between 0.0 and 1.0")

    # Build query strings using patterns compatible with tza-pypsa
    node_pattern = '|'.join(nodes)
    tech_pattern = '|'.join(technologies)
    
    # Get generators matching BOTH technology AND node criteria
    query_string_tech_and_node = f"type.str.contains('{tech_pattern}') and bus.str.contains('{node_pattern}')"
    generators_tech_and_node = network.generators.query(query_string_tech_and_node)
    
    if generators_tech_and_node.empty:
        print(f"Warning: No generators matching technologies {technologies} in nodes {nodes}")
        print(f"Skipping constraint constr_production_target_min")
        return

    # Get ALL generators in those nodes (for denominator)
    query_string_node = f"bus.str.contains('{node_pattern}')"
    generators_node = network.generators.query(query_string_node)
    
    if generators_node.empty:
        print(f"Warning: No generators found in nodes {nodes}")
        return

    # Build constraint expression
    # Target generation (numerator)
    target_generation = (
        network.model.variables["Generator-p"]
        .sel(Generator=generators_tech_and_node.index)
        .sum()
    )
    
    # Total generation in region (denominator)
    total_generation = (
        network.model.variables["Generator-p"]
        .sel(Generator=generators_node.index)
        .sum()
    )
    
    # Constraint: target_gen >= value * total_gen
    # Rearranged: target_gen - value * total_gen >= 0
    lhs_expression = target_generation - value * total_generation
    
    # Add constraint
    network.model.add_constraints(
        lhs=lhs_expression,
        sign=">=",
        rhs=0,
        name=f"production_target_min_{'_'.join(technologies[:2])}_{'_'.join(nodes[:2])}"
    )
    
    print(f"Added production target min constraint: {tech_pattern} >= {value*100}% in {node_pattern}")


def constr_production_target_max(
    network: pypsa.Network,
    nodes: list[str],
    technologies: list[str],
    value: float
):
    """
    ###################################
    PRODUCTION TARGET MAXIMUM CONSTRAINT
    ###################################

    Description:
    -----------------------------------
        This constraint ensures that specific technologies generate at most
        a certain percentage of total generation in specified nodes.

    Example user story:
    -----------------------------------
        "I want to ensure that coal generates at most 20% of total
        generation in the Kansai region."

    Inputs:
    -----------------------------------
        network : pypsa.Network

        nodes : list[str]
            List of node names (buses) to apply the constraint to.

        technologies : list[str]
            List of technology types to target.

        value : float
            Maximum share of generation (0.0 to 1.0).

    Returns:
    -----------------------------------
        None
    """
    
    if value > 1.0 or value < 0.0:
        raise ValueError("constr_production_target_max value must be between 0.0 and 1.0")

    node_pattern = '|'.join(nodes)
    tech_pattern = '|'.join(technologies)
    
    query_string_tech_and_node = f"type.str.contains('{tech_pattern}') and bus.str.contains('{node_pattern}')"
    generators_tech_and_node = network.generators.query(query_string_tech_and_node)
    
    if generators_tech_and_node.empty:
        print(f"Warning: No generators matching technologies {technologies} in nodes {nodes}")
        print(f"Skipping constraint constr_production_target_max")
        return

    query_string_node = f"bus.str.contains('{node_pattern}')"
    generators_node = network.generators.query(query_string_node)
    
    if generators_node.empty:
        print(f"Warning: No generators found in nodes {nodes}")
        return

    target_generation = (
        network.model.variables["Generator-p"]
        .sel(Generator=generators_tech_and_node.index)
        .sum()
    )
    
    total_generation = (
        network.model.variables["Generator-p"]
        .sel(Generator=generators_node.index)
        .sum()
    )
    
    # Constraint: target_gen <= value * total_gen
    # Rearranged: target_gen - value * total_gen <= 0
    lhs_expression = target_generation - value * total_generation
    
    network.model.add_constraints(
        lhs=lhs_expression,
        sign="<=",
        rhs=0,
        name=f"production_target_max_{'_'.join(technologies[:2])}_{'_'.join(nodes[:2])}"
    )
    
    print(f"Added production target max constraint: {tech_pattern} <= {value*100}% in {node_pattern}")

def apply_ramping_cost(
        network: pypsa.Network, 
        cost_dict: dict
    ):
    """
    Applies ramping costs to multiple carriers at once using a dictionary.
    
    Parameters
    ----------
    n : pypsa.Network
    cost_dict : dict
        Key = carrier name, Value = cost ($/MW).
        Example: {'coal': 400, 'gas': 200, 'nuclear': 50}
    """
    # Identify all target generators and filter out ones with p_nom = 0
    target_carriers = list(cost_dict.keys())
    target_gens = network.generators.index[
        network.generators.carrier.isin(target_carriers) &
        (network.generators.p_nom > 0)
        ]
    
    if target_gens.empty:
        print("No matching generators found. Skipping.")
        return

    # Map costs to the generators 
    gen_carriers = network.generators.loc[target_gens, 'carrier']
    costs_per_gen = gen_carriers.map(cost_dict)
    
    # Convert to xarray for vectorisation
    costs_per_gen.index.name = "Generator"
    costs_xr = costs_per_gen.to_xarray()

    # Create ramping variables for each generator
    ramp_up = network.model.add_variables(
        coords=[network.snapshots, target_gens],
        name="ramp_up",
        lower=0
    )
    ramp_down = network.model.add_variables(
        coords=[network.snapshots, target_gens],
        name="ramp_down",
        lower=0
    )

    # Math: P_t - P_t-1 = Up - Down
    # Example: if P_t - P_t-1 = 10 MW, then the model will set ramp_up = 10 MW and ramp_down = 0 MW
    # to satisfy the equality equation allowing tracking of ramping and vice versa.
    p = network.model.variables['Generator-p'].sel(Generator=target_gens)
    p_curr = p.isel(snapshot=slice(1, None))
    p_prev = p.shift(snapshot=1).isel(snapshot=slice(1, None))
    
    ramp_up_c = ramp_up.isel(snapshot=slice(1, None))
    ramp_down_c = ramp_down.isel(snapshot=slice(1, None))

    network.model.add_constraints(
        p_curr - p_prev == ramp_up_c - ramp_down_c,
        name="ramping_link"
    )

    # Objective: Sum( Ramp * Cost_of_that_specific_gen )
    cost_expr = (ramp_up_c * costs_xr).sum() + (ramp_down_c * costs_xr).sum()
    network.model.objective += cost_expr
    
    print(f"Ramping cost constraints applied to {len(target_gens)} generators.")

def constr_capacity_expansion_constraint(
    network: pypsa.Network,
    nodes: list[str],
    technologies: list[str],
    max_capacity: float
):
    """
    """
    generators_tech_and_node = network.generators[
        network.generators["type"].isin(technologies) & 
        network.generators["bus"].isin(nodes)
    ]
    
    if generators_tech_and_node.empty:
        print(f"Warning: No generators matching technologies {technologies} in nodes {nodes}")
        print(f"Skipping constraint constr_capacity_expansion_constraint")
        return

    initial_capacity = generators_tech_and_node.p_nom.sum()
    target_capacity = (
        network.model.variables["Generator-p_nom"]
        .sel(Generator=generators_tech_and_node.index)
        .sum()
    )

    network.model.add_constraints(
        lhs=target_capacity - initial_capacity,
        sign="<=",
        rhs=max_capacity,
        name=f"capacity_expansion_constraint_{'_'.join(technologies[:2])}_{'_'.join(nodes[:2])}"
    )

    print(f"Added capacity expansion constraint for {technologies} in {nodes}")