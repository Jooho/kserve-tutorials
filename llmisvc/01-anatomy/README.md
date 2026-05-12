# 01. One Apply, Ten Resources — Resource Anatomy

A single `kubectl apply` of an LLMInferenceService causes the controller to automatically create 10+ Kubernetes resources internally.
This demo observes that process firsthand.

## Key Question

> "What happens inside the cluster when you apply a single LLMInferenceService YAML?"

## Prerequisites

- [00-setup](../00-setup/) completed (KServe LLMIsvc installed + namespace created)

## Step 1: Pre-deploy State Snapshot

Record the current state first. It should be empty.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT/llmisvc/01-anatomy"
NS=kserve-demo

echo "=== Before Apply ==="
kubectl get pods,svc,deploy,inferencepool,httproute -n $NS 2>/dev/null
```

## Step 2: Deploy LLMIsvc

Apply a single YAML. The well-known config is automatically injected without a separate LLMIsvcConfig.

```bash
kubectl apply -f llmisvc-cpu.yaml -n $NS
```

<details>
<summary>llmisvc-cpu.yaml</summary>

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
</details>

Key points of this YAML:

| Field | Value | Description |
|-------|-------|-------------|
| `model.uri` | `hf://facebook/opt-125m` | Auto-downloaded from HuggingFace |
| `router.route: {}` | Required | HTTPRoute is not created without this |
| `securityContext.runAsUser` | `1000` | Must be specified since the vLLM CPU image is built as root |
| `baseRefs` | None | Well-known config auto-injected (see below) |

### Well-known LLMIsvcConfig Auto-injection

**Well-known LLMIsvcConfigs** are automatically installed in the cluster during KServe installation:

| Config | Role |
|--------|------|
| `kserve-config-llm-template` | vLLM container template (command, probes, security) |
| `kserve-config-llm-scheduler` | EPP scheduler + tokenizer sidecar |

When an LLMIsvc is created, the controller **automatically merges** these well-known configs.
So even without specifying `baseRefs`, `command`, probes, EPP scheduler, etc. are automatically configured.
Just override `image`, `env`, `resources` inline and the well-known config provides the rest.

## Observe Resource Creation

Right after apply, observe resources being created one by one.

```bash
# Watch resource creation in real-time (in another terminal)
watch -n 1 "kubectl get pods,svc,deploy,lws,inferencepool,httproute -n $NS 2>/dev/null"
```

## Resource Map

```text
kubectl apply -f llmisvc-cpu.yaml
        │
        ▼
┌─ KServe LLMIsvc Controller ──────────────────────────────────┐
│                                                               │
│  1. TLS Certificates                                          │
│     └── Secret (self-signed certs)                            │
│                                                               │
│  2. Workload (Model Serving)                                  │
│     ├── Deployment (vLLM Pod management, single-node)         │
│     │   └ Uses LeaderWorkerSet for multi-node                 │
│     ├── Service (*-workload-svc, port 8000)                   │
│     └── ServiceAccount                                        │
│                                                               │
│  3. Scheduler (Request Routing)                               │
│     ├── Deployment (EPP Scheduler + tokenizer sidecar)        │
│     ├── Service (*-epp-service, gRPC 9002 etc.)               │
│     ├── Role + RoleBinding (RBAC)                             │
│     └── ServiceAccount                                        │
│                                                               │
│  4. Traffic Wiring                                            │
│     ├── InferencePool (scheduler ↔ workload connection)       │
│     └── HTTPRoute (Gateway → InferencePool routing)           │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Per-resource Role Verification

### 1. LeaderWorkerSet — Workload Management

```bash
kubectl get lws -n $NS -o wide
kubectl describe lws -n $NS
```

LWS manages the lifecycle of vLLM Pods. It is used to configure Leader-Worker relationships in multi-node deployments (P/D disaggregation, DP+EP, etc.).
For single-node deployments (only `replicas` set, no `parallelism`), a regular Deployment is used and LWS is not created.

### 2. EPP Scheduler — The Brain of Request Distribution

```bash
kubectl get deploy -n $NS -l app.kubernetes.io/component=llminferenceservice-router-scheduler
kubectl logs -n $NS -l app.kubernetes.io/component=llminferenceservice-router-scheduler --tail=20
```

EPP (Endpoint Picker Plugin) decides which vLLM Pod to route each incoming request to.
Decision criteria: queue depth, KV cache utilization, etc.

#### Scheduler Pod Internal Structure (3 Containers)

```bash
kubectl get pod -n $NS -l app.kubernetes.io/component=llminferenceservice-router-scheduler \
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
│  ┌─────────────┐            ┌────────────┐  │
│  │  scheduler  │            │ tokenizer  │  │
│  │  (main)     │   (idle)   │ (sidecar)  │  │
│  │             │            │            │  │
│  │  gRPC:9002  │            │ HTTP:8082  │  │
│  │  health:9003│            │ (health)   │  │
│  │  metrics:   │            │            │  │
│  │   9090      │            │ Idle in    │  │
│  │             │            │ default    │  │
│  │  Scoring,   │            │ config     │  │
│  │  Pod select │            │            │  │
│  └─────────────┘            └────────────┘  │
└─────────────────────────────────────────────┘
         ▲
         │ gRPC (ExtProc)
    Envoy Gateway
