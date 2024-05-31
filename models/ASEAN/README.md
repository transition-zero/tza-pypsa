# TZ-Analysis-PyPSA: ASEAN
This folder contains the constructor files used to create a PyPSA model for the 10 Association of Southeast Asian Nations (ASEAN) states. 

PyPSA-ASEAN is an hourly-resolution power sector model. It can be used for:

- Dynamic dispatch modelling of power systems.
- Market pricing and intervention analysis.
- Power system capacity expansion planning.

The model can be run for the entire ASEAN region or a single country.

## Overview
The PyPSA-ASEAN model is comprised of X nodes and Y links. Here, each node represents a balancing zone, while each link represents the aggregated interconnector capacity between balancing zones. The model is spatially illustrated below.

<p align="center">
  <img src="https://github.com/transition-zero/tz-analysis-pypsa-minimal/blob/main/assets/static-asean-map.png" alt="" height="350">
  <img src="https://github.com/transition-zero/tz-analysis-pypsa-minimal/blob/main/assets/static-asean-map-pypsa2.png" alt="" height="350">
</p>

## Model configuration

### Geographical scope

The ASEAN region covers:

- Brunei 🇧🇳 (BRN)
- Cambodia 🇰🇭 (KHM)
- Indonesia 🇮🇩 (IDN)
- Laos 🇱🇦 (LAO)
- Malaysia 🇲🇾 (MYS)
- Myanmar 🇲🇲 (MMR)
- Philippines 🇵🇭 (PHL)
- Singapore 🇸🇬 (SGP)
- Thailand 🇹🇭 (THA)
- Vietnam 🇻🇳 (VNM)

<img src="https://github.com/transition-zero/tz-analysis-pypsa-minimal/blob/main/assets/static-asean-map-pypsa.png" alt="" height="350" align="center">


### Temporal resolution
TODO

<!-- TRM runs between 2024 and 2030 by default. Within each annual time step, there are six seasonal timeslices referred to as: ID, IN, SD, SN, WD and WN. The time definitions are defined in [`time_definitions.yaml`](https://github.com/transition-zero/tz-osemosys/blob/add-tutorials/examples/two-region-model/time_definitions.yaml). -->

### Emissions targets
<!-- TRM does not have any emissions targets by default. However, it is setup such that emissions targets (e.g., CO2, NOx etc) can be easily implemented. Emissions targets are defined in [`targets.yaml`](https://github.com/transition-zero/tz-osemosys/blob/add-tutorials/examples/two-region-model/targets.yaml). -->

## Running the model
`PyPSA-ASEAN` can be run using the command below:

```python
from models.loader import ASEAN
network = ASEAN().create_model() # <-- Returns a PyPSA network
network.optimize(solver_name='highs')
```

It is also possible to run the model for a subset of ASEAN countries. For example, you can run the model solely for Indonesia (IDN) and the Philippines (PHL) as below:

```python
from models.loader import ASEAN
network = ASEAN(countries=['IDN', 'PHL']).create_model() # <-- Returns a PyPSA network
network.optimize(solver_name='highs')
```

## Model performance
The table below shows the time it took to solve an annual dispatch (i.e., 8760 timesteps) for the ASEAN model, as well as country subsets of the ASEAN model. The optimisation is setup as a classical linear programming (LP) problem and solved using the [HiGHS](https://highs.dev/) solver. These benchmarks were computed using an Apple MacBook Pro (2023) with an M2 Pro processor and 16 GB of RAM.

Model       | Nodes/Links/Generators  | HiGHS (pdlp)    | Gurobi
---         | ---                     | ---             | ---
ASEAN       | 24/31/153               | 00h:08m:07s     | 00h:00m:49s
Indonesia   | 07/07/057               | 00h:00m:24s     | 00h:00m:14s
Philippines | 03/02/021               | 00h:03m:41s     | 00h:00m:05s
Thailand    | 03/02/020               | 00h:02m:31s     | 00h:00m:05s
Myanmar     | 01/00/005               | 00h:00m:12s     | 00h:00m:02s
Singapore   | 01/00/005               | 00h:00m:11s     | 00h:00m:01s

Note that unit commitment (UC) was not applied in the model benchmarks reported above. UC would likely increase the computation times significantly given that it transforms the optimisation into a mixed-integer linear programme (MILP).

## TODO

- [ ] Update network plot in README
- [ ] Update cost data with real costs (i.e., not dummy numbers)
    - [ ] Review `costs.yaml` with Analysis team
- [ ] Add emissions intensities to `Carrier`
- [ ] Implement emission constraints (`targets.yaml`)
- [ ] Add maximum RES build potential based on Calvin's data
- [ ] Assign sensible "must-run" conditions
- [ ] Assign sensible ramp rates
- [ ] Assign sensible import limits (i.e., bus self-sufficiency)