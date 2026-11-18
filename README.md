# KServe Tutorials

Hands-on tutorials for [KServe](https://kserve.github.io/website/). Every
tutorial lists the KServe versions it was tested with, and CI runs each one
end to end against those versions every week. If a tutorial says it works,
CI recently checked that it does.

## Tutorials

<!-- tut:catalog -->

<!-- Generated from tutorials/*/tutorial.yaml by `./tut sync` — do not edit by hand. -->
| Tutorial | Status | Tested KServe | Environment | GPU |
|---|---|---|---|---|
| [One Apply, Ten Resources — LLMInferenceService Anatomy](tutorials/llmisvc-anatomy/) | 🚧 draft | v0.18.0 | `kind-llmisvc/v1` | no |

**By KServe version**

- **v0.18.0**: [llmisvc-anatomy](tutorials/llmisvc-anatomy/)

<!-- /tut -->

## Using a tutorial

1. Pick a tutorial for your KServe version (table above, or the site's
   "By KServe version" page).
2. Clone this repository. Tutorials reference files by path.
   ```bash skip
   git clone https://github.com/Jooho/kserve-tutorials.git && cd kserve-tutorials
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
