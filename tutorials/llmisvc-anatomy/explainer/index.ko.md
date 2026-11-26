<!-- tut-explainer source=README.md sha=8559b134b951 by=codex reviewed=yes -->
# 한 번의 적용으로 리소스 10개가 만들어지는 과정

## 그림으로 보는 요청 흐름

![클라이언트가 보낸 요청은 Envoy Gateway에 도착해 HTTPRoute와 InferencePool을 따라 처리됩니다. Envoy는 EPP 스케줄러에 어느 Pod를 사용할지 물은 뒤 해당 vLLM Pod로 요청을 보냅니다.](request-path.svg)

짧은 YAML 파일 하나에 **LLMInferenceService**를 정의합니다. KServe는 이 정의를 바탕으로 모델 서버에 필요한 리소스를 모두 만듭니다. 모델을 실행하는 vLLM Pod와 각 요청을 어느 Pod가 처리할지 정하는 스케줄러, 그리고 이 둘을 공유 Gateway에 연결하는 라우팅 리소스가 생깁니다. 이 실습에서는 객체 하나를 적용해 모델 서빙 환경이 동작하기까지의 과정과 새로 생긴 각 객체의 역할을 살펴봅니다.

## 실습에서 배울 내용

- LLMInferenceService에 `kubectl apply`를 한 번 실행하면 무엇이 생기고, 왜 객체가 10개인지 살펴봅니다(README 2~5단계, 13~14단계).
- 요청이 Gateway → HTTPRoute → InferencePool → EPP 스케줄러 → vLLM Pod 순서로 전달되는 과정을 살펴봅니다(10~11단계, 15~16단계).
- 스케줄러 Pod 안에서 무엇이 실행되고, 기본 설정이 그중 어떤 구성 요소를 실제로 사용하는지 확인합니다(6~9단계).
- LLMInferenceService 하나만 삭제해도 정리가 끝나는 이유를 살펴봅니다(정리 단계).

## 구성 요소

### 객체 하나에서 10개로

![kubectl apply가 LLMInferenceService를 생성하면 llmisvc 컨트롤러가 네 그룹에 걸쳐 객체 10개를 만듭니다.](one-apply-ten-resources.svg)

적용 전에는 네임스페이스가 비어 있습니다(2단계). `kubectl apply`를 실행하고 약 6초 안에 객체 10개가 모두 생깁니다(3단계). 이후 Pod가 Ready 상태가 되기까지는 몇 분이 더 걸립니다(4단계). LLMInferenceService는 주문서와 같습니다. 모델, 이미지, 리소스를 적으면 나머지 생성 작업은 컨트롤러가 맡습니다. 이 작업을 맡는 컨트롤러는 `kserve` 네임스페이스의 `llmisvc-controller-manager`입니다. 같은 네임스페이스의 `kserve-controller-manager`는 예측용 InferenceService를 담당하며, 이 객체는 다루지 않습니다.

| 그룹 | 객체 | 역할 |
|---|---|---|
| 워크로드 | Deployment `demo-model-kserve`, Service `...-workload-svc`(포트 8000) | vLLM을 실행합니다. vLLM은 `/mnt/models`의 모델로 요청을 처리합니다. |
| TLS | Secret `...-self-signed-certs` | 컨트롤러가 생성한 인증서를 담습니다. TLS를 켰을 때만 인증서를 사용합니다(아래 참고). |
| 스케줄러 | Deployment `...-router-scheduler`, Service `demo-model-epp-service`, ServiceAccount `demo-model-epp-sa`, Role, RoleBinding | 전용 계정과 권한을 갖춘 엔드포인트 선택기(EPP)를 구성합니다. 로그에서 EPP가 Pod와 InferencePool을 감시하는 것을 확인할 수 있습니다. |
| 트래픽 연결 | InferencePool `...-inference-pool`, HTTPRoute `...-kserve-route` | 공유 Gateway를 스케줄러 및 vLLM Pod와 연결합니다. |

YAML에 실행 명령, 프로브, 스케줄러를 정의하지 않았는데 이 설정들은 어디에서 올까요? KServe는 `kserve` 네임스페이스에 **KServe가 기본으로 제공하는 LLMInferenceServiceConfig**를 설치하고, 컨트롤러는 그 설정을 사용자가 만든 객체에 병합합니다. 이번 실행에서는 `kserve-config-llm-template`, `kserve-config-llm-scheduler` 등을 포함해 8개가 설치됐습니다. YAML에는 이 모델에 맞게 달라지는 항목만 지정합니다. 이미지, 환경 변수, 리소스, 루트 사용자로 실행하지 않도록 지정한 securityContext, 그리고 이 모델에 맞춘 프로브 타이밍입니다.

