"""Проверка шага 2 нарезки: длина считается токенизатором bge-m3."""

from __future__ import annotations

from pathlib import Path

from preprocessing.chunking_config import load_chunking_config
from preprocessing.token_count import count_tokens

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "chunking" / "mdd_sections_512.yaml"
SAMPLE = "How aid is calculated for students."


def test_same_text_has_the_same_token_count() -> None:
    """Один и тот же текст дважды даёт одно и то же число токенов."""
    name = load_chunking_config(CONFIG)["tokenizer"]
    assert name == "BAAI/bge-m3"
    assert count_tokens(SAMPLE, name) == count_tokens(SAMPLE, name) == 8


def test_token_count_is_not_letters_or_words() -> None:
    """512 в настройках — это токены модели, а не буквы и не слова."""
    name = load_chunking_config(CONFIG)["tokenizer"]
    tokens = count_tokens(SAMPLE, name)
    assert tokens != len(SAMPLE)
    assert tokens != len(SAMPLE.split())
