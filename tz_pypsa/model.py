import os
import yaml
import pypsa

import pandas as pd
import xarray as xr

# ---
# Local imports

from . import cost_model

from .helpers import (
    load_yaml_from_dir,
    get_core_models,
    get_github_token,
    get_data_from_github_with_auth,
)

from .build_network import (
    build_pypsa_network,

)

# ---

class Model:

    '''

    Methods
    ----------

    get_available_models()
        Returns a list of core models available in tz_pypsa.

    load_model(model_name)
        Load a model from pre-defined core models.

    load_from_dir(path_to_dir)
        Loads a model from a directory containing yaml and .nc files.
    
    '''


    @staticmethod
    def load_model(
        model_name,
        years : list = None,
        select_nodes : list = None,
        frequency : str = None,
        backstop : bool = False,
        set_global_constraints : bool = False,
        **kwargs,
    ) -> pypsa.Network:

        '''
        Load a model from pre-defined core models.

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

            ValueError: If the specified model is not found in the core models.

        Example
        ----------
        
            To load a model named "example_model", you can call the function as follows:

            >>> model = load_model("example_model")

        This function loads a model from the core models available in tz_pypsa. It first checks if the specified model exists in the core models. If found, it loads the model YAML file and the associated timeseries data. Finally, it builds a PyPSA network using the loaded model, timeseries, and optional costs.

        Notes
        ----------

            To see a list of core models available in tz_pypsa, you can run the following command:

            >>> Model.get_available_models()

        '''

        # get core model
        if model_name in get_core_models():
            model = load_yaml_from_dir(
                os.path.join( 
                    os.path.dirname(os.path.abspath(__file__)), 
                    'core', 
                    model_name,
                ) 
            )
        else:
            raise ValueError(f"Model {model_name} not found in core models.")
        
        # --- get model years and frequency --- #
        if not years:
            years = model['time_definition']['years']
        
        if not frequency:
            frequency = model['time_definition']['frequency']

        # ---
        # Load data from remote directories

        PERSONAL_ACCESS_TOKEN = get_github_token()

        # load capital outlay file
        url = (
                get_data_from_github_with_auth(
                path_to_file = model['remote_data']['technology_costs']['path_to_cost'] + 'costs_capital_outlay_during_construction.csv',
                personal_access_token = PERSONAL_ACCESS_TOKEN,
                remote_data = model['remote_data'],
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
            get_data_from_github_with_auth(
                path_to_file = model['remote_data']['technology_costs']['path_to_cost'] + 'technology_costs.csv',
                personal_access_token = PERSONAL_ACCESS_TOKEN,
                remote_data = model['remote_data'],
            )
        )

        technology_costs = (
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

        # get timeseries
        datasets = []
        for year in years:

            url = get_data_from_github_with_auth(
                path_to_file=model['remote_data']['timeseries']['path_to_timeseries'] + f'timeseries_{year}.nc',
                personal_access_token=PERSONAL_ACCESS_TOKEN,
                remote_data=model['remote_data'],
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

        # build network
        return build_pypsa_network(
            model = model,
            timeseries = timeseries,
            costs = costs,
            years = years,
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

            ValueError: If the specified model is not found in the core models.

        Example
        ----------
        
            To load a model named "example_model", you can call the function as follows:

            >>> model = load_from_dir("some/path/to/dir")

        This function loads a model from the core models available in tz_pypsa. It first checks if the specified model exists in the core models. If found, it loads the model YAML file and the associated timeseries data. Finally, it builds a PyPSA network using the loaded model, timeseries, and optional costs.

        '''

        return Exception("This function is not yet implemented.")
        
        # try:
        #     #print( 'Loading model from: ' + path_to_dir)
        #     model = load_yaml_from_dir(path_to_dir)
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
    def get_available_models():
        '''Returns a list of core models available in tz_pypsa.
        '''
        return get_core_models()
    

    @staticmethod
    def get_raw_core_model(model_name):
        '''Returns a core model as a dictionary.
        '''
        return load_yaml_from_dir(
            os.path.join( 
                os.path.dirname(os.path.abspath(__file__)), 
                'core', 
                model_name,
            ) 
        )