```

| Container | Image | Role |
|-----------|-------|------|
| `storage-initializer` (init) | `kserve/storage-initializer` | Downloads only tokenizer files from HF (filtered by `STORAGE_ALLOW_PATTERNS`) |
| `main` (scheduler) | `llm-d/llm-d-inference-scheduler` | EPP scheduler. Communicates with Envoy via ExtProc gRPC. Selects optimal Pod after scoring |
| `tokenizer` (sidecar) | `llm-d/llm-d-uds-tokenizer` | **Idle** in default config. Used for precise prefix cache matching via UDS when switching to `precise-prefix-cache-scorer` |

#### Scheduling Plugin Configuration (Injected by well-known config)

```bash
kubectl describe pod -n $NS -l app.kubernetes.io/component=llminferenceservice-router-scheduler | grep -A 15 "config-text"
```

Default configuration:

- `queue-scorer` (weight: 2) — Prefers Pods with fewer queued requests
- `prefix-cache-scorer` (weight: 3) — Prefers Pods with higher prefix cache hit rate based on vLLM metrics
- `max-score-picker` — Selects the Pod with the highest combined score

#### Tokenizer Sidecar Is Not Used in Default Config

The well-known config (`kserve-config-llm-scheduler`) always injects the tokenizer, but the default `prefix-cache-scorer` only references vLLM metrics and **does not use the tokenizer**.
The tokenizer is only utilized when switching to `precise-prefix-cache-scorer`.

<details>
<summary>precise-prefix-cache-scorer — Advanced mode where tokenizer is utilized</summary>

When switching to `precise-prefix-cache-scorer`, the tokenizer becomes active:

1. Tokenizer tokenizes the prompt → computes block hashes
2. vLLM publishes cache events via ZMQ
3. Scheduler matches block hashes with cache events for precise Pod selection

| | `prefix-cache-scorer` (default) | `precise-prefix-cache-scorer` |
|---|---|---|
| Data source | vLLM metrics (`prefix_cache_hit_rate`) | vLLM's real-time ZMQ event stream |
| Method | References hit rate reported by vLLM | Scheduler directly tokenizes → block hash → exact match with vLLM cache |
| Tokenizer | **Not used** (injected but idle) | **Used** (communicates via UDS) |
| Additional vLLM config | None | `--enable-kvcache`, `--block-size`, ZMQ publish required |

The tokenizer and scheduler communicate within the same Pod via **Unix Domain Socket** (UDS, `/tmp/tokenizer/tokenizer-uds.socket`).
UDS is used instead of TCP to minimize latency by bypassing the kernel network stack.

```bash
# Check UDS socket file
kubectl exec -n $NS $(kubectl get pod -n $NS -l app.kubernetes.io/component=llminferenceservice-router-scheduler -o jsonpath='{.items[0].metadata.name}') \
  -c main -- ls -la /tmp/tokenizer/
