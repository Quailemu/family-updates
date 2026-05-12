from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "infographic.png"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size=size)


FONT_TITLE = font("segoeuib.ttf", 86)
FONT_SUBTITLE = font("segoeui.ttf", 34)
FONT_PANEL_NUM = font("segoeuib.ttf", 40)
FONT_PANEL_TITLE = font("segoeuib.ttf", 34)
FONT_BODY = font("segoeui.ttf", 25)
FONT_BODY_BOLD = font("segoeuib.ttf", 25)
FONT_SMALL = font("segoeui.ttf", 20)
FONT_FOOTER = font("segoeuib.ttf", 28)


NAVY = "#07165f"
BLUE = "#1d4ed8"
CYAN = "#e8fbff"
GREEN = "#14845e"
GREEN_SOFT = "#eaf7ef"
RED = "#d62435"
RED_SOFT = "#fff0f0"
AMBER = "#b66a00"
AMBER_SOFT = "#fff6df"
PURPLE = "#6338b8"
PURPLE_SOFT = "#f2edff"
PINK = "#c0266f"
PINK_SOFT = "#fff0f7"
INK = "#111827"
MUTED = "#4b5563"
BORDER = "#a7c4ee"
WHITE = "#ffffff"


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str = BORDER, width: int = 3, radius: int = 22) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fnt: ImageFont.FreeTypeFont, fill: str = NAVY) -> None:
    bbox = draw.multiline_textbbox((0, 0), text, font=fnt, spacing=5, align="center")
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = box[0] + ((box[2] - box[0]) - tw) / 2
    y = box[1] + ((box[3] - box[1]) - th) / 2
    draw.multiline_text((x, y), text, font=fnt, fill=fill, spacing=5, align="center")


def wrap_lines(text: str, width: int) -> str:
    parts: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            parts.append("")
        else:
            parts.extend(wrap(paragraph, width=width))
    return "\n".join(parts)


def panel(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, num: int, title: str, fill: str = WHITE) -> tuple[int, int, int, int]:
    rounded(draw, (x, y, x + w, y + h), fill)
    draw.ellipse((x + 22, y + 22, x + 82, y + 82), fill=NAVY)
    text_center(draw, (x + 22, y + 22, x + 82, y + 82), str(num), FONT_PANEL_NUM, WHITE)
    draw.text((x + 100, y + 24), title, font=FONT_PANEL_TITLE, fill=NAVY)
    return (x + 28, y + 104, x + w - 28, y + h - 24)


def body(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, width: int, fill: str = INK, fnt: ImageFont.FreeTypeFont = FONT_BODY, spacing: int = 8) -> None:
    draw.multiline_text(xy, wrap_lines(text, width), font=fnt, fill=fill, spacing=spacing)


def pill(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fill: str, outline: str, fg: str = NAVY) -> None:
    rounded(draw, box, fill, outline=outline, radius=18, width=2)
    text_center(draw, box, text, FONT_BODY_BOLD, fg)


def icon_people(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str) -> None:
    for dx, r in [(-36, 16), (0, 20), (36, 16)]:
        draw.ellipse((cx + dx - r, cy - r, cx + dx + r, cy + r), fill=color)
    draw.rounded_rectangle((cx - 76, cy + 22, cx + 76, cy + 72), radius=18, fill=color)


def icon_phone(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str) -> None:
    draw.rounded_rectangle((cx - 42, cy - 64, cx + 42, cy + 64), radius=16, outline=color, width=8)
    draw.ellipse((cx - 7, cy + 44, cx + 7, cy + 58), fill=color)
    draw.arc((cx - 18, cy - 18, cx + 18, cy + 18), 210, 330, fill=color, width=6)


def icon_doc(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str) -> None:
    draw.rounded_rectangle((cx - 50, cy - 58, cx + 50, cy + 58), radius=10, outline=color, width=6)
    for i in range(4):
        y = cy - 28 + i * 20
        draw.line((cx - 30, y, cx + 32, y), fill=color, width=5)


def draw_check(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str = WHITE) -> None:
    draw.line((cx - 11, cy + 1, cx - 2, cy + 12), fill=color, width=5)
    draw.line((cx - 2, cy + 12, cx + 15, cy - 13), fill=color, width=5)


