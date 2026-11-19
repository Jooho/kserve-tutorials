"""The UI shell session: blocks run in one real bash, state carries over, and
pass / fail / retry / stop-on-failure match the CI runner."""
from __future__ import annotations

import asyncio

from tut.ui.session import ShellSession


def run_session(tmp_path, blocks, stop_on_fail=True, timeout=20):
    events, output = [], []

    async def main():
        s = ShellSession("t", tmp_path, "v0.18.0", output.append, events.append)
        s.start()
        s.run_queue(blocks, stop_on_fail)
        try:
            await asyncio.wait_for(s.queue_task, timeout)
        finally:
            s.stop()

    asyncio.run(main())
    final = {e["idx"]: e["state"] for e in events if e["type"] == "block"}
    return final, "".join(output), events


def test_state_carries_over_and_failure_stops_queue(tmp_path):
    marker = tmp_path / "ready"
    blocks = [
        {"idx": 0, "role": "run", "code": 'X=42; cd /tmp; echo "kserve=$KSERVE_VERSION"'},
        {"idx": 1, "role": "verify", "code": 'test "$X" = 42 && test "$PWD" = /tmp'},
        {"idx": 2, "role": "verify", "attrs": {"retry": "3", "delay": "0"},
         "code": f'[ -f {marker} ] || {{ touch {marker}; false; }}'},
        {"idx": 3, "role": "verify", "code": "false\necho never-printed"},
        {"idx": 4, "role": "run", "code": "echo not-reached"},
    ]
    final, out, events = run_session(tmp_path, blocks)
    assert final == {0: "passed", 1: "passed", 2: "passed", 3: "failed", 4: "idle"}
    assert "kserve=v0.18.0" in out
    assert "never-printed" not in out           # verify stops at the first failing command
    assert "not-reached" not in out
    assert "✗ failed (exit 1)" in out and "── verify" in out
    assert {"type": "queue", "state": "stopped", "failed": 3} in events


def test_run_block_fails_if_any_command_fails(tmp_path):
    final, _, _ = run_session(tmp_path, [{"idx": 0, "role": "run", "code": "false\ntrue"}])
    assert final == {0: "failed"}


def test_markers_are_not_shown(tmp_path):
    _, out, _ = run_session(tmp_path, [{"idx": 0, "role": "run", "code": "echo hi"}])
    assert "\x1b]777" not in out and "hi" in out


def test_ui_shell_has_aliases_and_lazy_kubectl_completion(tmp_path, monkeypatch):
    # A fake kubectl that only "appears" once a block puts it on PATH, like the
    # pinned kubectl after a tutorial's setup step.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "kubectl").write_text(
        "#!/bin/sh\n[ \"$1\" = completion ] && echo '__start_kubectl() { :; }; __tut_fake_loaded=yes'\n")
    (bin_dir / "kubectl").chmod(0o755)
    blocks = [
        {"idx": 0, "role": "run", "code": f'export PATH="{bin_dir}:$PATH"'},
        # the prompt shown after block 0 loads the completion before block 1 runs
        {"idx": 1, "role": "verify", "code": 'test "$__tut_fake_loaded" = yes\n'
                                              'alias k | grep -q kubectl\n'
                                              'alias kc | grep -q "set-context --current --namespace"\n'
                                              'complete -p k | grep -q __start_kubectl\n'
                                              'complete -p kc | grep -q __tut_complete_kc'},
    ]
    final, out, _ = run_session(tmp_path, blocks)
    assert final == {0: "passed", 1: "passed"}, out
