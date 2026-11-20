"""Длинный раздел режется внутри своих границ.

Сначала по абзацам, слишком длинный абзац — по строкам, строка — по предложениям.
Соседние куски перекрываются. Предложение длиннее лимита режется по токенам и попадает в отчёт.
Таблица (GFM `|…|` или HTML `<table>`) по возможности остаётся целиком; если не влезает,
режется по строкам/`<tr>`, и шапка повторяется в каждом куске (для embed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from preprocessing.chunk_document import ChunkDocument
from preprocessing.section_cuts import SectionCut, cut_by_sections
from preprocessing.token_count import count_tokens, token_spans

_PARAGRAPHS = re.compile(r"\n[ \t]*\n")
_LINES = re.compile(r"\n")
_SENTENCES = re.compile(r"(?<=[.!?])[ \t]+")
_TABLE_SEP = re.compile(r":?-{3,}:?")
_HTML_TABLE = re.compile(r"(?is)<table\b[^>]*>.*?</table>")
_HTML_TABLE_OPEN = re.compile(r"(?is)<table\b[^>]*>")
_HTML_THEAD = re.compile(r"(?is)<thead\b[^>]*>.*?</thead>")
_HTML_TR = re.compile(r"(?is)<tr\b[^>]*>.*?</tr>")


@dataclass(frozen=True)
class SectionPiece:
    """Кусок внутри одного раздела."""

    doc_id: str
    title_path: tuple[str, ...]
    char_start: int
    char_end: int
    text: str
    header_repeated: bool


@dataclass(frozen=True)
class HardSplit:
    """Предложение длиннее лимита, его разрезали по токенам."""

    doc_id: str
    char_start: int
    char_end: int


def split_long_sections(
    document: ChunkDocument,
    *,
    max_tokens: int,
    overlap_tokens: int,
    tokenizer_name: str,
) -> tuple[list[SectionPiece], list[HardSplit]]:
    """Режет длинные разделы. Кусок не выходит за границы своего раздела."""
    if overlap_tokens >= max_tokens:
        raise ValueError("перекрытие должно быть меньше лимита")
    pieces: list[SectionPiece] = []
    notes: list[HardSplit] = []
    for cut in cut_by_sections(document):
        part, part_notes = _split_cut(document, cut, max_tokens, overlap_tokens, tokenizer_name)
        pieces.extend(part)
        notes.extend(part_notes)
    return pieces, notes


def _split_cut(
    document: ChunkDocument,
    cut: SectionCut,
    max_tokens: int,
    overlap_tokens: int,
    tokenizer_name: str,
) -> tuple[list[SectionPiece], list[HardSplit]]:
    pieces: list[SectionPiece] = []
    notes: list[HardSplit] = []
    for kind, start, end in _segments(document.text, cut.char_start, cut.char_end):
        if kind == "table":
            pieces.extend(_split_table(document, cut, start, end, max_tokens, tokenizer_name))
        else:
            part, part_notes = _split_prose(
                document, cut, start, end, 0, max_tokens, overlap_tokens, tokenizer_name
            )
            pieces.extend(part)
            notes.extend(part_notes)
    return pieces, notes


def _segments(text: str, start: int, end: int) -> list[tuple[str, int, int]]:
    """Делит раздел на prose / GFM-таблицы / HTML-таблицы. Границы абсолютные."""
    region = text[start:end]
    segments: list[tuple[str, int, int]] = []
    cursor = 0
    for match in _HTML_TABLE.finditer(region):
        if match.start() > cursor:
            segments.extend(
                _gfm_or_prose_segments(region, cursor, match.start(), abs_base=start)
            )
        segments.append(("table", start + match.start(), start + match.end()))
        cursor = match.end()
    if cursor < len(region):
        segments.extend(
            _gfm_or_prose_segments(region, cursor, len(region), abs_base=start)
        )
    if not segments:
        segments.append(("prose", start, end))
    return segments


def _gfm_or_prose_segments(
    region: str, rel_start: int, rel_end: int, *, abs_base: int
) -> list[tuple[str, int, int]]:
    """В промежутке без HTML-table ищет GFM pipe-таблицы, иначе prose."""
    slice_text = region[rel_start:rel_end]
    lines = _line_spans(slice_text)
    segments: list[tuple[str, int, int]] = []
    index = 0
    prose_from: int | None = None
    while index < len(lines):
        if _table_run(slice_text, lines, index) >= 2:
            if prose_from is not None:
                segments.append(
                    (
                        "prose",
                        abs_base + rel_start + prose_from,
                        abs_base + rel_start + lines[index][0],
                    )
                )
                prose_from = None
            run = _table_run(slice_text, lines, index)
            table_end = lines[index + run - 1][1]
            segments.append(
                (
                    "table",
                    abs_base + rel_start + lines[index][0],
                    abs_base + rel_start + table_end,
                )
            )
            index += run
            continue
        if prose_from is None:
            prose_from = lines[index][0]
        index += 1
    if prose_from is not None:
        segments.append(
            ("prose", abs_base + rel_start + prose_from, abs_base + rel_end)
        )
    if not segments and rel_start < rel_end:
        segments.append(("prose", abs_base + rel_start, abs_base + rel_end))
    return segments


def _line_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    begin = 0
    while begin <= len(text):
        newline = text.find("\n", begin)
        if newline == -1:
            if begin < len(text) or not spans:
                spans.append((begin, len(text)))
            break
        spans.append((begin, newline))
        begin = newline + 1
        if begin == len(text):
            break
    return spans


def _table_run(text: str, lines: list[tuple[int, int]], index: int) -> int:
    run = 0
    while index + run < len(lines) and _is_table_line(text[lines[index + run][0] : lines[index + run][1]]):
        run += 1
    return run


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _split_table(
    document: ChunkDocument,
    cut: SectionCut,
    start: int,
    end: int,
    max_tokens: int,
    tokenizer_name: str,
) -> list[SectionPiece]:
    table = document.text[start:end]
    if count_tokens(table, tokenizer_name) <= max_tokens:
        return [_piece(cut, start, end, table, False)]
    if _looks_like_html_table(table):
        return _split_html_table(
            document, cut, start, end, max_tokens, tokenizer_name
        )
    return _split_gfm_table(document, cut, start, end, max_tokens, tokenizer_name)


def _looks_like_html_table(table: str) -> bool:
    return bool(_HTML_TABLE_OPEN.search(table)) and bool(_HTML_TR.search(table))


def _split_gfm_table(
    document: ChunkDocument,
    cut: SectionCut,
    start: int,
    end: int,
    max_tokens: int,
    tokenizer_name: str,
) -> list[SectionPiece]:
    table = document.text[start:end]
    lines = [table[line_start:line_end] for line_start, line_end in _line_spans(table)]
    header = lines[0]
    separator = lines[1] if len(lines) > 1 and _is_separator(lines[1]) else None
    data_from = 2 if separator is not None else 1
    positions = _line_spans(table)
    pieces: list[SectionPiece] = []
    row = data_from
    while row < len(lines):
        taken: list[int] = []
        while row < len(lines):
            candidate = _table_text(
                header, separator, [lines[index] for index in taken + [row]]
            )
            if taken and count_tokens(candidate, tokenizer_name) > max_tokens:
                break
            taken.append(row)
            row += 1
            if count_tokens(candidate, tokenizer_name) > max_tokens:
                break
        body_start = start + positions[taken[0]][0]
        body_end = start + positions[taken[-1]][1]
        repeated = taken[0] != data_from
        if repeated:
            text = _table_text(header, separator, [lines[index] for index in taken])
        else:
            text = document.text[start:body_end]
            body_start = start
        pieces.append(_piece(cut, body_start, body_end, text, repeated))
    return pieces


def _split_html_table(
    document: ChunkDocument,
    cut: SectionCut,
    start: int,
    end: int,
    max_tokens: int,
    tokenizer_name: str,
) -> list[SectionPiece]:
    """Режет HTML-таблицу по <tr>; шапка (thead или первый tr) повторяется."""
    table = document.text[start:end]
    open_m = _HTML_TABLE_OPEN.search(table)
    open_tag = open_m.group(0) if open_m else "<table>"
    thead_m = _HTML_THEAD.search(table)
    trs = list(_HTML_TR.finditer(table))
    if not trs:
        return [_piece(cut, start, end, table, False)]

    if thead_m:
        header_html = thead_m.group(0)
        data_trs = [m for m in trs if m.start() >= thead_m.end()]
    else:
        header_html = trs[0].group(0)
        data_trs = trs[1:]

    if not data_trs:
        return [_piece(cut, start, end, table, False)]

    pieces: list[SectionPiece] = []
    index = 0
    while index < len(data_trs):
        taken: list[re.Match[str]] = []
        while index < len(data_trs):
            trial = taken + [data_trs[index]]
            # Считаем токены по тому же тексту, что попадёт в piece (срез vs wrap).
            will_repeat = trial[0] is not data_trs[0]
            if will_repeat:
                candidate = _html_table_text(
                    open_tag, header_html, [m.group(0) for m in trial]
                )
            else:
                candidate = document.text[start : start + trial[-1].end()]
            if taken and count_tokens(candidate, tokenizer_name) > max_tokens:
                break
            taken.append(data_trs[index])
            index += 1
            if count_tokens(candidate, tokenizer_name) > max_tokens:
                break
        if not taken:
            taken = [data_trs[index]]
            index += 1
        body_start = start + taken[0].start()
        body_end = start + taken[-1].end()
        repeated = taken[0] is not data_trs[0]
        if repeated:
            text = _html_table_text(
                open_tag, header_html, [m.group(0) for m in taken]
            )
        else:
            text = document.text[start:body_end]
            body_start = start
        # Одна строка таблицы больше лимита — режем как prose по символам строки.
        if (
            len(taken) == 1
            and count_tokens(text, tokenizer_name) > max_tokens
        ):
            row_start = start + taken[0].start()
            row_end = start + taken[0].end()
            if not repeated:
                if start < row_start:
                    prefix = document.text[start:row_start]
                    if prefix.strip():
                        pieces.append(_piece(cut, start, row_start, prefix, False))
                body_start = row_start
            else:
                body_start = row_start
            overflow, _notes = _split_prose(
                document,
                cut,
                body_start,
                row_end,
                0,
                max_tokens,
                0,
                tokenizer_name,
            )
            pieces.extend(overflow)
            continue
        pieces.append(_piece(cut, body_start, body_end, text, repeated))
    return pieces


def _html_table_text(open_tag: str, header_html: str, rows: list[str]) -> str:
    body = "".join(rows)
    # thead already wraps header rows; otherwise header is a bare <tr>
    return f"{open_tag}{header_html}{body}</table>"


def _is_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    cells = [cell for cell in cells if cell]
    return bool(cells) and all(_TABLE_SEP.fullmatch(cell.replace(" ", "")) for cell in cells)


def _table_text(header: str, separator: str | None, rows: list[str]) -> str:
    parts = [header]
    if separator is not None:
        parts.append(separator)
    parts.extend(rows)
    return "\n".join(parts)


def _split_prose(
    document: ChunkDocument,
    cut: SectionCut,
    start: int,
    end: int,
    level: int,
    max_tokens: int,
    overlap_tokens: int,
    tokenizer_name: str,
) -> tuple[list[SectionPiece], list[HardSplit]]:
    text = document.text[start:end]
    if count_tokens(text, tokenizer_name) <= max_tokens:
        return [_piece(cut, start, end, text, False)], []
    if level >= 3:
        return _split_tokens(document, cut, start, end, max_tokens, overlap_tokens, tokenizer_name)
    pattern = (_PARAGRAPHS, _LINES, _SENTENCES)[level]
    units = _units(text, pattern)
    if len(units) <= 1:
        return _split_prose(
            document, cut, start, end, level + 1, max_tokens, overlap_tokens, tokenizer_name
        )
    pieces: list[SectionPiece] = []
    notes: list[HardSplit] = []
    index = 0
    while index < len(units):
        unit_text = text[units[index][0] : units[index][1]]
        if count_tokens(unit_text, tokenizer_name) > max_tokens:
            part, part_notes = _split_prose(
                document,
                cut,
                start + units[index][0],
                start + units[index][1],
                level + 1,
                max_tokens,
                overlap_tokens,
                tokenizer_name,
            )
            pieces.extend(part)
            notes.extend(part_notes)
            index += 1
            continue
        finish = index + 1
        while finish < len(units):
            nxt = text[units[finish][0] : units[finish][1]]
            if count_tokens(nxt, tokenizer_name) > max_tokens:
                break
            joined = text[units[index][0] : units[finish][1]]
            if count_tokens(joined, tokenizer_name) > max_tokens:
                break
            finish += 1
        rel_start = units[index][0]
        rel_end = units[finish - 1][1]
        pieces.append(_piece(cut, start + rel_start, start + rel_end, text[rel_start:rel_end], False))
        if finish >= len(units):
            break
        overlap_at = finish - 1
        while overlap_at > index + 1 and count_tokens(
            text[units[overlap_at][0] : units[finish - 1][1]], tokenizer_name
        ) < overlap_tokens:
            overlap_at -= 1
        if overlap_at <= index:
            overlap_at = index + 1
        index = overlap_at
    return pieces, notes


def _units(text: str, pattern: re.Pattern[str]) -> list[tuple[int, int]]:
    spans = []
    cursor = 0
    for match in pattern.finditer(text):
        if match.start() > cursor:
            spans.append((cursor, match.start()))
        cursor = match.end()
    if cursor < len(text):
        spans.append((cursor, len(text)))
    return spans


def _split_tokens(
    document: ChunkDocument,
    cut: SectionCut,
    start: int,
    end: int,
    max_tokens: int,
    overlap_tokens: int,
    tokenizer_name: str,
) -> tuple[list[SectionPiece], list[HardSplit]]:
    text = document.text[start:end]
    spans = token_spans(text, tokenizer_name)
    note = HardSplit(cut.doc_id, start, end)
    if not spans:
        return [_piece(cut, start, end, text, False)], [note]
    pieces: list[SectionPiece] = []
    index = 0
    while index < len(spans):
        take = min(max_tokens, len(spans) - index)
        rel_start = 0 if index == 0 else spans[index][0]
        last = index + take - 1
        rel_end = len(text) if last + 1 >= len(spans) else spans[last + 1][0]
        pieces.append(_piece(cut, start + rel_start, start + rel_end, text[rel_start:rel_end], False))
        if index + take >= len(spans):
            break
        next_index = index + take - overlap_tokens
        if next_index <= index:
            next_index = index + 1
        index = next_index
    return pieces, [note]


def split_inside(
    document: ChunkDocument,
    piece: SectionPiece,
    *,
    max_tokens: int,
    overlap_tokens: int,
    tokenizer_name: str,
) -> list[SectionPiece]:
    """Режет уже готовый кусок внутри его границ, тем же способом, что длинный раздел."""
    exact = document.text[piece.char_start : piece.char_end]
    cut = SectionCut(
        piece.doc_id, piece.title_path, piece.char_start, piece.char_end, exact
    )
    # Повтор шапки таблицы: text ≠ срез документа — режем тело и снова оборачиваем.
    if piece.header_repeated:
        return _resplit_header_repeated(
            document, cut, piece, max_tokens, tokenizer_name
        )
    if piece.text != exact:
        raise ValueError(f"кусок {piece.doc_id} не совпадает со срезом документа")
    if _looks_like_html_table(exact) or _looks_like_gfm_table(exact):
        return _split_table(
            document, cut, piece.char_start, piece.char_end, max_tokens, tokenizer_name
        )
    parts, _notes = _split_prose(
        document,
        cut,
        piece.char_start,
        piece.char_end,
        0,
        max_tokens,
        overlap_tokens,
        tokenizer_name,
    )
    return parts


def _looks_like_gfm_table(text: str) -> bool:
    lines = [text[a:b] for a, b in _line_spans(text)]
    return _table_run(text, _line_spans(text), 0) >= 2 and _is_table_line(lines[0])


def _resplit_header_repeated(
    document: ChunkDocument,
    cut: SectionCut,
    piece: SectionPiece,
    max_tokens: int,
    tokenizer_name: str,
) -> list[SectionPiece]:
    """Дробит continuation-кусок таблицы (с уже повторённой шапкой) на меньшие ряды."""
    exact = document.text[piece.char_start : piece.char_end]
    if _HTML_TR.search(exact):
        open_m = _HTML_TABLE_OPEN.search(piece.text)
        open_tag = open_m.group(0) if open_m else "<table>"
        thead_m = _HTML_THEAD.search(piece.text)
        if thead_m:
            header_html = thead_m.group(0)
        else:
            first_tr = _HTML_TR.search(piece.text)
            header_html = first_tr.group(0) if first_tr else ""
        data_trs = list(_HTML_TR.finditer(exact))
        if not data_trs:
            return [piece]
        pieces: list[SectionPiece] = []
        index = 0
        while index < len(data_trs):
            taken: list[re.Match[str]] = []
            while index < len(data_trs):
                candidate_rows = [m.group(0) for m in taken + [data_trs[index]]]
                candidate = _html_table_text(open_tag, header_html, candidate_rows)
                if taken and count_tokens(candidate, tokenizer_name) > max_tokens:
                    break
                taken.append(data_trs[index])
                index += 1
                if count_tokens(candidate, tokenizer_name) > max_tokens:
                    break
            if not taken:
                taken = [data_trs[index]]
                index += 1
            body_start = piece.char_start + taken[0].start()
            body_end = piece.char_start + taken[-1].end()
            text = _html_table_text(
                open_tag, header_html, [m.group(0) for m in taken]
            )
            if (
                len(taken) == 1
                and count_tokens(text, tokenizer_name) > max_tokens
            ):
                row_text = document.text[body_start:body_end]
                overflow, _notes = _split_prose(
                    document,
                    cut,
                    body_start,
                    body_end,
                    0,
                    max_tokens,
                    0,
                    tokenizer_name,
                )
                # prose куски без повторной шапки: иначе снова не влезут
                pieces.extend(overflow if overflow else [
                    _piece(cut, body_start, body_end, row_text, False)
                ])
                continue
            pieces.append(_piece(cut, body_start, body_end, text, True))
        return pieces

    # GFM: шапка/сепаратор из piece.text, тело — срез документа
    wrapped_lines = [
        piece.text[a:b] for a, b in _line_spans(piece.text)
    ]
    if not wrapped_lines:
        return [piece]
    header = wrapped_lines[0]
    separator = (
        wrapped_lines[1]
        if len(wrapped_lines) > 1 and _is_separator(wrapped_lines[1])
        else None
    )
    body_lines = [exact[a:b] for a, b in _line_spans(exact)]
    positions = _line_spans(exact)
    pieces = []
    row = 0
    while row < len(body_lines):
        taken: list[int] = []
        while row < len(body_lines):
            candidate = _table_text(
                header, separator, [body_lines[i] for i in taken + [row]]
            )
            if taken and count_tokens(candidate, tokenizer_name) > max_tokens:
                break
            taken.append(row)
            row += 1
            if count_tokens(candidate, tokenizer_name) > max_tokens:
                break
        if not taken:
            taken = [row]
            row += 1
        body_start = piece.char_start + positions[taken[0]][0]
        body_end = piece.char_start + positions[taken[-1]][1]
        text = _table_text(header, separator, [body_lines[i] for i in taken])
        pieces.append(_piece(cut, body_start, body_end, text, True))
    return pieces


def _piece(
    cut: SectionCut,
    start: int,
    end: int,
    text: str,
    header_repeated: bool,
) -> SectionPiece:
    if start < cut.char_start or end > cut.char_end:
        raise ValueError(f"кусок {cut.doc_id} выходит за раздел")
    return SectionPiece(cut.doc_id, cut.title_path, start, end, text, header_repeated)
