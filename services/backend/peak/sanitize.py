"""Allowlist HTML sanitizer for imported item text (stems, passages, rationales).

Official exports carry HTML and MathML. Only structural, text and math tags survive;
scripts, styles, event handlers, and all but a few attributes are dropped.
"""
from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

ALLOWED = {
    "p", "br", "b", "i", "u", "em", "strong", "sub", "sup", "span", "div", "ul", "ol", "li", "blockquote",
    "table", "thead", "tbody", "tr", "th", "td", "caption", "figure", "figcaption", "img",
    "math", "mrow", "mi", "mn", "mo", "mtext", "msup", "msub", "msubsup", "mfrac", "msqrt", "mroot",
    "mover", "munder", "munderover", "mspace", "mfenced", "mtable", "mtr", "mtd", "semantics", "annotation",
}
VOID = {"br", "img", "mspace"}
DROP_CONTENT = {"script", "style", "iframe", "object", "embed"}
ATTRS = {"colspan", "rowspan", "alt", "src", "xmlns", "display", "mathvariant", "stretchy", "fence", "separators",
         "open", "close", "linethickness"}


# Inline raster images only. SVG is excluded on purpose: it can carry active content.
INLINE_IMAGE = re.compile(r"^data:image/(png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/=\s]+$")


def is_safe_src(value: str) -> bool:
    return bool(INLINE_IMAGE.match(value)) or value.startswith("asset:")


def _safe_src(value: str) -> bool:
    return is_safe_src(value)


class _Clean(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.skip += 1
            return
        if self.skip or tag not in ALLOWED:
            return
        kept = []
        for name, value in attrs:
            if name in ATTRS and value is not None and not name.startswith("on"):
                if name == "src" and not _safe_src(value):
                    continue
                kept.append(f' {name}="{escape(value, quote=True)}"')
        self.out.append(f"<{tag}{''.join(kept)}>")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in ALLOWED or tag in VOID:
            return
        if tag in self.stack:
            while self.stack:
                top = self.stack.pop()
                self.out.append(f"</{top}>")
                if top == tag:
                    break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(escape(data))

    def close(self):
        super().close()
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")


def sanitize_html(raw: str | None) -> str:
    if not raw:
        return ""
    parser = _Clean()
    parser.feed(raw)
    parser.close()
    return "".join(parser.out)
