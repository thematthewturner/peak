"""Turn stored (sanitized) item HTML into model-readable content blocks.

MathML is linearized (x^2, (a)/(b), sqrt(...)), inline PNG equation images become image blocks, and inline
SVG charts are passed as markup text (their text labels and shapes are readable). A naive tag strip would
turn <msup>x2</msup> into "x 2" and silently change the problem."""
from __future__ import annotations

import re
from html.parser import HTMLParser

VOID = {"br", "img", "mspace", "hr"}
BLOCK = {"p", "div", "br", "tr", "li", "table", "figure", "figcaption", "blockquote"}


class Node:
    __slots__ = ("tag", "attrs", "kids")

    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.kids = tag, dict(attrs or []), []


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].kids.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].kids.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].kids.append(data)


def build(html: str) -> Node:
    b = _Builder()
    b.feed(html or "")
    b.close()
    return b.root


def _markup(node) -> str:
    if isinstance(node, str):
        return node
    attrs = "".join(f' {k}="{v}"' for k, v in node.attrs.items())
    inner = "".join(_markup(k) for k in node.kids)
    return f"<{node.tag}{attrs}>{inner}</{node.tag}>"


def _kids(node, fn) -> list[str]:
    return [fn(k) for k in node.kids if not (isinstance(k, str) and not k.strip())]


def math(node) -> str:
    """Linearize a MathML subtree."""
    if isinstance(node, str):
        return re.sub(r"\s+", " ", node).strip()
    t, parts = node.tag, _kids(node, math)
    first = lambda i: parts[i] if i < len(parts) else ""  # noqa: E731
    if t == "msup":
        return f"{first(0)}^({first(1)})"
    if t == "msub":
        return f"{first(0)}_({first(1)})"
    if t == "msubsup":
        return f"{first(0)}_({first(1)})^({first(2)})"
    if t == "mfrac":
        return f"({first(0)})/({first(1)})"
    if t == "msqrt":
        return f"sqrt({''.join(parts)})"
    if t == "mroot":
        return f"root[{first(1)}]({first(0)})"
    if t in ("mover", "munder", "munderover"):
        return f"{first(0)}[{t[1:]}: {', '.join(parts[1:])}]"
    if t == "mfenced":
        return f"{node.attrs.get('open', '(')}{(node.attrs.get('separators') or ',')[:1].join(parts)}{node.attrs.get('close', ')')}"
    if t == "mtr":
        return ", ".join(parts)
    if t == "mtable":
        return "[" + "; ".join(parts) + "]"
    if t == "mspace":
        return " "
    if t == "annotation":
        return ""
    if t == "semantics":
        return parts[0] if parts else ""
    return "".join(parts) if t in ("mrow", "math", "mi", "mn", "mo", "mtext", "mtd") else " ".join(parts)


def render(node, imgs: list) -> str:
    if isinstance(node, str):
        return re.sub(r"[ \t\r\f\v]+", " ", node.replace("\n", " "))
    t = node.tag
    if t == "img":
        imgs.append(node.attrs.get("src", ""))
        return f"\x00IMG{len(imgs) - 1}\x00"
    if t == "svg":
        return "\n[SVG figure, as markup]\n" + _markup(node) + "\n"
    if t == "math":
        return " " + math(node) + " "
    inner = "".join(render(k, imgs) for k in node.kids)
    if t == "br":
        return "\n"
    if t == "li":
        return "\n- " + inner
    if t in ("td", "th"):
        return inner + " | "
    if t in BLOCK:
        return "\n" + inner + "\n"
    return inner


_DATA = re.compile(r"^data:image/(png|jpeg|jpg|gif|webp);base64,(.*)$", re.S)


def to_blocks(html: str) -> list[dict]:
    imgs: list[str] = []
    text = render(build(html), imgs)
    blocks: list[dict] = []

    def add_text(s):
        s = re.sub(r"\n\s*\n+", "\n", s).strip()
        if s:
            if blocks and blocks[-1]["type"] == "text":
                blocks[-1]["text"] += "\n" + s
            else:
                blocks.append({"type": "text", "text": s})

    for i, part in enumerate(re.split(r"\x00IMG(\d+)\x00", text)):
        if i % 2 == 0:
            add_text(part)
        else:
            m = _DATA.match(imgs[int(part)])
            if m:
                media = "image/jpeg" if m.group(1) == "jpg" else f"image/{m.group(1)}"
                blocks.append({"type": "image", "source": {"type": "base64", "media_type": media,
                                                           "data": re.sub(r"\s", "", m.group(2))}})
    return blocks


def plain(html: str) -> str:
    """Text only (images dropped); for length estimates."""
    return "\n".join(b["text"] for b in to_blocks(html) if b["type"] == "text")
