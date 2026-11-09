"""Replayable factual tables from a pinned public historical Assembly Kit export."""

import hashlib
import re
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree

PIN = "31020c8a75f8a08f83abe5410680a309d58475f1"
REPOSITORY = "https://github.com/ZadesSC/tt3k_dw9_dave"
RAW_BASE = f"https://raw.githubusercontent.com/ZadesSC/tt3k_dw9_dave/{PIN}/db/"
RULESET = "Historical vanilla 1.2.0 public Assembly Kit reference (190 CE)"


class SourceArchive:
    """Download bounded public XML; retain only factual table fields in snapshots."""

    def __init__(self, cache: Path, offline: bool = False):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        revision = self.cache / ".source-revision"
        if revision.exists() and revision.read_text().strip() != PIN:
            raise ValueError("Reference cache belongs to a different source revision")
        if not revision.exists():
            if any(self.cache.glob("*.xml")):
                raise ValueError("Reference cache has no source revision; use a fresh cache")
            revision.write_text(PIN + "\n")
        self.offline = offline
        self.records: dict[str, dict[str, str | int]] = {}

    def table(self, name: str) -> list[dict[str, str]]:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError(f"Invalid source table name: {name}")
        url = f"{RAW_BASE}{name}.xml"
        path = self.cache / f"{name}.xml"
        if not path.exists():
            self._download(url, path)
        raw = path.read_bytes()
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("Unexpected XML declarations in reference table")
        root = ElementTree.fromstring(raw)
        if root.tag != "dataroot":
            raise ValueError(f"Invalid Assembly Kit table: {name}")
        if any(child.tag not in {name, "edit_uuid"} for child in root):
            raise ValueError(f"Unexpected rows in Assembly Kit table: {name}")
        self.records[url] = {
            "url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        return [{column.tag: column.text or "" for column in row} for row in root.findall(name)]

    def _download(self, url: str, path: Path) -> None:
        if self.offline:
            raise FileNotFoundError(f"Missing offline source: {url}")
        request = Request(url, headers={"User-Agent": "twoptimizer-data-import/1.0"})
        with urlopen(request, timeout=45) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("Reference table exceeds size limit")
        path.write_bytes(raw)
