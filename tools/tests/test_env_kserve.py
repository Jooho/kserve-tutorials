"""envs/kind-kserve/v1/setup.sh decisions, with fake kind / kubectl / docker and
a fake KServe installer (no cluster): reuse, add only what is missing, refuse
to mix modes, accept a cluster from the replaced kind-llmisvc/v1 profile."""
from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from tut.model import REPO_ROOT

ENV = "envs/kind-kserve/v1"


def _exe(path: Path, body: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(body))
    path.chmod(0o755)


@pytest.fixture
def sandbox(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / ENV, repo / ENV)
    _exe(repo / "tools" / "install-tools.sh", "exit 0\n")
    state = tmp_path / "state"
    state.mkdir()
    tools = dict(line.split("=", 1) for line in (repo / ENV / "tools.env").read_text().split("\n")
                 if "=" in line and not line.startswith("#"))
    ver = lambda k: tools[k].split()[0]
    # kind: a cluster exists when state/cluster does
    _exe(repo / ".tools" / "kind" / ver("KIND") / "kind", f'''
        S={state}
        case "$1 $2" in
          "get clusters") [ -f $S/cluster ] && cat $S/cluster ;;
          "delete cluster") rm -f $S/cluster $S/cm ;;
        esac
        exit 0
        ''')
    # kubectl: the tut-env ConfigMap lives in state/cm as "profile|version|types|mode|keda"
    _exe(repo / ".tools" / "kubectl" / ver("KUBECTL") / "kubectl", f'''
        S={state}
        args="$*"
        if [[ "$args" == *"get configmap tut-env"* ]]; then [ -f $S/cm ] && cat $S/cm || exit 1; exit 0; fi
        if [[ "$args" == *"create configmap tut-env"* ]]; then
          declare -A v
          for a in "$@"; do [[ "$a" == --from-literal=* ]] && {{ kv="${{a#--from-literal=}}"; v[${{kv%%=*}}]="${{kv#*=}}"; }}; done
          printf '%s|%s|%s|%s|%s' "${{v[profile]}}" "${{v[kserve_version]}}" "${{v[types]}}" "${{v[mode]}}" "${{v[keda]}}" > $S/cm
          exit 0
        fi
        [[ "$args" == *"get llminferenceserviceconfig"* ]] && exit 1
        [[ "$args" == "apply -f -" ]] && cat >/dev/null
        exit 0
        ''')
    _exe(repo / ".tools" / "helm" / ver("HELM") / "helm", "exit 0\n")
    # cloud-provider-kind "runs" while state/cpk exists; every start is counted
    _exe(repo / ".tools" / "cloud-provider-kind" / ver("CLOUD_PROVIDER_KIND") / "cloud-provider-kind",
         f'echo started >> {state}/cpk_starts; touch {state}/cpk\n')
    fakebin = tmp_path / "bin"
    _exe(fakebin / "docker", "exit 0\n")
    _exe(fakebin / "pgrep", f'[[ "$*" == *cloud-provider-kind* && -f {state}/cpk ]]\n')
    _exe(fakebin / "pkill", f'[[ "$*" == *cloud-provider-kind* ]] && rm -f {state}/cpk; '
                            f'echo killed >> {state}/cpk_kills\n')
    cache = tmp_path / "cache"
    src = cache / "kserve-v0.18.0"
    (src / ".git").mkdir(parents=True)
    _exe(src / "hack" / "kserve-install.sh",
         f'echo "$*" >> {state}/installs; echo "${{PLATFORM:-}}" > {state}/platform\n')
    _exe(src / "hack" / "setup" / "dev" / "manage.kind-with-registry.sh",
         f'echo "$KIND_CLUSTER_NAME" > {state}/cluster; echo created >> {state}/creates\n')

    def run(env_vars: dict, ok=True):
        env = {**os.environ, "PATH": f"{fakebin}:{os.environ['PATH']}", "KSERVE_VERSION": "v0.18.0",
               "TUT_CACHE": str(cache), "KIND_CLUSTER_NAME": "kind", **env_vars}
        env.pop("TUT_ENV_RECREATE", None)
        r = subprocess.run(["bash", str(repo / ENV / "setup.sh")], env=env, capture_output=True, text=True)
        assert (r.returncode == 0) == ok, r.stdout + r.stderr
        return r

    def read(name):
        p = state / name
        return p.read_text().strip().split("\n") if p.exists() else []

    return run, read, state


def test_new_cluster_with_options(sandbox):
    run, read, _ = sandbox
    run({"TUT_ENV_TYPES": "kserve", "TUT_ENV_MODE": "standard"})
    assert read("creates") == ["created"]
    assert read("installs") == ["--type kserve --kserve-version v0.18.0 --raw"]
    assert read("cm") == ["kind-kserve/v1|v0.18.0|kserve|standard|false"]


def test_installer_is_told_the_platform_is_kind_whatever_the_cluster_name(sandbox):
    # CI-010: KServe's installer only detects kind when the node name contains
    # "kind"; with KIND_CLUSTER_NAME=tut it skipped cloud-provider-kind.
    run, read, _ = sandbox
    run({"TUT_ENV_TYPES": "llmisvc", "KIND_CLUSTER_NAME": "tut"})
    assert read("platform") == ["kind"]


def test_new_cluster_restarts_cloud_provider_kind(sandbox):
    # CI-012: a cloud-provider-kind that outlived a deleted cluster did not serve
    # a new cluster with the same name; a new cluster gets a fresh process.
    run, read, state = sandbox
    (state / "cpk").touch()  # one is already running
    run({"TUT_ENV_TYPES": "llmisvc"})
    assert read("cpk_kills") == ["killed"] and read("cpk_starts") == ["started"]


