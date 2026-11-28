# One Apply, Ten Resources — LLMInferenceService Anatomy

<!-- tut:header -->

<!-- Generated from tutorial.yaml by `./tut sync` — do not edit by hand. -->
> **Status:** 🚧 draft · **Tested with KServe:** v0.20.0 · **Environment:** [`kind-kserve/v1`](../../envs/kind-kserve/v1/) · **GPU:** not required
>
> 🌐 [한국어](README.ko.md)
>
> **Older KServe versions:** v0.18.0: [v0.18](revisions/v0.18/README.md)

<!-- /tut -->

A single `kubectl apply` of an LLMInferenceService makes the controller create 10+
Kubernetes resources. This tutorial watches that happen and explains what each
resource is for.

> **Key question:** what happens inside the cluster when you apply one
> LLMInferenceService YAML?

What you will learn:

- What one LLMInferenceService turns into: a vLLM workload, an EPP scheduler,
  an InferencePool, an HTTPRoute and the Services between them.
- Where the settings you did not write come from: the well-known
  LLMInferenceServiceConfigs that are merged into your object.
- How the pieces connect: Gateway, HTTPRoute, InferencePool, scheduler and
  vLLM Pods.
- What runs inside the scheduler Pod, and which of its parts the default
  configuration uses.
- Why deleting the LLMInferenceService is enough to clean up (owner
  references).

## Step 0: Environment

This prepares a Kind cluster with KServe LLMInferenceService (see the environment
link above) and creates the namespace used below. It is safe to run again.

<!-- tut:setup -->

```bash run
# Generated from tutorial.yaml by `./tut sync` — do not edit by hand.
export KSERVE_VERSION="${KSERVE_VERSION:-v0.20.0}"
export NS="${NS:-llmisvc-anatomy}"
export REPO_ROOT="$(git rev-parse --show-toplevel)"
source "$REPO_ROOT/tools/local-config.sh"   # your settings in .tut.env, if any
export TUT_LIB="$REPO_ROOT/lib"
# pinned CLI tools of the environment, for this shell only
export PATH="$REPO_ROOT/.tools/kind/v0.30.0:$REPO_ROOT/.tools/kubectl/v1.34.13:$REPO_ROOT/.tools/helm/v3.16.3:$REPO_ROOT/.tools/cloud-provider-kind/v0.12.0:$PATH"
# what this tutorial needs from the environment (env_options in tutorial.yaml)
TUT_ENV_TYPES=llmisvc TUT_ENV_MODE=standard TUT_ENV_KEDA=false "$REPO_ROOT/envs/kind-kserve/v1/setup.sh"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
cd "$REPO_ROOT/tutorials/llmisvc-anatomy"
```

<!-- /tut -->

## Step 1: Snapshot before applying

Record the current state first. The namespace should be empty.

```bash run
echo "=== Before Apply ==="
kubectl get pods,svc,deploy,inferencepool,httproute -n "$NS" 2>/dev/null || true
```

## Step 2: Deploy the LLMInferenceService

Apply a single YAML. The well-known config is injected automatically, so no
separate `LLMInferenceServiceConfig` is needed.

<!-- tut:define llmisvc-demo-model -->

```bash run
kubectl apply -f manifests/llmisvc-cpu.yaml -n "$NS"
```

<!-- /tut -->

<details>
<summary>manifests/llmisvc-cpu.yaml</summary>

<!-- tut:include manifests/llmisvc-cpu.yaml -->

```yaml
apiVersion: serving.kserve.io/v1alpha2
kind: LLMInferenceService
metadata:
  name: demo-model
spec:
  model:
    uri: "hf://facebook/opt-125m"
    name: facebook/opt-125m
  replicas: 1
  router:
    scheduler: {}
    route: {}
    gateway: {}
  template:
    containers:
      - name: main
        image: public.ecr.aws/q9t5s3a7/vllm-cpu-release-repo:v0.19.0
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
        env:
          - name: USER
            value: nonroot
          - name: VLLM_LOGGING_LEVEL
            value: DEBUG
          - name: VLLM_CPU_KVCACHE_SPACE
            value: "1"
          - name: VLLM_ADDITIONAL_ARGS
            value: "--block-size 16"
        resources:
          limits:
            cpu: "2"
            memory: 7Gi
          requests:
            cpu: 200m
            memory: 2Gi
        livenessProbe:
          initialDelaySeconds: 180
          periodSeconds: 30
          timeoutSeconds: 30
          failureThreshold: 8
        readinessProbe:
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
```

