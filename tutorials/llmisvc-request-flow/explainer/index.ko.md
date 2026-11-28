<!-- tut-explainer source=README.md sha=0825af938700 by=codex reviewed=yes -->
# 요청의 흐름 - Gateway에서 vLLM까지

## 그림으로 보는 요청 흐름

![curl에서 보낸 요청은 Envoy 프록시 Pod에 도착한 뒤 HTTPRoute의 0번 규칙을 따라 InferencePool로 향합니다. Envoy는 EPP 스케줄러에 어느 Pod로 보낼지 물은 다음 선택된 vLLM Pod로 요청을 전달합니다. 응답은 Envoy를 거쳐 돌아오며 응답 ID에는 x-request-id가 들어 있습니다.](request-journey.svg)

`curl`로 요청을 한 번 보내면 Envoy 프록시, EPP 스케줄러, vLLM을 차례로 거칩니다.
튜토리얼에서는 응답, Envoy 접근 로그, EPP 로그에서 같은 요청을 찾습니다.
세 곳을 연결하는 값은 **x-request-id**입니다. 마지막에는 스케줄러가 Pod를 고를 때
사용하는 지표를 살펴봅니다.

## 배울 내용

- Gateway에서 vLLM Pod까지 요청을 전달하는 리소스가 무엇인지, 그리고 KServe가 빈 필드
  세 개만으로 이 리소스를 모두 만들었다는 점을 확인합니다(2~6단계).
- 하나의 `x-request-id`로 응답, Envoy 접근 로그, EPP 로그에서 같은 요청을 찾습니다(9~12단계).
- 요청 하나에 EPP가 16번 호출되는 이유를 살펴봅니다(13~14단계).
- 어느 Pod가 요청을 처리했는지 확인하고, 복제본이 하나일 때 부하 분산이 어떻게 동작하는지 살펴봅니다(15~19단계).
- EPP가 실제로 어떤 구성으로 동작하는지 살펴보고, 같은 프롬프트를 반복해서 보내기 전후의 지표를 비교합니다(20~25단계).

## 요청 경로 구성

### 빈 필드 세 개로 라우팅 경로 만들기

매니페스트에는 `router: {scheduler: {}, route: {}, gateway: {}}`가 있습니다.
llmisvc 컨트롤러(`llmisvc-controller-manager`)는 이 설정을 바탕으로 EPP 스케줄러,
HTTPRoute, InferencePool을 만들고 HTTPRoute를 공용 Gateway
`kserve/kserve-ingress-gateway`에 연결했습니다(5단계에서는 Gateway가 `Programmed` 상태가 될 때까지 기다립니다).
컨트롤러 이름은 llmisvc-anatomy 실습에서 확인할 수 있습니다.

이 환경에서 Gateway는 두 프로그램으로 동작합니다. 두 프로그램 모두
`envoy-gateway-system`에 있으며, 역할은 다음과 같습니다.

- `envoy-gateway`는 제어 평면입니다. Gateway API 리소스를 Envoy 설정으로 변환합니다.
- **Envoy 프록시** Pod(`envoy-kserve-kserve-ingress-gateway-...`)는 데이터 평면입니다.
  요청이 실제로 이 프로그램을 거칩니다.

이 환경에는 컨트롤러가 하나 더 관여합니다. InferencePool 상태를 보면
`envoy-ai-gateway-system`에서 실행되는 `ai-gateway-controller`가 InferencePool을
수락했습니다. 이 컨트롤러는 환경에 설치된 Envoy AI Gateway의 구성 요소입니다.
HTTPRoute 자체는 Envoy Gateway의 컨트롤러가 수락합니다. 이 실행에서 확인한 것은
AI Gateway 컨트롤러가 InferencePool 상태를 관리한다는 점뿐입니다. 이 컨트롤러가
요청 경로에 구체적으로 어떤 동작을 추가하는지는 확인할 수 없었습니다.