def test_reuse_keeps_a_running_cloud_provider_kind_and_starts_a_missing_one(sandbox):
    run, read, state = sandbox
    run({"TUT_ENV_TYPES": "llmisvc"})
    run({"TUT_ENV_TYPES": "llmisvc"})          # reuse, process still running
    assert read("cpk_starts") == ["started"] and read("cpk_kills") == []
    (state / "cpk").unlink()                    # e.g. after a reboot
    run({"TUT_ENV_TYPES": "llmisvc"})
    assert read("cpk_starts") == ["started", "started"] and read("cpk_kills") == []


def test_same_request_reuses_without_installing(sandbox):
    run, read, _ = sandbox
    run({"TUT_ENV_TYPES": "kserve"})
    r = run({"TUT_ENV_TYPES": "kserve"})
    assert "reusing" in r.stdout and len(read("installs")) == 1 and read("creates") == ["created"]


def test_a_path_grows_one_cluster(sandbox):
    """kserve tutorial, then an llmisvc tutorial: llmisvc is added, no new cluster."""
    run, read, _ = sandbox
    run({"TUT_ENV_TYPES": "kserve"})
    r = run({"TUT_ENV_TYPES": "llmisvc"})
    assert "adding llmisvc" in r.stdout
    assert read("creates") == ["created"]
    assert read("installs")[-1] == "--type llmisvc --kserve-version v0.18.0"      # no mode flags for llmisvc
    assert read("cm") == ["kind-kserve/v1|v0.18.0|kserve,llmisvc|standard|false"]
    assert "reusing" in run({"TUT_ENV_TYPES": "llmisvc,kserve"}).stdout          # order does not matter


def test_modes_are_not_mixed(sandbox):
    run, read, _ = sandbox
    run({"TUT_ENV_TYPES": "kserve", "TUT_ENV_MODE": "standard"})
    r = run({"TUT_ENV_TYPES": "kserve", "TUT_ENV_MODE": "serverless"}, ok=False)
    assert "modes cannot be mixed" in r.stdout and len(read("installs")) == 1


def test_mode_only_matters_once_kserve_is_there(sandbox):
    run, read, _ = sandbox
    run({"TUT_ENV_TYPES": "llmisvc"})
    run({"TUT_ENV_TYPES": "kserve", "TUT_ENV_MODE": "serverless"})
    assert read("installs")[-1] == "--type kserve --kserve-version v0.18.0 --serverless"
    assert read("cm") == ["kind-kserve/v1|v0.18.0|kserve,llmisvc|serverless|false"]


def test_cluster_from_the_replaced_profile_counts_as_llmisvc(sandbox):
    run, read, state = sandbox
    (state / "cluster").write_text("kind")
    (state / "cm").write_text("kind-llmisvc/v1|v0.18.0|||")
    assert "reusing" in run({"TUT_ENV_TYPES": "llmisvc"}).stdout
    run({"TUT_ENV_TYPES": "kserve"})
    assert read("installs") == ["--type kserve --kserve-version v0.18.0 --raw"] and read("creates") == []


def test_foreign_or_other_version_cluster_stops(sandbox):
    run, read, state = sandbox
    (state / "cluster").write_text("kind")
    assert "not built by this profile" in run({}, ok=False).stdout       # no marker: someone's own cluster
    (state / "cm").write_text("kind-kserve/v1|v0.17.1|kserve|standard|false")
    assert "runs KServe v0.17.1" in run({}, ok=False).stdout
    assert read("installs") == []


def test_bad_options_are_rejected(sandbox):
    run, _, _ = sandbox
    assert "unknown type" in run({"TUT_ENV_TYPES": "kserve,foo"}, ok=False).stdout
    assert "KEDA needs mode standard" in run({"TUT_ENV_KEDA": "true", "TUT_ENV_MODE": "serverless"}, ok=False).stdout


def test_setup_step_passes_the_tutorials_options():
    from tut.model import load_tutorials
    from tut import generate
    ts = {t.id: t for t in load_tutorials(REPO_ROOT)}
    s = generate.render_setup(ts["llmisvc-anatomy"])
    assert 'TUT_ENV_TYPES=llmisvc TUT_ENV_MODE=standard TUT_ENV_KEDA=false "$REPO_ROOT/envs/kind-kserve/v1/setup.sh"' in s


def test_lint_T008_env_options(tmp_path):
    import yaml
    from tut import generate, lint
    for d in ("envs", "lib", "catalog", "schema"):
        shutil.copytree(REPO_ROOT / d, tmp_path / d)
    shutil.copy(REPO_ROOT / "project.yaml", tmp_path / "project.yaml")
    for p in (tmp_path / "catalog" / "collections").glob("*.yaml"):
        p.unlink()
    shutil.copytree(REPO_ROOT / "tutorials" / "_template", tmp_path / "tutorials" / "t")
    (tmp_path / ".github").mkdir()
    meta_path = tmp_path / "tutorials" / "t" / "tutorial.yaml"

    def errors(opts):
        m = yaml.safe_load(meta_path.read_text())
        m.update(id="t", namespace="t", env_options=opts)
        meta_path.write_text(yaml.safe_dump(m))
        generate.sync(tmp_path)
        return [f.message for f in lint.Linter(tmp_path).run() if f.code == "T008"]

    assert errors({"types": ["kserve", "llmisvc"], "mode": "standard", "keda": True}) == []
    assert any("'foo' is not one of" in e for e in errors({"types": ["kserve", "foo"]}))
    assert any("has no option 'gpu'" in e for e in errors({"gpu": True}))
    assert any("keda needs mode standard" in e for e in errors({"mode": "serverless", "keda": True}))
