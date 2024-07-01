import os
import pypsa

import xarray as xr

from . import helpers
from . import cost_model

class ASEAN:

    def __init__(
            self,
            countries = None,
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
        self.global_constraints = helpers.get_yaml("ASEAN/constraints.yaml")['global_constraints']
        self.custom_constraints = helpers.get_yaml("ASEAN/constraints.yaml")['custom_constraints']

        # get year
        self.years = kwargs.get('years', self.configs['time_definition']['years'])

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
            .resample(snapshot=self.configs['time_definition']['frequency'])
            .mean()
        )

        # get subset of countries
        self.subset = countries

        # get costs
        self.costs = cost_model.compute_costs()

        # filter costs for nearest year
        if isinstance(self.years, int):
            closest_year_in_data = min( self.costs.Year.unique(), key=lambda x:abs(x-self.years))
        else:
            closest_year_in_data = min( self.costs.Year.unique(), key=lambda x:abs(x-self.years[0]))

        self.costs = self.costs.loc[ self.costs.Year == closest_year_in_data].reset_index(drop=True).set_index(['Country','Technology'])
        


    def create_model(
            self,
            **kwargs,
    ):
        return helpers.build_pypsa_model(
            configs = self.configs,
            nodes = self.nodes,
            links = self.links,
            generators = self.generators,
            timeseries = self.timeseries,
            years = self.years,
            costs = self.costs,
            countries = self.subset,
            global_constraints=self.global_constraints,
            custom_constraints=self.custom_constraints,
            **kwargs,
        )


class Pakistan(pypsa.Network):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add ASEAN specific attributes here
        self.asean_specific_attribute = "ASEAN specific attribute"