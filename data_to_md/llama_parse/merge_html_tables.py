"""Merge HTML <table> fragments split across PDF page breaks (LlamaParse MD).

Structural heuristics only (no LLM). Inspired by common cross-page table
stitchers (sequential merge, column match, headerless continuation, cell stitch).
"""
from __future__ import annotations

import re

HTML_TABLE_RE = re.compile(r"(?is)<table\b[^>]*>.*?</table>")
TR_RE = re.compile(r"(?is)<tr\b[^>]*>.*?</tr>")
CELL_RE = re.compile(r"(?is)<(t[hd])\b([^>]*)>(.*?)</\1>")
PAGE_MARK_RE = re.compile(
    r"^(?:№\s*\d+[\-\u2013]?[а-яa-z]?|"
    r"стр\.?\s*\d+|"
    r"-\s*\d+\s*-|"
    r"\d+\s*/\s*\d+)\s*$",
    re.IGNORECASE,
)
NEW_TABLE_HEAD_RE = re.compile(
    r"(?i)^\s*(?:"
    r"Группа\s*\d|"
    r"Категори|"
    r"Уровн|"
    r"№\s*$|"
    r"№\s*/|"
    r"N\s*/|"
    r"Страница\s+Программы|"
    r"Итоговый\s+балл|"
    r"Степень\s+соответствия"
    r")"
)


def _plain(html_inner: str) -> str:
    t = re.sub(r"(?i)<br\s*/?>", " ", html_inner)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _rows(table_html: str) -> list[str]:
    return TR_RE.findall(table_html)


def _cells(tr_html: str) -> list[tuple[str, str, str]]:
    """List of (tag, attrs, inner_html)."""
    return [(m.group(1), m.group(2), m.group(3)) for m in CELL_RE.finditer(tr_html)]


def _ncols(tr_html: str) -> int:
    n = 0
    for _tag, attrs, _inner in _cells(tr_html):
        m = re.search(r'colspan\s*=\s*"?(\d+)"?', attrs, re.I)
        n += int(m.group(1)) if m else 1
    return n


def _table_ncols(table_html: str) -> int:
    rows = _rows(table_html)
    if not rows:
        return 0
    return max(_ncols(r) for r in rows)


def _has_th(table_html: str) -> bool:
    return bool(re.search(r"(?is)<th\b", table_html))


def _header_labels(table_html: str) -> list[str]:
    out: list[str] = []
    for tr in _rows(table_html):
        if not re.search(r"(?is)<th\b", tr):
            break
        out.extend(_plain(inner) for _t, _a, inner in _cells(tr))
    return out


def _first_cell_plain(table_html: str) -> str:
    for tr in _rows(table_html):
        cells = _cells(tr)
        if not cells:
            continue
        return _plain(cells[0][2])
    return ""


def _last_data_cell_plain(table_html: str) -> str:
    rows = _rows(table_html)
    for tr in reversed(rows):
        cells = _cells(tr)
        if not cells:
            continue
        # prefer last non-empty plain cell
        for _t, _a, inner in reversed(cells):
            p = _plain(inner)
            if p:
                return p
        return _plain(cells[-1][2])
    return ""


