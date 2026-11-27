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


# ---- inline SVG (charts, graphs) -------------------------------------------------------------
# Allowlist of shape/text elements. No script, style element, foreignObject, image, animation or use.
SVG_TAGS = {
    "svg", "g", "path", "line", "polyline", "polygon", "rect", "circle", "ellipse", "text", "tspan",
    "defs", "clippath", "marker", "title", "desc",
}
SVG_ATTRS = {
    "xmlns", "width", "height", "viewbox", "preserveaspectratio", "role", "aria-label", "aria-hidden",
    "d", "x", "y", "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry", "dx", "dy", "points", "transform",
    "fill", "fill-opacity", "fill-rule", "clip-rule", "stroke", "stroke-width", "stroke-dasharray",
    "stroke-dashoffset", "stroke-linecap", "stroke-linejoin", "stroke-opacity", "stroke-miterlimit", "opacity",
    "font-size", "font-family", "font-weight", "font-style", "text-anchor", "dominant-baseline",
    "alignment-baseline", "letter-spacing", "text-decoration", "clip-path", "marker-start", "marker-mid",
    "marker-end", "markerwidth", "markerheight", "refx", "refy", "orient", "markerunits", "clippathunits",
    "id", "style", "vector-effect", "shape-rendering",
}
SVG_STYLE_PROPS = {
    "fill", "fill-opacity", "stroke", "stroke-width", "stroke-dasharray", "stroke-opacity", "stroke-linecap",
    "stroke-linejoin", "opacity", "font-size", "font-family", "font-weight", "font-style", "text-anchor",
    "dominant-baseline", "display", "visibility", "letter-spacing",
}
_FRAGMENT_URL = re.compile(r"url\(\s*['\"]?#([A-Za-z][\w:.\-]{0,60})['\"]?\s*\)")
_ID = re.compile(r"^[A-Za-z][\w:.\-]{0,60}$")
ID_PREFIX = "pk-"  # keeps SVG ids from clobbering page ids or colliding across items


def _svg_value_ok(value: str) -> bool:
    v = value.lower()
    if any(bad in v for bad in ("javascript:", "expression(", "@import", "<", "&#", "\\")):
        return False
    if "url(" in v:
        return _FRAGMENT_URL.sub("", value).lower().find("url(") == -1  # only #fragment urls
    return True


def _svg_style(value: str) -> str:
    kept = []
    for decl in value.split(";"):
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop, val = prop.strip().lower(), val.strip()
        if prop in SVG_STYLE_PROPS and _svg_value_ok(val):
            kept.append(f"{prop}:{_prefix_urls(val)}")
    return ";".join(kept)


def _prefix_urls(value: str) -> str:
    return _FRAGMENT_URL.sub(lambda m: f"url(#{ID_PREFIX}{m.group(1)})", value)


def clean_svg_attrs(attrs) -> str:
    out = []
    for name, value in attrs:
        name = name.lower()
        if name not in SVG_ATTRS or value is None or len(value) > 20000:
            continue
        # style is validated declaration by declaration so one bad entry doesn't discard the safe ones.
        if name != "style" and not _svg_value_ok(value):
            continue
        if name == "id":
            if not _ID.match(value):
                continue
            value = ID_PREFIX + value
        elif name == "style":
            value = _svg_style(value)
            if not value:
                continue
        else:
            value = _prefix_urls(value)
        out.append(f' {name}="{escape(value, quote=True)}"')
    return "".join(out)


class _Clean(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.svg = 0  # depth inside an <svg>; the stricter SVG allowlists apply there
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "svg" or self.svg:
            if tag not in SVG_TAGS:
                return
            if tag == "svg":
                self.svg += 1
            self.out.append(f"<{tag}{clean_svg_attrs(attrs)}>")
            self.stack.append(tag)
            return
        if tag not in ALLOWED:
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
        if self.skip:
            return
        if self.svg and tag not in SVG_TAGS:
            return
        if tag in SVG_TAGS and tag in self.stack and (self.svg or tag == "svg"):
            while self.stack:
                top = self.stack.pop()
                self.out.append(f"</{top}>")
                if top == "svg":
                    self.svg -= 1
                if top == tag:
                    break
            return
        if tag not in ALLOWED or tag in VOID:
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
