import os
import pypsa

import xarray as xr

from . import helpers

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
        self.year = kwargs.get('year', self.configs['time_definition']['year'])

        # get input data (time series)
        self.timeseries = xr.open_dataset(self.configs['file_paths']['timeseries'])

        # get subset of countries
        self.subset = countries


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
            year = self.year,
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