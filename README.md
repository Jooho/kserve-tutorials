# KServe Tutorials

Hands-on tutorials for [KServe](https://kserve.github.io/website/). Every
tutorial lists the KServe versions it was tested with: CI runs it end to end
against those versions whenever it changes, and before every release.

## Tutorials

<!-- tut:catalog -->

<!-- Generated from tutorials/*/tutorial.yaml by `./tut sync` — do not edit by hand. -->
| Tutorial | Status | Tested KServe | Tags | Environment | GPU |
|---|---|---|---|---|---|
| [Two Models, One Answer — InferenceGraph Ensemble and Combiner](tutorials/inferencegraph-ensemble/) | ✅ stable | v0.18.0, v0.20.0 | `inferencegraph` `inferenceservice` `mlserver` `storage` `ensemble` `intermediate` | `kind-kserve/v1` | no |
| [One Apply, Ten Resources — LLMInferenceService Anatomy](tutorials/llmisvc-anatomy/) | ✅ stable | v0.18.0, v0.20.0 | `llmisvc` `gateway-api-inference-extension` `epp-scheduler` `vllm` `resources` `beginner` | `kind-kserve/v1` | no |
| [Through the Scheduler's Eyes - Metric Observation](tutorials/llmisvc-monitoring/) | ✅ stable | v0.18.0, v0.20.0 | `llmisvc` `gateway-api-inference-extension` `epp-scheduler` `vllm` `observability` `intermediate` | `kind-kserve/v1` | no |
| [Journey of a Request — From Gateway to vLLM](tutorials/llmisvc-request-flow/) | ✅ stable | v0.18.0, v0.20.0 | `llmisvc` `gateway-api-inference-extension` `epp-scheduler` `envoy-gateway` `vllm` `request-flow` `observability` `intermediate` | `kind-kserve/v1` | no |

**Collections** (reading paths)

- **LLMInferenceService deep dive** — From one YAML to the resources it creates, how a request is routed, how to observe it and how it scales.
  1. [One Apply, Ten Resources — LLMInferenceService Anatomy](tutorials/llmisvc-anatomy/)
  2. [Journey of a Request — From Gateway to vLLM](tutorials/llmisvc-request-flow/)
  3. [Through the Scheduler's Eyes - Metric Observation](tutorials/llmisvc-monitoring/)

**By KServe version**

- **v0.20.0**: [inferencegraph-ensemble](tutorials/inferencegraph-ensemble/), [llmisvc-anatomy](tutorials/llmisvc-anatomy/), [llmisvc-monitoring](tutorials/llmisvc-monitoring/), [llmisvc-request-flow](tutorials/llmisvc-request-flow/)
- **v0.18.0**: [inferencegraph-ensemble](tutorials/inferencegraph-ensemble/), [llmisvc-anatomy](tutorials/llmisvc-anatomy/), [llmisvc-monitoring](tutorials/llmisvc-monitoring/), [llmisvc-request-flow](tutorials/llmisvc-request-flow/)

<!-- /tut -->

## Running tutorials locally (recommended)

**You install:** Docker (running, ~4 CPU / 16 GiB for it), git, curl and
Python 3.11+. Nothing else.

```bash skip
git clone -b stable https://github.com/Jooho/kserve-tutorials.git && cd kserve-tutorials
```

```bash skip
make setup      # the toolkit only: a .venv with Python packages
make doctor     # can this machine run the tutorials? (Docker, resources, platform)
make ui         # opens the browser
```

Tab completion for `./tut` (tutorial ids, tags, collections, versions) in your
shell: `eval "$(./tut completion)"` (zsh: run `autoload -U +X bashcompinit &&
bashcompinit` first). The UI terminal has it already.

Already using a kind cluster called `kind` for something else? Let the
tutorials use their own, once (remembered in `.tut.env`, not in git):

```bash skip
make config CLUSTER=tut
```

Pick a KServe version and a tutorial, then step through it like a notebook:
**▶ Next** (or Shift+Enter) runs the selected step and moves to the next one;
click any step to select it. The commands run in a terminal on your machine,
shown in the page, and every check turns green or red. No copy and paste.

The CLI tools a tutorial needs (kind, kubectl, helm, cloud-provider-kind) are
installed by the tutorial's first step, at the versions its environment pins,
into `.tools/` inside this repository. Nothing is installed system-wide and
your shell configuration is not changed.

`stable` is the last fully verified state (see [releases](../../releases));
`main` is where tutorials are being written.

## Reading a tutorial without the UI

1. Pick a tutorial for your KServe version (table above, or the site's
   "By KServe version" page).
2. Clone this repository. Tutorials reference files by path.
   ```bash skip
   git clone -b stable https://github.com/Jooho/kserve-tutorials.git && cd kserve-tutorials
   ```
3. Open `tutorials/<id>/README.md` and copy the commands in order. The first
   block prepares the cluster for you (see the tutorial's **Environment**).
   To try another tested version, `export KSERVE_VERSION=<version>` first.

Status labels: ✅ stable · 🚧 draft · ⚠️ deprecated (still works, being
replaced) · 🗄️ archived (kept for reference, not tested anymore).

Found a broken step? [Open an issue](../../issues/new?template=tutorial-broken.yml).

## Contributing

Most of the work here is done with an AI coding agent (Claude Code, Codex).
New here? [docs/getting-started.md](docs/getting-started.md) shows the steps.
Start your agent in a clone of this repository and paste a prompt from
[docs/prompts.md](docs/prompts.md) as its first message:

| You want to | Prompt |
|---|---|
| start a first session (the agent reads the docs, checks your machine, reports back) | [Build the context](docs/prompts.md#1-build-the-context) |
| move a tutorial from the legacy repository | [Migrate a tutorial](docs/prompts.md#2-migrate-a-tutorial) |
| write a new tutorial | [from tested work](docs/prompts.md#3a-new-tutorial-from-tested-work) · [from scratch](docs/prompts.md#3b-new-tutorial-from-scratch) |
| fix a failed CI run | [Fix a CI failure](docs/prompts.md#4-fix-a-ci-failure) |
| add a teaching page with diagrams (AI explainer) | [Make an explainer](docs/prompts.md#5-make-an-explainer) |

See [CONTRIBUTING.md](CONTRIBUTING.md). The design is described in
[RFC 0001](docs/rfc/0001-repository-structure.md).