### NodePort로 접속하기

Envoy Service의 유형은 LoadBalancer입니다(예를 들어 `172.18.0.5`의 80번 포트).
튜토리얼의 보조 스크립트 `gateway-url.sh`는 워커 노드 IP와 Service의 NodePort를
사용합니다. 이 실행에서 사용한 주소는 `http://172.18.0.2:30857/<namespace>/demo-model`입니다(6단계).
NodePort 뒤에서는 Service가 80번 포트로 들어온 트래픽을 Envoy Pod의 10080번 포트로
전달합니다. 접근 로그의 `downstream_local_address`에는 Envoy Pod의 IP와 포트가
`10.244.1.10:10080`으로 기록됩니다.

### 라우팅 규칙 열두 개

4단계에서 확인하고 13단계에서 목록을 보는 HTTPRoute에는 규칙이 열두 개 있습니다.

| 규칙 | 일치 조건 | 백엔드 |
|---|---|---|
| `v1-completions-path`, `v1-chat-completions-path`, `v1-responses-path`, `v1-messages-path` | `/<namespace>/demo-model` 아래의 경로 | InferencePool |
| `v1-model-routing` | 접두사가 없는 `/v1/...` 경로와 `X-Gateway-Model-Name` 헤더의 조합(일치 조건 8개) | InferencePool |
| `v1-...-publisher-path`(규칙 4개) | `/publishers/<namespace>/models/<model>` 아래의 같은 경로 4개 | InferencePool |
| `v1-catch-all-path`, `v1-publisher-path-catch-all`, `v1-catch-all-model-routing` | 그 밖의 모든 요청 | Service `demo-model-kserve-workload-svc`의 8000번 포트 |

vLLM은 자체 경로만 인식하므로 경로 규칙은 `URLRewrite`로 각 경로의 접두사를 제거합니다.
표의 처음 세 행에 있는 규칙 9개는 요청을 EPP를 거쳐 전달합니다. 그 밖의 요청을 받는
규칙은 vLLM Service로 바로 전달합니다. 튜토리얼에서는 이 규칙들에 해당하는 요청을
보내지 않아 구체적인 용도는 확인할 수 없었습니다. 규칙의 두 시간 제한은 모두 `0s`입니다.
Gateway API에서는 시간 제한이 없다는 뜻이므로 응답 생성이 오래 걸려도 Gateway가 중간에
끊지 않습니다.

텍스트 생성 요청은 0번 규칙과 일치했습니다. 접근 로그에는
`route_name: httproute/<namespace>/demo-model-kserve-route/rule/0/match/0/*`로 기록됐습니다.

### ExtProc로 EPP에 Pod 선택 요청하기

InferencePool은 `endpointPickerRef`로 EPP를 지정합니다(Service `demo-model-epp-service`,
9002번 포트, `failureMode: FailOpen`). vLLM Pod는 레이블로 선택하며 포트는 8000번입니다.
0번 규칙과 일치하는 요청이 들어오면 Envoy가 **ExtProc**로 EPP를 호출합니다.
ExtProc는 외부 처리(External Processing)용 gRPC API입니다. Envoy는 요청을 전달하기 전에
이 API로 외부 프로그램에 요청을 넘깁니다. EPP가 Pod 하나를 골라 응답하면 Envoy가
그 Pod로 요청을 보냅니다.

Envoy는 요청 하나에 EPP를 여러 번 호출합니다. 13단계에서 InferencePool을 가리키는
규칙 9개의 일치 조건을 합산하면 4 + 8 + 4로 총 16개입니다. Envoy 설정에서는 일치 조건마다
별도의 경로가 생기고, Gateway 리스너에는 이 경로마다 ExtProc 필터가 하나씩 붙습니다.
InferencePool로 가는 요청은 이 필터를 모두 거칩니다. (필터 16개는 단계별 실행과 별도로
Envoy 설정을 읽어 확인했습니다. 단계별 실행에서는 일치 조건 16개를 확인하고, 14단계에서
요청 하나에 해당하는 EPP 로그 16묶음을 확인합니다.)

