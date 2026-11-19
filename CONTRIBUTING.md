# Contributing

Thanks for helping. This repository is maintained mostly by AI agents
following [AGENTS.md](AGENTS.md); people follow the same documents:

- **Writing or changing a tutorial:** [docs/authoring.md](docs/authoring.md)
- **Moving a tutorial from the legacy repository:** [docs/migration-guide.md](docs/migration-guide.md)
- **A CI run failed:** [docs/ci-playbook.md](docs/ci-playbook.md)
- **Tags, collections, owners:** [docs/authoring.md § Tags and collections](docs/authoring.md)
- **Releasing (`main` → `stable`):** [docs/release.md](docs/release.md)
- **Why it is built this way:** [RFC 0001](docs/rfc/0001-repository-structure.md)

Quick start:

```bash skip
make setup
cp -r tutorials/_template tutorials/<id>     # then edit tutorial.yaml and README.md
./tut sync && make check
make ui                                      # run it step by step
make help                                    # everything else
```