def main() -> None:
    img = Image.new("RGB", (3000, 1600), "#f8fbff")
    draw = ImageDraw.Draw(img)

    text_center(draw, (0, 8, 3000, 100), "familyupdates.care", FONT_TITLE, NAVY)
    text_center(draw, (0, 96, 3000, 145), "Structured family communication around care", FONT_SUBTITLE, MUTED)

    margin = 26
    gap = 22
    top = 165
    row_h = 520
    col_w = (3000 - 2 * margin - 4 * gap) // 5

    # Row 1
    c = panel(draw, margin, top, col_w, row_h, 1, "The real problem")
    icon_people(draw, c[0] + 150, c[1] + 70, BLUE)
    body(draw, (c[0], c[1] + 170), "One person often becomes the Family Organiser.\nCalls, texts, opinions and repeated updates can become another job.", 31)
    pill(draw, (c[0], c[3] - 78, c[2], c[3] - 12), "The app structures the non-urgent part", CYAN, BORDER)

    c = panel(draw, margin + (col_w + gap), top, col_w, row_h, 2, "Urgent stays outside")
    rounded(draw, (c[0], c[1], c[2], c[1] + 170), RED_SOFT, RED)
    text_center(draw, (c[0], c[1] + 8, c[2], c[1] + 64), "Emergency protocol", FONT_BODY_BOLD, RED)
    body(draw, (c[0] + 24, c[1] + 72), "Urgent, medical, safeguarding, legal and very private matters use the agreed direct route.", 34, fill=INK)
    rounded(draw, (c[0], c[1] + 205, c[2], c[3] - 12), GREEN_SOFT, GREEN)
    text_center(draw, (c[0], c[1] + 214, c[2], c[1] + 270), "Inside the app", FONT_BODY_BOLD, GREEN)
    body(draw, (c[0] + 24, c[1] + 285), "Everyday family communication only.\nChecked at agreed intervals.", 31, fnt=FONT_SMALL, spacing=6)

    c = panel(draw, margin + 2 * (col_w + gap), top, col_w, row_h, 3, "Family update")
    icon_doc(draw, c[0] + 110, c[1] + 80, GREEN)
    body(draw, (c[0] + 205, c[1] + 30), "The Family Organiser sends one current update to registered Family Members.", 25)
    pill(draw, (c[0], c[3] - 160, c[2], c[3] - 92), "1 update", GREEN_SOFT, GREEN)
    pill(draw, (c[0], c[3] - 78, c[2], c[3] - 12), "New update replaces the last", CYAN, BORDER)

    c = panel(draw, margin + 3 * (col_w + gap), top, col_w, row_h, 4, "Specific message")
    body(draw, (c[0], c[1] + 18), "The Family Organiser and each Family Member can keep one current specific message.", 33)
    rounded(draw, (c[0], c[1] + 155, c[2], c[1] + 260), PURPLE_SOFT, PURPLE)
    text_center(draw, (c[0] + 12, c[1] + 170, c[2] - 12, c[1] + 245), "Not a thread.\nNot live chat.", FONT_BODY_BOLD, PURPLE)
    pill(draw, (c[0], c[3] - 78, c[2], c[3] - 12), "1 current message per channel", PURPLE_SOFT, PURPLE)

    c = panel(draw, margin + 4 * (col_w + gap), top, col_w, row_h, 5, "Practical request")
    body(draw, (c[0], c[1] + 10), "Use one structured request for practical coordination.", 35)
    rounded(draw, (c[0], c[1] + 116, c[2], c[1] + 215), AMBER_SOFT, AMBER)
    text_center(draw, (c[0], c[1] + 126, c[2], c[1] + 205), "Can someone take her\nto the appointment?", FONT_BODY_BOLD, INK)
    pill(draw, (c[0], c[1] + 248, c[0] + 155, c[1] + 320), "Yes", GREEN_SOFT, GREEN)
    pill(draw, (c[0] + 176, c[1] + 248, c[0] + 330, c[1] + 320), "No", RED_SOFT, RED)
    pill(draw, (c[0] + 350, c[1] + 248, c[2], c[1] + 320), "Maybe", AMBER_SOFT, AMBER)
    pill(draw, (c[0], c[3] - 78, c[2], c[3] - 12), "1 request replaces the last", AMBER_SOFT, AMBER)

    # Row 2
    row2 = top + row_h + gap
    c = panel(draw, margin, row2, col_w, row_h, 6, "Noticeboard")
    body(draw, (c[0], c[1] + 5), "Each Family Member can pin one current note visible to the family group and Family Office.", 32)
    for i, note in enumerate(["Visiting Saturday 2pm", "Can bring shopping", "Away until Monday"]):
        rounded(draw, (c[0], c[1] + 155 + i * 78, c[2], c[1] + 215 + i * 78), WHITE, BORDER, width=2, radius=14)
        draw.text((c[0] + 24, c[1] + 170 + i * 78), note, font=FONT_BODY_BOLD, fill=NAVY)
    pill(draw, (c[0], c[3] - 78, c[2], c[3] - 12), "1 note per Family Member", CYAN, BORDER)

    c = panel(draw, margin + (col_w + gap), row2, col_w, row_h, 7, "Normal family contact")
    icon_phone(draw, c[0] + 125, c[1] + 92, BLUE)
    body(draw, (c[0] + 230, c[1] + 28), "Family Members still phone the person being supported in the normal way.", 28)
    rounded(draw, (c[0], c[1] + 210, c[2], c[1] + 340), GREEN_SOFT, GREEN)
    text_center(draw, (c[0] + 14, c[1] + 218, c[2] - 14, c[1] + 330), "The app organises family communication.\nIt does not replace personal contact.", FONT_BODY_BOLD, GREEN)
    pill(draw, (c[0], c[3] - 78, c[2], c[3] - 12), "Family phones stay outside the app", RED_SOFT, RED)

    c = panel(draw, margin + 2 * (col_w + gap), row2, col_w, row_h, 8, "Clear boundaries")
    for i, item in enumerate(["No threads", "No archive", "No search", "No live chat", "No read receipts"]):
        y = c[1] + 12 + i * 60
        draw.ellipse((c[0], y, c[0] + 42, y + 42), fill=GREEN)
        draw_check(draw, c[0] + 21, y + 21)
        draw.text((c[0] + 58, y + 4), item, font=FONT_BODY_BOLD, fill=INK)
    pill(draw, (c[0], c[3] - 78, c[2], c[3] - 12), "No threads: too many conversations", GREEN_SOFT, GREEN)

    c = panel(draw, margin + 3 * (col_w + gap), row2, col_w, row_h, 9, "Helps the organiser")
    body(draw, (c[0], c[1] + 10), "The Family Organiser is not agreeing to be available all the time or act as everyone's messenger.", 32)
    rounded(draw, (c[0], c[1] + 220, c[2], c[1] + 340), CYAN, BORDER)
    text_center(draw, (c[0] + 12, c[1] + 230, c[2] - 12, c[1] + 330), "A small number of channels\nstay current.", FONT_BODY_BOLD, NAVY)

    c = panel(draw, margin + 4 * (col_w + gap), row2, col_w, row_h, 10, "The simple offer")
    for i, item in enumerate(["1 family update", "1 specific organiser message", "1 practical request", "1 noticeboard note per Family Member"]):
        y = c[1] + 30 + i * 72
        rounded(draw, (c[0], y, c[2], y + 54), WHITE, BORDER, width=2, radius=14)
        draw.text((c[0] + 22, y + 10), item, font=FONT_BODY_BOLD, fill=NAVY)
    body(draw, (c[0], c[1] + 340), "Everything is non-urgent. Each new item replaces the last.", 33, fill=GREEN, fnt=FONT_BODY_BOLD)

    # Footer
    footer_y = row2 + row_h + 26
    rounded(draw, (margin, footer_y, 3000 - margin, footer_y + 190), WHITE, BORDER, radius=24)
    footer_items = [
        ("Current", "Latest item only"),
        ("Calm", "No instant reply pressure"),
        ("Practical", "Structured replies"),
        ("Transparent", "Shared notes where useful"),
        ("Human", "Phone calls stay normal"),
    ]
    fw = (3000 - 2 * margin - 40) // len(footer_items)
    for i, (head, sub) in enumerate(footer_items):
        x = margin + 20 + i * fw
        draw.text((x, footer_y + 34), head, font=FONT_FOOTER, fill=NAVY)
        body(draw, (x, footer_y + 82), sub, 24, fill=MUTED, fnt=FONT_SMALL, spacing=4)

    img.save(OUT, quality=95)


if __name__ == "__main__":
    main()