### ID 하나로 세 곳에서 요청 찾기

![x-request-id는 응답 ID, Envoy 접근 로그의 upstream_host 옆, EPP 로그에 나타납니다. upstream_host로 요청을 처리한 vLLM Pod를 찾을 수 있습니다.](trace-by-request-id.svg)

- **응답.** `id`는 `cmpl-` 뒤에 x-request-id를 붙인 값입니다(9단계에서는
  `cmpl-7ef3fabc-...`). 접두사를 떼면 요청을 찾는 데 쓸 값을 얻습니다.
- **Envoy 접근 로그**(11단계, 요청당 JSON 한 줄)에는 `x-request-id`, `upstream_host`(요청을
  받은 Pod의 주소, 예를 들어 `10.244.1.77:8000`), `duration`(토큰 20개 생성에 842ms),
  `response_code` 값 200, `route_name`이 기록됩니다.
- **EPP 로그**(12단계)에는 `EPP received request`, `EPP sent request body
  response(s) to proxy`(`modelName`과 `targetModelName` 포함), `EPP sent
  response body back to proxy`가 기록됩니다. 추적한 요청에서 EPP는 이 세 줄을 모두
  기록하는 일을 16번 반복했습니다(14단계에서 묶음 수를 셉니다). 묶음마다 오류 수준의
  `Request latency values are invalid for TPOT calculation` 로그도 한 줄씩 남겼습니다.
  요청 자체는 성공했습니다. EPP는 출력 토큰당 소요 시간(TPOT) 지표 하나만 집계하지
  않습니다. 비스트리밍 응답에서는 로그에 기록된 `completeTime`이 `firstTokenTime`보다
  약간 앞섭니다. README에서 해당 소스 코드 줄을 확인할 수 있습니다.

`upstream_host`에서 Pod IP를 확인하고, 15단계에서 `kubectl get pods -o wide`로 해당 IP의
Pod 이름을 찾습니다. 16단계에서는 이 Pod가 워크로드 Pod임을 확인해 스케줄러와 구분합니다.

### Pod가 하나일 때의 부하 분산

17단계에서 동시에 보낸 요청 10개는 모두 하나뿐인 vLLM Pod로 갔습니다. `replicas: 1`이므로
EPP가 선택할 수 있는 Pod는 하나뿐입니다. 18단계에서 센 로그 줄 수에는 두 가지 요인이 영향을 줍니다.

- Envoy는 요청이 끝나고 몇 초 뒤에 접근 로그를 남깁니다. 요청을 한꺼번에 보낸 직후
  18단계에서는 해당 Pod의 로그가 3줄만 잡혔습니다. 잠시 뒤 다시 확인하니 방금 보낸
  요청 10개와 앞서 보낸 요청을 합쳐 13줄이었습니다.
- Gateway는 공용입니다. 18단계에서 본 최근 로그 50줄의 대부분에는 이 튜토리얼의
  vLLM Pod와 다른 Pod의 IP가 기록돼 있습니다.

### 스케줄러가 Pod를 고르는 방식

![EPP가 요청을 파싱하면 기본 프로필의 플러그인 네 개가 Pod마다 점수를 매깁니다. 가중치는 queue-scorer가 2, kv-cache-utilization-scorer가 2, prefix-cache-scorer가 3, no-hit-lru-scorer가 2입니다. max-score-picker는 가중 점수의 합이 가장 높은 Pod를 고릅니다. EPP는 선택한 Pod의 주소 하나를 Envoy로 돌려보냅니다. 점수를 매기는 플러그인 두 개는 Pod별 vLLM 수치를 읽고, 나머지 두 개는 EPP 자체의 접두사 인덱스를 읽습니다. 지표는 9090번 포트에서 제공합니다.](epp-scheduling.svg)

