# Environment: `kind-kserve/v1`

A CPU-only Kind cluster with **the KServe parts a tutorial asks for**. One env
for every kind of KServe tutorial: what it installs is chosen per tutorial in
`tutorial.yaml` and passed to KServe's own installer (`hack/kserve-install.sh`,
checked out at the tag in `$KSERVE_VERSION`). Tutorials call it from their first
step, so you normally do not run it yourself. It replaces `kind-llmisvc/v1`.

## Options (`env_options` in tutorial.yaml)

```yaml
env: kind-kserve/v1
env_options: {types: [kserve], mode: standard}    # predictive AI: InferenceService
env_options: {types: [llmisvc]}                    # LLMInferenceService
```

| Option | Values | Default | Installer flag |
|---|---|---|---|
| `types` | `kserve`, `localmodel`, `llmisvc` (any combination) | `[kserve]` | `--type` |
| `mode` | `standard` (RawDeployment), `serverless` (Knative + Istio) | `standard` | `--raw` / `--serverless` (type `kserve` only) |
| `keda` | `true`, `false` | `false` | `--keda` (standard mode only) |

`./tut lint` (T008) rejects anything else. The generated setup step shows the
settings, e.g. `TUT_ENV_TYPES=kserve TUT_ENV_MODE=standard … setup.sh`.

## One cluster for a whole learning path

The cluster remembers what it has (ConfigMap `kube-system/tut-env`: profile,
KServe version, types, mode, keda). The next tutorial:

| The cluster has | The tutorial needs | setup.sh |
|---|---|---|
| everything it needs | — | reuses it (seconds) |
| `kserve` | `llmisvc` too | adds only `llmisvc` (no new cluster) |
| `kserve` in `standard` mode | `kserve` in `serverless` mode | stops: modes cannot be mixed (`TUT_ENV_RECREATE=1` recreates) |
| another KServe version, or not built by this env | — | stops; never changes a cluster it did not build |

A cluster built by `kind-llmisvc/v1` counts as one with `llmisvc`.

## What it can install

| Component | With |
|-----------|------|
| Kind cluster + local registry (`localhost:5001`), cert-manager | always |
| KServe InferenceService controller + ClusterServingRuntimes | `kserve` (`standard`: RawDeployment; `serverless`: + Knative, Istio) |
| KEDA | `keda: true` |
| LocalModel controller | `localmodel` |
| Gateway API + Inference Extension, Envoy Gateway + AI Gateway, LWS operator, LLMInferenceService controller + well-known configs | `llmisvc` |
| cloud-provider-kind (`LoadBalancer` IPs inside Kind) | always |

## Requirements

**You install:** Docker (running), git and curl. Roughly 4 CPUs and 16 GiB of
memory available to Docker. `./tut doctor` checks all of this.

**Installed for you:** the CLI tools listed in `tools.env` (kind, kubectl,
helm, cloud-provider-kind) at pinned versions, into `<repo>/.tools/<tool>/<version>/`.
Nothing is installed system-wide and no shell configuration changes; the
tutorial's setup step puts those directories on `PATH` for that shell only.

<!-- tut:include tools.env -->

```text
# CLI tools this environment needs, installed by setup.sh into
# <repo>/.tools/<tool>/<version>/ (never system-wide) and put on PATH only by
# the tutorial's setup step. kind and helm follow KServe's kserve-deps.env (v0.18.0).
KIND=v0.30.0                  # default node image: kindest/node:v1.34.0
KUBECTL=v1.34.13              # matches Kubernetes 1.34
HELM=v3.16.3
CLOUD_PROVIDER_KIND=v0.12.0   # LoadBalancer addresses for kind, like a cloud
```

<!-- /tut -->

## Run it by hand

```bash skip
export KSERVE_VERSION=<a version listed by the tutorial>
TUT_ENV_TYPES=kserve "$(git rev-parse --show-toplevel)/envs/kind-kserve/v1/setup.sh"
```

The script is idempotent: see "One cluster for a whole learning path" above. If a
cluster built by something else exists, the script stops instead of changing it. Either give the tutorials their own
cluster name (`make config CLUSTER=tut`, stored in `.tut.env`) or set
`TUT_ENV_RECREATE=1` to replace it.

## Remove it

```bash skip
"$(git rev-parse --show-toplevel)/envs/kind-kserve/v1/teardown.sh"
```

## Known issues and workarounds

| Issue | Affects | Workaround in `setup.sh` |
|---|---|---|
| `ghcr.io/llm-d/llm-d-inference-scheduler:v0.7.1` is no longer publicly pullable (403); the scheduler Pod stays in `ImagePullBackOff` | `llmisvc` with KServe v0.18.0 – v0.19.0 default config, on any cluster | the well-known `kserve-config-llm-scheduler` is pointed at the renamed `ghcr.io/llm-d/llm-d-router-endpoint-picker` (override with `TUT_SCHEDULER_IMAGE`). If you use your own cluster, apply the same change. |
| The installer applies LLMInferenceServiceConfigs before the webhook answers | fresh clusters, `llmisvc` | the install is retried with `FORCE_UPGRADE=true` |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Pod `Pending` | Not enough resources on the Kind worker | Give Docker more CPU / memory |
| `ImagePullBackOff` | Registry unreachable | Check proxy / firewall settings |
| Gateway `Programmed=False` | No LoadBalancer IP | Check that `cloud-provider-kind` is running |