<!-- /tut -->

</details>

Key points of this YAML:

| Field | Value | Description |
|-------|-------|-------------|
| `model.uri` | `hf://facebook/opt-125m` | Downloaded from Hugging Face automatically |
| `router.route: {}` | Required | No HTTPRoute is created without it |
| `securityContext.runAsUser` | `1000` | Needed because the vLLM CPU image is built as root |
| `baseRefs` | None | The well-known config is injected (see below) |

### Well-known LLMInferenceServiceConfig injection

KServe installs **well-known LLMInferenceServiceConfigs** into the cluster:

| Config | Role |
|--------|------|
| `kserve-config-llm-template` | vLLM container template (command, probes, security) |
| `kserve-config-llm-scheduler` | EPP scheduler |
| `kserve-config-llm-router-route` | The HTTPRoute rules (which paths go to the InferencePool) |

When an LLMInferenceService is created, the controller **merges** these configs
automatically. Even without `baseRefs`, the command, probes and EPP scheduler are
configured; you only override `image`, `env` and `resources` inline.

## Step 3: Watch the resources appear

Right after applying, watch the resources being created one by one (in a second
terminal; press `Ctrl+C` to stop):

```bash skip
watch -n 1 "kubectl get pods,svc,deploy,lws,inferencepool,httproute -n $NS 2>/dev/null"
```

Then wait until the service reports `Ready`. Downloading the model and starting
vLLM on CPU takes a few minutes.

```bash verify
kubectl wait --for=condition=Ready llminferenceservice/demo-model -n "$NS" --timeout=900s
```

## Resource map

```text
kubectl apply -f llmisvc-cpu.yaml
        │
        ▼
┌─ KServe LLMInferenceService controller ──────────────────────┐
│                                                               │
│  1. TLS certificates                                          │
│     └── Secret (self-signed certs)                            │
│                                                               │
│  2. Workload (model serving)                                  │
│     ├── Deployment (vLLM Pod, single node)                    │
│     │   └ LeaderWorkerSet is used for multi-node              │
│     ├── Service (*-workload-svc, port 8000)                   │
│     └── ServiceAccount                                        │
│                                                               │
│  3. Scheduler (request routing)                               │
│     ├── Deployment (EPP scheduler)                            │
│     ├── Service (*-epp-service, gRPC 9002 etc.)               │
│     ├── Role + RoleBinding (RBAC)                             │
│     └── ServiceAccount                                        │
│                                                               │
│  4. Traffic wiring                                            │
│     ├── InferencePool (scheduler ↔ workload)                  │
│     └── HTTPRoute (Gateway → InferencePool)                   │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Step 4: What each resource does

### 1. LeaderWorkerSet — workload management

```bash run
kubectl get lws -n "$NS" -o wide
```

LWS manages vLLM Pods in multi-node deployments (P/D disaggregation, DP+EP, ...).
A single-node deployment (only `replicas`, no `parallelism`) uses a regular
Deployment, so **no LWS is created here** and the command above prints
`No resources found`.

### 2. EPP scheduler — where each request goes

```bash run
kubectl get deploy -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler
kubectl logs -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler --tail=20
```

The EPP (Endpoint Picker Plugin) decides which vLLM Pod receives each request,
based on queue depth, KV-cache utilization and similar signals.

#### Inside the scheduler Pod

```bash run
kubectl get pod -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler \
  -o custom-columns='INIT:.spec.initContainers[*].image,CONTAINERS:.spec.containers[*].image'
```

```text
┌─────────────────────────────────────────────┐
│  Scheduler Pod                              │
│                                             │
│  Init: storage-initializer                  │
│    └ Downloads only tokenizer files from HF │
│      (tokenizer.json, vocab.json, etc.)     │
│      Does NOT download model weights        │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  scheduler (main)                   │    │
│  │  gRPC: 9002   health: 9003          │    │
│  │  metrics: 9090                      │    │
│  │  Scoring, Pod selection             │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
         ▲
         │ gRPC (ExtProc)
    Envoy Gateway
