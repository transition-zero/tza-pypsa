import os
import pypsa

import xarray as xr

from . import helpers
from . import cost_model


class ASEAN:

    def __init__(
            self,
            node_subset = None,
            **kwargs,
    ):
        # set working directory
        abspath = os.path.abspath(__file__)
        dname = os.path.dirname(abspath)
        os.chdir(dname)

        # Load yaml data
        self.configs = helpers.get_yaml("ASEAN/configs.yaml")
        self.generators = helpers.get_yaml("ASEAN/generators.yaml")
        self.nodes = helpers.get_yaml("ASEAN/nodes.yaml")['nodes']
        self.links = helpers.get_yaml("ASEAN/links.yaml")['links']
        self.storages = helpers.get_yaml("ASEAN/storages.yaml")['storages']
        self.carriers = helpers.get_yaml("ASEAN/carriers.yaml")['carriers']
        self.global_constraints = helpers.get_yaml("ASEAN/constraints.yaml")['global_constraints']
        self.custom_constraints = helpers.get_yaml("ASEAN/constraints.yaml")['custom_constraints']

        # get year
        self.years = kwargs.get('years', self.configs['time_definition']['years'])

        # check if multi-year investment
        if isinstance(self.years, int):
            self.multi_year_investment = False
            self.configs['time_definition']['multi_year_investment'] = False
        elif isinstance(self.years, list) and len(self.years) == 1:
            self.multi_year_investment = False
            self.configs['time_definition']['multi_year_investment'] = False
            self.years = self.years[0]
        elif isinstance(self.years, list) and len(self.years) > 1:
            self.multi_year_investment = True
            self.configs['time_definition']['multi_year_investment'] = True

        # get input data (time series)
        self.timeseries = (
            xr
            .open_dataset(self.configs['file_paths']['timeseries'])
        )

        # get subset of buses
        self.subset = node_subset

        # get costs
        self.costs = cost_model.compute_costs()

        # filter costs for nearest year
        if isinstance(self.years, int):
            closest_year_in_data = min( self.costs.Year.unique(), key=lambda x:abs(x-self.years))
        else:
            closest_year_in_data = min( self.costs.Year.unique(), key=lambda x:abs(x-self.years[0]))

        self.costs = self.costs.loc[ self.costs.Year == closest_year_in_data].reset_index(drop=True).set_index(['Country','Technology'])
        
        # get subset of model by countries
        if not self.subset:
            pass
        else:
            self.links      = [link for link in self.links if link['id'][0:3] in node_subset and link['id'][6:9] in node_subset]
            self.nodes      = [node for node in self.nodes if node['id'][0:3] in node_subset]
            self.timeseries = self.timeseries.sel(node=[n for n in self.timeseries.node.values if n[0:3] in node_subset])
            self.costs      = self.costs.loc[node_subset]


    def create_model(
            self,
            backstop = False,
            **kwargs,
    ):
        return helpers.build_pypsa_model(
            configs = self.configs,
            nodes = self.nodes,
            generators = self.generators,
            links = self.links,
            storages = self.storages,
            carriers = self.carriers,
            timeseries = self.timeseries,
            years = self.years,
            costs = self.costs,
            global_constraints = self.global_constraints,
            backstop = backstop,
            **kwargs,
        )


class Pakistan(pypsa.Network):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add ASEAN specific attributes here
        self.asean_specific_attribute = "ASEAN specific attribute"