def _is_glue_text(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    parts = [p.strip() for p in re.split(r"\n+", t) if p.strip()]
    if not parts:
        return True
    if all(PAGE_MARK_RE.match(p) or len(p) <= 3 for p in parts):
        return True
    if any(p.lstrip().startswith("#") for p in parts):
        return False
    if re.search(r"(?m)^\d+\.\s+\S", t):
        return False
    if re.search(r"(?i)ПРИКАЗЫВАЮ|Приложение\s*№", t):
        return False
    # short debris between page-split tables
    joined = " ".join(parts)
    if len(joined) <= 80 and not re.search(r"[.!?…]{1}(?:\s|$)", joined):
        return True
    return False


def _is_continuation_start(plain: str) -> bool:
    if not plain:
        return True
    if plain[:1].islower() or plain.startswith(")"):
        return True
    if plain.startswith(("—", "–", "- ", "• ", "и ", "или ", "по ", "на ")):
        return True
    if plain.startswith(
        ("индивидуальн", "достижен", "таможенн", "технологии", "безопасности")
    ):
        return True
    return False


def _last_cell_truncated(plain: str) -> bool:
    if not plain:
        return False
    if re.search(r"(?i)\bи\s*$", plain):
        return True
    if plain.endswith(("безопасности и", "ЕГЭ и", "баллы ЕГЭ и")):
        return True
    # ends without sentence punctuation and mid-phrase
    if plain[-1] not in ".!?;:»\"”)" and re.search(
        r"(?i)(?:\bи|\bили|\bпо|\bна|\bс|\bв|\bк)\s*$", plain
    ):
        return True
    return False


def _looks_like_new_table(table_html: str) -> bool:
    first = _first_cell_plain(table_html)
    if NEW_TABLE_HEAD_RE.match(first):
        return True
    if _has_th(table_html) and not _is_continuation_start(first):
        # real header row — new table unless it is a repeated header (checked later)
        return True
    return False


def _headers_equal(a: str, b: str) -> bool:
    ha = [x.casefold() for x in _header_labels(a) if x]
    hb = [x.casefold() for x in _header_labels(b) if x]
    return bool(ha) and ha == hb


def _should_merge(a: str, b: str, glue: str) -> bool:
    if not _is_glue_text(glue):
        return False
    na, nb = _table_ncols(a), _table_ncols(b)
    if na == 0 or nb == 0:
        return False

    if _has_th(b):
        if _headers_equal(a, b):
            return na == nb or abs(na - nb) <= 1
        # different / new header
        if _looks_like_new_table(b):
            return False

    if _looks_like_new_table(b) and not _is_continuation_start(_first_cell_plain(b)):
        return False

    first_b = _first_cell_plain(b)
    cont = _is_continuation_start(first_b)
    trunc = _last_cell_truncated(_last_data_cell_plain(a))

    # classic: same width, B has no header (data orphan)
    if na == nb and not _has_th(b):
        return True
    # spillover 1-col fragment
    if nb == 1 and na >= 2 and (cont or trunc):
        return True
    # width drift ±1 with strong continuation signal
    if abs(na - nb) == 1 and (cont or trunc) and not _has_th(b):
        return True
    return False


def _drop_leading_header_rows(rows: list[str]) -> list[str]:
    i = 0
    while i < len(rows) and re.search(r"(?is)<th\b", rows[i]):
        i += 1
    return rows[i:]


def _stitch_trs(tr_a: str, tr_b: str) -> str:
    cells_a = _cells(tr_a)
    cells_b = _cells(tr_b)
    if not cells_a:
        return tr_b
    if not cells_b:
        return tr_a

    # Align by index; append B text into corresponding A cells when B continues.
    out: list[str] = []
    n = max(len(cells_a), len(cells_b))
    for i in range(n):
        if i < len(cells_a) and i < len(cells_b):
            tag, attrs, inner_a = cells_a[i]
            _tb, attrs_b, inner_b = cells_b[i]
            pa, pb = _plain(inner_a), _plain(inner_b)
            if not pa:
                inner = inner_b
                attrs_use = attrs_b if attrs_b.strip() else attrs
            elif not pb:
                inner = inner_a
                attrs_use = attrs
            elif _is_continuation_start(pb) or _last_cell_truncated(pa):
                sep = "" if (pa.endswith("-") or pb.startswith(")")) else " "
                # keep A's markup; append plain continuation with space
                inner = inner_a.rstrip() + sep + pb
                attrs_use = attrs
            else:
                # not a cell split — keep A cell, B will be separate row (caller decides)
                return ""
            # drop empty rowspan noise from B-only attrs when using A
            out.append(f"<{tag}{attrs_use}>{inner}</{tag}>")
        elif i < len(cells_a):
            tag, attrs, inner = cells_a[i]
            out.append(f"<{tag}{attrs}>{inner}</{tag}>")
        else:
            tag, attrs, inner = cells_b[i]
            out.append(f"<{tag}{attrs}>{inner}</{tag}>")
    return "<tr>" + "".join(out) + "</tr>"


def _merge_tables(a: str, b: str) -> str:
    rows_a = _rows(a)
    rows_b = _rows(b)
    if _has_th(b) and _headers_equal(a, b):
        rows_b = _drop_leading_header_rows(rows_b)

    if not rows_a:
        body = rows_b
    elif not rows_b:
        body = rows_a
    else:
        # cell-level stitch when last A row is truncated into first B row
        last_plain = ""
        last_cells = _cells(rows_a[-1])
        if last_cells:
            last_plain = _plain(last_cells[0][2]) or _plain(last_cells[-1][2])
        first_b = _first_cell_plain(b)
        if (
            (_last_cell_truncated(last_plain) or _is_continuation_start(first_b))
            and _ncols(rows_a[-1]) == _ncols(rows_b[0])
        ):
            stitched = _stitch_trs(rows_a[-1], rows_b[0])
            if stitched:
                body = rows_a[:-1] + [stitched] + rows_b[1:]
            else:
                body = rows_a + rows_b
        elif _table_ncols(b) == 1 and _table_ncols(a) >= 2:
            # spillover: append into last cell of last row
            spill = _plain(_cells(rows_b[0])[0][2]) if _cells(rows_b[0]) else ""
            if spill and last_cells:
                tag, attrs, inner = last_cells[-1]
                last_cells[-1] = (tag, attrs, inner.rstrip() + " " + spill)
                rebuilt = (
                    "<tr>"
                    + "".join(f"<{t}{a_}>{h}</{t}>" for t, a_, h in last_cells)
                    + "</tr>"
                )
                body = rows_a[:-1] + [rebuilt] + rows_b[1:]
            else:
                body = rows_a + rows_b
        else:
            body = rows_a + rows_b

    return "<table>" + "".join(body) + "</table>"


def _split_document(md: str) -> list[tuple[str, str]]:
    """Return [('table'|'text', payload), ...] covering the whole document."""
    parts: list[tuple[str, str]] = []
    pos = 0
    for m in HTML_TABLE_RE.finditer(md):
        if m.start() > pos:
            parts.append(("text", md[pos : m.start()]))
        parts.append(("table", m.group(0)))
        pos = m.end()
    if pos < len(md):
        parts.append(("text", md[pos:]))
    return parts


def merge_html_tables(md: str) -> str:
    """Merge adjacent HTML tables that look like page-split continuations."""
    parts = _split_document(md)
    if not any(k == "table" for k, _ in parts):
        return md

    rebuilt: list[str] = []
    i = 0
    while i < len(parts):
        kind, payload = parts[i]
        if kind != "table":
            rebuilt.append(payload)
            i += 1
            continue

        current = payload
        i += 1
        while i < len(parts):
            glue = ""
            j = i
            if j < len(parts) and parts[j][0] == "text":
                glue = parts[j][1]
                j += 1
            if j < len(parts) and parts[j][0] == "table":
                nxt = parts[j][1]
                if _should_merge(current, nxt, glue):
                    current = _merge_tables(current, nxt)
                    # drop page-noise glue between fragments
                    i = j + 1
                    continue
            break
        rebuilt.append(current)

    text = "".join(rebuilt)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if not text.endswith("\n"):
        text += "\n"
    return text


def count_html_tables(md: str) -> int:
    return len(HTML_TABLE_RE.findall(md))
