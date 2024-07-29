<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/transition-zero/.github/raw/main/profile/img/logo-dark.png">
  <img alt="TransitionZero Logo" width="300px" src="https://github.com/transition-zero/.github/raw/main/profile/img/logo-light.png">
  <a href="https://www.transitionzero.org/">
</picture>

# TZ-Analysis-PyPSA

<!-- badges-begin -->

![Python][python badge]
![Status][status badge]

[python badge]: https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Lkruitwagen/bd1e357c1bce5fc2c0808bcdb569157c/raw/python_version_badge.json

[status badge]: https://img.shields.io/badge/under%20construction-ffae00

<!-- badges-end -->

This repo contains code developed by the Analysis team at TransitionZero (TZA) to build and solve with [`PyPSA`](https://pypsa.org/) models. `TZA-PyPSA` allows us to modularly construct and work with PyPSA network models. 

`TZA-PyPSA` can be used to build a PyPSA model from scratch, but there are a set of pre-built models that a user can call as a starting point for their analysis. Please see all pre-built models are available in `tza-pypsa` [here](https://github.com/transition-zero/tza-pypsa/tree/main/tz_pypsa/core). See instructions below on how to use a pre-built model or how you can build your own. 

<!-- Model  | Status | Method | Overview
--- | --- | ---  | ---
[ASEAN](https://github.com/transition-zero/tz-analysis-pypsa-minimal/tree/main/models/ASEAN) | 🟠 In dev! | `yaml` | An hourly resolution dispatch model for the 10 Association of Southeast Asian Nations (ASEAN) states.  -->
<!-- Pakistan | 🔴 Not started, coming soon | Orchestrated | An hourly resolution dispatch model for Pakistan -->

# Contributors

**Model construction and validation:**
- [Aman Majid](https://www.transitionzero.org/team/aman-majid)
- [Abhishek Shivakumar](https://www.transitionzero.org/team/abhishek-shivakumar)
- [Handriyanti Diah Puspitarini](https://www.transitionzero.org/team/handriyanti-diah-puspitarini)
- [Dan Welsby](https://github.com/djwels)

**Data:**
- [Calvin Nesbitt](https://www.transitionzero.org/team/calvin-nesbitt)
- [Isabella Söldner-Rembold](https://www.transitionzero.org/team/isabella-soldner-rembold)
- [Sabina Parvu](https://www.transitionzero.org/team/sabina-parvu)

# Getting started

## Setup

Firstly, clone or download this repository (or an older version) and then navigate into the directory.

```
cd tz-analysis-pypsa
```

Next, install `tza-pypsa` into your local environment by running:

```
pip install -e .
```

That's it! You are now ready to use `tza-pypsa` as shown below. However, you will need to install additional packages before doing so, which are:

- [PyPSA](https://github.com/PyPSA/PyPSA)
- [pandas](https://github.com/pandas-dev/pandas)
- [numpy](https://github.com/numpy/numpy)
- [HiGHS](https://highs.dev/)

## Usage (running a model)

### Working with a pre-built model

You can either build your model or use a pre-built model. With a pre-built model, you can construct and run a PyPSA model with only a few lines of code. For instance, you can run the [ASEAN](https://github.com/transition-zero/tz-analysis-pypsa/tree/main/tz_pypsa/core/ASEAN) at an hourly resolution between 2023 and 2050 at 10-year timesteps as shown below:

```python

from tz_pypsa.model import Model

# load a pre-defined model (returns PyPSA network)
network = Model.load_model('ASEAN', years=[2023,2030, 2040, 2050], frequency='1h')

network.optimize(
  solver_name='highs',
  solver_options={"solver": "pdlp"},
)
```

### Load your own model

If you'd like to build and run your own model, you can do so by running:

```python

from tz_pypsa.model import Model

# load from a directory (returns PyPSA network)
network = Model.load_from_dir('path_to_your_model/')

network.optimize(
  solver_name='highs',
  solver_options={"solver": "pdlp"},
)
```

For the above code snippet to work, you will need to define your model using the file structure below:

```
path_to_your_model/
├── data/
│   ├── costs_technology.csv
│   ├── timeseries.nc
│   ├── costs_capital_outlay_during_construction.csv
├── model.yaml
└── *.yaml
```

Please see one of the pre-built models to understand how the files should be written and structured. 

# Contributing and Support

We strongly welcome anyone interested in contributing to this project. If you have any ideas, suggestions or encounter problems, feel invited to file issues or make pull requests on GitHub.

To discuss ideas for the project, please contact [@amanmajid](mailto:aman.m@transitionzero.org)

## Contributing rules:
- Do not contribute to master directly without a pull request, wherever possible.
- Create issues and allocate an individual.
- One pull request per issue.

# Licence

Copyright 2020-2023 [TransitionZero](https://www.transitionzero.org/)

This repository is licensed under the open source [XXX](...).