EPP는 시작할 때 실제로 적용된 설정을 로그에 남깁니다(25단계가 끝난 뒤 추가 확인).
설정에 지정된 플러그인에 더해 다음 기본 구성도 추가합니다.

- **스케줄링**에는 `default` 프로필 하나(`single-profile-handler`)를 사용합니다.
  점수를 매기는 플러그인은 `queue-scorer`(가중치 2), `kv-cache-utilization-scorer`(가중치 2),
  `prefix-cache-scorer`(가중치 3), `no-hit-lru-scorer`(가중치 2)입니다. 이 프로필에는
  `max-score-picker`도 들어 있습니다.
- **요청 파싱**에는 `openai-parser`, `anthropic-parser`, `vllmhttp-parser`가 모두
  기본으로 추가됩니다. 여기서 보낸 요청은 OpenAI 형식입니다.
- **Pod 정보**는 `core-metrics-extractor`가 연결된 `metrics-data-source`로 수집합니다.
  대기열과 KV 캐시 점수를 매기는 플러그인은 EPP가 보관하는 Pod별 vLLM 수치를 사용합니다.
  이 동작은 llm-d-router v0.9.0 소스에서 확인할 수 있습니다. 로그에는 데이터 소스 설정만 나옵니다.
- **접두사 점수 산정용 데이터**는 `approx-prefix-cache-producer`와 `token-producer`가
  관리합니다. EPP가 둘 다 자동으로 만들며, 로그에는 각각 "auto-created default
  producer"라고 표시됩니다. 로그에 따르면 `approx-prefix-cache-producer`가 만든 데이터는
  `prefix-cache-scorer`가 사용하고, `token-producer`가 만든 데이터는
  `approx-prefix-cache-producer`가 사용합니다(20단계에서 두 로그 줄을 확인합니다). 두 플러그인은
  어느 Pod가 어떤 프롬프트를 받았는지 EPP 자체 인덱스에 기록합니다. 접두사 점수를
  매기는 플러그인은 EPP 인덱스만 읽으며 vLLM의 접두사 캐시는 참조하지 않습니다.
  `no-hit-lru-scorer`도 같은 일치 정보를 바탕으로 새 프롬프트인지 판단합니다
  (llm-d-router v0.9.0 소스의 `scorer/nohitlru`에서 확인할 수 있으며 로그에는 나오지 않습니다).
  같은 로그에는 인덱스가 블록 하나에 토큰을 최소 64개씩 처리한다고 나옵니다. 블록 크기로
  설정한 16개는 최솟값보다 작아 다른 값으로 대체됩니다.
- **흐름 제어**용 플러그인 `fcfs-ordering-policy`, `global-strict-fairness-policy`,
  `static-usage-limit-policy`, `utilization-detector`의 인스턴스가 만들어집니다.
  로그에는 `Experimental Flow Control layer is disabled, using legacy admission control`
  (실험적 흐름 제어 계층이 꺼져 있어 기존 요청 수락 제어를 쓴다는 뜻)이라는 메시지도 남습니다.

### 지표 읽기

9090번 포트에서 지표를 읽으려면 `/metrics` URL에 `get` 권한이 있는 주체의 베어러
토큰이 필요합니다. 21단계에서는 이 권한만 가진 ServiceAccount를 만듭니다.
22단계에서는 이 ServiceAccount로 잠깐 실행하는 curl Pod에서 해당 엔드포인트를 조회합니다.

조회한 값은 다음과 같습니다.

| | 7~19단계 이후 | 긴 프롬프트 하나를 5번 보낸 뒤 |
|---|---|---|
| `inference_pool_ready_pods` | 1 | 1 |
| `inference_pool_average_queue_size` | 0 | 0 |
| `inference_pool_average_kv_cache_utilization` | 0 | 0 |
| `inference_pool_average_running_requests` | 0 | 0 |
| `prefix_indexer_hit_bytes` 평가 횟수 / 합계 | 208 / 50432 | 288 / 70656 |
| `prefix_indexer_hit_ratio` 평가 횟수 / 합계 | 208 / 197 | 288 / 276 |
| `prefix_indexer_size` | 11 | 12 |

