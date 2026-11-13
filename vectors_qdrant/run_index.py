# -*- coding: utf-8 -*-
"""Create Qdrant collection rudn_chunks_v1 and upsert chunks+vectors (stage E).

Does not touch mdd_chunks_v1. Reuses multidoc2dial preprocessing.index.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MDD = ROOT / "multidoc2dial"
sys.path.insert(0, str(MDD))
sys.path.insert(0, str(MDD / "packages"))

from preprocessing.index import ensure_collection, index_collection, make_client  # noqa: E402
from rag_common.embeddings import get_embedder  # noqa: E402

COLLECTION = "rudn_chunks_v1"
CHUNKS = ROOT / "chunking" / "chunks.jsonl"
VECTORS = Path(__file__).parent / "vectors.jsonl"
CONFIG = ROOT / "chunking" / "stipendii_sections_512.yaml"
INFO = Path(__file__).parent / "index_info.json"
SNAPSHOT_ID = "stipendii_lp_v1"


def smoke(client, collection: str) -> None:
    embedder = get_embedder()
    q = "Какой размер государственной академической стипендии в РУДН?"
    encoded = embedder.encode_query(q)
    hits = client.query_points(
        collection_name=collection,
        query=list(encoded.dense),
        using="dense",
        limit=3,
        with_payload=True,
    ).points
    print(f"smoke query: {q}")
    for i, hit in enumerate(hits, 1):
        payload = hit.payload or {}
        print(
            f"  {i}. score={hit.score:.4f} section={payload.get('section')} "
            f"chunk_id={payload.get('chunk_id')} title={(payload.get('title') or '')[:60]}"
        )


def main() -> None:
    if not CHUNKS.is_file() or not VECTORS.is_file():
        raise SystemExit(f"нужны {CHUNKS} и {VECTORS}")
    client = make_client()
    exists = client.collection_exists(COLLECTION)
    print(f"collection={COLLECTION} exists_before={exists}")
    ensure_collection(client, COLLECTION)
    n = index_collection(
        chunks_path=CHUNKS,
        vectors_path=VECTORS,
        info_path=INFO,
        config_path=CONFIG,
        collection=COLLECTION,
        snapshot_id=SNAPSHOT_ID,
        client=client,
    )
    info = client.get_collection(COLLECTION)
    points = info.points_count
    print(f"upserted={n} points_count={points}")
    print(f"index_info={INFO}")
    if points != n:
        raise SystemExit(f"points_count {points} != upserted {n}")
    smoke(client, COLLECTION)


if __name__ == "__main__":
    main()
