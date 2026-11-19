#!/usr/bin/env bash
# envs/kind-llmisvc/v1 — remove everything setup.sh created.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
# shellcheck source=/dev/null
source "$HERE/tools.env"
export PATH="$REPO/.tools/kind/$KIND:$REPO/.tools/kubectl/$KUBECTL:$PATH"
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-kind}"
kind delete cluster --name "$KIND_CLUSTER_NAME" 2>/dev/null || true
docker rm -f kind-registry >/dev/null 2>&1 || true
echo "[env kind-llmisvc/v1] removed cluster '$KIND_CLUSTER_NAME' and registry"
