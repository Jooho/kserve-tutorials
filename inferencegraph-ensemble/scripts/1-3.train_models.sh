#!/bin/bash
# Step 3: Install Python dependencies and train models

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
cd "${PROJECT_DIR}"

GREEN='\033[0;32m'
NC='\033[0m'

if [ -d "models/xgboost-predictor" ] && [ -d "models/lightgbm-predictor" ]; then
    echo -e "${GREEN}✓ Models already trained, skipping${NC}"
    exit 0
fi

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Training models..."
python3 scripts/train.py

echo -e "${GREEN}✓ Models trained${NC}"
