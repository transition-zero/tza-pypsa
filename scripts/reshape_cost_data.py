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
costs['OvernightCapitalCost'] = costs['CapitalCost'].astype('float').mul(1e6) # convert $M/MW to $/MW
costs['FixedCost'] = costs['FixedCost'].str.replace(',','').astype('float').mul(1) # $/MW/year
costs['VariableCost'] = costs['VariableCost'].astype('float').mul(1) # $/MWh

# fix technology names -> match with TZ Platform
technology_mapping = {
    'Batteries - Lithium-ion (utility-scale), 4 hour charge:discharge' : 'lithium-ion',
    'Biogas' : 'biogas', 
    'Biomass Small' : 'biomass', 
    'Coal IGCC' : 'integrated-gasification-combined-cycle', 
    'Coal IGCC CCS': 'coal-ccs',
    'Coal Subcritical' : 'coal-subcritical', 
    'Coal Supercritical' : 'coal-supercritical', 
    'Coal Supercritical CCS' : 'coal-ccs',
    'Coal Ultra-Supercritical' : 'coal-ultrasupercritical', 
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
    'Oil Diesel' : 'oil-unspecified',
    'Solar Rooftop, grid-connected' : 'photovoltaic-unspecified', 
    'Solar Utility, grid-connected' : 'photovoltaic-unspecified',
    # 'UPSIMPFLTLNG', 
    # 'UPSIMPONSLNG', 
    'Wind Offshore' : 'wind-offshore-unspecified',
    'Wind Offshore Floating' : 'wind-offshore-floating', 
    'Wind Onshore' : 'wind-onshore', 
    'Oil Fuel Oil' : 'oil-unspecified',
}

carrier_mapping = {
    'lithium-ion': 'battery',
    'biomass': 'bioenergy',
    'biogas': 'bioenergy',
    'bioenergy': 'bioenergy',
    'subcritical': 'coal',
    'supercritical': 'coal',
    'ultrasupercritical': 'coal',
    'circulating-fluidized-bed': 'coal',
    'integrated-gasification-combined-cycle': 'coal',
    'coal-unspecified': 'coal',
    'coal-subcritical': 'coal',
    'coal-supercritical': 'coal',
    'coal-ultrasupercritical': 'coal',
    'internal-combustion-combined-cycle': 'gas',
    'combined-cycle': 'gas',
    'gas-turbine': 'gas',
    'open-cycle-gas-turbine': 'gas',
    'steam-turbine': 'gas',
    'integrated-solar-combined-cycle': 'gas',
    'allum-fetvedt-cycle': 'gas',
    'gas-unspecified': 'gas',
    'geothermal-unspecified': 'geothermal',
    'hydro-reservoir': 'hydro',
    'hydro-run-of-river': 'hydro',
    'hydro-pumped-storage': 'hydro',
    'hydro-reservoir-and-run-of-river': 'hydro',
    'hydro-reservoir-and-pumped-storage': 'hydro',
    'hydro-unspecified': 'hydro',
    'waste': 'waste',
    'pressurized-heavy-water-reactor': 'nuclear',
    'pressurized-water-reactor': 'nuclear',
    'fast-breeder-reactor': 'nuclear',
    'light-water-graphite-reactor': 'nuclear',
    'high-temperature-gas-reactor': 'nuclear',
    'boiling-water-reactor': 'nuclear',
    'gas-cooled-reactor': 'nuclear',
    'heavy-water-gas-cooled-reactor': 'nuclear',
    'small-modular-reactor': 'nuclear',
    'liquid-metal-cooled-fast-reactor': 'nuclear',
    'heavy-water-light-water-reactor': 'nuclear',
    'steam-generating-heavy-water-reactor': 'nuclear',
    'molten-salt-reactor': 'nuclear',
    'advanced-boiling-water': 'nuclear',
    'fast-neutron-reactor': 'nuclear',
    'nuclear-unspecified': 'nuclear',
    'petroleum-products-internal-combustion-engine': 'oil',
    'oil-unspecified': 'oil',
    'solar-unspecified': 'solar',
    'solar-thermal': 'solar',
    'photovoltaic': 'solar',
    'wind-nearshore-intertidal': 'wind',
    'wind-onshore': 'wind',
    'wind-offshore': 'wind',
    'wind-unspecified': 'wind',
    'wind-offshore-unspecified': 'wind',
    'coal-ccs': 'coal',
    'gas-ccs': 'gas',
    'photovoltaic-unspecified': 'solar',
    'wind-offshore-floating': 'wind',
    'geothermal-binary-cycle' : 'geothermal', 
    'geothermal-flash-steam-unspecified' : 'geothermal',
}

efficiency_mapping = {
    'bioenergy': 0.3,
    'biogas': 0.3,
    'biomass': 0.3,
    'coal-ccs': 0.4,
    'coal-unspecified': 0.4,
    'coal-subcritical': 0.4,
    'coal-supercritical': 0.4,
    'coal-ultrasupercritical': 0.4,
    'combined-cycle': 0.6,
    'gas-ccs': 0.7,
    'geothermal-unspecified': 0.15,
    'hydro-pumped-storage': 0.75,
    'hydro-unspecified': 0.75,
    'integrated-gasification-combined-cycle': 0.4,
    'lithium-ion': 1.0,
    'oil-unspecified': 0.55,
    'open-cycle-gas-turbine': 0.4,
    'photovoltaic-unspecified': 1.0,
    'pressurized-water-reactor': 0.8,
    'small-modular-reactor': 0.8,
    'subcritical': 0.4,
    'supercritical': 0.4,
    'ultrasupercritical': 0.4,
    'waste': 0.3,
    'wind-offshore-floating': 1.0,
    'wind-offshore-unspecified': 1.0,
    'wind-onshore': 1.0
}

costs['Technology'] = costs.Technology.map(technology_mapping)
costs['Carrier'] = costs.Technology.map(carrier_mapping)
costs['Efficiency'] = costs.Technology.map(efficiency_mapping)

costs = costs[['Country','Carrier','Technology','Year','Efficiency','OvernightCapitalCost','FixedCost','VariableCost']]

fuel_prices = (
    pd
    .read_csv('../data/raw/ASEAN/fuel_prices.csv')
)

FuelMapping = {
    'NGS' : 'gas',
    'OIL' : 'oil',
    'COA' : 'coal'
}

fuel_prices['Fuel'] = fuel_prices.Technology.str[3:6].map(FuelMapping)

fuel_prices.groupby(by=['Region','Fuel','Year']).mean(numeric_only=True).reset_index()

for country in costs.Country.unique():
    for carrier in costs.Carrier.unique():
        
        price = (
            fuel_prices.loc[
                (fuel_prices.Region == country) & (fuel_prices.Fuel == carrier),
                'VariableCost_$/MWh'
            ]
        )

        if price.empty:
            price = 0
        else:
            price = price.values[0]

        costs.loc[
            (costs.Country == country) & (costs.Carrier == carrier),
            'FuelCost'
        ] = price

costs.to_csv('../data/clean/ASEAN/costs_technology.csv', index=False)