```

| Container | Image | Role |
|-----------|-------|------|
| `storage-initializer` (init) | `kserve/storage-initializer` | Downloads only tokenizer files (filtered by `STORAGE_ALLOW_PATTERNS`), no model weights. They are for an optional tokenizer container that the default plugins do not use, so it is not started |
| `main` (scheduler) | `llm-d/llm-d-router-endpoint-picker` | EPP scheduler; talks to Envoy over ExtProc gRPC and picks a Pod after scoring |

The scheduler Pod must have exactly these two containers, one init and one
that keeps running:

```bash verify
POD=$("$TUT_LIB/llmisvc/v1/scheduler-pod.sh" "$NS")
test "$(kubectl get pod -n "$NS" "$POD" -o jsonpath='{.spec.initContainers[*].name}')" = "storage-initializer"
test "$(kubectl get pod -n "$NS" "$POD" -o jsonpath='{.spec.containers[*].name}')" = "main"
```

#### Scheduling plugins (from the well-known config)

```bash run
kubectl describe pod -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler \
  | grep -A 15 "config-text" || true
```

Default configuration: four scorers, each with a weight, and a picker. Every
scorer gives each vLLM Pod a score between 0 and 1; the picker adds them up
with their weights and takes the highest.

- `queue-scorer` (weight 2) — prefers Pods with fewer queued requests
- `kv-cache-utilization-scorer` (weight 2) — prefers Pods whose KV cache is less full
- `prefix-cache-scorer` (weight 3) — prefers the Pod that most likely has this prompt's prefix cached
- `no-hit-lru-scorer` (weight 2) — for a prompt no Pod has cached, prefers the Pod that got such a "cold" prompt least recently, so new prefixes spread over the Pods
- `max-score-picker` — picks the Pod with the highest combined score

With one vLLM Pod, as here, every request goes to that Pod whatever the
scores are. The request-flow tutorial of this series shows the scores.

### 3. InferencePool — linking scheduler and workload

```bash run
kubectl get inferencepool -n "$NS" -o yaml
```

InferencePool is a CRD from the Gateway API Inference Extension. It lets the
scheduler discover the workload Pods and route to them.

### 4. HTTPRoute — traffic from the Gateway

```bash run
kubectl get httproute -n "$NS" -o yaml
```

The HTTPRoute forwards requests received by the Gateway to the InferencePool,
and from there to the scheduler.

### 5. Services — internal wiring

```bash run
kubectl get svc -n "$NS"
```

| Service | Purpose | Ports |
|---------|---------|-------|
| `*-workload-svc` | Names the vLLM Pods (not used by inference requests, see below) | 8000 (`http`; it is `https` only when TLS is enabled for the workload) |
| `*-epp-service` | Exposes the EPP scheduler | 9002 (gRPC), 9003 (health), 9090 (metrics), 5557 (ZMQ) |

> The metrics port (9090) is plain HTTP but requires a bearer token
> (`metrics-endpoint-auth: true`). Reading those metrics is covered in the
> request-flow tutorial of this series.

> **Inference requests do not pass through `*-workload-svc`.** For
> `/v1/completions`, `/v1/chat/completions`, `/v1/responses` and
> `/v1/messages` the HTTPRoute's backend is the InferencePool: the EPP picks
> a Pod and Envoy connects to that Pod's IP directly. The workload Service
> serves the rest: the route's catch-all rules send other paths under
> `/<namespace>/demo-model` to it, monitoring finds the vLLM Pods through it,
> and clients inside the cluster can call vLLM by its name. The request-flow tutorial shows the Pod
> IP in the Envoy log.

## Step 5: Check the result

```bash run
echo "--- Pods ---";          kubectl get pods -n "$NS" -o wide
echo "--- Services ---";      kubectl get svc -n "$NS"
echo "--- InferencePool ---"; kubectl get inferencepool -n "$NS"
echo "--- HTTPRoute ---";     kubectl get httproute -n "$NS"
echo "--- Secrets ---";       kubectl get secret -n "$NS"
```

Expected (nothing before applying → after applying):

```text
Pods:          2 (vLLM x1 + scheduler x1)
Services:      2 (workload-svc + epp-service)
Deployments:   2 (workload + scheduler)
InferencePool: 1
HTTPRoute:     1
Secrets:       1+ (TLS certs)
```

The same expectations, checked automatically:

```bash verify
count() { kubectl get "$1" -n "$NS" --no-headers 2>/dev/null | wc -l; }
test "$(count deploy)" -eq 2
test "$(count svc)" -ge 2
test "$(count inferencepool)" -eq 1
test "$(count httproute)" -eq 1
```

## Step 6: Send a request

Once the LLMInferenceService is `Ready`, send a completion request through the
Gateway. In Kind the Gateway is reached through a NodePort on the worker node;
the shared `llmisvc/v1` module works out the URL.

```bash run
GATEWAY_URL=$("$TUT_LIB/llmisvc/v1/gateway-url.sh" "$NS" demo-model)
echo "$GATEWAY_URL"
```

```bash verify retry=10 delay=15
"$TUT_LIB/llmisvc/v1/completion.sh" "$GATEWAY_URL" facebook/opt-125m "Kubernetes is"
```

> **Do not judge the answer.** `facebook/opt-125m` is a tiny (125M parameters)
> *base* model, chosen so the whole tutorial runs on a CPU in minutes. It does
> not follow instructions; it continues the text, often oddly, and stops after
> 20 tokens (`"finish_reason": "length"`). What this step proves is the path:
> the request went through the Gateway and the scheduler to vLLM, and text came
> back. `temperature` is 0, so the answer is the same on every run.

<details>
<summary>lib/llmisvc/v1/gateway-url.sh</summary>

<!-- tut:include ../../lib/llmisvc/v1/gateway-url.sh -->

```bash skip
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
```

<!-- /tut -->

</details>

<details>
<summary>lib/llmisvc/v1/completion.sh</summary>

<!-- tut:include ../../lib/llmisvc/v1/completion.sh -->

```bash skip
#!/usr/bin/env bash
# Usage: completion.sh <url> <model> [prompt] [max_tokens] [temperature]
# Sends POST <url>/v1/completions, prints the JSON answer and fails unless
# the first choice contains text. temperature defaults to 0 (greedy): the same
# prompt gives the same answer every run, as in the tutorial text.
set -euo pipefail
url="${1:?url}"; model="${2:?model}"; prompt="${3:-Kubernetes is}"; max="${4:-20}"; temp="${5:-0}"
body=$(python3 -c 'import json,sys; print(json.dumps({"model":sys.argv[1],"prompt":sys.argv[2],"max_tokens":int(sys.argv[3]),"temperature":float(sys.argv[4])}))' \
  "$model" "$prompt" "$max" "$temp")
curl -sf "${url}/v1/completions" -H "Content-Type: application/json" -d "$body" \
  | python3 -c 'import json, sys; r = json.load(sys.stdin); print(json.dumps(r, indent=2)); assert r["choices"][0]["text"], "empty completion"'
```

<!-- /tut -->

</details>

## Cleanup

Deleting the LLMInferenceService removes every resource the controller created
(Deployments, Services, InferencePool, HTTPRoute, ...) through OwnerReference
cascading deletion.

```bash cleanup
kubectl delete llminferenceservice demo-model -n "$NS" --ignore-not-found --wait=true
kubectl delete namespace "$NS" --ignore-not-found
```

The Kind cluster itself is shared by the tutorials in this environment; remove it
with the environment's `teardown.sh` when you are done.

## What we learned

- One LLMInferenceService YAML creates 10+ resources
- The **well-known LLMInferenceServiceConfig** is injected, so no separate config is needed
- The scheduler Pod has two containers: an init container (tokenizer files) and the scheduler, which scores the Pods with four plugins
- Core structure: **Deployment (workload)** ↔ **InferencePool** ↔ **scheduler** ↔ **HTTPRoute** ↔ **Gateway**
- Cleanup cascades through OwnerReferences
