"""The UI shell session: blocks run in one real bash, state carries over, and
pass / fail / retry / stop-on-failure match the CI runner."""
from __future__ import annotations

import asyncio

import pytest

from test_rules import make_project
from tut.ui.session import ShellSession


@pytest.fixture(autouse=True)
def project_yaml(tmp_path):
    make_project(tmp_path)          # the session exports project.yaml's version_var


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

    try:
        asyncio.run(main())
    except (TimeoutError, asyncio.TimeoutError):
        raise AssertionError("shell session timed out; output so far:\n" + "".join(output)[-3000:])
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


def test_ui_shell_has_aliases_and_lazy_kubectl_completion(tmp_path):
    # A fake kubectl that only "appears" once a block puts it on PATH, like the
    # pinned kubectl after a tutorial's setup step. Its completion is loaded on
    # the first Tab (here: calling the stub), never before a prompt.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "kubectl").write_text(
        "#!/bin/sh\n[ \"$1\" = completion ] && echo '__start_kubectl() { :; }; complete -F __start_kubectl kubectl'\n")
    (bin_dir / "kubectl").chmod(0o755)
    blocks = [
        {"idx": 0, "role": "verify", "code": 'complete -p kubectl | grep -q __tut_lazy_complete\n'
                                              'alias k | grep -q kubectl\n'
                                              'alias kc | grep -q "set-context --current --namespace"\n'
                                              'complete -p kc | grep -q __tut_complete_kc'},
        {"idx": 1, "role": "run", "code": f'export PATH="{bin_dir}:$PATH"'},
        # first Tab: the stub loads the real completion and asks bash to retry (124)
        {"idx": 2, "role": "run", "code": 'rc=0; __tut_lazy_complete kubectl || rc=$?; test "$rc" -eq 124'},
        {"idx": 3, "role": "verify", "code": 'complete -p kubectl | grep -q __start_kubectl\n'
                                              'complete -p k | grep -q __start_kubectl'},
    ]
    final, out, _ = run_session(tmp_path, blocks)
    assert final == {0: "passed", 1: "passed", 2: "passed", 3: "passed"}, out


def test_internal_commands_never_show_on_screen(tmp_path):
    """Render the session through a real terminal emulator at a narrow width:
    the internal `__tut_run` call must not be visible, for many quick blocks."""
    import pyte
    cols, rows = 60, 400
    screen = pyte.Screen(cols, rows)
    stream = pyte.Stream(screen)
    events = []

    async def main():
        s = ShellSession("t", tmp_path, "v0.18.0", stream.feed, events.append)
        s.start()
        s.resize(cols, rows)
        s.run_queue([{"idx": i, "role": "run", "code": f"echo block-{i}"} for i in range(25)])
        await asyncio.wait_for(s.queue_task, 60)
        s.stop()

    asyncio.run(main())
    shown = "\n".join(line.rstrip() for line in screen.display)
    assert "block-24" in shown
    assert "__tut_run" not in shown, shown


def test_extra_shell_gets_the_tutorial_shells_variables_and_directory(tmp_path):
    """⧉ opens a terminal in its own tab: it starts with what the tutorial shell has
    (exported or set by a step) and its directory, and ↻ loads newer values."""
    import time
    work = tmp_path / "work"
    work.mkdir()
    out_extra = []

    async def main():
        t = ShellSession("t", tmp_path, "v0.18.0", lambda _: None, lambda _: None)
        t.start()
        t.run_queue([{"idx": 0, "role": "run",
                      "code": f'export NS=demo\nGATEWAY_URL="http://gw:80/a b"\ncd {work}'}], True)
        await asyncio.wait_for(t.queue_task, 20)
        env_file = t.tmp / "env.sh"
        for _ in range(100):                       # written at the next prompt
            if env_file.exists() and "GATEWAY_URL" in env_file.read_text():
                break
            await asyncio.sleep(0.05)
        x = ShellSession("t", tmp_path, "v0.18.0", out_extra.append, lambda _: None, env_from=env_file)
        x.start()
        await asyncio.wait_for(x.prompt_ready.wait(), 20)
        x.write('echo "[$NS|$GATEWAY_URL|$PWD]"\r')
        # a later step in the tutorial shell, then ↻ in the extra shell
        t.run_queue([{"idx": 1, "role": "run", "code": "export NS=changed"}], True)
        await asyncio.wait_for(t.queue_task, 20)
        await asyncio.sleep(0.5)
        x.write(" __tut_load_env\r")
        x.write('echo "[after:$NS]"\r')
        for _ in range(100):
            if "[after:changed]" in "".join(out_extra):
                break
            await asyncio.sleep(0.05)
        t.stop(); x.stop()

    asyncio.run(main())
    out = "".join(out_extra)
    assert f"[demo|http://gw:80/a b|{work}]" in out, out[-2000:]
    assert "[after:changed]" in out, out[-2000:]
    assert "shell:t" in out                              # its prompt says it is an extra shell


def test_shell_page_is_served_with_its_script():
    import asyncio as aio
    from aiohttp.test_utils import TestClient, TestServer
    from tut.model import REPO_ROOT
    from tut.ui.server import UI

    async def main():
        ui = UI(REPO_ROOT)
        async with TestClient(TestServer(ui.app())) as c:
            h = {"X-Tut-Token": ui.token}
            r = await c.get("/shell/llmisvc-anatomy", headers=h)
            assert r.status == 200 and "/static/shell.js" in await r.text()
            assert r.headers.get("Cache-Control") == "no-cache"
            assert (await c.get("/shell/no-such-tutorial", headers=h)).status == 404
            assert (await c.get("/shell/llmisvc-anatomy")).status == 403          # token required
    aio.run(main())


def test_teardown_runs_the_envs_teardown_script_in_the_tutorial_shell(tmp_path):
    """🗑 Teardown: the server runs envs/<env>/teardown.sh in the tutorial's shell
    (queued like a step, index -1); it never becomes a step state of the README."""
    import json
    from aiohttp.test_utils import TestClient, TestServer
    from test_rules import make_env, make_tut
    from tut.ui.server import UI

    make_env(tmp_path)
    marker = tmp_path / "torn-down"
    td = tmp_path / "envs" / "kind-x" / "v1" / "teardown.sh"
    td.write_text(f"#!/bin/sh\necho tearing down\ntouch {marker}\n")
    make_tut(tmp_path, "t")

    async def main():
        ui = UI(tmp_path)
        async with TestClient(TestServer(ui.app())) as c:
            ws = await c.ws_connect(f"/ws/t?token={ui.token}")
            await ws.send_str(json.dumps({"type": "start", "cols": 80, "rows": 24}))
            events = []
            async def until(pred, timeout=20):
                while True:
                    m = json.loads((await asyncio.wait_for(ws.receive(), timeout)).data)
                    events.append(m)
                    if pred(m):
                        return m
            await until(lambda m: m.get("type") == "session" and m.get("state") == "started")
            await ws.send_str(json.dumps({"type": "teardown"}))
            done = await until(lambda m: m.get("type") == "block" and m.get("idx") == -1
                               and m.get("state") in ("passed", "failed"))
            await ws.close()
            for s in ui.sessions.values():
                s.stop()
            return done, ui.block_states.get("t", {})

    done, states = asyncio.run(main())
    assert done["state"] == "passed" and marker.exists()
    assert -1 not in states