각 값은 이렇게 해석합니다.

- 요청 하나당 평가 횟수가 16회씩 늘었습니다. 22단계 전에 요청을 13개 보내 평가 횟수는
  208회였습니다. 이후 요청 5개를 더 보내자 80회가 늘었습니다. 접두사 인덱서는 EPP를
  한 번 호출할 때마다 평가를 1회 집계합니다. 14단계에서 요청 하나에 로그가 16묶음 나온
  것과 횟수가 같습니다.
- 새로 집계된 평가 80회 중 1회는 인덱스에서 일치하는 항목을 찾지 못했고(`le="0"` 버킷이
  11회에서 12회로 증가), 79회는 완전히 일치했습니다(적중률 합계가 79 증가). 새 프롬프트를
  맨 처음 평가했을 때만 인덱스에서 일치하는 항목을 찾지 못했습니다.
- 인덱서에는 항목이 하나 추가됐고, 일치한 접두사 데이터는 20224바이트 늘었습니다.

## 단계별로 살펴보기

| README 단계 | 클러스터에서 일어나는 일 | 확인할 내용 |
|---|---|---|
| 1~3단계 환경 준비, 배포, 대기 | 기존 환경을 재사용합니다. 네임스페이스를 만들고 배포한 뒤 몇 분이 지나면 Ready 상태가 됩니다. | `condition met` |
| 4~5단계 라우팅 | 규칙 열두 개가 있는 HTTPRoute와 InferencePool을 확인합니다. Gateway는 `Programmed` 상태가 됩니다. | `backendRefs`의 리소스 종류는 InferencePool과 Service입니다. |
| 6단계 Gateway URL | 노드 IP와 Envoy Service의 NodePort를 사용합니다. | `http://<node IP>:<NodePort>/<ns>/demo-model` |
| 7~8단계 첫 요청 | 텍스트 생성 요청이 Gateway, HTTPRoute, EPP를 거쳐 vLLM에 도착합니다. | `finish_reason: length` |
| 9~10단계 요청 ID | 응답의 `id`에서 `cmpl-`을 뗍니다. | `Request ID: ...` |
| 11단계 Envoy 로그 | 해당 요청 ID의 JSON 로그가 한 줄 나옵니다. | `upstream_host`, `duration`, `route_name` |
| 12단계 EPP 로그 | 요청 수신, 요청 본문 처리 결과 전송, 응답 전송 로그가 여러 묶음 나옵니다. | `modelName`, `targetModelName` |
| 13~14단계 규칙과 호출 횟수 | InferencePool을 가리키는 규칙 9개에 일치 조건이 16개 있습니다. 요청 하나에 EPP 로그가 16묶음 나옵니다. | `Matches ...: 16; EPP sets ...: 16` |
| 15~16단계 Pod 확인 | `upstream_host`의 IP로 Pod 이름을 찾습니다. | 찾은 Pod가 워크로드 Pod인지 확인해 스케줄러와 구분합니다. |
| 17~19단계 요청 10개 동시 전송 | 모든 요청이 Pod 하나로 갑니다. | 검증 단계에서 다시 센 값을 봅니다. |
| 20단계 접두사 인덱스 데이터 생성 | EPP가 자체 접두사 인덱스에 쓸 데이터를 만드는 플러그인을 확인합니다. | "auto-created default producer" |
| 21~23단계 지표 조회 | ServiceAccount와 ClusterRole을 만들고 curl Pod에서 해당 ServiceAccount의 토큰을 사용합니다. | `inference_pool_ready_pods 1` |
| 24~25단계 프롬프트 반복 | 일치한 접두사의 바이트 수가 늘어납니다. | `before 50432 now 70656` |
| 정리 | LLMInferenceService, ClusterRole 및 ClusterRoleBinding, 네임스페이스를 삭제합니다. | |

