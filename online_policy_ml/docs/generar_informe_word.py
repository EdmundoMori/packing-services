#!/usr/bin/env python3
"""Genera el informe de cierre RL online en Word (.docx) con índice."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn, nsmap
from docx.shared import Cm, Pt, RGBColor, Emu, Twips
from docx.enum.style import WD_STYLE_TYPE

OUT = Path(__file__).resolve().parent / "Informe_cierre_RL_online.docx"

NAVY = RGBColor(0x1F, 0x4E, 0x79)
BLUE = RGBColor(0x2E, 0x75, 0xB6)
GRAY = RGBColor(0x59, 0x59, 0x59)
DARK = RGBColor(0x2D, 0x2D, 0x2D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x37, 0x5A, 0x23)
HEADER_BG = "1F4E79"
ALT_BG = "D6E3F0"
WARN_BG = "FFF2CC"
OK_BG = "E2EFDA"


def set_run_font(run, name="Calibri", size=11, bold=False, italic=False, color=DARK):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = color


def set_cell_shading(cell, hex_color: str) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def set_cell_borders(cell, color="A6A6A6", sz="4") -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), sz)
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        tcBorders.append(el)
    tcPr.append(tcBorders)


def set_cell_text(cell, text, *, bold=False, color=DARK, size=10, align=WD_ALIGN_PARAGRAPH.LEFT, fill=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.08
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color)
    if fill:
        set_cell_shading(cell, fill)
    set_cell_borders(cell)
    cell.vertical_alignment = 1  # center


def shade_header_row(table, fill=HEADER_BG):
    for cell in table.rows[0].cells:
        for p in cell.paragraphs:
            for run in p.runs:
                run.font.color.rgb = WHITE
                run.bold = True
        set_cell_shading(cell, fill)


def add_table(doc, headers, rows, col_widths=None, header_fill=HEADER_BG):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for i, h in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], h, bold=True, color=WHITE, size=9, align=WD_ALIGN_PARAGRAPH.CENTER, fill=header_fill)
    for r_i, row in enumerate(rows):
        fill = ALT_BG if r_i % 2 == 1 else "FFFFFF"
        for c_i, val in enumerate(row):
            align = WD_ALIGN_PARAGRAPH.CENTER if c_i > 0 else WD_ALIGN_PARAGRAPH.LEFT
            set_cell_text(table.rows[r_i + 1].cells[c_i], str(val), size=9, align=align, fill=fill)
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return table


def prevent_widow(p):
    pPr = p._p.get_or_add_pPr()
    keep = OxmlElement("w:keepNext")
    pPr.append(keep)


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(text)
    set_run_font(run, size=9, italic=True, color=GRAY)


def add_body(doc, text, *, first_line=True):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.15
    if first_line:
        p.paragraph_format.first_line_indent = Cm(0.5)
    run = p.add_run(text)
    set_run_font(run, size=11)
    return p


def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.clear()
    p.paragraph_format.left_indent = Cm(1.0 + 0.5 * level)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.space_before = Pt(0)
    run = p.add_run(text)
    set_run_font(run, size=11)
    return p


def add_h1(doc, text):
    p = doc.add_heading(text, level=1)
    for run in p.runs:
        set_run_font(run, name="Calibri", size=16, bold=True, color=NAVY)
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)
    return p


def add_h2(doc, text):
    p = doc.add_heading(text, level=2)
    for run in p.runs:
        set_run_font(run, name="Calibri", size=13, bold=True, color=BLUE)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    return p


def add_h3(doc, text):
    p = doc.add_heading(text, level=3)
    for run in p.runs:
        set_run_font(run, name="Calibri", size=12, bold=True, color=RGBColor(0x5B, 0x9B, 0xD5))
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    return p


def add_quote(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(1.0)
    p.paragraph_format.right_indent = Cm(0.5)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(10)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    set_run_font(run, size=11, italic=True, color=NAVY)
    return p


def add_note(doc, title, text, fill=WARN_BG):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    cell.text = ""
    set_cell_shading(cell, fill)
    set_cell_borders(cell, color="BFBFBF")
    p1 = cell.paragraphs[0]
    r1 = p1.add_run(title)
    set_run_font(r1, size=10, bold=True, color=NAVY)
    p2 = cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r2 = p2.add_run(text)
    set_run_font(r2, size=10)
    doc.add_paragraph()


def add_page_number(paragraph):
    run = paragraph.add_run()
    fld1 = OxmlElement("w:fldChar")
    fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    run._r.append(fld1)
    run._r.append(instr)
    run._r.append(fld2)


def add_num_pages(paragraph):
    run = paragraph.add_run()
    fld1 = OxmlElement("w:fldChar")
    fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " NUMPAGES "
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    run._r.append(fld1)
    run._r.append(instr)
    run._r.append(fld2)


def enable_update_fields(doc):
    settings = doc.settings.element
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)


def add_toc_field(paragraph):
    """Campo TOC de Word (se actualiza al abrir o con clic derecho)."""
    run = paragraph.add_run()
    r = run._r
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "Haga clic derecho y elija «Actualizar campo» para numerar las páginas."
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r.append(fld_begin)
    r.append(instr)
    r.append(fld_sep)
    r.append(placeholder)
    r.append(fld_end)


def add_toc_entry(doc, number, title, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.15
    left = 0.0 if level == 1 else (0.6 if level == 2 else 1.2)
    p.paragraph_format.left_indent = Cm(left)
    tab_stops = p.paragraph_format.tab_stops
    tab_stops.add_tab_stop(Cm(16.0), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
    label = f"{number}  {title}" if number else title
    run = p.add_run(label)
    set_run_font(run, size=12 if level == 1 else 11, bold=(level == 1), color=NAVY if level == 1 else DARK)
    return p


def set_heading_outline(style, level):
    pPr = style.element.get_or_add_pPr()
    outline = OxmlElement("w:outlineLvl")
    outline.set(qn("w:val"), str(level))
    pPr.append(outline)


def configure_styles(doc):
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.font.color.rgb = DARK
    pf = normal.paragraph_format
    pf.space_after = Pt(8)
    pf.line_spacing = 1.15

    for name, size, color, outline in (
        ("Heading 1", 16, NAVY, 0),
        ("Heading 2", 13, BLUE, 1),
        ("Heading 3", 12, RGBColor(0x5B, 0x9B, 0xD5), 2),
    ):
        st = styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = color
        st.font.color.theme_color = None
        set_heading_outline(st, outline)

    for sname in ("Header", "Footer"):
        try:
            st = styles[sname]
            st.font.name = "Calibri"
            st.font.size = Pt(9)
            st.font.color.rgb = GRAY
        except KeyError:
            pass


def add_header_footer(doc):
    section = doc.sections[0]
    header = section.header
    header.is_linked_to_previous = False
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = hp.add_run("packing-services  ·  Informe de cierre RL online  ·  15 septiembre 2026")
    set_run_font(r, size=8, color=GRAY)

    footer = section.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = fp.add_run("Confidencial — uso interno  ·  Página ")
    set_run_font(r1, size=8, color=GRAY)
    add_page_number(fp)
    r2 = fp.add_run(" de ")
    set_run_font(r2, size=8, color=GRAY)
    add_num_pages(fp)


def build():
    doc = Document()
    configure_styles(doc)
    enable_update_fields(doc)

    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.4)
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.2)
    section.header_distance = Cm(1.0)
    section.footer_distance = Cm(1.0)
    add_header_footer(doc)

    # ── Portada ──────────────────────────────────────────────────────────
    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("PACKING-SERVICES")
    set_run_font(r, size=12, bold=True, color=BLUE)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(28)
    r = p.add_run("INFORME DE CIERRE")
    set_run_font(r, size=28, bold=True, color=NAVY)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    r = p.add_run("Subproyecto de política de aprendizaje por refuerzo online")
    set_run_font(r, size=16, color=BLUE)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("online_policy_ml  ·  encoder v1  ·  mlp_v1_p1s1_ppo.pt")
    set_run_font(r, size=12, italic=True, color=GRAY)

    # barra
    bar = doc.add_table(rows=1, cols=1)
    bar.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = bar.rows[0].cells[0]
    set_cell_shading(c, "1F4E79")
    c.paragraphs[0].text = ""
    c.width = Cm(14)

    doc.add_paragraph()

    meta = [
        ("Fecha", "15 de septiembre de 2026"),
        ("Versión del informe", "1.0 — cierre de ciclo (corrida relanzada 14–15 sep 2026)"),
        ("Universo de producto", "Fases 1–2 · packing-services · policy=rl · p=1 s=1"),
        ("Universo de comparación", "Fases 3–4 · Zhao ICLR 2022 / PCT · BED-BPP O3DBP"),
        ("Checkpoint de API", "mlp_v1_p1s1_ppo.pt  (equivale a BC: best_epoch=0)"),
        ("Fuente de cifras", "JSON de artifacts/reports de esta corrida (no informes PPO anteriores)"),
        ("Clasificación", "Interno / técnico"),
    ]
    t = doc.add_table(rows=len(meta), cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate(meta):
        set_cell_text(t.rows[i].cells[0], k, bold=True, color=WHITE, size=10, fill=HEADER_BG)
        set_cell_text(t.rows[i].cells[1], v, size=10, fill="F2F2F2")
        t.rows[i].cells[0].width = Cm(5.2)
        t.rows[i].cells[1].width = Cm(11.0)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(
        "Este documento sustituye la hoja de ruta de cierre. "
        "Cierra el ciclo de construcción de la política aprendida; no cierra el producto packing-services."
    )
    set_run_font(r, size=10, italic=True, color=GRAY)

    doc.add_page_break()

    # ── Índice ───────────────────────────────────────────────────────────
    add_h1(doc, "Índice")
    add_body(
        doc,
        "El índice siguiente es el cuerpo del informe. Al abrir el archivo en Microsoft Word, "
        "puede actualizar el campo de tabla de contenidos (clic derecho → Actualizar campo) "
        "para añadir numeración de páginas automática.",
        first_line=False,
    )

    toc = [
        ("1.", "Resumen ejecutivo", 1),
        ("2.", "Alcance y objeto del cierre", 1),
        ("2.1.", "Qué cierra este informe", 2),
        ("2.2.", "Qué no cierra", 2),
        ("2.3.", "Invariantes del ciclo", 2),
        ("3.", "Contexto y decisiones de diseño", 1),
        ("3.1.", "Encoder y arquitectura de la red", 2),
        ("3.2.", "Maestro: de privileged_volume_ep a receding_horizon_ep", 2),
        ("3.3.", "Dos universos de evaluación", 2),
        ("3.4.", "Archivo versions/v1 y versions/v2", 2),
        ("4.", "Protocolo experimental", 1),
        ("4.1.", "Fuente de datos y splits", 2),
        ("4.2.", "Holdout de producto bloqueado", 2),
        ("4.3.", "Receta de producción (p=1, s=1)", 2),
        ("4.4.", "Métricas: producto, Zhao y Kagerer", 2),
        ("5.", "Fase 1 — Datos, imitación y PPO", 1),
        ("5.1.", "Splits (notebook 01)", 2),
        ("5.2.", "Transiciones (notebook 02)", 2),
        ("5.3.", "Validación de imitación BC (notebook 03)", 2),
        ("5.4.", "Compuerta del maestro (notebook 04)", 2),
        ("5.5.", "PPO sobre el actor BC (notebook 05)", 2),
        ("6.", "Fase 2 — Producto packing-services", 1),
        ("6.1.", "Holdout de producto (notebook 06)", 2),
        ("6.2.", "Consolidación first-fit (notebook 07)", 2),
        ("6.3.", "Execute de API (notebook 08)", 2),
        ("6.4.", "Contrato pytest", 2),
        ("7.", "Marco de comparación: Zhao, Yu y Xu (ICLR 2022)", 1),
        ("7.1.", "PCT y el bin cerrado", 2),
        ("7.2.", "Settings 1, 2 y 3", 2),
        ("7.3.", "Uti. y Num. frente a ηutil de Kagerer", 2),
        ("7.4.", "BED-BPP y el packing plan publicado", 2),
        ("8.", "Fase 3 — Homologación", 1),
        ("8.1.", "Pedido fijo y condiciones a priori", 2),
        ("8.2.", "Resultados en 00100408", 2),
        ("8.3.", "Límite del plan LFS de PCT", 2),
        ("9.", "Fase 4 — Comparación y veredicto", 1),
        ("9.1.", "Tabla de comparabilidad", 2),
        ("9.2.", "Veredicto", 2),
        ("9.3.", "Alcance y no-afirmaciones", 2),
        ("10.", "Uso en packing-services", 1),
        ("11.", "Limitaciones y trabajo no realizado", 1),
        ("12.", "Conclusiones", 1),
        ("13.", "Referencias", 1),
        ("14.", "Anexos", 1),
        ("A.", "Rutas de artefactos de esta corrida", 2),
        ("B.", "Notebooks del ciclo", 2),
        ("C.", "Glosario", 2),
        ("D.", "Control de versiones del informe", 2),
    ]
    for num, title, lvl in toc:
        add_toc_entry(doc, num, title, lvl)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    add_toc_field(p)

    doc.add_page_break()

    # ── 1. Resumen ejecutivo ─────────────────────────────────────────────
    add_h1(doc, "1. Resumen ejecutivo")
    add_body(
        doc,
        "Se construyó otro motor online para packing-services, no un packer óptimo. "
        "La red solo puntúa candidatas ya legales del bucle EP (empty-maximal-space). "
        "El default de API es mlp_v1_p1s1_ppo.pt, con policy=rl, lookahead p=1 y selección s=1, "
        "porque es la única política aprendida expuesta — no porque superara al heurístico de producción.",
        first_line=False,
    )
    add_body(
        doc,
        "El PPO de esta corrida eligió best_epoch=0: el actor exportado es el de imitación "
        "(mlp_v1_p1s1.pt). En validación, la utilización bajó a lo largo de los epochs PPO "
        "(0,6875 → 0,662). STEP y shaping no se promocionan. La cinta p=3 s=2 (mlp_v1_p3s2.pt) "
        "existe como artefacto, no como default.",
    )
    add_body(
        doc,
        "En el holdout de producto (cinco pedidos nunca vistos en train/tune), el PPO y el "
        "heurístico empatan: Δ(PPO − H) = −0,0014 con IC95 [−0,025, +0,019], que cruza cero. "
        "No se declara victoria de producto. El execute multi-palé con consolidate first-fit "
        "reduce 30 → 24 palés en el sello v3 y replica el registro 07.",
    )
    add_body(
        doc,
        "La comparación con PCT (Zhao, Yu y Xu, ICLR 2022) se hizo en el marco del paper: "
        "online 3D-BPP, un bin cerrado de 1 200 × 800 × 2 000 mm, Uti. = volumen contenido / "
        "volumen del bin, Num. = ítems contenidos. Pedido homologado: 00100408. En esas "
        "condiciones, mlp_v1_p1s1_ppo.pt supera a PCT porque nuestra solución es factible "
        "(hn = 1,97 m) y el packing publicado de PCT no lo es (hn = 2,105 m). En Zhao, una "
        "colocación fuera del bin no es solución. No hay Uti. head-to-head: el plan LFS de PCT "
        "no está materializado. El veredicto no es ranking BED-BPP ni copia de las tablas ICLR "
        "en bins 10 × 10 × 10.",
    )

    add_h2(doc, "Hallazgos que deciden")
    add_table(
        doc,
        ["Ámbito", "Resultado", "Qué no implica"],
        [
            [
                "Holdout de producto (n=5)",
                "Empate PPO vs heurístico (Δ −0,0014; IC cruza 0)",
                "Victoria de RL en packing-services",
            ],
            [
                "PPO vs BC",
                "best_epoch=0: el .pt de API es el actor BC",
                "Que el bucle PPO mejorara utilización",
            ],
            [
                "Multi-palé (sello v3)",
                "30 → 24 palés; execute = 07 consolidado",
                "Reentrenamiento; cambio de p/s",
            ],
            [
                "Zhao / PCT en 00100408",
                "Supera por factibilidad (hn 1,97 vs 2,105 m)",
                "Ranking BED-BPP, Σalgo, Table 1 10×10×10",
            ],
        ],
        col_widths=[4.2, 6.4, 5.6],
    )
    add_caption(doc, "Tabla 1. Hallazgos decisores del cierre.")

    # ── 2. Alcance ───────────────────────────────────────────────────────
    add_h1(doc, "2. Alcance y objeto del cierre")
    add_h2(doc, "2.1. Qué cierra este informe")
    add_body(
        doc,
        "Cierra el ciclo de construcción de una política aprendida sobre el encoder v1 y "
        "run_online_loop: splits, transiciones, imitación, PPO, evaluación de holdout, "
        "consolidación multi-palé, homologación con el marco Zhao y el veredicto puntual "
        "frente a PCT en BED-BPP. Cierra también el .pt de API y la documentación viva que "
        "apuntaba a la hoja de ruta de cierre (sustituida por este informe).",
        first_line=False,
    )
    add_bullet(doc, "Producto packing-services: motor online con checkpoint mlp_v1_p1s1_ppo.pt.")
    add_bullet(doc, "Comparación puntual vs PCT (Zhao et al., ICLR 2022) en un pedido homologado.")
    add_bullet(doc, "Trazabilidad de la corrida: notebooks 01–10 y JSON en artifacts/reports.")

    add_h2(doc, "2.2. Qué no cierra")
    add_body(
        doc,
        "No cierra el producto packing-services. El execute sigue existiendo. El catálogo de "
        "31 motores, el packing offline y run_online_loop como infraestructura no se tocaron. "
        "No se introduce el algoritmo 32. No se promociona FEATURE_VERSION=2. No se envía "
        "submit al leaderboard BED-BPP ni se corre Blender / Σalgo.",
        first_line=False,
    )

    add_h2(doc, "2.3. Invariantes del ciclo")
    add_body(
        doc,
        "Las invariantes se fijaron a priori y se mantuvieron en toda la corrida. Romperlas "
        "habría invalidado el loader de API, el holdout o el marco Zhao.",
        first_line=False,
    )
    add_table(
        doc,
        ["Invariante", "Valor", "Por qué"],
        [
            ["FEATURE_VERSION", "1", "El loader de API espera el encoder v1"],
            ["FEATURE_DIM", "35", "Linear(35, 64) → ReLU → Linear(64, 1)"],
            ["Holdout nunca en train/tune", "00100001–00100004, 00100408", "Evaluación de producto no contaminada"],
            ["Europalé", "1 200 × 800 × 2 000 mm", "Bin de packing-services y de Zhao en BED-BPP"],
            ["Algoritmo 32", "no existe", "No se añade un motor paralelo al catálogo"],
            ["Offline / run_online_loop", "sin tocar", "El bucle EP sigue siendo la fuente de candidatas"],
            ["Semilla de splits", "42", "Reproducibilidad de WORKING_STRATEGY=random"],
        ],
        col_widths=[4.5, 5.5, 6.2],
    )
    add_caption(doc, "Tabla 2. Invariantes del ciclo de cierre.")

    # ── 3. Contexto ──────────────────────────────────────────────────────
    add_h1(doc, "3. Contexto y decisiones de diseño")
    add_h2(doc, "3.1. Encoder y arquitectura de la red")
    add_body(
        doc,
        "El encoder v1 proyecta cada candidata legal a un vector de 35 dimensiones. La red "
        "es un MLP pequeño: capa lineal 35→64, ReLU, capa lineal 64→1 (score). No hay "
        "heightmap, no hay FEATURE_VERSION=2, no hay transformer. El modelo no genera "
        "colocaciones: elige entre las que el bucle EP ya declaró legales (contención, "
        "no solape, apoyo). Si el bucle no ofrece una candidata, la red no puede inventarla.",
        first_line=False,
    )
    add_body(
        doc,
        "Esa arquitectura explica dos hechos del cierre. Primero, el techo de utilización "
        "está acotado por el generador de candidatas, no por la capacidad del MLP. Segundo, "
        "imitar al maestro o hacer PPO sobre el mismo espacio de acciones no puede superar "
        "a un heurístico que recorre el mismo espacio con otra regla de puntuación, salvo "
        "que la red aprenda un ranking sistemáticamente mejor — cosa que el holdout no muestra.",
    )

    add_h2(doc, "3.2. Maestro: de privileged_volume_ep a receding_horizon_ep")
    add_body(
        doc,
        "Una primera pista usó el maestro privileged_volume_ep. Esa etiqueta es tautológica: "
        "la regla cierra cerca del 100 % porque el maestro ve información que el actor online "
        "no tiene. El accuracy de imitación no medía empaquetar; medía reconstruir una etiqueta "
        "cerrada. Se sustituyó por receding_horizon_ep, un maestro que puntúa con horizonte "
        "recedente dentro del mismo bucle EP. Toda la corrida de cierre (01–05) usa ese maestro.",
        first_line=False,
    )
    add_note(
        doc,
        "Decisión de diseño.",
        "El accuracy BC (~0,33–0,36 en val) no se interpreta como calidad de packing. "
        "La métrica de producto es volume_utilization del execute, no el acierto de imitación.",
        fill=ALT_BG,
    )

    add_h2(doc, "3.3. Dos universos de evaluación")
    add_body(
        doc,
        "El cierre distingue dos universos que no se mezclan. Las fases 1 y 2 construyen y "
        "evalúan el motor de packing-services: un palé (o varios con consolidate), métrica "
        "volume_utilization de producto, holdout de cinco pedidos. Las fases 3 y 4 comparan "
        "con PCT bajo el protocolo Zhao: bin cerrado, Uti./Num., pedido 00100408, O3DBP p=1 s=1. "
        "El cubo del notebook 06 no declara gana/empata/pierde vs PCT. El veredicto Zhao no "
        "promociona el default de API.",
        first_line=False,
    )

    add_h2(doc, "3.4. Archivo versions/v1 y versions/v2")
    add_body(
        doc,
        "versions/v1 y versions/v2 se conservan como archivo: imitación histórica y recetas "
        "PPO 3 y 4 no promocionadas. No se ejecutan en este cierre. Los eval_*.md vivos, si "
        "existían, quedan sustituidos por este informe. La corrida que cuenta es la relanzada "
        "el 14–15 de septiembre de 2026 (semilla 42, holdout bloqueado).",
        first_line=False,
    )

    # ── 4. Protocolo ─────────────────────────────────────────────────────
    add_h1(doc, "4. Protocolo experimental")
    add_h2(doc, "4.1. Fuente de datos y splits")
    add_body(
        doc,
        "Fuente: bed-bpp_v1.json (BED-BPP, 10 003 pedidos). Splits full con semilla 42: "
        "train 6 999 / val 1 500 / test 1 499. El trabajo de esta corrida no usa el full: "
        "usa el working set (24 / 8 / 8) para 01–05 y el scale set (80 / 20 / 20) como "
        "reserva no promocionada. WORKING_STRATEGY=random. Los cinco IDs de holdout de "
        "producto se excluyen de todos los splits de entrenamiento y ajuste.",
        first_line=False,
    )
    add_table(
        doc,
        ["Conjunto", "Train", "Val", "Test", "Uso en esta corrida"],
        [
            ["Full", "6 999", "1 500", "1 499", "Marco; no se entrena el full"],
            ["Working", "24", "8", "8", "Transiciones, BC, PPO, val/test de 03"],
            ["Scale", "80", "20", "20", "Reserva; no promocionado"],
            ["Holdout producto", "—", "—", "5 pedidos", "Solo 06, 07, 08 y homologación 09/10"],
        ],
    )
    add_caption(doc, "Tabla 3. Tamaños de split (semilla 42).")

    add_h2(doc, "4.2. Holdout de producto bloqueado")
    add_body(
        doc,
        "Los pedidos 00100001, 00100002, 00100003, 00100004 y 00100408 no entran en train "
        "ni en tune. 00100408 es además el pedido de homologación Zhao (fases 3–4). El smoke "
        "del notebook 03 sobre 00100408 es una comprobación de que el execute no rompe; no "
        "es ajuste. Cualquier cifra de holdout anterior a esta corrida no se copia.",
        first_line=False,
    )

    add_h2(doc, "4.3. Receta de producción (p=1, s=1)")
    add_body(
        doc,
        "Lookahead p=1 y selección s=1: el actor ve el ítem actual y elige una de las "
        "candidatas legales inmediatas. Es la receta 2 de volumen-denso y el default de API. "
        "p=3 s=2 (cinta, más opciones por transición) se entrenó y se validó en un subconjunto; "
        "no se mezcla en el default. El PPO usó lr=1e−4, rollouts=2, gamma=0,99, kl_coef=0,02, "
        "support_coef=0,15, height_coef=0,15, modo place, inicialización desde el BC p=1 s=1.",
        first_line=False,
    )

    add_h2(doc, "4.4. Métricas: producto, Zhao y Kagerer")
    add_body(
        doc,
        "Tres jueces distintos. Mezclarlos produce veredictos falsos.",
        first_line=False,
    )
    add_table(
        doc,
        ["Métrica", "Definición", "Dónde se usa", "No se usa para"],
        [
            [
                "volume_utilization (producto)",
                "Volumen empaquetado / volumen del palé de packing-services",
                "Notebooks 03, 06, 07, 08; API",
                "Veredicto vs PCT",
            ],
            [
                "Uti. Zhao",
                "Volumen de ítems contenidos en el bin / volumen del bin cerrado",
                "Fases 3–4",
                "Default de API; ηutil",
            ],
            [
                "Num. Zhao",
                "Número de ítems contenidos en el bin",
                "Fases 3–4",
                "Ítems «apilados» si hn > 2 m",
            ],
            [
                "ηutil Kagerer",
                "V / (A_pallet × hn), ortoedro de huella × altura neta",
                "Columna auxiliar en 09/10",
                "Juez Zhao; Table 1 ICLR",
            ],
        ],
        col_widths=[3.8, 5.2, 3.6, 3.6],
    )
    add_caption(doc, "Tabla 4. Métricas y su jurisdicción.")

    add_note(
        doc,
        "Contención Zhao.",
        "Uti. y Num. solo cuentan ítems estrictamente dentro del bin 1 200 × 800 × 2 000 mm. "
        "Si hn > 2 m, la solución no es factible: no hay Uti. de Table 1. Ignorar la contención "
        "y reportar el volumen de los 26 ítems del pedido no es el protocolo del paper.",
        fill=WARN_BG,
    )

    # ── 5. Fase 1 ────────────────────────────────────────────────────────
    add_h1(doc, "5. Fase 1 — Datos, imitación y PPO")
    add_h2(doc, "5.1. Splits (notebook 01)")
    add_body(
        doc,
        "El notebook 01 materializó los IDs working y scale, bloqueó el holdout y dejó el "
        "sello 01_splits.json. IDs de train working (24): 00100463, 00101060, 00101462, "
        "00101694, 00101750, 00101904, 00101960, 00102415, 00102791, 00102884, 00104471, "
        "00104763, 00105094, 00105561, 00106336, 00106775, 00106895, 00106942, 00107147, "
        "00107701, 00108482, 00108624, 00108712, 00109288. Val (8): 00101450, 00101506, "
        "00104020, 00104335, 00105244, 00106072, 00106539, 00109074. Test (8): 00100303, "
        "00102258, 00104208, 00105871, 00106522, 00106627, 00107096, 00109799.",
        first_line=False,
    )

    add_h2(doc, "5.2. Transiciones (notebook 02)")
    add_body(
        doc,
        "Se generaron transiciones con maestro receding_horizon_ep, FEATURE_VERSION=1, "
        "FEATURE_DIM=35. Tasa de etiquetas = 1,0 en todos los splits. El holdout de producto "
        "quedó excluido.",
        first_line=False,
    )
    add_table(
        doc,
        ["Split", "p, s", "Pedidos", "Transiciones", "Opciones (media)", "Empaquetados (media)", "Tiempo (s)"],
        [
            ["train", "1, 1", "24", "1 006", "39,99", "41,92", "716"],
            ["val", "1, 1", "8", "356", "29,14", "44,50", "199"],
            ["test", "1, 1", "8", "429", "48,29", "53,62", "942"],
            ["train", "3, 2", "24", "1 011", "81,36", "42,12", "1 266"],
            ["val", "3, 2", "8", "360", "72,09", "45,00", "396"],
            ["test", "3, 2", "8", "422", "133,38", "52,75", "2 131"],
        ],
    )
    add_caption(doc, "Tabla 5. Transiciones generadas (02_transitions.json).")
    add_body(
        doc,
        "p=3 s=2 duplica o triplica el número medio de opciones por transición. Eso encarece "
        "el maestro y el PPO; no se usó para el default de API.",
        first_line=False,
    )

    add_h2(doc, "5.3. Validación de imitación BC (notebook 03)")
    add_body(
        doc,
        "Se entrenó un lineal (linear_v1.json) y dos MLP (p=1 s=1 y p=3 s=2). El lineal "
        "alcanzó accuracy train 0,349 / val 0,362. El MLP p=1 s=1 se seleccionó por val_loss "
        "(best_epoch=3, best_val_acc=0,334, lr=0,001). El MLP p=3 s=2: best_epoch=4, "
        "best_val_acc=0,322, lr=0,0003. Hidden size = 64.",
        first_line=False,
    )
    add_body(
        doc,
        "La métrica que importa en 03 no es el accuracy: es volume_utilization sobre val y test "
        "del working set, con el heurístico como referencia. Todos los motores reportaron "
        "valid=1,0 (soluciones legales).",
    )
    add_table(
        doc,
        ["Conjunto", "Motor", "n", "Utilización", "Ítems (media)", "s (media)"],
        [
            ["val p=1 s=1", "Heurístico", "8", "0,6826", "44,75", "2,07"],
            ["val p=1 s=1", "linear_v1.json", "8", "0,6671", "44,13", "2,08"],
            ["val p=1 s=1", "mlp_v1_p1s1.pt", "8", "0,6865", "44,63", "2,09"],
            ["val p=1 s=1", "placeholder linear JSON", "8", "0,6873", "45,00", "2,06"],
            ["test p=1 s=1", "Heurístico", "8", "0,6714", "54,13", "5,66"],
            ["test p=1 s=1", "linear_v1.json", "8", "0,6663", "53,88", "6,26"],
            ["test p=1 s=1", "mlp_v1_p1s1.pt", "8", "0,6679", "54,13", "4,47"],
            ["test p=1 s=1", "placeholder linear JSON", "8", "0,6660", "53,50", "5,67"],
            ["val p=3 s=2 (subconj.)", "Heurístico", "3", "0,6951", "39,67", "222"],
            ["val p=3 s=2 (subconj.)", "linear_v1.json", "3", "0,7057", "40,33", "2,88"],
            ["val p=3 s=2 (subconj.)", "mlp_v1_p3s2.pt", "3", "0,7010", "39,33", "2,23"],
            ["val p=3 s=2 (subconj.)", "placeholder linear JSON", "3", "0,6917", "39,67", "2,76"],
        ],
    )
    add_caption(doc, "Tabla 6. Utilización de producto en val/test working (03_validacion.json).")
    add_body(
        doc,
        "En val p=1 s=1 el MLP iguala o supera ligeramente al heurístico (0,6865 vs 0,6826). "
        "En test p=1 s=1 el heurístico vuelve a estar por delante (0,6714 vs 0,6679). El "
        "placeholder examples/online_policy_linear_v1.json no es producción: aparece como "
        "control. p=3 s=2 se midió en n=3; no se promociona.",
        first_line=False,
    )

    add_h2(doc, "5.4. Compuerta del maestro (notebook 04)")
    add_body(
        doc,
        "La compuerta compara el maestro receding_horizon_ep, el heurístico y el MLP p=1 s=1 "
        "sobre los ocho pedidos de val, para verificar que el maestro no es tautológico y que "
        "el actor BC está en el mismo orden de magnitud. El sello 04_compuerta_maestro.json "
        "documenta volume_utilization, ítems empaquetados y validez por pedido. La compuerta "
        "no elige el default de API; elige si se puede pasar a PPO sin un maestro cerrado.",
        first_line=False,
    )

    add_h2(doc, "5.5. PPO sobre el actor BC (notebook 05)")
    add_body(
        doc,
        "El PPO se inicializó con mlp_v1_p1s1.pt. Seis epochs. La utilización de validación "
        "del actor inicial (epoch 0, no listado como epoch de entrenamiento) es 0,6874582, "
        "el mejor valor de la corrida. A partir del epoch 1 la val_util desciende de forma "
        "monótona en tendencia: 0,6863; 0,6844; 0,6765; 0,6783; 0,6649; 0,6618. El criterio "
        "de selección eligió best_epoch=0: se exporta el actor BC, no un actor PPO posterior.",
        first_line=False,
    )
    add_table(
        doc,
        ["Epoch", "Reward train", "Val util", "Policy loss", "Value loss", "Entropía", "KL"],
        [
            ["0 (BC, seleccionado)", "—", "0,6875", "—", "—", "—", "—"],
            ["1", "1,390", "0,6863", "+7,2e−4", "0,337", "2,612", "0,0055"],
            ["2", "1,451", "0,6844", "−2,4e−4", "0,342", "2,613", "0,0087"],
            ["3", "1,437", "0,6765", "−7,0e−4", "0,330", "2,687", "0,026"],
            ["4", "1,432", "0,6783", "−1,3e−3", "0,318", "2,712", "0,052"],
            ["5", "1,495", "0,6649", "−8,5e−4", "0,384", "2,710", "0,083"],
            ["6", "1,511", "0,6618", "−6,4e−4", "0,356", "2,740", "0,113"],
        ],
    )
    add_caption(doc, "Tabla 7. Historia PPO (05_rl_ppo.json). El actor exportado es el epoch 0.")
    add_body(
        doc,
        "La KL crece (0,005 → 0,113) y la val_util cae. El bucle de PPO no mejoró packing "
        "en este working set. Por eso mlp_v1_p1s1_ppo.pt es, en pesos, mlp_v1_p1s1.pt. El "
        "nombre «ppo» en la API documenta el ciclo de entrenamiento, no una ganancia PPO.",
        first_line=False,
    )
    add_note(
        doc,
        "Implicación para el producto.",
        "Exponer mlp_v1_p1s1_ppo.pt como default es correcto como «única política aprendida "
        "en el ciclo». Es incorrecto presentarlo como un actor PPO que bate a BC o al heurístico.",
        fill=WARN_BG,
    )

    # ── 6. Fase 2 ────────────────────────────────────────────────────────
    add_h1(doc, "6. Fase 2 — Producto packing-services")
    add_h2(doc, "6.1. Holdout de producto (notebook 06)")
    add_body(
        doc,
        "Cinco pedidos, un palé, p=1 s=1, métrica volume_utilization de producto. Comparación "
        "apareada heurístico vs PPO. Todas las soluciones son válidas. n=5 es pequeño: el "
        "intervalo de confianza se reporta precisamente para no convertir una diferencia de "
        "una milésima en victoria.",
        first_line=False,
    )
    add_table(
        doc,
        ["Pedido", "Ítems", "H util", "H empaq.", "PPO util", "PPO empaq.", "Δ (PPO−H)"],
        [
            ["00100001", "44", "0,693342", "41", "0,697387", "41", "+0,004045"],
            ["00100002", "38", "0,705614", "35", "0,662963", "33", "−0,042651"],
            ["00100003", "34", "0,681261", "27", "0,712995", "28", "+0,031734"],
            ["00100004", "58", "0,614189", "58", "0,614189", "58", "0"],
            ["00100408", "26", "0,646376", "26", "0,646376", "26", "0"],
            ["Media / suma", "200", "0,668156", "187", "0,666782", "186", "−0,001374"],
        ],
    )
    add_caption(doc, "Tabla 8. Holdout de producto pedido a pedido (06_evaluar_holdout.json).")
    add_body(
        doc,
        "El apareamiento da 2 victorias PPO (00100001, 00100003), 1 derrota (00100002) y "
        "2 empates (00100004, 00100408). La media Δ(PPO − H) = −0,001374. IC95 "
        "[−0,02478, +0,01904], p=1,0, significant=false: cruza cero. Empate. No se declara "
        "victoria. n=5 es insuficiente para un ranking; el intervalo se reporta para no "
        "convertir una milésima en decisión de producto.",
        first_line=False,
    )

    add_h2(doc, "6.2. Consolidación first-fit (notebook 07)")
    add_body(
        doc,
        "Sin reentrenar. Mismos pesos. El sello v3 del registro aplica first-fit cuando hay "
        "dos o más contenedores: 30 → 24 palés, utilización 0,372548 → 0,498604, cero ítems "
        "fuera. La consolidación es un post-proceso de asignación a contenedores, no una "
        "política nueva. Paso A del registro v3 documenta ese cierre.",
        first_line=False,
    )

    add_h2(doc, "6.3. Execute de API (notebook 08)")
    add_body(
        doc,
        "El execute de packing-services (paso C del sello v3) iguala al 07 consolidado: "
        "24 palés, misma utilización, paso_c_exitoso = true. Eso cierra el contrato de "
        "producto: lo que el notebook consolida es lo que la API entrega con consolidate "
        "activo (default si hay 2+ contenedores; se puede forzar consolidate=false).",
        first_line=False,
    )

    add_h2(doc, "6.4. Contrato pytest")
    add_body(
        doc,
        "La batería de contrato del motor aprendido quedó en verde. Dos skips esperados: el "
        ".pt ya existía (no se regenera en el test de presencia). FastAPI emitió "
        "StarletteDeprecationWarning no bloqueante. El pytest no sustituye al holdout: "
        "comprueba que el loader Linear(35,64) carga el checkpoint y que el execute responde.",
        first_line=False,
    )

    # ── 7. Marco Zhao ────────────────────────────────────────────────────
    add_h1(doc, "7. Marco de comparación: Zhao, Yu y Xu (ICLR 2022)")
    add_h2(doc, "7.1. PCT y el bin cerrado")
    add_body(
        doc,
        "PCT (Packing Configuration Tree) es un método de DRL para 3D-BPP online. El paper "
        "de Zhao, Yu y Xu (ICLR 2022) evalúa en un bin cerrado: las cajas tienen que caber "
        "en las tres dimensiones. Uti. es el volumen de lo contenido dividido por el volumen "
        "del bin. Num. es el recuento de ítems contenidos. Una colocación con hn mayor que "
        "la altura del bin no es una fila de Table 1: no es solución.",
        first_line=False,
    )
    add_body(
        doc,
        "Este cierre toma ese marco como juez de las fases 3 y 4, no como fuente de una "
        "métrica auxiliar. No se copian las tablas ICLR en bins discretos 10 × 10 × 10: "
        "el producto y BED-BPP usan europalé métrico 1 200 × 800 × 2 000 mm.",
    )

    add_h2(doc, "7.2. Settings 1, 2 y 3")
    add_body(
        doc,
        "Zhao define tres settings de observabilidad. Setting 1: se conoce solo el ítem "
        "actual. Setting 2: se conoce una ventana de próximos ítems (lookahead). Setting 3: "
        "se conoce la secuencia completa. El default de producto (p=1 s=1) corresponde a "
        "Setting 2 mínimo más la cota de peso de packing-services (max_weight). No se afirma "
        "identidad formal con la implementación de PCT; se afirma la misma tarea de bin "
        "cerrado, el mismo europalé y el mismo pedido cuando Kagerer corrió PCT en BED-BPP.",
        first_line=False,
    )

    add_h2(doc, "7.3. Uti. y Num. frente a ηutil de Kagerer")
    add_body(
        doc,
        "Kagerer et al. (IJRR 2023) introducen BED-BPP y reportan ηutil = V / (A_pallet × hn), "
        "el volumen empaquetado sobre el ortoedro de huella por altura neta. ηutil premia "
        "bajar hn aunque hn rebase 2 m. Uti. Zhao, al contrario, vale cero como solución si "
        "el packing no cabe en el bin. Por eso ηutil no decide el veredicto de este informe. "
        "Se reporta como columna auxiliar porque es el KPI oficial de bed-bpp-env "
        "(KPIs.update).",
        first_line=False,
    )

    add_h2(doc, "7.4. BED-BPP y el packing plan publicado")
    add_body(
        doc,
        "Kagerer corrió el código de PCT sobre BED-BPP (O3DBP, europalé 120 × 80 × 200 cm) "
        "y publicó xkpi y un packing plan "
        "(2022-11-25_kagerer_o3dbpp-pct_O3dbp.json). En el árbol local ese archivo es un "
        "puntero Git LFS (~138 MB) no materializado. Sin el plan no se pueden recomputar "
        "Uti./Num. de PCT ítem a ítem dentro del bin de 2 m. Sí constan las cifras publicadas: "
        "para 00100408, ηutil = 0,614, νu = 0, hn = 2,105 m.",
        first_line=False,
    )

    # ── 8. Fase 3 ────────────────────────────────────────────────────────
    add_h1(doc, "8. Fase 3 — Homologación")
    add_h2(doc, "8.1. Pedido fijo y condiciones a priori")
    add_body(
        doc,
        "El pedido se fijó antes de ver el resultado: 00100408 (holdout; 26 ítems; no se "
        "entrenó con él). Condiciones: O3DBP p=1 s=1, un palé, bin 1 200 × 800 × 2 000 mm, "
        "encoder v1, checkpoint mlp_v1_p1s1_ppo.pt. El lado PCT es el xkpi / plan publicado "
        "por Kagerer para ese mismo pedido, no una reimplementación nuestra de PCT.",
        first_line=False,
    )

    add_h2(doc, "8.2. Resultados en 00100408")
    add_table(
        doc,
        ["Lado", "Factible (Zhao)", "Uti. Zhao", "Num.", "hn (m)", "ηutil Kagerer"],
        [
            ["mlp_v1_p1s1_ppo.pt", "sí", "0,646376", "26", "1,970", "0,656219"],
            [
                "PCT (xkpi publicado; plan LFS no materializado)",
                "no",
                "—",
                "—",
                "2,105",
                "0,614",
            ],
        ],
    )
    add_caption(doc, "Tabla 9. Homologación en 00100408 (09_homologar_pct.json).")
    add_body(
        doc,
        "Nuestra solución cabe: hn = 1,97 m < 2 m, 26/26 ítems dentro, Uti. = 0,646376. "
        "PCT publicado no cabe: hn = 2,105 m. Sin plan LFS no hay Uti. de PCT dentro del bin. "
        "Si se ignora la contención, el volumen de los 26 ítems empata (~0,646235 vs 0,646376): "
        "es el mismo pedido, no un empate Zhao. ηutil favorece a nuestro lado (0,656 vs 0,614) "
        "porque hn es menor; esa columna no decide.",
        first_line=False,
    )

    add_h2(doc, "8.3. Límite del plan LFS de PCT")
    add_body(
        doc,
        "Materializar el LFS permitiría recomputar Uti. y Num. de PCT con la misma función "
        "kpis_zhao_from_plan (contención estricta). Hasta entonces, PCT no tiene Uti. en bin "
        "cerrado para este pedido. El veredicto de la fase 4 se apoya en la única columna "
        "comparable y decisoria: la factibilidad. No se infiere una Uti. de PCT a partir de "
        "ηutil.",
        first_line=False,
    )

    # ── 9. Fase 4 ────────────────────────────────────────────────────────
    add_h1(doc, "9. Fase 4 — Comparación y veredicto")
    add_h2(doc, "9.1. Tabla de comparabilidad")
    add_body(
        doc,
        "El notebook 10 no resume «quién tiene más utilización». Construye una tabla de "
        "comparabilidad columna a columna: qué se puede comparar, qué decide, qué es auxiliar. "
        "columna_decisoria = feasible. uti_head_to_head = false.",
        first_line=False,
    )
    add_table(
        doc,
        ["Columna", "Nuestro", "PCT", "¿Comparable?", "¿Decide?"],
        [
            ["Tarea / pedido / bin", "O3DBP-1-1, 00100408, 1200×800×2000", "O3DBP, 00100408, europalé", "sí", "no"],
            ["Factible (contención Zhao)", "sí", "no", "sí", "sí"],
            ["Uti. Zhao (V_dentro / V_bin)", "0,646376", "nulo", "no", "no"],
            ["Num. Zhao (ítems dentro)", "26", "nulo", "no", "no"],
            ["Uti. si se ignora contención", "0,646376", "0,646235", "sí", "no"],
            ["ηutil Kagerer", "0,656219", "0,614", "sí", "no"],
            ["hn (m)", "1,97", "2,105", "sí", "no"],
        ],
        col_widths=[4.2, 3.6, 3.4, 2.4, 2.2],
    )
    add_caption(doc, "Tabla 10. Comparabilidad (10_comparar_pct.json). Solo «factible» decide.")

    add_h2(doc, "9.2. Veredicto")
    add_quote(
        doc,
        "En el pedido homologado, O3DBP p=1 s=1, bin 1 200 × 800 × 2 000 mm (Zhao ICLR 2022: "
        "Uti./Num., contención), mlp_v1_p1s1_ppo.pt supera a PCT. Nuestra solución es factible "
        "en el bin; la de PCT publicada no (hn > 2 m). En el protocolo Zhao una colocación "
        "fuera del bin no es solución. No es ranking sobre BED-BPP ni Σalgo.",
    )
    add_body(
        doc,
        "Lado = supera. El argumento es de factibilidad, no de una décima de Uti. Eso es "
        "coherente con el paper: Table 1 no admite soluciones que rebasan el bin. Si en el "
        "futuro se materializa el LFS y PCT resultara factible en 00100408, habría que "
        "reabrir Uti. head-to-head; hoy no es el caso (hn publicado 2,105 m).",
        first_line=False,
    )

    add_h2(doc, "9.3. Alcance y no-afirmaciones")
    add_bullet(doc, "Un pedido (00100408), no N≥20 europalé.")
    add_bullet(doc, "No es ranking del leaderboard BED-BPP ni Σalgo.")
    add_bullet(doc, "No se copian ni se contradicen las tablas ICLR en bins 10 × 10 × 10.")
    add_bullet(doc, "No se declara que RL gane al heurístico de packing-services (fase 2: empate).")
    add_bullet(doc, "No se declara que el PPO mejorara a BC (best_epoch=0).")
    add_bullet(doc, "No se usa el cubo del notebook 06 para el veredicto vs PCT.")

    # ── 10. Uso ──────────────────────────────────────────────────────────
    add_h1(doc, "10. Uso en packing-services")
    add_body(
        doc,
        "Tres rutas de execute exponen el mismo default: mlp_v1_p1s1_ppo.pt, policy=rl, p=1 s=1.",
        first_line=False,
    )
    add_table(
        doc,
        ["Ruta", "Notas"],
        [
            ["POST /api/v1/algorithms/drl_policy_3d_bpp/execute", "Entrada de catálogo; default de API"],
            ["POST /api/v1/online/learned/execute", "Alias online learned"],
            ["POST /api/v1/online/rl/execute", "Alias RL"],
        ],
        col_widths=[9.0, 7.2],
    )
    add_caption(doc, "Tabla 11. Rutas de execute del motor aprendido.")
    add_bullet(doc, "consolidate se activa si hay 2+ contenedores, salvo consolidate=false.")
    add_bullet(doc, "El heurístico online_3d_bpp_heuristic sigue siendo alternativa; en holdout empata con el PPO.")
    add_bullet(doc, "Cinta: mlp_v1_p3s2.pt (p=3 s=2), no es el default.")
    add_bullet(doc, "Sin torch: linear_v1.json.")
    add_bullet(doc, "El placeholder examples/online_policy_linear_v1.json no es producción.")

    # ── 11. Limitaciones ─────────────────────────────────────────────────
    add_h1(doc, "11. Limitaciones y trabajo no realizado")
    add_body(
        doc,
        "El cierre es deliberadamente estrecho. Lo siguiente no se hizo, y no debe leerse "
        "como hecho por omisión en los READMEs.",
        first_line=False,
    )
    add_table(
        doc,
        ["No hecho", "Estado", "Efecto si se hiciera"],
        [
            ["FEATURE_VERSION=2 / heightmap", "fuera de invariantes", "Otro loader; otro ciclo"],
            ["RL desde cero; pesos de PCT/GOPT", "no", "Otra política, no este .pt"],
            ["Submit leaderboard BED-BPP; Blender / Σalgo", "no", "Otro juez (Kagerer, no solo Zhao)"],
            ["N≥20 europalé", "no", "Veredicto Zhao con más potencia"],
            ["Materializar y reevaluar el plan LFS de PCT", "pendiente de LFS", "Uti. head-to-head posible"],
            ["Promocionar STEP o shaping", "no (val_util cayó)", "No hay evidencia de ganancia"],
            ["Mezclar p=3 s=2 en el default", "no", "Cambia latencia y contrato de API"],
            ["Entrenar el full 6 999", "no", "Otro working set; este cierre no aplica"],
        ],
    )
    add_caption(doc, "Tabla 12. Fuera de alcance de este cierre.")

    # ── 12. Conclusiones ─────────────────────────────────────────────────
    add_h1(doc, "12. Conclusiones")
    add_body(
        doc,
        "El ciclo entrega un motor online aprendido, integrable, con contrato de execute y "
        "consolidate, sobre encoder v1. En packing-services no gana al heurístico: empata en "
        "holdout, y el PPO no mejoró al BC. En el marco Zhao, en un pedido homologado, supera "
        "a PCT por factibilidad del bin cerrado. Esas dos frases no se contradicen: son jueces "
        "distintos.",
        first_line=False,
    )
    add_body(
        doc,
        "El valor de producto del .pt es tener una política aprendida en el catálogo, no un "
        "salto de utilización. El valor de la comparación con PCT es haber usado el protocolo "
        "del paper (bin cerrado, Uti./Num., contención) en lugar de una métrica de palé abierto. "
        "Los notebooks 01–10 y los JSON de artifacts/ se conservan como corrida. Este informe "
        "es la referencia viva del cierre.",
    )

    # ── 13. Referencias ──────────────────────────────────────────────────
    add_h1(doc, "13. Referencias")
    refs = [
        "Zhao, H.; Yu, Y.; Xu, K. Learning Efficient Online 3D Bin Packing on Packing Configuration Trees. International Conference on Learning Representations (ICLR), 2022.",
        "Kagerer, F.; et al. The Box and Elongated-object Dataset for Bin Packing Problems (BED-BPP) and associated evaluation protocol. The International Journal of Robotics Research (IJRR), 2023.",
        "bed-bpp-env. KPIs.update y packing plans publicados (xkpi PCT, 2022-11-25_kagerer_o3dbpp-pct_O3dbp.json).",
        "packing-services / online_policy_ml. Artefactos de la corrida 14–15 septiembre 2026: artifacts/reports/01_splits.json … 10_comparar_pct.json.",
        "packing-services / online_policy_ml/docs/informe_cierre_rl_online.md. Versión breve en Markdown (misma fecha).",
    ]
    for i, ref in enumerate(refs, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1.0)
        p.paragraph_format.first_line_indent = Cm(-0.6)
        p.paragraph_format.space_after = Pt(6)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(f"[{i}]  {ref}")
        set_run_font(run, size=10)

    # ── 14. Anexos ───────────────────────────────────────────────────────
    add_h1(doc, "14. Anexos")
    add_h2(doc, "A. Rutas de artefactos de esta corrida")
    add_table(
        doc,
        ["Artefacto", "Ruta"],
        [
            ["Splits", "online_policy_ml/artifacts/reports/01_splits.json"],
            ["Transiciones", "online_policy_ml/artifacts/reports/02_transitions.json"],
            ["Validación BC", "online_policy_ml/artifacts/reports/03_validacion.json"],
            ["Compuerta maestro", "online_policy_ml/artifacts/reports/04_compuerta_maestro.json"],
            ["PPO", "online_policy_ml/artifacts/reports/05_rl_ppo.json"],
            ["Holdout producto", "online_policy_ml/artifacts/reports/06_evaluar_holdout.json"],
            ["Registro 07/08 v3", "sellos de consolidación y execute en artifacts/"],
            ["Homologación Zhao", "online_policy_ml/artifacts/reports/09_homologar_pct.json"],
            ["Comparación / veredicto", "online_policy_ml/artifacts/reports/10_comparar_pct.json"],
            ["Checkpoint API", "online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt"],
            ["Actor BC", "online_policy_ml/artifacts/models/mlp_v1_p1s1.pt"],
            ["Cinta p=3 s=2", "online_policy_ml/artifacts/models/mlp_v1_p3s2.pt"],
            ["Lineal sin torch", "online_policy_ml/artifacts/models/linear_v1.json"],
            ["Informe Markdown", "online_policy_ml/docs/informe_cierre_rl_online.md"],
            ["Este informe Word", "online_policy_ml/docs/Informe_cierre_RL_online.docx"],
        ],
        col_widths=[5.0, 11.2],
    )
    add_caption(doc, "Tabla 13. Artefactos de la corrida de cierre.")

    add_h2(doc, "B. Notebooks del ciclo")
    add_table(
        doc,
        ["Nb", "Fase", "Función", "No hace"],
        [
            ["01", "1", "Splits seed 42, holdout bloqueado", "Entrenar"],
            ["02", "1", "Transiciones receding_horizon_ep", "Evaluar holdout"],
            ["03", "1", "BC lineal + MLP; val/test working", "Elegir default vs PCT"],
            ["04", "1", "Compuerta maestro vs H vs MLP", "Promocionar API"],
            ["05", "1", "PPO; exporta best_epoch=0", "Promocionar STEP/shaping"],
            ["06", "2", "Holdout n=5 vs heurístico", "Veredicto Zhao"],
            ["07", "2", "First-fit multi-palé (sello v3)", "Reentrenar"],
            ["08", "2", "Execute = 07 consolidado", "Cambiar p/s"],
            ["09", "3", "Homologación 00100408, kpis Zhao", "Σalgo / Blender"],
            ["10", "4", "Tabla de comparabilidad y veredicto", "Ranking BED-BPP"],
        ],
        col_widths=[1.6, 1.6, 7.0, 6.0],
    )
    add_caption(doc, "Tabla 14. Notebooks 01–10 y su jurisdicción.")

    add_h2(doc, "C. Glosario")
    add_table(
        doc,
        ["Término", "Significado en este informe"],
        [
            ["BC", "Behavioral cloning: imitación del maestro receding_horizon_ep."],
            ["EP", "Empty-maximal-space: generador de candidatas legales del bucle online."],
            ["hn", "Altura neta del packing (m). En Zhao, hn ≤ 2 m es condición de factibilidad."],
            ["O3DBP", "Tarea online 3D bin packing de BED-BPP."],
            ["p, s", "Lookahead y tamaño de selección del actor (producción: p=1, s=1)."],
            ["PCT", "Packing Configuration Tree (Zhao et al., ICLR 2022)."],
            ["PPO", "Proximal Policy Optimization; en esta corrida no mejoró a BC."],
            ["Uti.", "Utilización Zhao: volumen contenido / volumen del bin cerrado."],
            ["ηutil", "KPI Kagerer: V / (huella del palé × hn). No es Uti."],
            ["Working set", "24/8/8 pedidos usados para train/val/test de la fase 1."],
        ],
        col_widths=[3.2, 13.0],
    )
    add_caption(doc, "Tabla 15. Glosario.")

    add_h2(doc, "D. Control de versiones del informe")
    add_table(
        doc,
        ["Versión", "Fecha", "Soporte", "Notas"],
        [
            [
                "0.9",
                "2026-09-15",
                "Markdown",
                "informe_cierre_rl_online.md; cierre de ciclo, 7 secciones.",
            ],
            [
                "1.0",
                "2026-09-15",
                "Word",
                "Este documento: índice, detalle por fase, tablas de corrida, anexos.",
            ],
        ],
        col_widths=[2.4, 3.2, 3.0, 7.6],
    )
    add_caption(doc, "Tabla 16. Control de versiones.")

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("— Fin del informe —")
    set_run_font(r, size=10, italic=True, color=GRAY)

    doc.save(OUT)
    print(f"Escrito: {OUT}")
    print(f"Tamaño: {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    build()
