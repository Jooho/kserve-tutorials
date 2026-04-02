#!/bin/bash
# Setup Kind cluster for KServe InferenceGraph Demo
# This script installs Kind, creates a cluster, and sets up prerequisites for KServe

set -e

CLUSTER_NAME="${CLUSTER_NAME:-kind}"
KIND_VERSION="${KIND_VERSION:-v0.30.0}"

echo "========================================="
echo "KServe Demo - Kind Cluster Setup"
echo "========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 0: Check prerequisites
echo "[0/5] Checking prerequisites..."

# Check Docker
if ! command_exists docker; then
    print_error "Docker is not installed"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker daemon is not running"
    echo "Please start Docker and try again"
    exit 1
fi
print_success "Docker is installed and running"

# Check kubectl
if ! command_exists kubectl; then
    print_warning "kubectl is not installed"
    echo "Installing kubectl..."

    # Detect OS
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    if [ "$ARCH" = "x86_64" ]; then
        ARCH="amd64"
    elif [ "$ARCH" = "aarch64" ]; then
        ARCH="arm64"
    fi

    KUBECTL_VERSION=$(curl -L -s https://dl.k8s.io/release/stable.txt)
    curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl"
    chmod +x kubectl
    sudo mv kubectl /usr/local/bin/

    print_success "kubectl installed"
else
    print_success "kubectl is already installed ($(kubectl version --client --short 2>/dev/null || kubectl version --client))"
fi

echo ""

# Step 1: Install Kind
echo "[1/5] Installing Kind..."

if command_exists kind; then
    CURRENT_KIND_VERSION=$(kind version | grep -oP 'kind v\K[0-9.]+' || echo "unknown")
    print_success "Kind is already installed (version: ${CURRENT_KIND_VERSION})"
else
    echo "Installing Kind ${KIND_VERSION}..."
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    if [ "$ARCH" = "x86_64" ]; then
        ARCH="amd64"
    elif [ "$ARCH" = "aarch64" ]; then
        ARCH="arm64"
    fi

    curl -Lo ./kind "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-${OS}-${ARCH}"
    chmod +x ./kind
    sudo mv ./kind /usr/local/bin/kind
    print_success "Kind ${KIND_VERSION} installed"
fi

echo ""

# Step 2: Check if cluster already exists
echo "[2/5] Checking existing cluster..."

if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    print_warning "Cluster '${CLUSTER_NAME}' already exists"
    read -p "Do you want to delete and recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting existing cluster..."
        kind delete cluster --name ${CLUSTER_NAME}
        print_success "Existing cluster deleted"
    else
        print_success "Using existing cluster"
        kubectl cluster-info --context kind-${CLUSTER_NAME}
        echo ""
        echo "========================================="
        echo "Cluster is ready!"
        echo "========================================="
        exit 0
    fi
fi

echo ""

# Step 3: Create Kind cluster
echo "[3/5] Creating Kind cluster..."

cat <<EOF > /tmp/kind-cluster-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${CLUSTER_NAME}
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
EOF

kind create cluster --config /tmp/kind-cluster-config.yaml

print_success "Kind cluster '${CLUSTER_NAME}' created"

# Set kubectl context
kubectl cluster-info --context kind-${CLUSTER_NAME}

echo ""

# Step 4: Install local path provisioner (for PVC)
echo "[4/6] Configuring storage provisioner..."

# Kind already includes local-path-provisioner, just verify it
kubectl get storageclass standard >/dev/null 2>&1 || \
    kubectl patch storageclass local-path -p '{"metadata": {"name":"standard"}}'

print_success "Storage provisioner ready"

echo ""

# Step 5: Install Nginx Ingress Controller
echo "[5/6] Installing Nginx Ingress Controller..."

INGRESS_NGINX_VERSION="${INGRESS_NGINX_VERSION:-v1.11.3}"

# Ensure control-plane node has ingress-ready label
kubectl label node kind-${CLUSTER_NAME}-control-plane ingress-ready=true --overwrite 2>/dev/null || true

# Install nginx ingress controller
echo "Installing ingress-nginx ${INGRESS_NGINX_VERSION}..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-${INGRESS_NGINX_VERSION}/deploy/static/provider/kind/deploy.yaml

# Wait for ingress controller to be ready
echo "Waiting for ingress controller to be ready..."
sleep 5
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=300s

print_success "Nginx Ingress Controller installed"

echo ""

# Step 6: Verify cluster
echo "[6/6] Verifying cluster..."

echo "Waiting for nodes to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=300s

echo ""
echo "Cluster nodes:"
kubectl get nodes

echo ""
echo "Storage classes:"
kubectl get storageclass

echo ""
echo "========================================="
echo "✓ Kind Cluster Setup Complete!"
echo "========================================="
echo ""
echo "Cluster name: ${CLUSTER_NAME}"
echo "Context: kind-${CLUSTER_NAME}"
echo ""
echo "Next steps:"
echo "  ./scripts/1-2.install_kserve.sh"
echo "  ./scripts/1-3.train_models.sh"
echo "  ./scripts/1-4.build_combiner.sh"
echo "  ./scripts/2.deploy.sh"
echo ""
echo "To delete this cluster later:"
echo "  kind delete cluster --name ${CLUSTER_NAME}"
echo ""
