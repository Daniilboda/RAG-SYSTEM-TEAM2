# -*- coding: utf-8 -*-
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

pdfmetrics.registerFont(TTFont("ArialRu", r"C:\Windows\Fonts\arial.ttf"))
pdfmetrics.registerFont(TTFont("ArialRu-Bold", r"C:\Windows\Fonts\arialbd.ttf"))

out = Path(__file__).resolve().parent / "llamaparse_raw_vs_clean.pdf"

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="TitleRu", fontName="ArialRu-Bold", fontSize=16, leading=20, spaceAfter=8
    )
)
styles.add(
    ParagraphStyle(
        name="H2Ru",
        fontName="ArialRu-Bold",
        fontSize=12,
        leading=16,
        spaceBefore=12,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyRu", fontName="ArialRu", fontSize=10, leading=14, spaceAfter=4
    )
)
styles.add(
    ParagraphStyle(
        name="SmallRu",
        fontName="ArialRu",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#555555"),
    )
)
styles.add(ParagraphStyle(name="CellRu", fontName="ArialRu", fontSize=8, leading=10))

doc = SimpleDocTemplate(
    str(out),
    pagesize=A4,
    leftMargin=18 * mm,
    rightMargin=18 * mm,
    topMargin=16 * mm,
    bottomMargin=16 * mm,
    title="LlamaParse: raw vs clean",
    author="RAG SYSTEM",
)

story = []
story.append(Paragraph("LlamaParse: raw vs clean", styles["TitleRu"]))
story.append(
    Paragraph(
        "Сравнение 22 MD: <b>llama_parse_md</b> (raw) vs <b>llama_parse_md_clean</b> "
        "после postprocess_md.py. Шум = barcode / e1cib / e-signature / "
        "signature|logo / unique key.",
        styles["BodyRu"],
    )
)
story.append(
    Paragraph("Источник: сравнение после постпроцесса · 2026-11-13", styles["SmallRu"])
)
story.append(Spacer(1, 6))
story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc")))
story.append(Spacer(1, 8))

story.append(Paragraph("Вердикт", styles["H2Ru"]))
story.append(
    Paragraph(
        "Clean убирает почти весь шум СЭД/ЭП: <b>172 → 2</b> маркера. "
        "Среднее сокращение размера файла ≈ <b>11.0%</b> (штампы, не таблицы). "
        "Остаточный шум в 2 документах (No1051, No368).",
        styles["BodyRu"],
    )
)

kpi = [
    ["Документов", "Шум raw / clean", "Avg chars removed", "Chars removed total"],
    ["22", "172 / 2", "11.0%", "25 727"],
]
t = Table(kpi, colWidths=[40 * mm, 45 * mm, 45 * mm, 45 * mm])
t.setStyle(
    TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, 0), "ArialRu-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "ArialRu"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )
)
story.append(t)

story.append(Paragraph("Корпус: totals", styles["H2Ru"]))
corp = [
    ["Метрика", "raw", "clean"],
    ["Noise markers", "172", "2"],
    ["Docs with residual noise", "21", "2"],
]
t2 = Table(corp, colWidths=[70 * mm, 50 * mm, 50 * mm])
t2.setStyle(
    TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, 0), "ArialRu-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "ArialRu"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )
)
story.append(t2)

story.append(Paragraph("Смесь шума в raw (сумма hits)", styles["H2Ru"]))
mix = [
    ["barcode", "e1cib", "signature:", "e-signature text", "unique key", "logo:"],
    ["85", "36", "18", "15", "11", "7"],
]
t3 = Table(mix, colWidths=[29 * mm] * 6)
t3.setStyle(
    TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, 0), "ArialRu-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "ArialRu"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )
)
story.append(t3)

story.append(Paragraph("По документам", styles["H2Ru"]))
story.append(
    Paragraph(
        "Зелёный = шум снят · Жёлтый = остаточный маркер в clean",
        styles["SmallRu"],
    )
)

rows = [
    ["Document", "Noise raw", "Noise clean", "% chars"],
    ["Grant support regulation", "60", "0", "9.4%"],
    ["1356 support measures", "20", "0", "12.8%"],
    ["Material support order", "15", "0", "8.3%"],
    ["No1424 norms", "9", "0", "18.1%"],
    ["No1051 support", "7", "1", "22.6%"],
    ["No1843 families", "7", "0", "21.5%"],
    ["No595 Kutepov", "7", "0", "22.5%"],
    ["No749 districts", "7", "0", "19.6%"],
    ["No368 stipends", "7", "1", "3.2%"],
    ["Stipend commissions", "7", "0", "5.0%"],
    ["No352 changes", "5", "0", "14.8%"],
    ["Stanis stipend", "4", "0", "8.6%"],
    ["Payment schedule", "3", "0", "47.7%"],
    ["No545 amendments", "3", "0", "5.3%"],
    ["Public certification", "3", "0", "2.7%"],
    ["No541", "3", "0", "9.8%"],
    ["Alfa Future Scholarships", "1", "0", "1.7%"],
    ["Alfa grants v5", "1", "0", "2.2%"],
    ["Discounts / support", "1", "0", "1.6%"],
    ["Social support / transfer", "1", "0", "1.9%"],
    ["No344 regulation", "1", "0", "0.6%"],
    ["Social stipend rules", "0", "0", "1.6%"],
]

data = [rows[0]]
for r in rows[1:]:
    data.append([Paragraph(r[0], styles["CellRu"]), r[1], r[2], r[3]])

t4 = Table(data, colWidths=[95 * mm, 28 * mm, 30 * mm, 25 * mm], repeatRows=1)
style_cmds = [
    ("FONTNAME", (0, 0), (-1, 0), "ArialRu-Bold"),
    ("FONTNAME", (1, 1), (-1, -1), "ArialRu"),
    ("FONTSIZE", (0, 0), (-1, 0), 8),
    ("FONTSIZE", (1, 1), (-1, -1), 8),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
]
for i, r in enumerate(rows[1:], start=1):
    noise_clean = int(r[2])
    noise_raw = int(r[1])
    if noise_clean == 0 and noise_raw > 0:
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#e8f5e9")))
    elif noise_clean > 0:
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fff8e1")))
t4.setStyle(TableStyle(style_cmds))
story.append(t4)

story.append(Spacer(1, 10))
story.append(Paragraph("Итог", styles["H2Ru"]))
story.append(
    Paragraph(
        "Для корпуса стипендий брать <b>llama_parse/llama_parse_md_clean</b> "
        "как основной MD. Raw LlamaParse ещё несёт шум СЭД/ЭП, который "
        "снимает postprocess_md.",
        styles["BodyRu"],
    )
)

doc.build(story)
print(out)
print("size_bytes", out.stat().st_size)