```

Configuration example: [precise-prefix-kv-cache-routing](https://github.com/kserve/kserve/tree/master/docs/samples/llmisvc/precise-prefix-kv-cache-routing)
</details>

### 3. InferencePool — The Link Between Scheduler and Workload

```bash
kubectl get inferencepool -n $NS -o yaml
```

InferencePool is a CRD from Gateway API Inference Extension. It is an abstraction layer that enables the scheduler to discover and route to workload Pods.

### 4. HTTPRoute — Wiring Incoming Traffic from Gateway

```bash
kubectl get httproute -n $NS -o yaml
```

HTTPRoute defines rules that forward requests received by the Gateway to the InferencePool (→ scheduler).

### 5. Service Structure — Internal Network Wiring

```bash
kubectl get svc -n $NS
```

| Service | Purpose | Ports |
|---------|---------|-------|
| `*-workload-svc` | Exposes vLLM Pod | 8000 (HTTPS) |
| `*-epp-service` | Exposes EPP Scheduler | 9002 (gRPC), 9003 (health), 9090 (metrics), 5557 (zmq) |

> The metrics port (9090) is HTTP but requires Bearer token authentication (`metrics-endpoint-auth: true`).
> Access it using the token from the `metrics-reader` SA created in 00-setup.

## Verify Created Resources

Check the overall state after all resources are created.

```bash
echo "=== After Apply ==="
echo "--- Pods ---"
kubectl get pods -n $NS -o wide
echo "--- Services ---"
kubectl get svc -n $NS
echo "--- LeaderWorkerSet ---"
kubectl get lws -n $NS
echo "--- InferencePool ---"
kubectl get inferencepool -n $NS
echo "--- HTTPRoute ---"
kubectl get httproute -n $NS
echo "--- Secrets ---"
kubectl get secret -n $NS | grep -v default
echo "--- ConfigMaps ---"
kubectl get cm -n $NS | grep -v kube
```

Expected results (0 before apply → after apply):

```text
Pods:          2 (vLLM x1 + Scheduler x1)
Services:      2 (workload-svc + epp-service)
Deployments:   2 (workload + scheduler)
InferencePool: 1
HTTPRoute:     1
Secrets:       1 (TLS certs)
```

## Request Test

Once all resources are created and LLMIsvc shows `Ready=True`, send a test request.

```bash
kubectl get llmisvc -n $NS
# Check that READY is True

# Kind: Access via NodePort
NODE_IP=$(docker inspect kind-worker --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
NODE_PORT=$(kubectl get svc -n envoy-gateway-system -l gateway.envoyproxy.io/owning-gateway-name -o jsonpath='{.items[0].spec.ports[0].nodePort}')
GATEWAY_URL="http://${NODE_IP}:${NODE_PORT}/kserve-demo/demo-model"

curl -s "${GATEWAY_URL}/v1/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "facebook/opt-125m",
    "prompt": "Kubernetes is",
    "max_tokens": 20
  }' | python3 -m json.tool
```

## Cleanup

> To proceed to the next demo (02-request-flow), leave everything as is without cleanup.

```bash
# Run only when cleanup is needed
kubectl delete llmisvc demo-model -n $NS
```

Deleting the LLMIsvc automatically removes all controller-created resources (Deployment, Service, InferencePool, HTTPRoute, etc.) via OwnerReference cascade.

## What We Learned

- A single LLMIsvc YAML automatically creates 10+ resources
- **Well-known LLMIsvcConfig** is auto-injected, so it works without a separate config
- Scheduler Pod consists of 3 containers: init (tokenizer download) + scheduler + tokenizer (idle in default config)
- Core structure: **Deployment (workload)** ↔ **InferencePool** ↔ **Scheduler** ↔ **HTTPRoute** ↔ **Gateway**
- OwnerReference cascade deletion on cleanup

## Next Step

Now that we understand the resource structure, proceed to [02-request-flow](../02-request-flow/) to trace how actual requests flow through this structure.
