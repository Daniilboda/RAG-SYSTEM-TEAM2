"""Проверка шага 3 нарезки: документ собран из страницы, разделов и описи."""

from __future__ import annotations

import hashlib
from pathlib import Path

from preprocessing.chunk_document import load_chunk_documents

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "snapshots" / "mdd_v1"
KNOWN_ID = "0a6f1ad6-6a7d-5462-abe5-516ceca3c4bb"
KNOWN_TITLE = "How Aid Is Calculated | Federal Student Aid#1"


def test_text_matches_page_and_title_comes_from_manifest() -> None:
    """Текст совпадает с файлом в pages/. Заголовок взят из описи."""
    before = _page_hashes()
    documents = load_chunk_documents(SNAPSHOT)
    after = _page_hashes()
    assert before == after

    assert len(documents) == 488
    known = next(document for document in documents if document.doc_id == KNOWN_ID)
    page = (SNAPSHOT / "pages" / f"{KNOWN_ID}.txt").read_bytes()
    assert known.text.encode("utf-8") == page
    assert known.title == KNOWN_TITLE
    assert known.sections


def _page_hashes() -> dict[str, bytes]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).digest()
        for path in (SNAPSHOT / "pages").glob("*.txt")
    }
