# KServe Tutorials

Hands-on tutorials for [KServe](https://kserve.github.io/website/). Every
tutorial lists the KServe versions it was tested with, and CI runs each one
end to end against those versions every week. If a tutorial says it works,
CI recently checked that it does.

## Tutorials

<!-- tut:catalog -->

<!-- Generated from tutorials/*/tutorial.yaml by `./tut sync` — do not edit by hand. -->
| Tutorial | Status | Tested KServe | Tags | Environment | GPU |
|---|---|---|---|---|---|
| [One Apply, Ten Resources — LLMInferenceService Anatomy](tutorials/llmisvc-anatomy/) | 🚧 draft | v0.18.0 | `llmisvc` `gateway-api-inference-extension` `epp-scheduler` `vllm` `resources` `beginner` | `kind-llmisvc/v1` | no |

**Collections** (reading paths)

- **LLMInferenceService deep dive** — From one YAML to the resources it creates, how a request is routed, how to observe it and how it scales.
  1. [One Apply, Ten Resources — LLMInferenceService Anatomy](tutorials/llmisvc-anatomy/)

**By KServe version**

- **v0.18.0**: [llmisvc-anatomy](tutorials/llmisvc-anatomy/)

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

Already using a kind cluster called `kind` for something else? Let the
tutorials use their own, once (remembered in `.tut.env`, not in git):

```bash skip
make config CLUSTER=tut
```

Pick a KServe version and a tutorial, then press ▶ on each step (or ▶ Run
all): the commands run in a terminal on your machine, shown in the page, and
every check turns green or red. No copy and paste.

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

See [CONTRIBUTING.md](CONTRIBUTING.md). The design is described in
[RFC 0001](docs/rfc/0001-repository-structure.md).
