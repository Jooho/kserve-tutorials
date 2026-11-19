<!-- tut-translation source=README.md sha=5abd5fc4d05a -->
# 한 번의 Apply, 열 개의 리소스 — LLMInferenceService 해부

<!-- tut:header -->

<!-- tutorial.yaml에서 `./tut sync`로 생성됨 — 직접 수정하지 마세요. -->
> **상태:** 🚧 작성 중 · **검증된 KServe:** v0.18.0 · **환경:** [`kind-kserve/v1`](../../envs/kind-kserve/v1/) · **GPU:** 불필요
>
> 🌐 [English](README.md)

<!-- /tut -->

LLMInferenceService 하나를 `kubectl apply` 하면 컨트롤러가 10개 이상의
Kubernetes 리소스를 만듭니다. 이 튜토리얼에서는 그 과정을 직접 지켜보고
각 리소스가 어떤 역할을 하는지 설명합니다.

> **핵심 질문:** LLMInferenceService YAML 하나를 apply 하면
> 클러스터 안에서는 어떤 일이 일어날까요?

## Step 0: 환경 준비

KServe LLMInferenceService가 설치된 Kind 클러스터를 준비하고(위의 환경 링크 참고)
아래에서 사용할 네임스페이스를 만듭니다. 여러 번 실행해도 안전합니다.

<!-- tut:setup -->

```bash run
# Generated from tutorial.yaml by `./tut sync` — do not edit by hand.
export KSERVE_VERSION="${KSERVE_VERSION:-v0.18.0}"
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

## Step 1: Apply 전 스냅샷

먼저 현재 상태를 기록해 둡니다. 네임스페이스는 비어 있어야 합니다.

```bash run
echo "=== Before Apply ==="
kubectl get pods,svc,deploy,inferencepool,httproute -n "$NS" 2>/dev/null || true
```

## Step 2: LLMInferenceService 배포

YAML 하나만 apply 합니다. well-known config가 자동으로 주입되므로
별도의 `LLMInferenceServiceConfig`는 필요 없습니다.

```bash run
kubectl apply -f manifests/llmisvc-cpu.yaml -n "$NS"
```

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

이 YAML의 핵심 포인트:

| 필드 | 값 | 설명 |
|-------|-------|-------------|
| `model.uri` | `hf://facebook/opt-125m` | Hugging Face에서 자동으로 다운로드 |
| `router.route: {}` | 필수 | 없으면 HTTPRoute가 생성되지 않음 |
| `securityContext.runAsUser` | `1000` | vLLM CPU 이미지가 root 기준으로 빌드되어 있어 필요 |
| `baseRefs` | 없음 | well-known config가 주입됨 (아래 참고) |

### Well-known LLMInferenceServiceConfig 주입

KServe는 클러스터에 **well-known LLMInferenceServiceConfig**들을 설치합니다:

| Config | 역할 |
|--------|------|
| `kserve-config-llm-template` | vLLM 컨테이너 템플릿 (command, probe, 보안 설정) |
| `kserve-config-llm-scheduler` | EPP 스케줄러 + tokenizer 사이드카 |

LLMInferenceService가 생성되면 컨트롤러가 이 config들을 자동으로 **병합**합니다.
`baseRefs`가 없어도 command, probe, EPP 스케줄러가 구성되며,
사용자는 `image`, `env`, `resources`만 인라인으로 덮어쓰면 됩니다.

## Step 3: 리소스가 생성되는 과정 지켜보기

apply 직후, 리소스가 하나씩 생성되는 모습을 지켜봅니다(두 번째 터미널에서 실행,
`Ctrl+C`로 중지):

```bash skip
watch -n 1 "kubectl get pods,svc,deploy,lws,inferencepool,httproute -n $NS 2>/dev/null"
```

그다음 서비스가 `Ready` 상태가 될 때까지 기다립니다. 모델 다운로드와
CPU에서 vLLM을 기동하는 데 몇 분 정도 걸립니다.

```bash verify
kubectl wait --for=condition=Ready llminferenceservice/demo-model -n "$NS" --timeout=900s
```

## 리소스 맵

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
│     ├── Deployment (EPP scheduler + tokenizer sidecar)        │
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

## Step 4: 각 리소스의 역할

### 1. LeaderWorkerSet — 워크로드 관리

```bash run
kubectl get lws -n "$NS" -o wide
```

LWS는 멀티 노드 배포(P/D disaggregation, DP+EP 등)에서 vLLM Pod를 관리합니다.
단일 노드 배포(`parallelism` 없이 `replicas`만 지정)는 일반 Deployment를
사용하므로 **여기서는 LWS가 생성되지 않으며**, 위 명령은
`No resources found`를 출력합니다.

### 2. EPP 스케줄러 — 각 요청을 어디로 보낼지 결정

```bash run
kubectl get deploy -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler
kubectl logs -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler --tail=20
```

