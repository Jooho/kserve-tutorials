<!-- tut-explainer source=README.md sha=0825af938700 by=claude reviewed=yes -->
# Journey of a Request - From Gateway to vLLM: how it works

## In one picture

![A request goes from curl to the Envoy proxy Pod, through HTTPRoute rule 0 to the InferencePool; Envoy asks the EPP scheduler which Pod, then forwards to the vLLM Pod; the answer comes back through Envoy with an id that contains the x-request-id](request-journey.svg)

You send one `curl`. On its way it passes the Envoy proxy, the EPP scheduler
and vLLM. The tutorial finds that one request in three places: the answer, the
Envoy access log and the EPP log. The thread that ties them together is a
single value: the **x-request-id**. At the end you look at the
numbers the scheduler uses to choose a Pod.

## What you will learn

- Which objects carry a request from the Gateway to a vLLM Pod, and that
  KServe made all of them from three empty fields (steps 2-6).
- How one `x-request-id` lets you find the same request in the answer, the
  Envoy access log and the EPP log (steps 9-12).
- Why the EPP is asked 16 times for one request (steps 13-14).
- How to tell which Pod served a request, and what "load balancing" looks like
  with one replica (steps 15-19).
- What the EPP actually runs, and what its metrics say before and after you
  repeat a prompt (steps 20-25).

## The pieces

### Three empty fields, a whole route

The manifest has `router: {scheduler: {}, route: {}, gateway: {}}`. From these
the llmisvc controller (`llmisvc-controller-manager`; the name is seen in the
llmisvc-anatomy walk) made the EPP scheduler, the HTTPRoute and the
InferencePool, and hung the route on the shared Gateway
`kserve/kserve-ingress-gateway` (step 5 waits until it is `Programmed`).

The Gateway itself is not one Pod but two programs from the environment, both in
`envoy-gateway-system`:

- `envoy-gateway`: the control plane. It turns Gateway API objects into Envoy
  configuration.
- the **Envoy proxy** Pod (`envoy-kserve-kserve-ingress-gateway-...`): the data
  plane, the program your request actually passes through.

One more controller is involved in this environment: the InferencePool's
status says it was accepted by `ai-gateway-controller`, which runs in
`envoy-ai-gateway-system` (Envoy AI Gateway, installed by the environment). The
HTTPRoute itself is accepted by Envoy Gateway's controller. What exactly the AI
Gateway controller adds to the request path was not visible in this run; the
run only shows that it owns the InferencePool's status.

### Getting in: the NodePort

