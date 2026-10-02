"""Проверка шага 4 нарезки: кусок равен срезу раздела и не выходит за его границы."""

from __future__ import annotations

import hashlib
from pathlib import Path

from preprocessing.chunk_document import load_chunk_documents
from preprocessing.section_cuts import cut_by_sections

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "snapshots" / "mdd_v1"
KNOWN_ID = "0a6f1ad6-6a7d-5462-abe5-516ceca3c4bb"


def test_cut_text_equals_section_slice_and_stops_at_its_boundary() -> None:
    """Текст фрагмента равен срезу документа. Границы не выходят из раздела."""
    before = _page_hashes()
    documents = load_chunk_documents(SNAPSHOT)
    known = next(document for document in documents if document.doc_id == KNOWN_ID)
    cuts = cut_by_sections(known)
    after = _page_hashes()
    assert before == after

    assert len(cuts) == len(known.sections)
    assert [(cut.char_start, cut.char_end) for cut in cuts] == [
        (section["char_start"], section["char_end"]) for section in known.sections
    ]
    for cut in cuts:
        assert cut.text == known.text[cut.char_start : cut.char_end]
        assert 0 <= cut.char_start <= cut.char_end <= len(known.text)
    assert cuts[0].char_end == cuts[1].char_start == 71
    assert cuts[0].text == known.text[:71]
    assert cuts[1].text == known.text[71 : cuts[1].char_end]


def test_every_document_cut_stays_inside_its_section() -> None:
    """У всех 488 документов кусок кончается на границе своего раздела."""
    for document in load_chunk_documents(SNAPSHOT):
        cuts = cut_by_sections(document)
        assert len(cuts) == len(document.sections)
        for cut, section in zip(cuts, document.sections, strict=True):
            assert (cut.char_start, cut.char_end) == (section["char_start"], section["char_end"])
            assert cut.text == document.text[cut.char_start : cut.char_end]


def _page_hashes() -> dict[str, bytes]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).digest()
        for path in (SNAPSHOT / "pages").glob("*.txt")
    }