EPP(Endpoint Picker Plugin)는 큐 깊이, KV-cache 사용률 같은 신호를 바탕으로
각 요청을 어떤 vLLM Pod가 받을지 결정합니다.

#### 스케줄러 Pod 내부

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
│  ┌─────────────┐            ┌────────────┐  │
│  │  scheduler  │            │ tokenizer  │  │
│  │  (main)     │   (idle)   │ (sidecar)  │  │
│  │  gRPC:9002  │            │ HTTP:8082  │  │
│  │  health:9003│            │ (health)   │  │
│  │  metrics:   │            │ Idle in    │  │
│  │   9090      │            │ default    │  │
│  │  Scoring,   │            │ config     │  │
│  │  Pod select │            │            │  │
│  └─────────────┘            └────────────┘  │
└─────────────────────────────────────────────┘
         ▲
         │ gRPC (ExtProc)
    Envoy Gateway
```

| 컨테이너 | 이미지 | 역할 |
|-----------|-------|------|
| `storage-initializer` (init) | `kserve/storage-initializer` | tokenizer 파일만 다운로드 (`STORAGE_ALLOW_PATTERNS`로 필터링) |
| `main` (scheduler) | `llm-d/llm-d-inference-scheduler` | EPP 스케줄러. ExtProc gRPC로 Envoy와 통신하고 스코어링 후 Pod를 선택 |
| `tokenizer` (sidecar) | `llm-d/llm-d-uds-tokenizer` | 기본 설정에서는 **유휴 상태**. `precise-prefix-cache-scorer`가 Unix 소켓을 통해 사용 |

스케줄러 Pod에는 위의 세 컨테이너가 정확히 있어야 합니다:

```bash verify
POD=$("$TUT_LIB/llmisvc/v1/scheduler-pod.sh" "$NS")
test "$(kubectl get pod -n "$NS" "$POD" -o jsonpath='{.spec.initContainers[*].name}')" = "storage-initializer"
test "$(kubectl get pod -n "$NS" "$POD" -o jsonpath='{.spec.containers[*].name}' | wc -w)" -eq 2
```

#### 스케줄링 플러그인 (well-known config에서 제공)

```bash run
kubectl describe pod -n "$NS" -l app.kubernetes.io/component=llminferenceservice-router-scheduler \
  | grep -A 15 "config-text" || true
