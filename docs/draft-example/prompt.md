You turn a folder of TESTED work into a KServe tutorial in this repository's format.
Work in the repository at /home/user/kserve-tutorials.

Read first (fully):
- AGENTS.md and docs/authoring.md: the rules; lint enforces them
- build/draft/inferencegraph-ensemble/parts.md: envs, helper scripts and shared steps you can reuse
- tutorials/llmisvc-anatomy/: a finished tutorial to imitate (README.md, tutorial.yaml, manifests/)
- tutorials/inferencegraph-ensemble/: the scaffold to fill in (from tutorials/_template/)

The input (a copy; the author's original is not touched): build/draft/inferencegraph-ensemble/input/
Files: README.md, README_KO.md, combiner/Dockerfile, combiner/app.py, combiner/requirements.txt, data/inference_request.json, data/sample_data.json, docs/BLOG.md, docs/BLOG_KO.md, docs/TUTORIAL.md, docs/TUTORIAL_KO.md, images/architecture.svg, images/architecture_ko.svg, images/combiner.svg, images/combiner_ko.svg, images/inferencegraph.svg, images/inferencegraph_ko.svg, k8s/inferencegraph/housing-price-graph.yaml, k8s/inferenceservices/ensemble-combiner.yaml, k8s/inferenceservices/lightgbm-predictor.yaml, k8s/inferenceservices/xgboost-predictor.yaml, k8s/ingress/housing-price-ingress.yaml, k8s/pvc.yaml, models/lightgbm-predictor/model-settings.json, models/lightgbm-predictor/model.bst, models/xgboost-predictor/model-settings.json, models/xgboost-predictor/model.json, requirements.txt, scripts/1-1.setup_kind_cluster.sh, scripts/1-2.install_kserve.sh, scripts/1-3.train_models.sh, scripts/1-4.build_combiner.sh, scripts/1.prepare.sh, scripts/2.deploy.sh, scripts/cleanup.sh, scripts/test_inferencegraph.sh, scripts/train.py, scripts/upload_models.sh

Goal: tutorials/inferencegraph-ensemble/ becomes a tutorial a reader can follow and CI can run:
- README.md is the source: every command the reader runs is a ```bash run|verify|cleanup|skip block.
  Keep the commands the author tested. Change one only to meet a rule (safe to run twice,
  $KSERVE_VERSION instead of a hard-coded version, kubectl wait instead of sleep, no colors/echo
  decoration) and list every such change in the notes.
- Inline the steps of helper scripts; leave out decoration (color codes, banners, print functions).
- Cluster creation and KServe installation belong to an env (`env:`). If an env in parts.md fits,
  use it and drop those steps. If none fits, keep them as steps and say so in the notes.
- Use helper scripts and shared steps from parts.md where they do exactly what is needed.
- Kubernetes YAML goes to tutorials/inferencegraph-ensemble/manifests/ and is shown with <!-- tut:include manifests/x.yaml -->.
  Other files the steps need (code, data) go under tutorials/inferencegraph-ensemble/ too.
- Add verify blocks that prove each claim (retry=N delay=S where things take time) and a cleanup.
- Fill tutorial.yaml: title, summary, tags (from catalog/tags.yaml), kserve versions, requires,
  owners (keep the scaffold's), status: draft, langs: [en].
- Prose: short, explain what each step does and why, in English.

Rules for this run:
- Write ONLY under tutorials/inferencegraph-ensemble/ and build/draft/inferencegraph-ensemble/. Do not change anything else.
- The only command you may run is: ./tut _draftcheck inferencegraph-ensemble
  (runs ./tut sync, lint for this tutorial and a dry run; nothing touches a cluster).
  Run it after your edits and fix what it reports until it says "0 error(s)".
- When done, write build/draft/inferencegraph-ensemble/notes.md: what you built, every input command you changed or left
  out and why, which env/helpers/shared steps you used, and TODOs for the author (things you
  could not verify, a missing env, ...).
