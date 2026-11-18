#!/usr/bin/env bash
# envs/kind-llmisvc/v1 — idempotent: safe to run before every tutorial.
set -Eeuo pipefail

PROFILE="kind-llmisvc/v1"
: "${KSERVE_VERSION:?KSERVE_VERSION must be set (the tutorial setup block does this)}"
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-kind}"
TUT_CACHE="${TUT_CACHE:-$HOME/.cache/kserve-tutorials}"
KSERVE_SRC="$TUT_CACHE/kserve-$KSERVE_VERSION"
log() { echo "[env $PROFILE] $*"; }

# 1. Reuse the cluster when it was built by this profile with the same KServe version.
if kind get clusters 2>/dev/null | grep -qx "$KIND_CLUSTER_NAME"; then
  marker=$(kubectl --context "kind-$KIND_CLUSTER_NAME" -n kube-system get configmap tut-env \
    -o jsonpath='{.data.profile}@{.data.kserve_version}' 2>/dev/null || true)
  if [[ "$marker" == "$PROFILE@$KSERVE_VERSION" ]]; then
    kubectl config use-context "kind-$KIND_CLUSTER_NAME" >/dev/null
    log "cluster '$KIND_CLUSTER_NAME' already provides $PROFILE with KServe $KSERVE_VERSION — reusing"
    exit 0
  fi
  if [[ "${TUT_ENV_RECREATE:-0}" != "1" ]]; then
    log "cluster '$KIND_CLUSTER_NAME' exists but was built as '${marker:-unknown}'."
    log "Delete it ($(dirname "$0")/teardown.sh) or rerun with TUT_ENV_RECREATE=1."
    exit 1
  fi
  "$(dirname "$0")/teardown.sh"
fi

# 2. KServe sources pinned to the requested tag (never master).
if [[ ! -d "$KSERVE_SRC/.git" ]]; then
  log "fetching kserve $KSERVE_VERSION"
  mkdir -p "$TUT_CACHE"
  git clone --quiet --depth 1 --branch "$KSERVE_VERSION" https://github.com/kserve/kserve.git "$KSERVE_SRC"
fi
cd "$KSERVE_SRC"

# 3. Cluster + KServe LLMInferenceService stack.
log "creating kind cluster '$KIND_CLUSTER_NAME' with local registry"
KIND_CLUSTER_NAME="$KIND_CLUSTER_NAME" ./hack/setup/dev/manage.kind-with-registry.sh
log "installing KServe $KSERVE_VERSION (llmisvc)"
./hack/kserve-install.sh --type llmisvc --kserve-version "$KSERVE_VERSION"

# 4. Readiness gate: the profile is only "done" when the controller is serving.
kubectl wait --for=condition=Established crd/llminferenceservices.serving.kserve.io --timeout=120s
kubectl -n kserve wait --for=condition=Available deployment --all --timeout=600s

# 5. Record what built this cluster (used by step 1 next time).
kubectl -n kube-system create configmap tut-env \
  --from-literal=profile="$PROFILE" --from-literal=kserve_version="$KSERVE_VERSION" \
  --dry-run=client -o yaml | kubectl apply -f -
log "ready"
