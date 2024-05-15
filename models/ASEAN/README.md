# TZ-Analysis-PyPSA: ASEAN
This folder contains the constructor files used to create a PyPSA model for the 10 Association of Southeast Asian Nations (ASEAN) states. 

The ASEAN region covers Brunei 🇧🇳, Cambodia 🇰🇭, Indonesia 🇮🇩, Laos 🇱🇦, Malaysia 🇲🇾, Myanmar 🇲🇲, Philippines 🇵🇭, Singapore 🇸🇬, Thailand 🇹🇭, Timor-Leste 🇹🇱, and Vietnam 🇻🇳.

PyPSA-ASEAN is an hourly-resolution power sector model. It can be used for:

- Dynamic dispatch modelling of power systems.
- Market pricing and intervention analysis.
- Power system capacity expansion planning.

The model can be run for the entire ASEAN region or a single country.

## Overview
The PyPSA-ASEAN model is comprised of X nodes and Y links. Here, each node represents a balancing zone, while each link represents the aggregated interconnector capacity between balancing zones. The model is spatially illustrated below: 

<img src="https://github.com/transition-zero/tz-analysis-pypsa-minimal/blob/main/assets/static-asean-map.png" alt="" height="800" align="center">

## Model configuration
TODO

<!-- This folder contains the PyPSA-ASEAN model constructor files, the majority of which are in `yaml` format.  -->

### Temporal resolution
TODO

<!-- TRM runs between 2024 and 2030 by default. Within each annual time step, there are six seasonal timeslices referred to as: ID, IN, SD, SN, WD and WN. The time definitions are defined in [`time_definitions.yaml`](https://github.com/transition-zero/tz-osemosys/blob/add-tutorials/examples/two-region-model/time_definitions.yaml). -->

### Emissions targets
<!-- TRM does not have any emissions targets by default. However, it is setup such that emissions targets (e.g., CO2, NOx etc) can be easily implemented. Emissions targets are defined in [`targets.yaml`](https://github.com/transition-zero/tz-osemosys/blob/add-tutorials/examples/two-region-model/targets.yaml). -->

## Running the model
TODO

<!-- 
Provided you have successfully setup `tz-osemosys` on your local machine as instructed, you can run the TRM model as shown below:

```python
from tz.osemosys import Model
model = Model.from_yaml("tz-osemosys/examples/two-region-model/")
model.solve()
``` -->