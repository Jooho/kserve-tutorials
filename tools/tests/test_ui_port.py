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


def test_site_server_serves_the_built_site_on_localhost_only(tmp_path):
    """make site-run / ./tut site --serve: build/site over HTTP, this machine only."""
    import threading
    import urllib.request
    from tut import site

    (tmp_path / "index.html").write_text("<h1>tutorials</h1>")
    port = _free_block(1)
    httpd = site.make_server(tmp_path, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        assert httpd.server_address[0] == "127.0.0.1"
        assert b"<h1>tutorials</h1>" in urllib.request.urlopen(f"http://127.0.0.1:{port}/").read()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_site_serve_needs_a_built_site(tmp_path):
    from tut import site
    with pytest.raises(FileNotFoundError):
        site.serve(tmp_path, open_browser=False)
    assert site.SITE_PORT not in (8000, 8080)
