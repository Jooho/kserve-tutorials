#!/usr/bin/env bash
# envs/kind-llmisvc/v1 — idempotent: safe to run before every tutorial.
set -Eeuo pipefail

PROFILE="kind-llmisvc/v1"
: "${KSERVE_VERSION:?KSERVE_VERSION must be set (the tutorial setup block does this)}"
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-kind}"
TUT_CACHE="${TUT_CACHE:-$HOME/.cache/kserve-tutorials}"
KSERVE_SRC="$TUT_CACHE/kserve-$KSERVE_VERSION"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
log() { echo "[env $PROFILE] $*"; }

# 0. The CLI tools this environment needs (tools.env), installed into the
#    repository and put on PATH for this script only. Docker is a prerequisite.
command -v docker >/dev/null && docker info >/dev/null 2>&1 \
  || { log "Docker is not running. Install/start Docker, then run ./tut doctor"; exit 1; }
"$REPO/tools/install-tools.sh" "$HERE/tools.env"
# shellcheck source=/dev/null
source "$HERE/tools.env"
export PATH="$REPO/.tools/kind/$KIND:$REPO/.tools/kubectl/$KUBECTL:$REPO/.tools/helm/$HELM:$REPO/.tools/cloud-provider-kind/$CLOUD_PROVIDER_KIND:$PATH"

# 1. Reuse the cluster when it was built by this profile with the same KServe version.
if kind get clusters 2>/dev/null | grep -x "$KIND_CLUSTER_NAME" >/dev/null; then
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
# Retry the KServe installer (up to 3 attempts) because two failures were seen
# on fresh CI runners:
#  - it applies the LLMInferenceServiceConfigs right after the controller
#    Deployment is Available, before the validating webhook accepts connections
#    ("connection refused"); a plain re-run then skips the step ("already
#    installed"), hence FORCE_UPGRADE=true on retries;
#  - transient download errors (e.g. proxy.golang.org while building
#    cloud-provider-kind).
webhook_ready() {
  kubectl -n kserve get service llmisvc-webhook-server-service >/dev/null 2>&1 || return 0
  for _ in $(seq 1 60); do
    ip=$(kubectl -n kserve get endpoints llmisvc-webhook-server-service \
      -o jsonpath='{.subsets[0].addresses[0].ip}' 2>/dev/null || true)
    [[ -n "$ip" ]] && return 0
    sleep 5
  done
  return 1
}
for attempt in 1 2 3; do
  if [[ $attempt -eq 1 ]]; then
    ./hack/kserve-install.sh --type llmisvc --kserve-version "$KSERVE_VERSION" && break
  else
    FORCE_UPGRADE=true ./hack/kserve-install.sh --type llmisvc --kserve-version "$KSERVE_VERSION" && break
  fi
  [[ $attempt -eq 3 ]] && { log "KServe install failed after 3 attempts"; exit 1; }
  log "install attempt $attempt failed; waiting for the llmisvc webhook, then retrying"
  webhook_ready || log "webhook endpoint still not ready, retrying anyway"
  sleep 10
done

# Known upstream issue (KServe v0.18.0 - v0.19.0): the well-known scheduler
# config points to ghcr.io/llm-d/llm-d-inference-scheduler:v0.7.1, which is no
# longer publicly pullable (ghcr.io answers 403). llm-d renamed the image to
# llm-d-router-endpoint-picker (first tag v0.9.0; KServe master uses v1.0.0).
# Point the config at the renamed image so LLMInferenceServices can start.
SCHEDULER_IMAGE="${TUT_SCHEDULER_IMAGE:-ghcr.io/llm-d/llm-d-router-endpoint-picker:v0.9.0}"
if kubectl -n kserve get llminferenceserviceconfig kserve-config-llm-scheduler -o yaml 2>/dev/null \
    | grep "llm-d-inference-scheduler:v0.7.1" >/dev/null; then   # not -q: SIGPIPE under pipefail (CI-007)
  log "patching kserve-config-llm-scheduler: llm-d-inference-scheduler:v0.7.1 -> $SCHEDULER_IMAGE"
  kubectl -n kserve get llminferenceserviceconfig kserve-config-llm-scheduler -o json \
    | sed "s#ghcr.io/llm-d/llm-d-inference-scheduler:v0.7.1#${SCHEDULER_IMAGE}#g" \
    | kubectl replace -f -
fi

# 4. Readiness gate: the profile is only "done" when the controller is serving.
kubectl wait --for=condition=Established crd/llminferenceservices.serving.kserve.io --timeout=120s
kubectl -n kserve wait --for=condition=Available deployment --all --timeout=600s

# 5. Record what built this cluster (used by step 1 next time).
kubectl -n kube-system create configmap tut-env \
  --from-literal=profile="$PROFILE" --from-literal=kserve_version="$KSERVE_VERSION" \
  --dry-run=client -o yaml | kubectl apply -f -
log "ready"
