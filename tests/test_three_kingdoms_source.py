"""Pinned public reference ingestion must remain inspectable and fail closed."""

import hashlib
from io import BytesIO
from urllib.error import URLError

import pytest

from games.tw.three_kingdoms import source


def test_offline_table_preserves_fields_and_hashes_exact_bytes(tmp_path, monkeypatch):
    archive = source.SourceArchive(tmp_path, offline=True)
    raw = (
        b'<?xml version="1.0" encoding="utf-8"?>\n<dataroot>'
        b"<buildings><key>city</key><amount>-15</amount><empty/>"
        b"<name>&#35377;&#26124;</name></buildings></dataroot>"
    )
    (archive.cache / "buildings.xml").write_bytes(raw)
    monkeypatch.setattr(source, "urlopen", lambda *a, **k: pytest.fail("Offline network access"))
    assert archive.table("buildings") == [
        {"key": "city", "amount": "-15", "empty": "", "name": "許昌"}
    ]
    record = archive.records[source.RAW_BASE + "buildings.xml"]
    assert record["sha256"] == hashlib.sha256(raw).hexdigest()
    assert record["bytes"] == len(raw)
    assert isinstance(record["url"], str)
    assert source.PIN in record["url"]


def test_offline_missing_table_never_becomes_an_empty_catalog(tmp_path):
    archive = source.SourceArchive(tmp_path, offline=True)
    with pytest.raises(FileNotFoundError, match="Missing offline source"):
        archive.table("absent")
    assert not archive.records


@pytest.mark.parametrize("name", ["../secrets", "table.xml", "a/b", "A", "", "a?x=1"])
def test_source_table_names_cannot_escape_the_pinned_archive(tmp_path, name):
    archive = source.SourceArchive(tmp_path, offline=True)
    with pytest.raises(ValueError, match="Invalid source table name"):
        archive.table(name)


@pytest.mark.parametrize(
    "raw",
    [
        b"<html><body>temporarily unavailable</body></html>",
        b"<dataroot><different_table><key>city</key></different_table></dataroot>",
        b'<!DOCTYPE dataroot [<!ENTITY x SYSTEM "file:///etc/passwd">]><dataroot/>',
        b"<!ENTITY x 'unexpected'><dataroot/>",
    ],
)
def test_non_reference_responses_are_rejected(tmp_path, raw):
    archive = source.SourceArchive(tmp_path, offline=True)
    (archive.cache / "buildings.xml").write_bytes(raw)
    with pytest.raises(ValueError):
        archive.table("buildings")
    assert not archive.records


def test_online_download_uses_the_pinned_url_and_can_be_replayed(tmp_path, monkeypatch):
    raw = b"<dataroot><buildings><key>farm</key></buildings></dataroot>"
    requests = []

    def download(request, timeout):
        requests.append((request.full_url, timeout))
        return BytesIO(raw)

    monkeypatch.setattr(source, "urlopen", download)
    archive = source.SourceArchive(tmp_path)
    assert archive.table("buildings") == [{"key": "farm"}]
    assert requests == [(source.RAW_BASE + "buildings.xml", 45)]
    replay = source.SourceArchive(tmp_path, offline=True)
    assert replay.table("buildings") == [{"key": "farm"}]
    assert replay.records == archive.records
    assert len(requests) == 1


def test_failed_download_does_not_publish_a_source_file(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise URLError("unavailable")

    monkeypatch.setattr(source, "urlopen", unavailable)
    archive = source.SourceArchive(tmp_path)
    with pytest.raises(URLError):
        archive.table("buildings")
    assert not (archive.cache / "buildings.xml").exists()
    assert not archive.records


def test_overlarge_download_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "urlopen", lambda *a, **k: BytesIO(b"x" * (16 * 1024**2 + 1)))
    archive = source.SourceArchive(tmp_path)
    with pytest.raises(ValueError, match="size limit"):
        archive.table("buildings")
    assert not (archive.cache / "buildings.xml").exists()


def test_reference_cache_cannot_silently_mix_revisions(tmp_path):
    (tmp_path / ".source-revision").write_text("another-revision\n")
    with pytest.raises(ValueError, match="different source revision"):
        source.SourceArchive(tmp_path)
    assert (tmp_path / ".source-revision").read_text() == "another-revision\n"


def test_legacy_unversioned_tables_require_a_fresh_cache(tmp_path):
    raw = b"<dataroot/>"
    (tmp_path / "buildings.xml").write_bytes(raw)
    with pytest.raises(ValueError, match="no source revision"):
        source.SourceArchive(tmp_path)
    assert not (tmp_path / ".source-revision").exists()
    assert (tmp_path / "buildings.xml").read_bytes() == raw


def test_legitimate_empty_table_with_editor_metadata_remains_empty(tmp_path):
    archive = source.SourceArchive(tmp_path, offline=True)
    (archive.cache / "empty_table.xml").write_bytes(
        b"<dataroot><edit_uuid>id</edit_uuid></dataroot>"
    )
    assert archive.table("empty_table") == []
    size = archive.records[source.RAW_BASE + "empty_table.xml"]["bytes"]
    assert isinstance(size, int)
    assert size > 0
