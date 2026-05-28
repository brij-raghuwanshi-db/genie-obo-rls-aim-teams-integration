#!/bin/bash
# Azure App Service startup script for Genie API OBO RLS service
#
# This script is executed by Azure App Service when starting the application.
# Configure in Azure Portal: App Service > Configuration > General settings > Startup Command
# Set to: startup.sh

set -e

# Change to deployment directory
cd /home/site/wwwroot

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Get the port from environment variable (Azure sets WEBSITES_PORT or defaults to 8000)
PORT="${WEBSITES_PORT:-${PORT:-8000}}"

echo "Starting Genie Bot service on port $PORT"

# Set PYTHONPATH to include src directory where the module lives
export PYTHONPATH="/home/site/wwwroot/src:$PYTHONPATH"

# Run the bot server (Teams integration mode)
# Note: "server" subcommand is required before --mode
exec python -m genie_api_obo_rls.main server --mode bot --host 0.0.0.0 --port "$PORT"
