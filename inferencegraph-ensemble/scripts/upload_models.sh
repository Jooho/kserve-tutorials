#!/bin/bash
# Upload trained models to PVC

set -e

echo "========================================="
echo "Uploading Models to PVC"
echo "========================================="

PVC_NAME="${PVC_NAME:-model-pvc}"
NAMESPACE="${NAMESPACE:-kserve-graph-demo}"

# Check if models exist
if [ ! -d "models" ]; then
    echo "Error: models directory not found. Please run train.py first."
    exit 1
fi

echo "Creating temporary pod to mount PVC..."

# Create a temporary pod to mount the PVC
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: model-upload-helper
  namespace: ${NAMESPACE}
spec:
  containers:
  - name: uploader
    image: busybox
    command: ["sleep", "3600"]
    volumeMounts:
    - name: model-storage
      mountPath: /mnt/models
  volumes:
  - name: model-storage
    persistentVolumeClaim:
      claimName: ${PVC_NAME}
  restartPolicy: Never
EOF

echo "Waiting for pod to be ready..."
kubectl wait --for=condition=Ready pod/model-upload-helper -n ${NAMESPACE} --timeout=60s

echo "Copying models to PVC..."

# Copy each model directory
for model_dir in models/*/; do
    model_name=$(basename ${model_dir})
    echo "  - Uploading ${model_name}..."
    kubectl cp ${model_dir} ${NAMESPACE}/model-upload-helper:/mnt/models/${model_name}
done

echo "Verifying uploaded files..."
kubectl exec -n ${NAMESPACE} model-upload-helper -- ls -R /mnt/models/

echo "Cleaning up helper pod..."
kubectl delete pod model-upload-helper -n ${NAMESPACE} --force --grace-period=0

echo "========================================="
echo "✓ Models uploaded successfully!"
echo "========================================="
