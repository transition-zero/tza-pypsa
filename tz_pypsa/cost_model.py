import pandas as pd

def calculate_construction_finance_factor(
        r : float,      # discount rate [0-1]
        y : list,       # years ( e.g., [1,2,3] )
        c : list,       # fractional capital distribution of technology (e.g., [0.5,0.5,0]). Must sum to equal 1.
):
    
    if isinstance(y, list) and isinstance(c, list):
        return \
            pd.Series( [ (1 + ((1+r)**(i+0.5)-1)) for i in y] ) * c
    else:
        return \
            (1 + ((1+r)**(y+0.5)-1) ) * c


def calculate_annuity(
        n : int, 
        r : float,
) -> float:
    '''

    Calculate the annuity factor for an asset with lifetime n years and
    discount rate of r, e.g. annuity(20, 0.05) * 20 = 1.6
    
    Inputs:
    -----------------------------------

        n : asset lifetime (years)
        r : discount rate (%, decimal point [e.g., 0.04])

    '''

    if isinstance(r, pd.Series):
        return pd.Series(1/n, index=r.index).where(r == 0, r/(1. - 1./(1.+r)**n))
    elif r > 0:
        return r/(1. - 1./(1.+r)**n)
    else:
        return 1/n
    

def compute_costs(path_to_dir):
    '''Get the tech costs
    '''

    # load capital outlay file
    capital_outlay = ( 
        pd
        .read_csv(f'{path_to_dir}costs_capital_outlay_during_construction.csv',skiprows=1)
        .set_index('carrier')
    )

    # compute the construction finance factor
    y = list( range(1,len(capital_outlay.filter(regex='year').columns)+1) )

    # calculate construction finance factor (k) for each technology
    capital_outlay['k'] = ( 
        capital_outlay
        .apply( 
            lambda row: \
                calculate_construction_finance_factor( 
                    r = 0.1, 
                    y = y, 
                    c = row.filter(regex='year').to_list(),
                ), axis=1
        ).sum(axis=1)
    )

    # load cost data
    costs = (
        pd
        .read_csv(f'{path_to_dir}costs_technology.csv')
        .groupby(by=['Country','Technology','Year'])
        .mean(numeric_only=True)
        .reset_index()
        .set_index(['Country','Technology', 'Year'])
    )

    #overwrite blank fixed costs with VNM/IDN averages
    for i,x in costs.iterrows():
        if pd.isna(x.FixedCost):
            costs.at[i, 'FixedCost'] = (costs.loc[ ('IDN',i[1],i[2]) ].FixedCost + costs.loc[ ('VNM',i[1],i[2]) ].FixedCost) / 2

    costs = costs.reset_index(drop=False)

    # $/MW
    costs['CapitalCost'] = costs['Technology'].map( capital_outlay['k'].to_dict() ) * costs['OvernightCapitalCost']

    # $/MW/yr
    # calculate annualised capex 
    costs['AnnualCapitalCost'] = (
        # annuity factor
        (
            costs['Technology'].map( calculate_annuity(capital_outlay['useful_life'], r = 0.1).to_dict() )
        )
        * costs['CapitalCost'] # multiply capital cost gives us annualised capex
        + costs['FixedCost'] # finally add annual fixed costs 
    )

    # calculate marginal costs
    costs['MarginalCost'] = (
        (
            costs['VariableCost'] 
            + (costs['FuelCost'] / costs['Efficiency']) 
        )
        .fillna(0)   
    )

    return costs#[ ~costs.Technology.isna() ].reset_index(drop=True)


