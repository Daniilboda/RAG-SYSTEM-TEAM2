# -*- coding: utf-8 -*-
"""Embed chunking/chunks.jsonl → vectors_qdrant/vectors.jsonl (stage E, no Qdrant).

Uses multidoc2dial preprocessing.embed_chunks + check_vectors (bge-m3 dense+sparse).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MDD = ROOT / "multidoc2dial"
sys.path.insert(0, str(MDD))
sys.path.insert(0, str(MDD / "packages"))

from preprocessing.check_vectors import check_vectors  # noqa: E402
from preprocessing.embed_chunks import write_vectors  # noqa: E402

CHUNKS = ROOT / "chunking" / "chunks.jsonl"
OUT = Path(__file__).parent / "vectors.jsonl"


def main() -> None:
    if not CHUNKS.is_file():
        raise SystemExit(f"нет {CHUNKS}")
    print(f"chunks={CHUNKS}")
    print(f"out={OUT}")
    n = write_vectors(CHUNKS, OUT)
    print(f"wrote {OUT} vectors={n}")
    checked = check_vectors(CHUNKS, OUT)
    print(f"check_vectors ok rows={checked}")


if __name__ == "__main__":
    main()
