"""Проверка шага 4: адрес документа и наш doc_id."""

from __future__ import annotations

from pathlib import Path

from rag_common.mdd.documents import iter_documents
from rag_common.mdd.ids import k1_doc_id, k1_url, make_doc_id

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "cache" / "multidoc2dial.zip"
SOURCE_WITH_SPECIALS = "Top 5|Mistakes#3_0"


def test_t_pre_01_k1_url_encodes_space_pipe_and_hash() -> None:
    """Проверяет: T-PRE-01, адрес кодирует пробел, | и #."""
    assert k1_url("dmv", SOURCE_WITH_SPECIALS) == "mdd://dmv/Top%205%7CMistakes%233_0"


def test_t_cmn_10_doc_id_matches_recorded_uuid() -> None:
    """Проверяет: T-CMN-10, наш номер совпадает с записанным uuid5."""
    url = k1_url("dmv", SOURCE_WITH_SPECIALS)
    assert k1_doc_id("dmv", SOURCE_WITH_SPECIALS) == "ea46edf1-1887-5c61-b896-fe0bdd4b0742"
    assert k1_doc_id("dmv", SOURCE_WITH_SPECIALS) == make_doc_id(url)


def test_step4_same_document_keeps_same_id() -> None:
    """Повторный проход даёт тот же номер тому же документу. Исходный номер остаётся отдельно."""
    first = _ids()
    second = _ids()
    assert len(first) == 488
    assert first == second
    assert len(set(first.values())) == 488
    assert all(source_doc_id != our_id for (_, source_doc_id), our_id in first.items())


def _ids() -> dict[tuple[str, str], str]:
    return {
        (document.domain, document.source_doc_id): k1_doc_id(document.domain, document.source_doc_id)
        for document in iter_documents(ARCHIVE)
    }
