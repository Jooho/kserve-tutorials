"""The local UI never runs script that comes from a README (backlog B16).

A README can contain raw HTML; the UI page holds the token, so a script there
could drive the API and the tutorial shell just by being opened (an untrusted
branch under review). The rendered HTML is cleaned, and a CSP forbids inline
script as a second line of defence."""
from __future__ import annotations

import asyncio

import pytest

from test_rules import GOOD_README, make_env, make_tut
from tut.ui.sanitize import clean, safe_url

ATTACKS = [
    '<script>fetch("/api/sync")</script>',
    '<img src="x" onerror="alert(1)">',
    '<a href="javascript:alert(1)">x</a>',
    '<a href="  JaVa\tScript:alert(1)">x</a>',
    '<a href="&#106;avascript:alert(1)">x</a>',
    '<iframe src="https://evil.example"></iframe>',
    '<svg onload="alert(1)"><circle/></svg>',
    '<form action="/api/sync" method="post"><button>go</button></form>',
    '<meta http-equiv="refresh" content="0;url=https://evil.example">',
    '<style>body{display:none}</style>',
    '<object data="x.swf"></object><embed src="x.swf">',
    '<div style="background:url(javascript:alert(1))" onclick="x()">t</div>',
    '<img src="data:text/html;base64,PHNjcmlwdD4=">',
    '<base href="https://evil.example/">',
    '<p>ok</p><script>/*</p>*/alert(1)</script>',
]


@pytest.mark.parametrize("attack", ATTACKS)
def test_nothing_that_can_run_survives(attack):
    out = clean(attack).lower()
    for bad in ("<script", "javascript", "onerror", "onload", "onclick", "<iframe", "<svg",
                "<form", "<meta", "<style", "<object", "<embed", "style=", "data:text", "<base",
                "alert("):
        assert bad not in out, (attack, out)


def test_what_tutorials_use_is_kept():
    src = ('<details open><summary>More</summary><p>Text <code>a&lt;b</code></p></details>'
           '<table><tr><th colspan="2">h</th></tr><tr><td>1</td><td>2</td></tr></table>'
           '<img src="images/arch.svg" alt="Architecture" width="600">'
           '<a href="../other/" title="t">other</a> <a href="https://kserve.github.io/">KServe</a>'
           '<a href="#step-2">step 2</a><br><kbd>Ctrl</kbd>'
           '<div class="tut-block" data-idx="3"></div>')
    out = clean(src)
    for keep in ('<details open="">', "<summary>More</summary>", "<code>a&lt;b</code>",
                 '<th colspan="2">', '<img src="images/arch.svg" alt="Architecture" width="600">',
                 '<a href="../other/" title="t">', '<a href="https://kserve.github.io/">',
                 '<a href="#step-2">', "<br>", "<kbd>Ctrl</kbd>",
                 '<div class="tut-block" data-idx="3"></div>'):
        assert keep in out, (keep, out)


def test_text_is_escaped_and_unknown_tags_keep_their_text():
    assert clean("<blink>hi & bye</blink>") == "hi &amp; bye"
    assert clean("<p>1 &lt; 2</p>") == "<p>1 &lt; 2</p>"


@pytest.mark.parametrize("url,ok", [
    ("images/a.png", True), ("./a.png", True), ("../x/", True), ("/files/x", True),
    ("#anchor", True), ("https://x.y/", True), ("mailto:a@b.c", True), ("a.png", True),
    ("javascript:alert(1)", False), ("data:image/png;base64,AA", False), ("vbscript:x", False),
    ("java\nscript:x", False), ("&#106;avascript:x", False),
])
def test_safe_url(url, ok):
    assert safe_url(url) is ok


def test_rendered_page_is_clean_and_every_response_has_a_csp(tmp_path):
    from aiohttp.test_utils import TestClient, TestServer
    from tut.ui.server import UI
    make_env(tmp_path)
    evil = GOOD_README.replace("```bash cleanup", '<img src="x" onerror="fetch(\'/api/sync\')">\n'
                               '<script>alert(1)</script>\n\n```bash cleanup')
    make_tut(tmp_path, "t", evil)
    (tmp_path / "tutorials" / "t" / "page.svg").write_text('<svg onload="alert(1)"/>')

    async def main():
        ui = UI(tmp_path)
        async with TestClient(TestServer(ui.app())) as c:
            h = {"X-Tut-Token": ui.token}
            d = await (await c.get("/api/tutorials/t", headers=h)).json()
            page = await c.get("/", headers=h)
            svg = await c.get("/files/tutorials/t/page.svg", headers=h)
            denied = await c.get("/api/tutorials")          # no token: 403, still with the policy
            return d["html"], page.headers, svg.headers, denied
    html, page, svg, denied = asyncio.run(main())
    assert "onerror" not in html and "<script" not in html and 'src="/files/tutorials/t/x"' in html
    assert "script-src 'self'" in page["Content-Security-Policy"]
    assert "unsafe-inline" not in page["Content-Security-Policy"].split("script-src")[1].split(";")[0]
    assert svg["Content-Security-Policy"].startswith("sandbox")
    assert denied.status == 403 and "Content-Security-Policy" in denied.headers


def test_ui_pages_have_no_inline_script():
    """The CSP allows no inline script, so the pages must not need any."""
    import re
    from tut.ui.server import STATIC
    for page in ("index.html", "shell.html"):
        text = (STATIC / page).read_text()
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", text), page
        assert not re.search(r"\son[a-z]+=", text), page