5단계에서는 **LeaderWorkerSet**이 생성되지 않습니다. 병렬화 설정 없이 `replicas`만 지정하면 일반 Deployment 하나면 충분합니다. LeaderWorkerSet은 여러 Pod에 걸쳐 실행되는 모델에 사용합니다.

### 요청이 이동하는 경로

첫 번째 그림의 요청 경로를 단계별로 살펴봅니다.

1. 클라이언트는 **Gateway** `kserve/kserve-ingress-gateway`로 `POST /<namespace>/demo-model/v1/completions` 요청을 보냅니다. 이 Envoy 프록시는 모델과 별도로 동작하며, 이번 실행에서는 유일한 Gateway입니다. Gateway에는 cloud-provider-kind가 할당한 LoadBalancer 주소(예: 172.18.0.5)가 있습니다. 실습의 보조 스크립트 `gateway-url.sh`는 워커 노드의 IP와 Envoy Service의 NodePort(15단계의 예: `172.18.0.3:31084`)를 사용합니다. 두 주소 모두 같은 Envoy에 연결됩니다.
2. **HTTPRoute**는 요청 경로가 규칙과 일치하면 vLLM이 처리할 수 있는 경로인 `/v1/completions`로 바꿉니다.
3. 이 규칙은 백엔드에 Service 대신 **InferencePool**을 지정합니다. InferencePool에는 대상 Pod를 찾는 레이블 `kserve.io/component: workload`와 포트 8000이 지정돼 있습니다. 어떤 Pod를 쓸지 결정하는 주체는 `endpointPickerRef`가 가리키는 EPP Service(포트 9002)입니다.
4. Envoy는 ExtProc gRPC로 **EPP**에 어느 Pod를 사용할지 묻습니다. EPP는 Pod마다 점수를 계산해 주소 하나를 반환합니다. Envoy는 답을 기다리는 동안 원래 요청을 보관하며, 요청 자체는 EPP를 거치지 않습니다. 이 내용은 설정을 근거로 한 것입니다. 이번 실행에서는 EPP가 선택한 주소를 로그에 남기지 않았고, Pod가 하나여서 선택지도 하나뿐이었습니다. 실제로 Envoy는 EPP에 세 번 묻습니다. Envoy Gateway는 InferencePool을 가리키는 HTTPRoute 규칙마다 ExtProc 필터를 하나씩 추가하는데, 아래에서 볼 수 있듯 그런 규칙이 3개입니다. 이 동작은 이번 실행이 아니라 이후 실행의 Envoy 설정에서 확인했습니다. llmisvc-request-flow에서는 EPP 로그에서도 확인할 수 있습니다.
5. Envoy는 선택된 **vLLM Pod**의 IP로 요청을 직접 보냅니다. 이때 중간에 Service를 거치지 않습니다. EPP는 응답의 `x-gateway-destination-endpoint` 헤더에 Pod 주소를 담고, 이 규칙들이 사용하는 Envoy 클러스터는 그 주소로 연결합니다. 이 동작은 이번 실행이 아니라 Envoy 설정과 llmisvc-request-flow의 Envoy 로그에서 확인했습니다. 그 로그의 `upstream_host` 값은 Pod IP였습니다. 응답은 같은 경로로 돌아옵니다. 16단계에서는 토큰 20개짜리 텍스트 생성 결과를 받았습니다.

HTTPRoute에는 규칙이 총 4개 있습니다. `/v1/completions`, `/v1/chat/completions`, `/v1/responses` 요청은 InferencePool로 라우팅되므로 EPP가 대상 Pod를 선택합니다. `/<namespace>/demo-model` 아래의 나머지 경로는 모두 EPP를 건너뛰고 워크로드 Service로 바로 연결됩니다. 그림에서는 이 경로를 점선으로 표시했습니다.

워크로드 Service는 추론 요청 경로에 포함되지 않습니다. 그 밖의 용도에서는 이 Service의 이름과 연결된 vLLM Pod 목록을 사용합니다. 나머지 경로를 처리하는 규칙에서 Envoy는 Service의 엔드포인트 목록에서 Pod를 찾아 연결합니다. llmisvc-monitoring의 Prometheus와 `...-workload-svc:8000`으로 요청을 보내는 클러스터 내부 클라이언트도 이 Service를 사용합니다.

InferencePool의 `failureMode`는 `FailOpen`입니다. EPP를 사용할 수 없어도 Envoy는 요청을 실패로 처리하는 대신 Pod로 보냅니다.

### 스케줄러 Pod 내부

