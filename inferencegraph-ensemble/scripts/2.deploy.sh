#!/bin/bash
# Deploy KServe InferenceGraph for California Housing Price Prediction

set -e

NAMESPACE="${NAMESPACE:-kserve-graph-demo}"

echo "========================================="
echo "Deploying KServe InferenceGraph Demo"
echo "========================================="

# Step 0: Create namespace if not exists
echo ""
echo "[0/5] Creating namespace..."
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# Step 1: Create PVC
echo ""
echo "[1/5] Creating PersistentVolumeClaim..."
kubectl apply -f k8s/pvc.yaml

# Check PVC status (don't wait too long - it will be bound when pod mounts it)
echo "Checking PVC status..."
kubectl get pvc/model-pvc -n ${NAMESPACE} || true
echo "Note: PVC may remain in Pending state until a pod mounts it. This is normal."
sleep 2

# Step 2: Upload models to PVC
echo ""
echo "[2/5] Uploading trained models to PVC..."
./scripts/upload_models.sh

# Step 3: Deploy InferenceServices (XGBoost and LightGBM)
echo ""
echo "[3/5] Deploying InferenceServices..."
kubectl apply -f k8s/inferenceservices/xgboost-predictor.yaml
kubectl apply -f k8s/inferenceservices/lightgbm-predictor.yaml
kubectl apply -f k8s/inferenceservices/ensemble-combiner.yaml

# Wait for InferenceServices to be ready
echo "Waiting for InferenceServices to be ready..."
for isvc in xgboost-predictor lightgbm-predictor ensemble-combiner; do
    echo "  - Waiting for ${isvc}..."
    kubectl wait --for=condition=Ready isvc/${isvc} -n ${NAMESPACE} --timeout=300s || echo "Warning: ${isvc} not ready yet"
done

# Step 4: Deploy InferenceGraph
echo ""
echo "[4/5] Deploying InferenceGraph..."
kubectl apply -f k8s/inferencegraph/housing-price-graph.yaml

# Step 5: Create Ingress for InferenceGraph
echo ""
echo "[5/5] Creating Ingress for InferenceGraph..."
kubectl apply -f k8s/ingress/housing-price-ingress.yaml

echo ""
echo "========================================="
echo "✓ Deployment Complete!"
echo "========================================="
echo ""
echo "Check deployment status:"
echo "  kubectl get isvc -n ${NAMESPACE}"
echo "  kubectl get ig -n ${NAMESPACE}"
echo ""
echo "To test the InferenceGraph:"
echo "  ./scripts/test_inferencegraph.sh"
echo ""
