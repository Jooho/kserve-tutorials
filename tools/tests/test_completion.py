"""Tab completion for ./tut comes from the real argparse parser."""
from __future__ import annotations

import subprocess

from tut import cli
from tut.model import REPO_ROOT


def test_every_subcommand_is_offered_and_hidden_ones_are_not():
    parser = cli.build_parser()
    spa = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
    assert set(cli.complete([])) == {c for c in spa.choices if not c.startswith("_")}


def test_values_and_options():
    assert "llmisvc-anatomy" in cli.complete(["run"])
    assert "--twice" in cli.complete(["run", "llmisvc-anatomy"])
    assert cli.complete(["translation"]) == ["draft", "init", "mark", "status"]
    assert "ko" in cli.complete(["translation", "init", "llmisvc-anatomy"])
    assert "llmisvc" in cli.complete(["list", "--tag"])
    assert cli.complete(["list", "--status"]) == ["draft", "stable", "deprecated", "archived"]
    assert "v0.18.0" in cli.complete(["run", "llmisvc-anatomy", "--kserve-version"])
    assert cli.complete(["no-such-command"]) == []


def test_bash_function_completes_like_tab():
    script = (f'cd "{REPO_ROOT}"; source tools/tut-completion.bash; '
              'COMP_WORDS=(./tut translation in); COMP_CWORD=2; _tut_complete; echo "${COMPREPLY[*]}"')
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "init"
