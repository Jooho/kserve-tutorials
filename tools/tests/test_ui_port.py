"""./tut ui port: not 8080 (tutorials use it), the next free port by default,
and a port you asked for is used or refused, never silently swapped."""
from __future__ import annotations

import socket

import pytest

from tut.ui import server


def _hold(port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", port))
    s.listen(1)
    return s


def _free_block(n: int) -> int:
    """A start port with n free ports after it."""
    for start in range(20000, 60000, 50):
        if all(server._free(p) for p in range(start, start + n)):
            return start
    pytest.skip("no free port block")


def test_default_is_not_8080():
    assert server.DEFAULT_PORT != 8080


def test_default_port_is_used_when_free():
    start = _free_block(3)
    assert server.pick_port(start=start) == (start, None)


def test_busy_default_moves_to_the_next_free_port_and_says_so():
    start = _free_block(3)
    with _hold(start):
        port, note = server.pick_port(start=start)
    assert port == start + 1 and note == f"port {start} is in use, using {start + 1}"


def test_a_requested_port_is_never_swapped():
    start = _free_block(2)
    assert server.pick_port(start + 1) == (start + 1, None)
    with _hold(start + 1):
        with pytest.raises(server.PortError, match="in use"):
            server.pick_port(start + 1)


def test_all_tries_busy_is_an_error():
    start = _free_block(2)
    with _hold(start), _hold(start + 1):
        with pytest.raises(server.PortError):
            server.pick_port(start=start, tries=2)
