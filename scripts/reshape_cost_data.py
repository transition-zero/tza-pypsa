# -------------------------------------------------------------------------
#
#   RESHAPE COST DATA
#   
#     This script is takes the technology cost data collated by the Analysis
#      team and reshapes/processes it into a nicer format.
#
#     Link to docs: 
#       N/A
#
#     Authors:
#       - @amanmajid
#
# -------------------------------------------------------------------------

import pandas as pd

costs = (
    pd.concat(
        [
        (
            pd
            .read_csv('../data/raw/ASEAN/technology_costs.csv')
            .drop('Unit.1',axis=1)
            .query('Country.isin(["IDN","VNM"])')
            .pivot_table(index=['Country','Technology','Year'],columns='Parameter',values='Value',aggfunc='sum')
        ),
        (
            pd
            .read_csv('../data/raw/ASEAN/technology_costs.csv')
            .drop('Unit.1',axis=1)
            .query('~Country.isin(["IDN","VNM"])')
            .pivot_table(index=['Country','Technology','Year'],columns='Parameter',values='ParameterValue_2021Base',aggfunc='sum')
        )
        ], 
        axis=0
    )
    .drop('CaptureRate', axis=1)
    .reset_index()
)

# fix values
costs['CapitalCost'] = costs['CapitalCost'].astype('float').mul(1e6) # convert $M/MW to $/MW
costs['FixedCost'] = costs['FixedCost'].str.replace(',','').astype('float').mul(1) # $/MW/year
costs['VariableCost'] = costs['VariableCost'].astype('float').mul(1) # $/MWh

# fix technology names -> match with TZ Platform
technology_mapping = {
    'Batteries - Lithium-ion (utility-scale), 4 hour charge:discharge' : 'lithium-ion',
    'Biogas' : 'biogas', 
    'Biomass Small' : 'biomass', 
    'Coal IGCC' : 'integrated-gasification-combined-cycle', 
    'Coal IGCC CCS': 'coal-ccs',
    'Coal Subcritical' : 'subcritical', 
    'Coal Supercritical' : 'supercritical', 
    'Coal Supercritical CCS' : 'coal-ccs',
    'Coal Ultra-Supercritical' : 'ultrasupercritical', 
    'Gas CCGT' : 'combined-cycle', 
    'Gas CCGT CCS' : 'gas-ccs', 
    'Gas OCGT' : 'open-cycle-gas-turbine',
    'Geothermal Binary' : 'geothermal-binary-cycle', 
    'Geothermal Flash' : 'geothermal-flash-steam-unspecified', 
    'Hydro Large' : 'hydro-unspecified',
    'Hydro Micro' : 'hydro-unspecified', 
    'Hydro Pumped Storage' : 'hydro-pumped-storage', 
    'Hydro Small' : 'hydro-unspecified',
    'Landfill Gas' : 'waste', 
    'MSW' : 'waste', 
    'Nuclear Pressurised Water Reactor' : 'pressurized-water-reactor',
    'Nuclear Small Modular Reactor' : 'small-modular-reactor', 
    'Oil Diesel' : 'petroleum-products-internal-combustion-engine',
    'Solar Rooftop, grid-connected' : 'photovoltaic-unspecified', 
    'Solar Utility, grid-connected' : 'photovoltaic-unspecified',
    # 'UPSIMPFLTLNG', 
    # 'UPSIMPONSLNG', 
    'Wind Offshore' : 'wind-offshore-unspecified',
    'Wind Offshore Floating' : 'wind-offshore-floating', 
    'Wind Onshore' : 'wind-onshore', 
    'Oil Fuel Oil' : 'petroleum-products-internal-combustion-engine',
}

costs.Technology = costs.Technology.map(technology_mapping)

costs.to_csv('../data/clean/ASEAN/costs_technology.csv', index=False)