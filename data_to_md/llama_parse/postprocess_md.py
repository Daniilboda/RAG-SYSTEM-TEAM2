"""Post-process LlamaParse markdown for RAG: strip SED/EP noise + merge wraps/tables.

Removes e1cib/barcode footers, electronic-signature blocks, signature:/logo:
annotations, decorative <u>/<hr>, and similar stamps. Merges HTML <table>
fragments and prose/list lines split across PDF page breaks
(see merge_html_tables.py, merge_broken_wraps.py).

Usage:
  python data_to_md/llama_parse/postprocess_md.py
  python data_to_md/llama_parse/postprocess_md.py data_to_md/llama_parse/llama_parse_md --outdir data_to_md/llama_parse/llama_parse_md_clean
  python data_to_md/llama_parse/postprocess_md.py data_to_md/llama_parse/llama_parse_md_clean --outdir data_to_md/ready_to_corpus
  python data_to_md/llama_parse/postprocess_md.py path/to/file.md --in-place
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from merge_broken_wraps import merge_broken_wraps
from merge_html_tables import count_html_tables, merge_html_tables

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_IN = HERE / "llama_parse_md"
DEFAULT_OUT = HERE / "llama_parse_md_clean"
READY_TO_CORPUS = ROOT / "data_to_md" / "ready_to_corpus"


def _maybe_promote_raw_to_have_md(outdir: Path | None) -> None:
    """Если писали в ready_to_corpus — перенести оригиналы raw_data → have_md."""
    if outdir is None:
        return
    try:
        resolved = outdir.resolve()
    except OSError:
        return
    if resolved != READY_TO_CORPUS.resolve():
        return
    import sys

    mon = ROOT / "monitoring"
    if str(mon) not in sys.path:
        sys.path.insert(0, str(mon))
    from promote_raw_to_have_md import promote  # noqa: E402

    moved = promote(dry_run=False)
    if moved:
        print(f"monitoring: promoted {len(moved)} file(s) raw_data → have_md")

EDS_BLOCK_RE = re.compile(
    r"(?:Документ подписан простой электронной подписью|"
    r"Информация о владельце:|"
    r"Уникальный программный ключ:|"
    r"Действительный документ|"
    r"Действующий документ|"
    r"Документ хранится в программе|"
    r"Электронная копия документа)"
    r".*?(?=\n\n|\n(?:#{1,3}\s|Федеральное|\d+\s+[а-я]|\Z))",
    re.S | re.I,
)

EDS_LINE_RE = re.compile(
    r"^(?:"
    r"Документ подписан(?:\s+простой)?\s+электронной\s+подписью.*"
    r"|ДОКУМЕНТ\s+ПОДПИСАН\s+ЭЛЕКТРОННОЙ\s+ПОДПИСЬЮ.*"
    r"|Информация о владельце:.*"
    r"|ФИО:\s*.*"
    r"|Должность:\s*.*"
    r"|Дата подписания:\s*.*"
    r"|Уникальный программный ключ:\s*.*"
    r"|Сертификат\s*:.*"
    r"|Владелец\s*:.*"
    r"|Действителен\s*:.*"
    r"|[0-9a-f]{32,}"
    r"|Действительн(?:ый|ый|ий)\s+документ.*"
    r"|Действующий\s+документ.*"
    r"|Документ хранится в прог.*"
    r"|Электронная копия документа.*"
    r"|Электронная версия документа.*"
    r")\s*$",
    re.I,
)

SED_BARCODE_LINE_RE = re.compile(
    r"(?i)^\s*(?:"
    r"Действительн\w*\s+документ\s+e1cib/.*"
    r"|Действующ\w*\s+документ\s+e1cib/.*"
    r"|.*\be1cib/data\b.*"
    r"|.*\bcode:\s*barcode\b.*"
    r"|Документ\s+хранится\s+в\s+прог.*"
    r")\s*$"
)

SED_INLINE_RE = re.compile(
    r"(?i)\s*(?:"
    r"Действительн\w*\s+документ\s+e1cib/[^\n|]*"
    r"(?:\s*\|\s*Документ\s+хранится\s+в\s+прог[^\n|]*)?"
    r"(?:\s*\|\s*code:\s*barcode)?"
    r"|Действующ\w*\s+документ\s+e1cib/[^\n|]*"
    r"(?:\s*\|\s*Документ\s+хранится\s+в\s+прог[^\n|]*)?"
    r"(?:\s*\|\s*code:\s*barcode)?"
    r")"
)

LP_ANNOT_LINE_RE = re.compile(
    r"(?i)^\s*(?:"
    r"logo\s*:.*"
    r"|signature\s*:.*"
    r"|code\s*:\s*barcode\s*"
    r")\s*$"
)

LP_ANNOT_INLINE_RE = re.compile(
    r"(?i)\s*(?:logo|signature)\s*:\s*[^\n*|<]+"
)

IMAGE_PH_RE = re.compile(r"<!--\s*image\s*-->\s*\n?", re.I)
FORMULA_PH_RE = re.compile(r"<!--\s*formula-not-decoded\s*-->\s*\n?", re.I)
U_TAG_RE = re.compile(r"</?u>", re.I)
HR_TAG_RE = re.compile(r"<hr\s*/?>", re.I)


def _plain_for_match(ln: str) -> str:
    s = U_TAG_RE.sub("", ln)
    s = re.sub(r"[*_`]+", "", s)
    return s.strip()


def strip_eds(md: str) -> str:
    lines: list[str] = []
    for ln in md.splitlines():
        plain = _plain_for_match(ln)
        if EDS_LINE_RE.match(plain):
            continue
        if SED_BARCODE_LINE_RE.match(ln.strip()) or SED_BARCODE_LINE_RE.match(plain):
            continue
        if LP_ANNOT_LINE_RE.match(ln.strip()) or LP_ANNOT_LINE_RE.match(plain):
            continue
        if "электронной подписью" in ln.lower() and (
            "Уникальный программный ключ" in ln or "ФИО:" in ln or "Сертификат" in ln
        ):
            before = re.split(
                r"Документ подписан(?:\s+простой)?\s+электронной\s+подписью|"
                r"ДОКУМЕНТ\s+ПОДПИСАН\s+ЭЛЕКТРОННОЙ\s+ПОДПИСЬЮ",
                ln,
                maxsplit=1,
                flags=re.I,
            )[0].strip()
            before = U_TAG_RE.sub("", before).strip(" *_")
            if before and "ФИО:" not in before and "Сертификат" not in before:
                lines.append(before)
            continue
        if re.search(
            r"Документ подписан(?:\s+простой)?\s+электронной\s+подписью|"
            r"ДОКУМЕНТ\s+ПОДПИСАН\s+ЭЛЕКТРОННОЙ\s+ПОДПИСЬЮ",
            ln,
            re.I,
        ):
            parts = re.split(
                r"Уникальный программный ключ:\s*[0-9a-fA-F\s]+",
                ln,
                maxsplit=1,
                flags=re.I,
            )
            if len(parts) == 2 and parts[1].strip() and "ФИО:" not in parts[1]:
                rest = U_TAG_RE.sub("", parts[1]).strip()
                if rest:
                    lines.append(rest)
            continue
        ln = re.sub(
            r"\s*ФИО:\s*.*?Должность:\s*.*?Дата подписания:\s*\S+(?:\s+\S+)?\s*",
            " ",
            ln,
            flags=re.I,
        )
        ln = re.sub(
            r"\s*Уникальный программный ключ:\s*[0-9a-fA-F\s]+",
            " ",
            ln,
            flags=re.I,
        )
        ln = SED_INLINE_RE.sub(" ", ln)
        ln = LP_ANNOT_INLINE_RE.sub(" ", ln)
        ln = U_TAG_RE.sub("", ln)
        ln = HR_TAG_RE.sub("", ln)
        ln = re.sub(r"\*{3,}", "**", ln)
        ln = re.sub(r"[ \t]{2,}", " ", ln)
        if ln.strip():
            lines.append(ln.rstrip())
        elif lines and lines[-1] != "":
            lines.append("")
    text = "\n".join(lines)
    text = EDS_BLOCK_RE.sub("\n", text)
    text = SED_INLINE_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def strip_image_placeholders(md: str) -> str:
    md = IMAGE_PH_RE.sub("\n", md)
    md = FORMULA_PH_RE.sub("\n", md)
    return md


def postprocess_md(md: str) -> str:
    md = strip_image_placeholders(md)
    md = strip_eds(md)
    md = merge_html_tables(md)
    md = merge_broken_wraps(md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md


def _iter_md_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    # top-level only — skip Mira-web-parse and other subfolders
    return sorted(path.glob("*.md"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "md_path",
        type=Path,
        nargs="?",
        default=DEFAULT_IN,
        help=f"Markdown file or directory (default: {DEFAULT_IN.name}/)",
    )
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("-o", "--output", type=Path, help="Output file (single-file mode)")
    ap.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help=f"Output directory (default for dirs: {DEFAULT_OUT.name}/)",
    )
    args = ap.parse_args()

    files = _iter_md_files(args.md_path)
    if not files:
        raise SystemExit(f"no .md files in {args.md_path}")

    batch = args.md_path.is_dir() or len(files) > 1
    if batch:
        if args.in_place and args.outdir:
            raise SystemExit("use either --in-place or --outdir, not both")
        outdir = args.outdir
        if outdir is None and not args.in_place:
            outdir = DEFAULT_OUT
        if outdir is not None:
            outdir.mkdir(parents=True, exist_ok=True)
        for src in files:
            raw = src.read_text(encoding="utf-8")
            cleaned = postprocess_md(raw)
            dest = src if args.in_place else outdir / src.name  # type: ignore[operator]
            dest.write_text(cleaned, encoding="utf-8")
            t0, t1 = count_html_tables(raw), count_html_tables(cleaned)
            j = int(getattr(merge_broken_wraps, "last_joins", 0))
            bits = []
            if t0 or t1:
                bits.append(f"tables {t0}->{t1}")
            if j:
                bits.append(f"wrap_joins={j}")
            extra = (" " + ", ".join(bits)) if bits else ""
            print(f"{src.name}: {len(raw)} -> {len(cleaned)} chars{extra}")
        print(f"done: {len(files)} files -> {outdir or '(in-place)'}")
        _maybe_promote_raw_to_have_md(outdir)
        return
    raw = files[0].read_text(encoding="utf-8")
    out = postprocess_md(raw)
    if args.in_place:
        files[0].write_text(out, encoding="utf-8")
        print(f"updated {files[0]} ({len(raw)} -> {len(out)} chars)")
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out, encoding="utf-8")
        print(f"wrote {args.output}")
    elif args.outdir:
        args.outdir.mkdir(parents=True, exist_ok=True)
        dest = args.outdir / files[0].name
        dest.write_text(out, encoding="utf-8")
        print(f"wrote {dest}")
        _maybe_promote_raw_to_have_md(args.outdir)
    else:
        print(out, end="")


if __name__ == "__main__":
    main()
