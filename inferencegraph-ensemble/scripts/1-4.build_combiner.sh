#!/bin/bash
# Step 4: Build ensemble combiner image and load into Kind

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
cd "${PROJECT_DIR}"

CLUSTER_NAME="${CLUSTER_NAME:-kind}"
COMBINER_IMAGE="${COMBINER_IMAGE:-ensemble-combiner:latest}"

GREEN='\033[0;32m'
NC='\033[0m'

echo "Building combiner image..."
docker build -t ${COMBINER_IMAGE} combiner/

echo "Loading image into Kind cluster..."
kind load docker-image ${COMBINER_IMAGE} --name ${CLUSTER_NAME}

echo -e "${GREEN}✓ Combiner image built and loaded into Kind${NC}"
