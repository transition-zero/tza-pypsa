# TZ-Analysis-PyPSA: India
This folder contains the csv files used to create a PyPSA model for India.

PyPSA-India is an hourly-resolution power sector model. It can be used for:

- Dynamic dispatch modelling of power systems.
- Market pricing and intervention analysis.
- Power system capacity expansion planning.

## Overview
The PyPSA-India model is comprised of 5 nodes and 6 inter grid-zone links. Here, each node represents a regional power grid in the India National Grid, while each link represents the aggregated transmissions capacity between grid zones.

The model is setup and calibrated to run a 2023 dispatch year. Policy targets have also been setup to allow the model to run a 2030 NDC-compliant year.

## Model configuration

### Geographical scope
The 5 grid zones are as follows:

Grid zone       | Code
---             | ---                  
India East      | INDEA     
India North-East| INDNE   
India North     | INDNO   
India South     | INDSO   
India West      | INDWE                          

### Temporal resolution
PyPSA-India runs at an hourly resolution (i.e., 8760 timesteps). Other temporal resolutions are currently not supported.

### Data sources
This repo works with the [tza-india-data](https://github.com/transition-zero/tza-india-data/) repo which produces the data required for the India PyPSA model. See the README there for a list of data sources as well as the source code used to create the csvs.

### Policy targets
In addition to the data sources from the [tza-india-data](https://github.com/transition-zero/tza-india-data/) repo, there is a `power_sector_targets.csv` file to define NDC targets such as emissions and minimum capacity targets for 2030. This file also defines renewables potentials, upper limits of buildouts due to technological limitations or state targets.

## Running the model
`PyPSA-India` can be run using the command below:

```python
from tz_pypsa.model import Model
n = Model.load_csv_from_dir('../stock_models/India',
                          years=2023,
                          backstop=True)
model = n.optimize.create_model()
# Add any custom constraints here
n.optimize.solve_model(solver_name='highs')
```