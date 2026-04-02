#!/bin/bash
# Step 2: Install KServe and configure for Nginx Ingress

set -e

GREEN='\033[0;32m'
NC='\033[0m'

if kubectl get crd inferenceservices.serving.kserve.io >/dev/null 2>&1; then
    echo -e "${GREEN}✓ KServe is already installed, skipping${NC}"
    exit 0
fi

echo "Installing KServe v0.17.0..."
curl -s "https://raw.githubusercontent.com/kserve/kserve/refs/heads/master/install/v0.17.0/kserve-standard-mode-full-install-with-manifests.sh" | bash

echo "Configuring KServe for Nginx Ingress..."
kubectl get cm inferenceservice-config -n kserve -o json | \
    python3 -c "
import sys, json
cm = json.load(sys.stdin)
ingress = json.loads(cm['data']['ingress'])
ingress['ingressClassName'] = 'nginx'
ingress['ingressDomain'] = '127.0.0.1.sslip.io'
cm['data']['ingress'] = json.dumps(ingress)
json.dump(cm, sys.stdout)
" | kubectl apply -f -

echo "Restarting KServe controller..."
kubectl rollout restart deployment/kserve-controller-manager -n kserve
kubectl rollout status deployment/kserve-controller-manager -n kserve --timeout=120s

echo -e "${GREEN}✓ KServe installed and configured${NC}"
