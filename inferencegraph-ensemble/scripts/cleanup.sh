#!/bin/bash
# Cleanup KServe InferenceGraph demo resources

set -e

NAMESPACE="${NAMESPACE:-kserve-graph-demo}"

echo "========================================="
echo "Cleaning up KServe InferenceGraph Demo"
echo "========================================="

echo ""
echo "[1/3] Deleting InferenceGraph..."
kubectl delete -f k8s/inferencegraph/housing-price-graph.yaml --ignore-not-found=true

echo ""
echo "[2/3] Deleting InferenceServices..."
kubectl delete -f k8s/inferenceservices/ --ignore-not-found=true

echo ""
echo "[3/3] Deleting PVC..."
kubectl delete -f k8s/pvc.yaml --ignore-not-found=true

echo ""
echo "========================================="
echo "✓ Cleanup Complete!"
echo "========================================="
