import os
import yaml
import pypsa

import pandas as pd
import xarray as xr

# ---
# Local imports

from . import cost_model
from . import utils 

from .build_network import (
    build_pypsa_network,
)

# ---

class Model:

    '''

    Methods
    ----------

    get_available_models()
        Returns a list of stock models available in tz_pypsa.

    load_model(model_name)
        Load a model from pre-defined stock models.

    load_from_dir(path_to_dir)
        Loads a model from a directory containing yaml and .nc files.
    
    '''


    @staticmethod
    def load_model(
        model_name,
        years : list = None,
        select_nodes : list = None,
        frequency : str = None,
        timesteps : int = None,
        backstop : bool = False,
        set_global_constraints : bool = False,
        **kwargs,
    ) -> pypsa.Network:

        '''
        Load a model from pre-defined stock models.

        Parameters
        ----------

            model_name : str
                The name of the model to load.
            years : list (optional) 
                The list of years for multi-year investment (default is None).
            select_nodes : list (optional)
                The list of nodes to select for the network (default is None).
            frequency : str (optional)
                The frequency of the time series data (default is 24h).
            backstop : bool (optional)
                If True, the model will include backstop technologies (default is False).
            set_global_constraints : bool (optional)
                If True, the model will include global constraints (default is False).

        Returns
        ----------

            network : pypsa.Network.
                A PyPSA network object representing the loaded model.

        Raises
        ----------

            ValueError: If the specified model is not found in the stock models.

        Example
        ----------
        
            To load a model named "example_model", you can call the function as follows:

            >>> model = load_model("example_model")

        This function loads a model from the stock models available in tz_pypsa. It first checks if the specified model exists in the stock models. If found, it loads the model YAML file and the associated timeseries data. Finally, it builds a PyPSA network using the loaded model, timeseries, and optional costs.

        Notes
        ----------

            To see a list of stock models available in tz_pypsa, you can run the following command:

            >>> Model.get_available_models()

        '''

        # get core model
        if model_name in utils.get_stock_models():
            model = utils.load_yaml_from_dir(
                os.path.join( 
                    utils.get_package_root(), 
                    'stock_models', 
                    model_name,
                ) 
            )
        else:
            raise ValueError(f"Model {model_name} not found in stock models.")
        
        # --- get model years and frequency --- #
        if not years:
            years = model['time_definition']['years']
        
        if not frequency:
            frequency = model['time_definition']['frequency']

        # ---
        # Load data from remote directories

        PERSONAL_ACCESS_TOKEN = utils.get_github_token()

        # load capital outlay file
        url = (
                utils.get_data_from_github_with_auth(
                path_to_file = model['remote_data']['technology_costs']['path_to_cost'] + 'costs_capital_outlay_during_construction.csv',
                personal_access_token = PERSONAL_ACCESS_TOKEN,
                remote_data = model['remote_data'],
                branch=kwargs.get('branch', 'main'),
            )
        )

        capital_outlay = ( 
            pd
            .read_csv(
                url,
                skiprows=1
            )
            .set_index(
                'carrier'
            )
        )

        # load technology costs
        url = (
            utils.get_data_from_github_with_auth(
                path_to_file = model['remote_data']['technology_costs']['path_to_cost'] + 'technology_costs.csv',
                personal_access_token = PERSONAL_ACCESS_TOKEN,
                remote_data = model['remote_data'],
                branch=kwargs.get('branch', 'trial_data_for_blending'),
            )
        )

        technology_costs = (
            pd
            .read_csv(
                url
            )
        )

        # load policy and targets database
        url = (
            utils.get_data_from_github_with_auth(
                path_to_file = model['remote_data']['policies']['path_to_policy'] + 'power_sector_targets.csv',
                personal_access_token = PERSONAL_ACCESS_TOKEN,
                remote_data = model['remote_data'],
                branch=kwargs.get('branch', 'trial_data_for_blending'),
            )
        )

        targets = (
            pd
            .read_csv(
                url
            )
        )

        # get costs
        costs = (
            cost_model
            .compute_costs(
                technology_costs = technology_costs,
                capital_outlay = capital_outlay,
            )
            .set_index(['Country','Technology','Year'])
        )

        #costs.to_csv('COSTS.csv')

        # get timeseries
        datasets = []
        if isinstance(years, int):
            yyears = [years]
        else:
            yyears = years
        
        for year in yyears:

            url = utils.get_data_from_github_with_auth(
                path_to_file=model['remote_data']['timeseries']['path_to_timeseries'] + f'timeseries_{year}.nc',
                personal_access_token=PERSONAL_ACCESS_TOKEN,
                remote_data=model['remote_data'],
                branch=kwargs.get('branch', 'trial_data_for_blending'),
            )

            # open and resample
            ts = (
            xr
            .open_dataset(url)
            .resample(
                snapshot = frequency,
            )
            .mean()
            )

            datasets.append(ts)

        timeseries = xr.concat(datasets, dim='snapshot')

        # subset for timesteps
        if timesteps:
            timeseries = timeseries.isel(snapshot=slice(0, timesteps))
    
        # build network
        return build_pypsa_network(
            model = model,
            timeseries = timeseries,
            costs = costs,
            years = years,
            targets = targets,
            select_nodes = select_nodes,
            frequency = frequency,
            backstop = backstop,
            set_global_constraints = set_global_constraints,
            **kwargs,
        )
    

    @staticmethod
    def load_from_dir(
        path_to_dir,
        years : list = None,
        select_nodes : list = None,
        frequency : str = None,
        backstop : bool = False,
        set_global_constraints : bool = False,
        **kwargs,
    ) -> pypsa.Network:
        
        '''
        Load a model from a defined directory.

        Parameters
        ----------

            path_to_dir : str
                Directory from which we load the model. This directory should contain at least one yaml file and a data/ directory containing the timeseries and cost data. File names are strictly enforced.
            years : list (optional) 
                The list of years for multi-year investment (default is None).
            select_nodes : list (optional)
                The list of nodes to select for the network (default is None).
            frequency : str (optional)
                The frequency of the time series data (default is 24h).
            backstop : bool (optional)
                If True, the model will include backstop technologies (default is False).
            set_global_constraints : bool (optional)
                If True, the model will include global constraints (default is False).

        Returns
        ----------

            network : pypsa.Network.
                A PyPSA network object representing the loaded model.

        Raises
        ----------

            ValueError: If the specified model is not found in the stock models.

        Example
        ----------
        
            To load a model named "example_model", you can call the function as follows:

            >>> model = load_from_dir("some/path/to/dir")

        This function loads a model from the stock models available in tz_pypsa. It first checks if the specified model exists in the stock models. If found, it loads the model YAML file and the associated timeseries data. Finally, it builds a PyPSA network using the loaded model, timeseries, and optional costs.

        '''

        return Exception("This function is not yet implemented.")
        
        # try:
        #     #print( 'Loading model from: ' + path_to_dir)
        #     model = utils.load_yaml_from_dir(path_to_dir)
        # except:
        #     raise ValueError(f"Error loading model from directory {path_to_dir}")

        # try:
        #     #print( 'Loading timeseries from: ' + os.path.join( path_to_dir, f'data/', 'timeseries.nc' ) )
                  
        #     timeseries = (
        #         xr
        #         .open_dataset(
        #             os.path.join(
        #                 path_to_dir, 
        #                 f'data/', 
        #                 'timeseries.nc',
        #             )
        #         )
        #     )
        # except:
        #     raise ValueError(f"Error loading timeseries data from directory {path_to_dir}. Check if there is a timeseries.nc file in the data/ directory.")

        # try:
        #     # get costs
        #     costs = (
        #         cost_model
        #         .compute_costs(
        #             path_to_dir = os.path.join(
        #                 path_to_dir, 
        #                 f'data/',
        #             )
        #         )
        #     )
        # except:
        #     raise ValueError(f"Error computing costs from directory {path_to_dir}")
    
        # # build network
        # return build_pypsa_network(
        #     model = model,
        #     timeseries = timeseries,
        #     costs = costs,
        #     years = years,
        #     select_nodes = select_nodes,
        #     frequency = frequency,
        #     backstop = backstop,
        #     set_global_constraints = set_global_constraints,
        #     **kwargs,
        # )
        
    @staticmethod
    def load_csv_from_dir(
        path_to_dir,
        years,
        backstop : bool = False,
        **kwargs,
    ) -> pypsa.Network:
        
        '''
        Load a model from a defined directory.

        Parameters
        ----------

            path_to_dir : str
                Directory from which we load the model. This directory should contain csv files. File names are strictly enforced.
            years: int or list
                The year(s) to load in the model, which can be supplied as an integer or a list of integers.
            backstop : bool (optional)
                If True, the model will include backstop technologies (default is False).

        Returns
        ----------

            network : pypsa.Network.
                A PyPSA network object representing the loaded model.

        Example
        ----------
        
            You can call the function as follows:

            >>> n = model.load_csv_from_dir("some/path/to/dir")

        '''

        network = pypsa.Network()

        network.import_from_csv_folder(path_to_dir)

        # --- calculate annualised costs --- #
        for generator in network.generators.index:
            network.generators.loc[generator, 'capital_cost'] = (
                network.generators.loc[generator, 'total_capital_cost'] * 
                cost_model.calculate_annuity(
                    n = network.generators.loc[generator, 'lifetime'],
                    r = 0.1,
                )
                + network.generators.loc[generator, 'annual_fixed_costs']
            )
        
        for storage_units in network.storage_units.index:
            network.storage_units.loc[storage_units, 'capital_cost'] = (
                network.storage_units.loc[storage_units, 'total_capital_cost'] * 
                cost_model.calculate_annuity(
                    n = network.storage_units.loc[storage_units, 'lifetime'],
                    r = 0.1,
                )
                + network.storage_units.loc[storage_units, 'annual_fixed_costs']
            )
                
        network.generators['capital_cost'] = network.generators['capital_cost'].round(0)
        
        # --- add backstop --- #
        if backstop:

            for bus in network.buses.index:

                network.add(
                    'Generator',
                    f'Backstop-{bus}',
                    bus=bus,
                    carrier='backstop',
                    p_nom=1e9,
                    capital_cost=1e9,
                    marginal_cost=1e9,
                )
        
        

        # --- choose years to load in --- #
        if isinstance(years, list):
            network.snapshots = network.snapshots[network.snapshots.year.isin(years)]
        else:
            network.snapshots = network.snapshots[network.snapshots.year == years]

        return network


    @staticmethod
    def get_available_models():
        '''Returns a list of stock models available in tz_pypsa.
        '''
        return utils.get_stock_models()
    

    @staticmethod
    def get_raw_stock_model(model_name):
        '''Returns a core model as a dictionary.
        '''
        return utils.load_yaml_from_dir(
            os.path.join( 
                utils.get_package_root(), 
                'stock_models', 
                model_name,
            ) 
        )
    
    @staticmethod
    def load_example_model(
        year : int = 2030,
        add_emissions_constraint : bool = True,
    ):
        '''
        Creates a simple model for testing and demos. This code is adapted from Fabian Neumann's PyPSA tutorial: https://fneum.github.io/data-science-for-esm/09-workshop-pypsa.html

        Parameters
        ----------

            path_to_dir : str
                Directory from which we load the model. This directory should contain at least one yaml file and a data/ directory containing the timeseries and cost data. File names are strictly enforced.

        Returns
        ----------

            network : pypsa.Network.
                A PyPSA network object representing the loaded model.

        Raises
        ----------

            ValueError: If the specified model is not found in the stock models.

        Example
        ----------
        
            You can call the function as follows:

            >>> model = Model.load_example_model()
        
        '''

        url = f"https://raw.githubusercontent.com/PyPSA/technology-data/master/outputs/costs_{year}.csv"
        costs = pd.read_csv(url, index_col=[0, 1])


        costs.loc[costs.unit.str.contains("/kW"), "value"] *= 1e3
        costs.unit = costs.unit.str.replace("/kW", "/MW")

        defaults = {
            "FOM": 0,
            "VOM": 0,
            "efficiency": 1,
            "fuel": 0,
            "investment": 0,
            "lifetime": 25,
            "CO2 intensity": 0,
            "discount rate": 0.07,
        }
        costs = costs.value.unstack().fillna(defaults)

        costs.at["OCGT", "fuel"] = costs.at["gas", "fuel"]
        costs.at["CCGT", "fuel"] = costs.at["gas", "fuel"]
        costs.at["OCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]
        costs.at["CCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]

        def annuity(r, n):
            return r / (1.0 - 1.0 / (1.0 + r) ** n)

        annuity(0.07, 20)

        costs["marginal_cost"] = costs["VOM"] + costs["fuel"] / costs["efficiency"]

        annuity = costs.apply(lambda x: annuity(x["discount rate"], x["lifetime"]), axis=1)

        costs["capital_cost"] = (annuity + costs["FOM"] / 100) * costs["investment"]

        url = (
            "https://tubcloud.tu-berlin.de/s/pKttFadrbTKSJKF/download/time-series-lecture-2.csv"
        )

        ts = pd.read_csv(url, index_col=0, parse_dates=True)

        ts.load *= 1e3

        resolution = 4
        ts = ts.resample(f"{resolution}h").first()

        n = pypsa.Network()

        n.add("Bus", "electricity")

        n.set_snapshots(ts.index)

        n.snapshot_weightings.loc[:, :] = resolution

        carriers = [
            "onwind",
            "offwind",
            "solar",
            "OCGT",
            "hydrogen storage underground",
            "battery storage",
        ]

        n.madd(
            "Carrier",
            carriers,
            color=["dodgerblue", "aquamarine", "gold", "indianred", "magenta", "yellowgreen"],
            co2_emissions=[costs.at[c, "CO2 intensity"] for c in carriers],
        )

        n.add(
            "Load",
            "demand",
            bus="electricity",
            p_set=ts.load,
        )

        n.add(
            "Generator",
            "OCGT",
            bus="electricity",
            carrier="OCGT",
            capital_cost=costs.at["OCGT", "capital_cost"],
            marginal_cost=costs.at["OCGT", "marginal_cost"],
            efficiency=costs.at["OCGT", "efficiency"],
            p_nom_extendable=True,
        )

        for tech in ["onwind", "offwind", "solar"]:
            n.add(
                "Generator",
                tech,
                bus="electricity",
                carrier=tech,
                p_max_pu=ts[tech],
                capital_cost=costs.at[tech, "capital_cost"],
                marginal_cost=costs.at[tech, "marginal_cost"],
                efficiency=costs.at[tech, "efficiency"],
                p_nom_extendable=True,
            )

        n.add(
            "StorageUnit",
            "battery storage",
            bus="electricity",
            carrier="battery storage",
            max_hours=6,
            capital_cost=costs.at["battery inverter", "capital_cost"]
            + 6 * costs.at["battery storage", "capital_cost"],
            efficiency_store=costs.at["battery inverter", "efficiency"],
            efficiency_dispatch=costs.at["battery inverter", "efficiency"],
            p_nom_extendable=True,
            cyclic_state_of_charge=True,
        )

        capital_costs = (
            costs.at["electrolysis", "capital_cost"]
            + costs.at["fuel cell", "capital_cost"]
            + 168 * costs.at["hydrogen storage underground", "capital_cost"]
        )

        n.add(
            "StorageUnit",
            "hydrogen storage underground",
            bus="electricity",
            carrier="hydrogen storage underground",
            max_hours=168,
            capital_cost=capital_costs,
            efficiency_store=costs.at["electrolysis", "efficiency"],
            efficiency_dispatch=costs.at["fuel cell", "efficiency"],
            p_nom_extendable=True,
            cyclic_state_of_charge=True,
        )

        if add_emissions_constraint:
            n.add(
                "GlobalConstraint",
                "CO2Limit",
                carrier_attribute="co2_emissions",
                sense="<=",
                constant=0,
            )

        return n