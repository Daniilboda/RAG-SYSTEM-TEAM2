"""Проверка шага 8: паспорт снимка."""

from __future__ import annotations

import json
from pathlib import Path

from rag_common.mdd.manifest import FETCHED_AT
from rag_common.mdd.mdd import ARCHIVE_SHA256
from rag_common.mdd.snapshot_info import ADAPTER_VERSION, write_snapshot_info

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "cache" / "multidoc2dial.zip"
PAGE = ROOT / "data" / "snapshots" / "mdd_v1" / "pages" / "0a6f1ad6-6a7d-5462-abe5-516ceca3c4bb.txt"


def test_snapshot_info_counts_and_archive_hash(tmp_path: Path) -> None:
    """488 документов, сумма архива совпадает с шагом 2, txt не меняется."""
    before = PAGE.read_bytes()
    info_path = tmp_path / "snapshot_info.json"
    payload = write_snapshot_info(ARCHIVE, info_path)
    assert payload["schema_version"] == "k1.v1"
    assert payload["adapter_version"] == ADAPTER_VERSION
    assert payload["archive_sha256"] == ARCHIVE_SHA256
    assert payload["document_count"] == 488
    assert payload["created_at"] == FETCHED_AT
    assert json.loads(info_path.read_text(encoding="utf-8")) == payload
    assert PAGE.read_bytes() == before

    first = info_path.read_bytes()
    write_snapshot_info(ARCHIVE, info_path)
    assert info_path.read_bytes() == first
