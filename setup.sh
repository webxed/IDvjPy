#!/usr/bin/env bash

# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install the dependencies
pip install -r requirements.txt

# Database is initialized automatically on first run
echo "Setup complete. To run the application, use: python3 app.py"