## README에 없던 관찰 결과

- 이 환경에서 InferencePool을 수락하는 컨트롤러는 Envoy AI Gateway의
  `ai-gateway-controller`입니다. README는 Envoy Gateway만 언급합니다.
- EPP는 설정에 없는 플러그인도 추가합니다. 요청을 파싱하는 플러그인 3개, Pod 지표를
  수집하는 플러그인, 흐름 제어 플러그인입니다. 흐름 제어 계층이 꺼져 있어도 흐름 제어
  플러그인의 인스턴스는 만들어집니다.
- EPP의 접두사 인덱스는 최소 64개 토큰을 한 블록으로 처리합니다. 로그를 보면 EPP
  설정에서 지정한 블록 크기인 16개는 최솟값보다 작아 적용되지 않습니다.
- README 5단계(단계별 실행의 18단계)에서 처음 센 값은 접근 로그가 늦게 기록돼 실제보다
  적을 수 있습니다. Gateway가 공용이라 이때 조회한 로그 대부분에는 다른 Pod의 IP가
  나옵니다. 믿을 수 있는 값은 그 뒤 검증 단계에서 다시 센 값입니다.

## 이해도 확인

<details>
<summary>1. <code>GET /&lt;namespace&gt;/demo-model/v1/models</code>를 보냅니다. 이 요청의 x-request-id를 EPP 로그에서 찾을 수 있습니까?</summary>

찾을 수 없습니다. 이 경로는 그 밖의 요청을 받는 규칙에만 해당합니다. 이 규칙은
InferencePool을 거치지 않고 워크로드 Service로 바로 연결됩니다. Envoy는 EPP에 묻지
않고 요청을 전달합니다. 요청은 Envoy 접근 로그에 남습니다.
</details>

<details>
<summary>2. 어느 Pod가 요청을 처리했는지 어떤 로그에서 확인할 수 있습니까?</summary>

Envoy 접근 로그에서 확인할 수 있습니다. `upstream_host`는 요청을 전달한 대상의 IP와
포트입니다. `kubectl get pods -o wide`로 해당 IP의 Pod 이름을 찾습니다.
</details>

<details>
<summary>3. 방금 요청을 10개 보냈는데 18단계에서는 해당 Pod에 요청이 3개만 기록됩니다. 부하 분산에 문제가 있습니까?</summary>

문제가 없습니다. Envoy는 요청이 끝나고 몇 초 뒤에 접근 로그를 기록합니다. 처음에는
너무 일찍 셌기 때문에 3개만 나왔습니다. 잠시 뒤 검증 단계에서는 10개를 모두 확인할 수 있습니다.
</details>

<details>
<summary>4. 같은 프롬프트를 5번 보냅니다. 인덱서의 크기는 거의 그대로인데 일치한 접두사의 바이트 수는 왜 늘어납니까?</summary>

첫 평가가 끝나면 프롬프트가 이미 인덱서에 들어 있습니다. 이후 평가에서는 같은
프롬프트를 인덱스에서 찾아 적중으로 집계하므로 새로 추가되는 내용은 거의 없습니다.
</details>

<details>
<summary>5. 요청은 하나인데 EPP의 접두사 인덱서는 왜 평가를 16회 집계합니까?</summary>

Envoy는 ExtProc 필터마다 EPP를 한 번 호출합니다. Envoy 설정에서는 InferencePool을
가리키는 라우팅 규칙의 일치 조건마다 필터가 하나씩 붙으며, 이 구성에는 해당 필터가
16개 있습니다.
EPP가 한 번 호출될 때마다 인덱서는 프롬프트를 한 번 조회합니다.
</details>

Based on a run of llmisvc-request-flow with KServe v0.20.0 on 2026-11-27.
