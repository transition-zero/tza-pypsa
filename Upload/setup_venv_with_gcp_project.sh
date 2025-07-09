#!/bin/bash

# Usage: bash setup_venv_with_gcp_project.sh <GCP_PROJECT_ID> <VENV_PATH>
# Example: bash setup_venv_with_gcp_project.sh tz-data-dev ~/venvs/tz-data-dev-venv

set -e

GCP_PROJECT_ID="$1"
VENV_PATH="$2"

if [[ -z "$GCP_PROJECT_ID" || -z "$VENV_PATH" ]]; then
  echo "Usage: $0 <GCP_PROJECT_ID> <VENV_PATH>"
  exit 1
fi

echo "Creating virtual environment at $VENV_PATH..."
python3 -m venv "$VENV_PATH"

echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

echo "Installing Google Cloud libraries..."
pip install --upgrade pip
pip install google-cloud-storage google-cloud-bigquery google-auth pandas pypsa pandas-gbq pyarrow

echo "Setting project env var in activate script..."
ENV_FILE="$VENV_PATH/bin/activate_project_env.sh"
echo "export GOOGLE_CLOUD_PROJECT=$GCP_PROJECT_ID" > "$ENV_FILE"
chmod +x "$ENV_FILE"

# Append to venv's activate script
ACTIVATE_SCRIPT="$VENV_PATH/bin/activate"
if ! grep -q "activate_project_env.sh" "$ACTIVATE_SCRIPT"; then
  echo "source \"\$VIRTUAL_ENV/bin/activate_project_env.sh\"" >> "$ACTIVATE_SCRIPT"
fi

echo "Done! Activate your venv with:"
echo "source $VENV_PATH/bin/activate"
echo "This will set GOOGLE_CLOUD_PROJECT=$GCP_PROJECT_ID"
