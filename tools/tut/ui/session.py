"""One interactive bash per tutorial, running on the user's machine.

The UI sends README blocks to this shell exactly as a reader would type them,
so variables and `cd` carry over between blocks. Each block is wrapped by the
`__tut_run` shell function, which prints invisible OSC markers when a block
starts and ends; the session strips them from the output and turns them into
block events (running / passed / failed) for the UI.

Execution semantics match the CI runner (tools/tut/runner.py):
  run     executed in the shell; failed if any command in it failed
  verify  executed in a subshell with `set -Eeo pipefail`; retried with retry=N delay=S
  cleanup executed like run
"""
from __future__ import annotations

import asyncio
import codecs
import fcntl
import os
import pty
import re
import shlex
import signal
import struct
import subprocess
import tempfile
import termios
from pathlib import Path
from typing import Callable

SHELLRC = Path(__file__).parent / "shellrc.sh"


def pick_bash() -> str:
    """Prefer a modern bash (macOS ships 3.2); TUT_BASH overrides."""
    if os.environ.get("TUT_BASH"):
        return os.environ["TUT_BASH"]
    for cand in ("/opt/homebrew/bin/bash", "/usr/local/bin/bash"):
        if os.access(cand, os.X_OK):
            return cand
    return "bash"


MARKER_RE = re.compile(r"\x1b\]777;tut;(start|end|ready);(\d+)(?:;(\d+))?\x07")
MARKER_PREFIX = "\x1b]777;"
# Result lines are written by the server, which is the only party that knows
# whether a block was stopped by the user (a command may exit 0 on Ctrl-C).
RESULT_TEXT = {
    "passed": "\x1b[32m✓ passed\x1b[0m\r\n",
    "failed": "\x1b[31m✗ failed (exit {rc})\x1b[0m\r\n",
    "stopped": "\x1b[33m■ stopped\x1b[0m\r\n",
}

RC_TEMPLATE = r"""
[ -f /etc/bash.bashrc ] && . /etc/bash.bashrc >/dev/null 2>&1
PS1='\[\e[36m\]tut:{tid}\[\e[0m\] \[\e[2m\]\W\[\e[0m\] $ '
. {shellrc}
cd {repo}
TUT_UI_DIR={tmpdir}
# Called as ` __tut_run <idx>`: a short line that cannot wrap, so the erase
# below removes it completely. The block's settings are in block-<idx>.args.
__tut_run() {{
  local idx=$1 role=run retry=1 delay=10 label="" rc=0 try
  local file="$TUT_UI_DIR/block-$idx.sh"
  . "$TUT_UI_DIR/block-$idx.args"
  printf '\e[1A\e[2K'
  printf '\e[2m── %s ──\e[0m\n' "$label"
  printf '\e]777;tut;start;%s\a' "$idx"
  for ((try=1; try<=retry; try++)); do
    if [ "$role" = verify ]; then
      ( set -Eeo pipefail; source "$file" ); rc=$?
    else
      __tut_err=0
      trap '__tut_err=$?' ERR
      source "$file"
      trap - ERR
      rc=$__tut_err
    fi
    [ "$rc" -eq 0 ] && break
    if [ "$try" -lt "$retry" ]; then
      printf '\e[33m… attempt %d/%d failed, retrying in %ss\e[0m\n' "$try" "$retry" "$delay"
      sleep "$delay"
    fi
  done
  printf '\e]777;tut;end;%s;%s\a' "$idx" "$rc"
}}
# The prompt ends with an invisible "ready" marker. Readline draws PS1 only
# after it has taken over the terminal, so once the UI sees the marker, text it
# types is read by readline instead of being echoed by the tty (PROMPT_COMMAND
# would be too early: it runs before readline starts).
PS1="$PS1\[\e]777;tut;ready;0\a\]"
"""


