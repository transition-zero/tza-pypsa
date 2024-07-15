import os
import yaml


def get_core_models() -> list:
    '''Returns a list of pre-defined core models available in tz_pypsa.
    '''
    abspath = os.path.dirname( os.path.abspath(__file__) ) 
    entries = os.listdir( os.path.join(abspath, 'core') )
    return [entry for entry in entries if os.path.isdir(os.path.join(abspath, 'core', entry))]


def load_yaml_from_dir(path_to_dir) -> dict:
    '''Load all yaml files in a directory into a dictionary
    '''
    all_yaml_data = {}
    # Iterate over all files in the specified folder
    for filename in os.listdir(path_to_dir):
        
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            file_path = os.path.join(path_to_dir, filename)
            with open(file_path, 'r') as file:
                try:
                    data = yaml.safe_load(file)
                    all_yaml_data[ list(data.keys())[0] ] = data[ list(data.keys())[0] ]
                except yaml.YAMLError as exc:
                    print(f"Error parsing {filename}: {exc}")
    
    return all_yaml_data