## Source

<details>
<summary>setup.sh</summary>

<!-- tut:include setup.sh -->

```bash skip
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
# KServe's installer guesses the platform from the node hostname and only
# treats it as kind when the name contains "kind". With another cluster name
# (KIND_CLUSTER_NAME=tut -> node tut-control-plane) it skips cloud-provider-kind
# and the Gateway never gets an address (CI-010). This env always builds kind.
export PLATFORM=kind

# cloud-provider-kind gives LoadBalancer Services (the Gateway) an address. It
# is one host process for every kind cluster. KServe's installer only starts it
# when none is running and throws its output away; a process that outlived a
# deleted cluster did not serve a new cluster with the same name (CI-012), and
# nothing started it again after a reboot. So this env owns it: the pinned
# binary, a log file, a restart whenever this script creates a cluster, and a
# check that the Gateway really got an address.
CPK_LOG="$TUT_CACHE/cloud-provider-kind.log"
lb_running() { pgrep -f '^([^ ]*/)?cloud-provider-kind( |$)' >/dev/null; }
start_lb() {   # $1 = 1: restart a running one
  if lb_running; then
    [[ "$1" == 1 ]] || return 0
    log "restarting cloud-provider-kind (new cluster)"
    pkill -f '^([^ ]*/)?cloud-provider-kind( |$)' || true
    for _ in $(seq 1 20); do lb_running || break; sleep 0.5; done
  fi
  mkdir -p "$TUT_CACHE"
  log "starting cloud-provider-kind $CLOUD_PROVIDER_KIND (log: $CPK_LOG)"
  nohup cloud-provider-kind >>"$CPK_LOG" 2>&1 </dev/null &
  for _ in $(seq 1 20); do lb_running && return 0; sleep 0.5; done
  log "cloud-provider-kind did not start; see $CPK_LOG"
  return 1
}
lb_ready() {   # $1 = types on the cluster; only llmisvc installs a Gateway
  has "$1" llmisvc || return 0
  kubectl -n kserve wait --for=condition=Programmed gateway --all --timeout=180s && return 0
  log "the Gateway got no address: cloud-provider-kind does not serve this cluster"
  log "last lines of $CPK_LOG:"
  tail -n 20 "$CPK_LOG" 2>/dev/null | sed 's/^/  /' || true
  return 1
}

# 1. An existing cluster: reuse it, add what is missing, or stop.
HAVE="" HAVE_MODE="" HAVE_KEDA="false" ADD="$WANT" CREATE=1
if kind get clusters 2>/dev/null | grep -x "$KIND_CLUSTER_NAME" >/dev/null; then
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
    start_lb 0
    if [[ -z "$ADD" ]]; then
      lb_ready "$HAVE" || exit 1
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
  start_lb 1
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
    | grep "llm-d-inference-scheduler:v0.7.1" >/dev/null; then   # not -q: SIGPIPE under pipefail (CI-007)
  log "patching kserve-config-llm-scheduler: llm-d-inference-scheduler:v0.7.1 -> $SCHEDULER_IMAGE"
  kubectl -n kserve get llminferenceserviceconfig kserve-config-llm-scheduler -o json \
    | sed "s#ghcr.io/llm-d/llm-d-inference-scheduler:v0.7.1#${SCHEDULER_IMAGE}#g" \
    | kubectl replace -f -
fi

# 4. Readiness gate: the profile is only "done" when the controllers serve.
has "$ALL" kserve  && kubectl wait --for=condition=Established crd/inferenceservices.serving.kserve.io --timeout=120s
has "$ALL" llmisvc && kubectl wait --for=condition=Established crd/llminferenceservices.serving.kserve.io --timeout=120s
kubectl -n kserve wait --for=condition=Available deployment --all --timeout=600s
lb_ready "$ALL" || exit 1

# 5. Record what this cluster provides (used by step 1 next time).
kubectl -n kube-system create configmap tut-env \
  --from-literal=profile="$PROFILE" --from-literal=kserve_version="$KSERVE_VERSION" \
  --from-literal=types="$ALL" --from-literal=mode="$(has "$ALL" kserve && echo "${HAVE_MODE:-$MODE}")" \
  --from-literal=keda="$([[ "$KEDA" == true || "$HAVE_KEDA" == true ]] && echo true || echo false)" \
  --dry-run=client -o yaml | kubectl apply -f -
log "ready: $ALL"
```

<!-- /tut -->

</details>

> Once **frozen** (`frozen: true` in profile.yaml), this profile must not change: that would silently change every tutorial that
> uses it, so changes go into `envs/kind-kserve/v2` and tutorials move one at a time.
