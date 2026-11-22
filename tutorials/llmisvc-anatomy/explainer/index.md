<!-- tut-explainer source=README.md sha=0 by=claude reviewed=no -->
# One Apply, Ten Resources: how it works

## In one picture

![A request travels from the client through the Envoy Gateway, the HTTPRoute and the InferencePool; Envoy asks the EPP scheduler which Pod to use, then forwards the request to the vLLM Pod](request-path.svg)

You write one small YAML file: an **LLMInferenceService**. KServe turns it into
everything a model server needs: the vLLM Pod that runs the model, a scheduler
that decides which Pod answers each request, and the routing that connects them
to a shared Gateway. The tutorial is about that one step from "one object" to
"a working serving stack", and about what each of the new objects is for.

## What you will learn

- What one `kubectl apply` of an LLMInferenceService creates, and why there are
  ten objects (README steps 2-5, 13-14).
- How a request finds its way: Gateway -> HTTPRoute -> InferencePool -> EPP
  scheduler -> vLLM Pod (steps 10-11, 15-16).
- What runs inside the scheduler Pod and which of its parts the default
  configuration actually uses (steps 6-9).
- Why deleting the LLMInferenceService is enough to clean up (cleanup).

## The pieces

### From one object to ten

![kubectl apply creates the LLMInferenceService; the KServe controller creates ten objects in four groups](one-apply-ten-resources.svg)

The namespace is empty before the apply (step 2). Within about six seconds of
`kubectl apply` (step 3) all ten objects exist; the Pods then need a few
minutes until they are Ready (step 4). Think of the LLMInferenceService as an order form: you fill in the
model, the image and the resources; the controller does the paperwork.

| Group | Objects | What for |
|---|---|---|
| Workload | Deployment `demo-model-kserve`, Service `...-workload-svc` (port 8000) | runs vLLM, which serves the model from `/mnt/models` |
| TLS | Secret `...-self-signed-certs` | certificates the controller generates; used only when TLS is switched on (see below) |
| Scheduler | Deployment `...-router-scheduler`, Service `demo-model-epp-service`, ServiceAccount `demo-model-epp-sa`, Role, RoleBinding | the endpoint picker (EPP), with its own identity and permissions (its log shows it watching Pods and the InferencePool) |
| Traffic wiring | InferencePool `...-inference-pool`, HTTPRoute `...-kserve-route` | connect the shared Gateway to the scheduler and the vLLM Pods |

Where do the command, the probes and the scheduler come from if the YAML does
not mention them? KServe installs **well-known LLMInferenceServiceConfigs** in
the `kserve` namespace (eight of them in this run, e.g.
`kserve-config-llm-template` and `kserve-config-llm-scheduler`), and the
controller merges them into your object. Your YAML sets only what differs for
this model: the image, the environment, the resources, a non-root
securityContext and its own probe timings.

No **LeaderWorkerSet** is created (step 5): with only `replicas` and no
parallelism settings, one ordinary Deployment is enough. LeaderWorkerSets are
for models that span several Pods.

### The path of a request

Look at the first picture again, step by step:

1. The client sends `POST /<namespace>/demo-model/v1/completions` to the
   **Gateway** `kserve/kserve-ingress-gateway`, an Envoy proxy that is not part
   of the model (in this run it is the only Gateway). It has a LoadBalancer
   address (e.g. 172.18.0.5, from cloud-provider-kind), but the tutorial's
   helper `gateway-url.sh` sends the request to the worker node IP and the
   NodePort of the Envoy Service (e.g. `172.18.0.3:31084`, step 15). Both reach
   the same Envoy.
2. The **HTTPRoute** matches the path and rewrites it to `/v1/completions`,
   which is the path vLLM understands.
3. Its backend is not a Service but an **InferencePool**. The pool knows the
   Pods (by label: `kserve.io/component: workload`, port 8000) and who picks
   among them (`endpointPickerRef`: the EPP Service, port 9002).
4. Envoy asks the **EPP** over ExtProc gRPC: "which Pod?". The EPP scores the
   Pods and returns one address.
5. Envoy sends the request to that **vLLM Pod**; the answer comes back the same
   way (step 16 got a 20-token completion).

The HTTPRoute has four rules, not one: `/v1/completions`,
`/v1/chat/completions` and `/v1/responses` go to the InferencePool (so through
the EPP); everything else under `/<namespace>/demo-model` goes straight to the
workload Service and skips the EPP (dashed in the picture).

If the EPP is unavailable, the pool's `failureMode` is `FailOpen`: Envoy still
sends requests to a Pod instead of failing them.

### Inside the scheduler Pod

![The scheduler Pod: the endpoint picker with its ports and plugins, and an unused tokenizer sidecar fed by an init container that downloads only tokenizer files](scheduler-pod.svg)

The Pod has two containers and one init container (step 8 checks exactly
this):

- **main**, the endpoint picker. Ports: 9002 (gRPC, the ExtProc calls from
  Envoy), 9003 (gRPC health), 9090 (metrics). Its configuration (step 9) lists
  four plugins. `single-profile-handler` means there is one scheduling profile,
  `default`, and that profile uses the other three: `queue-scorer` (weight 2),
  `prefix-cache-scorer` (weight 3) and `max-score-picker`, which takes the Pod
  with the highest weighted score.
