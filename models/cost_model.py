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
    

def compute_costs():
    '''Get the tech costs
    '''

    # load capital outlay file
    capital_outlay = ( 
        pd
        .read_csv('../data/clean/ASEAN/costs_capital_outlay_during_construction.csv',skiprows=1)
        .set_index('Technology')
    )

    # compute the construction finance factor
    y = list( range(1,len(capital_outlay.filter(regex='Year').columns)+1) )

    # calculate construction finance factor (k) for each technology
    capital_outlay['k'] = ( 
        capital_outlay
        .apply( 
            lambda row: \
                calculate_construction_finance_factor( 
                    r = 0.1, 
                    y = y, 
                    c = row.filter(regex='Year').to_list(),
                ), axis=1
        ).sum(axis=1)
    )

    # load cost data
    costs = pd.read_csv('../data/clean/ASEAN/costs_technology.csv')

    # calculate real capex
    costs['CapitalCost'] = costs['Technology'].map( capital_outlay['k'].to_dict() ) * costs['OvernightCapitalCost']

    # calculate annualised capex
    costs['AnnualCapitalCost'] = costs['CapitalCost'] * costs['Technology'].map( calculate_annuity(capital_outlay['Useful life'], r = 0.1).to_dict() )

    # calculate marginal costs
    costs['MarginalCost'] = (costs['FixedCost'] + ( costs['VariableCost'] ) ).fillna(0) # need to divide VOM by efficiency

    return costs[ ~costs.Technology.isna() ].reset_index(drop=True)