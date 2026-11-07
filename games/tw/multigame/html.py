"""Small non-executing HTML reader for the public reference tables."""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: object = None

    def nodes(self, tag=None, **attrs):
        for child in self.children:
            if not isinstance(child, Node):
                continue
            if (tag is None or child.tag == tag) and all(
                child.attrs.get(k) == v for k, v in attrs.items()
            ):
                yield child
            yield from child.nodes(tag, **attrs)

    def text(self):
        return " ".join(self.raw_text().split())

    def raw_text(self):
        return "".join(c.raw_text() if isinstance(c, Node) else c for c in self.children)

    def lines(self):
        return [" ".join(line.split()) for line in self.raw_text().splitlines() if line.strip()]

    def cells(self):
        return [c for c in self.children if isinstance(c, Node) and c.tag in {"th", "td"}]


class Document(HTMLParser):
    VOID = frozenset(
        {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
    )

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag == "br":
            self.stack[-1].children.append("\n")
        elif tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                if tag in {"p", "li"}:
                    self.stack[-1].children.append("\n")
                return

    def handle_data(self, data):
        if not any(n.tag in {"script", "style"} for n in self.stack):
            self.stack[-1].children.append(data)


def number(value):
    value = value.strip().replace(",", "").replace("\N{MINUS SIGN}", "-")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        raise ValueError(f"Not a source number: {value!r}")
    return float(value) if "." in value else int(value)
