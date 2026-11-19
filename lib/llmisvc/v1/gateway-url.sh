#!/usr/bin/env bash
# Usage: gateway-url.sh <namespace> <llmisvc-name>
# Prints the URL that reaches the LLMInferenceService through the Envoy Gateway.
# In Kind there is no external load balancer, so we use the worker node IP and
# the Gateway service NodePort.
set -euo pipefail
ns="${1:?namespace}"; name="${2:?llmisvc name}"
node_ip=$(docker inspect "${KIND_CLUSTER_NAME:-kind}-worker" \
  --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
node_port=$(kubectl get svc -n envoy-gateway-system \
  -l gateway.envoyproxy.io/owning-gateway-name \
  -o jsonpath='{.items[0].spec.ports[0].nodePort}')
echo "http://${node_ip}:${node_port}/${ns}/${name}"
