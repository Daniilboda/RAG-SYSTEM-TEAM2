"""Проверка шага 10: снимок проходит K1, вторая сборка даёт те же файлы."""

from __future__ import annotations

from pathlib import Path

from rag_common.mdd.build import build_snapshot
from rag_common.mdd.validate import validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "cache" / "multidoc2dial.zip"
SNAPSHOT = ROOT / "data" / "snapshots" / "mdd_v1"


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_t_cmn_01_snapshot_and_identical_rebuild(tmp_path: Path) -> None:
    """Проверяет: T-CMN-01, валидатор без ошибок и вторая сборка байт в байт та же."""
    assert validate_snapshot(SNAPSHOT) == []
    rebuilt = tmp_path / "mdd_v1"
    build_snapshot(ARCHIVE, rebuilt)
    assert validate_snapshot(rebuilt) == []
    assert _files(rebuilt) == _files(SNAPSHOT)