class ShellSession:
    def __init__(self, tid: str, repo: Path, kserve_version: str | None,
                 on_output: Callable[[str], None], on_event: Callable[[dict], None]):
        self.tid = tid
        self.repo = repo
        self.kserve_version = kserve_version
        self.on_output = on_output
        self.on_event = on_event
        self.tmp = Path(tempfile.mkdtemp(prefix=f"tut-ui-{tid}-"))
        self.proc: subprocess.Popen | None = None
        self.fd: int | None = None
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.pending = ""
        self.waiters: dict[int, asyncio.Future] = {}
        self.queue_task: asyncio.Task | None = None
        self.running: int | None = None
        self.stopped: set[int] = set()   # blocks the user interrupted
        self.prompt_ready: asyncio.Event | None = None
        self.scrollback: list[str] = []

    # ------------------------------------------------------------ lifecycle
    def start(self):
        rc = self.tmp / "rc.sh"
        rc.write_text(RC_TEMPLATE.format(tid=self.tid, repo=shlex.quote(str(self.repo)),
                                         shellrc=shlex.quote(str(SHELLRC)),
                                         tmpdir=shlex.quote(str(self.tmp))))
        env = {k: v for k, v in os.environ.items() if not k.startswith("TUT_")}
        env.update(TERM="xterm-256color", TUT_UI="1", HISTCONTROL="ignorespace")
        if self.kserve_version:
            env["KSERVE_VERSION"] = self.kserve_version
        else:
            env.pop("KSERVE_VERSION", None)
        self.prompt_ready = asyncio.Event()
        master, slave = pty.openpty()
        self.proc = subprocess.Popen(
            [pick_bash(), "--noprofile", "--rcfile", str(rc), "-i"],
            stdin=slave, stdout=slave, stderr=slave, cwd=self.repo, env=env,
            start_new_session=True, close_fds=True)
        os.close(slave)
        self.fd = master
        os.set_blocking(master, False)
        asyncio.get_running_loop().add_reader(master, self._read)
        self.on_event({"type": "session", "state": "started",
                       "kserve_version": self.kserve_version})

    def stop(self):
        self.cancel_queue()
        if self.fd is not None:
            try:
                asyncio.get_running_loop().remove_reader(self.fd)
            except Exception:
                pass
            os.close(self.fd)
            self.fd = None
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
        for f in self.waiters.values():
            if not f.done():
                f.set_result(130)

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    # ------------------------------------------------------------------ I/O
    def _read(self):
        try:
            data = os.read(self.fd, 65536)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""
        if not data:
            asyncio.get_running_loop().remove_reader(self.fd)
            self.on_event({"type": "session", "state": "exited"})
            return
        self._feed(self.decoder.decode(data))

    def _feed(self, text: str):
        text = self.pending + text
        self.pending = ""
        # Hold back an unfinished marker until the rest arrives.
        cut = text.rfind(MARKER_PREFIX)
        if cut != -1 and "\x07" not in text[cut:]:
            text, self.pending = text[:cut], text[cut:]
        out, pos = [], 0
        for m in MARKER_RE.finditer(text):
            out.append(text[pos:m.start()])
            pos = m.end()
            kind, idx = m.group(1), int(m.group(2))
            if kind == "ready":
                if self.prompt_ready:
                    self.prompt_ready.set()
                continue
            if kind == "start":
                self.running = idx
                self.on_event({"type": "block", "idx": idx, "state": "running"})
            else:
                rc = int(m.group(3) or 0)
                self.running = None
                if idx in self.stopped:
                    out.append(RESULT_TEXT["stopped"])
                    self._report_stopped(idx, echo=False)
                    continue
                state = "passed" if rc == 0 else "failed"
                out.append(RESULT_TEXT[state].format(rc=rc))
                self.on_event({"type": "block", "idx": idx, "state": state, "rc": rc})
                f = self.waiters.pop(idx, None)
                if f and not f.done():
                    f.set_result(rc)
        out.append(text[pos:])
        chunk = "".join(out)
        if chunk:
            self.scrollback.append(chunk)
            if len(self.scrollback) > 2000:
                self.scrollback = self.scrollback[-1000:]
            self.on_output(chunk)

    def write(self, data: str):
        if self.fd is not None:
            os.write(self.fd, data.encode())

    def resize(self, cols: int, rows: int):
        if self.fd is not None:
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    # ------------------------------------------------------------- running
    async def run_block(self, idx: int, role: str, code: str, attrs: dict, label: str = "") -> int:
        f = self.tmp / f"block-{idx}.sh"
        f.write_text(code + "\n")
        retry = int(attrs.get("retry", 1)) if role == "verify" else 1
        delay = int(attrs.get("delay", 10))
        fut = asyncio.get_running_loop().create_future()
        self.waiters[idx] = fut
        # wait until bash shows a prompt, so the command is not typed ahead
        try:
            await asyncio.wait_for(self.prompt_ready.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass  # e.g. a foreground program still running; type anyway
        self.prompt_ready.clear()
        # Ctrl-U clears anything half-typed at the prompt; the leading space keeps
        # the call out of the shell history.
        (self.tmp / f"block-{idx}.args").write_text(
            f"role={shlex.quote(role)} retry={retry} delay={delay} "
            f"label={shlex.quote(label or f'{role} block {idx}')}\n")
        self.write(f"\x15 __tut_run {idx}\n")
        return await fut

    def run_queue(self, blocks: list[dict], stop_on_fail: bool = True):
        self.cancel_queue()

        async def go():
            for b in blocks:
                self.on_event({"type": "block", "idx": b["idx"], "state": "queued"})
            for n, b in enumerate(blocks):
                rc = await self.run_block(b["idx"], b["role"], b["code"], b.get("attrs", {}),
                                          b.get("label", ""))
                if rc != 0 and stop_on_fail:
                    for rest in blocks[n + 1:]:
                        self.on_event({"type": "block", "idx": rest["idx"], "state": "idle"})
                    self.on_event({"type": "queue", "state": "stopped", "failed": b["idx"]})
                    return
            self.on_event({"type": "queue", "state": "done"})

        self.queue_task = asyncio.ensure_future(go())

    def cancel_queue(self):
        if self.queue_task and not self.queue_task.done():
            self.queue_task.cancel()
        self.queue_task = None

    def interrupt(self):
        """Ctrl-C: stop the queue and the running block. The block is reported as
        `stopped`, whatever exit code the interrupted command returns (`watch`
        exits 0, `sleep` 130, and bash may abort the wrapper without an end
        marker, so fall back to reporting it after a short wait)."""
        self.cancel_queue()
        self.write("\x03")
        self.on_event({"type": "queue", "state": "cancelled"})
        if self.running is None:
            return
        idx = self.running
        self.stopped.add(idx)
        asyncio.get_running_loop().call_later(1.5, self._report_stopped, idx)

    def _report_stopped(self, idx: int, echo: bool = True):
        if idx not in self.stopped:
            return
        self.stopped.discard(idx)
        if echo:
            self.on_output(RESULT_TEXT["stopped"])
        if self.running == idx:
            self.running = None
        self.on_event({"type": "block", "idx": idx, "state": "stopped", "rc": 130})
        f = self.waiters.pop(idx, None)
        if f and not f.done():
            f.set_result(130)
