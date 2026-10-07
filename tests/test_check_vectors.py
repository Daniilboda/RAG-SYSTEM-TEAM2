"""Проверка шага 3 эмбеддингов: вектор есть у каждой строки, плотный длины 1024."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from preprocessing.check_vectors import check_vectors
from rag_common.embeddings import DENSE_SIZE

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "index" / "mdd_chunks_v1" / "chunks.jsonl"
VECTORS = ROOT / "data" / "index" / "mdd_chunks_v1" / "vectors.jsonl"


def test_saved_vectors_cover_every_chunk() -> None:
    """У каждой строки фрагмента есть вектор. В плотном 1024 числа. Пустых нет."""
    assert check_vectors(CHUNKS, VECTORS) == _line_count(CHUNKS)


def test_short_dense_vector_is_rejected(tmp_path: Path) -> None:
    """Плотный вектор короче 1024 проверка не пропускает."""
    chunks = tmp_path / "chunks.jsonl"
    vectors = tmp_path / "vectors.jsonl"
    _write(chunks, [{"chunk_id": "id-0", "embed_text": "text"}])
    _write(vectors, [{"chunk_id": "id-0", "dense": [0.1], "sparse_indices": [1], "sparse_values": [0.5]}])
    with pytest.raises(ValueError, match="1024"):
        check_vectors(chunks, vectors)


def test_missing_vector_row_is_rejected(tmp_path: Path) -> None:
    """Если строк векторов меньше, чем фрагментов, проверка останавливается."""
    chunks = tmp_path / "chunks.jsonl"
    vectors = tmp_path / "vectors.jsonl"
    _write(
        chunks,
        [
            {"chunk_id": "id-0", "embed_text": "one"},
            {"chunk_id": "id-1", "embed_text": "two"},
        ],
    )
    _write(
        vectors,
        [{
            "chunk_id": "id-0",
            "dense": [0.1] * DENSE_SIZE,
            "sparse_indices": [1],
            "sparse_values": [0.5],
        }],
    )
    with pytest.raises(ValueError, match="векторов 1"):
        check_vectors(chunks, vectors)


def _write(path: Path, rows: list[dict]) -> None:
    path.write_bytes("".join(json.dumps(row) + "\n" for row in rows).encode("utf-8"))


def _line_count(path: Path) -> int:
    return sum(1 for line in path.read_bytes().decode("utf-8").splitlines() if line)
