"""Make README HTML safe to show in the local UI.

The UI page holds the token, so a script in a README could call the API and
type into the tutorial shell just by being opened (a PR branch under review,
for example). Markdown allows raw HTML, so the rendered page is rebuilt from an
allowlist: known tags and attributes only, links and images with safe URLs,
everything else dropped (`<script>` and `<style>` with their content). The
Content-Security-Policy set by the server is the second line of defence.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

TAGS = {
    "a", "abbr", "b", "blockquote", "br", "code", "dd", "del", "details", "div", "dl", "dt",
    "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "ins", "kbd", "li", "mark",
    "ol", "p", "picture", "pre", "q", "s", "samp", "small", "source", "span", "strong", "sub",
    "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul", "var",
}
VOID = {"br", "hr", "img", "source"}
# Removed together with everything inside them.
DROP_WITH_CONTENT = {"script", "style", "template", "noscript", "textarea", "title", "xmp",
                     "iframe", "object", "embed", "svg", "math", "select"}
GLOBAL_ATTRS = {"id", "class", "title", "lang", "dir", "align"}
ATTRS = {
    "a": {"href", "name"},
    "img": {"src", "alt", "width", "height"},
    "source": {"srcset", "media", "type"},
    "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan", "scope"},
    "details": {"open"},
    "ol": {"start", "type"},
    "div": {"data-idx"},            # the UI's block placeholders: <div class="tut-block" data-idx="3">
}
URL_ATTRS = {"href", "src", "srcset"}
SAFE_URL = re.compile(r"^(?:https?:|mailto:|#|/|\.{0,2}/|[^:/?#]+(?:[/?#]|$))", re.I)


def safe_url(value: str) -> bool:
    """Relative paths, #anchors and http(s)/mailto; never javascript:, data:, ..."""
    v = re.sub(r"[\x00-\x20]+", "", html.unescape(value))   # browsers ignore these in schemes
    return bool(SAFE_URL.match(v))


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0                     # inside a DROP_WITH_CONTENT element
        self.skip_tag: list[str] = []

    def handle_starttag(self, tag, attrs):
        if self.skip:
            if tag in DROP_WITH_CONTENT:
                self.skip += 1
                self.skip_tag.append(tag)
            return
        if tag in DROP_WITH_CONTENT:
            self.skip, self.skip_tag = 1, [tag]
            return
        if tag not in TAGS:
            return                         # the tag goes, its text stays
        allowed = GLOBAL_ATTRS | ATTRS.get(tag, set())
        kept = []
        for name, value in attrs:
            name = name.lower()
            if name not in allowed or name.startswith("on"):
                continue
            value = "" if value is None else value
            if name in URL_ATTRS and not all(safe_url(u.strip().split(" ")[0])
                                            for u in value.split(",") if u.strip()):
                continue
            kept.append(f' {name}="{html.escape(value, quote=True)}"')
        self.out.append(f"<{tag}{''.join(kept)}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and tag in TAGS and not self.skip:
            self.out.append(f"</{tag}>")

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip_tag[-1]:
                self.skip_tag.pop()
                self.skip -= 1
            return
        if tag in TAGS and tag not in VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    # comments, <!DOCTYPE>, processing instructions: dropped
    def handle_comment(self, data):
        pass


def clean(fragment: str) -> str:
    """The same HTML with only allowlisted tags, attributes and URLs."""
    c = _Cleaner()
    c.feed(fragment)
    c.close()
    return "".join(c.out)
