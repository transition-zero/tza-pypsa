<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/transition-zero/.github/raw/main/profile/img/logo-dark.png">
  <img alt="TransitionZero Logo" width="300px" src="https://github.com/transition-zero/.github/raw/main/profile/img/logo-light.png">
  <a href="https://www.transitionzero.org/">
</picture>

# TZ-Analysis: PyPSA Minimal
This repo contains [`PyPSA`](https://pypsa.org/) models developed and used by the Analysis team at TransitionZero. 

Specifically, this repo has the models shown in the table below.

Model  | Status | Method | Overview
--- | --- | ---  | ---
[ASEAN](https://github.com/transition-zero/tz-analysis-pypsa-minimal/tree/main/models/ASEAN) | 🟠 In dev! | `yaml` | An hourly resolution dispatch model for the 10 Association of Southeast Asian Nations (ASEAN) states. 
Pakistan | 🔴 Not started, coming soon | Orchestrated | An hourly resolution dispatch model for Pakistan

# Contributors
The data and code provided here was developed by the following modellers/analysts at TransitionZero:

- [Aman Majid](https://www.transitionzero.org/team/aman-majid)
- [Handriyanti Diah Puspitarini](https://www.transitionzero.org/team/handriyanti-diah-puspitarini)
- [Abhishek Shivakumar](https://www.transitionzero.org/team/abhishek-shivakumar)

# Getting started

## Setup

Firstly, clone or download this repository (or an older version). 

Next, create a project environment using the yaml file in the repository as below.

conda:

```
conda env create --prefix ./env --file tz-analysis-env.yml
conda activate ./env
```

mamba:

```
mamba env update -n tz-analysis --file tz-analysis-env.yml
conda activate ./env
```

Additionally, install a solver for optimisation. We recommend using [HiGHS](https://highs.dev/), which is free and open source.

## Usage (running a model)
TODO!

# Contributing and Support

We strongly welcome anyone interested in contributing to this project. If you have any ideas, suggestions or encounter problems, feel invited to file issues or make pull requests on GitHub.

To discuss ideas for the project, please contact [@amanmajid](mailto:aman.m@transitionzero.org)

# Licence

Copyright 2020-2023 [TransitionZero](https://www.transitionzero.org/)

This repository is licensed under the open source [XXX](...).