The Envoy Service is of type LoadBalancer (e.g. `172.18.0.5`, port 80), but the
tutorial's helper `gateway-url.sh` uses the worker node IP and the Service's
NodePort instead: `http://172.18.0.2:30857/<namespace>/demo-model` in this run
(step 6). Behind the NodePort, the Service sends port 80 to port 10080 of the
Envoy Pod; the access log shows exactly that as `downstream_local_address`
(`10.244.1.10:10080`, the Envoy Pod's IP).

### The route: twelve rules

The HTTPRoute (step 4, listed in step 13) has twelve rules:

| Rules | Match | Backend |
|---|---|---|
| `v1-completions-path`, `v1-chat-completions-path`, `v1-responses-path`, `v1-messages-path` | the path under `/<namespace>/demo-model` | InferencePool |
| `v1-model-routing` | the bare `/v1/...` paths, with the header `X-Gateway-Model-Name` (eight matches) | InferencePool |
| `v1-...-publisher-path` (four) | the same four paths under `/publishers/<namespace>/models/<model>` | InferencePool |
| `v1-catch-all-path`, `v1-publisher-path-catch-all`, `v1-catch-all-model-routing` | everything else | Service `demo-model-kserve-workload-svc`, port 8000 |

The path rules strip their prefix (`URLRewrite`), because vLLM only knows its
own paths. The nine rules in the first three rows go through the EPP; the
catch-alls go straight to the vLLM Service. No request of the tutorial used a
catch-all, so this run does not show what they are meant for. The rules also
set both timeouts to `0s`, which in Gateway API means no timeout: a slow
generation is not cut off by the Gateway.

Your completion matched rule 0: the access log says
`route_name: httproute/<namespace>/demo-model-kserve-route/rule/0/match/0/*`.

### The picker: ExtProc to the EPP

The InferencePool names the EPP (`endpointPickerRef`: Service
`demo-model-epp-service`, port 9002, `failureMode: FailOpen`) and selects the
vLLM Pods by label (port 8000). For a request on rule 0, Envoy calls the EPP
over **ExtProc** (External Processing, a gRPC API where Envoy hands a request
to an outside program before forwarding it). The EPP answers with one Pod, and
Envoy sends the request there.

Envoy does not ask once. Step 13 counts the matches of the nine rules that
point at the InferencePool: 4 + 8 + 4 = 16. In Envoy's configuration
every match is a route of its own, and the Gateway's listener has one ExtProc
filter per such route; a request to the pool passes all of them. (The 16
filters were read from Envoy's configuration, outside this walk; the walk
shows the 16 matches and, in step 14, 16 sets of EPP log lines for one
request.)

### One id, three logs

![The x-request-id appears in the answer id, in the Envoy access log next to upstream_host, and in the EPP log lines; upstream_host leads to the vLLM Pod](trace-by-request-id.svg)

- **The answer.** Its `id` is `cmpl-` followed by the x-request-id
  (`cmpl-7ef3fabc-...` in step 9). Strip the prefix and you have the key.
- **Envoy access log** (one JSON line per request, step 11): `x-request-id`,
  `upstream_host` (the Pod the request went to, e.g. `10.244.1.77:8000`),
  `duration` (842 ms for 20 tokens), `response_code` 200, `route_name`.
- **EPP log** (step 12): `EPP received request`, `EPP sent request body
  response(s) to proxy` (with `modelName` and `targetModelName`), `EPP sent
  response body back to proxy`. For the traced request the EPP wrote 16
  complete sets of these lines (step 14 counts them), and with each set an
  error-level line `Request latency values are invalid for TPOT calculation`.
  The request itself succeeded: the EPP only skips one metric, TPOT (time per
  output token). In the logged values `completeTime` is slightly before
  `firstTokenTime`, which a non-streamed answer produces; the README gives the
  source lines.

`upstream_host` gives the Pod IP; `kubectl get pods -o wide` turns it into the
Pod name (step 15), and step 16 checks that it is the workload Pod, not the
scheduler.

### Load balancing with one Pod

Ten requests at once (step 17) all went to the one vLLM Pod: with
`replicas: 1` the EPP has one candidate. Two things make the count in step 18
noisy:

- Envoy writes access-log lines a few seconds after a request ends. Right
  after the burst, step 18 counted only 3 lines for the Pod; the verify a
  moment later found 13 (the ten plus earlier requests).
- The Gateway is shared. Most of the last 50 lines in step 18 name other Pod
  IPs than this tutorial's vLLM Pod.

### How the scheduler chooses

![Inside the EPP: parsers, then the default profile scores Pods with four scorers, queue-scorer (weight 2), kv-cache-utilization-scorer (weight 2), prefix-cache-scorer (weight 3) and no-hit-lru-scorer (weight 2), and max-score-picker takes the highest sum; the answer, one Pod address, goes back to Envoy; two scorers read per-Pod vLLM numbers, two the EPP's own prefix index; metrics are exported on 9090](epp-scheduling.svg)

The EPP logs its effective configuration at start (probe after step 25).
Besides the configured plugins it adds system defaults:

- **scheduling**: one profile, `default` (`single-profile-handler`), with four
  scorers, `queue-scorer` (weight 2), `kv-cache-utilization-scorer` (weight
  2), `prefix-cache-scorer` (weight 3) and `no-hit-lru-scorer` (weight 2), and
  `max-score-picker`.
- **request parsing**: `openai-parser`, `anthropic-parser`, `vllmhttp-parser`,
  all three added by default. The requests here are OpenAI-style.
- **data about Pods**: `metrics-data-source` with `core-metrics-extractor`.
  The queue scorer and the KV-cache scorer score with the EPP's copy of each
  Pod's vLLM numbers (llm-d-router v0.9.0 source; the log shows only the data
  source being configured).
- **data for the prefix scorer**: `approx-prefix-cache-producer` and
  `token-producer`, which the EPP creates on its own ("auto-created default
  producer" in its log: `approx-prefix-cache-producer` with
  `prefix-cache-scorer` as its consumer, `token-producer` with
  `approx-prefix-cache-producer` as its consumer; step 20 checks for these
  lines). They keep the EPP's own index of which Pod got
  which prompt; the prefix scorer reads that index, not vLLM's prefix cache.
  `no-hit-lru-scorer` uses the same match information to tell whether a
  prompt is new (llm-d-router v0.9.0 source, `scorer/nohitlru`; not in the
  log).
  The same log says the index works in blocks of at least 64 tokens: the
  configured 16 is below the minimum and is overridden.
- **flow control**: the plugins `fcfs-ordering-policy`,
  `global-strict-fairness-policy`, `static-usage-limit-policy` and
  `utilization-detector` are instantiated, but the log also says "Experimental
  Flow Control layer is disabled, using legacy admission control".

### Reading the metrics

The metrics port 9090 needs a bearer token whose owner may `get` the URL
`/metrics`, so step 21 creates a ServiceAccount with only that permission, and
step 22 reads the endpoint from a short-lived curl Pod that runs as it.

What the numbers showed:

| | after steps 7-19 | after 5 repeats of one long prompt |
|---|---|---|
| `inference_pool_ready_pods` | 1 | 1 |
| `inference_pool_average_queue_size` | 0 | 0 |
| `inference_pool_average_kv_cache_utilization` | 0 | 0 |
| `inference_pool_average_running_requests` | 0 | 0 |
| `prefix_indexer_hit_bytes` count / sum | 208 / 50432 | 288 / 70656 |
| `prefix_indexer_hit_ratio` count / sum | 208 / 197 | 288 / 276 |
| `prefix_indexer_size` | 11 | 12 |

Read them like this:

- The counts move by 16 per request: 13 requests had been sent before step 22,
  and the count was 208; five more requests added 80. The prefix indexer
  counts one evaluation per EPP call, like the 16 sets of log lines in step
  14.
- Of the 80 new evaluations, one was a miss (the `le="0"` bucket went from 11
  to 12) and 79 were full hits (the ratio sum grew by 79): only the very first
  look at the new prompt found nothing in the indexer.
- The indexer grew by one entry, while the matched bytes grew by 20224.

## Step by step

| README step | What happens in the cluster | What to look at |
|---|---|---|
| 1-3 setup, deploy, wait | the environment is reused; the namespace is created; Ready after a few minutes | `condition met` |
| 4-5 routing | HTTPRoute with twelve rules, InferencePool, Gateway `Programmed` | `backendRefs` kinds: InferencePool and Service |
| 6 gateway URL | node IP + NodePort of the Envoy Service | `http://<node IP>:<NodePort>/<ns>/demo-model` |
| 7-8 first requests | completions through Gateway, route, EPP, vLLM | `finish_reason: length` |
| 9-10 request id | `id` of the answer minus `cmpl-` | `Request ID: ...` |
| 11 Envoy log | one JSON line for the id | `upstream_host`, `duration`, `route_name` |
| 12 EPP log | sets of received / sent body / sent response | `modelName`, `targetModelName` |
| 13-14 rules and calls | nine rules to the pool with 16 matches; 16 sets of EPP lines for the request | `Matches ...: 16; EPP sets ...: 16` |
| 15-16 the Pod | IP from `upstream_host` -> Pod name | the workload Pod, not the scheduler |
| 17-19 ten at once | all to one Pod | the verify, not the first count |
| 20 producers | the EPP's own prefix index helpers | "auto-created default producer" |
| 21-23 metrics | ServiceAccount + ClusterRole, curl Pod with its token | `inference_pool_ready_pods 1` |
| 24-25 repeat a prompt | hit bytes grow | `before 50432 now 70656` |
| cleanup | LLMInferenceService, ClusterRole(Binding), namespace deleted | |

## What we saw that the README does not say

- In this environment the InferencePool is accepted by Envoy AI Gateway's
  `ai-gateway-controller`; the README mentions only Envoy Gateway.
- The EPP adds plugins the configuration does not list: three request parsers,
  the data source for Pod metrics, and flow-control plugins that are
  instantiated while the flow-control layer itself is disabled.
- The EPP's prefix index uses blocks of at least 64 tokens: its log says its
  own configured block size, 16, is below the minimum and is overridden.
- The first count of README Step 5 (walk step 18) can be short (the access log
  lags) and mostly shows lines for other Pod IPs (the Gateway is shared);
  the verify after it is the reliable number.

## Check yourself

<details>
<summary>1. You send <code>GET /&lt;namespace&gt;/demo-model/v1/models</code>. Do you find its x-request-id in the EPP log?</summary>

No. That path matches only a catch-all rule, whose backend is the workload
Service, not the InferencePool. Envoy forwards it without asking the
EPP. It still appears in the Envoy access log.
</details>

<details>
<summary>2. Which log tells you which Pod served a request?</summary>

The Envoy access log: `upstream_host` is the IP and port the request was
forwarded to. `kubectl get pods -o wide` turns the IP into a Pod name.
</details>

<details>
<summary>3. Step 18 shows 3 requests for the Pod although you just sent 10. Is load balancing broken?</summary>

No. Envoy writes the access log a few seconds after a request ends; the count
ran too early. The verify a moment later sees all of them.
</details>

<details>
<summary>4. You repeat one prompt five times. Why do the matched prefix bytes grow while the indexer size barely moves?</summary>

The prompt is already in the indexer after its first evaluation, so later
evaluations match it (hits) without adding much that is new.
</details>

<details>
<summary>5. One request, and the EPP's prefix indexer counts 16 evaluations. Why?</summary>

Envoy asks the EPP once per ExtProc filter, and its configuration has one
filter for every match of the route rules that point at the InferencePool: 16
here.
Each call makes the indexer look the prompt up once.
</details>

Based on a run of llmisvc-request-flow with KServe v0.20.0 on 2026-11-27.
