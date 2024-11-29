import os
import yaml

def get_package_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_stock_models() -> list:
    '''Returns a list of pre-defined stock models available in tz_pypsa.
    '''
    abspath = get_package_root()
    entries = os.listdir( os.path.join(abspath, 'stock_models') )
    return [entry for entry in entries if os.path.isdir(os.path.join(abspath, 'stock_models', entry))]


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


def get_github_token(
        path_to_token : str = '_GITHUB_TOKEN_'
) -> str:
    '''Get the GitHub token from a file or ask the user to input it.
    '''
    # Check if the token file exists
    if os.path.exists(path_to_token):
        with open(path_to_token, 'r') as file:
            token = file.read().strip()
            if token:
                return token
            else:
                raise ValueError("Token file is empty.")
    
    # If the file doesn't exist, ask the user to input a token
    token = input("Enter your GitHub token (https://github.com/settings/tokens): \n").strip()

    # Save the token to the file
    with open(path_to_token, 'w') as file:
        file.write(token)
    
    if not token:
        raise ValueError("No token provided!\nPlease generate a token on GitHub: https://github.com/settings/tokens")
    
    return token


def get_data_from_github_with_auth(
        path_to_file: str,
        personal_access_token: str,
        remote_data: dict,
        branch: str = 'main'  # Default to 'main' branch if not specified
):
    '''
    Check for data in a remote repository and return the data as a StringIO or BytesIO object.

        Parameters
        ----------
            path_to_file : str
                The path to the file in the remote repository.
            personal_access_token : str
                The personal access token for the GitHub API.
            remote_data : dict
                A dictionary containing the GitHub API information.
            branch : str, optional
                The branch from which to fetch the file (default is 'main').

        Returns
        ----------
            StringIO or BytesIO:
                The data from the remote repository as a StringIO or BytesIO object.

        Raises
        ----------
            Exception:
                If the response code is not 200, it raises an exception with the response code.
    '''

    import requests
    from io import StringIO, BytesIO

    REPO_OWNER = remote_data['github_api_info']['repo_owner']
    REPO_NAME = remote_data['github_api_info']['repo_name']

    # GitHub API URL for the file with the branch parameter
    url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path_to_file}?ref={branch}'

    # Headers with authentication
    headers = {
        'Authorization': f'token {personal_access_token}',
        'Accept': 'application/vnd.github.v3.raw'
    }

    # Send request to GitHub API
    response = requests.get(url, headers=headers)

    # Check for successful response
    if response.status_code == 200:
        if '.csv' in path_to_file:
            return StringIO(response.text) 
        elif '.nc' in path_to_file:
            return BytesIO(response.content)
    else:
        raise Exception(f'\nCould not access remote repository.\nRepository: {url}\nResponse code: {response.status_code}')