![스케줄러 Pod에는 포트와 플러그인이 설정된 엔드포인트 선택기와 기본 설정에서 쓰이지 않는 토크나이저 사이드카가 있습니다. 초기화 컨테이너는 이 사이드카에 필요한 토크나이저 파일만 내려받습니다.](scheduler-pod.svg)

스케줄러 Pod에는 일반 컨테이너 2개와 초기화 컨테이너 1개가 있습니다. 8단계에서 이 구성을 확인합니다.

- **main**은 엔드포인트 선택기입니다. 포트 9002는 Envoy의 ExtProc gRPC 호출, 9003은 gRPC 상태 확인, 9090은 메트릭에 사용합니다. 9단계에서 확인하는 설정에는 플러그인 4개가 나옵니다. `single-profile-handler`는 스케줄링 프로필을 `default` 하나만 사용한다는 뜻입니다. 이 프로필은 나머지 3개 플러그인인 `queue-scorer`(가중치 2), `prefix-cache-scorer`(가중치 3), `max-score-picker`를 사용합니다. `max-score-picker`는 가중치를 반영한 점수가 가장 높은 Pod를 고릅니다.
- **tokenizer**는 사이드카입니다. 현재 설정된 플러그인 중 이 사이드카를 사용하는 것은 없습니다. KServe v0.18.0 소스의 `scheduler.go`에 있는 `WithUdsTokenizerConfig`를 보면, 컨트롤러는 `precise-prefix-cache-scorer` 플러그인만 토크나이저의 유닉스 소켓에 연결합니다. 이 플러그인은 현재 설정에 빠져 있습니다.
- **storage-initializer**는 초기화 컨테이너입니다. 모델을 서빙하지 않는 스케줄러에 이 컨테이너가 있는 이유는 토크나이저 사이드카 때문입니다. 스케줄러 템플릿에 `tokenizer` 컨테이너가 있으면 llmisvc 컨트롤러는 vLLM Pod에 쓰는 것과 같은 초기화 컨테이너를 추가합니다. 다만 `STORAGE_ALLOW_PATTERNS`로 다운로드 범위를 토크나이저 파일(`tokenizer.json`, `vocab.json`, `config.json` 등)로 제한해 모델 가중치는 내려받지 않습니다. 사이드카는 `/mnt/models`에서 이 파일을 읽습니다. 따라서 기본 플러그인 구성에서는 아무 플러그인도 호출하지 않는 사이드카를 위해 파일을 내려받습니다. 초기화 컨테이너가 추가되는 이유는 클러스터 출력만으로는 알 수 없으며, KServe v0.18.0 소스인 `pkg/controller/v1alpha2/llmisvc/scheduler.go`와 `workload_storage.go`에서 확인할 수 있습니다.

복제본이 하나일 때는 선택이 간단합니다. Pod가 여러 개일 때도 같은 방식으로 고릅니다. 대기열이 짧은 Pod와 요청 프롬프트의 앞부분을 이미 캐시에 담고 있는 Pod에 더 높은 점수를 줍니다.

### 리소스 정리

객체 10개에는 모두 `LLMInferenceService/demo-model`을 가리키는 ownerReference가 있습니다. 정리 명령 블록에서 이 객체 하나를 삭제하면 Kubernetes가 나머지를 삭제합니다. ReplicaSet과 Pod는 각각을 관리하는 Deployment가 삭제될 때 함께 정리됩니다.

## 단계별로 확인할 내용

| README 단계 | 클러스터에서 일어나는 일 | 확인할 내용 |
|---|---|---|
| 1단계 설정 | Kind 클러스터에 KServe, Envoy Gateway, Gateway API Inference Extension이 설치되어 있고, 네임스페이스가 생성됩니다. | `kubectl get gateway -A`에서 Gateway 1개가 `Programmed` 상태인지 확인합니다. |
| 2단계 초기 상태 확인 | 네임스페이스가 아직 비어 있습니다. | 리소스가 없다는 메시지("No resources found")가 표시됩니다. |
| 3단계 적용 | 컨트롤러가 몇 초 안에 객체 10개를 만듭니다. | Pod가 `Init:0/1` 상태입니다. |
| 4단계 대기 | 초기화 컨테이너가 파일을 내려받고 vLLM이 시작됩니다. `/health`에서 준비 상태를 확인합니다. | 몇 분 뒤 `Ready` 상태가 됩니다. |
| 5단계 LWS | LWS는 생성되지 않습니다. 단일 노드에서 실행되는 모델은 Deployment를 사용합니다. | 리소스가 없다는 메시지("No resources found")가 표시됩니다. |
| 6~9단계 스케줄러 | EPP가 실행됩니다. 로그에 InferencePool과 Pod를 감시하는 컨트롤러와 포트 9002의 `gRPC server listening` 메시지가 표시됩니다. | 이미지와 플러그인 목록을 확인합니다. |
| 10~12단계 InferencePool, HTTPRoute, Service | 위 그림과 같이 연결됩니다. | `endpointPickerRef`, 라우팅 규칙 4개, Service 포트를 확인합니다. |
| 13~14단계 리소스 개수 | Deployment 2개, Service 2개, InferencePool 1개, HTTPRoute 1개가 있습니다. | 검증 과정에서 각 리소스의 개수를 확인합니다. |
| 15~16단계 요청 | Gateway로 텍스트 생성을 요청해 결과를 받습니다. | 토큰 20개를 생성한 뒤 `"finish_reason": "length"`가 반환됩니다. |

