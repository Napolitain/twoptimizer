"""Read effect sections and metadata from Honga detail pages, without scripts."""

from games.tw.multigame.html import Document, Node


def detail_record(html):
    document = Document(html).root
    detail = next(document.nodes("div", id="detail"), None)
    if detail is None or (
        not any(n.text() == "Effects" for n in detail.nodes("h3"))
        and not any(n.text() == "Effects" for n in detail.nodes("p"))
    ):
        detail = next(document.nodes("div", id="article_body"), None)
    if detail is None:
        raise ValueError("Source detail container missing")
    facts = _effect_facts(detail)
    metadata = _detail_metadata(document)
    title = next(document.nodes("h1"), None)
    contextual = _contextual_facts(facts)
    return {
        "name": title.text() if title else None,
        "facts": contextual,
        "explicit_no_effect": facts == ["No Effect"],
        "metadata": metadata,
    }


def _effect_facts(detail):
    facts, buffer, active = [], [], False
    for child in detail.children:
        if isinstance(child, Node) and (child.tag in {"h2", "h3"} or child.text() == "Effects"):
            if active:
                break
            active = child.text() == "Effects"
            continue
        if not active:
            continue
        if isinstance(child, Node) and child.tag == "table":
            break
        if isinstance(child, Node) and child.tag == "ul":
            facts.extend(n.text() for n in child.nodes("li"))
            continue
        if isinstance(child, Node) and child.tag == "br":
            _flush_fact(buffer, facts)
            buffer = []
        else:
            buffer.append(child.raw_text() if isinstance(child, Node) else child)
    _flush_fact(buffer, facts)
    if not active:
        raise ValueError("Source effect section missing")
    return facts


def _contextual_facts(facts):
    contextual, prefix = [], None
    for fact in facts:
        if fact.endswith("Edict:"):
            prefix = fact
        elif fact != "No Effect":
            contextual.append(prefix + " " + fact if prefix else fact)
    return contextual


def _detail_metadata(document):
    metadata = {}
    for table in document.nodes("table", **{"class": "table_stat"}):
        for row in table.nodes("tr"):
            cells = row.cells()
            if len(cells) == 2:
                metadata[cells[0].text()] = cells[1].text()
            elif len(cells) == 1:
                label = next(cells[0].nodes("p"), None)
                if label:
                    metadata[label.text()] = cells[0].text().removeprefix(label.text()).strip()
    return metadata


def _flush_fact(buffer, facts):
    text = " ".join("".join(buffer).split())
    if text:
        facts.append(text)
