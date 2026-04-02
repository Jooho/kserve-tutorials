#!/bin/bash
# Prepare all prerequisites for KServe InferenceGraph Demo
#
# This script runs all preparation steps in order:
#   1. Kind cluster setup + Nginx Ingress
#   2. KServe installation
#   3. Python dependencies + model training
#   4. Combiner image build & load

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MLSERVER_IMAGE="${MLSERVER_IMAGE:-docker.io/seldonio/mlserver:1.5.0}"
CLUSTER_NAME="${CLUSTER_NAME:-kind}"

echo ""
echo "========================================="
echo " KServe InferenceGraph Demo - Preparation"
echo "========================================="

# Pre-pull large MLServer image in background
echo "Starting background pull: ${MLSERVER_IMAGE}..."
docker pull ${MLSERVER_IMAGE} &
PULL_PID=$!

"${SCRIPT_DIR}/1-1.setup_kind_cluster.sh"
"${SCRIPT_DIR}/1-2.install_kserve.sh"
"${SCRIPT_DIR}/1-3.train_models.sh"
"${SCRIPT_DIR}/1-4.build_combiner.sh"

# Wait for MLServer image pull and load into Kind
echo "Waiting for MLServer image pull to complete..."
wait ${PULL_PID}
echo "Loading MLServer image into Kind..."
kind load docker-image ${MLSERVER_IMAGE} --name ${CLUSTER_NAME}

echo ""
echo -e "\033[0;32m========================================="
echo " ✓ All preparations complete!"
echo "========================================="
echo ""
echo "Next step: deploy the InferenceGraph"
echo "  ./scripts/2.deploy.sh"
echo -e "\033[0m"
