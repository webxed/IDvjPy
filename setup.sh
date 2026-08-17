#!/usr/bin/env bash

# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install the dependencies
pip install -r requirements.txt

# Database file is created empty on first run (not shipped in git).
echo "Setup complete. To run: python3 app.py"
echo "Optional handbook tags: python3 src/seed_linux_commands.py --seed"
echo "Optional k8s playbooks:  python3 src/seed_k8s_chains.py --seed"
echo "Optional git playbooks:  python3 src/seed_git.py --seed"
echo "Optional ops handbooks:  python3 src/seed_ops.py --seed"
