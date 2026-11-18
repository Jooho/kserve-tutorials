# Module: `llmisvc/v1`

Scripts shared by tutorials that deploy an LLMInferenceService on Kind.
A tutorial lists `llmisvc/v1` under `uses:` in its `tutorial.yaml` and calls
the scripts as `"$TUT_LIB/llmisvc/v1/<script>"`.

| Script | Purpose |
|---|---|
| `gateway-url.sh <ns> <name>` | Print the Gateway URL of an LLMInferenceService (Kind NodePort) |
| `scheduler-pod.sh <ns>` | Print the EPP scheduler Pod name |
| `completion.sh <url> <model> [prompt] [max_tokens]` | Send a completion request; fail unless text comes back |

> Once **frozen** (`frozen: true` in module.yaml) this module must not change;
> create `lib/llmisvc/v2` and move tutorials one at a time.
