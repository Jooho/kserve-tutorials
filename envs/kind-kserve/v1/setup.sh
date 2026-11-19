#!/usr/bin/env bash
# envs/kind-kserve/v1 — idempotent: safe to run before every tutorial.
#
# One Kind cluster for every kind of KServe tutorial. What gets installed is
# chosen per tutorial (env_options in tutorial.yaml; the generated setup step
# passes them here) and handed to KServe's own installer, hack/kserve-install.sh:
#   TUT_ENV_TYPES  comma list of kserve, localmodel, llmisvc   (default: kserve)
#   TUT_ENV_MODE   standard | serverless  (for type kserve;     default: standard)
#   TUT_ENV_KEDA   true | false           (standard mode only;  default: false)
# A cluster this profile built is reused, and only what is missing is added:
# a learning path grows one cluster instead of recreating it.
set -Eeuo pipefail

PROFILE="kind-kserve/v1"
: "${KSERVE_VERSION:?KSERVE_VERSION must be set (the tutorial setup block does this)}"
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-kind}"
TUT_CACHE="${TUT_CACHE:-$HOME/.cache/kserve-tutorials}"
KSERVE_SRC="$TUT_CACHE/kserve-$KSERVE_VERSION"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
log() { echo "[env $PROFILE] $*"; }

