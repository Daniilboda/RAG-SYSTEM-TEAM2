# -*- coding: utf-8 -*-
"""Перенос оригиналов data/raw_data → data/have_md, когда MD уже в ready_to_corpus.

Правило: для файла raw_data/<stem>.<ext> если есть
data_to_md/ready_to_corpus/<stem>.md — оригинал переносится в have_md/.

Запуск:
  py -3.14 -X utf8 monitoring/promote_raw_to_have_md.py
  py -3.14 -X utf8 monitoring/promote_raw_to_have_md.py --dry-run
"""
from __future__ import annotations

import argparse
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw_data"
HAVE_DIR = ROOT / "data" / "have_md"
READY_DIR = ROOT / "data_to_md" / "ready_to_corpus"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def ready_stems() -> set[str]:
    if not READY_DIR.is_dir():
        return set()
    return {nfc(p.stem) for p in READY_DIR.glob("*.md")}


def promote(*, dry_run: bool = False) -> list[tuple[Path, Path]]:
    HAVE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stems = ready_stems()
    moved: list[tuple[Path, Path]] = []
    if not RAW_DIR.is_dir():
        return moved
    for src in sorted(RAW_DIR.iterdir()):
        if not src.is_file() or src.name.startswith("."):
            continue
        if nfc(src.stem) not in stems:
            continue
        dest = HAVE_DIR / src.name
        if dest.exists():
            raise FileExistsError(f"уже есть в have_md: {dest}")
        if dry_run:
            print(f"DRY {src.relative_to(ROOT)} → {dest.relative_to(ROOT)}")
        else:
            shutil.move(str(src), str(dest))
            print(f"MOVED {src.name} → data/have_md/")
        moved.append((src, dest))
    return moved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="raw_data → have_md когда MD есть в ready_to_corpus"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="только показать, что будет перенесено",
    )
    args = parser.parse_args()
    moved = promote(dry_run=args.dry_run)
    print(f"done moved={len(moved)} ready_md={len(ready_stems())}")


if __name__ == "__main__":
    main()