```

기본 구성:

- `queue-scorer` (가중치 2) — 대기 중인 요청이 적은 Pod를 우선
- `prefix-cache-scorer` (가중치 3) — prefix-cache 적중률이 높은 Pod를 우선 (vLLM 메트릭 기반)
- `max-score-picker` — 합산 점수가 가장 높은 Pod를 선택

#### tokenizer 사이드카가 유휴 상태인 이유

well-known config(`kserve-config-llm-scheduler`)는 항상 tokenizer를 주입하지만,
기본 `prefix-cache-scorer`는 vLLM 메트릭만 읽습니다. tokenizer는
`precise-prefix-cache-scorer`로 전환한 뒤에야 사용됩니다.

<details>
<summary>precise-prefix-cache-scorer — tokenizer가 사용되는 경우</summary>

`precise-prefix-cache-scorer`를 사용하면 tokenizer가 활성화됩니다:

1. tokenizer가 프롬프트를 토큰화하고 블록 해시를 계산
2. vLLM이 ZMQ로 캐시 이벤트를 발행
3. 스케줄러가 블록 해시와 캐시 이벤트를 매칭해 정확한 Pod를 선택

| | `prefix-cache-scorer` (기본값) | `precise-prefix-cache-scorer` |
|---|---|---|
| 데이터 소스 | vLLM 메트릭 (`prefix_cache_hit_rate`) | vLLM의 실시간 ZMQ 이벤트 스트림 |
| 방식 | vLLM이 보고한 적중률 사용 | 스케줄러가 토큰화 → 블록 해시 → 정확한 매칭 |
| Tokenizer | **사용 안 함** (주입되지만 유휴 상태) | **사용** (Unix 도메인 소켓 경유) |
| 추가 vLLM 설정 | 없음 | `--enable-kvcache`, `--block-size`, ZMQ 발행 |

tokenizer와 스케줄러는 같은 Pod 안에서 **Unix 도메인 소켓**
(`/tmp/tokenizer/tokenizer-uds.socket`)으로 통신하므로 커널 네트워크 스택을
거치지 않습니다:

```bash skip
kubectl exec -n "$NS" "$("$TUT_LIB/llmisvc/v1/scheduler-pod.sh" "$NS")" -c main -- ls -la /tmp/tokenizer/
```

설정 예시: [precise-prefix-kv-cache-routing](https://github.com/kserve/kserve/tree/master/docs/samples/llmisvc/precise-prefix-kv-cache-routing)
</details>

### 3. InferencePool — 스케줄러와 워크로드 연결

```bash run
kubectl get inferencepool -n "$NS" -o yaml
```

InferencePool은 Gateway API Inference Extension에서 제공하는 CRD입니다.
스케줄러가 워크로드 Pod를 찾아 라우팅할 수 있게 해 줍니다.

### 4. HTTPRoute — Gateway로부터 들어오는 트래픽

```bash run
kubectl get httproute -n "$NS" -o yaml
```

HTTPRoute는 Gateway가 받은 요청을 InferencePool로 전달하고,
거기서 다시 스케줄러로 넘깁니다.

### 5. Service — 내부 연결

```bash run
kubectl get svc -n "$NS"
```

| Service | 용도 | 포트 |
|---------|---------|-------|
| `*-workload-svc` | vLLM Pod 노출 | 8000 (HTTPS) |
| `*-epp-service` | EPP 스케줄러 노출 | 9002 (gRPC), 9003 (health), 9090 (metrics), 5557 (ZMQ) |

> 메트릭 포트(9090)는 일반 HTTP지만 bearer 토큰이 필요합니다
> (`metrics-endpoint-auth: true`). 메트릭 조회 방법은 이 시리즈의
> request-flow 튜토리얼에서 다룹니다.

## Step 5: 결과 확인

```bash run
echo "--- Pods ---";          kubectl get pods -n "$NS" -o wide
echo "--- Services ---";      kubectl get svc -n "$NS"
echo "--- InferencePool ---"; kubectl get inferencepool -n "$NS"
echo "--- HTTPRoute ---";     kubectl get httproute -n "$NS"
echo "--- Secrets ---";       kubectl get secret -n "$NS"
```

예상 결과 (apply 전에는 아무것도 없음 → apply 후):

```text
Pods:          2 (vLLM x1 + scheduler x1)
Services:      2 (workload-svc + epp-service)
Deployments:   2 (workload + scheduler)
InferencePool: 1
HTTPRoute:     1
Secrets:       1+ (TLS certs)
```

같은 기대값을 자동으로 검증합니다:

```bash verify
count() { kubectl get "$1" -n "$NS" --no-headers 2>/dev/null | wc -l; }
test "$(count deploy)" -eq 2
test "$(count svc)" -ge 2
test "$(count inferencepool)" -eq 1
test "$(count httproute)" -eq 1
```

## Step 6: 요청 보내기

LLMInferenceService가 `Ready` 상태가 되면 Gateway를 통해 completion 요청을
보냅니다. Kind에서는 worker 노드의 NodePort를 통해 Gateway에 접근하며,
공용 `llmisvc/v1` 모듈이 URL을 계산해 줍니다.

```bash run
GATEWAY_URL=$("$TUT_LIB/llmisvc/v1/gateway-url.sh" "$NS" demo-model)
echo "$GATEWAY_URL"
```

```bash verify retry=10 delay=15
"$TUT_LIB/llmisvc/v1/completion.sh" "$GATEWAY_URL" facebook/opt-125m "Kubernetes is"
```

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
# Usage: completion.sh <url> <model> [prompt] [max_tokens]
# Sends POST <url>/v1/completions, prints the JSON answer and fails unless
# the first choice contains text.
set -euo pipefail
url="${1:?url}"; model="${2:?model}"; prompt="${3:-Kubernetes is}"; max="${4:-20}"
body=$(python3 -c 'import json,sys; print(json.dumps({"model":sys.argv[1],"prompt":sys.argv[2],"max_tokens":int(sys.argv[3])}))' \
  "$model" "$prompt" "$max")
curl -sf "${url}/v1/completions" -H "Content-Type: application/json" -d "$body" \
  | python3 -c 'import json, sys; r = json.load(sys.stdin); print(json.dumps(r, indent=2)); assert r["choices"][0]["text"], "empty completion"'
```

<!-- /tut -->

</details>

## 정리

LLMInferenceService를 삭제하면 컨트롤러가 만든 모든 리소스
(Deployment, Service, InferencePool, HTTPRoute 등)가 OwnerReference
cascading 삭제를 통해 함께 제거됩니다.

```bash cleanup
kubectl delete llminferenceservice demo-model -n "$NS" --ignore-not-found --wait=true
kubectl delete namespace "$NS" --ignore-not-found
```

Kind 클러스터 자체는 이 환경의 튜토리얼들이 공유합니다. 모든 작업을 마쳤다면
환경의 `teardown.sh`로 제거하세요.

## 배운 점

- LLMInferenceService YAML 하나가 10개 이상의 리소스를 생성한다
- **well-known LLMInferenceServiceConfig**가 주입되므로 별도 config가 필요 없다
- 스케줄러 Pod는 세 개의 컨테이너로 구성된다: init (tokenizer 다운로드) + scheduler + tokenizer (기본값에서는 유휴 상태)
- 핵심 구조: **Deployment (워크로드)** ↔ **InferencePool** ↔ **스케줄러** ↔ **HTTPRoute** ↔ **Gateway**
- 정리 시 OwnerReference를 따라 cascading 삭제된다
