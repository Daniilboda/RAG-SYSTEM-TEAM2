"""Проверка шага 1 нарезки: лимит, перекрытие, минимум и имя способа."""

from __future__ import annotations

from pathlib import Path

import pytest

from preprocessing.chunking_config import load_chunking_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "chunking" / "mdd_sections_512.yaml"


def test_mdd_sections_config_records_limit_overlap_minimum_and_name() -> None:
    """В файле записаны 512, 64, 24 и имя способа нарезки по разделам."""
    config = load_chunking_config(CONFIG)
    assert config["max_tokens"] == 512
    assert config["overlap_tokens"] == 64
    assert config["min_tokens"] == 24
    assert config["chunker"] == "mdd-sections+recursive/v1/512/64"


def test_config_without_max_tokens_is_rejected(tmp_path: Path) -> None:
    """Конфиг без лимита не принимается."""
    path = tmp_path / "no_limit.yaml"
    path.write_text("overlap_tokens: 64\nmin_tokens: 24\n", encoding="utf-8")
    with pytest.raises(ValueError, match="max_tokens"):
        load_chunking_config(path)
