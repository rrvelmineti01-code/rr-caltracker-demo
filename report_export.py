"""Create a downloadable nutrition PDF entirely in memory."""
from branding import APP_NAME, DISPLAY_NAME, APP_MARK, APP_TAGLINE
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
import re
from nutrition import CATALOG, summarize_foods, format_amount, coverage_label

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FONT_DIR = Path(__file__).with_name("assets") / "fonts"
pdfmetrics.registerFont(TTFont("RRBody", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("RRBold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("RRBody", normal="RRBody", bold="RRBold", italic="RRBody", boldItalic="RRBold")
INK = colors.HexColor("#20382E")
GREEN = colors.HexColor("#295842")
MUTED = colors.HexColor("#66756C")
LINE = colors.HexColor("#DFE5D8")
CREAM = colors.HexColor("#F7F8F2")
NUTRIENTS = ("Calories", "Protein", "Carbs", "Fat")


def text(value):
    """Treat all food names and provider notes as plain text, never PDF markup."""
    raw = str(value).replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
    return escape(raw).replace("\n", "<br/>")


def value_label(value, nutrient):
    if value is None:
        return "Unavailable"
    return f"{value:,.0f} kcal" if nutrient == "Calories" else f"{value:,.1f} g"


class NutritionCards(Flowable):
    def __init__(self, totals):
        super().__init__()
        self.totals = totals
        self.height = 86

    def wrap(self, available_width, available_height):
        self.width = available_width
        return self.width, self.height

    def draw(self):
        gap = 10
        card_width = (self.width - 3 * gap) / 4
        c = self.canv
        for index, nutrient in enumerate(NUTRIENTS):
            x = index * (card_width + gap)
            primary = index == 0
            c.setFillColor(GREEN if primary else colors.HexColor("#EEF2E7"))
            c.roundRect(x, 5, card_width, 76, 10, fill=1, stroke=0)
            c.setFillColor(colors.white if primary else MUTED)
            c.setFont("RRBody", 8.5)
            c.drawString(x + 13, 59, nutrient)
            value = self.totals.get(nutrient)
            c.setFont("RRBold", 12 if value is None else 21)
            c.setFillColor(colors.white if primary else INK)
            c.drawString(x + 13, 32, "Unavailable" if value is None else f"{value:,.0f}")
            if value is not None:
                c.setFont("RRBody", 8)
                c.drawString(x + 13, 17, "kcal" if primary else "grams")


class MacroBar(Flowable):
    def __init__(self, totals):
        super().__init__()
        energies = [max(0, totals[n]) * factor for n, factor in zip(NUTRIENTS[1:], (4, 4, 9))]
        self.shares = [v / sum(energies) for v in energies]
        self.height = 54

    def wrap(self, available_width, available_height):
        self.width = available_width
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(INK)
        c.setFont("RRBold", 8)
        c.drawString(0, 43, "MACRO ENERGY BALANCE")
        x = 0
        palette = ("#476C47", "#C5D59F", "#E9B89A")
        for share, shade in zip(self.shares, palette):
            c.setFillColor(colors.HexColor(shade))
            c.rect(x, 24, self.width * share, 8, stroke=0, fill=1)
            x += self.width * share
        x = 0
        for name, share, shade in zip(NUTRIENTS[1:], self.shares, palette):
            c.setFillColor(colors.HexColor(shade))
            c.circle(x + 3, 11, 3, fill=1, stroke=0)
            c.setFillColor(MUTED)
            c.setFont("RRBody", 8)
            c.drawString(x + 12, 8, f"{name} {share * 100:.0f}%")
            x += self.width / 3


def build_meal_pdf(meal):
    """Render the exact reviewed export values, including partial and demo flags."""
    output = BytesIO()
    width, height = A4
    margin = 42
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=margin, rightMargin=margin,
                                 topMargin=89, bottomMargin=48,
                                 title=f"{APP_NAME} - Meal nutrition report", author=APP_NAME)
    body = ParagraphStyle("Body", fontName="RRBody", fontSize=9, leading=14, textColor=INK,
                          spaceAfter=7, splitLongWords=True)
    muted = ParagraphStyle("Muted", parent=body, fontSize=8, leading=12, textColor=MUTED)
    heading = ParagraphStyle("Heading", parent=body, fontName="RRBold", fontSize=12,
                             leading=17, spaceBefore=14, spaceAfter=8, keepWithNext=True)
    title = ParagraphStyle("Title", parent=body, fontName="RRBold", fontSize=27, leading=34, spaceAfter=7)
    cell = ParagraphStyle("Cell", parent=body, fontSize=8, leading=12, spaceAfter=0)
    numeric = ParagraphStyle("Number", parent=cell, alignment=TA_RIGHT, fontSize=8)
    table_head = ParagraphStyle("TableHead", parent=cell, fontName="RRBold", textColor=colors.white)
    date = meal.get("generated_at") or datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    def page_frame(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(CREAM)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(GREEN)
        canvas.roundRect(margin, height - 58, 31, 31, 8, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("RRBold", 10)
        canvas.drawString(margin + 7, height - 47, APP_MARK)
        canvas.setFillColor(INK)
        canvas.setFont("RRBold", 11)
        canvas.drawString(margin + 42, height - 40, DISPLAY_NAME)
        canvas.setFont("RRBody", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin + 42, height - 52, APP_TAGLINE)
        canvas.setFont("RRBody", 8)
        canvas.drawRightString(width - margin, height - 43, "NUTRITION REPORT")
        canvas.setStrokeColor(LINE)
        canvas.line(margin, height - 72, width - margin, height - 72)
        canvas.line(margin, 34, width - margin, 34)
        canvas.setFont("RRBody", 7)
        canvas.drawString(margin, 21, f"{APP_NAME} | Reviewed portions, estimated nutrition")
        canvas.drawRightString(width - margin, 21, f"Page {doc.page}")
        canvas.restoreState()

    story = [Paragraph("Your meal, at a glance.", title),
             Paragraph("Prepared " + text(date), muted)]
    if meal.get("demo"):
        story.append(Paragraph("<b>SAMPLE MEAL</b> - Illustrative values. No photograph was analyzed and no live USDA lookup was made.", body))
    else:
        story.append(Paragraph(escape(f"A snapshot of the foods and portions you reviewed in {APP_NAME}."), muted))
    if meal.get("partial") or meal.get("excluded_foods"):
        story.append(Paragraph("<b>PARTIAL ESTIMATE</b> - Excluded from these totals: " +
                               text(", ".join(meal.get("excluded_foods", []))) + ".", body))
    totals = meal["totals"]
    story.extend([Spacer(1, 7), NutritionCards(totals), Spacer(1, 12)])
    if all(totals.get(n) is not None for n in NUTRIENTS[1:]) and any(totals.get(n, 0) > 0 for n in NUTRIENTS[1:]):
        story.extend([MacroBar(totals), Paragraph(
            "Approximate split using 4 / 4 / 9 kcal per gram; it may differ from database calories.", muted)])
    calorie_range = meal.get("calorie_range")
    if calorie_range and calorie_range[0] != calorie_range[1]:
        story.append(Paragraph(f"<b>Portion-based calorie range:</b> {calorie_range[0]:,.0f}-{calorie_range[1]:,.0f} kcal.", body))
        story.append(Paragraph("Model-suggested portion range, not a validated confidence interval. Recipe and database-match errors are not included.", muted))
    if any(totals.get(n) is None for n in NUTRIENTS):
        story.append(Paragraph("Unavailable means nutrient data is missing for at least one matched food. It does not mean zero.", muted))

    story.append(Paragraph("Foods & reviewed portions", heading))
    rows = [[Paragraph(label, table_head) for label in ("Food / match", "Portion", "Calories", "Protein", "Carbs", "Fat")]]
    for food in meal["foods"]:
        identity = "<b>" + text(food["name"]) + "</b><br/>" + text(food["nutrition_match"])
        if food.get("usda_fdc_id") is not None:
            identity += "<br/>FDC ID: " + text(food["usda_fdc_id"])
        status = "Measured" if food.get("weighed") else "Sample" if meal.get("demo") else "Estimated"
        grams = f"<b>{food['grams']:,.0f} g</b><br/><font size='7'>{status}</font>"
        nutrients = food.get("nutrients", {})
        rows.append([Paragraph(identity, cell), Paragraph(grams, numeric)] +
                    [Paragraph(value_label(nutrients.get(name), name), numeric) for name in NUTRIENTS])
    available_width = width - 2 * margin
    table = Table(rows, colWidths=[available_width - 287, 55, 68, 57, 53, 54], repeatRows=1,
                  hAlign="LEFT", splitByRow=1, splitInRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F3E9")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LINEBELOW", (0, 0), (-1, 0), .5, GREEN),
        ("LINEBELOW", (0, 1), (-1, -1), .3, LINE),
    ]))
    story.append(table)
    story.append(Paragraph("Vitamins, minerals & fiber", heading))
    story.append(Paragraph("Estimated amounts for the reviewed portions. Partial values include only foods with data; missing values are not zero. mcg means micrograms. These are intake amounts, not daily targets.", muted))
    summary = summarize_foods(meal["foods"], meal.get("excluded_foods", []), meal.get("partial", False))
    nutrient_rows = [[Paragraph(label, table_head) for label in ("Nutrient", "Estimated amount", "Data coverage")]]
    for spec in CATALOG:
        if spec["group"] == "Macros" and spec["key"] != "Fiber":
            continue
        entry = summary[spec["key"]]
        nutrient_rows.append([Paragraph(text(spec["label"]), cell),
                              Paragraph(text(format_amount(entry["value"], spec["unit"])), numeric),
                              Paragraph(text(coverage_label(entry)), cell)])
    nutrient_table = Table(nutrient_rows, colWidths=[available_width * .48, available_width * .25, available_width * .27], repeatRows=1)
    nutrient_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CREAM]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), .3, LINE),
    ]))
    story.append(nutrient_table)
    story.append(Paragraph("Portion notes", heading))
    for food in meal["foods"]:
        low, high = food.get("portion_low_g"), food.get("portion_high_g")
        bounds = (f" Suggested range: {low:,.0f}-{high:,.0f} g." if
                  not food.get("weighed") and low is not None and high is not None else "")
        note = "Weight supplied as measured on a kitchen scale." if food.get("weighed") else food.get("portion_notes", "Visual portion estimate.")
        story.append(Paragraph("<b>" + text(food["name"]) + ":</b> " + text(note + bounds), muted))
    story.append(Paragraph("How to read this report", heading))
    method = ("This report demonstrates the interface using fixed sample data." if meal.get("demo") else
              "AI suggests food identities and portions. USDA supplies nutrient values per 100 g; Python scales them to your reviewed weights. Hidden oils, recipes, and database matches can change the result. Photo portion accuracy has not yet been validated against weighed meals.")
    story.append(Paragraph(method, muted))
    for assumption in meal.get("assumptions", []):
        story.append(Paragraph("- " + text(assumption), muted))
    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return output.getvalue()
