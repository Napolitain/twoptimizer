"""Explicit, isolated engine dependencies for arithmetic examples."""

import pytest

from games.tw.attila.context import AttilaContext
from tests.support.rome2 import tiny_catalog


@pytest.fixture
def context() -> AttilaContext:
    return AttilaContext(fertility=2)


@pytest.fixture
def tiny():
    return tiny_catalog()


@pytest.fixture
def public_source(tmp_path, monkeypatch):
    from games.hoi4.data_pipeline import public_import
    from tests.support.hoi4 import make_public_source, source_git

    root = make_public_source(tmp_path / "source")
    monkeypatch.setattr(public_import, "SOURCE_REVISION", source_git(root, "rev-parse", "HEAD"))
    return root
