import os
import pypsa

from . import helpers

class ASEAN:

    def __init__(
            self,
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

        # get year
        self.year = kwargs.get('year', self.configs['time_definition']['year'])

        # get loads
        self.loads = helpers.compute_load(
            path_to_annual_demand=self.configs['file_paths']['annual_demand'],
            path_to_demand_profile=self.configs['file_paths']['demand_profile'],
            year=self.year,
        )

    def create_model(
            self
    ):
        return helpers.build_pypsa_model(
            configs = self.configs,
            nodes = self.nodes,
            links = self.links,
            generators = self.generators,
            loads = self.loads,
            year = self.year,
        )


class Pakistan(pypsa.Network):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add ASEAN specific attributes here
        self.asean_specific_attribute = "ASEAN specific attribute"