# -*- coding: utf-8 -*-
"""Build data_to_md/llama_parse/manifest.jsonl for llama_parse_md_clean (22 docs).

Reuses doc_id order from data_to_md/docling/docling.jsonl when stems match (NFC).
Adds content_hash of clean MD and paths relative to repo root.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT / "multidoc2dial" / "packages"))

from rag_common.text import normalized_hash  # noqa: E402

CLEAN = HERE / "llama_parse_md_clean"
PDF_DIR = HERE / "llama_parse_pdf"
DOCLING_MANIFEST = REPO_ROOT / "data_to_md" / "docling" / "docling.jsonl"
OUT = HERE / "manifest.jsonl"
MD_PREFIX = "data_to_md/llama_parse/llama_parse_md_clean"
PDF_PREFIX = "data_to_md/llama_parse/llama_parse_pdf"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def stem_nfc(name: str) -> str:
    return nfc(Path(name).stem)


_SKIP_TITLE = re.compile(
    r"(?i)^(ПРИКАЗ|РУДН|\(РУДН\)|Москва|Федеральное|"
    r"Российский университет|«Российский университет)"
)


def guess_title(md_text: str, fallback: str) -> str:
    candidates: list[str] = []
    for ln in md_text.splitlines()[:50]:
        s = ln.strip()
        if not s:
            continue
        m = re.match(r"^#{1,6}\s+(.+)$", s)
        if m:
            t = re.sub(r"[*_`]+", "", m.group(1)).strip()
        elif s.startswith("**") and s.endswith("**") and len(s) > 8:
            t = s.strip("*").strip()
        elif s.startswith("####"):
            t = re.sub(r"^#+\s*", "", s)
            t = re.sub(r"[*_`]+", "", t).strip()
        else:
            # plain subject lines like "О мерах поддержки…"
            t = re.sub(r"[*_`]+", "", s).strip()
            if not (t.startswith("О ") or t.startswith("Об ") or "Положение" in t or "Регламент" in t or "График" in t):
                continue
        if not t or _SKIP_TITLE.search(t):
            continue
        if "Федеральное государственное" in t:
            continue
        candidates.append(t[:200])
    # prefer subject-like titles
    for t in candidates:
        if t.startswith("О ") or t.startswith("Об ") or "Положение" in t or "Регламент" in t or "График" in t:
            return t
    if candidates:
        return candidates[0]
    return fallback.replace("_", " ")[:200]


def main() -> None:
    clean_by_stem = {stem_nfc(p.name): p for p in CLEAN.glob("*.md")}
    pdf_by_stem = {stem_nfc(p.name): p for p in PDF_DIR.glob("*.pdf")}

    base_rows = []
    for line in DOCLING_MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            base_rows.append(json.loads(line))

    if len(base_rows) != 22:
        raise SystemExit(f"expected 22 docling rows, got {len(base_rows)}")

    missing_md = []
    missing_pdf = []
    out_rows = []

    for row in base_rows:
        stem = stem_nfc(row["document_new"])
        md = clean_by_stem.get(stem)
        pdf = pdf_by_stem.get(stem)
        if md is None:
            missing_md.append(row["document_new"])
            continue
        if pdf is None:
            # try pdf name from document_old
            pdf = pdf_by_stem.get(stem_nfc(row["document_old"]))
        if pdf is None:
            missing_pdf.append(row["document_old"])

        text = md.read_text(encoding="utf-8")
        title = guess_title(text, stem)
        rec = {
            "doc_id": row["doc_id"],
            "document_new": md.name,  # actual clean filename on disk
            "document_old": pdf.name if pdf else row["document_old"],
            "md_path": f"{MD_PREFIX}/{md.name}",
            "pdf_path": f"{PDF_PREFIX}/{pdf.name}" if pdf else None,
            "title": title,
            "category": "стипендии",
            "section": "stipendii",
            "previous_format": "pdf",
            "new_format": "md",
            "converter": "llamaparse+postprocess_md",
            "source": "llama_parse_md_clean",
            "content_hash": normalized_hash(text),
            "chars": len(text),
            "adr": "project_docs/adr/pre-stipendii-md-source.md",
        }
        out_rows.append(rec)

    if missing_md:
        raise SystemExit(f"missing clean md for: {missing_md}")
    if len(out_rows) != 22:
        raise SystemExit(f"expected 22 rows, got {len(out_rows)}; missing_pdf={missing_pdf}")

    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in out_rows) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(out_rows)} rows)")
    if missing_pdf:
        print("WARN missing pdf match:", missing_pdf)
    for r in out_rows:
        print(f"{r['doc_id']:>2} {r['content_hash'][:12]}…  {r['document_new'][:60]}")


if __name__ == "__main__":
    main()
