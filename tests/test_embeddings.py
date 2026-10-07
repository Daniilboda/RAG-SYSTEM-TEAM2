"""Проверка шага 1 эмбеддингов: один проход даёт два вектора."""

from __future__ import annotations

import pytest

from rag_common.embeddings import DENSE_SIZE, MODEL_NAME, Embedder, get_embedder


def test_one_pass_returns_dense_and_sparse_and_repeat_matches() -> None:
    """Один текст дважды даёт те же два вектора. В плотном 1024 числа."""
    embedder = Embedder(_FakeModel(), MODEL_NAME)
    text = "How aid is calculated for students."
    first = embedder.encode_documents([text])
    second = embedder.encode_documents([text])
    assert len(first) == 1
    assert len(first[0].dense) == DENSE_SIZE
    assert first[0].dense == second[0].dense
    assert first[0].sparse == second[0].sparse
    assert first[0].sparse.indices == (1, 4)
    assert first[0].sparse.values == (0.5, 0.25)
    assert embedder.encode_query(text) == first[0]
    assert embedder.model_name == MODEL_NAME


def test_unknown_model_is_rejected() -> None:
    """Модуль знает только BAAI/bge-m3."""
    with pytest.raises(ValueError):
        get_embedder("intfloat/multilingual-e5-large")


def test_real_model_returns_two_vectors_for_one_text() -> None:
    """Настоящая bge-m3 за один проход отвечает двумя векторами."""
    embedder = get_embedder()
    text = "How aid is calculated for students."
    first = embedder.encode_documents([text])[0]
    second = embedder.encode_query(text)
    assert embedder.model_name == MODEL_NAME
    assert len(first.dense) == DENSE_SIZE
    assert first.dense == second.dense
    assert first.sparse == second.sparse
    assert first.sparse.indices
    assert all(weight > 0 for weight in first.sparse.values)


class _FakeModel:
    def encode(self, texts, return_dense, return_sparse, return_colbert_vecs, batch_size=12, max_length=8192):
        assert return_dense is True
        assert return_sparse is True
        assert return_colbert_vecs is False
        dense = [[0.1] * DENSE_SIZE for _text in texts]
        sparse = [{4: 0.25, 1: 0.5, 9: 0.0} for _text in texts]
        return {"dense_vecs": dense, "lexical_weights": sparse}
