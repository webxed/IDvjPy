#!/bin/bash

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install the dependencies
pip install -r requirements.txt

# Initialize the database
python database.py

echo "Setup complete. To run the application, use: python app.py"