## README에 나오지 않는 실습 관찰 결과

- README 표에는 포트 8000이 HTTPS라고 적혀 있고, 워크로드 Service의 포트 이름도 `https`입니다. 이번 실행에서 vLLM은 암호화되지 않은 HTTP를 사용했습니다. 준비 상태 프로브는 HTTP를 사용했고 vLLM 실행 명령에는 TLS 옵션이 없었습니다. 이 차이는 TLS 설정에 따라 생기며 README의 오류는 아닙니다. KServe v0.18.0의 기본 제공 설정에서 vLLM의 `--ssl-*` 옵션, 프로브의 프로토콜, EPP의 `--secure-serving`은 모두 ingress 설정의 `enableLLMInferenceServiceTLS`에 따라 달라집니다. 같은 설정은 TLS를 켜든 끄든 `...-self-signed-certs` Secret을 두 Pod의 `/var/run/kserve/tls`에 마운트하도록 구성합니다. 이번 실행에서는 실제 마운트 상태를 살펴보지 않았습니다.
- 이번 실행에서 컨트롤러가 만든 ServiceAccount는 EPP용 하나뿐입니다. vLLM Pod는 네임스페이스의 `default` ServiceAccount로 실행됩니다. README의 리소스 구성도에는 워크로드에도 ServiceAccount가 표시돼 있습니다. KServe 소스에서는 여러 노드에 걸친 LeaderWorkerSet 배포에 워크로드용 ServiceAccount를 만듭니다. 이 실습은 단일 노드에서 모델을 실행합니다.
- 이 환경에서 스케줄러 이미지는 `llm-d-router-endpoint-picker`입니다. 실습 환경은 KServe 설정에 지정된 이미지를 교체합니다. 환경의 README(`envs/kind-kserve/v1/README.md`)에 따르면 이전 이미지는 이제 403을 반환합니다. 실습 README의 표에는 이전 이미지 이름이 나옵니다.
- HTTPRoute에는 나머지 경로를 모두 받아 EPP를 건너뛰는 규칙이 있습니다.

## 이해도 확인

<details>
<summary>1. <code>replicas: 1</code>의 값을 3으로 바꾸면 어떤 객체가 달라지고 어떤 객체가 그대로 유지됩니까?</summary>

워크로드 Deployment의 Pod가 3개로 늘어납니다. InferencePool, HTTPRoute, EPP는 그대로 유지됩니다. InferencePool은 레이블로 Pod를 선택하므로 새 Pod도 자동으로 대상에 포함됩니다. 이제 EPP는 후보 Pod 3개의 점수를 계산합니다.
</details>

<details>
<summary>2. <code>/&lt;namespace&gt;/demo-model/health</code>로 요청을 보내면 EPP가 관여합니까?</summary>

관여하지 않습니다. OpenAI 형식의 API 경로 3개만 InferencePool로 라우팅됩니다. 나머지 경로는 이를 모두 처리하는 규칙에 따라 워크로드 Service로 바로 연결됩니다.
</details>

<details>
<summary>3. LeaderWorkerSet은 왜 생성되지 않습니까?</summary>

모델이 Pod 하나에서 실행되므로 Deployment 하나면 충분합니다. `replicas`만 지정했고 병렬화 설정은 없습니다. LeaderWorkerSet은 여러 Pod가 함께 모델 하나를 서빙할 때 그 Pod들을 묶어 줍니다.
</details>

<details>
<summary>4. 실습에서 네임스페이스에 만든 리소스를 모두 정리하려면 최소한 어떤 객체를 삭제해야 합니까?</summary>

LLMInferenceService 하나만 삭제하면 됩니다. 이 LLMInferenceService가 소유한 객체 10개도 함께 삭제됩니다.
</details>

Based on a run of llmisvc-anatomy with KServe v0.18.0 on 2026-11-21.
