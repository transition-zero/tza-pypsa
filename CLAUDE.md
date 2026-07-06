# CLAUDE.md — tza-pypsa

Modular PyPSA network construction library for hourly dispatch and multi-year capacity
expansion modeling in Asia-Pacific energy systems. Pre-built stock models (ASEAN, India,
Japan, Taiwan) are defined declaratively in YAML under `stock_models/`. Custom constraints
follow the `constr_*()` pattern using Linopy expressions. Remote timeseries and cost data
are fetched from a separate GitHub repository via the GitHub API.

Used as a dependency by `tz-mod` (as `tza-pypsa`).

## Commands

```bash
uv run pytest                        # run all tests
uv run pytest tests/path/test_foo.py # run single test file
uv run pre-commit run --all-files    # lint + format + type checks
ruff check . --fix                   # lint only
ruff format .                        # format only
mypy .                               # type check only
```

## Architecture

### Core API — `tz_pypsa/model.py`

```python
from tz_pypsa.model import Model

# Load a stock model
network = Model.load_model(
    model_name='ASEAN',             # 'ASEAN', 'India', 'Japan', 'Taiwan'
    years=[2023, 2030, 2040, 2050], # multi-year investment periods
    frequency='24h',                # resample timeseries ('1h', '4h', '24h')
    select_nodes=['IDN', 'THA'],    # optional node subset
    backstop=False,                 # add $1e9/MWh backstop generators
    set_global_constraints=False,   # apply constraints from constraints.yaml
    branch='main',                  # GitHub branch for remote data
)

# Load from a local CSV directory (PyPSA CSV format)
network = Model.load_csv_from_dir('path/to/csv_dir/')
```

`Model.load_model()` fetches remote data (timeseries NetCDF, technology costs CSV,
construction cost CSV) from a separate GitHub repository specified in `data.yaml`.
A GitHub personal access token is required — stored in `_GITHUB_TOKEN_` file at the
repo root (fetched lazily on first use).

### Network Construction — `tz_pypsa/build_network.py`

`build_pypsa_network(model, timeseries, costs, years, **kwargs)` constructs the
`pypsa.Network` object step by step:

1. **Snapshots** — single-year `DatetimeIndex` or multi-year `MultiIndex`
   (investment periods with pre-computed discount weights)
2. **Carriers** — CO2 emissions, display name, colour
3. **Buses** — coordinates, `min_self_sufficiency`, per-year CO2 budgets
4. **Links** (interconnectors) — bidirectional, transmission efficiency, haversine
   auto-distance if length is 0
5. **Generators** — capacity factors from YAML or timeseries NetCDF, per-node
   initial/planned/maximum capacity, `p_nom_extendable` flag
6. **Storage units** — `max_hours`, efficiencies, cyclic SOC
7. **Loads** — from timeseries, scaled by `load_multiplier` kwarg

**Capacity logic for multi-year models:**
- Pre-base-year technologies: `p_nom_extendable=False` (committed capacity)
- Post-base-year technologies: `p_nom_extendable=True` with `p_nom_min` from planned
  expansions and `p_nom_max` from maximum limits

### Custom Constraints — `tz_pypsa/constraints.py`

All constraint functions follow this signature:

```python
def constr_NAME(network: pypsa.Network, **kwargs) -> None:
    # Access decision variables via Linopy
    lhs = network.model.variables['Generator-p'].sel(Generator=...).sum()
    rhs = network.model.variables['Generator-p_nom'].sel({'Generator-ext': ...}) * ...
    network.model.add_constraints(lhs=lhs, sign='>=', rhs=rhs, name='ConstraintName')
```

**Apply constraints after `load_model()`, before `network.optimize()`.**

Implemented constraints (19 total):

