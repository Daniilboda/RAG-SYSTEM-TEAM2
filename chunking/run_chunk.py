# -*- coding: utf-8 -*-
"""Cut stipendii_lp_v1 snapshot into chunking/chunks.jsonl (stage D).

Reuses multidoc2dial preprocessing (md_header / write_chunks / check_chunks).

Workaround: long GFM tables get a repeated header in SectionPiece.text while
char_start/end still point at the body rows. K2 requires text == page slice,
so we keep the exact slice in text and put the enriched table into embed_text.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MDD = ROOT / "multidoc2dial"
sys.path.insert(0, str(MDD))
sys.path.insert(0, str(MDD / "packages"))

from preprocessing import fragment_card as fc_mod  # noqa: E402
from preprocessing.chunkers import md_header as mh  # noqa: E402
from preprocessing.check_chunks import check_chunks  # noqa: E402
from preprocessing.embed_limit import fit_embed_limit  # noqa: E402
from preprocessing.write_chunks import write_chunks  # noqa: E402

SNAPSHOT = ROOT / "snapshot_k1" / "stipendii_lp_v1"
CONFIG = Path(__file__).parent / "stipendii_sections_512.yaml"
OUT = Path(__file__).parent / "chunks.jsonl"

_orig_fragment_card = fc_mod.fragment_card


def _fragment_card_exact_slice(document, piece):
    card = _orig_fragment_card(document, piece)
    exact = document.text[piece.char_start : piece.char_end]
    if card.text == exact:
        return card
    # e.g. table header repeated into piece.text for continuity
    embed = fc_mod._embed_text(document.title, card.headings, piece.text)
    return fc_mod.FragmentCard(
        doc_id=card.doc_id,
        title=card.title,
        breadcrumbs=card.breadcrumbs,
        headings=card.headings,
        text=exact,
        embed_text=embed,
        char_start=card.char_start,
        char_end=card.char_end,
        has_generated_text=False,
    )


def _patch() -> None:
    fc_mod.fragment_card = _fragment_card_exact_slice
    mh.fragment_card = _fragment_card_exact_slice
    # embed_limit imports fragment_card by name at call time via module attr
    import preprocessing.embed_limit as el

    el.fragment_card = _fragment_card_exact_slice


def main() -> None:
    if not SNAPSHOT.is_dir():
        raise SystemExit(f"нет снимка {SNAPSHOT}")
    _patch()
    print(f"snapshot={SNAPSHOT}")
    print(f"config={CONFIG}")
    n = write_chunks(SNAPSHOT, CONFIG, OUT)
    print(f"wrote {OUT} chunks={n}")
    checked = check_chunks(SNAPSHOT, CONFIG, OUT)
    print(f"check_chunks ok rows={checked}")


if __name__ == "__main__":
    main()
