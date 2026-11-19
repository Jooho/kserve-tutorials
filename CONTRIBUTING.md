# Contributing

Thanks for helping. This repository is maintained mostly by AI agents
following [AGENTS.md](AGENTS.md); people follow the same documents:

- **Writing or changing a tutorial:** [docs/authoring.md](docs/authoring.md)
- **Moving a tutorial from the legacy repository:** [docs/migration-guide.md](docs/migration-guide.md)
- **A CI run failed:** [docs/ci-playbook.md](docs/ci-playbook.md)
- **Why it is built this way:** [RFC 0001](docs/rfc/0001-repository-structure.md)

Quick start:

```bash skip
python3 -m pip install -r tools/requirements.txt
cp -r tutorials/_template tutorials/<id>     # then edit tutorial.yaml and README.md
./tut sync && ./tut lint
./tut ui                                     # run it step by step
```