| Function | Purpose |
|---|---|
| `constr_bus_self_sufficiency` | Min % local generation per bus |
| `constr_cumulative_p_nom` | Cumulative capacity limits across investment periods |
| `constr_policy_targets` | Capacity/generation targets from CSV (per node, per year) |
| `constr_min/max_annual_utilisation` | Annual capacity factor bounds per carrier |
| `constr_min/max_annual_utilisation_links` | Throughput bounds on interconnectors |
| `constr_min/max_annual_utilisation_generator` | Annual generation rate bounds |
| `constr_min/max_annual_utilisation_storage_*` | Charge/discharge bounds on storage |
| `constr_soc_intraday_profile` | Intra-day SOC profile constraints |
| `constr_soc_weekly_profile` | Day-of-week SOC bounds |
| `constr_cofiring_ccs_generation_join_plant` | Cofiring/CCS blend constraints |
| `constr_production_target_min` | Minimum production targets per technology |

### Stock Models — `stock_models/`

Each stock model directory contains up to 8 files:

| File | Contents |
|---|---|
| `time_definition.yaml` | `years`, `frequency`, `multi_year_discount_rate` |
| `carriers.yaml` | Energy carriers: CO2 intensity, colour, display name |
| `nodes.yaml` | Buses: coordinates, `min_self_sufficiency`, CO2 budgets |
| `generators.yaml` | Technologies: initial/planned/max capacity (per node), efficiency, costs |
| `storages.yaml` | Storage technologies: same capacity fields + `max_hours`, efficiency |
| `links.yaml` | Interconnectors: bidirectional flag, efficiency, capacity |
| `constraints.yaml` | Which global/custom constraints to apply, and with what parameters |
| `data.yaml` | GitHub repo owner/name and paths for remote timeseries and cost files |

Per-node capacities are specified as dicts — e.g., `initial_capacity: {IDNSM: 1840.1, IDNJW: 14.0}`.
Nodes not listed inherit zero initial capacity.

**Available stock models:**

| Model | Nodes | Format | Notes |
|---|---|---|---|
| ASEAN | 24 (10 countries) | YAML | Flagship multi-country model |
| India | 5 | CSV (PyPSA format) | Hourly dispatch |
| Japan | varies | Hybrid YAML/CSV | Multi-year investment |
| Taiwan | minimal | YAML | Smaller model |

### Other Modules

- `tz_pypsa/cost_model.py` — annuity calculations, construction finance factors (AFUDC)
- `tz_pypsa/wrangle.py` — result extraction, cost summaries, data export utilities
- `tz_pypsa/plotting.py` — Plotly/Cartopy/Matplotlib visualisation (energy balance,
  dispatch charts, maps)
- `tz_pypsa/helpers.py` — haversine distance, SOC bounds loading
- `tz_pypsa/utils.py` — GitHub API client, YAML loading, package path utilities

## Key Conventions

- **Do not read CSV files** unless explicitly requested — timeseries files are large.
- Remote data requires `_GITHUB_TOKEN_` file at repo root. Do not commit this file.
- Timeseries are fetched as NetCDF and resampled on-the-fly — do not cache intermediate
  resolutions to disk unless explicitly building a pipeline step.
- All custom constraints use Linopy expressions (`network.model.variables[...]`), not
  the older PyPSA/pyomo backend.
- Haversine auto-distance is applied only when a link's `length` is 0 — set explicit
  lengths in YAML when geographic accuracy matters.
- `generation_blend_share` and `is_blend_or_ccs` generator attributes are custom columns
  read by `constr_cofiring_ccs_generation_join_plant` — keep these in sync.

## Adding a New Stock Model

1. Create `stock_models/NewModel/`
2. Add the 7-8 YAML files following the ASEAN structure as a template
3. Point `data.yaml` to the correct GitHub repo and file paths
4. Call `Model.load_model('NewModel')`

## Adding a New Constraint

1. Define `constr_my_constraint(network: pypsa.Network, **kwargs)` in `constraints.py`
2. Access variables via `network.model.variables['Component-attribute']`
3. Build Linopy expressions (`.sum()`, `.sel()`, arithmetic, comparisons)
4. Register with `network.model.add_constraints(lhs=..., sign=..., rhs=..., name=...)`
5. If it should be applied automatically, add an entry to `constraints.yaml` in the
   relevant stock model and wire it up in the `set_global_constraints` block of
   `build_network.py`

## Dependencies

Core: `pypsa`, `pandas`, `xarray`, `h5netcdf`, `requests`
Visualisation: `cartopy`, `plotly`
Dev: `pytest`, `highspy` (HiGHS Python wrapper for solve tests)