# Options, normalized: types sorted and unique, so "llmisvc,kserve" == "kserve,llmisvc".
norm() { tr ', ' '\n\n' | sed '/^$/d' | sort -u | paste -sd, -; }
has() { [[ ",$1," == *",$2,"* ]]; }
WANT="$(printf '%s' "${TUT_ENV_TYPES:-kserve}" | norm)"
MODE="${TUT_ENV_MODE:-standard}"
KEDA="${TUT_ENV_KEDA:-false}"
for t in ${WANT//,/ }; do
  [[ "$t" =~ ^(kserve|localmodel|llmisvc)$ ]] || { log "unknown type '$t' (kserve, localmodel, llmisvc)"; exit 2; }
done
[[ "$MODE" =~ ^(standard|serverless)$ ]] || { log "unknown mode '$MODE' (standard, serverless)"; exit 2; }
[[ "$KEDA" =~ ^(true|false)$ ]] || { log "TUT_ENV_KEDA must be true or false"; exit 2; }
[[ "$KEDA" == true && "$MODE" != standard ]] && { log "KEDA needs mode standard"; exit 2; }

# 0. The CLI tools this environment needs (tools.env), installed into the
#    repository and put on PATH for this script only. Docker is a prerequisite.
command -v docker >/dev/null && docker info >/dev/null 2>&1 \
  || { log "Docker is not running. Install/start Docker, then run ./tut doctor"; exit 1; }
"$REPO/tools/install-tools.sh" "$HERE/tools.env"
# shellcheck source=/dev/null
source "$HERE/tools.env"
export PATH="$REPO/.tools/kind/$KIND:$REPO/.tools/kubectl/$KUBECTL:$REPO/.tools/helm/$HELM:$REPO/.tools/cloud-provider-kind/$CLOUD_PROVIDER_KIND:$PATH"

# 1. An existing cluster: reuse it, add what is missing, or stop.
HAVE="" HAVE_MODE="" HAVE_KEDA="false" ADD="$WANT" CREATE=1
if kind get clusters 2>/dev/null | grep -qx "$KIND_CLUSTER_NAME"; then
  # `|| true`: jsonpath prints no trailing newline, so read returns 1 at EOF (set -e).
  IFS='|' read -r m_profile m_version m_types m_mode m_keda < <(
    kubectl --context "kind-$KIND_CLUSTER_NAME" -n kube-system get configmap tut-env -o \
      jsonpath='{.data.profile}|{.data.kserve_version}|{.data.types}|{.data.mode}|{.data.keda}' 2>/dev/null || true) || true
  # A cluster from the profile this one replaced counts as llmisvc only.
  [[ "${m_profile:-}" == "kind-llmisvc/v1" ]] && { m_profile="$PROFILE"; m_types="llmisvc"; m_mode=""; }
  reason=""
  if [[ "${m_profile:-}" != "$PROFILE" ]]; then
    reason="it was not built by this profile (built as '${m_profile:-unknown}')"
  elif [[ "${m_version:-}" != "$KSERVE_VERSION" ]]; then
    reason="it runs KServe ${m_version:-?}, not $KSERVE_VERSION"
  elif has "$WANT" kserve && has "${m_types:-}" kserve && [[ "${m_mode:-}" != "$MODE" ]]; then
    reason="KServe runs in ${m_mode} mode there, this tutorial needs $MODE (modes cannot be mixed)"
  fi
  if [[ -n "$reason" ]]; then
    if [[ "${TUT_ENV_RECREATE:-0}" != "1" ]]; then
      log "cluster '$KIND_CLUSTER_NAME' exists but $reason."
      log "Delete it ($(dirname "$0")/teardown.sh) or rerun with TUT_ENV_RECREATE=1."
      exit 1
    fi
    "$(dirname "$0")/teardown.sh"
  else
    CREATE=0
    HAVE="$(printf '%s' "${m_types:-}" | norm)" HAVE_MODE="${m_mode:-}" HAVE_KEDA="${m_keda:-false}"
    ADD="$(comm -23 <(tr , '\n' <<<"$WANT" | sort) <(tr , '\n' <<<"$HAVE" | sort) | paste -sd, -)"
    # KEDA is installed together with kserve: asking for it later reinstalls kserve with it.
    [[ "$KEDA" == true && "$HAVE_KEDA" != true ]] && ADD="$(printf '%s,kserve' "$ADD" | norm)"
    kubectl config use-context "kind-$KIND_CLUSTER_NAME" >/dev/null
    if [[ -z "$ADD" ]]; then
      log "cluster '$KIND_CLUSTER_NAME' already provides ${HAVE} (KServe $KSERVE_VERSION) — reusing"
      exit 0
    fi
    log "cluster '$KIND_CLUSTER_NAME' has ${HAVE:-nothing}; adding $ADD"
  fi
fi

# 2. KServe sources pinned to the requested tag (never master).
if [[ ! -d "$KSERVE_SRC/.git" ]]; then
  log "fetching kserve $KSERVE_VERSION"
  mkdir -p "$TUT_CACHE"
  git clone --quiet --depth 1 --branch "$KSERVE_VERSION" https://github.com/kserve/kserve.git "$KSERVE_SRC"
fi
cd "$KSERVE_SRC"

# 3. Cluster (only when there is none) + the requested KServe parts.
if [[ "$CREATE" == 1 ]]; then
  log "creating kind cluster '$KIND_CLUSTER_NAME' with local registry"
  KIND_CLUSTER_NAME="$KIND_CLUSTER_NAME" ./hack/setup/dev/manage.kind-with-registry.sh
fi
args=(--type "$ADD" --kserve-version "$KSERVE_VERSION")
if has "$ADD" kserve; then
  [[ "$MODE" == standard ]] && args+=(--raw) || args+=(--serverless)
  [[ "$KEDA" == true ]] && args+=(--keda)
fi
log "installing KServe $KSERVE_VERSION: ${args[*]}"
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
    ./hack/kserve-install.sh "${args[@]}" && break
  else
    FORCE_UPGRADE=true ./hack/kserve-install.sh "${args[@]}" && break
  fi
  [[ $attempt -eq 3 ]] && { log "KServe install failed after 3 attempts"; exit 1; }
  log "install attempt $attempt failed; waiting for the webhooks, then retrying"
  webhook_ready || log "webhook endpoint still not ready, retrying anyway"
  sleep 10
done

ALL="$(printf '%s,%s' "$HAVE" "$ADD" | norm)"

# Known upstream issue (KServe v0.18.0 - v0.19.0): the well-known scheduler
# config points to ghcr.io/llm-d/llm-d-inference-scheduler:v0.7.1, which is no
# longer publicly pullable (ghcr.io answers 403). llm-d renamed the image to
# llm-d-router-endpoint-picker (first tag v0.9.0; KServe master uses v1.0.0).
# Point the config at the renamed image so LLMInferenceServices can start.
SCHEDULER_IMAGE="${TUT_SCHEDULER_IMAGE:-ghcr.io/llm-d/llm-d-router-endpoint-picker:v0.9.0}"
if has "$ALL" llmisvc && kubectl -n kserve get llminferenceserviceconfig kserve-config-llm-scheduler -o yaml 2>/dev/null \
    | grep -q "llm-d-inference-scheduler:v0.7.1"; then
  log "patching kserve-config-llm-scheduler: llm-d-inference-scheduler:v0.7.1 -> $SCHEDULER_IMAGE"
  kubectl -n kserve get llminferenceserviceconfig kserve-config-llm-scheduler -o json \
    | sed "s#ghcr.io/llm-d/llm-d-inference-scheduler:v0.7.1#${SCHEDULER_IMAGE}#g" \
    | kubectl replace -f -
fi

# 4. Readiness gate: the profile is only "done" when the controllers serve.
has "$ALL" kserve  && kubectl wait --for=condition=Established crd/inferenceservices.serving.kserve.io --timeout=120s
has "$ALL" llmisvc && kubectl wait --for=condition=Established crd/llminferenceservices.serving.kserve.io --timeout=120s
kubectl -n kserve wait --for=condition=Available deployment --all --timeout=600s

# 5. Record what this cluster provides (used by step 1 next time).
kubectl -n kube-system create configmap tut-env \
  --from-literal=profile="$PROFILE" --from-literal=kserve_version="$KSERVE_VERSION" \
  --from-literal=types="$ALL" --from-literal=mode="$(has "$ALL" kserve && echo "${HAVE_MODE:-$MODE}")" \
  --from-literal=keda="$([[ "$KEDA" == true || "$HAVE_KEDA" == true ]] && echo true || echo false)" \
  --dry-run=client -o yaml | kubectl apply -f -
log "ready: $ALL"