- **tokenizer**, a sidecar. None of the configured plugins uses it: in the
  KServe v0.18.0 source (`scheduler.go`, `WithUdsTokenizerConfig`) the
  controller connects only the `precise-prefix-cache-scorer` plugin to the
  tokenizer's Unix socket, and that plugin is not in this configuration.
- **storage-initializer** (init). It looks odd on a scheduler, which serves no
  model. It is there only because of the tokenizer sidecar: when the scheduler
  template has a `tokenizer` container, the KServe controller adds the same
  init container the vLLM Pod has, but limited by `STORAGE_ALLOW_PATTERNS` to
  the tokenizer files (`tokenizer.json`, `vocab.json`, `config.json`, ...), no
  weights. The sidecar reads them from `/mnt/models`. So with the default
  plugins this download is done for a container nobody calls. (The reason is
  in the KServe v0.18.0 source, `pkg/controller/v1alpha2/llmisvc/scheduler.go`
  and `workload_storage.go`, not in the cluster output.)

With one replica the choice is easy, but the same machinery decides between
many Pods: prefer short queues, and prefer Pods that already have the start of
your prompt in their cache.

### Cleaning up

Every one of the ten objects has an ownerReference to
`LLMInferenceService/demo-model`. Deleting that one object (the cleanup block)
makes Kubernetes delete the rest; the ReplicaSets and Pods follow their
Deployments.

## Step by step

| README step | What happens in the cluster | What to look at |
|---|---|---|
| 1 setup | Kind cluster with KServe, Envoy Gateway, Gateway API Inference Extension; namespace created | `kubectl get gateway -A`: one Gateway, `Programmed` |
| 2 snapshot | nothing in the namespace yet | "No resources found" |
| 3 apply | the controller creates the ten objects within seconds | Pods in `Init:0/1` |
| 4 wait | storage-initializer downloads, vLLM starts, readiness on `/health` | `Ready` after a few minutes |
| 5 LWS | none: a single-node model uses a Deployment | "No resources found" |
| 6-9 scheduler | the EPP is running; its log shows controllers for InferencePool and Pods and `gRPC server listening` on 9002 | images and the plugin list |
| 10-12 pool, route, services | the wiring of the picture above | `endpointPickerRef`, the four route rules, service ports |
| 13-14 counts | 2 Deployments, 2 Services, 1 InferencePool, 1 HTTPRoute | the verify checks these numbers |
| 15-16 request | a completion through the Gateway | `"finish_reason": "length"` after 20 tokens |

## What we saw that the README does not say

- The README's table calls port 8000 HTTPS, and the workload Service port is
  named `https`. In this run vLLM spoke plain HTTP: the readiness probe uses
  HTTP and the vLLM command line has no TLS options. That is a setting, not a
  README error: in the KServe v0.18.0 well-known configs, vLLM's `--ssl-*`
  options, the probe scheme and the EPP's `--secure-serving` all depend on
  TLS being switched on (`enableLLMInferenceServiceTLS` in the ingress
  config). The same configs mount the `...-self-signed-certs` Secret into
  both Pods either way (`/var/run/kserve/tls`); this run did not look at the
  mounts.
- In this run the only ServiceAccount the controller created is the EPP's; the
  vLLM Pod runs as the namespace's `default` ServiceAccount. The README's
  resource map lists a ServiceAccount under the workload. (In the KServe
  source the controller creates a workload ServiceAccount for multi-node
  LeaderWorkerSet deployments; this tutorial is single-node.)
- The scheduler image in this environment is `llm-d-router-endpoint-picker`.
  The environment replaces the image KServe's config names; its README
  (`envs/kind-kserve/v1/README.md`) says the old image now returns 403. The
  tutorial README's table shows the old name.
- The HTTPRoute has a catch-all rule that bypasses the EPP.

## Check yourself

<details>
<summary>1. You change <code>replicas: 1</code> to 3. Which objects change, and which stay the same?</summary>

The workload Deployment gets three Pods. The InferencePool, HTTPRoute and EPP
stay as they are: the pool selects Pods by label, so new Pods join it
automatically, and the EPP now has three candidates to score.
</details>

<details>
<summary>2. A request to <code>/&lt;namespace&gt;/demo-model/health</code>: does the EPP see it?</summary>

No. Only the three OpenAI-style API paths go to the InferencePool; the
catch-all rule sends other paths straight to the workload Service.
</details>

<details>
<summary>3. Why is no LeaderWorkerSet created?</summary>

The model fits in one Pod (`replicas` only, no parallelism), so a Deployment is
enough. LeaderWorkerSets group several Pods that serve one model together.
</details>

<details>
<summary>4. What is the minimum you must delete to remove everything the tutorial created in the namespace?</summary>

The LLMInferenceService. Its ten objects are owned by it and are deleted with
it.
</details>

Based on a run of llmisvc-anatomy with KServe v0.18.0 on 2026-11-21.
