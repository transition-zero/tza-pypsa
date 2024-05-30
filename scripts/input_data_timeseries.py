# -------------------------------------------------------------------------
#
#   INPUT DATA
#   
#     This script is used to aggregate multiple time series data files (csv)
#      into a single xarray dataset. The data are related to:
#
#       - Capacity factors
#       - Demand
#
#     Link to docs: 
#       N/A
#
#     Authors:
#       - @amanmajid
#
# -------------------------------------------------------------------------

import argparse

import pandas as pd
import xarray as xr

def get_demand_ts(
        path_annual_demand,
        path_demand_profile,
        year
):

    annual_demand = pd.read_csv(path_annual_demand)
    demand_profile = pd.read_csv(path_demand_profile)

    annual_demand = ( 
        pd
        .read_csv('../data/raw/ASEAN/specified_annual_demand.csv')
        .query(f"YEAR == {year}")
        .pivot_table(
            index='YEAR',
            columns='CUSTOM_NODE',
            values='VALUE',
            aggfunc='sum')
    )

    for n in annual_demand.columns:
        demand_profile[n] = demand_profile[n].mul(annual_demand[n].values[0])

    demand = demand_profile.drop(['Month', 'Day', 'Hour'], axis=1)

    demand = (
        demand
        .set_index( 
            pd.date_range(
                start=f'{year}-01-01 00:00:00',
                end= f'{year}-12-31 23:00:00',
                freq='h' 
            ),
        )
    )

    demand.index.names = ['snapshot']

    return xr.DataArray(demand, dims=['snapshot', 'node'])


def read_ts(file_name, year):
    return ( 
        xr
        .DataArray(( pd
                .read_csv(file_name)
                .drop('Datetime', axis=1)
                #.drop('Time',axis=1)
                .set_index( 
                    pd.date_range(
                        start=f'{year}-01-01 00:00:00',
                        end= f'{year}-12-31 23:00:00',
                        freq='h' 
                    ),
                )
                .rename_axis('snapshot')
                ),
            dims=['snapshot', 'node'], 
        )
    )


if __name__ == '__main__':

    # Initialize the parser
    parser = argparse.ArgumentParser(description="Generate input data time series.")
    # Add arguments
    parser.add_argument('--year', type=str, help='Year for which to generate the data. Default is 2023.')
    # Parse the arguments
    args = parser.parse_args()
    
    # Get year from args
    year = args.year if args.year else '2023'

    offshore_cf = read_ts('../data/raw/ASEAN/RE_profiles_WOF.csv', year = year)
    onshore_cf = read_ts('../data/raw/ASEAN/RE_profiles_WON.csv', year = year)
    solar_cf = read_ts('../data/raw/ASEAN/RE_profiles_SPV.csv', year = year)

    demand = get_demand_ts(
        path_annual_demand='../data/raw/ASEAN/specified_annual_demand.csv',
        path_demand_profile='../data/raw/ASEAN/specified_demand_profile.csv',
        year=year
    )


    xdf = xr.Dataset(
        { 'cf_wind_offshore' : offshore_cf, 
        'cf_wind_onshore' : onshore_cf, 
        'cf_solar_pv' : solar_cf,
        'demand' : demand,
        },
        attrs=dict(
            sources="Raw data was sent by @Abhishek Shivakumar",
            capacity_factors="CF are for the year 2015. We've adjusted the snapshot to match demand.",
        )
    )

    # save dataset
    xdf.to_netcdf(f'../data/clean/ASEAN/timeseries_{year}.nc')

    print(f"Data for {year} saved to ../data/clean/ASEAN/timeseries_{year}.nc")