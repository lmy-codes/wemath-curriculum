"""
WeMath worksheet packets. Each subject gets its own folder:

  1-ten-buddies/          Ten Buddies (pairs that make 10)
  2-ten-and-some-more/    10 + a number
  3-up-to-and-over-ten/   crossing ten with buddies (break-apart)
  4-over-the-next-ten/    crossing 20, 30, 40… with buddies
  5-back-through-ten/     subtracting across ten with the jump diagram
  6-doubles-and-near-doubles/  doubles to 10 + 10, then near doubles (6 + 7 = double 6 + 1)
  7-tens-and-ones/        two-digit numbers as tens and ones (ten-sticks, quick tens)

Each folder has color/ and black-and-white/ versions of:
  <subject>-packet.pdf       page 1 = picture-first learning page, then practice
  <subject>-answer-key.pdf   the same pages filled in, plus a short teacher note

Run:  python build_worksheets.py   (needs reportlab; uses macOS system fonts)

No question appears twice across all four packets: Book.ask() stops the build
if one does.
"""

import math
import os
from fractions import Fraction
import re
from pathlib import Path
from types import SimpleNamespace

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(os.environ.get("WEMATH_OUT") or Path(__file__).parent)  # WEMATH_OUT: build somewhere else (previews)

AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
# Off a Mac, WEMATH_PREVIEW_FONTS can point at a folder of stand-in fonts (Inter-Regular/Medium/
# SemiBold/Bold.ttf + LiberationSans-Bold.ttf) to check layouts. Never ship PDFs built that way.
PREVIEW_FONTS = None if Path(AVENIR).exists() else os.environ.get("WEMATH_PREVIEW_FONTS")
if PREVIEW_FONTS:
    for name, file in [("Av", "Inter-Regular"), ("AvM", "Inter-Medium"), ("AvD", "Inter-SemiBold"),
                       ("AvB", "Inter-Bold"), ("Rnd", "LiberationSans-Bold")]:
        pdfmetrics.registerFont(TTFont(name, f"{PREVIEW_FONTS}/{file}.ttf"))
else:
    pdfmetrics.registerFont(TTFont("Av", AVENIR, subfontIndex=7))
    pdfmetrics.registerFont(TTFont("AvM", AVENIR, subfontIndex=5))
    pdfmetrics.registerFont(TTFont("AvD", AVENIR, subfontIndex=2))
    pdfmetrics.registerFont(TTFont("AvB", AVENIR, subfontIndex=0))
    pdfmetrics.registerFont(TTFont("Rnd", "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"))
pdfmetrics.registerFontFamily("Av", normal="Av", bold="AvD", italic="Av", boldItalic="AvD")
pdfmetrics.registerFontFamily("AvM", normal="AvM", bold="AvB", italic="AvM", boldItalic="AvB")


def theme(color):
    """All colours used on the page. The black-and-white theme uses no fills."""
    if color:
        return SimpleNamespace(
            color=True,
            ink=HexColor("#0f2742"), text2=HexColor("#5b6b80"), muted=HexColor("#94a3b8"),
            line=HexColor("#d3dbe6"), box=HexColor("#8a9bb1"),
            dot_a=HexColor("#1d63e0"), dot_b=HexColor("#f08c00"),
            accent=HexColor("#f08c00"), answer=HexColor("#e03131"),
            band=HexColor("#dbe8fd"), panel=HexColor("#f3f7fe"), panel_line=HexColor("#c9defc"),
            strip=HexColor("#fff6e8"), strip_line=HexColor("#f5d9a8"),
            share=HexColor("#bcd3fb"), share_ans=HexColor("#ffc9c9"),  # shaded parts of a shape
            copper=HexColor("#eebf98"), silver=HexColor("#e4e9ef"), bill=HexColor("#dcf1df"),  # money
        )
    return SimpleNamespace(
        color=False,
        ink=HexColor("#1a1a1a"), text2=HexColor("#555555"), muted=HexColor("#999999"),
        line=HexColor("#c4c4c4"), box=HexColor("#8c8c8c"),
        dot_a=HexColor("#1a1a1a"), dot_b=None,  # None = hollow dot
        accent=HexColor("#1a1a1a"), answer=HexColor("#1a1a1a"),
        band=None, panel=None, panel_line=HexColor("#c4c4c4"),
        strip=None, strip_line=HexColor("#c4c4c4"),
        share=None, share_ans=None,  # None = diagonal hatching
        copper=None, silver=None, bill=None,
    )


T = theme(True)

W, H = letter
M = 48
CW = W - 2 * M
OPS = {"+", "−", "=", "-", "×", "÷"}
GUT = 46  # content in a numbered card starts at least this far from the card's left edge


def sw(text, font, size):
    return pdfmetrics.stringWidth(text, font, size)


# The WeMath "buddies" mark: a blue piece and an orange piece that fit together into a square
# (assets/wemath-logo.svg). Points are in the SVG's 88-unit box, y pointing down.
LOGO_PIECES = [("#1d63e0", [(12, 12), (60, 12), (60, 40), (40, 40), (40, 88), (12, 88)]),
               ("#f08c00", [(70, 12), (88, 12), (88, 88), (50, 88), (50, 50), (70, 50)])]


def draw_logo(c, x, y, size):
    """The buddies mark, size points square, bottom-left at (x, y). Black-and-white: black and grey."""
    k = size / 88
    c.setLineJoin(1)
    c.setLineWidth(5 * k)
    for i, (hexcol, pts) in enumerate(LOGO_PIECES):
        col = HexColor(hexcol) if T.color else (T.ink if i == 0 else T.muted)
        c.setFillColor(col)
        c.setStrokeColor(col)
        p = c.beginPath()
        for j, (px, py) in enumerate(pts):
            (p.moveTo if j == 0 else p.lineTo)(x + (px - 6) * k, y + (94 - py) * k)
        p.close()
        c.drawPath(p, stroke=1, fill=1)
    c.setLineJoin(0)


class Book:
    def __init__(self, path, key, subtitle="Up to and Over Ten", asked=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.c = canvas.Canvas(str(path), pagesize=letter)
        self.key = key
        self.page = 0
        self.subtitle = subtitle
        self.footer = ""
        self.asked = {} if asked is None else asked  # shared across packets
        self.rec = None  # a list while a check-in or assessment card is drawn: its answers (curriculum.json)
        self.c.setTitle(f"{subtitle}: " + ("Answer Key" if key else "Student Workbook"))
        self.c.setAuthor("WeMath")

    # ------------------------------------------------------------------ page chrome

    def new_page(self, heading, goal=None, first=True, name_line=True, footer=None, big=False):
        """Starts a page (closing the previous one). Returns the y where content begins."""
        c = self.c
        if self.page:
            self._footer()
            c.showPage()
        self.page += 1
        if footer:
            self.footer = footer

        # top line: small mark + WeMath, Name/Date (or Answer Key) on the right
        top = H - 40
        draw_logo(c, M, top - 4, 17)
        c.setFillColor(T.ink)
        c.setFont("AvB", 12.5)
        c.drawString(M + 24, top, "WeMath")
        c.setFillColor(T.text2)
        c.setFont("Av", 9.5)
        c.drawString(M + 24 + sw("WeMath", "AvB", 12.5) + 8, top, self.subtitle)

        if self.key:
            c.setFillColor(T.answer)
            c.setFont("AvB", 11)
            c.drawRightString(W - M, top, "Answer Key")
        elif name_line:
            c.setFont("Av", 9.5)
            c.setFillColor(T.text2)
            c.drawString(W - M - 236, top, "Name")
            c.drawString(W - M - 82, top, "Date")
            c.setStrokeColor(T.muted)
            c.setLineWidth(0.7)
            c.line(W - M - 206, top - 2, W - M - 94, top - 2)
            c.line(W - M - 56, top - 2, W - M, top - 2)
        c.setStrokeColor(T.line)
        c.setLineWidth(0.7)
        c.line(M, top - 14, W - M, top - 14)

        if big:  # learning page: large, friendly title
            c.setFillColor(T.ink)
            c.setFont("AvB", 30)
            c.drawString(M, H - 96, heading)
            if goal:
                c.setFillColor(T.text2)
                c.setFont("Rnd", 15)
                c.drawString(M, H - 120, goal)
            return H - 146
        if first:
            c.setFillColor(T.ink)
            c.setFont("AvB", 19)
            c.drawString(M, H - 86, heading)
            if goal:
                c.setFillColor(T.text2)
                c.setFont("Av", 10.5)
                c.drawString(M, H - 103, goal)
                return H - 130
            return H - 112
        c.setFillColor(T.ink)
        c.setFont("AvD", 12.5)
        c.drawString(M, H - 80, heading)
        c.setFillColor(T.muted)
        c.setFont("Av", 10)
        c.drawString(M + sw(heading, "AvD", 12.5) + 6, H - 80, "(continued)")
        return H - 104

    def _footer(self):
        c = self.c
        c.setFillColor(T.muted)
        c.setFont("Av", 8)
        c.drawString(M, 28, self.footer)
        c.drawRightString(W - M, 28, str(self.page))

    def save(self):
        self._footer()
        self.c.save()

    def ask(self, question):
        """Register a question; the build fails if the same question appears twice."""
        key = re.sub(r"\[[^\]]*\]", "[]", question)
        key = re.sub(r"\s+", " ", key).strip()
        where = f"page {self.page}"
        if key in self.asked:
            raise ValueError(f"Duplicate question {key!r} on {where} (also on {self.asked[key]})")
        self.asked[key] = where

    # ------------------------------------------------------------------ building blocks

    def part(self, y, n, text, sub=None):
        """Section label: 'Part 2   Fill in the buddy.   sub'"""
        c = self.c
        label = f"Part {n}"
        c.setFillColor(T.ink)
        c.setFont("AvB", 11.5)
        c.drawString(M, y, label)
        x = M + sw(label, "AvB", 11.5) + 10
        c.setFont("AvM", 11.5)
        c.drawString(x, y, text)
        if sub:
            c.setFillColor(T.text2)
            c.setFont("Av", 10)
            c.drawString(x + sw(text, "AvM", 11.5) + 8, y, sub)
        return y - 14

    def note(self, y, text):
        self.c.setFillColor(T.text2)
        self.c.setFont("Av", 10)
        self.c.drawString(M, y, text)
        return y - 12

    def card(self, x, y, w, h, num=None):
        """
        Problem card. The problem number is written "12)" in small grey type at the
        left: top-left corner on tall cards, vertically centred on short ones.
        Content starts at x + GUT (or below the number), leaving a clear gap.
        """
        if y < 44:
            print(f"WARNING: page {self.page} card at y={y:.0f} overlaps the footer")
        c = self.c
        c.setStrokeColor(T.line)
        c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, 6, stroke=1, fill=0)
        if num is not None:
            c.setFillColor(T.text2)
            c.setFont("AvD", 10)
            ny = y + h / 2 - 3.5 if h < 60 else y + h - 17
            c.drawString(x + 10, ny, f"{num})")

    def box(self, x, y, w, h, value=None, size=16, reveal=None):
        c = self.c
        c.setFillColor(white)
        c.setStrokeColor(T.box)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
        self.value(x + w / 2, y + h / 2, value, size, reveal)

    def value(self, cx, cy, value, size=16, reveal=None):
        """An answer centred at (cx, cy): shown on the key, or always in `reveal` colour."""
        if self.rec is not None and reveal is None and value not in (None, ""):
            self.rec.append(str(value))
        if value in (None, "") or not (reveal or self.key):
            return
        self.c.setFillColor(reveal or T.answer)
        self.c.setFont("AvD" if str(value) in OPS else "Rnd", size)
        self.c.drawCentredString(cx, cy - size * 0.36, str(value))

    def dot(self, cx, cy, r, kind):
        """kind 'a' = the starting number, 'b' = the buddy / extra."""
        c = self.c
        if kind == "a" or T.dot_b is not None:
            c.setFillColor(T.dot_a if kind == "a" else T.dot_b)
            c.circle(cx, cy, r, stroke=0, fill=1)
        else:
            c.setFillColor(white)
            c.setStrokeColor(T.ink)
            c.setLineWidth(1.1)
            c.circle(cx, cy, r - 0.5, stroke=1, fill=1)

    def _tokens(self, text, size):
        out = []
        for tok in text.split():
            if tok.startswith("[") and tok.endswith("]"):
                ans = tok[1:-1]
                out.append(("box", ans, size * 1.75 + max(len(ans) - 1, 0) * size * 0.55))
            elif tok.startswith("{") and tok.endswith("}"):
                out.append(("hi", tok[1:-1], sw(tok[1:-1], "Rnd", size)))
            elif tok in OPS:
                out.append(("op", tok, sw(tok, "AvD", size)))
            else:
                out.append(("num", tok, sw(tok, "Rnd", size)))
        return out

    def eq_width(self, text, size=17):
        toks = self._tokens(text, size)
        return sum(t[2] for t in toks) + size * 0.32 * (len(toks) - 1)

    def eq(self, x, y, text, size=17, color=None):
        """Equation on baseline y. [n] = answer box, {n} = highlighted number."""
        c = self.c
        color = color or T.ink
        gap = size * 0.32
        for kind, t, w in self._tokens(text, size):
            if kind == "box":
                self.box(x, y - size * 0.42, w, size * 1.6, t, size=size * 0.92)
            elif kind == "op":
                c.setFillColor(T.text2 if color is T.ink else color)
                c.setFont("AvD", size)
                c.drawString(x, y, t)
            else:
                c.setFillColor(T.accent if kind == "hi" else color)
                c.setFont("Rnd", size)
                c.drawString(x, y, t)
            x += w + gap
        return x - gap

    def fit_eq(self, x, y, w, text, size=17, color=None):
        """eq(), shrinking the type until it fits in width w."""
        while self.eq_width(text, size) > w and size > 9:
            size -= 0.5
        return self.eq(x, y, text, size=size, color=color)

    def ten_frame(self, x, y, cell, fills):
        """fills: 'a' / 'b' / None for each of 10 cells, top row then bottom row."""
        c = self.c
        fw, fh = cell * 5, cell * 2
        c.setStrokeColor(T.muted)
        c.setLineWidth(0.6)
        for i in range(1, 5):
            c.line(x + i * cell, y, x + i * cell, y + fh)
        c.line(x, y + cell, x + fw, y + cell)
        c.setStrokeColor(T.ink)
        c.setLineWidth(1.2)
        c.roundRect(x, y, fw, fh, 2.5, stroke=1, fill=0)
        for i, kind in enumerate(list(fills)[:10]):
            if kind:
                self.dot(x + (i % 5) * cell + cell / 2, y + fh - (i // 5) * cell - cell / 2, cell * 0.33, kind)

    def frames(self, x, y, cell, fills, gap=8):
        fills = list(fills) + [None] * (20 - len(fills))
        self.ten_frame(x, y, cell, fills[:10])
        self.ten_frame(x + cell * 5 + gap, y, cell, fills[10:20])

    def work(self, x, y, w, h, label="Show your work"):
        c = self.c
        c.setStrokeColor(T.line)
        c.setLineWidth(0.8)
        c.setDash(3, 3)
        c.roundRect(x, y, w, h, 5, stroke=1, fill=0)
        c.setDash()
        if label:
            c.setFillColor(T.muted)
            c.setFont("Av", 7.5)
            c.drawString(x + 7, y + h - 11, label)

    def arrow(self, x1, y1, x2, y2):
        c = self.c
        c.setStrokeColor(T.accent)
        c.setLineWidth(1.2)
        ang = math.atan2(y2 - y1, x2 - x1)
        c.line(x1, y1, x2 - 5 * math.cos(ang), y2 - 5 * math.sin(ang))
        p = c.beginPath()
        p.moveTo(x2, y2)
        for da in (2.6, -2.6):
            p.lineTo(x2 + 7 * math.cos(ang + da), y2 + 7 * math.sin(ang + da))
        p.close()
        c.setFillColor(T.accent)
        c.drawPath(p, stroke=0, fill=1)

    def make_ten_box(self, x, y, w, h, band_h, label=None):
        """Rounded box with a band on top showing the ten."""
        c = self.c
        if T.band is not None:
            c.setFillColor(T.band)
            c.roundRect(x, y + h - band_h, w, band_h, 5, stroke=0, fill=1)
            c.rect(x, y + h - band_h, w, band_h / 2, stroke=0, fill=1)
        c.setStrokeColor(T.ink)
        c.setLineWidth(1.2)
        c.roundRect(x, y, w, h, 5, stroke=1, fill=0)
        c.setLineWidth(0.8)
        c.line(x, y + h - band_h, x + w, y + h - band_h)
        if label is not None:
            c.setFillColor(T.ink)
            c.setFont("AvB", 10.5)
            c.drawCentredString(x + w / 2, y + h - band_h + 5, str(label))

    def captions(self, y, items):
        self.c.setFillColor(T.muted)
        self.c.setFont("Av", 7)
        for x, word in items:
            self.c.drawCentredString(x, y, word)

    def break_apart(self, cx, top, keep=None, split=None, ten=None, example=False):
        """
        The break-apart diagram (WeMath template for crossing a ten):

                 9 + 4            problem; the number being broken apart is highlighted
                    / \\
            [ 10      ]   ( )     band = the next ten
            [ 9 | 1   ] + (3) = [13]
            start buddy  left over  answer

        The problem is always written bigger + smaller, so the arrows come straight down
        from the second number. keep=None draws a blank diagram. Answers show on the key,
        or always when example=True.
        """
        c = self.c
        blank = keep is None
        if not blank:
            ten = ten or (keep // 10 + 1) * 10
            buddy, total = ten - keep, keep + split
            left = split - buddy
        BW, BH, HB, KW = 92, 56, 17, 48
        CR, AW, AH, g = 16, 40, 34, 7
        pw, ew = sw("+", "AvD", 18), sw("=", "AvD", 18)
        width = BW + g + pw + g + 2 * CR + g + ew + g + AW
        x0 = cx - width / 2
        row_y = top - 54 - BH
        mid_y = row_y + (BH - HB) / 2
        bx = x0 + KW + (BW - KW) / 2
        plus_x = x0 + BW + g
        ccx = plus_x + pw + g + CR
        eq_x = ccx + CR + g
        ax = eq_x + ew + g
        span_mid = (x0 + ccx + CR) / 2

        base = top - 20
        if blank:
            c.setStrokeColor(T.muted)
            c.setLineWidth(0.8)
            c.line(span_mid - 62, base - 3, span_mid - 14, base - 3)
            c.line(span_mid + 14, base - 3, span_mid + 62, base - 3)
            c.setFillColor(T.text2)
            c.setFont("AvD", 18)
            c.drawCentredString(span_mid, base, "+")
            sx = span_mid + 38
        else:
            a_txt, b_txt = str(keep), str(split)
            wa, wb = sw(a_txt, "Rnd", 20), sw(b_txt, "Rnd", 20)
            tx = span_mid - (wa + 16 + pw + wb) / 2
            c.setFont("Rnd", 20)
            c.setFillColor(T.ink)
            c.drawString(tx, base, a_txt)
            c.setFillColor(T.text2)
            c.setFont("AvD", 18)
            c.drawString(tx + wa + 8, base, "+")
            c.setFont("Rnd", 20)
            c.setFillColor(T.accent)
            c.drawString(tx + wa + 16 + pw, base, b_txt)
            sx = tx + wa + 16 + pw + wb / 2

        self.arrow(sx - 4, base - 7, bx + 2, row_y + BH + 3)
        self.arrow(sx + 4, base - 7, ccx, mid_y + CR + 3)

        self.make_ten_box(x0, row_y, BW, BH, HB, None if blank else ten)
        c.setStrokeColor(T.muted)
        c.setLineWidth(0.9)
        c.setDash(2.5, 2.5)
        c.line(x0 + KW, row_y + 5, x0 + KW, row_y + BH - HB - 5)
        c.setDash()
        if not blank:
            c.setFillColor(T.ink)
            c.setFont("Rnd", 20)
            c.drawCentredString(x0 + KW / 2, mid_y - 7, str(keep))
        reveal = T.accent if example else None
        self.box(bx - 17, mid_y - 14, 34, 28, None if blank else buddy, size=16, reveal=reveal)

        c.setFillColor(T.text2)
        c.setFont("AvD", 18)
        c.drawString(plus_x, mid_y - 6, "+")
        c.setFillColor(white)
        c.setStrokeColor(T.box)
        c.setLineWidth(1)
        c.circle(ccx, mid_y, CR, stroke=1, fill=1)
        if not blank:
            self.value(ccx, mid_y, left, 16, reveal)
        c.setFillColor(T.text2)
        c.setFont("AvD", 18)
        c.drawString(eq_x, mid_y - 6, "=")
        self.box(ax, mid_y - AH / 2, AW, AH, None if blank else total, size=17,
                 reveal=T.ink if example else None)
        self.captions(row_y - 10, [(x0 + KW / 2, "start"), (bx, "buddy"),
                                   (ccx, "left over"), (ax + AW / 2, "answer")])
        return row_y - 12

    def buddies_first(self, cx, top, nums, pair):
        """
        Three numbers: circle the two buddies, then 10 + leftover.

                6 + 3 + 4
            [ 10 ] + ( 3 ) = [13]
        """
        c = self.c
        texts = [str(n) for n in nums]
        size, gap = 20, 16  # room for the circles drawn on the key
        pw = sw("+", "AvD", 18)
        widths = [sw(t, "Rnd", size) for t in texts]
        tw = sum(widths) + 2 * (pw + 2 * gap)
        x = cx - tw / 2
        base = top - 22
        centers = []
        for i, t in enumerate(texts):
            c.setFillColor(T.ink)
            c.setFont("Rnd", size)
            c.drawString(x, base, t)
            centers.append(x + widths[i] / 2)
            x += widths[i] + gap
            if i < 2:
                c.setFillColor(T.text2)
                c.setFont("AvD", 18)
                c.drawString(x, base, "+")
                x += pw + gap
        if self.key:
            c.setStrokeColor(T.answer)
            c.setLineWidth(1.4)
            for i in pair:
                c.circle(centers[i], base + 7, 13, stroke=1, fill=0)

        rest = sum(nums) - 10
        BW, BH, HB, CR, AW, AH, g = 54, 44, 15, 17, 42, 34, 8
        pw2, ew = sw("+", "AvD", 18), sw("=", "AvD", 18)
        width = BW + g + pw2 + g + 2 * CR + g + ew + g + AW
        x0 = cx - width / 2
        row_y = top - 48 - BH
        mid_y = row_y + (BH - HB) / 2
        self.make_ten_box(x0, row_y, BW, BH, HB, "buddies")
        c.setFillColor(T.ink)
        c.setFont("Rnd", 19)
        c.drawCentredString(x0 + BW / 2, mid_y - 7, "10")
        plus_x = x0 + BW + g
        ccx = plus_x + pw2 + g + CR
        eq_x = ccx + CR + g
        ax = eq_x + ew + g
        c.setFillColor(T.text2)
        c.setFont("AvD", 18)
        c.drawString(plus_x, mid_y - 6, "+")
        c.setFillColor(white)
        c.setStrokeColor(T.box)
        c.setLineWidth(1)
        c.circle(ccx, mid_y, CR, stroke=1, fill=1)
        self.value(ccx, mid_y, rest, 16)
        c.setFillColor(T.text2)
        c.setFont("AvD", 18)
        c.drawString(eq_x, mid_y - 6, "=")
        self.box(ax, mid_y - AH / 2, AW, AH, sum(nums), size=17)
        self.captions(row_y - 10, [(ccx, "left over"), (ax + AW / 2, "answer")])

    def grid(self, y, cols, rows, h, gap=10):
        """(x, y, w) for each cell of a cols × rows grid hanging below y."""
        w = (CW - gap * (cols - 1)) / cols
        for r in range(rows):
            for col in range(cols):
                yield M + col * (w + gap), y - (r + 1) * h - r * gap, w

    def paragraph(self, x, y, w, html, size=10.5, leading=15, font="Av", color=None):
        style = ParagraphStyle("p", fontName=font, fontSize=size, leading=leading,
                               textColor=color or T.ink, alignment=TA_LEFT)
        p = Paragraph(html, style)
        _, ph = p.wrapOn(self.c, w, 1000)
        p.drawOn(self.c, x, y - ph)
        return y - ph


def dots(n, kind="a"):
    return [kind] * n


def ba_grid(bk, y, probs, first_num, cols=2, h=130, gap=12):
    """Break-apart cards. probs: (bigger, smaller) pairs; (None, None) = blank."""
    rows = (len(probs) + cols - 1) // cols
    for k, (x, cy, w) in enumerate(bk.grid(y, cols, rows, h, gap)):
        if k < len(probs):
            keep, split = probs[k]
            if keep is not None:
                bk.ask(f"{keep} + {split} = []")
            bk.card(x, cy, w, h, first_num + k)
            bk.break_apart(x + w / 2 + 6, cy + h - 8, keep, split)
    return y - rows * h - (rows - 1) * gap


# ---------------------------------------------------------------------- the sets


def buddy_strip(bk, y):
    """Reference strip of the five Ten Buddy pairs."""
    c = bk.c
    h = 70
    if T.strip is not None:
        c.setFillColor(T.strip)
        c.roundRect(M, y - h, CW, h, 8, stroke=0, fill=1)
    else:
        c.setStrokeColor(T.strip_line)
        c.setLineWidth(0.8)
        c.roundRect(M, y - h, CW, h, 8, stroke=1, fill=0)
    c.setFillColor(T.ink)
    c.setFont("AvB", 9)
    c.drawString(M + 14, y - 16, "Ten Buddies")
    pairs = [(1, 9), (2, 8), (3, 7), (4, 6), (5, 5)]
    pw = (CW - 28) / 5
    for i, (a, b) in enumerate(pairs):
        mid = M + 14 + i * pw + pw / 2
        if i:
            c.setStrokeColor(T.strip_line)
            c.setLineWidth(0.7)
            c.line(mid - pw / 2, y - 24, mid - pw / 2, y - h + 10)
        for j in range(10):
            bk.dot(mid - 19 + (j % 5) * 9.5, y - 28 - (j // 5) * 9.5, 3.5, "a" if j < a else "b")
        text = f"{a} + {{{b}}} = 10"
        bk.eq(mid - bk.eq_width(text, 13) / 2, y - 59, text, size=13)


def word_card(bk, y, num, text, sentence, answer, unit):
    bk.ask(f"story: {sentence}")
    h = 110
    cy = y - h
    bk.card(M, cy, CW, h, num)
    lw = 300
    tx = M + GUT + 4
    bk.paragraph(tx, y - 9, M + lw + 30 - tx, text, size=11.5, leading=16, font="AvM")
    c = bk.c
    c.setFillColor(T.text2)
    c.setFont("AvM", 8.5)
    c.drawString(tx, cy + 44, "Number sentence")
    c.setStrokeColor(T.muted)
    c.setLineWidth(0.7)
    c.line(tx + 78, cy + 42, M + 30 + lw, cy + 42)
    if bk.key:
        bk.eq(tx + 84, cy + 46, sentence, size=13, color=T.answer)
    c.setFillColor(T.text2)
    c.setFont("AvM", 8.5)
    c.drawString(tx, cy + 17, "Answer")
    bw = max(46, sw(str(answer), "Rnd", 17) + 16)  # wider only for long answers like 11:30
    bk.box(tx + 38, cy + 8, bw, 28, answer, size=17)
    c.setFillColor(T.ink)
    c.setFont("AvM", 11)
    c.drawString(tx + 46 + bw, cy + 18, unit)
    bk.work(M + lw + 46, cy + 10, CW - lw - 56, h - 20, "Draw or show your work")
    return cy - 8


# ---------------------------------------------------------------------- teacher guide


def build_template(folder):
    path = folder / "break-apart-template.pdf"
    bk = Book(path, key=False, subtitle="Break-Apart Practice")
    bk.c.setTitle("Break-Apart Practice")
    y = bk.new_page("Break-Apart Practice", footer="WeMath  ·  Break-Apart Practice")
    y = bk.paragraph(M, y + 6, CW,
        "Write a problem on the top line. Write the next ten in the band, the bigger number in the box, "
        "its buddy beside it, what is left over in the circle, then the answer.",
        size=10.5, leading=15, color=T.text2) - 14
    ba_grid(bk, y, [(None, None)] * 8, 1)
    bk.save()
    return path




# ====================================================================== learning-page helpers

def color_eq(bk, x, y, parts, size, anchor="left"):
    """
    Coloured equation for learning pages. parts: (text, kind) or (text, kind, "tight"),
    kind 'a' = first number colour, 'b' = buddy colour, 'op' = grey sign, None = ink.
    "tight" draws the part with no space before it (for the ones digit of 14).
    """
    c = bk.c
    gap = size * 0.28

    def font(kind):
        return "AvD" if kind == "op" else "Rnd"

    total = 0
    for i, p in enumerate(parts):
        total += sw(p[0], font(p[1]), size) + (0 if i == 0 or (len(p) > 2 and p[2] == "tight") else gap)
    if anchor == "center":
        x -= total / 2
    for i, p in enumerate(parts):
        text, kind = p[0], p[1]
        if i and not (len(p) > 2 and p[2] == "tight"):
            x += gap
        col = {"a": T.dot_a, "b": T.accent, "op": T.text2}.get(kind, T.ink)
        c.setFillColor(col)
        c.setFont(font(kind), size)
        c.drawString(x, y, text)
        x += sw(text, font(kind), size)
    return x


def label(bk, x, y, text, size=13):
    bk.c.setFillColor(T.ink)
    bk.c.setFont("AvB", size)
    bk.c.drawString(x, y, text)


def dot_row(bk, x, y, n, kind="b", r=6.5, step=19):
    for i in range(n):
        bk.dot(x + i * step, y, r, kind)


def panel(bk, x, y, w, h):
    c = bk.c
    if T.panel is not None:
        c.setFillColor(T.panel)
        c.setStrokeColor(T.panel_line)
        c.roundRect(x, y, w, h, 10, stroke=1, fill=1)
    else:
        c.setStrokeColor(T.panel_line)
        c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, 10, stroke=1, fill=0)


def your_turn(bk, y, h=96):
    panel(bk, M, y - h, CW, h)
    label(bk, M + 16, y - 22, "Your turn!", 13)
    return y - h


def teacher_note(bk, text):
    """Answer key only: a small note at the bottom of the learning page."""
    if not bk.key:
        return
    c = bk.c
    h, y0 = 58, 48
    c.setStrokeColor(T.answer)
    c.setLineWidth(0.8)
    c.roundRect(M, y0, CW, h, 6, stroke=1, fill=0)
    c.setFillColor(T.answer)
    c.setFont("AvB", 9)
    c.drawString(M + 12, y0 + h - 15, "For teachers")
    bk.paragraph(M + 12, y0 + h - 20, CW - 24, text, size=9.5, leading=13)


def practice_cards(bk, y, items, first_num, cols, rows, h, gap, draw):
    """Grid of numbered cards; draw(x, cy, w, item) fills each one."""
    for k, (x, cy, w) in enumerate(bk.grid(y, cols, rows, h, gap)):
        if k < len(items):
            bk.card(x, cy, w, h, first_num + k)
            draw(x, cy, w, items[k])
    return y - rows * h - (rows - 1) * gap


def compact(bk, y, problems, first_num, cols=3):
    """Short one-line problems, e.g. "9 + [1] = 10"."""
    rows = (len(problems) + cols - 1) // cols

    def draw(x, cy, w, text):
        bk.ask(text)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 8, text, size=18)
    return practice_cards(bk, y, problems, first_num, cols, rows, 42, 8, draw)


def words(bk, y, stories, first_num):
    for i, (story, sentence, answer, unit) in enumerate(stories):
        y = word_card(bk, y, first_num + i, story, sentence, answer, unit)
    return y


# ====================================================================== 1. Ten Buddies

def learn_buddies(bk):
    y = bk.new_page("Ten Buddies", "Two numbers that make 10.", name_line=False, big=True,
                    footer="WeMath  ·  Ten Buddies")
    # hero: 7 and 3 fill a ten-frame
    bk.ten_frame(M + 24, y - 86, 34, dots(7) + dots(3, "b"))
    color_eq(bk, M + 262, y - 50, [("7", "a"), ("+", "op"), ("3", "b"), ("=", "op"), ("10", None)], 44)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("Rnd", 16)
    bk.c.drawString(M + 264, y - 82, "7 and 3 are buddies!")
    y -= 122

    label(bk, M, y, "All the buddies")
    y -= 14
    for a, b in [(1, 9), (2, 8), (3, 7), (4, 6), (5, 5)]:
        bk.ten_frame(M + 60, y - 44, 20, dots(a) + dots(b, "b"))
        color_eq(bk, M + 200, y - 31, [(str(a), "a"), ("+", "op"), (str(b), "b"), ("=", "op"), ("10", None)], 26)
        if a != b:
            bk.c.setFillColor(T.text2)
            bk.c.setFont("Rnd", 16)
            bk.c.drawString(M + 370, y - 30, f"{b} + {a} = 10 too!")
        y -= 52
    y -= 12

    bottom = your_turn(bk, y)
    bk.ten_frame(M + 130, bottom + 16, 26, dots(2) + (dots(8, "b") if bk.key else []))
    bk.ask("2 + [] = 10")
    bk.eq(M + 300, bottom + 34, "2 + [8] = 10", size=30)
    teacher_note(bk, "Goal: say the buddy of any number from 0 to 10 in about 3 seconds, without counting. "
                     "Ask “What’s 7’s buddy?” and have students show it on a ten-frame or with fingers.")


def practice_buddies(bk):
    y = bk.new_page("Ten Buddies: Practice", "Know every pair that makes 10 without counting.")
    y = bk.part(y, 1, "How many dots? What is its buddy?")

    def frame_card(x, cy, w, n):
        bk.ask(f"frame {n}")
        bk.ten_frame(x + GUT, cy + 20, 22, dots(n) + (dots(10 - n, "b") if bk.key else []))
        for j, (lab, val) in enumerate([("Dots", n), ("Buddy", 10 - n)]):
            bx = x + 170 + j * 41
            bk.c.setFillColor(T.text2)
            bk.c.setFont("AvM", 8)
            bk.c.drawCentredString(bx + 18, cy + 58, lab)
            bk.box(bx, cy + 18, 36, 34, val, size=17)
    y = practice_cards(bk, y, [7, 9, 3, 5], 1, 2, 2, 84, 12, frame_card) - 26

    y = bk.part(y, 2, "Fill in the buddy.")
    y = compact(bk, y, ["8 + [2] = 10", "[4] + 6 = 10", "1 + [9] = 10", "4 + [6] = 10",
                        "[8] + 2 = 10", "10 + [0] = 10", "5 + [5] = 10", "[3] + 7 = 10",
                        "9 + [1] = 10", "[7] + 3 = 10", "0 + [10] = 10", "6 + [4] = 10"], 5) - 26

    y = bk.part(y, 3, "Are they Ten Buddies?", "Circle yes or no.")

    def yes_no(x, cy, w, item):
        text, yes = item
        bk.ask(f"buddies? {text}")
        bk.c.setFillColor(T.ink)
        bk.c.setFont("Rnd", 18)
        bk.c.drawString(x + GUT, cy + 15, text)
        for j, word in enumerate(["yes", "no"]):
            px = x + w - 104 + j * 50
            bk.c.setFillColor(T.text2)
            bk.c.setFont("AvD", 13)
            bk.c.drawCentredString(px + 20, cy + 16, word)
            if bk.key and (word == "yes") == yes:
                bk.c.setStrokeColor(T.answer)
                bk.c.setLineWidth(1.6)
                bk.c.ellipse(px + 2, cy + 8, px + 38, cy + 34, stroke=1, fill=0)
    # shuffle the questions so the right answer isn't always on one side ("yes" stays first)
    practice_cards(bk, y, [("6 and 4", True), ("7 and 2", False), ("5 and 4", False), ("8 and 2", True)],
                   17, 2, 2, 44, 8, yes_no)

    y = bk.new_page("Ten Buddies: Practice", first=False)
    y = bk.part(y, 4, "How many more to make 10?", "Draw dots in the empty spaces to help.")

    def more_card(x, cy, w, item):
        text, have, need = item
        bk.ask(text)
        ew = bk.eq_width(text, 17)
        bk.eq(x + GUT + (w - GUT - ew) / 2, cy + 64, text, size=17)
        bk.ten_frame(x + GUT + (w - GUT - 100) / 2, cy + 13, 20,
                     dots(have) + (dots(need, "b") if bk.key else []))
    y = practice_cards(bk, y, [("7 + [3] = 10", 7, 3), ("[9] + 1 = 10", 1, 9), ("[6] + 4 = 10", 4, 6),
                               ("[2] + 8 = 10", 8, 2), ("3 + [7] = 10", 3, 7), ("[1] + 9 = 10", 9, 1)],
                       21, 3, 2, 96, 10, more_card) - 30
    y = bk.part(y, 5, "Word problems", "Use your buddies.")
    words(bk, y, [
        ("A pack holds 10 juice boxes. There are 3 in it. How many more juice boxes will fill the pack?",
         "3 + 7 = 10", "7", "juice boxes"),
        ("A box holds 10 crayons. It has 6 crayons in it. How many more crayons will fill the box?",
         "6 + 4 = 10", "4", "crayons"),
        ("Sam has 5 red blocks and 5 blue blocks. How many blocks does Sam have?",
         "5 + 5 = 10", "10", "blocks"),
    ], 27)


# ====================================================================== 2. Ten and Some More

def learn_ten_and_more(bk):
    y = bk.new_page("Ten and Some More", "A full ten-frame is 10.", name_line=False, big=True,
                    footer="WeMath  ·  Ten and Some More")
    cell = 28
    fw = cell * 5
    x0 = M + (CW - (fw * 2 + 40 + 40 + 70)) / 2
    bk.ten_frame(x0, y - 70, cell, dots(10))
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvD", 30)
    bk.c.drawCentredString(x0 + fw + 20, y - 52, "+")
    bk.ten_frame(x0 + fw + 40, y - 70, cell, dots(4, "b"))
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvD", 30)
    bk.c.drawCentredString(x0 + 2 * fw + 60, y - 52, "=")
    color_eq(bk, x0 + 2 * fw + 84, y - 60, [("1", None), ("4", "b", "tight")], 48)
    color_eq(bk, x0 + fw / 2, y - 96, [("10", None)], 20, anchor="center")
    color_eq(bk, x0 + fw * 1.5 + 40, y - 96, [("4", "b")], 20, anchor="center")
    y -= 128

    label(bk, M, y, "See the pattern")
    y -= 12
    half = CW / 2
    for n in range(1, 10):
        col, row = (0, n - 1) if n <= 5 else (1, n - 6)
        x = M + col * half
        ry = y - row * 36
        bk.ten_frame(x + 8, ry - 26, 9, dots(10))
        bk.ten_frame(x + 59, ry - 26, 9, dots(n, "b"))
        color_eq(bk, x + 122, ry - 22, [("10", None), ("+", "op"), (str(n), "b"), ("=", "op"),
                                        ("1", None), (str(n), "b", "tight")], 20)
    y -= 5 * 36 + 14

    bottom = your_turn(bk, y)
    bk.frames(M + 60, bottom + 22, 20, dots(10) + dots(3, "b"))
    bk.ask("10 + [] = 13")
    # keep the equation (and its answer box) inside the panel
    bk.fit_eq(M + 292, bottom + 34, CW - 292 - 20, "10 + [3] = 13", size=26)
    teacher_note(bk, "Goal: read 10 + a number as a teen number straight away, and split a teen number "
                     "into 10 and some more. Say “10 and 4 more is 14.” The ones digit matches the extra dots.")


def practice_ten_and_more(bk):
    y = bk.new_page("Ten and Some More: Practice", "Ten and some more makes a teen number.")
    y = bk.part(y, 1, "Ten and some more", "Count the extra dots.")

    def teen_card(x, cy, w, item):
        text, extra = item
        bk.ask(text)
        bk.frames(x + GUT + 4, cy + 54, 19, dots(10) + dots(extra, "b"))
        bk.eq(x + GUT + 4, cy + 20, text, size=18)
    y = practice_cards(bk, y, [("10 + 3 = [13]", 3), ("10 + 7 = [17]", 7), ("10 + 9 = [19]", 9),
                               ("10 + [6] = 16", 6), ("10 + [2] = 12", 2), ("[10] + 8 = 18", 8)],
                       1, 2, 3, 104, 12, teen_card) - 30
    y = bk.part(y, 2, "Quick tens", "No dots this time.")
    compact(bk, y, ["10 + 6 = [16]", "10 + 2 = [12]", "10 + [5] = 15", "10 + [1] = 11",
                    "[10] + 4 = 14", "10 + [9] = 19", "[10] + 3 = 13", "10 + 8 = [18]",
                    "4 + 10 = [14]", "10 + [7] = 17", "10 + 5 = [15]", "10 + 1 = [11]"], 7)

    y = bk.new_page("Ten and Some More: Practice", first=False)
    y = bk.part(y, 3, "Draw it", "Show 17 as ten and some more, then finish the number sentence.")
    bk.ask("draw 17 as ten and some more")
    bk.card(M, y - 120, CW, 120, 19)
    bk.frames(M + GUT, y - 92, 28, (dots(10) + dots(7, "b")) if bk.key else [])
    bk.eq(M + 352, y - 72, "[10] + [7] = 17", size=20)
    y -= 120 + 30
    y = bk.part(y, 4, "Word problems", "Ten and some more.")
    words(bk, y, [
        ("Mia has 10 crayons in a box and 4 more on the table. How many crayons does she have?",
         "10 + 4 = 14", "14", "crayons"),
        ("A bus has 10 kids on it. 7 more kids get on. How many kids are on the bus now?",
         "10 + 7 = 17", "17", "kids"),
        ("Lily picked 10 apples, then 9 more. How many apples did Lily pick?",
         "10 + 9 = 19", "19", "apples"),
    ], 20)

    y = bk.new_page("Ten and Some More: Practice", first=False)
    y = bk.part(y, 5, "Find the buddies first, then add.", "Circle the two numbers that make 10.")

    def three_card(x, cy, w, nums):
        bk.ask(" + ".join(map(str, nums)) + " = []")
        pair = next((i, j) for i in range(3) for j in range(i + 1, 3) if nums[i] + nums[j] == 10)
        bk.buddies_first(x + w / 2 + 6, cy + 110 - 6, nums, pair)
    # The buddies sit in different places: first two, last two, or the outside two.
    y = practice_cards(bk, y, [(6, 4, 3), (5, 8, 2), (7, 1, 3), (4, 1, 9), (5, 5, 6), (2, 9, 8)],
                       23, 2, 3, 110, 10, three_card) - 30
    y = bk.part(y, 6, "Word problem", "Find the buddies first.")
    words(bk, y, [
        ("Ben has 7 red cars, 2 blue cars and 3 green cars. How many cars does Ben have?",
         "7 + 3 + 2 = 12", "12", "cars"),
    ], 29)


# ====================================================================== 3. Up to and Over Ten

def step_panel(bk, x, top, w, h, num, title, fills, left_over, result=None):
    panel(bk, x, top - h, w, h)
    bk.c.setFillColor(T.dot_a)
    bk.c.setFont("Rnd", 22)
    bk.c.drawString(x + 12, top - 28, str(num))
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 16)
    bk.c.drawCentredString(x + w / 2 + 10, top - 27, title)
    bk.ten_frame(x + (w - 100) / 2, top - 84, 20, fills)
    if left_over:
        dot_row(bk, x + w / 2 - (left_over - 1) * 9.5, top - 104, left_over, step=19)
    if result:
        color_eq(bk, x + w / 2, top - h + 18, result, 26, anchor="center")


def learn_over_ten(bk):
    y = bk.new_page("Over Ten with Buddies", "Fill the ten first!", name_line=False, big=True,
                    footer="WeMath  ·  Up to and Over Ten")
    gap, ph = 22, 172
    pw = (CW - 2 * gap) / 3
    xs = [M + i * (pw + gap) for i in range(3)]
    step_panel(bk, xs[0], y, pw, ph, 1, "8 + 5", dots(8), 5)
    step_panel(bk, xs[1], y, pw, ph, 2, "fill the ten", dots(8) + dots(2, "b"), 3)
    step_panel(bk, xs[2], y, pw, ph, 3, "add the rest", dots(8) + dots(2, "b"), 3,
               result=[("10", None), ("+", "op"), ("3", "b"), ("=", "op"), ("13", None)])
    c = bk.c
    for i in range(2):  # arrows between the steps
        ax = xs[i] + pw + gap / 2
        p = c.beginPath()
        p.moveTo(ax - 5, y - ph / 2 + 8)
        p.lineTo(ax + 6, y - ph / 2)
        p.lineTo(ax - 5, y - ph / 2 - 8)
        p.close()
        c.setFillColor(T.muted)
        c.drawPath(p, stroke=0, fill=1)
    y -= ph + 28

    label(bk, M, y, "Write it like this")
    bk.break_apart(M + CW / 2, y - 4, 8, 5, example=True)
    y -= 4 + 120 + 20
    buddy_strip(bk, y)
    teacher_note(bk, "Goal: cross ten by filling the ten first. Say “8 needs 2 to make 10. "
                     "5 is 2 and 3. 10 and 3 more is 13.” Use real counters on a ten-frame before the diagram.")


def practice_over_ten(bk):
    # Every single-digit fact appears once, mixed so students look for the buddy each time.
    y = bk.new_page("Up to and Over Ten: Practice", "Give the first number its buddy, then add what is left over.")
    y = bk.part(y, 1, "Break it apart")
    y = ba_grid(bk, y, [(9, 4), (7, 5), (8, 3), (6, 6), (9, 7), (8, 6)], 1) - 22
    buddy_strip(bk, y)

    y = bk.new_page("Up to and Over Ten: Practice", first=False)
    y = bk.part(y, 2, "Keep practicing", "Find the buddy, then what is left over.")
    ba_grid(bk, y, [(7, 4), (9, 2), (6, 5), (8, 8), (7, 7), (9, 5), (8, 4), (9, 8)], 7)

    y = bk.new_page("Up to and Over Ten: Practice", first=False)
    y = bk.part(y, 3, "On your own", "Try these without looking back.")
    y = ba_grid(bk, y, [(7, 6), (9, 3), (8, 7), (9, 6)], 15) - 30
    y = bk.part(y, 4, "Word problems", "Fill the ten first.")
    words(bk, y, [
        ("Maya has 8 stickers. Her friend gives her 5 more. How many stickers does Maya have now?",
         "8 + 5 = 13", "13", "stickers"),
        ("There are 9 kids on the bus. 6 more kids get on. How many kids are on the bus?",
         "9 + 6 = 15", "15", "kids"),
    ], 19)

    y = bk.new_page("Up to and Over Ten: Practice", first=False)
    y = bk.part(y, 5, "In your head", "No writing steps. Say the buddy out loud.")
    y = compact(bk, y, [f"{a} + {b} = [{a + b}]" for a, b in
                        [(9, 9), (5, 7), (4, 8), (3, 9), (5, 8), (5, 9), (4, 7), (2, 9)]], 21, cols=2) - 30
    y = bk.part(y, 6, "Up to ten or over ten?", "Some make exactly 10. Some go over.")
    compact(bk, y, [f"{a} + {b} = [{a + b}]" for a, b in
                    [(1, 9), (3, 8), (2, 8), (4, 9), (3, 7), (6, 8),
                     (6, 4), (6, 9), (8, 2), (7, 9), (5, 5), (9, 1)]], 29)

    y = bk.new_page("Up to and Over Ten: Practice", first=False)
    y = bk.part(y, 7, "Word problems")
    y = words(bk, y, [
        ("Leo read 7 pages on Monday and 6 pages on Tuesday. How many pages did he read in all?",
         "7 + 6 = 13", "13", "pages"),
        ("Ava had some marbles. She got 4 more and now has 12. How many marbles did she start with?",
         "8 + 4 = 12", "8", "marbles"),
        ("The class planted 9 flowers in the morning and 8 in the afternoon. How many flowers did they plant?",
         "9 + 8 = 17", "17", "flowers"),
    ], 41) - 22
    y = bk.part(y, 8, "Make your own", "Write a problem that crosses ten, then break it apart.")
    ba_grid(bk, y, [(None, None)] * 2, 44)


# ====================================================================== 4. Over the Next Ten

def learn_over_tens(bk):
    y = bk.new_page("Over the Next Ten", "Buddies work with big numbers too!", name_line=False, big=True,
                    footer="WeMath  ·  Over the Next Ten")
    label(bk, M, y, "See the pattern")
    y -= 12
    for t in range(4):
        x = M + 4
        for _ in range(t):
            bk.ten_frame(x, y - 34, 14, dots(10))
            x += 76
        bk.ten_frame(x, y - 34, 14, dots(8) + dots(2, "b"))
        start = [("8", "a")] if t == 0 else [(str(t), None), ("8", "a", "tight")]
        color_eq(bk, M + 318, y - 28, start + [("+", "op"), ("2", "b"), ("=", "op"), (str(10 * (t + 1)), None)], 26)
        y -= 46
    y -= 18

    label(bk, M, y, "Write it like this")
    bk.break_apart(M + CW / 2, y - 4, 28, 5, example=True)
    y -= 4 + 120 + 22

    bottom = your_turn(bk, y, h=108)
    bk.ask("47 + [] = 50")
    bk.ask("47 + 5 = []")
    bk.eq(M + 160, bottom + 66, "47 + [3] = 50", size=24)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvM", 12)
    bk.c.drawString(M + 128, bottom + 21, "so")
    bk.eq(M + 160, bottom + 20, "47 + 5 = [52]", size=24)
    teacher_note(bk, "Goal: use the same buddy to reach the next ten. Say “28 needs 2 to make 30. "
                     "5 is 2 and 3. 30 and 3 more is 33.” Point out that 8 + 2, 18 + 2 and 28 + 2 all use the 8–2 buddies.")


def practice_over_tens(bk):
    y = bk.new_page("Over the Next Ten: Practice", "Fill up to the next ten, then add what is left over.")
    y = bk.part(y, 1, "Up to the next ten, then over")

    def ladder_card(x, cy, w, item):
        a, b = item
        ten = (a // 10 + 1) * 10
        bk.ask(f"{a} + [] = {ten}")
        bk.ask(f"{a} + {b} = []")
        bk.eq(x + GUT, cy + 52, f"{a} + [{ten - a}] = {ten}", size=18)
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvM", 10)
        bk.c.drawString(x + GUT, cy + 17, "so")
        bk.eq(x + GUT + 22, cy + 16, f"{a} + {b} = [{a + b}]", size=18)
    y = practice_cards(bk, y, [(18, 4), (27, 5), (36, 8), (49, 3), (15, 7), (26, 6)],
                       1, 2, 3, 84, 10, ladder_card) - 30
    big = [(18, 5), (19, 3), (28, 6), (25, 7), (39, 4), (36, 7), (47, 6), (58, 4),
           (56, 8), (64, 9), (77, 6), (83, 9)]
    y = bk.part(y, 2, "Break it apart", "The band shows the next ten.")
    ba_grid(bk, y, big[:4], 7)

    y = bk.new_page("Over the Next Ten: Practice", first=False)
    y = bk.part(y, 2, "Break it apart", "(continued)")
    ba_grid(bk, y, big[4:], 11)

    # Training wheels come off: first only a "next ten" hint, then plain problems.
    y = bk.new_page("Over the Next Ten: Practice", first=False)
    y = bk.part(y, 3, "Less help", "Write the next ten first if it helps.")

    def hint_card(x, cy, w, item):
        a, b = item
        ten = (a // 10 + 1) * 10
        bk.ask(f"{a} + {b} = []")
        bk.eq(x + GUT, cy + 48, f"{a} + {b} = [{a + b}]", size=20)
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvM", 9.5)
        bk.c.drawString(x + GUT, cy + 15, "next ten")
        bk.box(x + GUT + 48, cy + 8, 34, 24, ten, size=13)
    y = practice_cards(bk, y, [(45, 7), (29, 4), (66, 8), (38, 5), (17, 6), (54, 9)],
                       19, 2, 3, 84, 10, hint_card) - 30
    y = bk.part(y, 4, "On your own", "No hints. Think: what is the next ten?")
    compact(bk, y, [f"{a} + {b} = [{a + b}]" for a, b in
                    [(16, 5), (28, 4), (35, 9), (47, 8), (59, 6), (63, 8), (74, 7), (88, 5),
                     (26, 9), (39, 2), (57, 7), (69, 3), (85, 6), (44, 9), (78, 4)]], 25)

    y = bk.new_page("Over the Next Ten: Practice", first=False)
    y = bk.part(y, 5, "Word problems", "Fill up to the next ten first.")
    words(bk, y, [
        ("Ella has 37 stickers. She gets 5 more. How many stickers does Ella have now?",
         "37 + 5 = 42", "42", "stickers"),
        ("There are 46 kids at the park. 7 more kids come. How many kids are at the park?",
         "46 + 7 = 53", "53", "kids"),
        ("Tom scored 59 points. Then he scored 4 more. What is his score now?",
         "59 + 4 = 63", "63", "points"),
        ("A farm has 68 chickens. 6 more chicks hatch. How many chickens are on the farm now?",
         "68 + 6 = 74", "74", "chickens"),
        ("Challenge: Zoe has 9 red beads and 7 blue beads. How many more beads does she need to have 20?",
         "9 + 7 = 16,  16 + 4 = 20", "4", "beads"),
    ], 40)


# ====================================================================== 5. Back Through Ten

def curve_arrow(bk, p0, p1, p2, p3):
    """Curved arrow (cubic Bézier p0→p3) with the head at p3."""
    c = bk.c
    ang = math.atan2(p3[1] - p2[1], p3[0] - p2[0])
    end = (p3[0] - 5 * math.cos(ang), p3[1] - 5 * math.sin(ang))
    c.setStrokeColor(T.accent)
    c.setLineWidth(1.4)
    path = c.beginPath()
    path.moveTo(*p0)
    path.curveTo(*p1, *p2, *end)
    c.drawPath(path, stroke=1, fill=0)
    head = c.beginPath()
    head.moveTo(*p3)
    for da in (2.6, -2.6):
        head.lineTo(p3[0] + 7 * math.cos(ang + da), p3[1] + 7 * math.sin(ang + da))
    head.close()
    c.setFillColor(T.accent)
    c.drawPath(head, stroke=0, fill=1)


def jump_circle(bk, cx, cy, value, r=16, reveal=None, size=15):
    c = bk.c
    c.setFillColor(white)
    c.setStrokeColor(T.box)
    c.setLineWidth(1.1)
    c.circle(cx, cy, r, stroke=1, fill=1)
    bk.value(cx, cy, value, size, reveal)


def plus_sign(bk, cx, y, size=16):
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvD", size)
    bk.c.drawCentredString(cx, y, "+")


JUMP_W = 180  # width of the horizontal jump diagram
JUMP_STYLE = "inline"  # "inline" (chosen): bubbles sit on the curve; "below": older style, circles under the arrows


def bezier_point(p0, p1, p2, p3, t):
    u = 1 - t
    return tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d
                 for a, b, c, d in zip(p0, p1, p2, p3))


def jump_inline(bk, x0, top, a, b, example=False):
    """
    Test style: one smooth curved path from a down to the ten and back up to b,
    with each jump bubble sitting on the curve (the line is hidden behind it).

        14  −  7  = [7]
         \         /
         (4)     (3)
           \_10_/
    Returns the bottom y.
    """
    c = bk.c
    ten = (b // 10 + 1) * 10
    j1, j2 = a - ten, ten - b
    base = top - 22
    a_cx, minus_x, b_cx, eq_x, box_x = x0 + 14, x0 + 69, x0 + 124, x0 + 155, x0 + 169
    mid = (a_cx + b_cx) / 2
    c.setFillColor(T.ink)
    c.setFont("Rnd", 22)
    c.drawCentredString(a_cx, base, str(a))
    c.drawCentredString(b_cx, base, str(b))
    c.setFillColor(T.text2)
    c.setFont("AvD", 22)
    c.drawCentredString(minus_x, base, "\u2212")
    c.drawCentredString(eq_x, base, "=")
    bk.box(box_x, base - 9, 34, 32, a - b, size=17, reveal=T.ink if example else None)

    ty = base - 56                      # baseline of the ten at the bottom of the curve
    c.setFillColor(T.ink)
    c.setFont("Rnd", 18)
    c.drawCentredString(mid, ty, str(ten))
    tw = sw(str(ten), "Rnd", 18) / 2 + 5
    y_top, y_low = base - 9, ty + 6

    # down: leaves the first number straight down, arrives at the ten going right
    s0, s3 = (a_cx, y_top), (mid - tw, y_low)
    s1 = (s0[0], y_low + 0.45 * (y_top - y_low))
    s2 = (s3[0] - 0.55 * (s3[0] - s0[0]), y_low)
    # up: leaves the ten going right, arrives at the second number going straight up
    u0, u3 = (mid + tw, y_low), (b_cx, y_top)
    u1 = (u0[0] + 0.55 * (u3[0] - u0[0]), y_low)
    u2 = (u3[0], y_low + 0.45 * (y_top - y_low))
    curve_arrow(bk, s0, s1, s2, s3)
    curve_arrow(bk, u0, u1, u2, u3)

    # bubbles on the curves; the white fill hides the line underneath
    r = 12
    reveal = T.accent if example else None
    for (p0, p1, p2, p3), t, val in [((s0, s1, s2, s3), 0.45, j1), ((u0, u1, u2, u3), 0.55, j2)]:
        bx, by = bezier_point(p0, p1, p2, p3, t)
        c.setFillColor(white)
        c.setStrokeColor(T.accent)
        c.setLineWidth(1.4)
        c.circle(bx, by, r, stroke=1, fill=1)
        bk.value(bx, by, val, 13, reveal)
    return ty - 6


def jump_diagram(bk, x0, top, a, b, guided=False, example=False):
    """
    WeMath jump diagram for a − b across a ten (the difference through ten):

        15  −  8  = [7]
          ↘  10  ↗          jump from 15 down to 10, then from 10 to 8
        (5)  +  (2)         the two jumps; add them for the answer

    guided=True adds small labels under the circles ("15 to 10", "10 to 8").
    Returns the bottom y.
    """
    if JUMP_STYLE == "inline":
        return jump_inline(bk, x0, top, a, b, example)
    c = bk.c
    ten = (b // 10 + 1) * 10
    j1, j2 = a - ten, ten - b
    base = top - 22
    a_cx, minus_x, b_cx, eq_x, box_x = x0 + 18, x0 + 53, x0 + 88, x0 + 120, x0 + 138
    mid = (a_cx + b_cx) / 2
    c.setFillColor(T.ink)
    c.setFont("Rnd", 22)
    c.drawCentredString(a_cx, base, str(a))
    c.drawCentredString(b_cx, base, str(b))
    c.setFillColor(T.text2)
    c.setFont("AvD", 22)
    c.drawCentredString(minus_x, base, "−")
    c.drawCentredString(eq_x, base, "=")
    reveal = T.accent if example else None
    bk.box(box_x, base - 9, 40, 32, a - b, size=17, reveal=T.ink if example else None)

    ty = base - 44  # the ten, between the two numbers
    c.setFillColor(T.ink)
    c.setFont("Rnd", 18)
    c.drawCentredString(mid, ty, str(ten))
    tw = sw(str(ten), "Rnd", 18) / 2 + 6
    curve_arrow(bk, (a_cx, base - 8), (a_cx, ty + 2), (a_cx + 4, ty + 6), (mid - tw, ty + 6))
    curve_arrow(bk, (mid + tw, ty + 6), (b_cx - 4, ty + 6), (b_cx, ty + 2), (b_cx, base - 8))

    # each circle sits right under its arrow, so it reads as "the size of this jump"
    cy = base - 62
    jump_circle(bk, a_cx, cy, j1, r=15, reveal=reveal)
    jump_circle(bk, b_cx, cy, j2, r=15, reveal=reveal)
    plus_sign(bk, mid, cy - 18)
    if guided:
        bk.captions(cy - 26, [(a_cx, f"{a} to {ten}"), (b_cx, f"{ten} to {b}")])
        return cy - 30
    return cy - 17


def jump_dots(bk, x, y, a, b, cell=11):
    """Two ten-frames showing a: the first b dots blue, the jumps orange (orange = the answer)."""
    fills = ["a" if i < b else "b" for i in range(a)]
    bk.frames(x, y, cell, fills, gap=6)


def jump_column_inline(bk, x, top, w, a, b):
    """
    Test style, vertical: a column subtraction with the jumps curving out to the ten
    beside it and back in to the second number.

          14 ─╮
              (4)
               10
              (3)
       −   7 ←╯
       ─────
         [ ]
    """
    c = bk.c
    ten = (b // 10 + 1) * 10
    j1, j2 = a - ten, ten - b
    xr = x + w / 2 + 12              # right edge of the column (column + curves sit centred)
    y1, y2 = top - 34, top - 116     # baselines of a and b
    c.setFillColor(T.ink)
    c.setFont("Rnd", 22)
    c.drawRightString(xr, y1, str(a))
    c.drawRightString(xr, y2, str(b))
    c.setFillColor(T.text2)
    c.setFont("AvD", 22)
    c.drawString(xr - 46, y2, "\u2212")
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.4)
    c.line(xr - 48, y2 - 10, xr + 2, y2 - 10)
    bk.box(xr - 40, y2 - 48, 42, 32, a - b, size=17)

    tx = xr + 46                     # the ten, out to the right (kept close to the column)
    ty = (y1 + y2) / 2 - 6
    c.setFillColor(T.ink)
    c.setFont("Rnd", 18)
    c.drawCentredString(tx, ty, str(ten))
    ten_top, ten_bot = ty + 16, ty - 5
    m1, m2 = y1 + 7, y2 + 7          # vertical middles of the two numbers

    # out from the first number, down into the ten
    s0, s3 = (xr + 6, m1), (tx, ten_top)
    s1 = (s0[0] + 0.55 * (s3[0] - s0[0]), m1)
    s2 = (tx, ten_top + 0.45 * (m1 - ten_top))
    # down out of the ten, back in to the second number
    u0, u3 = (tx, ten_bot), (xr + 6, m2)
    u1 = (tx, ten_bot - 0.45 * (ten_bot - m2))
    u2 = (u3[0] + 0.55 * (tx - u3[0]), m2)
    curve_arrow(bk, s0, s1, s2, s3)
    curve_arrow(bk, u0, u1, u2, u3)
    for (p0, p1, p2, p3), t, val in [((s0, s1, s2, s3), 0.5, j1), ((u0, u1, u2, u3), 0.5, j2)]:
        bx, by = bezier_point(p0, p1, p2, p3, t)
        c.setFillColor(white)
        c.setStrokeColor(T.accent)
        c.setLineWidth(1.4)
        c.circle(bx, by, 11, stroke=1, fill=1)
        bk.value(bx, by, val, 12)


def jump_vertical(bk, x, top, w, a, b):
    """The same jumps drawn top to bottom: a, then 10, then b; circles beside each jump."""
    c = bk.c
    ten = (b // 10 + 1) * 10
    bk.fit_eq(x + GUT, top - 22, w - GUT - 8, f"{a} − {b} = [{a - b}]", size=17)
    vx = x + 64
    rows = [(a, top - 58), (ten, top - 104), (b, top - 150)]
    c.setFillColor(T.ink)
    for n, ry in rows:
        c.setFont("Rnd", 19)
        c.drawCentredString(vx, ry, str(n))
    bk.arrow(vx, top - 64, vx, top - 86)
    bk.arrow(vx, top - 110, vx, top - 132)
    cx = vx + 26  # right beside each arrow
    jump_circle(bk, cx, top - 75, a - ten, r=13, size=14)
    jump_circle(bk, cx, top - 121, ten - b, r=13, size=14)


def learn_back_through_ten(bk):
    y = bk.new_page("Back Through Ten", "Jump to 10, then jump to the number.", name_line=False, big=True,
                    footer="WeMath  ·  Back Through Ten")
    gap, ph = 22, 176
    pw = (CW - 2 * gap) / 3
    xs = [M + i * (pw + gap) for i in range(3)]
    c = bk.c

    def step(i, title, fills, note_parts):
        x = xs[i]
        panel(bk, x, y - ph, pw, ph)
        c.setFillColor(T.dot_a)
        c.setFont("Rnd", 22)
        c.drawString(x + 12, y - 28, str(i + 1))
        c.setFillColor(T.ink)
        c.setFont("Rnd", 16)
        c.drawCentredString(x + pw / 2 + 10, y - 27, title)
        bk.frames(x + (pw - 146) / 2, y - 84, 14, fills, gap=6)
        color_eq(bk, x + pw / 2, y - ph + 26, note_parts, 26, anchor="center")

    # 15 − 8: blue = the 8, orange = the jumps
    step(0, "15 to 10", dots(10) + dots(5, "b"), [("jump", "op"), ("5", "b")])
    step(1, "10 to 8", dots(8) + dots(2, "b"), [("jump", "op"), ("2", "b")])
    step(2, "add the jumps", dots(8) + dots(2, "b") + dots(5, "b"),
         [("5", "b"), ("+", "op"), ("2", "b"), ("=", "op"), ("7", None)])
    for i in range(2):
        ax = xs[i] + pw + gap / 2
        p = c.beginPath()
        p.moveTo(ax - 5, y - ph / 2 + 8)
        p.lineTo(ax + 6, y - ph / 2)
        p.lineTo(ax - 5, y - ph / 2 - 8)
        p.close()
        c.setFillColor(T.muted)
        c.drawPath(p, stroke=0, fill=1)
    # the rounded font has no minus sign, so build the line with color_eq (signs in Avenir)
    color_eq(bk, M + CW / 2, y - ph - 20, [("So", "op"), ("15", None), ("−", "op"), ("8", "a"),
                                          ("=", "op"), ("7", "b")], 16, anchor="center")
    y -= ph + 40

    label(bk, M, y, "Write it like this")
    inline = JUMP_STYLE == "inline"
    jump_diagram(bk, M + (CW - JUMP_W) / 2, y - 4, 15, 8, guided=True, example=True)
    y -= 4 + (90 if inline else 132) + 14

    turn_h = 110 if inline else 146
    bottom = your_turn(bk, y, h=turn_h)
    bk.ask("13 − 4 = []")
    jump_diagram(bk, M + (CW - JUMP_W) / 2, bottom + turn_h - 4, 13, 4, guided=True)
    teacher_note(bk, "Goal: subtract across ten by finding how far apart the numbers are. For 15 − 8 say "
                     "“15 to 10 is 5. 10 to 8 is 2. 5 and 2 is 7.” The second jump is the buddy of 8. "
                     "Check with addition: 8 + 7 = 15.")


def practice_back_through_ten(bk):
    title = "Back Through Ten: Practice"
    y = bk.new_page(title, "Jump to 10, then to the number. Add the two jumps.")
    y = bk.part(y, 1, "See the jumps", f"The {'orange' if T.dot_b else 'hollow'} dots are the jumps.")

    def dots_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} − {b} = []")
        x0 = x + GUT - 4
        jump_diagram(bk, x0, cy + p1_h - 8, a, b, guided=True)
        jump_dots(bk, x0, cy + 18, a, b)
    p1_h = 146 if JUMP_STYLE == "inline" else 176
    y = practice_cards(bk, y, [(13, 8), (12, 9), (15, 6), (11, 7), (18, 9), (13, 5)],
                       1, 2, 3, p1_h, 12, dots_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "Jump through ten", "Fill in both jumps, then add them.")

    def jump_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} − {b} = []")
        jump_diagram(bk, x + GUT - 4, cy + p2_h - 8, a, b, guided=True)
    p2_h = 104 if JUMP_STYLE == "inline" else 140
    practice_cards(bk, y, [(12, 3), (15, 9), (11, 4), (14, 8), (17, 9), (13, 6), (12, 5), (16, 8)],
                   7, 2, 4, p2_h, 12, jump_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 3, "Up and down", "Subtract in a column. Jump out to 10 and back, then add the jumps."
                if JUMP_STYLE == "inline" else "The same jumps, going down. Add the two jumps.")

    def vertical_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} − {b} = []")
        if JUMP_STYLE == "inline":
            jump_column_inline(bk, x, cy + 172 - 4, w, a, b)
        else:
            jump_vertical(bk, x, cy + 164 - 4, w, a, b)
    col_h = 172 if JUMP_STYLE == "inline" else 164
    y = practice_cards(bk, y, [(11, 9), (14, 7), (13, 9), (12, 6), (15, 7), (11, 3)],
                       15, 3, 2, col_h, 10, vertical_card) - 30

    y = bk.part(y, 4, "Less help", "No arrows this time. Fill in the two jumps.")

    def less_help_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} − {b} = []")
        bk.eq(x + GUT, cy + 50, f"{a} − {b} = [{a - b}]", size=20)
        jump_circle(bk, x + GUT + 16, cy + 22, a - 10, r=13, size=13)
        plus_sign(bk, x + GUT + 42, cy + 17, 13)
        jump_circle(bk, x + GUT + 68, cy + 22, 10 - b, r=13, size=13)
        bk.captions(cy + 22 - 3, [(x + GUT + 110, "jumps")])
    practice_cards(bk, y, [(12, 8), (14, 9), (11, 6), (16, 7)], 21, 2, 2, 84, 10, less_help_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 5, "Bigger numbers", "Jump to the ten in the middle.")

    def big_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} − {b} = []")
        jump_diagram(bk, x + GUT - 4, cy + big_h - 8, a, b)
    big_h = 104 if JUMP_STYLE == "inline" else 128
    y = practice_cards(bk, y, [(32, 28), (41, 37), (53, 46), (64, 58), (72, 67), (85, 79)],
                       25, 2, 3, big_h, 12, big_card) - 30
    y = bk.part(y, 6, "On your own", "No help. Think: how far to 10?")
    compact(bk, y, ["13 − 7 = [6]", "11 − 8 = [3]", "12 − 4 = [8]",
                    "17 − 8 = [9]", "14 − 5 = [9]", "11 − 5 = [6]"], 31)

    # No help at all: small and big numbers mixed together.
    y = bk.new_page(title, first=False)
    y = bk.part(y, 7, "Small numbers", "No help this time.")
    small = [(17, 5), (19, 4), (16, 3), (18, 7), (20, 6), (20, 4), (20, 9), (19, 13), (17, 12),
             (21, 18), (22, 17), (23, 16), (15, 11), (18, 14), (24, 19)]
    y = compact(bk, y, [f"{a} \u2212 {b} = [{a - b}]" for a, b in small], 37) - 30
    y = bk.part(y, 8, "Big numbers", "No help this time.")
    big = [(43, 38), (51, 46), (62, 57), (74, 69), (83, 76), (91, 85), (25, 19), (36, 29),
           (47, 39), (58, 49), (66, 59), (95, 88), (34, 27), (71, 64), (82, 78)]
    compact(bk, y, [f"{a} \u2212 {b} = [{a - b}]" for a, b in big], 52)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Jump through ten.")
    words(bk, y, [
        ("Mia had 11 balloons. 2 floated away. How many balloons does Mia have now?",
         "11 − 2 = 9", "9", "balloons"),
        ("There are 14 birds on a fence. 6 fly away. How many birds are still on the fence?",
         "14 − 6 = 8", "8", "birds"),
        ("Jake has 16 crayons. Emma has 9 crayons. How many more crayons does Jake have?",
         "16 − 9 = 7", "7", "crayons"),
        ("There are 12 kids in a class. 7 are girls. How many are boys?",
         "12 − 7 = 5", "5", "boys"),
        ("Challenge: Ana has 31 cards. Ben has 26 cards. How many more cards does Ana have?",
         "31 − 26 = 5", "5", "cards"),
    ], 67)


# ====================================================================== 6. Doubles and Near Doubles

def dot_pair(bk, x, y, top_n, bottom_n, r=5, step=14):
    """
    Two rows of dots lined up in pairs (like a domino). Top row at y, bottom row below it.
    Bottom dots past top_n are the "one more" and drawn in the buddy colour.
    A small gap after every 5 dots helps kids see the number without counting.
    """
    gap = r * 2 + 5

    def px(i):
        return x + i * step + (step * 0.45 if i >= 5 else 0)
    for i in range(top_n):
        bk.dot(px(i), y, r, "a")
    for i in range(bottom_n):
        bk.dot(px(i), y - gap, r, "a" if i < top_n else "b")
    return px(max(top_n, bottom_n) - 1) + r - x  # width


def learn_doubles(bk):
    y = bk.new_page("Doubles and Near Doubles", "Same number, two times!", name_line=False, big=True,
                    footer="WeMath  ·  Doubles and Near Doubles")
    c = bk.c
    # hero: 6 and 6 lined up like twins
    dot_pair(bk, M + 50, y - 30, 6, 6, r=10, step=27)
    for row_y, lab in [(y - 37, "6"), (y - 62, "6")]:
        c.setFillColor(T.dot_a)
        c.setFont("Rnd", 20)
        c.drawRightString(M + 22, row_y, lab)
    color_eq(bk, M + 262, y - 46, [("6", "a"), ("+", "op"), ("6", "a"), ("=", "op"), ("12", None)], 42)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 16)
    c.drawString(M + 264, y - 76, "Double 6 is 12!")
    y -= 96

    label(bk, M, y, "All the doubles")
    y -= 10
    half = CW / 2
    for n in range(1, 11):
        col, row = (0, n - 1) if n <= 5 else (1, n - 6)
        x = M + col * half
        ry = y - row * 31
        # dots right-aligned so each picture sits next to its equation
        dw = (n - 1) * 9 + (9 * 0.45 if n > 5 else 0) + 3.4
        dot_pair(bk, x + 112 - dw, ry - 12, n, n, r=3.4, step=9)
        color_eq(bk, x + 128, ry - 22, [(str(n), "a"), ("+", "op"), (str(n), "a"), ("=", "op"),
                                        (str(2 * n), None)], 20)
    y -= 5 * 31 + 18

    label(bk, M, y, "Near doubles: one more than a double")
    y -= 12
    gap, ph = 22, 122
    pw = (CW - 2 * gap) / 3
    xs = [M + i * (pw + gap) for i in range(3)]
    steps = [("6 + 7", 6, 7, [("6", "a"), ("+", "op"), ("7", None)]),
             ("double 6", 6, 6, [("6", "a"), ("+", "op"), ("6", "a"), ("=", "op"), ("12", None)]),
             ("1 more", 6, 7, [("12", None), ("+", "op"), ("1", "b"), ("=", "op"), ("13", None)])]
    for i, (title, top_n, bot_n, result) in enumerate(steps):
        x = xs[i]
        panel(bk, x, y - ph, pw, ph)
        c.setFillColor(T.dot_a)
        c.setFont("Rnd", 22)
        c.drawString(x + 12, y - 28, str(i + 1))
        c.setFillColor(T.ink)
        c.setFont("Rnd", 16)
        c.drawCentredString(x + pw / 2 + 10, y - 27, title)
        dw = (7 - 1) * 15 + 15 * 0.45 + 12
        if i == 1:  # the double: the seventh dot is set aside
            dot_pair(bk, x + (pw - dw) / 2, y - 54, 6, 6, r=6, step=15)
            bk.dot(x + (pw - dw) / 2 + 6 * 15 + 15 * 0.45 + 10, y - 54 - 17, 6, "b")
        else:
            dot_pair(bk, x + (pw - dw) / 2, y - 54, top_n, bot_n, r=6, step=15)
        color_eq(bk, x + pw / 2, y - ph + 20, result, 22, anchor="center")
    for i in range(2):
        ax = xs[i] + pw + gap / 2
        p = c.beginPath()
        p.moveTo(ax - 5, y - ph / 2 + 8)
        p.lineTo(ax + 6, y - ph / 2)
        p.lineTo(ax - 5, y - ph / 2 - 8)
        p.close()
        c.setFillColor(T.muted)
        c.drawPath(p, stroke=0, fill=1)
    y -= ph + 14

    bottom = your_turn(bk, y, h=90)
    bk.ask("double 2 = [], so 2 + 3 = []")
    dot_pair(bk, M + 140, bottom + 52, 2, 3, r=8, step=22)
    bk.eq(M + 260, bottom + 50, "double 2 = [4]", size=20)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvM", 11)
    bk.c.drawString(M + 236, bottom + 15, "so")
    bk.eq(M + 260, bottom + 14, "2 + 3 = [5]", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: know the doubles to 10 + 10 by heart, then use them for near doubles. "
                     "Say “6 + 7 is double 6 and 1 more. 12 and 1 more is 13.” Two hands, egg cartons "
                     "and dominoes make doubles easy to see.")


def practice_doubles(bk):
    title = "Doubles and Near Doubles: Practice"
    y = bk.new_page(title, "Learn the doubles, then use them for near doubles.")
    y = bk.part(y, 1, "Doubles with dots", "Each row has the same number.")

    def double_card(x, cy, w, n):
        bk.ask(f"double {n} = []")
        dot_pair(bk, x + GUT, cy + 96 - 22, n, n, r=5, step=14)
        bk.eq(x + GUT, cy + 16, f"double {n} = [{2 * n}]", size=20)
    y = practice_cards(bk, y, [6, 3, 8, 5, 9, 7], 1, 2, 3, 96, 10, double_card) - 30

    y = bk.part(y, 2, "Doubles facts", "In the boxes that go together, write the same number.")
    compact(bk, y, ["4 + 4 = [8]", "[6] + [6] = 12", "2 + 2 = [4]", "[8] + [8] = 16",
                    "10 + 10 = [20]", "[7] + [7] = 14", "3 + 3 = [6]", "[9] + [9] = 18",
                    "1 + 1 = [2]", "double [5] = 10"], 7, cols=2)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 3, "Near doubles with dots", "Find the double, then add 1 more.")

    def near_card(x, cy, w, item):
        n, m = item
        bk.ask(f"double {n} = [], so {n} + {m} = []")
        dot_pair(bk, x + GUT, cy + 124 - 22, n, m, r=5, step=14)
        bk.eq(x + GUT, cy + 52, f"double {n} = [{2 * n}]", size=18)
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvM", 10)
        bk.c.drawString(x + GUT, cy + 17, "so")
        bk.eq(x + GUT + 22, cy + 16, f"{n} + {m} = [{n + m}]", size=18)
    y = practice_cards(bk, y, [(7, 8), (3, 4), (8, 9), (5, 6), (9, 10), (4, 5)],
                       17, 2, 3, 124, 10, near_card) - 30

    y = bk.part(y, 4, "Bigger number first", "Double the smaller number, then add 1.")

    def flip_card(x, cy, w, item):
        a, b = item
        bk.ask(f"double {b} = [], so {a} + {b} = []")
        bk.eq(x + GUT, cy + 50, f"double {b} = [{2 * b}]", size=18)
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvM", 10)
        bk.c.drawString(x + GUT, cy + 17, "so")
        bk.eq(x + GUT + 22, cy + 16, f"{a} + {b} = [{a + b}]", size=18)
    practice_cards(bk, y, [(9, 8), (7, 6), (5, 4), (6, 5)], 23, 2, 2, 82, 10, flip_card)

    # No help, in four kinds: missing double, near double (find the total),
    # missing near double, and big numbers.
    y = bk.new_page(title, first=False)
    y = bk.part(y, 5, "Find the missing double", "Both numbers are the same.")
    y = compact(bk, y, ["[7] + 7 = 14", "2 + [2] = 4", "[9] + 9 = 18", "4 + [4] = 8", "[8] + 8 = 16",
                        "[6] + 6 = 12", "[5] + 5 = 10", "9 + [9] = 18", "[3] + 3 = 6", "8 + [8] = 16",
                        "7 + [7] = 14", "1 + [1] = 2", "[10] + 10 = 20", "6 + [6] = 12",
                        "[2] + 2 = 4"], 27) - 30
    y = bk.part(y, 6, "Find the near double", "The numbers are 1 apart. Double the smaller, add 1.")
    compact(bk, y, [f"{a} + {b} = [{a + b}]" for a, b in
                    [(5, 6), (3, 2), (7, 8), (4, 5), (6, 7), (2, 1), (8, 9), (9, 10),
                     (4, 3), (3, 4), (5, 4), (2, 3), (1, 2), (10, 11), (11, 10)]], 42)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 7, "Find the missing near double", "The two numbers are 1 apart.")
    y = compact(bk, y, ["[6] + 7 = 13", "8 + [9] = 17", "7 + [8] = 15", "[4] + 5 = 9",
                        "5 + [6] = 11", "[8] + 7 = 15", "[9] + 8 = 17", "[5] + 4 = 9",
                        "6 + [7] = 13", "[3] + 4 = 7", "[10] + 9 = 19", "4 + [3] = 7"], 57) - 30
    y = bk.part(y, 8, "Big numbers", "Ten and ten, then the ones.")
    compact(bk, y, ["11 + 11 = [22]", "12 + 13 = [25]", "[11] + 11 = 22", "14 + 14 = [28]",
                    "14 + 15 = [29]", "12 + [12] = 24", "13 + 13 = [26]", "11 + 12 = [23]",
                    "[12] + 13 = 25", "12 + 12 = [24]", "13 + 14 = [27]", "13 + [14] = 27"], 69)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Look for a double.")
    words(bk, y, [
        ("Sam has 6 toy cars. Lily has the same number. How many toy cars do they have together?",
         "6 + 6 = 12", "12", "toy cars"),
        ("A spider has 8 legs. How many legs do 2 spiders have?",
         "8 + 8 = 16", "16", "legs"),
        ("Ella found 5 shells. Ben found 1 more shell than Ella. How many shells did they find together?",
         "5 + 6 = 11", "11", "shells"),
        ("Max read 9 pages on Monday and 9 pages on Tuesday. How many pages did he read?",
         "9 + 9 = 18", "18", "pages"),
    ], 81)


# ====================================================================== 7. Tens and Ones

STICK_W, STICK_GAP = 14, 7


def ten_stick(bk, x, y, h=60, w=STICK_W, kind="a"):
    """A ten: a rounded bar holding 10 dots (like 10 straws bundled). y = bottom."""
    c = bk.c
    c.setFillColor(white)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.1)
    c.roundRect(x, y, w, h, w / 2, stroke=1, fill=1)
    step = (h - 4) / 10
    for i in range(10):
        bk.dot(x + w / 2, y + h - 2 - (i + 0.5) * step, min(w * 0.3, step * 0.38), kind)


def ones_dots(bk, x, top, n, r=4.5, step=12, kind="b"):
    """Loose ones: columns of 5, filled from the top. Returns the width used."""
    for i in range(n):
        col, row = divmod(i, 5)
        bk.dot(x + r + col * step, top - r - row * step, r, kind)
    return 0 if n == 0 else r * 2 + ((n - 1) // 5) * step


def tens_ones_picture(bk, x, y, tens, ones, h=60):
    """Ten-sticks then loose ones, bottoms lined up at y. Returns the width."""
    for i in range(tens):
        ten_stick(bk, x + i * (STICK_W + STICK_GAP), y, h)
    ox = x + tens * (STICK_W + STICK_GAP) + (6 if tens else 0)
    w = ones_dots(bk, ox, y + h, ones)
    return ox + w - x


def quick_tens(bk, x, y, tens, ones, h=46, color=None):
    """Quick drawing: a line for each ten, a dot for each one. y = bottom."""
    c = bk.c
    col = color or T.ink
    c.setStrokeColor(col)
    c.setLineWidth(2.4)
    for i in range(tens):
        c.line(x + i * 10, y, x + i * 10, y + h)
    ox = x + tens * 10 + 8
    c.setFillColor(col)
    for i in range(ones):
        cl, row = divmod(i, 5)
        c.circle(ox + cl * 10, y + h - 4 - row * 9.5, 3.2, stroke=0, fill=1)


def pv_chart(bk, x, y, tens, ones, w=58, h=62, given=True):
    """A tens | ones chart. given=False makes the digits answer boxes."""
    c = bk.c
    for i, (lab, val) in enumerate([("tens", tens), ("ones", ones)]):
        bx = x + i * w
        bk.make_ten_box(bx, y, w, h, 17, None)
        c.setFillColor(T.ink)
        c.setFont("AvB", 10)
        c.drawCentredString(bx + w / 2, y + h - 12, lab)
        if given:
            c.setFillColor(T.dot_a if i == 0 else T.accent)
            c.setFont("Rnd", 28)
            c.drawCentredString(bx + w / 2, y + 10, str(val))
        else:
            bk.box(bx + w / 2 - 16, y + 7, 32, 30, val, size=18)


def learn_tens_and_ones(bk):
    y = bk.new_page("Tens and Ones", "10 ones make 1 ten.", name_line=False, big=True,
                    footer="WeMath  ·  Tens and Ones")
    c = bk.c
    # 10 loose ones bundle into 1 ten
    for i in range(10):
        r_, cl = divmod(i, 5)
        bk.dot(M + 22 + cl * 19, y - 28 - r_ * 19, 7, "b")
    bk.arrow(M + 124, y - 38, M + 166, y - 38)
    ten_stick(bk, M + 182, y - 88, h=86, w=18)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawCentredString(M + 60, y - 74, "10 ones")
    c.drawCentredString(M + 191, y - 104, "1 ten")
    color_eq(bk, M + 250, y - 52, [("10", "b"), ("ones", None), ("=", "op"), ("1", "a"), ("ten", None)], 30)
    y -= 128

    label(bk, M, y, "34 is 3 tens and 4 ones")
    y -= 12
    tens_ones_picture(bk, M + 12, y - 80, 3, 4, h=76)
    pv_chart(bk, M + 124, y - 80, 3, 4)
    color_eq(bk, M + 256, y - 56, [("=", "op"), ("3", "a"), ("4", "b", "tight")], 40)
    color_eq(bk, M + 372, y - 52, [("30", "a"), ("+", "op"), ("4", "b"), ("=", "op"), ("34", None)], 20)
    y -= 104

    label(bk, M, y, "Quick tens: a line for each ten, a dot for each one")
    y -= 12
    quick_tens(bk, M + 16, y - 58, 5, 2, h=50)
    color_eq(bk, M + 110, y - 42, [("=", "op"), ("5", "a"), ("2", "b", "tight")], 34)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 14)
    c.drawString(M + 190, y - 40, "5 tens and 2 ones")
    y -= 78

    label(bk, M, y, "Count by tens")
    for i in range(10):
        sx = M + 22 + i * 48
        ten_stick(bk, sx, y - 52, h=38, w=11)
        c.setFillColor(T.dot_a)
        c.setFont("Rnd", 14)
        c.drawCentredString(sx + 5.5, y - 68, str((i + 1) * 10))
    y -= 84

    bottom = your_turn(bk, y, h=104)
    bk.ask("tens and ones in the picture of 53")
    tens_ones_picture(bk, M + 130, bottom + 16, 5, 3, h=62)
    bk.fit_eq(M + 290, bottom + 40, CW - 290 - 16, "[5] tens [3] ones = [53]", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: see a two-digit number as tens and ones. Say “34 is 3 tens and 4 ones.” "
                     "Bundle real straws or craft sticks into tens with rubber bands before drawing quick tens. "
                     "The tens digit always tells you more than the ones digit.")


def practice_tens_and_ones(bk):
    title = "Tens and Ones: Practice"
    y = bk.new_page(title, "Count the tens, then the ones.")
    y = bk.part(y, 1, "Count the tens and ones", "Each stick is 10. Each dot is 1.")

    def count_card(x, cy, w, n):
        t, o = divmod(n, 10)
        bk.ask(f"tens and ones in the picture of {n}")
        tens_ones_picture(bk, x + GUT, cy + 44, t, o, h=60)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{t}] tens [{o}] ones = [{n}]", size=17)
    y = practice_cards(bk, y, [23, 41, 35, 17, 62, 54], 1, 2, 3, 120, 10, count_card) - 30

    y = bk.part(y, 2, "Draw it", "Draw quick tens: a line for each ten, a dot for each one.")

    def draw_card(x, cy, w, n):
        t, o = divmod(n, 10)
        bk.ask(f"draw {n} as quick tens")
        bk.c.setFillColor(T.ink)
        bk.c.setFont("Rnd", 30)
        bk.c.drawString(x + GUT, cy + 64, str(n))
        bx, bw = x + GUT + 58, w - GUT - 66
        bk.work(bx, cy + 42, bw, 62, "Draw it")
        if bk.key:
            quick_tens(bk, bx + 14, cy + 48, t, o, h=40, color=T.answer)
        bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"[{t}] tens [{o}] ones", size=17)
    practice_cards(bk, y, [38, 26], 7, 2, 1, 114, 10, draw_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "Draw it", "(continued)")
    y = practice_cards(bk, y, [45, 19], 9, 2, 1, 114, 10, draw_card) - 30
    y = bk.part(y, 3, "Count the tens", "Count by tens: 10, 20, 30 \u2026")

    def tens_card(x, cy, w, n):
        t = n // 10
        bk.ask(f"count the tens in the picture of {n}")
        tens_ones_picture(bk, x + GUT, cy + 36, t, 0, h=48)
        bk.fit_eq(x + GUT, cy + 10, w - GUT - 10, f"[{t}] tens = [{n}]", size=16)
    y = practice_cards(bk, y, [30, 70, 50, 20, 80, 60], 11, 2, 3, 94, 10, tens_card) - 30
    y = bk.part(y, 4, "Tens plus ones", "Put the tens and the ones together.")
    compact(bk, y, ["40 + 6 = [46]", "[30] + 9 = 39", "70 + [2] = 72", "50 + 5 = [55]",
                    "[80] + 1 = 81", "20 + [8] = 28"], 17)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 4, "Tens plus ones", "(continued)")
    y = compact(bk, y, ["90 + 4 = [94]", "60 + [3] = 63", "[40] + 7 = 47", "[20] + 2 = 22",
                        "80 + 9 = [89]", "50 + [7] = 57"], 23) - 30
    y = bk.part(y, 5, "Which is more?", "Circle the bigger number. Look at the tens first.")

    def more_card(x, cy, w, pair):
        a, b = pair
        bk.ask(f"which is more: {a} or {b}")
        for j, n in enumerate((a, b)):
            nx = x + GUT + 30 + j * 90
            bk.c.setFillColor(T.ink)
            bk.c.setFont("Rnd", 24)
            bk.c.drawCentredString(nx, cy + 14, str(n))
            if bk.key and n == max(a, b):
                bk.c.setStrokeColor(T.answer)
                bk.c.setLineWidth(1.6)
                bk.c.ellipse(nx - 26, cy + 5, nx + 26, cy + 40, stroke=1, fill=0)
    y = practice_cards(bk, y, [(46, 64), (39, 41), (72, 27), (58, 85), (33, 30), (19, 91)],
                       29, 2, 3, 46, 8, more_card) - 30
    y = bk.part(y, 6, "Tens and ones", "No help this time. How many tens? How many ones?")
    compact(bk, y, [f"[{n // 10}] tens [{n % 10}] ones = {n}" for n in (76, 31, 98, 13, 67, 42)], 35, cols=2)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 6, "Tens and ones", "(continued)")
    y = compact(bk, y, [f"[{n // 10}] tens [{n % 10}] ones = {n}" for n in (85, 29, 70, 61, 93, 54)], 41,
                cols=2) - 30
    y = bk.part(y, 7, "Put it together", "No help this time. What number is it?")
    compact(bk, y, ["6 tens 2 ones = [62]", "70 + 5 = [75]", "8 tens 4 ones = [84]", "40 + 3 = [43]",
                    "2 tens 5 ones = [25]", "30 + 7 = [37]", "7 tens 1 one = [71]", "90 + 6 = [96]",
                    "3 tens 6 ones = [36]", "50 + 1 = [51]", "9 tens 9 ones = [99]", "5 tens 0 ones = [50]"],
            47, cols=2)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Think in tens and ones.")
    words(bk, y, [
        ("Sam has 3 bags with 10 marbles in each bag. He also has 5 loose marbles. How many marbles does Sam have?",
         "30 + 5 = 35", "35", "marbles"),
        ("There are 4 boxes of 10 crayons and 8 loose crayons. How many crayons are there?",
         "40 + 8 = 48", "48", "crayons"),
        ("A farmer has 6 bundles of 10 sticks and 9 single sticks. How many sticks does the farmer have?",
         "60 + 9 = 69", "69", "sticks"),
        ("Mia has 27 stickers. A full sheet holds 10 stickers. How many full sheets can Mia fill?",
         "2 tens 7 ones = 27", "2", "sheets"),
        ("Challenge: Ben has 5 tens and 14 ones. What number does Ben have?",
         "50 + 14 = 64", "64", ""),
    ], 59)


# ====================================================================== 8. Ten More, Ten Less


def cross_out(bk, x, y, w, h):
    """An X over a ten-stick that is taken away."""
    c = bk.c
    c.setStrokeColor(T.accent)
    c.setLineWidth(2.2)
    c.line(x - 4, y + 4, x + w + 4, y + h - 4)
    c.line(x - 4, y + h - 4, x + w + 4, y + 4)


def more_less_picture(bk, x, y, n, change, h=60, w=STICK_W):
    """
    n as ten-sticks and loose ones. change="more" adds an orange ten after the tens,
    change="less" crosses out the last ten. y = bottom. Returns the width.
    """
    t, o = divmod(n, 10)
    step = w + STICK_GAP * w / STICK_W
    for i in range(t):
        ten_stick(bk, x + i * step, y, h, w)
    sx = x + t * step
    if change == "more":
        ten_stick(bk, sx, y, h, w, kind="b")
        sx += step
    elif change == "less" and t:
        cross_out(bk, x + (t - 1) * step, y, w, h)
    ox = sx + (6 if sx > x else 0)
    r = 4.5 * w / STICK_W
    return ox + ones_dots(bk, ox, y + h, o, r=r, step=r * 2.7) - x


def tens_digit_eq(bk, x, y, a, op, b, size):
    """a op 10 = answer with the changed tens digit in orange (learning page)."""
    ans = a + 10 if op == "+" else a - 10
    t, o = divmod(ans, 10)
    color_eq(bk, x, y, [(str(a), "a"), (op, "op"), ("10", "b"), ("=", "op"),
                        (str(t), "b"), (str(o), None, "tight")], size)


def learn_ten_more_less(bk):
    y = bk.new_page("Ten More, Ten Less", "Only the tens change.", name_line=False, big=True,
                    footer="WeMath  ·  Ten More, Ten Less")
    c = bk.c
    label(bk, M, y - 6, "10 more: add a ten")
    more_less_picture(bk, M + 14, y - 96, 34, "more", h=76, w=18)
    tens_digit_eq(bk, M + 236, y - 64, 34, "+", 10, 34)
    y -= 122

    label(bk, M, y - 6, "10 less: take away a ten")
    more_less_picture(bk, M + 14, y - 96, 34, "less", h=76, w=18)
    tens_digit_eq(bk, M + 236, y - 64, 34, "−", 10, 34)
    y -= 122

    label(bk, M, y - 6, "Count on by tens. The ones stay the same.")
    nums = [6, 16, 26, 36, 46, 56]
    gx = 86
    for i, n in enumerate(nums):
        cx = M + 30 + i * gx
        parts = [(str(n), None)] if n < 10 else [(str(n // 10), "b"), (str(n % 10), None, "tight")]
        color_eq(bk, cx, y - 50, parts, 28, anchor="center")
        if i:
            bk.arrow(cx - gx + 22, y - 41, cx - 22, y - 41)
            c.setFillColor(T.text2)
            c.setFont("AvD", 11)
            c.drawCentredString(cx - gx / 2, y - 30, "+10")
    y -= 76

    bottom = your_turn(bk, y, h=112)
    bk.ask("52 + 10 = []")
    bk.ask("52 − 10 = []")
    more_less_picture(bk, M + 130, bottom + 22, 52, None, h=66)
    bk.eq(M + 300, bottom + 64, "52 + 10 = [62]", size=22)
    bk.eq(M + 300, bottom + 22, "52 − 10 = [42]", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: find 10 more or 10 less without counting by ones. Say “34 is 3 tens. "
                     "One more ten makes 4 tens, so 44.” Add or remove a real bundle of 10 sticks first. "
                     "Point out that the ones digit never changes.")


def practice_ten_more_less(bk):
    title = "Ten More, Ten Less: Practice"
    y = bk.new_page(title, "Add a ten, or take a ten away.")
    y = bk.part(y, 1, "10 more", f"Add the {'orange' if T.dot_b else 'hollow'} ten. What number is it now?")

    def more_card(x, cy, w, n):
        bk.ask(f"{n} + 10 = []")
        more_less_picture(bk, x + GUT, cy + 44, n, "more")
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{n} + 10 = [{n + 10}]", size=18)
    y = practice_cards(bk, y, [23, 45, 16, 51, 38, 64], 1, 2, 3, 120, 10, more_card) - 30
    y = bk.part(y, 2, "10 less", "Take away the crossed-out ten. What number is left?")

    def less_card(x, cy, w, n):
        bk.ask(f"{n} − 10 = []")
        more_less_picture(bk, x + GUT, cy + 44, n, "less")
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{n} − 10 = [{n - 10}]", size=18)
    practice_cards(bk, y, [47, 32], 7, 2, 1, 120, 10, less_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "10 less", "(continued)")
    y = practice_cards(bk, y, [56, 29, 71, 18], 9, 2, 2, 120, 10, less_card) - 30
    y = bk.part(y, 3, "10 less and 10 more", "Fill in both sides.")

    def side_card(x, cy, w, n):
        c = bk.c
        bk.ask(f"10 less and 10 more than {n}")
        bx = x + GUT
        mid = bx + 100
        for lab, val, lx in (("10 less", n - 10, bx), ("10 more", n + 10, bx + 156)):
            c.setFillColor(T.text2)
            c.setFont("AvD", 10)
            c.drawCentredString(lx + 22, cy + 48, lab)
            bk.box(lx, cy + 12, 44, 30, val, size=18)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 24)
        c.drawCentredString(mid, cy + 18, str(n))
        bk.arrow(mid - 22, cy + 27, bx + 52, cy + 27)
        bk.arrow(mid + 22, cy + 27, bx + 148, cy + 27)
    practice_cards(bk, y, [35, 67, 14, 82, 49, 21, 73, 58], 13, 2, 4, 64, 8, side_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 4, "Keep going", "Jump by tens. Fill in the next three numbers.")

    def chain_card(x, cy, w, item):
        op, start = item
        c = bk.c
        bk.ask(f"keep going {op}10 from {start}")
        seq = [start + (10 if op == "+" else -10) * i for i in range(6)]
        c.setFillColor(T.text2)
        c.setFont("AvD", 15)
        c.drawString(x + GUT, cy + 18, f"{op}10")
        gx = 68
        for i, n in enumerate(seq):
            cx = x + GUT + 82 + i * gx
            if i < 3:
                c.setFillColor(T.ink)
                c.setFont("Rnd", 20)
                c.drawCentredString(cx, cy + 18, str(n))
            else:
                bk.box(cx - 21, cy + 10, 42, 30, n, size=18)
            if i:
                bk.arrow(cx - gx + 25, cy + 25, cx - 25, cy + 25)
    y = practice_cards(bk, y, [("+", 3), ("−", 96), ("+", 41), ("−", 58)], 21, 1, 4, 50, 8,
                       chain_card) - 30
    y = bk.part(y, 5, "Ten more", "No help this time.")
    y = compact(bk, y, ["26 + 10 = [36]", "53 + 10 = [63]", "74 + 10 = [84]", "31 + 10 = [41]",
                        "87 + 10 = [97]", "15 + 10 = [25]", "42 + 10 = [52]", "69 + 10 = [79]",
                        "90 + 10 = [100]", "57 + 10 = [67]", "13 + 10 = [23]", "88 + 10 = [98]"], 25) - 30
    y = bk.part(y, 6, "Ten less", "No help this time.")
    compact(bk, y, ["64 − 10 = [54]", "19 − 10 = [9]", "85 − 10 = [75]",
                    "37 − 10 = [27]", "100 − 10 = [90]", "43 − 10 = [33]"], 37)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 6, "Ten less", "(continued)")
    y = compact(bk, y, ["76 − 10 = [66]", "28 − 10 = [18]", "91 − 10 = [81]",
                        "60 − 10 = [50]", "15 − 10 = [5]", "59 − 10 = [49]"], 43) - 30
    y = bk.part(y, 7, "Both ways", "Find 10 more, then 10 less.")
    y = compact(bk, y, ["63 + 10 = [73]", "63 \u2212 10 = [53]", "81 + 10 = [91]", "81 \u2212 10 = [71]",
                        "24 + 10 = [34]", "24 \u2212 10 = [14]", "68 + 10 = [78]", "68 \u2212 10 = [58]"],
                49, cols=2) - 30
    y = bk.part(y, 8, "Mixed", "Watch the sign: + or −.")
    compact(bk, y, ["77 + 10 = [87]", "40 − 10 = [30]", "92 − 10 = [82]", "36 + 10 = [46]",
                    "11 − 10 = [1]", "89 + 10 = [99]", "25 − 10 = [15]", "60 + 10 = [70]",
                    "83 − 10 = [73]", "48 + 10 = [58]", "99 − 10 = [89]", "30 + 10 = [40]"], 57)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Is it 10 more or 10 less?")
    words(bk, y, [
        ("Lena has 46 stickers. Her friend gives her 10 more. How many stickers does Lena have now?",
         "46 + 10 = 56", "56", "stickers"),
        ("There are 73 books on a shelf. The class borrows 10 of them. How many books are left?",
         "73 − 10 = 63", "63", "books"),
        ("A bus has 28 kids on it. At the next stop, 10 more kids get on. How many kids are on the bus now?",
         "28 + 10 = 38", "38", "kids"),
        ("A tree has 84 apples. Then 10 apples fall off. How many apples are on the tree now?",
         "84 \u2212 10 = 74", "74", "apples"),
        ("Challenge: Ava has 35 cents. She gets 10 cents, then 10 more. How many cents does she have now?", "35 + 10 + 10 = 55", "55", "cents"),
    ], 69)


# ====================================================================== 9. Adding Two-Digit Numbers


def add_picture(bk, x, y, a, b, h=56, w=STICK_W):
    """a in blue (sticks + ones), then b in orange. y = bottom. Returns the width."""
    step = w + STICK_GAP * w / STICK_W
    r = 4.5 * w / STICK_W
    sx = x
    for n, kind in ((a, "a"), (b, "b")):
        t, o = divmod(n, 10)
        for i in range(t):
            ten_stick(bk, sx + i * step, y, h, w, kind=kind)
        ox = sx + t * step + 2
        ow = ones_dots(bk, ox, y + h, o, r=r, step=r * 2.4, kind=kind)
        sx = ox + ow + 16
    return sx - 16 - x


def split_rows(bk, x, top, a, b, helped=False, size=15, gap=24, op="+"):
    """
    The tens / ones / total scaffold for a + b (or a − b with op="−"), first baseline at `top`.
    helped=True prints the tens and ones parts; otherwise every part is a box.
    The total row always adds the tens and ones back together.
    """
    ta, oa, tb, ob = a // 10 * 10, a % 10, b // 10 * 10, b % 10
    f = (lambda p, q: p + q) if op == "+" else (lambda p, q: p - q)
    fmt = (lambda v: str(v)) if helped else (lambda v: f"[{v}]")
    rows = [("tens", f"{fmt(ta)} {op} {fmt(tb)} = [{f(ta, tb)}]"),
            ("ones", f"{fmt(oa)} {op} {fmt(ob)} = [{f(oa, ob)}]"),
            ("total", f"[{f(ta, tb)}] + [{f(oa, ob)}] = [{f(a, b)}]")]
    for i, (lab, text) in enumerate(rows):
        yy = top - i * gap
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 10)
        bk.c.drawString(x, yy + 1, lab)
        bk.eq(x + 38, yy, text, size=size)


def learn_adding_two_digit(bk):
    y = bk.new_page("Adding Two-Digit Numbers", "Add the tens. Add the ones. Put them together.",
                    name_line=False, big=True, footer="WeMath  ·  Adding Two-Digit Numbers")
    c = bk.c

    def rows(x, top, lines, size=22, gap=34):
        for i, (lab, parts) in enumerate(lines):
            yy = top - i * gap
            c.setFillColor(T.text2)
            c.setFont("AvD", 12)
            c.drawString(x, yy + 2, lab)
            color_eq(bk, x + 50, yy, parts, size)

    label(bk, M, y - 6, "34 + 25: add the tens, then the ones")
    add_picture(bk, M + 14, y - 104, 34, 25, h=80, w=17)
    rows(M + 270, y - 42, [("tens", [("30", "a"), ("+", "op"), ("20", "b"), ("=", "op"), ("50", None)]),
                           ("ones", [("4", "a"), ("+", "op"), ("5", "b"), ("=", "op"), ("9", None)]),
                           ("total", [("50", None), ("+", "op"), ("9", None), ("=", "op"), ("59", None)])])
    y -= 132

    label(bk, M, y - 6, "38 + 25: 8 + 5 makes a new ten")
    bk.frames(M + 14, y - 80, 19, ["a"] * 8 + ["b"] * 5)
    color_eq(bk, M + 14, y - 106, [("8", "a"), ("+", "op"), ("5", "b"), ("=", "op"), ("1", None),
                                   ("ten", None), ("3", None), ("ones", None)], 15)
    rows(M + 270, y - 42, [("tens", [("30", "a"), ("+", "op"), ("20", "b"), ("=", "op"), ("50", None)]),
                           ("ones", [("8", "a"), ("+", "op"), ("5", "b"), ("=", "op"), ("13", None)]),
                           ("total", [("50", None), ("+", "op"), ("13", None), ("=", "op"), ("63", None)])])
    y -= 140

    bottom = your_turn(bk, y, h=140)
    bk.ask("42 + 35 = []")
    bk.eq(M + 40, bottom + 60, "42 + 35 = [77]", size=24)
    split_rows(bk, M + 290, bottom + 102, 42, 35, size=17, gap=36)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: add two-digit numbers by place value. Say “30 and 20 is 50. 4 and 5 is 9. "
                     "50 and 9 is 59.” When the ones make 10 or more, bundle 10 of them into a new ten "
                     "(use packet 3’s make-ten). Always add the tens first.")


def practice_adding_two_digit(bk):
    title = "Adding Two-Digit Numbers: Practice"
    y = bk.new_page(title, "Tens with tens, ones with ones.")
    y = bk.part(y, 1, "Add tens", "Count on by tens: add the second number's tens.")

    def tens_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} + {b} = []")
        add_picture(bk, x + GUT, cy + 44, a, b, h=52)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)
    y = practice_cards(bk, y, [(23, 30), (41, 20), (15, 40), (36, 20), (52, 30), (17, 50)],
                       1, 2, 3, 106, 10, tens_card) - 30
    y = bk.part(y, 2, "Tens and ones", "Add the tens. Add the ones. Then put them together.")

    def picture_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} + {b} = []")
        add_picture(bk, x + GUT, cy + 120, a, b, h=54)
        bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)
        split_rows(bk, x + GUT, cy + 66, a, b, helped=True, size=13, gap=27)
    practice_cards(bk, y, [(23, 14), (32, 26)], 7, 2, 1, 180, 10, picture_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "Tens and ones", "(continued)")
    y = practice_cards(bk, y, [(41, 25), (15, 22)], 9, 2, 1, 180, 10, picture_card) - 30
    y = bk.part(y, 3, "Split it", "Fill in every box.")

    def split_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} + {b} = []")
        bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)
        split_rows(bk, x + GUT, cy + 66, a, b, size=13, gap=27)
    practice_cards(bk, y, [(52, 34), (61, 27), (43, 45), (26, 31), (74, 13), (53, 24)],
                   11, 2, 3, 122, 10, split_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 4, "Make a new ten", "The ones make 10 or more. Add them to the tens.")
    y = practice_cards(bk, y, [(27, 15), (46, 38), (19, 24), (58, 27), (35, 29), (63, 18)],
                       17, 2, 3, 122, 10, split_card) - 30
    y = bk.part(y, 5, "Add tens", "No help this time.")
    compact(bk, y, ["45 + 30 = [75]", "18 + 60 = [78]", "72 + 20 = [92]", "26 + 40 = [66]",
                    "39 + 50 = [89]", "51 + 40 = [91]", "14 + 70 = [84]", "63 + 30 = [93]",
                    "27 + 20 = [47]"], 23)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 6, "No new ten", "No help this time.")
    y = compact(bk, y, ["21 + 46 = [67]", "34 + 52 = [86]", "15 + 73 = [88]", "62 + 25 = [87]",
                        "47 + 31 = [78]", "13 + 64 = [77]", "71 + 18 = [89]", "36 + 12 = [48]",
                        "42 + 27 = [69]", "58 + 21 = [79]", "16 + 82 = [98]", "25 + 44 = [69]"], 32) - 30
    y = bk.part(y, 7, "Make a new ten", "No help this time.")
    y = compact(bk, y, ["28 + 16 = [44]", "37 + 45 = [82]", "59 + 33 = [92]", "14 + 27 = [41]",
                        "66 + 25 = [91]", "48 + 19 = [67]", "25 + 38 = [63]", "17 + 56 = [73]",
                        "39 + 39 = [78]", "44 + 28 = [72]", "76 + 17 = [93]", "29 + 55 = [84]"], 44) - 30
    y = bk.part(y, 8, "Mixed", "Some make a new ten and some don\u2019t.")
    compact(bk, y, ["34 + 47 = [81]", "52 + 36 = [88]", "18 + 75 = [93]", "63 + 24 = [87]",
                    "27 + 49 = [76]", "41 + 38 = [79]", "56 + 35 = [91]", "22 + 53 = [75]",
                    "15 + 68 = [83]"], 56)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Add the tens, then the ones.")
    words(bk, y, [
        ("There are 32 kids in one class and 25 kids in another class. How many kids are there in all?",
         "32 + 25 = 57", "57", "kids"),
        ("Leo read 24 pages on Monday and 30 pages on Tuesday. How many pages did he read?",
         "24 + 30 = 54", "54", "pages"),
        ("A store has 46 red apples and 28 green apples. How many apples does the store have?",
         "46 + 28 = 74", "74", "apples"),
        ("Nia has 38 beads. She buys 15 more beads. How many beads does she have now?",
         "38 + 15 = 53", "53", "beads"),
        ("Challenge: Jo has 19 cards. Max has 10 more cards than Jo. How many cards do they have together?",
         "19 + 29 = 48", "48", "cards"),
    ], 65)


# ====================================================================== 10. Subtracting Two-Digit Numbers


def take_away_picture(bk, x, y, a, b, h=56, w=STICK_W):
    """a as blue sticks + ones; the last tens and ones of b are crossed out. y = bottom."""
    c = bk.c
    step = w + STICK_GAP * w / STICK_W
    r = 4.5 * w / STICK_W
    ta, oa, tb, ob = a // 10, a % 10, b // 10, b % 10
    for i in range(ta):
        ten_stick(bk, x + i * step, y, h, w)
        if i >= ta - tb:
            cross_out(bk, x + i * step, y, w, h)
    ox = x + ta * step + 2
    ones_dots(bk, ox, y + h, oa, r=r, step=r * 2.4, kind="a")
    c.setStrokeColor(T.accent)
    c.setLineWidth(1.8)
    for i in range(oa - ob, oa):
        col, row = divmod(i, 5)
        cx, cy = ox + r + col * r * 2.4, y + h - r - row * r * 2.4
        c.line(cx - r * 1.5, cy - r * 1.5, cx + r * 1.5, cy + r * 1.5)


def learn_subtracting_two_digit(bk):
    y = bk.new_page("Subtracting Two-Digit Numbers", "Take away the tens. Take away the ones.",
                    name_line=False, big=True, footer="WeMath  ·  Subtracting Two-Digit Numbers")
    c = bk.c

    def rows(x, top, lines, size=22, gap=34):
        for i, (lab, parts) in enumerate(lines):
            yy = top - i * gap
            c.setFillColor(T.text2)
            c.setFont("AvD", 12)
            c.drawString(x, yy + 2, lab)
            color_eq(bk, x + 50, yy, parts, size)

    label(bk, M, y - 6, "64 − 20: take away 2 tens")
    take_away_picture(bk, M + 14, y - 96, 64, 20, h=76, w=17)
    color_eq(bk, M + 270, y - 62, [("64", "a"), ("−", "op"), ("20", "b"), ("=", "op"), ("44", None)], 30)
    y -= 118

    label(bk, M, y - 6, "58 − 23: take away the tens, then the ones")
    take_away_picture(bk, M + 14, y - 104, 58, 23, h=80, w=17)
    rows(M + 270, y - 42, [("tens", [("50", "a"), ("−", "op"), ("20", "b"), ("=", "op"), ("30", None)]),
                           ("ones", [("8", "a"), ("−", "op"), ("3", "b"), ("=", "op"), ("5", None)]),
                           ("total", [("30", None), ("+", "op"), ("5", None), ("=", "op"), ("35", None)])])
    y -= 136

    bottom = your_turn(bk, y, h=140)
    bk.ask("76 − 42 = []")
    bk.eq(M + 40, bottom + 60, "76 − 42 = [34]", size=24)
    split_rows(bk, M + 290, bottom + 102, 76, 42, size=17, gap=36, op="−")
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: subtract by place value. Say “50 take away 20 is 30. 8 take away 3 is 5. "
                     "30 and 5 is 35.” Every problem has enough ones. Part 4 only spots the ones that don’t "
                     "(52 − 27); borrowing comes in a later packet.")


def practice_subtracting_two_digit(bk):
    title = "Subtracting Two-Digit Numbers: Practice"
    y = bk.new_page(title, "Tens from tens, ones from ones.")
    y = bk.part(y, 1, "Take away tens", "Cross out the tens. What is left?")

    def tens_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} − {b} = []")
        take_away_picture(bk, x + GUT, cy + 44, a, b, h=52)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{a} − {b} = [{a - b}]", size=18)
    y = practice_cards(bk, y, [(57, 30), (73, 40), (46, 20), (65, 50), (84, 30), (39, 20)],
                       1, 2, 3, 106, 10, tens_card) - 30
    y = bk.part(y, 2, "Tens and ones", "Take away the tens. Take away the ones. Then put them together.")

    def picture_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} − {b} = []")
        take_away_picture(bk, x + GUT, cy + 120, a, b, h=54)
        bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"{a} − {b} = [{a - b}]", size=18)
        split_rows(bk, x + GUT, cy + 66, a, b, helped=True, size=13, gap=27, op="−")
    practice_cards(bk, y, [(47, 23), (68, 35)], 7, 2, 1, 180, 10, picture_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "Tens and ones", "(continued)")
    y = practice_cards(bk, y, [(59, 14), (76, 52)], 9, 2, 1, 180, 10, picture_card) - 30
    y = bk.part(y, 3, "Split it", "Fill in every box.")

    def split_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} − {b} = []")
        bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"{a} − {b} = [{a - b}]", size=18)
        split_rows(bk, x + GUT, cy + 66, a, b, size=13, gap=27, op="−")
    practice_cards(bk, y, [(85, 42), (97, 63), (64, 31), (78, 41), (99, 27), (56, 24)],
                   11, 2, 3, 122, 10, split_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 4, "Enough ones?", "Can you take away the ones? Circle yes or no. Don’t solve it.")

    def enough_card(x, cy, w, item):
        a, b = item
        bk.ask(f"enough ones? {a} − {b}")
        bk.eq(x + GUT, cy + 15, f"{a} − {b}", size=18)
        yes = a % 10 >= b % 10
        for j, word in enumerate(["yes", "no"]):
            px = x + w - 104 + j * 50
            bk.c.setFillColor(T.text2)
            bk.c.setFont("AvD", 13)
            bk.c.drawCentredString(px + 20, cy + 16, word)
            if bk.key and (word == "yes") == yes:
                bk.c.setStrokeColor(T.answer)
                bk.c.setLineWidth(1.6)
                bk.c.ellipse(px + 2, cy + 8, px + 38, cy + 34, stroke=1, fill=0)
    # shuffle the questions so the right answer isn't always on one side ("yes" stays first)
    y = practice_cards(bk, y, [(43, 21), (52, 27), (71, 38), (66, 35), (34, 19), (89, 46)],
                       17, 2, 3, 44, 8, enough_card) - 30
    y = bk.part(y, 5, "Take away tens", "No help this time.")
    y = compact(bk, y, ["94 − 60 = [34]", "58 − 20 = [38]", "71 − 50 = [21]",
                        "86 − 40 = [46]", "47 − 30 = [17]", "63 − 20 = [43]",
                        "99 − 70 = [29]", "52 − 40 = [12]", "78 − 60 = [18]"], 23) - 30
    y = bk.part(y, 6, "Take away ones", "No help this time.")
    compact(bk, y, ["47 − 5 = [42]", "68 − 3 = [65]", "89 − 6 = [83]",
                    "36 − 4 = [32]", "75 − 2 = [73]", "59 − 8 = [51]",
                    "94 − 3 = [91]", "28 − 7 = [21]", "66 − 5 = [61]"], 32)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 7, "Tens and ones", "No help this time.")
    y = compact(bk, y, ["67 − 24 = [43]", "88 − 53 = [35]", "49 − 36 = [13]", "95 − 41 = [54]",
                        "74 − 22 = [52]", "58 − 17 = [41]", "86 − 65 = [21]", "39 − 15 = [24]",
                        "97 − 54 = [43]", "65 − 33 = [32]", "77 − 46 = [31]", "48 − 25 = [23]"],
                41) - 30
    y = bk.part(y, 8, "Mixed", "Tens, ones, or both?")
    compact(bk, y, ["83 − 51 = [32]", "76 − 4 = [72]", "92 − 30 = [62]", "69 − 47 = [22]",
                    "45 − 20 = [25]", "87 − 6 = [81]", "54 − 13 = [41]", "98 − 75 = [23]",
                    "63 − 50 = [13]", "29 − 8 = [21]", "79 − 34 = [45]", "56 − 5 = [51]"], 53)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Take away the tens, then the ones.")
    words(bk, y, [
        ("There are 68 birds in a tree. Then 25 birds fly away. How many birds are left in the tree?",
         "68 − 25 = 43", "43", "birds"),
        ("Sam has 75 cents. He spends 40 cents on a snack. How many cents does he have left?",
         "75 − 40 = 35", "35", "cents"),
        ("A box has 48 crayons. Then 6 crayons break. How many crayons are not broken?",
         "48 − 6 = 42", "42", "crayons"),
        ("There are 86 books on a cart. The kids take 34 of them. How many books are still on the cart?",
         "86 − 34 = 52", "52", "books"),
        ("Challenge: Mia has 89 beads. She uses 30 for a necklace and 6 for a ring. How many are left?",
         "89 − 30 − 6 = 53", "53", "beads"),
    ], 65)


# ====================================================================== 11. Missing Numbers


def jump_stops(start, total):
    """Stops for jumping up: the start, the next ten, the last ten, the total (no repeats)."""
    nxt = -(-start // 10) * 10
    last = total // 10 * 10
    if nxt > last:
        return [start, total]
    stops = [start]
    for s in (nxt, last, total):
        if s != stops[-1]:
            stops.append(s)
    return stops


def jump_up(bk, x, base, stops, spacing, size=18, H=20, r=11, vsize=12, given=True, example=False):
    """
    Jumping up from the start to the total: the stops in a row (left to right) with a curved
    arrow over each jump and the jump size in a bubble on the curve (packet 5 style).
    given=False draws the inside stops (the tens) as boxes to fill in.
    """
    c = bk.c
    xs = [x + i * spacing for i in range(len(stops))]
    for i, (sx, n) in enumerate(zip(xs, stops)):
        if given or i in (0, len(stops) - 1):
            c.setFillColor(T.ink)
            c.setFont("Rnd", size)
            c.drawCentredString(sx, base, str(n))
        else:
            bk.box(sx - size * 0.95, base - size * 0.42, size * 1.9, size * 1.5, n, size=size * 0.85)
    lift = size * 1.2  # clears both printed numbers and answer boxes
    reveal = T.accent if example else None
    for i in range(len(stops) - 1):
        p0 = (xs[i] + size * 0.25, base + lift)
        p3 = (xs[i + 1] - size * 0.25, base + lift)
        p1 = (p0[0] + 4, base + lift + H)
        p2 = (p3[0] - 4, base + lift + H)
        curve_arrow(bk, p0, p1, p2, p3)
        bx, by = bezier_point(p0, p1, p2, p3, 0.5)
        c.setFillColor(white)
        c.setStrokeColor(T.accent)
        c.setLineWidth(1.4)
        c.circle(bx, by, r, stroke=1, fill=1)
        bk.value(bx, by, stops[i + 1] - stops[i], vsize, reveal)


def jumps_sum(stops):
    return " + ".join(f"[{b - a}]" for a, b in zip(stops, stops[1:])) + f" = [{stops[-1] - stops[0]}]"


def learn_missing_numbers(bk):
    y = bk.new_page("Missing Numbers", "Start at the number you know. Jump up to the total.",
                    name_line=False, big=True, footer="WeMath  ·  Missing Numbers")
    c = bk.c

    def example(y, a, total, note):
        stops = jump_stops(a, total)
        label(bk, M, y - 6, note)
        color_eq(bk, M, y - 44, [(str(a), "a"), ("+", "op"), (str(total - a), "b"), ("=", "op"),
                                 (str(total), None)], 26)
        jump_up(bk, M + 236, y - 88, stops, 84 if len(stops) == 4 else 110, size=24, H=30, r=15, vsize=16,
                example=True)
        jumps = [b - p for p, b in zip(stops, stops[1:])]
        parts = []
        for k, j in enumerate(jumps):
            if k:
                parts.append(("+", "op"))
            parts.append((str(j), "b"))
        parts += [("=", "op"), (str(total - a), None)]
        color_eq(bk, M + 236, y - 122, parts, 20)

    example(y, 8, 13, "8 + ? = 13: jump to 10, then to 13")
    y -= 150
    example(y, 42, 75, "42 + ? = 75: jump to the next ten, then by tens, then the ones")
    y -= 156

    bottom = your_turn(bk, y, h=128)
    bk.ask("36 + [] = 64")
    stops = jump_stops(36, 64)
    bk.eq(M + 30, bottom + 70, "36 + [28] = 64", size=24)
    jump_up(bk, M + 270, bottom + 58, stops, 70, size=20, H=26, r=13, vsize=14, given=False)
    bk.fit_eq(M + 250, bottom + 16, CW - 260, jumps_sum(stops), size=16)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: find a missing addend by jumping up. Say “Start at 42. Jump to 50: that’s 8. "
                     "Jump to 70: that’s 20. Jump to 75: that’s 5. 8 + 20 + 5 = 33.” Always jump to the "
                     "next ten first, then by tens, then the ones.")


def practice_missing_numbers(bk):
    title = "Missing Numbers: Practice"
    y = bk.new_page(title, "Jump up from the number you know.")

    def jump_card(x, cy, w, item, given=True):
        a, total = item
        bk.ask(f"{a} + [] = {total}")
        stops = jump_stops(a, total)
        # ~15pt of air between the problem, the jumps and the sum row
        bk.fit_eq(x + GUT, cy + 122, w - GUT - 10, f"{a} + [{total - a}] = {total}", size=18)
        spacing = min(80, (w - GUT - 36) / (len(stops) - 1))
        jump_up(bk, x + GUT + 14, cy + 52, stops, spacing, given=given)
        bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, jumps_sum(stops), size=14)

    y = bk.part(y, 1, "Jump to 10, then up", "Fill in the jumps. Add them up.")
    y = practice_cards(bk, y, [(7, 12), (9, 15), (6, 14), (5, 13)], 1, 2, 2, 152, 10, jump_card) - 30
    y = bk.part(y, 2, "Jump to the next ten", "Then jump by tens, then the ones.")
    practice_cards(bk, y, [(27, 54), (36, 72)], 5, 2, 1, 152, 10, jump_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "Jump to the next ten", "(continued)")
    y = practice_cards(bk, y, [(18, 46), (64, 83)], 7, 2, 1, 152, 10, jump_card) - 30
    y = bk.part(y, 3, "Find the stops", "Write the tens you jump to. Then fill in the jumps.")
    practice_cards(bk, y, [(4, 13), (53, 91), (45, 97), (29, 60)], 9, 2, 2, 152, 10,
                   lambda x, cy, w, item: jump_card(x, cy, w, item, given=False))

    y = bk.new_page(title, first=False)
    y = bk.part(y, 4, "Up to 20", "No help this time.")
    y = compact(bk, y, ["9 + [4] = 13", "8 + [6] = 14", "3 + [9] = 12", "7 + [4] = 11",
                    "5 + [9] = 14", "9 + [7] = 16", "4 + [7] = 11", "8 + [3] = 11",
                    "6 + [9] = 15", "2 + [9] = 11", "3 + [8] = 11", "9 + [5] = 14"], 13) - 30
    y = bk.part(y, 5, "Jump to a ten", "No help this time. The total is a ten.")
    y = compact(bk, y, ["47 + [33] = 80", "6 + [14] = 20", "62 + [28] = 90", "35 + [25] = 60",
                        "18 + [22] = 40", "71 + [29] = 100", "54 + [16] = 70", "23 + [27] = 50",
                        "86 + [14] = 100"], 25)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 6, "Two-digit numbers", "No help this time.")
    y = compact(bk, y, ["24 + [33] = 57", "38 + [25] = 63", "15 + [41] = 56", "57 + [28] = 85",
                        "43 + [36] = 79", "66 + [27] = 93", "29 + [45] = 74", "52 + [19] = 71",
                        "17 + [65] = 82", "48 + [37] = 85", "33 + [29] = 62", "75 + [18] = 93"], 34) - 30
    y = bk.part(y, 7, "Mixed", "No help this time.")
    compact(bk, y, ["8 + [4] = 12", "46 + [24] = 70", "39 + [42] = 81", "7 + [9] = 16",
                    "58 + [34] = 92", "26 + [14] = 40", "5 + [7] = 12", "61 + [27] = 88",
                    "14 + [49] = 63"], 46)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Jump up from the number you know.")
    words(bk, y, [
        ("Lia has 8 stickers. She gets some more. Now she has 15. How many stickers did she get?",
         "8 + 7 = 15", "7", "stickers"),
        ("A book has 70 pages. Max has read 46 pages. How many more pages does he need to read?",
         "46 + 24 = 70", "24", "pages"),
        ("Ana has 9 shells. Ben has 16 shells. How many more shells does Ben have than Ana?",
         "9 + 7 = 16", "7", "shells"),
        ("The class needs 85 cups for a party. They have 52 cups. How many more cups do they need?",
         "52 + 33 = 85", "33", "cups"),
        ("Challenge: Zoe has saved 27 dollars. A bike costs 64 dollars. How many more dollars does she need?",
         "27 + 37 = 64", "37", "dollars"),
    ], 55)


# ====================================================================== 12. Subtracting with Borrowing
# Rows (break / tens / ones / total), like packets 9 and 10. A stacked-column version was also built
# and shown to the founder, who chose rows as the better first start; columns come in packet 14.

MINUS = "−"


def slash(bk, cx, cy, r, color=None):
    c = bk.c
    c.setStrokeColor(color or T.accent)
    c.setLineWidth(1.8)
    c.line(cx - r, cy - r, cx + r, cy + r)


def broken_picture(bk, x, y, a, b=None, h=60, w=STICK_W, cell=11):
    """
    a after breaking one ten: (tens - 1) blue sticks, the opened ten as a ten-frame of orange
    dots, then the loose ones. With b, the taken tens are crossed out and the taken ones
    slashed (loose ones first, then from the end of the frame). y = bottom.
    """
    step = w + STICK_GAP * w / STICK_W
    t, o = a // 10 - 1, a % 10
    tb, ob = (b // 10, b % 10) if b else (0, 0)
    for i in range(t):
        ten_stick(bk, x + i * step, y, h, w)
        if i >= t - tb:
            cross_out(bk, x + i * step, y, w, h)
    fx = x + t * step + 4
    fy = y + h - cell * 2
    bk.ten_frame(fx, fy, cell, ["b"] * 10)
    r = 4.5 * w / STICK_W
    ox = fx + cell * 5 + 8
    ones_dots(bk, ox, y + h, o, r=r, step=r * 2.4, kind="a")
    taken = ob
    for i in range(o - 1, -1, -1):  # loose ones first
        if taken == 0:
            break
        col, row = divmod(i, 5)
        slash(bk, ox + r + col * r * 2.4, y + h - r - row * r * 2.4, r * 1.5, T.ink)
        taken -= 1
    for i in range(9, 9 - taken, -1):  # then the frame, from the end
        slash(bk, fx + (i % 5) * cell + cell / 2, fy + cell * 2 - (i // 5) * cell - cell / 2, cell * 0.45, T.ink)
    return ox + (r * 2 if o else 0) - x


def borrow_rows(bk, x, top, a, b, helped=False, size=13, gap=26):
    """break / tens / ones / total for a − b when a ten has to be broken."""
    t, o = a // 10 * 10 - 10, a % 10 + 10
    tb, ob = b // 10 * 10, b % 10
    fmt = (lambda v: str(v)) if helped else (lambda v: f"[{v}]")
    rows = [("break", f"{a} = {fmt(t)} + {fmt(o)}"),
            ("tens", f"[{t}] {MINUS} {tb} = [{t - tb}]" if tb else f"[{t}] {MINUS} 0 = [{t}]"),
            ("ones", f"[{o}] {MINUS} {ob} = [{o - ob}]"),
            ("total", f"[{t - tb}] + [{o - ob}] = [{a - b}]")]
    for i, (lab, text) in enumerate(rows):
        yy = top - i * gap
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 10)
        bk.c.drawString(x, yy + 1, lab)
        bk.eq(x + 40, yy, text, size=size)


# shared problem sets (the two options differ only in how the subtraction is written)
B_BREAK = [63, 41, 85, 70, 34, 56]
B_HELPED = [(61, 34), (45, 19), (83, 47), (72, 25)]
B_BOXES = [(54, 36), (91, 46), (37, 18), (66, 29)]
B_NOHELP = [
    ("Break a ten", [(42, 17), (73, 35), (95, 58), (64, 29), (81, 52), (56, 38),
                     (33, 16), (75, 47), (62, 39), (84, 66), (51, 23), (93, 74)]),
    ("From a tens number", [(50, 23), (80, 46), (40, 17), (70, 38), (60, 24), (90, 52), (30, 14), (80, 61)]),
    ("Take away ones", [(43, 6), (72, 5), (31, 4), (85, 9), (64, 8), (26, 7), (92, 3), (57, 9)]),
    ("Mixed", [(68, 25), (54, 37), (79, 46), (82, 58), (45, 22), (63, 18),
               (97, 34), (71, 27), (38, 14), (86, 49), (59, 33), (44, 19)]),
]
B_WORDS = [
    ("There are 53 kids at the park. Then 27 kids go home. How many kids are still at the park?",
     f"53 {MINUS} 27 = 26", "26", "kids"),
    ("Mo has 40 cents. He spends 18 cents on a pencil. How many cents does he have left?",
     f"40 {MINUS} 18 = 22", "22", "cents"),
    ("A farm has 75 eggs. Then 39 eggs are sold. How many eggs are left?",
     f"75 {MINUS} 39 = 36", "36", "eggs"),
    ("Ivy has 63 beads. She uses 7 beads to make a ring. How many beads does she have left?",
     f"63 {MINUS} 7 = 56", "56", "beads"),
    ("Challenge: Leo has 90 stickers. He gives 25 to Mia and 30 to Sam. How many stickers are left?",
     f"90 {MINUS} 25 {MINUS} 30 = 35", "35", "stickers"),
]


def learn_borrowing(bk):
    y = bk.new_page("Subtracting with Borrowing", "Not enough ones? Break a ten.", name_line=False, big=True,
                    footer="WeMath  ·  Subtracting with Borrowing")
    c = bk.c
    label(bk, M, y - 6, "Break a ten: 10 ones come out of one ten")
    tens_ones_picture(bk, M + 14, y - 92, 5, 2, h=70)
    bk.arrow(M + 150, y - 58, M + 196, y - 58)
    broken_picture(bk, M + 214, y - 92, 52, h=70, cell=13)
    color_eq(bk, M + 14, y - 122, [("5", "a"), ("tens", None), ("2", "a"), ("ones", None), ("=", "op"),
                                   ("4", "a"), ("tens", None), ("12", "b"), ("ones", None)], 17)
    y -= 150

    label(bk, M, y - 6, f"52 {MINUS} 27: 2 {MINUS} 7? Not enough ones, so break a ten")
    broken_picture(bk, M + 14, y - 100, 52, 27, h=70, cell=13)
    lines = [("break", [("52", None), ("=", "op"), ("40", "a"), ("+", "op"), ("12", "b")]),
             ("tens", [("40", "a"), (MINUS, "op"), ("20", None), ("=", "op"), ("20", None)]),
             ("ones", [("12", "b"), (MINUS, "op"), ("7", None), ("=", "op"), ("5", None)]),
             ("total", [("20", None), ("+", "op"), ("5", None), ("=", "op"), ("25", None)])]
    for i, (lab, parts) in enumerate(lines):
        yy = y - 36 - i * 30
        c.setFillColor(T.text2)
        c.setFont("AvD", 12)
        c.drawString(M + 280, yy + 2, lab)
        color_eq(bk, M + 330, yy, parts, 20)
    y -= 160
    bottom = your_turn(bk, y, h=150)
    bk.ask(f"74 {MINUS} 38 = []")
    bk.eq(M + 30, bottom + 64, f"74 {MINUS} 38 = [36]", size=24)
    borrow_rows(bk, M + 270, bottom + 112, 74, 38, size=15, gap=30)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: subtract when there aren\u2019t enough ones. Ask \u201cCan I take 7 from 2? No, so break a "
                     "ten: 52 is 4 tens and 12 ones.\u201d Open a real bundle of 10 sticks. The ones step is a packet 5 "
                     "fact (12 \u2212 7).")


def practice_borrowing(bk):
    title = "Subtracting with Borrowing: Practice"
    y = bk.new_page(title, "Not enough ones? Break a ten first.")
    y = bk.part(y, 1, "Break a ten", "One ten opens into 10 ones. Add them to the ones you have.")

    def break_card(x, cy, w, n):
        bk.ask(f"break a ten: {n}")
        tens_ones_picture(bk, x + GUT, cy + 44, n // 10, n % 10, h=52)
        # the tens are given, so the only question is the new number of ones
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{n} = {n // 10 - 1} tens [{n % 10 + 10}] ones", size=17)
    y = practice_cards(bk, y, B_BREAK, 1, 2, 3, 106, 10, break_card) - 30

    def rows_card(x, cy, w, item, helped):
        a, b = item
        bk.ask(f"{a} {MINUS} {b} = []")
        bk.fit_eq(x + GUT, cy + 126, w - GUT - 10, f"{a} {MINUS} {b} = [{a - b}]", size=18)
        borrow_rows(bk, x + GUT, cy + 90, a, b, helped=helped)
    y = bk.part(y, 2, "Break, then subtract", "The ten is broken for you. Finish the rows.")
    practice_cards(bk, y, B_HELPED[:2], 7, 2, 1, 154, 10, lambda x, cy, w, it: rows_card(x, cy, w, it, True))
    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "Break, then subtract", "(continued)")
    y = practice_cards(bk, y, B_HELPED[2:], 9, 2, 1, 154, 10,
                       lambda x, cy, w, it: rows_card(x, cy, w, it, True)) - 30
    y = bk.part(y, 3, "Your turn to break", "Break the ten yourself. Fill in every box.")
    practice_cards(bk, y, B_BOXES, 11, 2, 2, 154, 10, lambda x, cy, w, it: rows_card(x, cy, w, it, False))

    y = bk.new_page(title, first=False)
    num = 15
    for k, (name, probs) in enumerate(B_NOHELP):
        if k == 3:
            y = bk.new_page(title, first=False)
        y = bk.part(y, 4 + k, name, "No help this time." if k < 3 else "Some need a broken ten. Some don’t.")
        y = compact(bk, y, [f"{a} {MINUS} {b} = [{a - b}]" for a, b in probs], num) - 30
        num += len(probs)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Not enough ones? Break a ten.")
    words(bk, y, B_WORDS, 55)


# ====================================================================== stacked (column) arithmetic
# Shared by packets 13, 14, 19 and 20.


def stacked(bk, x, y, a, b, op="+", mode="plain", size=20, header=False, places=None, room=True):
    """
    a op b written in columns. x = the sign, y = bottom of the answer boxes. Returns the top y used.
    mode "shown": the carried 1s (or the crossed-out digits and new digits) drawn as a worked example;
    "boxes": small boxes above the digits to write them in; "plain": blank space (the key fills it in).
    room=False leaves out the row for those marks (a worked example with nothing to carry).
    """
    c = bk.c
    res = a + b if op == "+" else a - b
    da, db = [int(ch) for ch in str(a)], [int(ch) for ch in str(b)]
    places = places or max(len(da), len(db), len(str(res)))
    sp = size * (1.4 if places <= 2 else 1.75)
    cols = [x + size * 1.5 + i * sp for i in range(places)]

    def pad(d):
        return [None] * (places - len(d)) + d
    ta, tb = pad(da), pad(db)
    marks, changed = {}, set()
    if op == "+":
        carry = 0
        for i in range(places - 1, -1, -1):
            carry = ((ta[i] or 0) + (tb[i] or 0) + carry) // 10
            if carry and i > 0:
                marks[i - 1] = "1"
    else:
        new = [d or 0 for d in ta]
        for i in range(places - 1, 0, -1):
            if new[i] < (tb[i] or 0):
                new[i] += 10
                new[i - 1] -= 1
                changed |= {i, i - 1}
        marks = {i: str(new[i]) for i in changed}

    bw, bh = size * 1.15, size * 1.3
    line_y = y + bh + 6
    bot = line_y + 7
    topb = bot + size * 1.25
    mark = topb + size * 1.35
    ms = size * 0.62
    if not room:
        mark, ms = topb + size * 0.85, 0
    c.setFillColor(T.ink)
    c.setFont("Rnd", size)
    for i in range(places):
        if ta[i] is not None:
            c.drawCentredString(cols[i], topb, str(ta[i]))
        if tb[i] is not None:
            c.drawCentredString(cols[i], bot, str(tb[i]))
    c.setFillColor(T.text2)
    c.setFont("AvD", size)
    c.drawCentredString(x, bot, "+" if op == "+" else MINUS)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.4)
    c.line(x - size * 0.5, line_y, cols[-1] + size * 0.7, line_y)
    rd = pad([int(ch) for ch in str(res)])
    for i in range(places):
        bk.box(cols[i] - bw / 2, y, bw, bh, "" if rd[i] is None else rd[i], size=size * 0.85)

    def crosses(col):
        for i in changed:
            c.setStrokeColor(col)
            c.setLineWidth(1.6)
            c.line(cols[i] - size * 0.38, topb - 2, cols[i] + size * 0.38, topb + size * 0.75)
    if mode == "shown" or (mode == "plain" and bk.key):
        col = T.accent if mode == "shown" else T.answer
        crosses(col)
        c.setFillColor(col)
        c.setFont("Rnd", ms)
        for i, t in marks.items():
            c.drawCentredString(cols[i], mark, t)
    elif mode == "boxes":
        if bk.key:
            crosses(T.answer)
        spots = range(places - 1) if op == "+" else range(places)
        for i in spots:
            w = size * 1.3 if (op != "+" and (places == 3 or i == places - 1)) else size * 1.0
            bk.box(cols[i] - w / 2, mark - 5, w, ms + 9, marks.get(i, ""), size=ms)
    top = mark + ms + 4
    if header:
        names = ["tens", "ones"] if places == 2 else ["hundreds", "tens", "ones"]
        c.setFillColor(T.text2)
        c.setFont("AvD", 7.5)
        for i, n in enumerate(names[-places:]):
            c.drawCentredString(cols[i], top + 5, n)
        top += 13
    return top


def stack_grid(bk, x, y, a, b, op="+", size=18):
    """Empty columns to copy a op b into (digits revealed on the key). x = sign, y = answer-box bottom."""
    c = bk.c
    res = a + b if op == "+" else a - b
    places = max(len(str(a)), len(str(b)), len(str(res)))
    sp = size * (1.4 if places <= 2 else 1.75)
    cols = [x + size * 1.5 + i * sp for i in range(places)]
    bw, bh = size * 1.15, size * 1.3
    line_y = y + bh + 6
    rows_y = [line_y + 5, line_y + 10 + bh]
    for n, ry in zip((b, a), rows_y):
        ds = [None] * (places - len(str(n))) + [int(ch) for ch in str(n)]
        for i in range(places):
            bk.box(cols[i] - bw / 2, ry, bw, bh, "" if ds[i] is None else ds[i], size=size * 0.85)
    c.setFillColor(T.text2)
    c.setFont("AvD", size)
    c.drawCentredString(x, rows_y[0] + bh * 0.3, "+" if op == "+" else MINUS)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.4)
    c.line(x - size * 0.5, line_y, cols[-1] + size * 0.7, line_y)
    rd = [None] * (places - len(str(res))) + [int(ch) for ch in str(res)]
    for i in range(places):
        bk.box(cols[i] - bw / 2, y, bw, bh, "" if rd[i] is None else rd[i], size=size * 0.85)
    top = rows_y[1] + bh + 4
    names = ["tens", "ones"] if places == 2 else ["hundreds", "tens", "ones"]
    c.setFillColor(T.text2)
    c.setFont("AvD", 7.5)
    for i, n in enumerate(names[-places:]):
        c.drawCentredString(cols[i], top + 3, n)
    return top + 11


def add_mat(bk, x, top, a, b, result=True, wt=150, wo=130, row_h=42):
    """
    A place-value mat for a + b: a tens column of sticks and a ones column of dots, one row per
    number (a blue, b orange). With result, a third row shows the total; when the ones make 10 or
    more, those 10 dots become a new stick (its dots keep their colours). Returns the bottom y.
    """
    c = bk.c
    hh = 18
    rows = [(a // 10, [("a", a % 10)], ["a"] * (a // 10)), (b // 10, [("b", b % 10)], ["b"] * (b // 10))]
    if result:
        ao, bo = a % 10, b % 10
        if ao + bo >= 10:
            new_ten = ["a"] * ao + ["b"] * (10 - ao)
            ones = [("b", ao + bo - 10)]
        else:
            new_ten = None
            ones = [("a", ao), ("b", bo)]
        rows.append((None, ones, ["a"] * (a // 10) + ["b"] * (b // 10) + ([new_ten] if new_ten else [])))
    n = len(rows)
    total_h = hh + n * row_h + (6 if result else 0)
    bottom = top - total_h
    if T.band is not None:
        c.setFillColor(T.band)
        c.rect(x, top - hh, wt + wo, hh, stroke=0, fill=1)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1)
    c.rect(x, bottom, wt + wo, total_h, stroke=1, fill=0)
    c.line(x + wt, bottom, x + wt, top)
    c.line(x, top - hh, x + wt + wo, top - hh)
    c.setFillColor(T.ink)
    c.setFont("AvB", 10)
    c.drawCentredString(x + wt / 2, top - 13, "tens")
    c.drawCentredString(x + wt + wo / 2, top - 13, "ones")
    sh, swid, sstep = row_h - 12, 9, 13
    for r, (_, ones, sticks) in enumerate(rows):
        ry = top - hh - (r + 1) * row_h - (6 if (result and r == n - 1) else 0)
        if result and r == n - 1:
            c.setStrokeColor(T.ink)
            c.setLineWidth(2)
            c.line(x, ry + row_h + 3, x + wt + wo, ry + row_h + 3)
        for i, k in enumerate(sticks):
            sx = x + 10 + i * sstep
            if isinstance(k, list):  # the new ten, made from the ones
                ten_stick_mixed(bk, sx, ry + 6, sh, swid, k)
            else:
                ten_stick(bk, sx, ry + 6, sh, swid, kind=k)
        ox, i = x + wt + 12, 0
        for kind, cnt in ones:
            for _ in range(cnt):
                bk.dot(ox + i * 10.5 + (5 if i >= 5 else 0), ry + row_h / 2, 4, kind)
                i += 1
    return bottom


def ten_stick_mixed(bk, x, y, h, w, kinds):
    """A ten-stick whose dots have their own kinds (a new ten made of blue and orange ones)."""
    c = bk.c
    c.setFillColor(white)
    c.setStrokeColor(T.accent)
    c.setLineWidth(1.6)
    c.roundRect(x, y, w, h, w / 2, stroke=1, fill=1)
    step = (h - 4) / 10
    for i, k in enumerate(kinds):
        bk.dot(x + w / 2, y + h - 2 - (i + 0.5) * step, min(w * 0.3, step * 0.38), k)


# ====================================================================== 13. Adding in Columns


def learn_adding_columns(bk):
    y = bk.new_page("Adding in Columns", "Tens under tens, ones under ones. Add the ones first.",
                    name_line=False, big=True, footer="WeMath  ·  Adding in Columns")
    c = bk.c

    def notes(x, y0, lines, gap=20):
        for k, line in enumerate(lines):
            c.setFillColor(T.text2)
            c.setFont("AvD", 12)
            c.drawString(x, y0 - k * gap, line)

    label(bk, M, y - 6, "43 + 26: line them up")
    stacked(bk, M + 40, y - 136, 43, 26, mode="shown", size=26, header=True, room=False)
    notes(M + 190, y - 50, ["1. Add the ones: 3 + 6 = 9", "2. Add the tens: 4 + 2 = 6", "3. 43 + 26 = 69"], 24)
    y -= 150

    label(bk, M, y - 6, "37 + 26: 7 + 6 = 13 ones. That makes a new ten!")
    add_mat(bk, M, y - 18, 37, 26, wt=150, wo=136, row_h=38)
    stacked(bk, M + 330, y - 150, 37, 26, mode="shown", size=26, header=True)
    notes(M + 300, y - 168, ["3 stays in the ones.", "The new ten goes on top of the tens."], 16)
    y -= 214

    bottom = your_turn(bk, y, h=150)
    bk.ask("48 + 35 = []")
    stacked(bk, M + 200, bottom + 14, 48, 35, mode="boxes", size=24, header=True)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: the written form of packet 9. Always start with the ones. When the ones make 10 or "
                     "more, bundle 10 into a new ten and write a small 1 on top of the tens. Say “7 and 6 is 13: "
                     "3 ones, and 1 new ten.”")


def practice_adding_columns(bk):
    title = "Adding in Columns: Practice"
    y = bk.new_page(title, "Add the ones first, then the tens.")

    def col5(x, cy, w, item, mode="plain", header=False):
        a, b = item
        bk.ask(f"{a} + {b} = []")
        stacked(bk, x + 26, cy + 8, a, b, mode=mode, size=18, header=header)

    y = bk.part(y, 1, "Stack and add", "Add the ones. Then add the tens.")
    y = practice_cards(bk, y, [(52, 37), (23, 41), (64, 25), (31, 17), (45, 33),
                               (17, 62), (26, 12), (40, 35), (18, 21), (63, 34)], 1, 5, 2, 124, 8,
                       lambda x, cy, w, it: col5(x, cy, w, it, header=True)) - 30

    y = bk.part(y, 2, "Line them up", "Write each number in the boxes: tens under tens, ones under ones.")

    def grid_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} + {b} = []")
        bk.eq(x + GUT, cy + 128, f"{a} + {b}", size=16)
        stack_grid(bk, x + 40, cy + 8, a, b, size=18)
    y = practice_cards(bk, y, [(46, 3), (5, 72), (30, 48), (61, 8)], 11, 4, 1, 150, 8, grid_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 3, "Make a new ten", "10 ones make a new ten. Write the 1 in the box on top.")

    def mat_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} + {b} = []")
        add_mat(bk, x + GUT, cy + 132, a, b, result=False, wt=140, wo=124, row_h=44)
        stacked(bk, x + GUT + 330, cy + 12, a, b, mode="boxes", size=22, header=True)
    y = practice_cards(bk, y, [(28, 35), (46, 27)], 15, 1, 2, 150, 10, mat_card) - 30
    y = bk.part(y, 4, "Carry the new ten", "Do the ones make 10 or more? Write the new ten on top.")
    practice_cards(bk, y, [(39, 25), (56, 18), (27, 45), (68, 19), (15, 37)], 17, 5, 1, 124, 8,
                   lambda x, cy, w, it: col5(x, cy, w, it, mode="boxes", header=True))

    num = 22
    for k, (name, sub, probs) in enumerate([
        ("No new ten", "No help this time.",
         [(34, 43), (51, 28), (72, 16), (13, 25), (46, 52), (20, 47), (37, 31), (82, 14), (24, 65), (55, 42)]),
        ("New ten", "No help this time.",
         [(38, 47), (16, 58), (49, 33), (27, 64), (18, 25), (55, 36), (36, 29), (19, 19), (44, 38), (67, 25)]),
        ("Add a one-digit number", "Line up the ones!",
         [(47, 4), (63, 5), (29, 6), (84, 7), (52, 4), (75, 9), (36, 3), (58, 5), (91, 6), (26, 7)]),
        ("Mixed", "Some make a new ten. Some don’t.",
         [(25, 48), (61, 37), (34, 9), (57, 26), (42, 45), (19, 67), (73, 18), (50, 29), (66, 27), (8, 45)]),
    ]):
        if k % 2 == 0:
            y = bk.new_page(title, first=False)
        y = bk.part(y, 5 + k, name, sub)
        y = practice_cards(bk, y, probs, num, 5, 2, 120, 8, col5) - 30
        num += len(probs)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Stack the numbers, then add.")
    words(bk, y, [
        ("A class has 26 boys and 37 girls. How many kids are in the class?", "26 + 37 = 63", "63", "kids"),
        ("Sam picked 45 apples. Lily picked 32 apples. How many apples did they pick in all?",
         "45 + 32 = 77", "77", "apples"),
        ("A shop sold 38 hats on Monday and 46 hats on Tuesday. How many hats did it sell?",
         "38 + 46 = 84", "84", "hats"),
        ("Ben has 57 cards. He gets 8 more cards. How many cards does he have now?", "57 + 8 = 65", "65", "cards"),
        ("Challenge: A bus has 24 kids. Then 19 more get on, and then 15 more. How many kids are on it?",
         "24 + 19 + 15 = 58", "58", "kids"),
    ], 62)


# ====================================================================== 14. Subtracting in Columns


def sub_mat(bk, x, top, a, b, wt=130, wo=126, row_h=46, labels=True):
    """
    A place-value mat for a − b. Row 1 is a. If there aren't enough ones, row 2 breaks a ten:
    one fewer stick and 10 orange ones on top of the loose ones. The last row crosses out b
    (the tens with an X, the ones with a slash: loose ones first). Returns the bottom y.
    """
    c = bk.c
    hh = 18
    t, o, tb, ob = a // 10, a % 10, b // 10, b % 10
    needs = o < ob
    rows = [(t, 0, o, False)] + ([(t - 1, 10, o, True)] if needs else [])
    n = len(rows)
    total_h = hh + n * row_h
    bottom = top - total_h
    if T.band is not None:
        c.setFillColor(T.band)
        c.rect(x, top - hh, wt + wo, hh, stroke=0, fill=1)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1)
    c.rect(x, bottom, wt + wo, total_h, stroke=1, fill=0)
    c.line(x + wt, bottom, x + wt, top)
    c.line(x, top - hh, x + wt + wo, top - hh)
    for r in range(1, n):
        c.line(x, top - hh - r * row_h, x + wt + wo, top - hh - r * row_h)
    c.setFillColor(T.ink)
    c.setFont("AvB", 10)
    c.drawCentredString(x + wt / 2, top - 13, "tens")
    c.drawCentredString(x + wt + wo / 2, top - 13, "ones")
    sh, swid, sstep, r_, dstep = row_h - 12, 9, 13, 3.6, 9.5
    for r, (sticks, opened, loose, take) in enumerate(rows):
        take = take or not needs
        ry = top - hh - (r + 1) * row_h
        if labels:
            c.setFillColor(T.text2)
            c.setFont("AvD", 10)
            c.drawRightString(x - 8, ry + row_h / 2 - 3, str(a) if r == 0 else "break a ten")
        for i in range(sticks):
            sx = x + 10 + i * sstep
            ten_stick(bk, sx, ry + 6, sh, swid)
            if take and i >= sticks - tb:
                cross_out(bk, sx, ry + 6, swid, sh)
        ox = x + wt + 12
        two = opened > 0
        orange_y, blue_y = (ry + row_h * 0.7, ry + row_h * 0.3) if two else (None, ry + row_h / 2)
        pos = []
        for i in range(loose):
            pos.append(("a", ox + r_ + i * dstep + (4 if i >= 5 else 0), blue_y))
        for i in range(opened):
            pos.append(("b", ox + r_ + i * dstep + (4 if i >= 5 else 0), orange_y))
        for kind, px, py in pos:
            bk.dot(px, py, r_, kind)
        if take:
            order = [p for p in pos if p[0] == "a"][::-1] + [p for p in pos if p[0] == "b"][::-1]
            for _, px, py in order[:ob]:
                slash(bk, px, py, r_ * 1.2, T.ink)
    return bottom


def learn_subtracting_columns(bk):
    y = bk.new_page("Subtracting in Columns", "Start with the ones. Not enough ones? Break a ten.",
                    name_line=False, big=True, footer="WeMath  ·  Subtracting in Columns")
    c = bk.c

    def notes(x, y0, lines, gap=20):
        for k, line in enumerate(lines):
            c.setFillColor(T.text2)
            c.setFont("AvD", 12)
            c.drawString(x, y0 - k * gap, line)

    label(bk, M, y - 6, f"69 {MINUS} 24: line them up")
    stacked(bk, M + 40, y - 136, 69, 24, op=MINUS, mode="shown", size=26, header=True, room=False)
    notes(M + 190, y - 50, [f"1. Take away the ones: 9 {MINUS} 4 = 5", f"2. Take away the tens: 6 {MINUS} 2 = 4",
                            f"3. 69 {MINUS} 24 = 45"], 24)
    y -= 150

    label(bk, M, y - 6, f"53 {MINUS} 28: 3 {MINUS} 8? Not enough ones, so break a ten")
    bottom = sub_mat(bk, M + 74, y - 22, 53, 28, wt=124, wo=120, row_h=50)
    stacked(bk, M + 360, y - 168, 53, 28, op=MINUS, mode="shown", size=26, header=True)
    notes(M + 74, bottom - 18, ["Cross out 5, write 4.  Cross out 3, write 13.",
                                f"Ones: 13 {MINUS} 8 = 5.  Tens: 4 {MINUS} 2 = 2."], 18)
    y -= 214

    bottom = your_turn(bk, y, h=150)
    bk.ask(f"81 {MINUS} 46 = []")
    stacked(bk, M + 200, bottom + 14, 81, 46, op=MINUS, mode="boxes", size=24, header=True)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: the written form of packet 12. Always start with the ones. If the top ones are too few, "
                     "cross out the tens digit and write one less, then write 10 more ones above the ones. "
                     "Say “53 is 4 tens and 13 ones.”")


def practice_subtracting_columns(bk):
    title = "Subtracting in Columns: Practice"
    y = bk.new_page(title, "Start with the ones.")

    def col5(x, cy, w, item, mode="plain", header=False):
        a, b = item
        bk.ask(f"{a} {MINUS} {b} = []")
        stacked(bk, x + 26, cy + 8, a, b, op=MINUS, mode=mode, size=18, header=header)

    y = bk.part(y, 1, "Stack and subtract", "Take away the ones. Then take away the tens.")
    y = practice_cards(bk, y, [(87, 52), (69, 35), (78, 42), (95, 63), (46, 23),
                               (58, 14), (39, 26), (74, 50), (67, 44), (28, 15)], 1, 5, 2, 124, 8,
                       lambda x, cy, w, it: col5(x, cy, w, it, header=True)) - 30

    def mat_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} {MINUS} {b} = []")
        sub_mat(bk, x + GUT + 70, cy + 136, a, b, wt=124, wo=120, row_h=56)
        stacked(bk, x + GUT + 360, cy + 12, a, b, op=MINUS, mode="boxes", size=22, header=True)
    y = bk.part(y, 2, "Use the mat", "The ten is broken on the mat. Write the new tens and ones on top.")
    practice_cards(bk, y, [(43, 17), (62, 35)], 11, 1, 2, 144, 8, mat_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 3, "Break shown", "The ten is broken for you. Subtract.")
    y = practice_cards(bk, y, [(74, 39), (91, 57), (56, 29), (85, 48), (34, 16)], 13, 5, 1, 124, 8,
                       lambda x, cy, w, it: col5(x, cy, w, it, mode="shown", header=True)) - 30
    y = bk.part(y, 4, "Break it yourself", "Cross out, write the new tens and ones, then subtract.")
    practice_cards(bk, y, [(42, 19), (70, 34), (65, 27), (83, 46), (51, 24)], 18, 5, 1, 124, 8,
                   lambda x, cy, w, it: col5(x, cy, w, it, mode="boxes", header=True))

    num = 23
    for k, (name, sub, probs) in enumerate([
        ("Nothing to break", "No help this time.",
         [(96, 43), (78, 24), (59, 17), (84, 62), (47, 24), (88, 36), (35, 12), (97, 85), (63, 41), (29, 18)]),
        ("Break a ten", "No help this time.",
         [(63, 28), (72, 45), (94, 56), (31, 14), (85, 39), (52, 18), (76, 48), (44, 27), (93, 65), (61, 33)]),
        ("From a tens number", "The ones digit is 0, so break a ten.",
         [(60, 27), (90, 46), (50, 18), (80, 35), (30, 12), (70, 59), (40, 23), (90, 71), (60, 44), (80, 17)]),
        ("Mixed", "Break a ten only when you need to.",
         [(75, 32), (84, 57), (68, 9), (41, 6), (97, 61), (53, 36), (66, 21), (82, 8), (49, 25), (71, 44)]),
    ]):
        if k % 2 == 0:
            y = bk.new_page(title, first=False)
        y = bk.part(y, 5 + k, name, sub)
        y = practice_cards(bk, y, probs, num, 5, 2, 120, 8, col5) - 30
        num += len(probs)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Stack the numbers, then subtract.")
    words(bk, y, [
        ("There were 72 balloons. Then 35 balloons popped. How many balloons are left?",
         f"72 {MINUS} 35 = 37", "37", "balloons"),
        ("A book has 64 pages. Kim has read 30 pages. How many pages are left to read?",
         f"64 {MINUS} 30 = 34", "34", "pages"),
        ("A baker made 85 rolls and sold 47 of them. How many rolls are left?",
         f"85 {MINUS} 47 = 38", "38", "rolls"),
        ("Jay had 50 cents. He spent 26 cents on a snack. How many cents does he have left?",
         f"50 {MINUS} 26 = 24", "24", "cents"),
        ("Challenge: A tree has 93 apples. Then 25 fall off and 18 get picked. How many are left?",
         f"93 {MINUS} 25 {MINUS} 18 = 50", "50", "apples"),
    ], 63)


# ====================================================================== 15. Hundreds, Tens and Ones


def hundred_flat(bk, x, y, s=40, crossed=False, kind="a"):
    """A hundred: a square of 10 × 10 small cells (a base-ten flat). y = bottom.
    kind "b" draws an added hundred in orange (packet 18)."""
    c = bk.c
    if T.band is not None:
        c.setFillColor(T.band if kind == "a" else T.strip)
        c.rect(x, y, s, s, stroke=0, fill=1)
    c.setStrokeColor((T.dot_a if kind == "a" else T.accent) if T.color else T.muted)
    c.setLineWidth(0.4)
    for i in range(1, 10):
        c.line(x + i * s / 10, y, x + i * s / 10, y + s)
        c.line(x, y + i * s / 10, x + s, y + i * s / 10)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.2)
    c.rect(x, y, s, s, stroke=1, fill=0)
    if crossed:
        cross_out(bk, x + 4, y, s - 8, s)


def hto_picture(bk, x, y, h, t, o, s=40, sw_=9, gap=5, extra=None, cross=None):
    """Flats, then ten-sticks (as tall as a flat), then loose ones. y = bottom. Returns the width.
    extra="h" adds an orange hundred, "t" an orange ten; cross="h"/"t" crosses out the last one."""
    cx = x
    for i in range(h):
        hundred_flat(bk, cx, y, s, crossed=(cross == "h" and i == h - 1))
        cx += s + gap
    if extra == "h":
        hundred_flat(bk, cx, y, s, kind="b")
        cx += s + gap
    if h or extra == "h":
        cx += 3
    for i in range(t):
        ten_stick(bk, cx, y, s, sw_)
        if cross == "t" and i == t - 1:
            cross_out(bk, cx, y, sw_, s)
        cx += sw_ + 4
    if extra == "t":
        ten_stick(bk, cx, y, s, sw_, kind="b")
        cx += sw_ + 4
    if t or extra == "t":
        cx += 3
    r = 3.6
    w = ones_dots(bk, cx, y + s, o, r=r, step=r * 2.3, kind="a")
    return cx + w - x


def quick_hto(bk, x, y, h, t, o, size=14, line_h=34, color=None):
    """Quick drawing: a square for each hundred, a line for each ten, a dot for each one. y = bottom."""
    c = bk.c
    col = color or T.ink
    c.setStrokeColor(col)
    c.setFillColor(col)
    cx = x
    for i in range(h):
        c.setLineWidth(1.8)
        c.rect(cx, y + line_h - size, size, size, stroke=1, fill=0)
        cx += size + 6
    if h:
        cx += 4
    for i in range(t):
        c.setLineWidth(2.4)
        c.line(cx, y, cx, y + line_h)
        cx += 9
    if t:
        cx += 6
    for i in range(o):
        cl, row = divmod(i, 5)
        c.circle(cx + cl * 9, y + line_h - 4 - row * 7.5, 2.8, stroke=0, fill=1)
    return cx + (9 * ((o - 1) // 5 + 1) if o else 0) - x


def hto_chart(bk, x, y, h, t, o, w=64, ht=62):
    """A hundreds | tens | ones chart with big coloured digits."""
    c = bk.c
    for i, (lab, val) in enumerate([("hundreds", h), ("tens", t), ("ones", o)]):
        bx = x + i * w
        bk.make_ten_box(bx, y, w, ht, 17, None)
        c.setFillColor(T.ink)
        c.setFont("AvB", 9.5)
        c.drawCentredString(bx + w / 2, y + ht - 12, lab)
        c.setFillColor([T.ink, T.dot_a, T.accent][i])
        c.setFont("Rnd", 28)
        c.drawCentredString(bx + w / 2, y + 10, str(val))


def hto_boxes(bk, x, y, h, t, o, bw=34, step=44, show_total=True):
    """Answer boxes labelled hundreds / tens / ones (then = the number). y = bottom of the boxes."""
    c = bk.c
    for i, (lab, val) in enumerate([("hundreds", h), ("tens", t), ("ones", o)]):
        bx = x + i * step
        c.setFillColor(T.text2)
        c.setFont("AvD", 8)
        c.drawCentredString(bx + bw / 2, y + 32, lab)
        bk.box(bx, y, bw, 28, val, size=16)
    if show_total:
        ex = x + 3 * step
        c.setFillColor(T.text2)
        c.setFont("AvD", 16)
        c.drawString(ex - 2, y + 8, "=")
        bk.box(ex + 14, y, 48, 28, h * 100 + t * 10 + o, size=16)


def learn_hundreds(bk):
    y = bk.new_page("Hundreds, Tens and Ones", "10 tens make 1 hundred.", name_line=False, big=True,
                    footer="WeMath  ·  Hundreds, Tens and Ones")
    c = bk.c
    label(bk, M, y - 6, "10 tens make 1 hundred")
    for i in range(10):
        ten_stick(bk, M + 14 + i * 13, y - 82, 62, 9)
    bk.arrow(M + 156, y - 51, M + 196, y - 51)
    hundred_flat(bk, M + 210, y - 82, 62)
    color_eq(bk, M + 300, y - 58, [("10", "a"), ("tens", None), ("=", "op"), ("1", None), ("hundred", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawCentredString(M + 76, y - 98, "10 tens")
    c.drawCentredString(M + 241, y - 98, "1 hundred = 100")
    y -= 122

    label(bk, M, y - 6, "243 is 2 hundreds, 4 tens and 3 ones")
    hto_picture(bk, M + 14, y - 82, 2, 4, 3, s=56, sw_=11)
    hto_chart(bk, M + 236, y - 84, 2, 4, 3, w=60)
    color_eq(bk, M + 236, y - 112, [("200", None), ("+", "op"), ("40", "a"), ("+", "op"), ("3", "b"),
                                    ("=", "op"), ("243", None)], 20)
    y -= 140

    label(bk, M, y - 6, "Quick drawing: a square for each hundred, a line for each ten, a dot for each one")
    quick_hto(bk, M + 16, y - 62, 1, 3, 2, size=18, line_h=40)
    color_eq(bk, M + 150, y - 46, [("=", "op"), ("1", None), ("3", "a", "tight"), ("2", "b", "tight")], 34)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 14)
    c.drawString(M + 250, y - 44, "1 hundred, 3 tens, 2 ones")
    y -= 84

    bottom = your_turn(bk, y, h=110)
    bk.ask("hundreds, tens and ones in the picture of 325")
    hto_picture(bk, M + 110, bottom + 32, 3, 2, 5, s=46, sw_=10)
    hto_boxes(bk, M + 318, bottom + 30, 3, 2, 5)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: three-digit place value. Build 100 from 10 bundles of 10 sticks. Say “243 is 2 "
                     "hundreds, 4 tens and 3 ones: 200 and 40 and 3.” A zero holds a place: 305 has no tens.")


def practice_hundreds(bk):
    title = "Hundreds, Tens and Ones: Practice"
    y = bk.new_page(title, "Count the hundreds, then the tens, then the ones.")
    y = bk.part(y, 1, "Count them", "A square is 100. A stick is 10. A dot is 1.")

    def count_card(x, cy, w, n):
        h, t, o = n // 100, n // 10 % 10, n % 10
        bk.ask(f"hundreds, tens and ones in the picture of {n}")
        hto_picture(bk, x + GUT, cy + 58, h, t, o, s=38, gap=4)
        hto_boxes(bk, x + GUT, cy + 10, h, t, o)
    y = practice_cards(bk, y, [214, 132, 305, 241, 123, 340], 1, 2, 3, 112, 10, count_card) - 30

    y = bk.part(y, 2, "Draw it", "Quick drawing: a square for each hundred, a line for each ten, a dot for each one.")

    def draw_card(x, cy, w, n):
        h, t, o = n // 100, n // 10 % 10, n % 10
        bk.ask(f"draw {n} as a quick drawing")
        bk.c.setFillColor(T.ink)
        bk.c.setFont("Rnd", 28)
        bk.c.drawString(x + GUT, cy + 70, str(n))
        bx, bw = x + GUT + 66, w - GUT - 74
        bk.work(bx, cy + 44, bw, 66, "Draw it")
        if bk.key:
            quick_hto(bk, bx + 10, cy + 50, h, t, o, size=11, line_h=28, color=T.answer)
        bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"[{h}] hundreds [{t}] tens [{o}] ones", size=15)
    practice_cards(bk, y, [263, 412], 7, 2, 1, 120, 10, draw_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "Draw it", "(continued)")
    y = practice_cards(bk, y, [158, 530], 9, 2, 1, 120, 10, draw_card) - 30
    y = bk.part(y, 3, "Put it together", "Hundreds + tens + ones.")
    y = compact(bk, y, ["300 + 40 + 5 = [345]", "600 + 10 + 9 = [619]", "[200] + 70 + 4 = 274",
                        "800 + 50 + 2 = [852]", "100 + 90 + 6 = [196]", "400 + [30] + 8 = 438",
                        "700 + 20 + 1 = [721]", "500 + 60 + [3] = 563", "900 + 80 + 7 = [987]",
                        "200 + 30 + 9 = [239]", "[600] + 40 + 2 = 642", "300 + [80] + 1 = 381"], 11) - 30
    y = bk.part(y, 4, "Zeros hold a place", "No tens? Write 0 in the tens place.")
    compact(bk, y, ["400 + 7 = [407]", "300 + 60 = [360]", "800 + 2 = [802]",
                    "900 + 30 = [930]", "100 + 5 = [105]", "600 + 90 = [690]",
                    "200 + 4 = [204]", "500 + 10 = [510]", "700 + 8 = [708]"], 23)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 5, "What is it worth?", "Look at the place: hundreds, tens or ones.")

    def worth_card(x, cy, w, item):
        n, d = item
        s_ = str(n)
        pos = s_.index(str(d))
        val = d * 10 ** (2 - pos)
        bk.ask(f"worth: the {d} in {n}")
        c = bk.c
        c.setFillColor(T.text2)
        c.setFont("AvD", 12)
        c.drawString(x + GUT, cy + 16, "In")
        xx = x + GUT + 22
        c.setFont("Rnd", 18)
        for i, ch in enumerate(s_):
            c.setFillColor(T.accent if i == pos else T.ink)
            c.drawString(xx, cy + 15, ch)
            xx += sw(ch, "Rnd", 18) + 1
        c.setFillColor(T.text2)
        c.setFont("AvD", 12)
        c.drawString(xx + 6, cy + 16, f"the {d} is")
        bk.box(xx + 6 + sw(f"the {d} is", "AvD", 12) + 6, cy + 8, 46, 28, val, size=16)
    y = practice_cards(bk, y, [(472, 7), (518, 5), (936, 6), (249, 4), (385, 3), (703, 7),
                               (614, 1), (857, 8), (290, 9), (561, 6)], 31, 2, 5, 44, 8, worth_card) - 30
    y = bk.part(y, 6, "Write the number", "No help this time.")
    compact(bk, y, ["6 hundreds 2 tens 9 ones = [629]", "1 hundred 4 tens 7 ones = [147]",
                    "8 hundreds 3 tens 0 ones = [830]", "3 hundreds 5 tens 6 ones = [356]",
                    "9 hundreds 0 tens 4 ones = [904]", "2 hundreds 8 tens 1 one = [281]",
                    "7 hundreds 6 tens 3 ones = [763]", "4 hundreds 1 ten 5 ones = [415]",
                    "5 hundreds 9 tens 8 ones = [598]", "6 hundreds 0 tens 6 ones = [606]",
                    "1 hundred 7 tens 2 ones = [172]", "8 hundreds 4 tens 9 ones = [849]"], 41, cols=2)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 7, "Break it apart", "No help this time. How many hundreds, tens and ones?")
    def parts(n):  # always plural: "1 ten" next to a blank would give the answer away
        return f"[{n // 100}] hundreds [{n // 10 % 10}] tens [{n % 10}] ones = {n}"
    y = compact(bk, y, [parts(n) for n in (472, 815, 360, 594, 128, 207, 941, 653, 386, 739)], 53, cols=2) - 30
    y = bk.part(y, 8, "Hundreds + tens + ones", "No help this time. Break each number into its parts.")
    compact(bk, y, [f"[{n // 100 * 100}] + [{n // 10 % 10 * 10}] + [{n % 10}] = {n}"
                    for n in (538, 927, 164, 715, 283, 476, 359, 842, 691, 457)], 63, cols=2)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Think in hundreds, tens and ones.")
    words(bk, y, [
        ("A store has 3 boxes of 100 pens, 4 packs of 10 pens, and 6 loose pens. How many pens is that?",
         "300 + 40 + 6 = 346", "346", "pens"),
        ("Lila has 2 sheets of 100 stickers and 5 loose stickers. How many stickers does she have?",
         "200 + 5 = 205", "205", "stickers"),
        ("A farm has 5 crates of 100 eggs and 3 cartons of 10 eggs. How many eggs are there?",
         "500 + 30 = 530", "530", "eggs"),
        ("Max has 427 marbles. A bag holds 100 marbles. How many bags can he fill?",
         "427 = 4 hundreds 2 tens 7 ones", "4", "bags"),
        ("Challenge: Zoe has 2 hundreds, 13 tens and 4 ones. What number is that?",
         "200 + 130 + 4 = 334", "334", ""),
    ], 73)


# ====================================================================== 16. Skip Counting by 5s, 10s and 100s


def five_bar(bk, x, y, cell=12, kind="a"):
    """A bar of five: 5 cells in a row, each with a dot (half of a ten-frame). y = bottom."""
    c = bk.c
    c.setStrokeColor(T.muted)
    c.setLineWidth(0.6)
    for i in range(1, 5):
        c.line(x + i * cell, y, x + i * cell, y + cell)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.1)
    c.roundRect(x, y, cell * 5, cell, 2, stroke=1, fill=0)
    for i in range(5):
        bk.dot(x + i * cell + cell / 2, y + cell / 2, cell * 0.33, kind)


def step_bubble(bk, cx, cy, text, r=11, size=9):
    c = bk.c
    c.setFillColor(white)
    c.setStrokeColor(T.accent)
    c.setLineWidth(1.3)
    c.circle(cx, cy, r, stroke=1, fill=1)
    c.setFillColor(T.accent)
    c.setFont("AvB", size)
    c.drawCentredString(cx, cy - size * 0.36, text)


def count_chain(bk, x, base, seq, blanks=(), step=None, spacing=64, size=18, bw=46, arcs=True):
    """
    Numbers in a row, left to right. blanks are answer boxes. With arcs, a curved arrow joins each
    pair with the step ("+5") in a bubble on it; otherwise small arrows join them.
    """
    c = bk.c
    xs = [x + i * spacing for i in range(len(seq))]
    for i, (cx, n) in enumerate(zip(xs, seq)):
        if i in blanks:
            bk.box(cx - bw / 2, base - size * 0.45, bw, size * 1.55, n, size=size * 0.9)
        else:
            c.setFillColor(T.ink)
            c.setFont("Rnd", size)
            c.drawCentredString(cx, base, str(n))
    half = bw / 2 + 4
    for i in range(len(seq) - 1):
        if arcs:
            lift = size * 1.25
            p0 = (xs[i] + size * 0.3, base + lift)
            p3 = (xs[i + 1] - size * 0.3, base + lift)
            p1, p2 = (p0[0] + 4, base + lift + 18), (p3[0] - 4, base + lift + 18)
            curve_arrow(bk, p0, p1, p2, p3)
            bx, by = bezier_point(p0, p1, p2, p3, 0.5)
            step_bubble(bk, bx, by, step, r=10 if len(step) < 3 else 13, size=9 if len(step) < 4 else 8)
        else:  # a comma right after each number or box, like a list
            right = bw / 2 if i in blanks else sw(str(seq[i]), "Rnd", size) / 2
            c.setFillColor(T.text2)
            c.setFont("Rnd", size)
            c.drawString(xs[i] + right + 1.5, base, ",")


def learn_skip_counting(bk):
    y = bk.new_page("Skip Counting", "Count by 5s, by 10s and by 100s.", name_line=False, big=True,
                    footer="WeMath  ·  Skip Counting")
    c = bk.c
    label(bk, M, y - 6, "Count by 5s")
    for i in range(5):
        bx = M + 10 + i * 82
        five_bar(bk, bx, y - 44, 13, "a" if i % 2 == 0 else "b")
        color_eq(bk, bx + 32, y - 68, [(str((i + 1) * 5), None)], 20, anchor="center")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 420, y - 40, "The ones go")
    c.drawString(M + 420, y - 58, "5, 0, 5, 0 …")
    y -= 96

    label(bk, M, y - 6, "Count by 10s from any number: only the tens change")
    count_chain(bk, M + 26, y - 74, [23, 33, 43, 53, 63, 73], step="+10", spacing=84, size=24)
    y -= 104

    label(bk, M, y - 6, "Count by 100s: only the hundreds change")
    for i in range(4):
        hundred_flat(bk, M + 10 + i * 58, y - 66, 46)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 16)
        c.drawCentredString(M + 33 + i * 58, y - 86, str((i + 1) * 100))
    count_chain(bk, M + 290, y - 62, [140, 240, 340], step="+100", spacing=82, size=22)
    y -= 112

    bottom = your_turn(bk, y, h=96)
    bk.ask("count by 5 from 35: 45, 50, 55")
    count_chain(bk, M + 150, bottom + 28, [35, 40, 45, 50, 55], blanks=(2, 3, 4), step="+5", spacing=74, size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: skip-count by 5s, 10s and 100s from any number. By 5s the ones go 5, 0, 5, 0. "
                     "By 10s only the tens digit changes (until it passes 9). By 100s only the hundreds change. "
                     "Count out loud while pointing at each jump.")


def practice_skip_counting(bk):
    title = "Skip Counting: Practice"
    y = bk.new_page(title, "Jump by the same amount each time.")
    y = bk.part(y, 1, "Count the fives", "Each bar has 5 dots. Count down the bars by 5s.")

    def bars_card(x, cy, w, n):
        bk.ask(f"count {n} bars of five")
        for i in range(n):
            by = cy + 112 - (i + 1) * 13.2
            five_bar(bk, x + GUT, by, 10.5, "a" if i % 2 == 0 else "b")
            v = (i + 1) * 5
            if i == 0:
                bk.c.setFillColor(T.ink)
                bk.c.setFont("Rnd", 11)
                bk.c.drawCentredString(x + GUT + 80, by + 2, "5")
            else:
                bk.box(x + GUT + 66, by - 1, 28, 12.5, v, size=10)
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 11)
        bk.c.drawString(x + GUT + 112, cy + 52, "dots in all:")
        bk.box(x + GUT + 112, cy + 18, 50, 28, n * 5, size=17)
    y = practice_cards(bk, y, [4, 7, 5, 8], 1, 2, 2, 124, 10, bars_card) - 30

    def chain_card(x, cy, w, item, arcs=True):
        start, step, blanks = item
        seq = [start + step * i for i in range(7)]
        bk.ask(f"count by {step} from {start}: {', '.join(str(seq[i]) for i in blanks)}")
        c = bk.c
        if arcs:
            count_chain(bk, x + GUT + 24, cy + 16, seq, blanks, f"+{step}", spacing=68, size=17, bw=44)
        else:
            count_chain(bk, x + GUT + 24, cy + 16, seq, blanks, spacing=68, size=17, bw=44, arcs=False)
    y = bk.part(y, 2, "Count by 10s", "Start at the first number. Jump by 10 each time.")
    practice_cards(bk, y, [(27, 10, (3, 4, 5, 6)), (64, 10, (2, 3, 5, 6)), (8, 10, (3, 4, 5, 6)),
                           (135, 10, (2, 4, 5, 6))], 5, 1, 4, 64, 8, chain_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 3, "Count by 100s", "Only the hundreds change.")
    y = practice_cards(bk, y, [(100, 100, (3, 4, 5, 6)), (250, 100, (2, 3, 5, 6)), (40, 100, (3, 4, 5, 6)),
                               (306, 100, (2, 4, 5, 6))], 9, 1, 4, 64, 8, chain_card) - 30
    y = bk.part(y, 4, "Count by 5s", "The ones go 5, 0, 5, 0 … or 0, 5, 0, 5 …")
    practice_cards(bk, y, [(15, 5, (3, 4, 5, 6)), (70, 5, (2, 3, 5, 6)), (125, 5, (3, 4, 5, 6)),
                           (380, 5, (2, 4, 5, 6))], 13, 1, 4, 64, 8, chain_card)

    def seq_card(x, cy, w, item):
        start, step, blanks = item
        seq = [start + step * i for i in range(5)]
        bk.ask(f"count by {step} from {start}: {', '.join(str(seq[i]) for i in blanks)}")
        count_chain(bk, x + GUT + 10, cy + 16, seq, blanks, spacing=42, size=15, bw=34, arcs=False)

    num = 17
    for k, (name, sub, items) in enumerate([
        ("By 5s", "No help this time.",
         [(5, 5, (2, 4)), (35, 5, (1, 3)), (60, 5, (2, 3)), (90, 5, (2, 4)), (240, 5, (1, 4)),
          (85, 5, (3, 4)), (370, 5, (1, 2)), (515, 5, (2, 4))]),
        ("By 10s", "No help this time.",
         [(30, 10, (2, 4)), (47, 10, (1, 3)), (160, 10, (3, 4)), (93, 10, (1, 2)), (520, 10, (2, 4)),
          (6, 10, (1, 3)), (275, 10, (2, 3)), (680, 10, (2, 4))]),
        ("By 100s", "No help this time.",
         [(200, 100, (2, 4)), (75, 100, (1, 3)), (430, 100, (3, 4)), (500, 100, (1, 2)), (128, 100, (2, 4)),
          (9, 100, (1, 3)), (360, 100, (2, 3)), (315, 100, (1, 4))]),
    ]):
        if k != 1:
            y = bk.new_page(title, first=False)
        y = bk.part(y, 5 + k, name, sub)
        y = practice_cards(bk, y, items, num, 2, 4, 46, 8, seq_card) - 30
        num += len(items)

    y = bk.part(y, 8, "What are we counting by?", "Look at how much each number grows.")

    def by_card(x, cy, w, item):
        seq = item
        step = seq[1] - seq[0]
        bk.ask(f"counting by? {', '.join(map(str, seq))}")
        c = bk.c
        c.setFillColor(T.ink)
        c.setFont("Rnd", 15)
        c.drawString(x + GUT, cy + 16, ",  ".join(map(str, seq)))
        c.setFillColor(T.text2)
        c.setFont("AvD", 12)
        c.drawString(x + GUT + 250, cy + 17, "We are counting by")
        bk.box(x + GUT + 370, cy + 8, 50, 28, step, size=16)
    practice_cards(bk, y, [[45, 50, 55, 60], [310, 320, 330, 340], [205, 305, 405, 505],
                           [380, 390, 400, 410], [80, 85, 90, 95], [100, 200, 300, 400]], 41, 1, 6, 44, 8, by_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Skip-count to find out.")
    words(bk, y, [
        ("Each hand has 5 fingers. How many fingers are on 6 hands?", "5, 10, 15, 20, 25, 30", "30", "fingers"),
        ("A pack has 10 crayons. How many crayons are in 7 packs?",
         "10, 20, 30, 40, 50, 60, 70", "70", "crayons"),
        ("A box holds 100 paper clips. How many paper clips are in 4 boxes?",
         "100, 200, 300, 400", "400", "clips"),
        ("Kim has 35 cents. She gets three 5-cent coins. How many cents does she have now?",
         "35, 40, 45, 50", "50", "cents"),
        ("Challenge: Start at 250 and count by 100s. What is the fifth number you say?",
         "250, 350, 450, 550, 650", "650", ""),
    ], 47)


# ====================================================================== 17. Comparing Numbers


def sign_of(a, b):
    return "<" if a < b else (">" if a > b else "=")


def mini_tens(bk, x, y, n, h=28):
    """A small sticks-and-dots picture of a two-digit number. y = bottom. Returns the width."""
    t, o = divmod(n, 10)
    for i in range(t):
        ten_stick(bk, x + i * 8, y, h, 6)
    ox = x + t * 8 + 3
    for i in range(o):
        col, row = divmod(i, 3)
        bk.dot(ox + 3.2 + col * 7.5, y + h - 3.2 - row * 7.5, 2.9, "a")
    return ox + (7.5 * ((o - 1) // 3) + 6.4 if o else 0) - x


def compare_card(bk, x, cy, w, a, b, draw):
    """a and b drawn side by side, each above its number, with the sign box between them."""
    c = bk.c
    bk.ask(f"compare {a} and {b}")
    left, right = x + GUT + 44, x + w - 50
    for n, cx in ((a, left), (b, right)):
        draw(cx, cy + 46, n)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 20)
        c.drawCentredString(cx, cy + 14, str(n))
    mid = (left + right) / 2
    bk.box(mid - 17, cy + 6, 34, 30, sign_of(a, b), size=20)


def learn_comparing(bk):
    y = bk.new_page("Comparing Numbers", "Which number is bigger? Look at the biggest place first.",
                    name_line=False, big=True, footer="WeMath  ·  Comparing Numbers")
    c = bk.c
    label(bk, M, y - 6, "The wide side of the sign faces the bigger number")
    for i in range(3):
        bk.dot(M + 30 + i * 18, y - 46, 7, "a")
    c.setFillColor(T.accent)
    c.setFont("AvB", 44)
    c.drawCentredString(M + 128, y - 62, "<")
    for i in range(8):
        col, row = divmod(i, 2)
        bk.dot(M + 172 + col * 18, y - 37 - row * 18, 7, "b")
    color_eq(bk, M + 262, y - 50, [("3", None), ("<", "op"), ("8", None)], 26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 350, y - 40, "3 is less than 8.")
    c.drawString(M + 350, y - 60, "8 > 3: 8 is greater than 3.")
    y -= 96

    label(bk, M, y - 6, "46 or 64? Compare the tens first")
    tens_ones_picture(bk, M + 14, y - 82, 4, 6, h=56)
    tens_ones_picture(bk, M + 200, y - 82, 6, 4, h=56)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawCentredString(M + 60, y - 100, "4 tens")
    c.drawCentredString(M + 246, y - 100, "6 tens")
    color_eq(bk, M + 380, y - 58, [("46", None), ("<", "op"), ("64", None)], 30)
    y -= 122

    label(bk, M, y - 6, "352 or 325? Same hundreds, so compare the tens")
    quick_hto(bk, M + 16, y - 70, 3, 5, 2, size=16, line_h=40)
    quick_hto(bk, M + 196, y - 70, 3, 2, 5, size=16, line_h=40)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawCentredString(M + 70, y - 92, "352")
    c.drawCentredString(M + 250, y - 92, "325")
    color_eq(bk, M + 380, y - 58, [("3", None), ("5", "b", "tight"), ("2", None, "tight"), (">", "op"),
                                   ("3", None), ("2", "b", "tight"), ("5", None, "tight")], 30)
    y -= 116

    bottom = your_turn(bk, y, h=96)
    bk.ask("compare 471 and 417")
    bk.eq(M + 170, bottom + 36, "471 [>] 417", size=30)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 380, bottom + 40, "Write <, > or =")
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: compare by place value with <, > and =. Look at the hundreds first; if they match, the "
                     "tens; then the ones. Read 46 < 64 as “46 is less than 64.” The wide (open) side always "
                     "faces the bigger number.")


def practice_comparing(bk):
    title = "Comparing Numbers: Practice"
    y = bk.new_page(title, "Write <, > or =. The wide side faces the bigger number.")
    y = bk.part(y, 1, "Compare the pictures", "Count the tens first.")

    def pic_card(x, cy, w, item):
        def draw(cx, y0, n):
            t, o = divmod(n, 10)
            width = t * 8 + 3 + (7.5 * ((o - 1) // 3) + 6.4 if o else 0)
            mini_tens(bk, cx - width / 2, y0, n)
        compare_card(bk, x, cy, w, *item, draw)
    y = practice_cards(bk, y, [(46, 54), (73, 37), (58, 52), (29, 31), (60, 59), (85, 85)], 1, 2, 3, 96, 10,
                       pic_card) - 30

    y = bk.part(y, 2, "Compare the drawings", "Hundreds first. Same hundreds? Look at the tens.")

    def draw_card(x, cy, w, item):
        def draw(cx, y0, n):
            h, t, o = n // 100, n // 10 % 10, n % 10
            width = h * 14 + (4 if h else 0) + t * 9 + (6 if t else 0) + (9 * ((o - 1) // 5 + 1) if o else 0)
            quick_hto(bk, cx - width / 2, y0, h, t, o, size=8, line_h=26)
        compare_card(bk, x, cy, w, *item, draw)
    practice_cards(bk, y, [(241, 214), (132, 312)], 7, 2, 1, 104, 10, draw_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "Compare the drawings", "(continued)")
    y = practice_cards(bk, y, [(305, 350), (423, 421)], 9, 2, 1, 104, 10, draw_card) - 30
    y = bk.part(y, 3, "Which place decides?", "Circle the place where the numbers are different first.")

    def place_card(x, cy, w, item):
        a, b = item
        sa, sb = str(a), str(b)
        first = next(i for i in range(3) if sa[i] != sb[i])
        bk.ask(f"which place decides {a} or {b}")
        bk.c.setFillColor(T.ink)
        bk.c.setFont("Rnd", 20)
        bk.c.drawString(x + GUT, cy + 30, f"{a}   {b}")
        for j, word in enumerate(["hundreds", "tens", "ones"]):
            px = x + GUT + j * 64
            bk.c.setFillColor(T.text2)
            bk.c.setFont("AvD", 11)
            bk.c.drawCentredString(px + 26, cy + 9, word)
            if bk.key and j == first:
                bk.c.setStrokeColor(T.answer)
                bk.c.setLineWidth(1.5)
                bk.c.ellipse(px - 4, cy + 3, px + 56, cy + 23, stroke=1, fill=0)
    y = practice_cards(bk, y, [(615, 415), (483, 492), (738, 735), (371, 376), (509, 905), (264, 284)],
                       11, 2, 3, 58, 8, place_card) - 30
    y = bk.part(y, 4, "Put them in order", "Smallest first.")

    def order_card(x, cy, w, nums):
        srt = sorted(nums)
        bk.ask(f"order {', '.join(map(str, nums))}")
        bk.c.setFillColor(T.ink)
        bk.c.setFont("Rnd", 17)
        bk.c.drawString(x + GUT, cy + 50, "   ".join(map(str, nums)))
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{srt[0]}] < [{srt[1]}] < [{srt[2]}]", size=17)
    practice_cards(bk, y, [(352, 235, 523), (47, 74, 44), (608, 680, 86), (199, 910, 190)], 17, 2, 2, 78, 10,
                   order_card)

    def cmp(items):
        return [f"{a} [{sign_of(a, b)}] {b}" for a, b in items]
    y = bk.new_page(title, first=False)
    y = bk.part(y, 5, "Two-digit numbers", "No help this time.")
    y = compact(bk, y, cmp([(38, 83), (91, 19), (56, 65), (42, 47), (70, 69), (25, 25),
                            (63, 36), (18, 81), (99, 89), (54, 45), (12, 21), (77, 76)]), 21) - 30
    y = bk.part(y, 6, "Three-digit numbers", "No help this time.")
    compact(bk, y, cmp([(426, 624), (815, 518), (237, 273), (904, 409), (561, 516), (382, 832),
                        (147, 174), (690, 609), (753, 735), (218, 812), (466, 646), (329, 392)]), 33)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 7, "Same hundreds", "No help this time. Look past the hundreds.")
    y = compact(bk, y, cmp([(352, 359), (741, 714), (629, 692), (275, 257), (433, 434),
                            (920, 902), (186, 168), (517, 571), (864, 846)]), 45) - 30
    y = bk.part(y, 8, "Zeros and equals", "No help this time. Some are equal.")
    compact(bk, y, ["409 [<] 490", "300 + 40 [=] 340", "507 [<] 570", "60 [<] 600", "200 + 5 [=] 205",
                    "880 [>] 808", "100 [>] 99", "500 + 6 [<] 560", "90 + 9 [=] 99"], 54)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Compare, then answer.")
    words(bk, y, [
        ("Ana has 46 stickers. Ben has 64 stickers. Who has more stickers?", "46 < 64", "Ben", ""),
        ("Mia read 125 pages. Leo read 152 pages. Who read fewer pages?", "125 < 152", "Mia", ""),
        ("A red box holds 308 beads. A blue box holds 380 beads. Which box holds more?",
         "308 < 380", "blue", "box"),
        ("Kim scored 250 points. Sam scored 200 + 50 points. Compare them with <, > or =.",
         "250 = 200 + 50", "=", ""),
        ("Challenge: Use the digits 4, 7 and 2 once each. What is the biggest number you can make?",
         "7 hundreds 4 tens 2 ones", "742", ""),
    ], 63)


# ====================================================================== 18. 10 and 100 More or Less


def number_cross(bk, cx, cy, n, example=False, dx=80, dy=50, bw=50, bh=28):
    """n in the middle; 100 more above, 100 less below, 10 less to the left, 10 more to the right."""
    c = bk.c
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.4)
    c.roundRect(cx - 30, cy - 17, 60, 34, 6, stroke=1, fill=0)
    c.setFillColor(T.ink)
    c.setFont("Rnd", 21)
    c.drawCentredString(cx, cy - 7.5, str(n))
    reveal = T.accent if example else None
    spots = [(dx, 0, "10 more", n + 10), (-dx, 0, "10 less", n - 10),
             (0, dy, "100 more", n + 100), (0, -dy, "100 less", n - 100)]
    for ox, oy, lab, val in spots:
        bx, by = cx + ox, cy + oy
        bk.box(bx - bw / 2, by - bh / 2, bw, bh, val, size=16, reveal=reveal)
        c.setFillColor(T.text2)
        c.setFont("AvD", 8.5)
        if oy == 0:
            c.drawCentredString(bx, by + bh / 2 + 4, lab)
            sx = cx + (32 if ox > 0 else -32)
            ex = bx - (bw / 2 + 2 if ox > 0 else -(bw / 2 + 2))
            bk.arrow(sx, cy, ex, cy)
        else:
            ly = by + bh / 2 + 4 if oy > 0 else by - bh / 2 - 11
            c.drawString(bx + bw / 2 + 4, by - 3, lab)
            bk.arrow(cx, cy + (19 if oy > 0 else -19), cx, by + (-(bh / 2 + 2) if oy > 0 else bh / 2 + 2))


def learn_more_less_100(bk):
    y = bk.new_page("10 and 100 More or Less", "Add or take away a hundred: only the hundreds change.",
                    name_line=False, big=True, footer="WeMath  ·  10 and 100 More or Less")
    c = bk.c

    def changed(n, place):
        s_ = str(n)
        return [(ch, "b" if i == place else None, "tight") if i else (ch, "b" if i == place else None)
                for i, ch in enumerate(s_)]

    label(bk, M, y - 6, "243 + 100: add a hundred")
    hto_picture(bk, M + 14, y - 74, 2, 4, 3, s=50, sw_=10, extra="h")
    color_eq(bk, M + 290, y - 54, [("243", "a"), ("+", "op"), ("100", "b"), ("=", "op")] + changed(343, 0), 26)
    y -= 92

    label(bk, M, y - 6, f"243 {MINUS} 100: take away a hundred")
    hto_picture(bk, M + 14, y - 74, 2, 4, 3, s=50, sw_=10, cross="h")
    color_eq(bk, M + 290, y - 54, [("243", "a"), (MINUS, "op"), ("100", "b"), ("=", "op")] + changed(143, 0), 26)
    y -= 96

    label(bk, M, y - 6, "The number cross: up and down 100, left and right 10")
    number_cross(bk, M + 120, y - 92, 243, example=True)
    for k, line in enumerate(["Up: 100 more", "Down: 100 less", "Right: 10 more", "Left: 10 less"]):
        c.setFillColor(T.text2)
        c.setFont("AvD", 12.5)
        c.drawString(M + 300, y - 52 - k * 22, line)
    y -= 174

    bottom = your_turn(bk, y, h=96)
    bk.ask("357 + 100 = []")
    bk.ask(f"357 {MINUS} 10 = []")
    bk.eq(M + 140, bottom + 50, "357 + 100 = [457]", size=20)
    bk.eq(M + 140, bottom + 14, f"357 {MINUS} 10 = [347]", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: 10 or 100 more or less without counting (2.NBT.8). 100 more changes only the hundreds "
                     "digit; 10 more only the tens, until the tens pass 9 (395 + 10 = 405). Use real flats and sticks "
                     "and say which digit changes before writing.")


def practice_more_less_100(bk):
    title = "10 and 100 More or Less: Practice"
    y = bk.new_page(title, "Which digit changes?")
    y = bk.part(y, 1, "100 more", "Add the orange hundred.")

    def pic_card(x, cy, w, n, op):
        h, t, o = n // 100, n // 10 % 10, n % 10
        text = f"{n} + 100 = [{n + 100}]" if op == "+" else f"{n} {MINUS} 100 = [{n - 100}]"
        bk.ask(text.split(" = ")[0] + " = []")
        hto_picture(bk, x + GUT, cy + 50, h, t, o, s=34, sw_=8, gap=4,
                    extra="h" if op == "+" else None, cross="h" if op != "+" else None)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, text, size=18)
    y = practice_cards(bk, y, [135, 213, 321, 102], 1, 2, 2, 100, 10,
                       lambda x, cy, w, n: pic_card(x, cy, w, n, "+")) - 30
    y = bk.part(y, 2, "100 less", "Take away the crossed-out hundred.")
    practice_cards(bk, y, [245, 318, 104, 432], 5, 2, 2, 100, 10,
                   lambda x, cy, w, n: pic_card(x, cy, w, n, MINUS))

    y = bk.new_page(title, first=False)
    y = bk.part(y, 3, "Number crosses", "Up 100 more, down 100 less, right 10 more, left 10 less.")

    def cross_card(x, cy, w, n):
        bk.ask(f"number cross {n}")
        number_cross(bk, x + w / 2 + 6, cy + 80, n, dx=76, dy=50, bw=48)
    y = practice_cards(bk, y, [456, 172, 609, 835], 9, 2, 2, 162, 10, cross_card) - 30
    y = bk.part(y, 4, "Keep going", "Jump the same amount each time.")

    def chain_card(x, cy, w, item):
        start, step = item
        seq = [start + step * i for i in range(6)]
        sign = "+" if step > 0 else MINUS
        bk.ask(f"count by {step} from {start}: {', '.join(map(str, seq[3:]))}")
        count_chain(bk, x + GUT + 24, cy + 16, seq, (3, 4, 5), f"{sign}{abs(step)}", spacing=78, size=17, bw=46)
    practice_cards(bk, y, [(118, 100), (962, -100), (453, 10)], 13, 1, 3, 64, 8, chain_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 5, "100 more", "No help this time.")
    y = compact(bk, y, ["264 + 100 = [364]", "507 + 100 = [607]", "831 + 100 = [931]",
                        "149 + 100 = [249]", "690 + 100 = [790]", "312 + 100 = [412]",
                        "75 + 100 = [175]", "426 + 100 = [526]", "853 + 100 = [953]"], 16) - 30
    y = bk.part(y, 6, "100 less", "No help this time.")
    y = compact(bk, y, [f"{a} {MINUS} 100 = [{a - 100}]" for a in (738, 215, 962, 480, 307, 651, 129, 894, 543)],
                25) - 30
    y = bk.part(y, 7, "10 more or 10 less", "No help this time. Watch for the tens passing 9!")
    compact(bk, y, ["347 + 10 = [357]", f"520 {MINUS} 10 = [510]", "693 + 10 = [703]",
                    f"815 {MINUS} 10 = [805]", "238 + 10 = [248]", f"702 {MINUS} 10 = [692]",
                    "461 + 10 = [471]", f"159 {MINUS} 10 = [149]", "395 + 10 = [405]",
                    f"976 {MINUS} 10 = [966]", "584 + 10 = [594]", f"433 {MINUS} 10 = [423]"], 34)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Mixed", "10 or 100? More or less?")
    y = compact(bk, y, ["672 + 100 = [772]", f"381 {MINUS} 10 = [371]", f"546 {MINUS} 100 = [446]",
                        "218 + 10 = [228]", "905 + 10 = [915]", f"760 {MINUS} 100 = [660]",
                        f"143 {MINUS} 10 = [133]", "457 + 100 = [557]", "889 + 10 = [899]",
                        f"612 {MINUS} 100 = [512]", "299 + 100 = [399]", f"830 {MINUS} 10 = [820]"], 46) - 30
    y = bk.part(y, 9, "Word problems", "10 or 100? More or less?")
    words(bk, y, [
        ("A school has 456 kids. Next year, 100 more kids come. How many kids will there be?",
         "456 + 100 = 556", "556", "kids"),
        ("A jar has 380 beads. Zoe uses 100 of them. How many beads are left?",
         f"380 {MINUS} 100 = 280", "280", "beads"),
        ("Max has 245 stamps. He buys a pack of 10 stamps. How many stamps does he have now?",
         "245 + 10 = 255", "255", "stamps"),
    ], 58)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "(continued)")
    words(bk, y, [
        ("A box had 507 nails. Then 10 nails were used. How many nails are left?",
         f"507 {MINUS} 10 = 497", "497", "nails"),
        ("Challenge: Start at 238. Add 100, then take away 10. What number do you get?",
         f"238 + 100 {MINUS} 10 = 328", "328", ""),
    ], 61)


# ====================================================================== 19. Adding Three-Digit Numbers


def hto_add_rows(bk, x, top, a, b, helped=False, size=13, gap=26, maxw=None):
    """hundreds / tens / ones / total rows for a + b (the total adds the three parts)."""
    h, t, o = (a // 100 + b // 100) * 100, (a // 10 % 10 + b // 10 % 10) * 10, a % 10 + b % 10
    fmt = (lambda v: str(v)) if helped else (lambda v: f"[{v}]")
    rows = [("hundreds", f"{fmt(a // 100 * 100)} + {fmt(b // 100 * 100)} = [{h}]"),
            ("tens", f"{fmt(a // 10 % 10 * 10)} + {fmt(b // 10 % 10 * 10)} = [{t}]"),
            ("ones", f"{fmt(a % 10)} + {fmt(b % 10)} = [{o}]"),
            ("total", f"[{h}] + [{t}] + [{o}] = [{a + b}]")]
    for i, (lab, text) in enumerate(rows):
        yy = top - i * gap
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 9.5)
        bk.c.drawString(x, yy + 1, lab)
        if maxw:
            bk.fit_eq(x + 52, yy, maxw - 52, text, size=size)
        else:
            bk.eq(x + 52, yy, text, size=size)


def two_drawings(bk, x, y, a, b, size=9, line_h=24, gap=24):
    """Quick drawings of a (blue) and b (orange) side by side, with a + between. y = bottom."""
    wa = quick_hto(bk, x, y, a // 100, a // 10 % 10, a % 10, size=size, line_h=line_h, color=T.dot_a)
    plus_sign(bk, x + wa + gap / 2, y + line_h / 2 - 5, 14)
    quick_hto(bk, x + wa + gap, y, b // 100, b // 10 % 10, b % 10, size=size, line_h=line_h, color=T.accent)


def learn_adding_three_digit(bk):
    y = bk.new_page("Adding Three-Digit Numbers", "Hundreds + hundreds, tens + tens, ones + ones.",
                    name_line=False, big=True, footer="WeMath  ·  Adding Three-Digit Numbers")
    c = bk.c

    def rows(x, top, lines, size=19, gap=29):
        for i, (lab, parts) in enumerate(lines):
            yy = top - i * gap
            c.setFillColor(T.text2)
            c.setFont("AvD", 11)
            c.drawString(x, yy + 2, lab)
            color_eq(bk, x + 64, yy, parts, size)

    def add_lines(a, b, total_parts):
        return [("hundreds", [(str(a // 100 * 100), "a"), ("+", "op"), (str(b // 100 * 100), "b"), ("=", "op"),
                              (str((a // 100 + b // 100) * 100), None)]),
                ("tens", [(str(a // 10 % 10 * 10), "a"), ("+", "op"), (str(b // 10 % 10 * 10), "b"), ("=", "op"),
                          (str((a // 10 % 10 + b // 10 % 10) * 10), None)]),
                ("ones", [(str(a % 10), "a"), ("+", "op"), (str(b % 10), "b"), ("=", "op"),
                          (str(a % 10 + b % 10), None)]),
                ("total", total_parts)]

    label(bk, M, y - 6, "243 + 125")
    two_drawings(bk, M + 14, y - 66, 243, 125, size=13, line_h=36, gap=30)
    rows(M + 250, y - 30, add_lines(243, 125, [("300", None), ("+", "op"), ("60", None), ("+", "op"), ("8", None),
                                               ("=", "op"), ("368", None)]))
    y -= 138

    label(bk, M, y - 6, "247 + 135: 7 + 5 = 12 ones, so the total gets a new ten")
    two_drawings(bk, M + 14, y - 66, 247, 135, size=13, line_h=36, gap=30)
    rows(M + 250, y - 30, add_lines(247, 135, [("300", None), ("+", "op"), ("70", None), ("+", "op"), ("12", "b"),
                                               ("=", "op"), ("382", None)]))
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 92, "12 ones = 1 ten and 2 ones")
    y -= 140

    bottom = your_turn(bk, y, h=146)
    bk.ask("362 + 254 = []")
    bk.eq(M + 26, bottom + 60, "362 + 254 = [616]", size=22)
    hto_add_rows(bk, M + 236, bottom + 106, 362, 254, size=15, gap=29, maxw=CW - 250)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: add within 1000 by place value (2.NBT.7). Add each place, then add the three parts. "
                     "If the ones or tens make 10 or more, the total row takes care of it: 300 + 70 + 12 = 382. "
                     "Draw squares, lines and dots to check.")


def practice_adding_three_digit(bk):
    title = "Adding Three-Digit Numbers: Practice"
    y = bk.new_page(title, "Add each place. Then put them together.")
    y = bk.part(y, 1, "Add hundreds", "Only the hundreds change.")
    y = compact(bk, y, ["300 + 200 = [500]", "340 + 200 = [540]", "600 + 100 = [700]",
                        "450 + 300 = [750]", "200 + 700 = [900]", "520 + 400 = [920]",
                        "100 + 800 = [900]", "236 + 600 = [836]", "710 + 200 = [910]"], 1) - 30

    def rows_card(x, cy, w, item, helped, drawing):
        a, b = item
        bk.ask(f"{a} + {b} = []")
        top = cy + (196 if drawing else 150)
        if drawing:
            two_drawings(bk, x + GUT, top - 26, a, b)
            top -= 46
        bk.fit_eq(x + GUT, top - 22, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)
        hto_add_rows(bk, x + GUT, top - 56, a, b, helped=helped, size=12, gap=27, maxw=w - GUT - 8)

    y = bk.part(y, 2, "Add each place", "The parts are filled in. Add them.")
    practice_cards(bk, y, [(312, 145), (231, 426)], 10, 2, 1, 206, 10,
                   lambda x, cy, w, it: rows_card(x, cy, w, it, True, True))

    y = bk.new_page(title, first=False)
    y = bk.part(y, 2, "Add each place", "(continued)")
    y = practice_cards(bk, y, [(154, 323), (402, 235)], 12, 2, 1, 206, 10,
                       lambda x, cy, w, it: rows_card(x, cy, w, it, True, True)) - 30
    y = bk.part(y, 3, "New tens and new hundreds", "Fill in every box. The total row adds it all up.")
    practice_cards(bk, y, [(258, 134), (375, 142), (164, 229), (481, 253)], 14, 2, 2, 160, 10,
                   lambda x, cy, w, it: rows_card(x, cy, w, it, False, False))

    def col5(x, cy, w, item, mode="plain", header=False):
        a, b = item
        bk.ask(f"{a} + {b} = []")
        stacked(bk, x + 28, cy + 8, a, b, mode=mode, size=16, header=header)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 4, "Stack it", "Add the ones, then the tens, then the hundreds. Carry new tens and hundreds.")
    y = practice_cards(bk, y, [(236, 152), (347, 128), (452, 273), (518, 164)], 18, 4, 1, 116, 8,
                       lambda x, cy, w, it: col5(x, cy, w, it, "boxes", True)) - 30
    num = 22
    for k, (name, sub, probs) in enumerate([
        ("No new tens or hundreds", "No help this time.",
         [(421, 356), (213, 524), (132, 405), (251, 333), (614, 172), (340, 218), (726, 163), (107, 281)]),
        ("New ten", "No help this time. The ones make 10 or more.",
         [(238, 145), (456, 217), (129, 368), (547, 236), (315, 479), (608, 185), (163, 729), (736, 148)]),
        ("New hundred", "No help this time. The tens make 10 tens or more.",
         [(361, 254), (482, 173), (293, 461), (154, 372), (570, 260), (645, 182), (263, 194), (174, 652)]),
        ("Mixed", "Watch the ones and the tens.",
         [(458, 327), (236, 541), (384, 252), (127, 468), (615, 243), (293, 584), (349, 218), (465, 371)]),
    ]):
        if k in (1, 3):
            y = bk.new_page(title, first=False)
        y = bk.part(y, 5 + k, name, sub)
        y = practice_cards(bk, y, probs, num, 4, 2, 108, 8, col5) - 30
        num += len(probs)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Add each place.")
    words(bk, y, [
        ("A school has 245 boys and 312 girls. How many kids go to the school?", "245 + 312 = 557", "557", "kids"),
        ("A farm has 368 hens and 127 ducks. How many birds are on the farm?", "368 + 127 = 495", "495", "birds"),
        ("Zoe read 182 pages in May and 245 pages in June. How many pages did she read?",
         "182 + 245 = 427", "427", "pages"),
        ("A shop sold 456 apples on Monday and 238 on Tuesday. How many apples did it sell?",
         "456 + 238 = 694", "694", "apples"),
        ("Challenge: A train has 3 cars. They hold 124, 132 and 215 people. How many people in all?",
         "124 + 132 + 215 = 471", "471", "people"),
    ], 54)


# ====================================================================== 20. Subtracting Three-Digit Numbers


def quick_take(bk, x, y, a, b, size=12, line_h=30):
    """Quick drawing of a with b crossed out (the last squares, lines and dots). Nothing to break."""
    c = bk.c
    h, t, o = a // 100, a // 10 % 10, a % 10
    bh, bt, bo = b // 100, b // 10 % 10, b % 10
    quick_hto(bk, x, y, h, t, o, size=size, line_h=line_h)
    c.setStrokeColor(T.accent)
    c.setLineWidth(1.6)
    cx = x
    for i in range(h):
        if i >= h - bh:
            c.line(cx - 2, y + line_h - size - 2, cx + size + 2, y + line_h + 2)
        cx += size + 6
    if h:
        cx += 4
    for i in range(t):
        if i >= t - bt:
            c.line(cx - 4, y + line_h * 0.35, cx + 4, y + line_h * 0.65)
        cx += 9
    if t:
        cx += 6
    for i in range(o):
        if i >= o - bo:
            cl, row = divmod(i, 5)
            px, py = cx + cl * 9, y + line_h - 4 - row * 7.5
            c.line(px - 4, py - 4, px + 4, py + 4)


def hto_sub_rows(bk, x, top, a, b, helped=False, size=13, gap=26, maxw=None):
    """(break) / hundreds / tens / ones / total rows for a − b with at most one break."""
    H, Tn, O = a // 100 * 100, a // 10 % 10 * 10, a % 10
    h, t, o = b // 100 * 100, b // 10 % 10 * 10, b % 10
    rows = []
    if O < o:
        Tn, O = Tn - 10, O + 10
        brk = True
    elif Tn < t:
        H, Tn = H - 100, Tn + 100
        brk = True
    else:
        brk = False
    fmt = (lambda v: str(v)) if helped else (lambda v: f"[{v}]")
    if brk:
        rows.append(("break", f"{a} = {fmt(H)} + {fmt(Tn)} + {fmt(O)}"))
    rows += [("hundreds", f"[{H}] {MINUS} {h} = [{H - h}]"),
             ("tens", f"[{Tn}] {MINUS} {t} = [{Tn - t}]"),
             ("ones", f"[{O}] {MINUS} {o} = [{O - o}]"),
             ("total", f"[{H - h}] + [{Tn - t}] + [{O - o}] = [{a - b}]")]
    if not brk:  # nothing to break: the top numbers are just the places of a
        rows = [(lab, txt.replace(f"[{v}] {MINUS}", f"{v} {MINUS}", 1)) for (lab, txt), v in
                zip(rows[:3], (H, Tn, O))] + rows[3:]
    for i, (lab, text) in enumerate(rows):
        yy = top - i * gap
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 9.5)
        bk.c.drawString(x, yy + 1, lab)
        if maxw:
            bk.fit_eq(x + 52, yy, maxw - 52, text, size=size)
        else:
            bk.eq(x + 52, yy, text, size=size)
    return top - (len(rows) - 1) * gap


def learn_subtracting_three_digit(bk):
    y = bk.new_page("Subtracting Three-Digit Numbers", "Take away each place. Not enough? Break a ten or a hundred.",
                    name_line=False, big=True, footer="WeMath  ·  Subtracting Three-Digit Numbers")
    c = bk.c

    def rows(x, top, lines, size=15, gap=24, labw=58):
        for i, (lab, parts) in enumerate(lines):
            yy = top - i * gap
            c.setFillColor(T.text2)
            c.setFont("AvD", 10)
            c.drawString(x, yy + 2, lab)
            color_eq(bk, x + labw, yy, parts, size)

    def m(a_, b_, r_):
        return [(str(a_), "a"), (MINUS, "op"), (str(b_), None), ("=", "op"), (str(r_), None)]

    label(bk, M, y - 6, f"468 {MINUS} 135: take away each place")
    quick_take(bk, M + 14, y - 64, 468, 135, size=16, line_h=40)
    rows(M + 250, y - 28, [("hundreds", m(400, 100, 300)), ("tens", m(60, 30, 30)), ("ones", m(8, 5, 3)),
                           ("total", [("300", None), ("+", "op"), ("30", None), ("+", "op"), ("3", None),
                                      ("=", "op"), ("333", None)])])
    y -= 126

    label(bk, M, y - 6, f"452 {MINUS} 127: 2 {MINUS} 7? Break a ten")
    label(bk, M + CW / 2 + 6, y - 6, f"528 {MINUS} 263: 2 tens {MINUS} 6 tens? Break a hundred", 12)
    rows(M, y - 30, [("break", [("452", None), ("=", "op"), ("400", None), ("+", "op"), ("40", "a"), ("+", "op"),
                                ("12", "b")]),
                     ("hundreds", m(400, 100, 300)), ("tens", m(40, 20, 20)), ("ones", m(12, 7, 5)),
                     ("total", [("300", None), ("+", "op"), ("20", None), ("+", "op"), ("5", None), ("=", "op"),
                                ("325", None)])], size=14, gap=24, labw=56)
    rows(M + CW / 2 + 6, y - 30, [("break", [("528", None), ("=", "op"), ("400", "a"), ("+", "op"), ("120", "b"),
                                             ("+", "op"), ("8", None)]),
                                  ("hundreds", m(400, 200, 200)), ("tens", m(120, 60, 60)), ("ones", m(8, 3, 5)),
                                  ("total", [("200", None), ("+", "op"), ("60", None), ("+", "op"), ("5", None),
                                             ("=", "op"), ("265", None)])], size=14, gap=24, labw=56)
    y -= 158

    bottom = your_turn(bk, y, h=166)
    bk.ask(f"643 {MINUS} 281 = []")
    bk.eq(M + 26, bottom + 74, f"643 {MINUS} 281 = [362]", size=22)
    hto_sub_rows(bk, M + 236, bottom + 136, 643, 281, size=14, gap=28, maxw=CW - 250)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: subtract within 1000 by place value. Check each place first. Not enough ones: break a "
                     "ten (452 = 400 + 40 + 12). Not enough tens: break a hundred (528 = 400 + 120 + 8).")


def practice_subtracting_three_digit(bk):
    title = "Subtracting Three-Digit Numbers: Practice"
    y = bk.new_page(title, "Take away each place. Break a ten or a hundred when you need to.")
    y = bk.part(y, 1, "Take away hundreds", "Only the hundreds change.")
    y = compact(bk, y, [f"{a} {MINUS} {b} = [{a - b}]" for a, b in
                        [(700, 300), (650, 200), (900, 600), (840, 500), (500, 100), (975, 300),
                         (380, 200), (760, 400), (430, 100)]], 1) - 30
    y = bk.part(y, 2, "What is left?", "The crossed-out parts are taken away. Count what is left.")

    def take_card(x, cy, w, item):
        a, b = item
        bk.ask(f"{a} {MINUS} {b} = []")
        quick_take(bk, x + GUT, cy + 50, a, b, size=11, line_h=28)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{a} {MINUS} {b} = [{a - b}]", size=18)
    practice_cards(bk, y, [(357, 124), (486, 152), (279, 135), (395, 271), (148, 36), (264, 142)], 10, 2, 3, 96,
                   10, take_card)

    def rows_card(x, cy, w, item, helped):
        a, b = item
        bk.ask(f"{a} {MINUS} {b} = []")
        bk.fit_eq(x + GUT, cy + 156, w - GUT - 10, f"{a} {MINUS} {b} = [{a - b}]", size=18)
        hto_sub_rows(bk, x + GUT, cy + 122, a, b, helped=helped, size=12, gap=27, maxw=w - GUT - 8)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 3, "Break a ten", "Not enough ones. The break row is done for you.")
    y = practice_cards(bk, y, [(362, 128), (571, 245), (483, 159), (640, 215)], 16, 2, 2, 186, 10,
                       lambda x, cy, w, it: rows_card(x, cy, w, it, True)) - 30
    y = bk.part(y, 4, "Break a hundred", "Not enough tens. The break row is done for you.")
    practice_cards(bk, y, [(418, 154), (625, 371)], 20, 2, 1, 186, 10,
                   lambda x, cy, w, it: rows_card(x, cy, w, it, True))

    def col4(x, cy, w, item, mode="plain", header=False):
        a, b = item
        bk.ask(f"{a} {MINUS} {b} = []")
        stacked(bk, x + 28, cy + 8, a, b, op=MINUS, mode=mode, size=16, header=header)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 4, "Break a hundred", "(continued)")
    y = practice_cards(bk, y, [(537, 281), (806, 452)], 22, 2, 1, 186, 10,
                       lambda x, cy, w, it: rows_card(x, cy, w, it, True)) - 30
    y = bk.part(y, 5, "Stack it", "Cross out and write the new digits on top, then subtract.")
    y = practice_cards(bk, y, [(453, 128), (724, 361), (385, 142), (916, 573)], 24, 4, 1, 120, 8,
                       lambda x, cy, w, it: col4(x, cy, w, it, "boxes", True)) - 30
    num = 28
    for k, (name, sub, probs) in enumerate([
        ("Nothing to break", "No help this time.",
         [(587, 243), (896, 154), (479, 326), (658, 405), (937, 612), (764, 531), (349, 127), (875, 234)]),
        ("Break a ten", "No help this time.",
         [(473, 138), (652, 319), (381, 156), (794, 368), (560, 234), (842, 517), (931, 405), (275, 149)]),
        ("Break a hundred", "No help this time.",
         [(527, 184), (648, 273), (915, 341), (436, 192), (708, 354), (352, 171), (823, 492), (619, 287)]),
        ("Mixed", "Break only when you need to.",
         [(586, 231), (743, 528), (467, 293), (895, 462), (634, 219), (521, 180), (978, 345), (362, 137)]),
    ]):
        if k in (1, 3):
            y = bk.new_page(title, first=False)
        y = bk.part(y, 6 + k, name, sub)
        y = practice_cards(bk, y, probs, num, 4, 2, 112, 8, col4) - 30
        num += len(probs)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 10, "Word problems", "Take away each place.")
    words(bk, y, [
        ("A library has 485 books. Kids borrow 132 of them. How many books are left?",
         f"485 {MINUS} 132 = 353", "353", "books"),
        ("A farm had 352 eggs. It sold 127 eggs. How many eggs are left?", f"352 {MINUS} 127 = 225", "225", "eggs"),
        ("There are 628 seats in a hall, and 274 seats are full. How many seats are empty?",
         f"628 {MINUS} 274 = 354", "354", "seats"),
        ("Ben had 540 stickers. He gave away 215 stickers. How many stickers does he have now?",
         f"540 {MINUS} 215 = 325", "325", "stickers"),
        ("Challenge: A store had 900 pencils. It sold 350, then 120 more. How many pencils are left?",
         f"900 {MINUS} 350 {MINUS} 120 = 430", "430", "pencils"),
    ], 60)


# ====================================================================== 21. Equal Groups and Arrays

DICE = {1: [(0, 0)], 2: [(-1, 1), (1, -1)], 3: [(-1, 1), (0, 0), (1, -1)],
        4: [(-1, 1), (1, 1), (-1, -1), (1, -1)], 5: [(-1, 1), (1, 1), (0, 0), (-1, -1), (1, -1)]}


def group_ring(bk, cx, cy, n, R=17, r=3.8, kind="a"):
    """A ring holding n dots in a dice pattern (n up to 5)."""
    c = bk.c
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.2)
    c.circle(cx, cy, R, stroke=1, fill=0)
    d = R * 0.45
    for ox, oy in DICE[n]:
        bk.dot(cx + ox * d, cy + oy * d, r, kind)


def groups_picture(bk, x, cy, sizes, R=17, gap=10):
    """Rings in a row (one per group). sizes = dots in each ring. cy = centre line. Returns the width."""
    for i, n in enumerate(sizes):
        group_ring(bk, x + R + i * (2 * R + gap), cy, n, R, kind="a" if i % 2 == 0 else "b")
    return len(sizes) * (2 * R + gap) - gap


def array_picture(bk, x, top, rows, cols, step=15, r=4.6, color_by="row"):
    """rows × cols dots. color_by "row" or "col" alternates blue and orange. Returns (width, height)."""
    for i in range(rows):
        for j in range(cols):
            k = i if color_by == "row" else j
            bk.dot(x + r + j * step, top - r - i * step, r, "a" if k % 2 == 0 else "b")
    return r * 2 + (cols - 1) * step, r * 2 + (rows - 1) * step


def learn_arrays(bk):
    y = bk.new_page("Equal Groups and Arrays", "Same number in every group. Add them up.",
                    name_line=False, big=True, footer="WeMath  ·  Equal Groups and Arrays")
    c = bk.c
    label(bk, M, y - 6, "3 groups of 4")
    groups_picture(bk, M + 14, y - 46, [4, 4, 4], R=22, gap=14)
    color_eq(bk, M + 250, y - 54, [("4", "a"), ("+", "op"), ("4", "b"), ("+", "op"), ("4", "a"), ("=", "op"),
                                   ("12", None)], 28)
    y -= 92

    label(bk, M, y - 6, "An array: 3 rows of 4")
    w, h = array_picture(bk, M + 20, y - 22, 3, 4, step=20, r=6.5, color_by="row")
    for i in range(3):
        c.setFillColor(T.text2)
        c.setFont("Rnd", 13)
        c.drawString(M + 20 + w + 12, y - 22 - 6.5 - i * 20 - 4.5, "4")
    color_eq(bk, M + 250, y - 56, [("4", "a"), ("+", "op"), ("4", "b"), ("+", "op"), ("4", "a"), ("=", "op"),
                                   ("12", None)], 28)
    y -= 100

    label(bk, M, y - 6, "Turn it: the same dots are 4 columns of 3")
    array_picture(bk, M + 20, y - 22, 3, 4, step=20, r=6.5, color_by="col")
    for j in range(4):
        c.setFillColor(T.text2)
        c.setFont("Rnd", 13)
        c.drawCentredString(M + 20 + 6.5 + j * 20, y - 22 - 13 - 2 * 20 - 16, "3")
    color_eq(bk, M + 250, y - 56, [("3", "a"), ("+", "op"), ("3", "b"), ("+", "op"), ("3", "a"), ("+", "op"),
                                   ("3", "b"), ("=", "op"), ("12", None)], 28)
    y -= 112

    bottom = your_turn(bk, y, h=104)
    bk.ask("array 2 rows of 5")
    array_picture(bk, M + 130, bottom + 78, 2, 5, step=20, r=6.5)
    bk.eq(M + 300, bottom + 66, "[2] rows of [5]", size=18)
    bk.eq(M + 300, bottom + 24, "[5] + [5] = [10]", size=18)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: find the total of equal groups and arrays with repeated addition (2.OA.4). Say “3 rows "
                     "of 4: 4, 8, 12.” Turning an array gives the same total. No × sign yet: this gets "
                     "kids ready for multiplication.")


def practice_arrays(bk):
    title = "Equal Groups and Arrays: Practice"
    y = bk.new_page(title, "Count the groups. Count how many in each. Add.")
    y = bk.part(y, 1, "Equal groups", "How many groups? How many in each? How many in all?")

    def groups_card(x, cy, w, item):
        g, n = item
        bk.ask(f"groups: {g} groups of {n}")
        groups_picture(bk, x + GUT, cy + 66, [n] * g, R=16, gap=8)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{g}] groups of [{n}] = [{g * n}]", size=16)
    y = practice_cards(bk, y, [(3, 2), (4, 5), (2, 4), (5, 3), (3, 5), (4, 3)], 1, 2, 3, 96, 10, groups_card) - 30
    y = bk.part(y, 2, "Equal or not?", "Are all the groups the same size? Circle yes or no.")

    def eq_card(x, cy, w, sizes):
        bk.ask(f"equal groups? {'-'.join(map(str, sizes))}")
        groups_picture(bk, x + GUT, cy + 30, sizes, R=14, gap=6)
        yes = len(set(sizes)) == 1
        for j, word in enumerate(["yes", "no"]):  # yes on top, no below (always this order)
            px, py = x + w - 46, cy + 36 - j * 24
            bk.c.setFillColor(T.text2)
            bk.c.setFont("AvD", 13)
            bk.c.drawCentredString(px, py, word)
            if bk.key and (word == "yes") == yes:
                bk.c.setStrokeColor(T.answer)
                bk.c.setLineWidth(1.6)
                bk.c.ellipse(px - 19, py - 7, px + 19, py + 14, stroke=1, fill=0)
    practice_cards(bk, y, [[3, 3, 3], [4, 2, 4], [5, 5], [2, 2, 3, 2], [4, 4, 4, 4], [1, 3, 3]], 7, 2, 3, 60, 8,
                   eq_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 3, "Arrays", "Count the rows. Count how many in each row. Add the rows.")

    def array_card(x, cy, w, item):
        rows, cols = item
        bk.ask(f"array {rows} rows of {cols}")
        array_picture(bk, x + GUT, cy + 104, rows, cols, step=13, r=4.4)
        bk.eq(x + GUT + 84, cy + 76, f"[{rows}] rows of [{cols}]", size=15)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, " + ".join([f"[{cols}]"] * rows) + f" = [{rows * cols}]", size=15)
    y = practice_cards(bk, y, [(2, 3), (4, 5), (3, 2), (5, 4), (3, 5), (4, 4)], 13, 2, 3, 118, 10,
                       array_card) - 30
    y = bk.part(y, 4, "Draw the array", "Draw dots in rows. Then add the rows.")

    def draw_card(x, cy, w, item):
        rows, cols = item
        bk.ask(f"draw {rows} rows of {cols}")
        c = bk.c
        c.setFillColor(T.ink)
        c.setFont("Rnd", 13)
        c.drawString(x + GUT, cy + 92, f"{rows} rows of {cols}")
        bx, bw = x + GUT + 104, w - GUT - 112
        bk.work(bx, cy + 40, bw, 70, "Draw it")
        if bk.key:
            array_picture(bk, bx + 14, cy + 92, rows, cols, step=10.5, r=3.6)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, " + ".join([f"[{cols}]"] * rows) + f" = [{rows * cols}]", size=15)
    practice_cards(bk, y, [(3, 4), (2, 5)], 19, 2, 1, 118, 10, draw_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 4, "Draw the array", "(continued)")
    y = practice_cards(bk, y, [(4, 2), (5, 3)], 21, 2, 1, 118, 10, draw_card) - 30
    y = bk.part(y, 5, "Two ways", "Add the rows. Then add the columns. Same total?")

    def two_card(x, cy, w, item):
        rows, cols = item
        bk.ask(f"two ways {rows} rows of {cols}")
        array_picture(bk, x + GUT, cy + 128, rows, cols, step=13, r=4.4)
        bk.fit_eq(x + GUT, cy + 44, w - GUT - 10, " + ".join([str(cols)] * rows) + f" = [{rows * cols}]", size=15)
        bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, " + ".join([str(rows)] * cols) + f" = [{rows * cols}]", size=15)
    y = practice_cards(bk, y, [(2, 4), (3, 5), (4, 3), (5, 2)], 23, 2, 2, 140, 10, two_card) - 30

    y = bk.new_page(title, first=False)
    y = bk.part(y, 6, "Add equal groups", "No help this time.")
    y = compact(bk, y, ["3 + 3 + 3 + 3 = [12]", "5 + 5 + 5 = [15]", "2 + 2 + 2 + 2 + 2 = [10]",
                        "4 + 4 + 4 = [12]", "5 + 5 + 5 + 5 = [20]", "2 + 2 + 2 + 2 = [8]",
                        "4 + 4 + 4 + 4 + 4 = [20]", "2 + 2 + 2 = [6]", "5 + 5 + 5 + 5 + 5 = [25]",
                        "1 + 1 + 1 + 1 = [4]", "4 + 4 + 4 + 4 = [16]", "3 + 3 + 3 + 3 + 3 = [15]"], 27, cols=2) - 30
    y = bk.part(y, 7, "Rows of", "No help this time. How many in all?")
    compact(bk, y, ["2 rows of 4 = [8]", "5 rows of 3 = [15]", "3 rows of 2 = [6]", "4 rows of 5 = [20]",
                    "1 row of 5 = [5]", "3 rows of 4 = [12]", "5 rows of 5 = [25]", "2 rows of 3 = [6]",
                    "4 rows of 2 = [8]", "3 rows of 3 = [9]", "5 rows of 4 = [20]", "2 rows of 5 = [10]"], 39)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Count the rows", "No help this time. Skip-count one row at a time.")

    def rows_seq(x, cy, w, item):
        n, rows = item
        seq = [n * (i + 1) for i in range(rows)]
        bk.ask(f"rows of {n}, {rows} rows")
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 11)
        bk.c.drawString(x + GUT, cy + 17, f"{rows} rows of {n}:")
        count_chain(bk, x + GUT + 100, cy + 16, seq, tuple(range(1, rows)), spacing=44, size=15, bw=34, arcs=False)
    y = practice_cards(bk, y, [(3, 4), (5, 3), (2, 5), (4, 4), (5, 5), (3, 5)], 51, 1, 6, 44, 8, rows_seq) - 30
    y = bk.part(y, 9, "Word problems", "Draw the groups or the rows.")
    words(bk, y, [
        ("An egg tray has 3 rows of 5 eggs. How many eggs are on the tray?", "5 + 5 + 5 = 15", "15", "eggs"),
        ("There are 4 rows of chairs with 3 chairs in each row. How many chairs are there?",
         "3 + 3 + 3 + 3 = 12", "12", "chairs"),
    ], 57)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "(continued)")
    words(bk, y, [
        ("Mia has 5 bags. Each bag has 4 apples. How many apples does she have?",
         "4 + 4 + 4 + 4 + 4 = 20", "20", "apples"),
        ("A window has 3 rows of 3 panes. How many panes are there?", "3 + 3 + 3 = 9", "9", "panes"),
        ("Challenge: 4 kids each have 5 stickers. Each kid gives 1 away. How many stickers are left?",
         "4 + 4 + 4 + 4 = 16", "16", "stickers"),
    ], 59)


# ====================================================================== 22. Even and Odd


def pairs_picture(bk, x, y, n, step=14, r=4.4, rings=True, highlight=True):
    """n dots in pairs (two rows). With highlight, the dot without a partner is orange and set apart
    (on a practice sheet that would give the answer away, so it's only highlighted on the key).
    y = bottom. Returns the width."""
    c = bk.c
    pairs, extra = divmod(n, 2)
    for i in range(pairs):
        px = x + r + 2 + i * step
        bk.dot(px, y + r + 2 + step * 0.9, r, "a")
        bk.dot(px, y + r + 2, r, "a")
        if rings:
            c.setStrokeColor(T.muted)
            c.setLineWidth(0.9)
            c.roundRect(px - r - 2, y, 2 * r + 4, 2 * r + 4 + step * 0.9, r + 2, stroke=1, fill=0)
    if extra:
        bk.dot(x + r + 2 + pairs * step + (4 if highlight else 0), y + r + 2 + step * 0.9, r,
               "b" if highlight else "a")
    return (pairs + extra) * step + (4 if extra else 0)


def even_odd_choice(bk, x, y, n):
    """even / odd, always in that order; the key circles the right one."""
    for j, word in enumerate(["even", "odd"]):
        px = x + j * 52
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 13)
        bk.c.drawCentredString(px + 20, y, word)
        if bk.key and (word == "even") == (n % 2 == 0):
            bk.c.setStrokeColor(T.answer)
            bk.c.setLineWidth(1.6)
            bk.c.ellipse(px - 2, y - 8, px + 42, y + 17, stroke=1, fill=0)


def learn_even_odd(bk):
    y = bk.new_page("Even and Odd", "Make pairs. Is anyone left over?", name_line=False, big=True,
                    footer="WeMath  ·  Even and Odd")
    c = bk.c
    label(bk, M, y - 6, "Pair them up")
    pairs_picture(bk, M + 14, y - 62, 8, step=24, r=7.5)
    color_eq(bk, M + 140, y - 46, [("8", None), ("is", None), ("even", "a")], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 140, y - 64, "No one is left over.")
    pairs_picture(bk, M + 290, y - 62, 7, step=24, r=7.5)
    color_eq(bk, M + 410, y - 46, [("7", None), ("is", None), ("odd", "b")], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 410, y - 64, "1 is left over.")
    y -= 90

    label(bk, M, y - 6, "Even numbers are doubles. Odd numbers are a double + 1")
    color_eq(bk, M + 14, y - 44, [("4", "a"), ("+", "op"), ("4", "a"), ("=", "op"), ("8", None)], 24)
    color_eq(bk, M + 290, y - 44, [("3", "a"), ("+", "op"), ("3", "a"), ("+", "op"), ("1", "b"), ("=", "op"),
                                   ("7", None)], 24)
    y -= 70

    label(bk, M, y - 6, "Count by 2s: these are the even numbers")
    count_chain(bk, M + 26, y - 74, [2, 4, 6, 8, 10, 12], step="+2", spacing=84, size=24)
    y -= 104

    label(bk, M, y - 6, "Big number? Look only at the ones digit")
    c.setFont("Rnd", 16)
    c.setFillColor(T.dot_a)
    c.drawString(M + 14, y - 40, "ends in 0, 2, 4, 6, 8: even")
    c.setFillColor(T.accent)
    c.drawString(M + 14, y - 64, "ends in 1, 3, 5, 7, 9: odd")
    color_eq(bk, M + 290, y - 40, [("3", None), ("6", "a", "tight"), ("is", None), ("even", "a")], 20)
    color_eq(bk, M + 290, y - 64, [("5", None), ("7", "b", "tight"), ("is", None), ("odd", "b")], 20)
    y -= 92

    bottom = your_turn(bk, y, h=84)
    bk.ask("even or odd picture 11")
    pairs_picture(bk, M + 130, bottom + 28, 11, step=20, r=6.5, rings=bk.key, highlight=bk.key)
    even_odd_choice(bk, M + 300, bottom + 38, 11)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: tell even from odd (2.OA.3). Pair real counters: no one left over means even. Even "
                     "numbers are doubles (4 + 4); odd numbers are a double + 1. For big numbers, only the ones digit "
                     "matters, because tens always pair up.")


def practice_even_odd(bk):
    title = "Even and Odd: Practice"
    y = bk.new_page(title, "Make pairs. Is anyone left over?")
    y = bk.part(y, 1, "Pair them up", "Circle the pairs. Then circle even or odd.")

    def pair_card(x, cy, w, n):
        bk.ask(f"even or odd picture {n}")
        pairs_picture(bk, x + GUT, cy + 40, n, step=14, r=4.6, rings=bk.key, highlight=bk.key)
        even_odd_choice(bk, x + GUT, cy + 12, n)
    y = practice_cards(bk, y, [9, 12, 6, 15, 10, 13], 1, 2, 3, 84, 10, pair_card) - 30
    y = bk.part(y, 2, "Big doubles", "Even numbers split into two equal parts. Split each digit in half.")
    y = compact(bk, y, ["[20] + [20] = 40", "[11] + [11] = 22", "[30] + [30] = 60",
                        "[22] + [22] = 44", "[40] + [40] = 80", "[33] + [33] = 66"], 7) - 30
    y = bk.part(y, 3, "Count by 2s", "Jump by 2 each time.")

    def chain_card(x, cy, w, item):
        start, blanks = item
        seq = [start + 2 * i for i in range(7)]
        bk.ask(f"count by 2 from {start}: {', '.join(str(seq[i]) for i in blanks)}")
        count_chain(bk, x + GUT + 24, cy + 16, seq, blanks, "+2", spacing=66, size=17, bw=42)
    practice_cards(bk, y, [(14, (3, 4, 5, 6)), (1, (2, 3, 5, 6))], 13, 1, 2, 64, 8, chain_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 3, "Count by 2s", "(continued)")
    y = practice_cards(bk, y, [(30, (2, 4, 5, 6)), (47, (3, 4, 5, 6))], 15, 1, 2, 64, 8, chain_card) - 30
    y = bk.part(y, 4, "Look at the ones", "Circle even or odd.")

    def ones_card(x, cy, w, n):
        bk.ask(f"even or odd {n}")
        s_ = str(n)
        bk.c.setFont("Rnd", 22)
        bk.c.setFillColor(T.ink)
        bk.c.drawString(x + GUT, cy + 30, s_)
        even_odd_choice(bk, x + GUT, cy + 10, n)
    y = practice_cards(bk, y, [36, 47, 58, 81, 90, 23, 64, 175, 302], 17, 3, 3, 62, 8, ones_card) - 30
    y = bk.part(y, 5, "Even or odd?", "No help this time. Write even or odd.")

    def word_box(x, cy, w, n):  # same box width for "even" and "odd", so its size isn't a hint
        bk.ask(f"{n} is []")
        bk.c.setFillColor(T.ink)
        bk.c.setFont("Rnd", 17)
        bk.c.drawString(x + GUT, cy + 15, f"{n} is")
        bk.box(x + GUT + sw(f"{n} is", "Rnd", 17) + 7, cy + 7, 56, 28, "even" if n % 2 == 0 else "odd", size=15)
    practice_cards(bk, y, [27, 44, 19, 62, 35, 80, 71, 16, 93, 58, 105, 240], 26, 3, 4, 42, 8, word_box)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 6, "A double + 1", "No help this time. Every odd number is a double and 1 more.")
    y = compact(bk, y, [f"[{n // 2}] + [{n // 2}] + 1 = {n}" for n in (9, 13, 7, 15, 11, 19, 5, 17, 21)], 38) - 30
    y = bk.part(y, 7, "Count by 2s", "No help this time.")

    def seq_card(x, cy, w, item):
        start, blanks = item
        seq = [start + 2 * i for i in range(5)]
        bk.ask(f"count by 2 from {start}: {', '.join(str(seq[i]) for i in blanks)}")
        count_chain(bk, x + GUT + 10, cy + 16, seq, blanks, spacing=42, size=15, bw=34, arcs=False)
    practice_cards(bk, y, [(12, (2, 4)), (31, (1, 3)), (46, (2, 3)), (7, (3, 4)), (88, (1, 4)), (23, (2, 4)),
                           (60, (1, 2)), (95, (3, 4))], 47, 2, 4, 46, 8, seq_card)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Make pairs.")
    words(bk, y, [
        ("There are 14 kids. Can every kid have a partner, with no one left out?", "7 + 7 = 14", "yes", ""),
        ("Max has 9 socks. He puts them in pairs. How many socks are left over?", "4 + 4 + 1 = 9", "1", "sock"),
        ("A shoe store has 8 pairs of shoes on a shelf. How many shoes is that?",
         "2, 4, 6, 8, 10, 12, 14, 16", "16", "shoes"),
        ("A week has 7 days. Is 7 even or odd?", "3 + 3 + 1 = 7", "odd", ""),
        ("Challenge: I am an even number between 30 and 36. My digits add up to 7. What number am I?",
         "3 + 4 = 7", "34", ""),
    ], 55)


# ====================================================================== object pictures (packet 0)
# Small vector drawings of everyday things for story problems. Each is drawn centred at (cx, cy),
# about s points tall. Colour: a fill with a darker outline. Black-and-white: white fill, black outline.

ICON_COLORS = {
    "gummy bear": ("#ef4b4b", "#b3261e"), "apple": ("#e03131", "#a51d1d"), "cookie": ("#d9a066", "#9c6630"),
    "balloon": ("#4c8df6", "#2a62c9"), "fish": ("#ff922b", "#d9480f"), "star": ("#fcc419", "#e08600"),
    "cupcake": ("#f783ac", "#c2255c"), "flower": ("#f06595", "#c2255c"), "ladybug": ("#f03e3e", "#b02525"),
    "egg": ("#fff4dc", "#b8925a"), "bird": ("#4dabf7", "#1c6fb8"), "frog": ("#51cf66", "#2b8a3e"),
    "leaf": ("#fd7e14", "#c25400"), "crayon": ("#9775fa", "#5f3dc4"), "car": ("#4c8df6", "#2a62c9"),
    "duck": ("#ffd43b", "#d9a400"), "candy": ("#cc5de8", "#9c36b5"),
}


def _paint(c, fill, line, width=1.0):
    if T.color:
        c.setFillColor(HexColor(fill))
        c.setStrokeColor(HexColor(line))
    else:
        c.setFillColor(white)
        c.setStrokeColor(T.ink)
    c.setLineWidth(width)


def _dark(c, hexcol="#3b2a1a"):
    c.setFillColor(HexColor(hexcol) if T.color else T.ink)


def _path(c, pts, cx, cy, s, close=True):
    """pts: [("m", x, y), ("c", x1, y1, x2, y2, x3, y3), ("l", x, y)] in units of s."""
    p = c.beginPath()
    for op, *v in pts:
        v = [cx + v[i] * s if i % 2 == 0 else cy + v[i] * s for i in range(len(v))]
        {"m": p.moveTo, "l": p.lineTo, "c": p.curveTo}[op](*v)
    if close:
        p.close()
    return p


def icon(bk, kind, cx, cy, s=22):
    c = bk.c
    fill, line = ICON_COLORS[kind]
    lw = max(0.7, s / 26)
    if kind == "gummy bear":
        _paint(c, fill, line, lw)
        for dx in (-0.15, 0.15):
            c.circle(cx + dx * s, cy - 0.36 * s, 0.1 * s, stroke=1, fill=1)
            c.circle(cx + dx * s * 1.65, cy - 0.04 * s, 0.09 * s, stroke=1, fill=1)
            c.circle(cx + dx * s, cy + 0.4 * s, 0.085 * s, stroke=1, fill=1)
        c.ellipse(cx - 0.24 * s, cy - 0.38 * s, cx + 0.24 * s, cy + 0.12 * s, stroke=1, fill=1)
        c.circle(cx, cy + 0.24 * s, 0.19 * s, stroke=1, fill=1)
        _dark(c, line)
        for dx in (-0.07, 0.07):
            c.circle(cx + dx * s, cy + 0.27 * s, 0.025 * s, stroke=0, fill=1)
        if T.color:
            c.setFillColor(HexColor("#ffffff"))
            c.setFillAlpha(0.45)
            c.ellipse(cx - 0.16 * s, cy - 0.2 * s, cx - 0.06 * s, cy + 0.02 * s, stroke=0, fill=1)
            c.setFillAlpha(1)
    elif kind == "apple":
        _paint(c, fill, line, lw)
        c.drawPath(_path(c, [("m", 0, 0.24), ("c", 0.18, 0.4, 0.44, 0.3, 0.44, 0.02),
                             ("c", 0.44, -0.26, 0.22, -0.44, 0.08, -0.38), ("c", 0.03, -0.36, -0.03, -0.36, -0.08, -0.38),
                             ("c", -0.22, -0.44, -0.44, -0.26, -0.44, 0.02), ("c", -0.44, 0.3, -0.18, 0.4, 0, 0.24)],
                         cx, cy - 0.03 * s, s), stroke=1, fill=1)
        c.setStrokeColor(HexColor("#7a4a1e") if T.color else T.ink)
        c.setLineWidth(lw * 1.6)
        c.line(cx, cy + 0.2 * s, cx + 0.04 * s, cy + 0.42 * s)
        _paint(c, "#51b13b", "#2f7a1f", lw * 0.8)
        c.drawPath(_path(c, [("m", 0.06, 0.34), ("c", 0.12, 0.5, 0.3, 0.52, 0.36, 0.44),
                             ("c", 0.28, 0.32, 0.12, 0.3, 0.06, 0.34)], cx, cy, s), stroke=1, fill=1)
    elif kind == "cookie":
        _paint(c, fill, line, lw)
        c.circle(cx, cy, 0.42 * s, stroke=1, fill=1)
        _dark(c, "#4a2c14")
        for dx, dy in ((-0.18, 0.16), (0.14, 0.2), (0.02, -0.02), (-0.16, -0.18), (0.2, -0.14), (-0.02, 0.32)):
            c.circle(cx + dx * s, cy + dy * s, 0.05 * s, stroke=0, fill=1)
    elif kind == "balloon":
        c.setStrokeColor(HexColor("#868e96") if T.color else T.ink)
        c.setLineWidth(lw * 0.8)
        c.drawPath(_path(c, [("m", 0, -0.24), ("c", 0.08, -0.32, -0.08, -0.42, 0.02, -0.5)], cx, cy, s, close=False),
                   stroke=1, fill=0)
        _paint(c, fill, line, lw)
        c.drawPath(_path(c, [("m", -0.04, -0.29), ("l", 0.04, -0.29), ("l", 0, -0.22)], cx, cy, s), stroke=1, fill=1)
        c.ellipse(cx - 0.3 * s, cy - 0.24 * s, cx + 0.3 * s, cy + 0.48 * s, stroke=1, fill=1)
        if T.color:
            c.setFillColor(HexColor("#ffffff"))
            c.setFillAlpha(0.55)
            c.ellipse(cx - 0.18 * s, cy + 0.16 * s, cx - 0.08 * s, cy + 0.34 * s, stroke=0, fill=1)
            c.setFillAlpha(1)
    elif kind == "fish":
        _paint(c, fill, line, lw)
        c.drawPath(_path(c, [("m", 0.2, 0), ("l", 0.46, 0.2), ("l", 0.46, -0.2)], cx, cy, s), stroke=1, fill=1)
        c.ellipse(cx - 0.44 * s, cy - 0.22 * s, cx + 0.26 * s, cy + 0.22 * s, stroke=1, fill=1)
        c.setFillColor(white)
        c.circle(cx - 0.24 * s, cy + 0.05 * s, 0.06 * s, stroke=0, fill=1)
        _dark(c, "#222222")
        c.circle(cx - 0.24 * s, cy + 0.05 * s, 0.03 * s, stroke=0, fill=1)
        c.setStrokeColor(HexColor(line) if T.color else T.ink)
        c.setLineWidth(lw * 0.8)
        c.drawPath(_path(c, [("m", 0.0, 0.14), ("c", 0.06, 0.04, 0.06, -0.04, 0.0, -0.14)], cx, cy, s, close=False),
                   stroke=1, fill=0)
    elif kind == "star":
        _paint(c, fill, line, lw)
        p = c.beginPath()
        for i in range(10):
            r = 0.47 * s if i % 2 == 0 else 0.2 * s
            a = math.pi / 2 + i * math.pi / 5
            (p.moveTo if i == 0 else p.lineTo)(cx + r * math.cos(a), cy - 0.03 * s + r * math.sin(a))
        p.close()
        c.drawPath(p, stroke=1, fill=1)
    elif kind == "cupcake":
        _paint(c, "#74c0fc", "#1c7ed6", lw)
        c.drawPath(_path(c, [("m", -0.28, -0.45), ("l", 0.28, -0.45), ("l", 0.35, -0.06), ("l", -0.35, -0.06)],
                         cx, cy, s), stroke=1, fill=1)
        c.setStrokeColor(HexColor("#1c7ed6") if T.color else T.ink)
        c.setLineWidth(lw * 0.6)
        for dx in (-0.14, 0, 0.14):
            c.line(cx + dx * s, cy - 0.42 * s, cx + dx * 1.2 * s, cy - 0.09 * s)
        _paint(c, fill, line, lw)
        c.drawPath(_path(c, [("m", -0.4, -0.06), ("c", -0.5, 0.12, -0.32, 0.26, -0.16, 0.2),
                             ("c", -0.12, 0.38, 0.12, 0.4, 0.16, 0.22), ("c", 0.32, 0.27, 0.5, 0.12, 0.4, -0.06)],
                         cx, cy, s), stroke=1, fill=1)
        _paint(c, "#e03131", "#a51d1d", lw * 0.8)
        c.circle(cx + 0.02 * s, cy + 0.37 * s, 0.07 * s, stroke=1, fill=1)
    elif kind == "flower":
        c.setStrokeColor(HexColor("#2f9e44") if T.color else T.ink)
        c.setLineWidth(lw * 1.4)
        c.line(cx, cy - 0.1 * s, cx, cy - 0.5 * s)
        _paint(c, fill, line, lw)
        for i in range(5):
            a = math.pi / 2 + i * 2 * math.pi / 5
            c.circle(cx + 0.19 * s * math.cos(a), cy + 0.1 * s + 0.19 * s * math.sin(a), 0.15 * s, stroke=1, fill=1)
        _paint(c, "#fcc419", "#e08600", lw)
        c.circle(cx, cy + 0.1 * s, 0.11 * s, stroke=1, fill=1)
    elif kind == "ladybug":
        _dark(c, "#212529")
        c.setStrokeColor(HexColor("#212529") if T.color else T.ink)
        c.setLineWidth(lw * 0.8)
        for dx in (-1, 1):
            c.line(cx + dx * 0.06 * s, cy + 0.4 * s, cx + dx * 0.16 * s, cy + 0.5 * s)
        c.circle(cx, cy + 0.3 * s, 0.14 * s, stroke=0, fill=1)
        _paint(c, fill, line, lw)
        c.circle(cx, cy - 0.04 * s, 0.36 * s, stroke=1, fill=1)
        c.setStrokeColor(HexColor("#212529") if T.color else T.ink)
        c.line(cx, cy + 0.32 * s, cx, cy - 0.4 * s)
        _dark(c, "#212529")
        for dx, dy in ((-0.17, 0.08), (0.17, 0.08), (-0.15, -0.17), (0.15, -0.17)):
            c.circle(cx + dx * s, cy + dy * s, 0.065 * s, stroke=0, fill=1)
    elif kind == "egg":
        _paint(c, fill, line, lw)
        c.drawPath(_path(c, [("m", 0, 0.46), ("c", 0.22, 0.46, 0.32, 0.06, 0.32, -0.12),
                             ("c", 0.32, -0.34, 0.18, -0.44, 0, -0.44), ("c", -0.18, -0.44, -0.32, -0.34, -0.32, -0.12),
                             ("c", -0.32, 0.06, -0.22, 0.46, 0, 0.46)], cx, cy, s), stroke=1, fill=1)
    elif kind == "bird":
        _paint(c, "#fab005", "#e67700", lw * 0.8)
        c.drawPath(_path(c, [("m", 0.32, 0.12), ("l", 0.5, 0.06), ("l", 0.32, 0.0)], cx, cy, s), stroke=1, fill=1)
        _paint(c, fill, line, lw)
        c.drawPath(_path(c, [("m", -0.3, 0.0), ("l", -0.5, 0.12), ("l", -0.46, -0.1)], cx, cy, s), stroke=1, fill=1)
        c.circle(cx, cy - 0.02 * s, 0.34 * s, stroke=1, fill=1)
        c.drawPath(_path(c, [("m", -0.16, 0.0), ("c", -0.1, -0.2, 0.12, -0.22, 0.14, -0.04),
                             ("c", 0.02, 0.02, -0.08, 0.04, -0.16, 0.0)], cx, cy, s), stroke=1, fill=1)
        _dark(c, "#212529")
        c.circle(cx + 0.16 * s, cy + 0.12 * s, 0.04 * s, stroke=0, fill=1)
        c.setStrokeColor(HexColor("#e67700") if T.color else T.ink)
        c.setLineWidth(lw)
        for dx in (-0.08, 0.08):
            c.line(cx + dx * s, cy - 0.36 * s, cx + dx * s, cy - 0.48 * s)
    elif kind == "frog":
        _paint(c, fill, line, lw)
        c.ellipse(cx - 0.42 * s, cy - 0.38 * s, cx + 0.42 * s, cy + 0.16 * s, stroke=1, fill=1)
        for dx in (-0.2, 0.2):
            c.circle(cx + dx * s, cy + 0.2 * s, 0.14 * s, stroke=1, fill=1)
        c.setFillColor(white)
        for dx in (-0.2, 0.2):
            c.circle(cx + dx * s, cy + 0.21 * s, 0.085 * s, stroke=0, fill=1)
        _dark(c, "#212529")
        for dx in (-0.2, 0.2):
            c.circle(cx + dx * s, cy + 0.21 * s, 0.04 * s, stroke=0, fill=1)
        c.setStrokeColor(HexColor(line) if T.color else T.ink)
        c.setLineWidth(lw)
        c.drawPath(_path(c, [("m", -0.16, -0.08), ("c", -0.06, -0.18, 0.06, -0.18, 0.16, -0.08)], cx, cy, s,
                         close=False), stroke=1, fill=0)
    elif kind == "leaf":
        _paint(c, fill, line, lw)
        c.drawPath(_path(c, [("m", -0.38, -0.38), ("c", -0.44, 0.1, -0.04, 0.42, 0.42, 0.42),
                             ("c", 0.42, -0.02, 0.08, -0.42, -0.38, -0.38)], cx, cy, s), stroke=1, fill=1)
        c.setLineWidth(lw * 0.8)
        c.line(cx - 0.46 * s, cy - 0.46 * s, cx + 0.3 * s, cy + 0.3 * s)
    elif kind == "crayon":
        _paint(c, fill, line, lw)
        c.rect(cx - 0.13 * s, cy - 0.46 * s, 0.26 * s, 0.62 * s, stroke=1, fill=1)
        c.drawPath(_path(c, [("m", -0.13, 0.16), ("l", 0.13, 0.16), ("l", 0, 0.46)], cx, cy, s), stroke=1, fill=1)
        c.setStrokeColor(HexColor("#ffffff") if T.color else T.ink)
        c.setLineWidth(lw * 1.1)
        for dy in (-0.32, 0.02):
            c.line(cx - 0.1 * s, cy + dy * s, cx + 0.1 * s, cy + dy * s)
    elif kind == "car":
        _paint(c, fill, line, lw)
        c.drawPath(_path(c, [("m", -0.26, 0.04), ("l", -0.16, 0.28), ("l", 0.18, 0.28), ("l", 0.3, 0.04)],
                         cx, cy, s), stroke=1, fill=1)
        c.roundRect(cx - 0.48 * s, cy - 0.2 * s, 0.96 * s, 0.26 * s, 0.07 * s, stroke=1, fill=1)
        c.setFillColor(HexColor("#d0ebff") if T.color else white)
        c.rect(cx - 0.12 * s, cy + 0.08 * s, 0.11 * s, 0.14 * s, stroke=0, fill=1)
        c.rect(cx + 0.03 * s, cy + 0.08 * s, 0.12 * s, 0.14 * s, stroke=0, fill=1)
        _paint(c, "#343a40", "#212529", lw)
        if not T.color:
            c.setFillColor(T.ink)
        for dx in (-0.26, 0.26):
            c.circle(cx + dx * s, cy - 0.22 * s, 0.11 * s, stroke=1, fill=1)
    elif kind == "duck":
        _paint(c, "#fd7e14", "#c25400", lw * 0.8)
        c.drawPath(_path(c, [("m", -0.36, 0.22), ("l", -0.52, 0.16), ("l", -0.36, 0.1)], cx, cy, s), stroke=1, fill=1)
        _paint(c, fill, line, lw)
        c.circle(cx - 0.2 * s, cy + 0.16 * s, 0.17 * s, stroke=1, fill=1)
        c.drawPath(_path(c, [("m", -0.34, -0.02), ("c", -0.38, -0.34, 0.3, -0.42, 0.44, -0.12),
                             ("l", 0.48, 0.08), ("c", 0.3, 0.06, 0.1, 0.02, -0.02, 0.04),
                             ("c", -0.14, 0.04, -0.3, 0.04, -0.34, -0.02)], cx, cy, s), stroke=1, fill=1)
        _dark(c, "#212529")
        c.circle(cx - 0.25 * s, cy + 0.22 * s, 0.035 * s, stroke=0, fill=1)
    elif kind == "candy":
        _paint(c, fill, line, lw)
        for d in (-1, 1):
            c.drawPath(_path(c, [("m", d * 0.18, 0), ("l", d * 0.48, 0.2), ("l", d * 0.48, -0.2)], cx, cy, s),
                       stroke=1, fill=1)
        c.circle(cx, cy, 0.24 * s, stroke=1, fill=1)
        c.setStrokeColor(HexColor("#ffffff") if T.color else T.ink)
        c.setLineWidth(lw)
        c.drawPath(_path(c, [("m", -0.14, -0.12), ("c", -0.04, 0.04, 0.04, -0.04, 0.14, 0.12)], cx, cy, s,
                         close=False), stroke=1, fill=0)


def cross(bk, cx, cy, s, color):
    """An X over an object that goes away."""
    c = bk.c
    c.setStrokeColor(color)
    c.setLineWidth(max(1.6, s / 11))
    d = 0.42 * s
    c.line(cx - d, cy - d, cx + d, cy + d)
    c.line(cx - d, cy + d, cx + d, cy - d)


# ====================================================================== 0. Adding and Taking Away

# Story bank: (singular, plural, start (one, many), add (one, many), take (one, many)).
# {a} = how many to start, {b} = how many come or go, {N} = the noun for {a}.
STORY_BANK = {
    "gummy bear": ("gummy bear", "gummy bears", ("You have 1 gummy bear.", "You have {a} gummy bears."),
                   ("I give you 1 more.", "I give you {b} more."), ("I eat 1 of them.", "I eat {b} of them.")),
    "apple": ("apple", "apples", ("You have 1 apple.", "You have {a} apples."),
              ("You pick 1 more.", "You pick {b} more."), ("You eat 1.", "You eat {b}.")),
    "cookie": ("cookie", "cookies", ("There is 1 cookie on a plate.", "There are {a} cookies on a plate."),
               ("Mom bakes 1 more.", "Mom bakes {b} more."), ("You eat 1.", "You eat {b}.")),
    "balloon": ("balloon", "balloons", ("You have 1 balloon.", "You have {a} balloons."),
                ("You get 1 more.", "You get {b} more."), ("1 pops!", "{b} pop!")),
    "fish": ("fish", "fish", ("1 fish swims in a pond.", "{a} fish swim in a pond."),
             ("1 more swims in.", "{b} more swim in."), ("1 swims away.", "{b} swim away.")),
    "star": ("star", "stars", ("You draw 1 star.", "You draw {a} stars."),
             ("You draw 1 more.", "You draw {b} more."), ("You erase 1.", "You erase {b}.")),
    "cupcake": ("cupcake", "cupcakes", ("There is 1 cupcake.", "There are {a} cupcakes."),
                ("Dad makes 1 more.", "Dad makes {b} more."), ("Your friend eats 1.", "Your friends eat {b}.")),
    "flower": ("flower", "flowers", ("1 flower grows in a garden.", "{a} flowers grow in a garden."),
               ("1 more grows.", "{b} more grow."), ("You pick 1.", "You pick {b}.")),
    "ladybug": ("ladybug", "ladybugs", ("1 ladybug sits on a leaf.", "{a} ladybugs sit on a leaf."),
                ("1 more lands.", "{b} more land."), ("1 flies away.", "{b} fly away.")),
    "egg": ("egg", "eggs", ("A nest has 1 egg.", "A nest has {a} eggs."),
            ("The bird lays 1 more.", "The bird lays {b} more."), ("1 hatches.", "{b} hatch.")),
    "bird": ("bird", "birds", ("1 bird sits in a tree.", "{a} birds sit in a tree."),
             ("1 more flies in.", "{b} more fly in."), ("1 flies away.", "{b} fly away.")),
    "frog": ("frog", "frogs", ("1 frog sits on a log.", "{a} frogs sit on a log."),
             ("1 more hops on.", "{b} more hop on."), ("1 hops off.", "{b} hop off.")),
    "leaf": ("leaf", "leaves", ("1 leaf is on the ground.", "{a} leaves are on the ground."),
             ("1 more falls.", "{b} more fall."), ("The wind blows 1 away.", "The wind blows {b} away.")),
    "crayon": ("crayon", "crayons", ("You have 1 crayon.", "You have {a} crayons."),
               ("You find 1 more.", "You find {b} more."), ("1 breaks.", "{b} break.")),
    "car": ("car", "cars", ("1 car is parked.", "{a} cars are parked."),
            ("1 more parks.", "{b} more park."), ("1 drives away.", "{b} drive away.")),
    "duck": ("duck", "ducks", ("1 duck swims in a pond.", "{a} ducks swim in a pond."),
             ("1 more swims over.", "{b} more swim over."), ("1 waddles away.", "{b} waddle away.")),
    "candy": ("candy", "candies", ("You have 1 candy.", "You have {a} candies."),
              ("Grandma gives you 1 more.", "Grandma gives you {b} more."),
              ("You share 1 with a friend.", "You share {b} with a friend.")),
}


def story_text(kind, a, op, b):
    one, many, start, add, take = STORY_BANK[kind]
    first = (start[0] if a == 1 else start[1]).format(a=a)
    act = add if op == "+" else take
    second = (act[0] if b == 1 else act[1]).format(b=b)
    q = f"How many {many} now?" if op == "+" else "How many are left?"
    return f"{first} {second} {q}"


def objects(bk, kind, x, top, n, s=19, step=22, per_row=5, crossed=0, cross_color=None):
    """n objects in rows of per_row from the top-left. The last `crossed` get an X. Returns (w, h)."""
    for i in range(n):
        r, col = divmod(i, per_row)
        cx, cy = x + s / 2 + col * step, top - s / 2 - r * step
        icon(bk, kind, cx, cy, s)
        if cross_color is not None and i >= n - crossed:
            cross(bk, cx, cy, s, cross_color)
    rows = (n + per_row - 1) // per_row
    return (min(n, per_row) - 1) * step + s, (rows - 1) * step + s


def together(bk, kind, x, top, a, b, s=19, step=22, per_row=4, gap=26, outline=False):
    """Group a, a + sign, then group b. outline draws a light ring around each group. Returns (w, h)."""
    wa, ha = objects(bk, kind, x, top, a, s, step, per_row)
    plus_sign(bk, x + wa + gap / 2, top - s / 2 - 5, 15)
    wb, hb = objects(bk, kind, x + wa + gap, top, b, s, step, per_row)
    if outline:
        c = bk.c
        c.setStrokeColor(T.muted)
        c.setLineWidth(0.8)
        c.setDash(2.5, 2.5)
        for gx, gw, gh in ((x, wa, ha), (x + wa + gap, wb, hb)):
            c.roundRect(gx - 5, top - gh - 5, gw + 10, gh + 10, 7, stroke=1, fill=0)
        c.setDash()
    return wa + gap + wb, max(ha, hb)


def circles(bk, x, top, n, crossed=0, r=5.5, step=15, per_row=5, color=None):
    """Circles a child might draw (answer key)."""
    c = bk.c
    col = color or T.answer
    for i in range(n):
        rr, cl = divmod(i, per_row)
        cx, cy = x + r + cl * step, top - r - rr * step
        c.setStrokeColor(col)
        c.setLineWidth(1.4)
        c.circle(cx, cy, r, stroke=1, fill=0)
        if i >= n - crossed:
            c.line(cx - r * 1.2, cy - r * 1.2, cx + r * 1.2, cy + r * 1.2)
            c.line(cx - r * 1.2, cy + r * 1.2, cx + r * 1.2, cy - r * 1.2)
    return (min(n, per_row) - 1) * step + 2 * r


def flow(bk, title, y, n, name, sub, items, num, cols, h, gap, draw):
    """A part whose cards run onto new pages as needed. Returns (y after the part, next number)."""
    if y - 14 - h < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, n, name, sub)
    for i in range(0, len(items), cols):
        if y - h < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, n, name, "(continued)")
        practice_cards(bk, y, items[i:i + cols], num + i, cols, 1, h, gap, draw)
        y -= h + gap
    return y - 30 + gap, num + len(items)


def learn_adding_taking_away(bk):
    y = bk.new_page("Adding and Taking Away", "Put together to add. Take away to subtract.", name_line=False,
                    big=True, footer="WeMath  ·  Adding and Taking Away")
    c = bk.c
    label(bk, M, y - 6, "Put together: 3 gummy bears and 2 more")
    w, _ = together(bk, "gummy bear", M + 14, y - 22, 3, 2, s=36, step=40, gap=40)
    c.setFillColor(T.text2)
    c.setFont("AvD", 26)
    c.drawCentredString(M + 14 + w + 24, y - 50, "=")
    objects(bk, "gummy bear", M + 14 + w + 48, y - 22, 5, s=36, step=40)
    color_eq(bk, M + 14, y - 100, [("3", "a"), ("+", "op"), ("2", "b"), ("=", "op"), ("5", None)], 34)
    color_eq(bk, M + 200, y - 94, [("+", "op"), ("means put together. Count them all.", None)], 14)
    y -= 130

    label(bk, M, y - 6, "Take away: 4 cookies, and you eat 1")
    objects(bk, "cookie", M + 14, y - 22, 4, s=36, step=42, crossed=1, cross_color=T.accent)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 210, y - 36, "Cross out the one you eat.")
    c.drawString(M + 210, y - 54, "Count what is left: 1, 2, 3.")
    color_eq(bk, M + 14, y - 100, [("4", "a"), (MINUS, "op"), ("1", "b"), ("=", "op"), ("3", None)], 34)
    color_eq(bk, M + 200, y - 94, [(MINUS, "op"), ("means take away.", None)], 14)
    y -= 132

    bottom = your_turn(bk, y, h=150)
    bk.ask("pic: apple 5 - 2")
    bk.paragraph(M + 120, y - 14, 360, "You have 5 apples. You eat 2. How many are left?", size=14, leading=18,
                 font="AvM")
    objects(bk, "apple", M + 120, y - 50, 5, s=32, step=38, crossed=2, cross_color=T.answer if bk.key else None)
    bk.eq(M + 120, bottom + 18, f"5 {MINUS} 2 = [3]", size=24)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: add and take away with things kids can see. Read each story out loud. Act it out with real "
                     "snacks or counters first, then use the pictures: count them all to add; cross out what goes "
                     "away and count what is left to take away. Start within 5 before going to 9.")


def practice_adding_taking_away(bk):
    title = "Adding and Taking Away: Practice"
    y = bk.new_page(title, "Count the pictures. Cross out what goes away.")
    S5, ST5 = 28, 33   # pictures up to 5: big
    S9, ST9 = 23, 27   # pictures up to 9: rows of 5, like a ten-frame
    keyx = T.answer if bk.key else None

    def sign_of_op(op):
        return "+" if op == "+" else MINUS

    def result(a, op, b):
        return a + b if op == "+" else a - b

    def picture(kind, x, top, a, op, b, small, crossed_color=None):
        s, st = (S9, ST9) if small else (S5, ST5)
        if op == "+":
            return together(bk, kind, x, top, a, b, s=s, step=st, per_row=5, gap=34, outline=small)
        return objects(bk, kind, x, top, a, s=s, step=st, crossed=b, cross_color=crossed_color)

    # ---- half-width cards (up to 5)
    def together_card(x, cy, w, item):
        kind, a, b = item
        bk.ask(f"pic: {kind} {a} + {b}")
        picture(kind, x + GUT, cy + 82, a, "+", b, False)
        bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)

    def take_card(x, cy, w, item):
        kind, n, b = item
        bk.ask(f"pic: {kind} {n} - {b}")
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 11)
        bk.c.drawString(x + GUT, cy + 84, f"Cross out {b}.")
        picture(kind, x + GUT, cy + 74, n, "-", b, False, keyx)
        bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"{n} {MINUS} {b} = [{n - b}]", size=18)

    def story_card(x, cy, w, item):
        kind, a, op, b = item
        bk.ask(f"story pic: {kind} {a} {op} {b}")
        bk.paragraph(x + GUT, cy + 126, w - GUT - 12, story_text(kind, a, op, b), size=11, leading=15, font="AvM")
        picture(kind, x + GUT, cy + 82, a, op, b, False, keyx)
        bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"{a} {sign_of_op(op)} {b} = [{result(a, op, b)}]", size=18)

    # ---- full-width cards (up to 9): picture on the left, equation right-aligned so it never meets the picture
    def right_eq(x, cy, w, text, size=20):
        bk.eq(x + w - 16 - bk.eq_width(text, size), cy + 30, text, size=size)

    def wide_together(x, cy, w, item):
        kind, a, b = item
        bk.ask(f"pic: {kind} {a} + {b}")
        picture(kind, x + GUT, cy + 68, a, "+", b, True)
        right_eq(x, cy, w, f"{a} + {b} = [{a + b}]")

    def wide_take(x, cy, w, item):
        kind, n, b = item
        bk.ask(f"pic: {kind} {n} - {b}")
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 11)
        bk.c.drawString(x + GUT + 175, cy + 54, f"Cross out {b}.")
        picture(kind, x + GUT, cy + 68, n, "-", b, True, keyx)
        right_eq(x, cy, w, f"{n} {MINUS} {b} = [{n - b}]")

    def wide_draw_more(x, cy, w, item):
        kind, a, b = item
        one, many = STORY_BANK[kind][:2]
        bk.ask(f"draw more: {kind} {a} + {b}")
        bk.c.setFillColor(T.ink)
        bk.c.setFont("AvM", 12)
        bk.c.drawString(x + GUT, cy + 76, f"You have {a} {one if a == 1 else many}. Draw {b} more.")
        objects(bk, kind, x + GUT, cy + 62, a, s=S9, step=ST9)
        bx = x + GUT + 5 * ST9 + 12
        bk.work(bx, cy + 10, 130, 58, "Draw " + str(b) + " more")
        if bk.key:
            circles(bk, bx + 12, cy + 50, b, r=6, step=17)
        right_eq(x, cy, w, f"{a} + {b} = [{a + b}]")

    def wide_story(x, cy, w, item):
        kind, a, op, b = item
        bk.ask(f"story pic: {kind} {a} {op} {b}")
        bk.paragraph(x + GUT, cy + 112, w - GUT - 16, story_text(kind, a, op, b), size=11.5, leading=15,
                     font="AvM")
        picture(kind, x + GUT, cy + 68, a, op, b, True, keyx)
        # number boxes, and a circle for the sign (so it can't be read as a three-digit number)
        r = 14
        rest = f"[{b}] = [{result(a, op, b)}]"
        start = x + w - 16 - (bk.eq_width(f"[{a}]", 19) + 12 + 2 * r + bk.eq_width(rest, 19))
        ex = bk.eq(start, cy + 30, f"[{a}]", size=19)
        c = bk.c
        c.setFillColor(white)
        c.setStrokeColor(T.box)
        c.setLineWidth(1)
        c.circle(ex + 6 + r, cy + 30 + 6, r, stroke=1, fill=1)
        bk.value(ex + 6 + r, cy + 36, sign_of_op(op), 18)
        bk.eq(ex + 12 + 2 * r, cy + 30, rest, size=19)

    def wide_sentence(x, cy, w, item):
        kind, a, op, b = item
        bk.ask(f"sentence pic: {kind} {a} {op} {b}")
        picture(kind, x + GUT, cy + 68, a, op, b, True, T.accent)
        right_eq(x, cy, w, f"[{a}] {sign_of_op(op)} [{b}] = [{result(a, op, b)}]")

    def draw_solve_card(x, cy, w, item):
        a, op, b = item
        bk.ask(f"draw to solve: {a} {op} {b}")
        bx = x + GUT
        bk.work(bx, cy + 42, w - GUT - 12, 62, "Draw circles")
        if bk.key:
            if op == "+":
                wa = circles(bk, bx + 10, cy + 84, a, r=5.5, step=14)
                circles(bk, bx + 26 + wa, cy + 84, b, r=5.5, step=14, color=T.accent if T.color else T.answer)
            else:
                circles(bk, bx + 10, cy + 84, a, crossed=b, r=5.5, step=14)
        bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"{a} {sign_of_op(op)} {b} = [{result(a, op, b)}]", size=18)

    def plain(x, cy, w, text):
        bk.ask(text)
        bk.fit_eq(x + GUT, cy + 14, w - GUT - 8, text, size=18)

    def P(items):
        return [f"{a} {sign_of_op(op)} {b} = [{result(a, op, b)}]" for a, op, b in items]

    num = 1
    y, num = flow(bk, title, y, 1, "Put together", "Count them all. How many in all?",
                  [("gummy bear", 2, 1), ("apple", 1, 3), ("star", 2, 2), ("duck", 3, 1),
                   ("fish", 1, 1), ("cookie", 2, 3), ("flower", 4, 1), ("ladybug", 1, 2)], num, 2, 92, 10,
                  together_card)
    y, num = flow(bk, title, y, 2, "Take away", "Cross out the ones that go away. How many are left?",
                  [("cupcake", 3, 1), ("balloon", 5, 2), ("egg", 4, 1), ("candy", 2, 1),
                   ("frog", 5, 3), ("leaf", 4, 2), ("bird", 3, 2), ("car", 5, 1)], num, 2, 100, 10, take_card)
    y, num = flow(bk, title, y, 3, "Story problems", "Listen to the story. Use the picture.",
                  [("gummy bear", 3, "-", 1), ("balloon", 2, "+", 2), ("cookie", 5, "-", 2), ("fish", 3, "+", 2),
                   ("apple", 4, "-", 3), ("bird", 1, "+", 3), ("ladybug", 5, "-", 4), ("candy", 4, "+", 1)],
                  num, 2, 140, 10, story_card)
    y, num = flow(bk, title, y, 4, "Put together up to 9", "Count them all.",
                  [("gummy bear", 5, 3), ("cookie", 4, 2), ("star", 6, 1), ("fish", 3, 4),
                   ("cupcake", 2, 7), ("balloon", 5, 4), ("egg", 6, 2), ("crayon", 1, 5)], num, 1, 80, 8,
                  wide_together)
    y, num = flow(bk, title, y, 5, "Take away from up to 9", "Cross out. Count what is left.",
                  [("apple", 7, 2), ("duck", 8, 3), ("flower", 6, 4), ("ladybug", 9, 5),
                   ("leaf", 8, 6), ("car", 7, 4), ("frog", 9, 2), ("candy", 6, 1)], num, 1, 80, 8, wide_take)
    y, num = flow(bk, title, y, 6, "Draw more", "Draw circles for the ones you add. Count them all.",
                  [("star", 4, 3), ("egg", 2, 5), ("bird", 6, 2), ("flower", 3, 3), ("gummy bear", 5, 4),
                   ("cupcake", 1, 6)], num, 1, 90, 8, wide_draw_more)
    y, num = flow(bk, title, y, 7, "Story problems up to 9",
                  "Put together or take away? Write the numbers, and + or − in the circle.",
                  [("gummy bear", 8, "-", 3), ("balloon", 7, "-", 2), ("fish", 5, "+", 3), ("egg", 6, "-", 4),
                   ("frog", 4, "+", 4), ("leaf", 9, "-", 4), ("car", 6, "+", 3), ("duck", 7, "-", 5),
                   ("apple", 3, "+", 5), ("candy", 9, "-", 6)], num, 1, 124, 8, wide_story)
    y, num = flow(bk, title, y, 8, "Write the number sentence", "Look at the picture. Write the numbers.",
                  [("crayon", 3, "+", 4), ("ladybug", 6, "-", 2), ("cookie", 5, "+", 2), ("flower", 8, "-", 5),
                   ("star", 9, "-", 3), ("bird", 4, "+", 5), ("egg", 7, "-", 1), ("fish", 2, "+", 6)],
                  num, 1, 80, 8, wide_sentence)
    y, num = flow(bk, title, y, 9, "Draw to solve", "Draw circles. Cross out to take away.",
                  [(3, "+", 5), (7, "-", 3), (4, "+", 4), (9, "-", 4), (6, "+", 3), (8, "-", 2)], num, 2, 114, 10,
                  draw_solve_card)

    for n_, name, sub, items in [
        (10, "Adding to 5", "No help this time. Use your fingers or draw if you need to.",
         [(1, "+", 3), (4, "+", 1), (0, "+", 2), (3, "+", 1), (5, "+", 0), (1, "+", 4), (0, "+", 3), (2, "+", 0),
          (4, "+", 0)]),
        (11, "Taking away from 5", "No help this time.",
         [(5, "-", 1), (4, "-", 2), (3, "-", 1), (5, "-", 3), (2, "-", 1), (4, "-", 1), (5, "-", 2), (3, "-", 2),
          (4, "-", 3), (5, "-", 4), (3, "-", 3), (2, "-", 0)]),
        (12, "Adding to 9", "No help this time.",
         [(5, "+", 1), (2, "+", 4), (6, "+", 2), (1, "+", 6), (3, "+", 5), (7, "+", 2), (4, "+", 2), (2, "+", 6),
          (8, "+", 1), (1, "+", 5), (5, "+", 3), (2, "+", 7), (6, "+", 1), (3, "+", 6), (1, "+", 7)]),
        (13, "Taking away from 9", "No help this time.",
         [(7, "-", 2), (9, "-", 4), (6, "-", 1), (8, "-", 3), (9, "-", 6), (7, "-", 5), (8, "-", 6), (6, "-", 4),
          (9, "-", 1), (7, "-", 3), (8, "-", 5), (6, "-", 2), (9, "-", 7), (8, "-", 2), (7, "-", 6)]),
        (14, "Mixed", "No help this time. Watch the sign: + or −.",
         [(1, "+", 8), (9, "-", 5), (7, "+", 1), (6, "-", 3), (2, "+", 5), (8, "-", 4), (5, "+", 2), (9, "-", 3),
          (6, "+", 3), (7, "-", 4), (8, "-", 1), (6, "-", 5), (9, "-", 2), (7, "-", 1), (6, "-", 6)]),
    ]:
        y, num = flow(bk, title, y, n_, name, sub, P(items), num, 3, 42, 8, plain)

    y = bk.new_page(title, first=False)
    y = bk.part(y, 15, "Word problems", "Draw a picture to help.")
    words(bk, y, [
        ("Sam has 6 crayons. He finds 2 more. How many crayons does he have now?", "6 + 2 = 8", "8", "crayons"),
        ("There are 9 bubbles. 5 bubbles pop. How many bubbles are left?", f"9 {MINUS} 5 = 4", "4", "bubbles"),
        ("Mia has 5 stickers. Her mom gives her 4 more. How many stickers does she have?",
         "5 + 4 = 9", "9", "stickers"),
        ("8 kids are on the slide. 6 kids go home. How many kids are still on the slide?",
         f"8 {MINUS} 6 = 2", "2", "kids"),
        ("Challenge: You have 4 cookies. Mom gives you 3 more. Then you eat 2. How many cookies now?",
         f"4 + 3 {MINUS} 2 = 5", "5", "cookies"),
    ], num)


# ====================================================================== card drawers (shared)

def c_frame_buddy(bk, x, cy, w, n):
    bk.ten_frame(x + GUT, cy + 20, 22, dots(n) + (dots(10 - n, "b") if bk.key else []))
    for j, (lab, val) in enumerate([("Dots", n), ("Buddy", 10 - n)]):
        bx = x + 170 + j * 41
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvM", 8)
        bk.c.drawCentredString(bx + 18, cy + 58, lab)
        bk.box(bx, cy + 18, 36, 34, val, size=17)


def c_buddy_yesno(bk, x, cy, w, item):
    text, yes = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 18)
    bk.c.drawString(x + GUT, cy + 15, text)
    for j, word in enumerate(["yes", "no"]):
        px = x + w - 104 + j * 50
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 13)
        bk.c.drawCentredString(px + 20, cy + 16, word)
        if bk.key and (word == "yes") == yes:
            bk.c.setStrokeColor(T.answer)
            bk.c.setLineWidth(1.6)
            bk.c.ellipse(px + 2, cy + 8, px + 38, cy + 34, stroke=1, fill=0)


def c_more10(bk, x, cy, w, item):
    text, have, need = item
    ew = bk.eq_width(text, 17)
    bk.eq(x + GUT + (w - GUT - ew) / 2, cy + 64, text, size=17)
    bk.ten_frame(x + GUT + (w - GUT - 100) / 2, cy + 13, 20,
                 dots(have) + (dots(need, "b") if bk.key else []))


def c_teen(bk, x, cy, w, item):
    text, extra = item
    bk.frames(x + GUT + 4, cy + 54, 19, dots(10) + dots(extra, "b"))
    bk.eq(x + GUT + 4, cy + 20, text, size=18)


def c_three(bk, x, cy, w, nums):
    pair = next((i, j) for i in range(3) for j in range(i + 1, 3) if nums[i] + nums[j] == 10)
    bk.buddies_first(x + w / 2 + 6, cy + 110 - 6, nums, pair)


def c_ladder(bk, x, cy, w, item):
    a, b = item
    ten = (a // 10 + 1) * 10
    bk.eq(x + GUT, cy + 52, f"{a} + [{ten - a}] = {ten}", size=18)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvM", 10)
    bk.c.drawString(x + GUT, cy + 17, "so")
    bk.eq(x + GUT + 22, cy + 16, f"{a} + {b} = [{a + b}]", size=18)


def c_hint(bk, x, cy, w, item):
    a, b = item
    ten = (a // 10 + 1) * 10
    bk.eq(x + GUT, cy + 48, f"{a} + {b} = [{a + b}]", size=20)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvM", 9.5)
    bk.c.drawString(x + GUT, cy + 15, "next ten")
    bk.box(x + GUT + 48, cy + 8, 34, 24, ten, size=13)


def c_jump_dots(bk, x, cy, w, item):
    a, b = item
    x0 = x + GUT - 4
    jump_diagram(bk, x0, cy + 146 - 8, a, b, guided=True)
    jump_dots(bk, x0, cy + 18, a, b)


def c_jump(bk, x, cy, w, item):
    a, b = item
    jump_diagram(bk, x + GUT - 4, cy + 104 - 8, a, b, guided=True)


def c_jump_col(bk, x, cy, w, item):
    a, b = item
    if JUMP_STYLE == "inline":
        jump_column_inline(bk, x, cy + 172 - 4, w, a, b)
    else:
        jump_vertical(bk, x, cy + 164 - 4, w, a, b)


def c_jump_less(bk, x, cy, w, item):
    a, b = item
    bk.eq(x + GUT, cy + 50, f"{a} − {b} = [{a - b}]", size=20)
    jump_circle(bk, x + GUT + 16, cy + 22, a - 10, r=13, size=13)
    plus_sign(bk, x + GUT + 42, cy + 17, 13)
    jump_circle(bk, x + GUT + 68, cy + 22, 10 - b, r=13, size=13)
    bk.captions(cy + 22 - 3, [(x + GUT + 110, "jumps")])


def c_jump_big(bk, x, cy, w, item):
    a, b = item
    jump_diagram(bk, x + GUT - 4, cy + 104 - 8, a, b)


def c_double_dots(bk, x, cy, w, n):
    dot_pair(bk, x + GUT, cy + 96 - 22, n, n, r=5, step=14)
    bk.eq(x + GUT, cy + 16, f"double {n} = [{2 * n}]", size=20)


def c_near_dots(bk, x, cy, w, item):
    n, m = item
    dot_pair(bk, x + GUT, cy + 124 - 22, n, m, r=5, step=14)
    bk.eq(x + GUT, cy + 52, f"double {n} = [{2 * n}]", size=18)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvM", 10)
    bk.c.drawString(x + GUT, cy + 17, "so")
    bk.eq(x + GUT + 22, cy + 16, f"{n} + {m} = [{n + m}]", size=18)


def c_count_to(bk, x, cy, w, n):
    t, o = divmod(n, 10)
    tens_ones_picture(bk, x + GUT, cy + 44, t, o, h=60)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{t}] tens [{o}] ones = [{n}]", size=17)


def c_draw_qt(bk, x, cy, w, n):
    t, o = divmod(n, 10)
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 30)
    bk.c.drawString(x + GUT, cy + 64, str(n))
    bx, bw = x + GUT + 58, w - GUT - 66
    bk.work(bx, cy + 42, bw, 62, "Draw it")
    if bk.key:
        quick_tens(bk, bx + 14, cy + 48, t, o, h=40, color=T.answer)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"[{t}] tens [{o}] ones", size=17)


def c_count_tens(bk, x, cy, w, n):
    t = n // 10
    tens_ones_picture(bk, x + GUT, cy + 36, t, 0, h=48)
    bk.fit_eq(x + GUT, cy + 10, w - GUT - 10, f"[{t}] tens = [{n}]", size=16)


def c_which_more(bk, x, cy, w, pair):
    a, b = pair
    for j, n in enumerate((a, b)):
        nx = x + GUT + 30 + j * 90
        bk.c.setFillColor(T.ink)
        bk.c.setFont("Rnd", 24)
        bk.c.drawCentredString(nx, cy + 14, str(n))
        if bk.key and n == max(a, b):
            bk.c.setStrokeColor(T.answer)
            bk.c.setLineWidth(1.6)
            bk.c.ellipse(nx - 26, cy + 5, nx + 26, cy + 40, stroke=1, fill=0)


def c_ten_more_pic(bk, x, cy, w, n):
    more_less_picture(bk, x + GUT, cy + 44, n, "more")
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{n} + 10 = [{n + 10}]", size=18)


def c_ten_less_pic(bk, x, cy, w, n):
    more_less_picture(bk, x + GUT, cy + 44, n, "less")
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{n} − 10 = [{n - 10}]", size=18)


def c_side(bk, x, cy, w, n):
    c = bk.c
    bx = x + GUT
    mid = bx + 100
    for lab, val, lx in (("10 less", n - 10, bx), ("10 more", n + 10, bx + 156)):
        c.setFillColor(T.text2)
        c.setFont("AvD", 10)
        c.drawCentredString(lx + 22, cy + 48, lab)
        bk.box(lx, cy + 12, 44, 30, val, size=18)
    c.setFillColor(T.ink)
    c.setFont("Rnd", 24)
    c.drawCentredString(mid, cy + 18, str(n))
    bk.arrow(mid - 22, cy + 27, bx + 52, cy + 27)
    bk.arrow(mid + 22, cy + 27, bx + 148, cy + 27)


def c_chain10(bk, x, cy, w, item):
    op, start = item
    c = bk.c
    seq = [start + (10 if op == "+" else -10) * i for i in range(6)]
    c.setFillColor(T.text2)
    c.setFont("AvD", 15)
    c.drawString(x + GUT, cy + 18, f"{op}10")
    gx = 68
    for i, n in enumerate(seq):
        cx = x + GUT + 82 + i * gx
        if i < 3:
            c.setFillColor(T.ink)
            c.setFont("Rnd", 20)
            c.drawCentredString(cx, cy + 18, str(n))
        else:
            bk.box(cx - 21, cy + 10, 42, 30, n, size=18)
        if i:
            bk.arrow(cx - gx + 25, cy + 25, cx - 25, cy + 25)


def c_add_tens_pic(bk, x, cy, w, item):
    a, b = item
    add_picture(bk, x + GUT, cy + 44, a, b, h=52)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)


def c_add_pic_rows(bk, x, cy, w, item):
    a, b = item
    add_picture(bk, x + GUT, cy + 120, a, b, h=54)
    bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)
    split_rows(bk, x + GUT, cy + 66, a, b, helped=True, size=13, gap=27)


def c_add_split(bk, x, cy, w, item):
    a, b = item
    bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)
    split_rows(bk, x + GUT, cy + 66, a, b, size=13, gap=27)


def c_sub_tens_pic(bk, x, cy, w, item):
    a, b = item
    take_away_picture(bk, x + GUT, cy + 44, a, b, h=52)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{a} − {b} = [{a - b}]", size=18)


def c_sub_pic_rows(bk, x, cy, w, item):
    a, b = item
    take_away_picture(bk, x + GUT, cy + 120, a, b, h=54)
    bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"{a} − {b} = [{a - b}]", size=18)
    split_rows(bk, x + GUT, cy + 66, a, b, helped=True, size=13, gap=27, op="−")


def c_sub_split(bk, x, cy, w, item):
    a, b = item
    bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"{a} − {b} = [{a - b}]", size=18)
    split_rows(bk, x + GUT, cy + 66, a, b, size=13, gap=27, op="−")


def c_enough(bk, x, cy, w, item):
    a, b = item
    bk.eq(x + GUT, cy + 15, f"{a} − {b}", size=18)
    yes = a % 10 >= b % 10
    for j, word in enumerate(["yes", "no"]):
        px = x + w - 104 + j * 50
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 13)
        bk.c.drawCentredString(px + 20, cy + 16, word)
        if bk.key and (word == "yes") == yes:
            bk.c.setStrokeColor(T.answer)
            bk.c.setLineWidth(1.6)
            bk.c.ellipse(px + 2, cy + 8, px + 38, cy + 34, stroke=1, fill=0)


def c_jump_up(bk, x, cy, w, item, given=True):
    a, total = item
    stops = jump_stops(a, total)
    # ~15pt of air between the problem, the jumps and the sum row
    bk.fit_eq(x + GUT, cy + 122, w - GUT - 10, f"{a} + [{total - a}] = {total}", size=18)
    spacing = min(80, (w - GUT - 36) / (len(stops) - 1))
    jump_up(bk, x + GUT + 14, cy + 52, stops, spacing, given=given)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, jumps_sum(stops), size=14)


def c_break_ten(bk, x, cy, w, n):
    tens_ones_picture(bk, x + GUT, cy + 44, n // 10, n % 10, h=52)
    # the tens are given, so the only question is the new number of ones
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{n} = {n // 10 - 1} tens [{n % 10 + 10}] ones", size=17)


def c_borrow_rows(bk, x, cy, w, item, helped):
    a, b = item
    bk.fit_eq(x + GUT, cy + 126, w - GUT - 10, f"{a} {MINUS} {b} = [{a - b}]", size=18)
    borrow_rows(bk, x + GUT, cy + 90, a, b, helped=helped)


def c_col_add(bk, x, cy, w, item, mode="plain", header=False):
    a, b = item
    stacked(bk, x + 26, cy + 8, a, b, mode=mode, size=18, header=header)


def c_line_up(bk, x, cy, w, item):
    a, b = item
    bk.eq(x + GUT, cy + 128, f"{a} + {b}", size=16)
    stack_grid(bk, x + 40, cy + 8, a, b, size=18)


def c_add_mat(bk, x, cy, w, item):
    a, b = item
    add_mat(bk, x + GUT, cy + 132, a, b, result=False, wt=140, wo=124, row_h=44)
    stacked(bk, x + GUT + 330, cy + 12, a, b, mode="boxes", size=22, header=True)


def c_col_sub(bk, x, cy, w, item, mode="plain", header=False):
    a, b = item
    stacked(bk, x + 26, cy + 8, a, b, op=MINUS, mode=mode, size=18, header=header)


def c_sub_mat(bk, x, cy, w, item):
    a, b = item
    sub_mat(bk, x + GUT + 70, cy + 136, a, b, wt=124, wo=120, row_h=56)
    stacked(bk, x + GUT + 360, cy + 12, a, b, op=MINUS, mode="boxes", size=22, header=True)


def c_count_hto(bk, x, cy, w, n):
    h, t, o = n // 100, n // 10 % 10, n % 10
    hto_picture(bk, x + GUT, cy + 58, h, t, o, s=38, gap=4)
    hto_boxes(bk, x + GUT, cy + 10, h, t, o)


def c_draw_hto(bk, x, cy, w, n):
    h, t, o = n // 100, n // 10 % 10, n % 10
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 28)
    bk.c.drawString(x + GUT, cy + 70, str(n))
    bx, bw = x + GUT + 66, w - GUT - 74
    bk.work(bx, cy + 44, bw, 66, "Draw it")
    if bk.key:
        quick_hto(bk, bx + 10, cy + 50, h, t, o, size=11, line_h=28, color=T.answer)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"[{h}] hundreds [{t}] tens [{o}] ones", size=15)


def c_worth(bk, x, cy, w, item):
    n, d = item
    s_ = str(n)
    pos = s_.index(str(d))
    val = d * 10 ** (2 - pos)
    c = bk.c
    c.setFillColor(T.text2)
    c.setFont("AvD", 12)
    c.drawString(x + GUT, cy + 16, "In")
    xx = x + GUT + 22
    c.setFont("Rnd", 18)
    for i, ch in enumerate(s_):
        c.setFillColor(T.accent if i == pos else T.ink)
        c.drawString(xx, cy + 15, ch)
        xx += sw(ch, "Rnd", 18) + 1
    c.setFillColor(T.text2)
    c.setFont("AvD", 12)
    c.drawString(xx + 6, cy + 16, f"the {d} is")
    bk.box(xx + 6 + sw(f"the {d} is", "AvD", 12) + 6, cy + 8, 46, 28, val, size=16)


def c_bars5(bk, x, cy, w, n):
    for i in range(n):
        by = cy + 112 - (i + 1) * 13.2
        five_bar(bk, x + GUT, by, 10.5, "a" if i % 2 == 0 else "b")
        v = (i + 1) * 5
        if i == 0:
            bk.c.setFillColor(T.ink)
            bk.c.setFont("Rnd", 11)
            bk.c.drawCentredString(x + GUT + 80, by + 2, "5")
        else:
            bk.box(x + GUT + 66, by - 1, 28, 12.5, v, size=10)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvD", 11)
    bk.c.drawString(x + GUT + 112, cy + 52, "dots in all:")
    bk.box(x + GUT + 112, cy + 18, 50, 28, n * 5, size=17)


def c_chain(bk, x, cy, w, item, arcs=True):
    start, step, blanks = item
    seq = [start + step * i for i in range(7)]
    c = bk.c
    if arcs:
        count_chain(bk, x + GUT + 24, cy + 16, seq, blanks, f"+{step}" if step > 0 else f"\u2212{-step}",
                    spacing=68, size=17, bw=44)
    else:
        count_chain(bk, x + GUT + 24, cy + 16, seq, blanks, spacing=68, size=17, bw=44, arcs=False)


def c_seq(bk, x, cy, w, item):
    start, step, blanks = item
    seq = [start + step * i for i in range(5)]
    count_chain(bk, x + GUT + 10, cy + 16, seq, blanks, spacing=42, size=15, bw=34, arcs=False)


def c_count_by(bk, x, cy, w, item):
    seq = item
    step = seq[1] - seq[0]
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("Rnd", 15)
    c.drawString(x + GUT, cy + 16, ",  ".join(map(str, seq)))
    c.setFillColor(T.text2)
    c.setFont("AvD", 12)
    c.drawString(x + GUT + 250, cy + 17, "We are counting by")
    bk.box(x + GUT + 370, cy + 8, 50, 28, step, size=16)


def c_cmp_pic(bk, x, cy, w, item):
    def draw(cx, y0, n):
        t, o = divmod(n, 10)
        width = t * 8 + 3 + (7.5 * ((o - 1) // 3) + 6.4 if o else 0)
        mini_tens(bk, cx - width / 2, y0, n)
    compare_card(bk, x, cy, w, *item, draw)


def c_cmp_draw(bk, x, cy, w, item):
    def draw(cx, y0, n):
        h, t, o = n // 100, n // 10 % 10, n % 10
        width = h * 14 + (4 if h else 0) + t * 9 + (6 if t else 0) + (9 * ((o - 1) // 5 + 1) if o else 0)
        quick_hto(bk, cx - width / 2, y0, h, t, o, size=8, line_h=26)
    compare_card(bk, x, cy, w, *item, draw)


def c_place(bk, x, cy, w, item):
    a, b = item
    sa, sb = str(a), str(b)
    first = next(i for i in range(3) if sa[i] != sb[i])
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 20)
    bk.c.drawString(x + GUT, cy + 30, f"{a}   {b}")
    for j, word in enumerate(["hundreds", "tens", "ones"]):
        px = x + GUT + j * 64
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 11)
        bk.c.drawCentredString(px + 26, cy + 9, word)
        if bk.key and j == first:
            bk.c.setStrokeColor(T.answer)
            bk.c.setLineWidth(1.5)
            bk.c.ellipse(px - 4, cy + 3, px + 56, cy + 23, stroke=1, fill=0)


def c_order(bk, x, cy, w, nums):
    srt = sorted(nums)
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 17)
    bk.c.drawString(x + GUT, cy + 50, "   ".join(map(str, nums)))
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{srt[0]}] < [{srt[1]}] < [{srt[2]}]", size=17)


def c_hund_pic(bk, x, cy, w, n, op):
    h, t, o = n // 100, n // 10 % 10, n % 10
    text = f"{n} + 100 = [{n + 100}]" if op == "+" else f"{n} {MINUS} 100 = [{n - 100}]"
    hto_picture(bk, x + GUT, cy + 50, h, t, o, s=34, sw_=8, gap=4,
                extra="h" if op == "+" else None, cross="h" if op != "+" else None)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, text, size=18)


def c_cross(bk, x, cy, w, n):
    number_cross(bk, x + w / 2 + 6, cy + 80, n, dx=76, dy=50, bw=48)


def c_chain_hund(bk, x, cy, w, item):
    start, step = item
    seq = [start + step * i for i in range(6)]
    sign = "+" if step > 0 else MINUS
    count_chain(bk, x + GUT + 24, cy + 16, seq, (3, 4, 5), f"{sign}{abs(step)}", spacing=78, size=17, bw=46)


def c_add3_rows(bk, x, cy, w, item, helped, drawing):
    a, b = item
    top = cy + (196 if drawing else 150)
    if drawing:
        two_drawings(bk, x + GUT, top - 26, a, b)
        top -= 46
    bk.fit_eq(x + GUT, top - 22, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)
    hto_add_rows(bk, x + GUT, top - 56, a, b, helped=helped, size=12, gap=27, maxw=w - GUT - 8)


def c_col_add3(bk, x, cy, w, item, mode="plain", header=False):
    a, b = item
    stacked(bk, x + 28, cy + 8, a, b, mode=mode, size=16, header=header)


def c_take3(bk, x, cy, w, item):
    a, b = item
    quick_take(bk, x + GUT, cy + 50, a, b, size=11, line_h=28)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{a} {MINUS} {b} = [{a - b}]", size=18)


def c_sub3_rows(bk, x, cy, w, item, helped):
    a, b = item
    bk.fit_eq(x + GUT, cy + 156, w - GUT - 10, f"{a} {MINUS} {b} = [{a - b}]", size=18)
    hto_sub_rows(bk, x + GUT, cy + 122, a, b, helped=helped, size=12, gap=27, maxw=w - GUT - 8)


def c_col_sub3(bk, x, cy, w, item, mode="plain", header=False):
    a, b = item
    stacked(bk, x + 28, cy + 8, a, b, op=MINUS, mode=mode, size=16, header=header)


def c_groups(bk, x, cy, w, item):
    g, n = item
    groups_picture(bk, x + GUT, cy + 66, [n] * g, R=16, gap=8)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{g}] groups of [{n}] = [{g * n}]", size=16)


def c_eq_groups(bk, x, cy, w, sizes):
    groups_picture(bk, x + GUT, cy + 30, sizes, R=14, gap=6)
    yes = len(set(sizes)) == 1
    for j, word in enumerate(["yes", "no"]):  # yes on top, no below (always this order)
        px, py = x + w - 46, cy + 36 - j * 24
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 13)
        bk.c.drawCentredString(px, py, word)
        if bk.key and (word == "yes") == yes:
            bk.c.setStrokeColor(T.answer)
            bk.c.setLineWidth(1.6)
            bk.c.ellipse(px - 19, py - 7, px + 19, py + 14, stroke=1, fill=0)


def c_array(bk, x, cy, w, item):
    rows, cols = item
    array_picture(bk, x + GUT, cy + 104, rows, cols, step=13, r=4.4)
    bk.eq(x + GUT + 84, cy + 76, f"[{rows}] rows of [{cols}]", size=15)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, " + ".join([f"[{cols}]"] * rows) + f" = [{rows * cols}]", size=15)


def c_draw_array(bk, x, cy, w, item):
    rows, cols = item
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("Rnd", 13)
    c.drawString(x + GUT, cy + 92, f"{rows} rows of {cols}")
    bx, bw = x + GUT + 104, w - GUT - 112
    bk.work(bx, cy + 40, bw, 70, "Draw it")
    if bk.key:
        array_picture(bk, bx + 14, cy + 92, rows, cols, step=10.5, r=3.6)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, " + ".join([f"[{cols}]"] * rows) + f" = [{rows * cols}]", size=15)


def c_two_ways(bk, x, cy, w, item):
    rows, cols = item
    array_picture(bk, x + GUT, cy + 128, rows, cols, step=13, r=4.4)
    bk.fit_eq(x + GUT, cy + 44, w - GUT - 10, " + ".join([str(cols)] * rows) + f" = [{rows * cols}]", size=15)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, " + ".join([str(rows)] * cols) + f" = [{rows * cols}]", size=15)


def c_rows_seq(bk, x, cy, w, item):
    n, rows = item
    seq = [n * (i + 1) for i in range(rows)]
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvD", 11)
    bk.c.drawString(x + GUT, cy + 17, f"{rows} rows of {n}:")
    count_chain(bk, x + GUT + 100, cy + 16, seq, tuple(range(1, rows)), spacing=44, size=15, bw=34, arcs=False)


def c_pairs_eo(bk, x, cy, w, n):
    pairs_picture(bk, x + GUT, cy + 40, n, step=14, r=4.6, rings=bk.key, highlight=bk.key)
    even_odd_choice(bk, x + GUT, cy + 12, n)


def c_chain2(bk, x, cy, w, item):
    start, blanks = item
    seq = [start + 2 * i for i in range(7)]
    count_chain(bk, x + GUT + 24, cy + 16, seq, blanks, "+2", spacing=66, size=17, bw=42)


def c_eo_ones(bk, x, cy, w, n):
    s_ = str(n)
    bk.c.setFont("Rnd", 22)
    bk.c.setFillColor(T.ink)
    bk.c.drawString(x + GUT, cy + 30, s_)
    even_odd_choice(bk, x + GUT, cy + 10, n)


def c_eo_word(bk, x, cy, w, n):
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 17)
    bk.c.drawString(x + GUT, cy + 15, f"{n} is")
    bk.box(x + GUT + sw(f"{n} is", "Rnd", 17) + 7, cy + 7, 56, 28, "even" if n % 2 == 0 else "odd", size=15)


def c_seq2(bk, x, cy, w, item):
    start, blanks = item
    seq = [start + 2 * i for i in range(5)]
    count_chain(bk, x + GUT + 10, cy + 16, seq, blanks, spacing=42, size=15, bw=34, arcs=False)
# ====================================================================== check-ins and assessments
# Every problem type from the packets is a card below (c_*). A Section names a card type, a pool of
# possible problems and how many to use. The Picker chooses problems: it prefers ones no practice
# packet used, and never uses one twice across all check-ins and assessments in a build.

import random
from collections import namedtuple

Section = namedtuple("Section", "name sub kind pool count packet", defaults=(None,))
Kind = namedtuple("Kind", "h cols key draw gap", defaults=(10,))


def qkey(question):
    key = re.sub(r"\[[^\]]*\]", "[]", question)
    return re.sub(r"\s+", " ", key).strip()


class Picker:
    def __init__(self, practice):
        self.practice = set(practice)
        self.used = set()

    def pick(self, kind, pool, n, doc=None):
        """1st choice: new to everything. 2nd: used in a practice packet. Last resort (tiny fact sets like
        the ten buddies): used in another check-in or assessment, but never twice in the same document."""
        out, keys = [], []
        doc = set() if doc is None else doc
        for level in (0, 1, 2):
            for item in pool:
                k = qkey(KINDS[kind].key(item))
                if k in keys or k in doc or (level < 2 and k in self.used) or (level == 0 and k in self.practice):
                    continue
                out.append(item)
                keys.append(k)
                if len(out) == n:
                    self.used.update(keys)
                    doc.update(keys)
                    return out
        raise ValueError(f"Not enough {kind} problems: wanted {n}, found {len(out)}")


def shuf(seed, xs):
    xs = list(xs)
    random.Random(seed).shuffle(xs)
    return xs


def E(a, op, b):
    """Plain equation text with the answer box."""
    return f"{a} + {b} = [{a + b}]" if op == "+" else f"{a} {MINUS} {b} = [{a - b}]"


# ---------------------------------------------------------------------- packet 0 cards

def c_pic_add(bk, x, cy, w, item):
    kind, a, b = item
    together(bk, kind, x + GUT, cy + 82, a, b, s=28, step=33, per_row=5, gap=34)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"{a} + {b} = [{a + b}]", size=18)


def c_pic_take(bk, x, cy, w, item):
    kind, n, b = item
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvD", 11)
    bk.c.drawString(x + GUT, cy + 84, f"Cross out {b}.")
    objects(bk, kind, x + GUT, cy + 74, n, s=28, step=33, crossed=b, cross_color=T.answer if bk.key else None)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"{n} {MINUS} {b} = [{n - b}]", size=18)


def c_story_pic(bk, x, cy, w, item):
    kind, a, op, b = item
    bk.paragraph(x + GUT, cy + 126, w - GUT - 12, story_text(kind, a, op, b), size=11, leading=15, font="AvM")
    if op == "+":
        together(bk, kind, x + GUT, cy + 82, a, b, s=28, step=33, per_row=5, gap=34)
    else:
        objects(bk, kind, x + GUT, cy + 82, a, s=28, step=33, crossed=b, cross_color=T.answer if bk.key else None)
    sign = "+" if op == "+" else MINUS
    r = a + b if op == "+" else a - b
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"{a} {sign} {b} = [{r}]", size=18)


def c_wide_story(bk, x, cy, w, item):
    kind, a, op, b = item
    bk.paragraph(x + GUT, cy + 112, w - GUT - 16, story_text(kind, a, op, b), size=11.5, leading=15, font="AvM")
    if op == "+":
        together(bk, kind, x + GUT, cy + 68, a, b, s=23, step=27, per_row=5, gap=34, outline=True)
    else:
        objects(bk, kind, x + GUT, cy + 68, a, s=23, step=27, crossed=b, cross_color=T.answer if bk.key else None)
    sign = "+" if op == "+" else MINUS
    r = a + b if op == "+" else a - b
    rr, rest = 14, f"[{b}] = [{r}]"
    start = x + w - 16 - (bk.eq_width(f"[{a}]", 19) + 12 + 2 * rr + bk.eq_width(rest, 19))
    ex = bk.eq(start, cy + 30, f"[{a}]", size=19)
    c = bk.c
    c.setFillColor(white)
    c.setStrokeColor(T.box)
    c.setLineWidth(1)
    c.circle(ex + 6 + rr, cy + 36, rr, stroke=1, fill=1)
    bk.value(ex + 6 + rr, cy + 36, sign, 18)
    bk.eq(ex + 12 + 2 * rr, cy + 30, rest, size=19)


def c_draw_solve(bk, x, cy, w, item):
    a, op, b = item
    bx = x + GUT
    bk.work(bx, cy + 42, w - GUT - 12, 62, "Draw circles")
    if bk.key:
        if op == "+":
            wa = circles(bk, bx + 10, cy + 84, a, r=5.5, step=14)
            circles(bk, bx + 26 + wa, cy + 84, b, r=5.5, step=14, color=T.accent if T.color else T.answer)
        else:
            circles(bk, bx + 10, cy + 84, a, crossed=b, r=5.5, step=14)
    sign = "+" if op == "+" else MINUS
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"{a} {sign} {b} = [{a + b if op == '+' else a - b}]", size=18)


def c_ba(bk, x, cy, w, item):
    bk.break_apart(x + w / 2 + 6, cy + 130 - 8, item[0], item[1])


def c_eq(bk, x, cy, w, text):
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 8, text, size=18)


def c_word(bk, x, cy, w, item):
    story, sentence, answer, unit = item
    tx = x + GUT
    bk.paragraph(tx, cy + 66, w - GUT - 190, story, size=11.5, leading=15, font="AvM")
    if bk.key:
        bk.eq(tx, cy + 10, sentence, size=12, color=T.answer)
    c = bk.c
    ax = x + w - 170
    c.setFillColor(T.text2)
    c.setFont("AvM", 9)
    c.drawString(ax, cy + 31, "Answer")
    bw = max(48, sw(str(answer), "Rnd", 17) + 16)
    bk.box(ax + 40, cy + 22, bw, 30, answer, size=17)
    c.setFillColor(T.ink)
    c.setFont("AvM", 11)
    c.drawString(ax + 46 + bw, cy + 32, unit)


# ---------------------------------------------------------------------- card types

def _k(name, h, cols, key, gap=10):
    draw = globals()[f"c_{name}"]
    return Kind(h, cols, key, lambda bk, x, cy, w, it: draw(bk, x, cy, w, it), gap)


def _plus(it):
    return f"{it[0]} + {it[1]} = []"


def _minus(it):
    return f"{it[0]} {MINUS} {it[1]} = []"


def _countby(n):
    def key(it):
        start, step, blanks = it
        seq = [start + step * i for i in range(n)]
        return f"count by {step} from {start}: {', '.join(str(seq[i]) for i in blanks)}"
    return key


KINDS = {
    "eq3": Kind(42, 3, lambda t: t, c_eq, 8),
    "eq2": Kind(42, 2, lambda t: t, c_eq, 8),
    "word": Kind(80, 1, lambda it: "story: " + it[1], c_word, 8),
    "pic_add": _k("pic_add", 92, 2, lambda it: f"pic: {it[0]} {it[1]} + {it[2]}"),
    "pic_take": _k("pic_take", 100, 2, lambda it: f"pic: {it[0]} {it[1]} - {it[2]}"),
    "story_pic": _k("story_pic", 140, 2, lambda it: f"story pic: {it[0]} {it[1]} {it[2]} {it[3]}"),
    "wide_story": _k("wide_story", 124, 1, lambda it: f"story pic: {it[0]} {it[1]} {it[2]} {it[3]}", 8),
    "draw_solve": _k("draw_solve", 114, 2, lambda it: f"draw to solve: {it[0]} {it[1]} {it[2]}"),
    "frame_buddy": _k("frame_buddy", 84, 2, lambda n: f"frame {n}"),
    "buddy_yesno": _k("buddy_yesno", 44, 2, lambda it: f"buddies? {it[0]}", 8),
    "more10": _k("more10", 96, 3, lambda it: it[0]),
    "teen": _k("teen", 104, 2, lambda it: it[0]),
    "three": _k("three", 110, 2, lambda it: " + ".join(map(str, it)) + " = []"),
    "ba": _k("ba", 130, 2, _plus, 12),
    "ladder": _k("ladder", 84, 2, _plus),
    "hint": _k("hint", 84, 2, _plus),
    "jump_dots": _k("jump_dots", 146, 2, _minus, 12),
    "jump": _k("jump", 104, 2, _minus, 12),
    "jump_less": _k("jump_less", 84, 2, _minus),
    "jump_big": _k("jump_big", 104, 2, _minus, 12),
    "double_dots": _k("double_dots", 96, 2, lambda n: f"double {n} = []"),
    "near_dots": _k("near_dots", 124, 2, lambda it: f"double {it[0]} = [], so {it[0]} + {it[1]} = []"),
    "count_to": _k("count_to", 120, 2, lambda n: f"tens and ones in the picture of {n}"),
    "draw_qt": _k("draw_qt", 114, 2, lambda n: f"draw {n} as quick tens"),
    "count_tens": _k("count_tens", 98, 3, lambda n: f"count the tens in the picture of {n}"),
    "which_more": _k("which_more", 46, 2, lambda it: f"which is more: {it[0]} or {it[1]}", 8),
    "ten_more_pic": _k("ten_more_pic", 120, 2, lambda n: f"{n} + 10 = []"),
    "ten_pic": Kind(120, 2, lambda it: f"{it[0]} + 10 = []" if it[1] == "+" else f"{it[0]} {MINUS} 10 = []",
                    lambda bk, x, cy, w, it: (c_ten_more_pic if it[1] == "+" else c_ten_less_pic)(bk, x, cy, w, it[0])),
    "ten_less_pic": _k("ten_less_pic", 120, 2, lambda n: f"{n} {MINUS} 10 = []"),
    "side": _k("side", 64, 2, lambda n: f"10 less and 10 more than {n}", 8),
    "chain10": _k("chain10", 50, 1, lambda it: f"keep going {it[0]}10 from {it[1]}", 8),
    "add_tens_pic": _k("add_tens_pic", 106, 2, _plus),
    "add_split": _k("add_split", 122, 2, _plus),
    "sub_tens_pic": _k("sub_tens_pic", 106, 2, _minus),
    "sub_split": _k("sub_split", 122, 2, _minus),
    "enough": _k("enough", 44, 2, lambda it: f"enough ones? {it[0]} {MINUS} {it[1]}", 8),
    "jump_up": _k("jump_up", 152, 2, lambda it: f"{it[0]} + [] = {it[1]}"),
    "find_stops": Kind(152, 2, lambda it: f"{it[0]} + [] = {it[1]}",
                       lambda bk, x, cy, w, it: c_jump_up(bk, x, cy, w, it, given=False)),
    "break_ten": _k("break_ten", 106, 2, lambda n: f"break a ten: {n}"),
    "borrow_rows": Kind(154, 2, _minus, lambda bk, x, cy, w, it: c_borrow_rows(bk, x, cy, w, it, False)),
    "col_add": Kind(112, 5, _plus, lambda bk, x, cy, w, it: c_col_add(bk, x, cy, w, it), 8),
    "col_add_boxes": Kind(124, 5, _plus, lambda bk, x, cy, w, it: c_col_add(bk, x, cy, w, it, "boxes", True), 8),
    "line_up": _k("line_up", 150, 4, _plus, 8),
    "col_sub": Kind(118, 5, _minus, lambda bk, x, cy, w, it: c_col_sub(bk, x, cy, w, it), 8),
    "col_sub_boxes": Kind(124, 5, _minus, lambda bk, x, cy, w, it: c_col_sub(bk, x, cy, w, it, "boxes", True), 8),
    "sub_mat": _k("sub_mat", 144, 1, _minus, 8),
    "count_hto": _k("count_hto", 112, 2, lambda n: f"hundreds, tens and ones in the picture of {n}"),
    "draw_hto": _k("draw_hto", 120, 2, lambda n: f"draw {n} as a quick drawing"),
    "worth": _k("worth", 44, 2, lambda it: f"worth: the {it[1]} in {it[0]}", 8),
    "bars5": _k("bars5", 124, 2, lambda n: f"count {n} bars of five"),
    "chain": _k("chain", 64, 1, _countby(7), 8),
    "seq": _k("seq", 46, 2, _countby(5), 8),
    "count_by": _k("count_by", 44, 1, lambda s: f"counting by? {', '.join(map(str, s))}", 8),
    "cmp_pic": _k("cmp_pic", 96, 2, lambda it: f"compare {it[0]} and {it[1]}"),
    "cmp_draw": _k("cmp_draw", 104, 2, lambda it: f"compare {it[0]} and {it[1]}"),
    "place": _k("place", 58, 2, lambda it: f"which place decides {it[0]} or {it[1]}", 8),
    "order": _k("order", 78, 2, lambda it: f"order {', '.join(map(str, it))}"),
    "hund_pic": Kind(100, 2, lambda it: f"{it[0]} + 100 = []" if it[1] == "+" else f"{it[0]} {MINUS} 100 = []",
                     lambda bk, x, cy, w, it: c_hund_pic(bk, x, cy, w, it[0], it[1])),
    "cross": _k("cross", 162, 2, lambda n: f"number cross {n}"),
    "chain_hund": _k("chain_hund", 64, 1, lambda it: f"count by {it[1]} from {it[0]}: " + ", ".join(
        str(it[0] + it[1] * i) for i in range(3, 6)), 8),
    "add3_rows": Kind(160, 2, _plus, lambda bk, x, cy, w, it: c_add3_rows(bk, x, cy, w, it, False, False)),
    "col_add3": Kind(108, 4, _plus, lambda bk, x, cy, w, it: c_col_add3(bk, x, cy, w, it), 8),
    "col_add3_boxes": Kind(116, 4, _plus, lambda bk, x, cy, w, it: c_col_add3(bk, x, cy, w, it, "boxes", True), 8),
    "take3": _k("take3", 96, 2, _minus),
    "sub3_rows": Kind(186, 2, _minus, lambda bk, x, cy, w, it: c_sub3_rows(bk, x, cy, w, it, False)),
    "col_sub3": Kind(112, 4, _minus, lambda bk, x, cy, w, it: c_col_sub3(bk, x, cy, w, it), 8),
    "groups": _k("groups", 96, 2, lambda it: f"groups: {it[0]} groups of {it[1]}"),
    "eq_groups": _k("eq_groups", 60, 2, lambda s: f"equal groups? {'-'.join(map(str, s))}", 8),
    "array": _k("array", 118, 2, lambda it: f"array {it[0]} rows of {it[1]}"),
    "draw_array": _k("draw_array", 118, 2, lambda it: f"draw {it[0]} rows of {it[1]}"),
    "rows_seq": _k("rows_seq", 44, 1, lambda it: f"rows of {it[0]}, {it[1]} rows", 8),
    "pairs_eo": _k("pairs_eo", 84, 2, lambda n: f"even or odd picture {n}"),
    "chain2": _k("chain2", 64, 1, lambda it: f"count by 2 from {it[0]}: " + ", ".join(
        str(it[0] + 2 * i) for i in it[1]), 8),
    "eo_ones": _k("eo_ones", 62, 3, lambda n: f"even or odd {n}", 8),
    "eo_word": _k("eo_word", 42, 3, lambda n: f"{n} is []", 8),
}


# ---------------------------------------------------------------------- problem pools

OBJ = list(STORY_BANK)
NAMES = ["Ava", "Ben", "Mia", "Leo", "Zoe", "Sam", "Kim", "Max", "Lily", "Omar", "Nia", "Jay", "Ella", "Ravi",
         "Tess", "Finn", "Rosa", "Theo", "June", "Kai"]
THINGS = ["stickers", "marbles", "shells", "cards", "beads", "blocks", "books", "pencils", "rocks", "buttons",
          "stamps", "crayons", "toy cars", "leaves", "acorns", "seeds"]


def stories(seed, kind, items):
    """Story problems built from templates. kind: add, sub, compare, make10, tens, groups, pairs, more10."""
    r = random.Random(seed)
    items = list(items)
    r.shuffle(items)
    out = []
    for it in items:
        n, m = r.sample(NAMES, 2)
        t = r.choice(THINGS)
        if kind == "add":
            a, b = it
            out.append((f"{n} has {a} {t} and finds {b} more. How many {t} does {n} have now?",
                        f"{a} + {b} = {a + b}", a + b, t))
        elif kind == "sub":
            a, b = it
            out.append((f"{n} has {a} {t} and gives {b} away. How many {t} does {n} have left?",
                        f"{a} {MINUS} {b} = {a - b}", a - b, t))
        elif kind == "compare":
            a, b = it
            out.append((f"{n} has {a} {t}. {m} has {b} {t}. How many more {t} does {n} have than {m}?",
                        f"{b} + {a - b} = {a}", a - b, t))
        elif kind == "make10":
            out.append((f"A box holds 10 {t}. It has {it} {t} in it. How many more {t} will fill the box?",
                        f"{it} + {10 - it} = 10", 10 - it, t))
        elif kind == "make100":
            out.append((f"A jar holds 100 {t}. It has {it} {t} in it. How many more {t} will fill the jar?",
                        f"{it} + {100 - it} = 100", 100 - it, t))
        elif kind == "tens":
            out.append((f"{n} has {it // 10} packs of 10 {t} and {it % 10} loose {t}. How many {t} is that?",
                        f"{it // 10 * 10} + {it % 10} = {it}", it, t))
        elif kind == "groups":
            g, k = it
            out.append((f"{n} has {g} bags with {k} {t} in each bag. How many {t} are there in all?",
                        " + ".join([str(k)] * g) + f" = {g * k}", g * k, t))
        elif kind == "pairs":
            out.append((f"{it} kids want to play in pairs. Can every kid have a partner, with no one left out?",
                        f"{it} is {'even' if it % 2 == 0 else 'odd'}", "yes" if it % 2 == 0 else "no", ""))
    return out


def rng(lo, hi, step=1):
    return range(lo, hi + 1, step)


ADD5 = [(a, b) for a in rng(1, 4) for b in rng(1, 4) if a + b <= 5]
SUB5 = [(n, b) for n in rng(2, 5) for b in rng(1, n - 1)]
ADD9 = [(a, b) for a in rng(1, 8) for b in rng(1, 8) if 6 <= a + b <= 9]
SUB9 = [(n, b) for n in rng(6, 9) for b in rng(1, n - 1)]
OVER10 = [(a, b) for a in rng(3, 9) for b in rng(2, 9) if a + b > 10 and a >= b]
OVER10_ANY = OVER10 + [(b, a) for a, b in OVER10 if a != b]
TEEN_SUB = [(a, b) for a in rng(11, 18) for b in rng(2, 9) if 0 < a - b < 10]
NEXT10 = [(a, b) for a in rng(15, 88) if a % 10 >= 5 for b in rng(4, 9) if a % 10 + b > 10]
NEAR = [(n, n + 1) for n in rng(2, 9)] + [(n + 1, n) for n in rng(2, 9)]
TWO_ADD_NO = [(a, b) for a in rng(21, 68) for b in rng(11, 31) if a % 10 and b % 10 and a % 10 + b % 10 < 10
              and a + b < 100]
TWO_ADD_NEW = [(a, b) for a in rng(15, 69) for b in rng(13, 29) if a % 10 + b % 10 > 10 and a + b < 100]
TWO_SUB_NO = [(a, b) for a in rng(36, 99) for b in rng(11, 49) if a % 10 > b % 10 > 0 and a - b >= 10]
TWO_SUB_BRK = [(a, b) for a in rng(31, 97) for b in rng(12, 68) if 0 < a % 10 < b % 10 and a - b >= 10]
THREE_ADD = [(a, b) for a in rng(112, 689) if a % 7 == 0 for b in rng(103, 296) if b % 11 == 0
             and a + b < 1000 and a % 10 and b % 10 and a // 10 % 10 and b // 10 % 10]
THREE_SUB = [(a, b) for a in rng(321, 987) if a % 13 == 0 for b in rng(104, 289) if b % 7 == 0
             and a - b > 100 and (a % 10 < b % 10) + (a // 10 % 10 < b // 10 % 10) <= 1
             and a % 10 and a // 10 % 10]


BALANCE = {  # answers that must not form a pattern: the pool alternates between the two answers
    "buddy_yesno": lambda it: it[1],
    "enough": lambda it: it[0] % 10 >= it[1] % 10,
    "which_more": lambda it: it[0] > it[1],
    "cmp_pic": lambda it: it[0] > it[1],
    "cmp_draw": lambda it: it[0] > it[1],
    "eq_groups": lambda it: len(set(it)) == 1,
    "pairs_eo": lambda n: n % 2 == 0,
    "eo_ones": lambda n: n % 2 == 0,
    "eo_word": lambda n: n % 2 == 0,
}


def alternate(pool, test):
    a = [x for x in pool if test(x)]
    b = [x for x in pool if not test(x)]
    out = []
    for i in range(max(len(a), len(b))):
        out += a[i:i + 1] + b[i:i + 1]
    return out


def S(name, sub, kind, pool, count, packet=None, seed=None, balance=None):
    pool = shuf(seed or (name + kind), pool)
    test = balance or BALANCE.get(kind)
    if test:
        pool = alternate(pool, test)
    return Section(name, sub, kind, pool, count, packet)


def is_less(text):
    return "[<]" in text


def eqs(pairs, op):
    return [E(a, op, b) for a, b in pairs]


def buddy_eqs():
    return [f"{a} + [{10 - a}] = 10" for a in rng(0, 10)] + [f"[{a}] + {10 - a} = 10" for a in rng(0, 10)]


def teen_eqs():
    return ([f"10 + {n} = [{10 + n}]" for n in rng(1, 9)] + [f"{n} + 10 = [{10 + n}]" for n in rng(1, 9)]
            + [f"10 + [{n}] = {10 + n}" for n in rng(1, 9)] + [f"[10] + {n} = {10 + n}" for n in rng(1, 9)]
            + [f"{n} + [10] = {10 + n}" for n in rng(1, 9)])


def compare_eqs(pairs):
    return [f"{a} [{sign_of(a, b)}] {b}" for a, b in pairs]


TWO_DIG = [n for n in rng(21, 98) if n % 10]
THREE_DIG = [n for n in rng(102, 987) if n % 10 and n // 10 % 10]


# ---------------------------------------------------------------------- one check-in page per packet

CHECKINS = {
    "0-adding-and-taking-away": [
        S("Put together", "Count them all.", "pic_add", [(k, a, b) for k in OBJ for a, b in ADD5], 2),
        S("Take away", "Cross out. Count what is left.", "pic_take", [(k, n, b) for k in OBJ for n, b in SUB5], 2),
        S("Story problems", "Listen to the story.", "story_pic",
          [(k, a, "+", b) for k in OBJ for a, b in ADD5] + [(k, n, "-", b) for k in OBJ for n, b in SUB5], 2),
        S("Add and take away", "Up to 9.", "eq3", eqs(ADD9, "+") + eqs(SUB9, "-"), 6),
    ],
    "1-ten-buddies": [
        S("How many dots? What is its buddy?", None, "frame_buddy", list(rng(1, 9)), 2),
        S("Fill in the buddy", None, "eq3", buddy_eqs(), 6),
        S("Are they Ten Buddies?", "Circle yes or no.", "buddy_yesno",
          [(f"{a} and {b}", a + b == 10) for a in rng(1, 9) for b in rng(1, 9)], 2),
        S("How many more to make 10?", None, "more10", [(f"{a} + [{10 - a}] = 10", a, 10 - a) for a in rng(1, 9)], 3),
        S("Word problem", None, "word", stories("w1", "make10", rng(1, 9)), 1),
    ],
    "2-ten-and-some-more": [
        S("Ten and some more", "Count the extra dots.", "teen", [(f"10 + {n} = [{10 + n}]", n) for n in rng(1, 9)]
          + [(f"10 + [{n}] = {10 + n}", n) for n in rng(1, 9)], 2),
        S("Teen numbers", None, "eq3", teen_eqs(), 6),
        S("Find the buddies first, then add", "Circle the two numbers that make 10.", "three",
          [(a, 10 - a, c) for a in rng(1, 9) for c in rng(1, 9)] + [(c, a, 10 - a) for a in rng(1, 9) for c in rng(1, 9)], 2),
        S("Word problem", None, "word", stories("w2", "add", [(10, n) for n in rng(1, 9)]), 1),
    ],
    "3-up-to-and-over-ten": [
        S("Break it apart", None, "ba", OVER10, 2),
        S("In your head", None, "eq3", eqs(OVER10_ANY, "+"), 6),
        S("Up to ten or over ten?", None, "eq3", eqs([(a, 10 - a) for a in rng(1, 9)], "+") + eqs(OVER10, "+"), 3),
        S("Word problem", None, "word", stories("w3", "add", OVER10), 1),
    ],
    "4-over-the-next-ten": [
        S("Up to the next ten, then over", None, "ladder", NEXT10, 2),
        S("Break it apart", None, "ba", NEXT10, 2),
        S("On your own", None, "eq3", eqs(NEXT10, "+"), 6),
        S("Word problem", None, "word", stories("w4", "add", NEXT10), 1),
    ],
    "5-back-through-ten": [
        S("See the jumps", None, "jump_dots", TEEN_SUB, 2),
        S("Jump through ten", "Fill in both jumps.", "jump", TEEN_SUB, 2),
        S("Less help", "Fill in the two jumps.", "jump_less", TEEN_SUB, 2),
        S("On your own", None, "eq3", eqs(TEEN_SUB, "-"), 6),
    ],
    "6-doubles-and-near-doubles": [
        S("Doubles with dots", None, "double_dots", list(rng(2, 9)), 2),
        S("Near doubles with dots", "Find the double, then add 1.", "near_dots", [(n, n + 1) for n in rng(2, 9)], 2),
        S("Doubles and near doubles", None, "eq3", eqs([(n, n) for n in rng(1, 10)] + NEAR, "+"), 6),
        S("Big numbers", None, "eq3", eqs([(a, b) for a in rng(11, 15) for b in rng(11, 15) if abs(a - b) <= 1], "+"), 3),
    ],
    "7-tens-and-ones": [
        S("Count the tens and ones", None, "count_to", [n for n in TWO_DIG if n < 70], 2),
        S("Draw it", "A line for each ten, a dot for each one.", "draw_qt", [n for n in TWO_DIG if n < 60], 2),
        S("Tens and ones", None, "eq2", [f"[{n // 10}] tens [{n % 10}] ones = {n}" for n in TWO_DIG]
          + [f"{n // 10} tens {n % 10} ones = [{n}]" for n in TWO_DIG], 6),
        S("Which is more?", "Circle the bigger number.", "which_more",
          [(a, b) for a in TWO_DIG for b in TWO_DIG if a // 10 != b // 10 and a % 10 > b % 10][:400], 2),
    ],
    "8-ten-more-ten-less": [
        S("10 more and 10 less", None, "ten_pic", [(n, "+") for n in TWO_DIG if n < 70]
          + [(n, "-") for n in TWO_DIG if 20 < n < 80], 2),
        S("10 less and 10 more", None, "side", [n for n in TWO_DIG if n < 90], 2),
        S("Keep going", None, "chain10", [("+", n) for n in rng(2, 39)] + [("−", n) for n in rng(60, 99)], 1),
        S("Ten more, ten less", None, "eq3", eqs([(n, 10) for n in TWO_DIG if n < 90], "+")
          + eqs([(n, 10) for n in TWO_DIG], "-"), 6),
        S("Word problem", None, "word", stories("w8", "add", [(n, 10) for n in TWO_DIG if n < 90]), 1),
    ],
    "9-adding-two-digit-numbers": [
        S("Add tens", None, "add_tens_pic", [(a, b) for a in rng(12, 45) for b in (20, 30, 40) if a % 10], 2),
        S("Split it", "Fill in every box.", "add_split", TWO_ADD_NO + TWO_ADD_NEW, 2),
        S("Add", None, "eq3", eqs(TWO_ADD_NO + TWO_ADD_NEW, "+"), 6),
        S("Word problem", None, "word", stories("w9", "add", TWO_ADD_NEW), 1),
    ],
    "10-subtracting-two-digit-numbers": [
        S("Take away tens", None, "sub_tens_pic", [(a, b) for a in rng(41, 89) for b in (20, 30) if a % 10], 2),
        S("Split it", "Fill in every box.", "sub_split", TWO_SUB_NO, 2),
        S("Enough ones?", "Circle yes or no.", "enough", TWO_SUB_NO + TWO_SUB_BRK, 2),
        S("Take away", None, "eq3", eqs(TWO_SUB_NO, "-"), 3),
        S("Word problem", None, "word", stories("w10", "sub", TWO_SUB_NO), 1),
    ],
    "11-missing-numbers": [
        S("Jump up", "Fill in the jumps. Add them up.", "jump_up", [(a, t) for a, t in
          [(a, a + b) for a, b in NEXT10] if t % 10], 2),
        S("Find the stops", "Write the tens you jump to.", "find_stops", [(a, a + b) for a, b in TWO_ADD_NEW], 2),
        S("Missing numbers", None, "eq3", [f"{a} + [{b}] = {a + b}" for a, b in OVER10 + TWO_ADD_NEW], 3),
        S("Word problem", None, "word", stories("w11", "compare", [(a + b, a) for a, b in TWO_ADD_NEW]), 1),
    ],
    "12-subtracting-with-borrowing": [
        S("Break a ten", None, "break_ten", TWO_DIG, 2),
        S("Break, then subtract", "Fill in every box.", "borrow_rows", TWO_SUB_BRK, 2),
        S("Subtract", None, "eq3", eqs(TWO_SUB_BRK, "-"), 6),
        S("Word problem", None, "word", stories("w12", "sub", TWO_SUB_BRK), 1),
    ],
    "13-adding-in-columns": [
        S("Carry the new ten", None, "col_add_boxes", TWO_ADD_NEW, 5),
        S("Line them up", None, "line_up", [(a, b) for a in TWO_DIG for b in rng(3, 9) if a + b < 100], 4),
        S("Add", None, "col_add", TWO_ADD_NO + TWO_ADD_NEW, 5),
    ],
    "14-subtracting-in-columns": [
        S("Use the mat", None, "sub_mat", TWO_SUB_BRK, 1),
        S("Break it yourself", None, "col_sub_boxes", TWO_SUB_BRK, 5),
        S("Subtract", None, "col_sub", TWO_SUB_NO + TWO_SUB_BRK + [(t * 10, b) for t in rng(4, 9) for b in rng(11, 39)
                                                                      if t * 10 - b >= 10 and b % 10], 5),
        S("Word problem", None, "word", stories("w14", "sub", TWO_SUB_BRK), 1),
    ],
    "15-hundreds-tens-and-ones": [
        S("Count them", None, "count_hto", [n for n in THREE_DIG if n < 400 and n // 10 % 10 <= 5 and n % 10 <= 6], 2),
        S("Draw it", None, "draw_hto", [n for n in THREE_DIG if n < 500 and n // 10 % 10 <= 6], 2),
        S("What is it worth?", None, "worth", [(n, int(str(n)[i])) for n in THREE_DIG for i in range(3)
                                              if len(set(str(n))) == 3], 4),
        S("Write the number", None, "eq2", [f"{n // 100} hundreds {n // 10 % 10} tens {n % 10} ones = [{n}]"
                                            for n in THREE_DIG if n >= 200], 4),
    ],
    "16-skip-counting": [
        S("Count the fives", None, "bars5", list(rng(4, 8)), 2),
        S("Keep counting", None, "chain", [(s, 10, (3, 4, 5, 6)) for s in rng(3, 160)]
          + [(s, 100, (3, 4, 5, 6)) for s in rng(5, 290, 5)], 2),
        S("Fill in the missing numbers", None, "seq", [(s, st, (1, 3)) for st in (5, 10, 100) for s in
                                                       rng(5, 400) if s % 5 == 0], 4),
        S("What are we counting by?", None, "count_by", [[s + st * i for i in range(4)] for st in (5, 10, 100)
                                                         for s in rng(15, 300) if s % 5 == 0], 1),
    ],
    "17-comparing-numbers": [
        S("Compare the pictures", None, "cmp_pic", [(a, b) for a in TWO_DIG for b in TWO_DIG if a != b and a < 80
                                                   and b < 80][:2000], 2),
        S("Compare the drawings", None, "cmp_draw", [(a, b) for a in THREE_DIG[:300] for b in THREE_DIG[:300]
                                                     if a // 100 == b // 100 and a != b and a < 300 and b < 300
                                                     and a // 10 % 10 <= 5 and b // 10 % 10 <= 5], 2),
        S("Put them in order", "Smallest first.", "order", [(a, b, c) for a, b, c in
                                                            zip(THREE_DIG[::7], THREE_DIG[3::11], THREE_DIG[5::13])
                                                            if len({a, b, c}) == 3], 2),
        S("Compare", "Write <, > or =.", "eq3", compare_eqs([(a, b) for a in THREE_DIG[::5] for b in THREE_DIG[::9]
                                                              if a != b][:3000]), 6, balance=is_less),
    ],
    "18-10-and-100-more-or-less": [
        S("100 more or 100 less", None, "hund_pic", [(n, "+") for n in THREE_DIG if n < 340 and n // 10 % 10 <= 4]
          + [(n, "-") for n in THREE_DIG if 200 < n < 450 and n // 10 % 10 <= 4], 2),
        S("Number cross", None, "cross", [n for n in THREE_DIG if 150 < n < 850], 2),
        S("Keep going", None, "chain_hund", [(n, 100) for n in rng(102, 380)] + [(n, -10) for n in rng(250, 980)], 1),
        S("10 or 100 more or less", None, "eq3", [E(n, op, d) for n in THREE_DIG[::3] for d in (10, 100)
                                                   for op in "+-" if n - d > 0 and n + d < 1000], 6),
    ],
    "19-adding-three-digit-numbers": [
        S("Add each place", "Fill in every box.", "add3_rows", THREE_ADD, 2),
        S("Stack it", None, "col_add3_boxes", THREE_ADD, 4),
        S("Add", None, "col_add3", THREE_ADD, 4),
        S("Word problem", None, "word", stories("w19", "add", THREE_ADD), 1),
    ],
    "20-subtracting-three-digit-numbers": [
        S("What is left?", None, "take3", [(a, b) for a in THREE_DIG if a < 400 for b in THREE_DIG
                                           if b < 250 and a % 10 >= b % 10 and a // 10 % 10 >= b // 10 % 10
                                           and a // 100 > b // 100][:3000], 2),
        S("Take away each place", "Fill in every box.", "sub3_rows", THREE_SUB, 2),
        S("Subtract", None, "col_sub3", THREE_SUB, 4),
    ],
    "21-equal-groups-and-arrays": [
        S("Equal groups", None, "groups", [(g, n) for g in rng(2, 5) for n in rng(2, 5)], 2),
        S("Equal or not?", "Circle yes or no.", "eq_groups", [[n] * g for g in rng(2, 4) for n in rng(2, 5)]
          + [[n, n + 1, n][:g] + [n] * (g - 3) for g in rng(3, 4) for n in rng(1, 4)], 2),
        S("Arrays", None, "array", [(r, c) for r in rng(2, 5) for c in rng(2, 5)], 2),
        S("Add equal groups", None, "eq2", [" + ".join([str(n)] * g) + f" = [{n * g}]" for g in rng(2, 5)
                                            for n in rng(2, 5)] + [f"{r} rows of {c} = [{r * c}]"
                                                                   for r in rng(2, 5) for c in rng(2, 5)], 6),
    ],
    "22-even-and-odd": [
        S("Pair them up", "Then circle even or odd.", "pairs_eo", list(rng(5, 16)), 2),
        S("Big doubles", None, "eq3", [f"[{n}] + [{n}] = {2 * n}" for n in rng(10, 44) if n % 10 <= 4], 3),
        S("Look at the ones", "Circle even or odd.", "eo_ones", list(rng(21, 199)), 3),
        S("Even or odd?", "Write even or odd.", "eo_word", list(rng(11, 299)), 6),
        S("Count by 2s", None, "seq", [(s, 2, (1, 3)) for s in rng(3, 90)], 2),
    ],
}


# ---------------------------------------------------------------------- grade-level assessments

GRADES = [
    ("kindergarten", "Kindergarten", "Packets 0–2", [
        S("Put together", "Count them all.", "pic_add", [(k, a, b) for k in OBJ for a, b in ADD5], 4, 0),
        S("Take away", "Cross out. Count what is left.", "pic_take", [(k, n, b) for k in OBJ for n, b in SUB5], 4, 0),
        S("Story problems", "Write the numbers, and + or − in the circle.", "wide_story",
          [(k, a, "+", b) for k in OBJ for a, b in ADD9 if max(a, b) <= 5]
          + [(k, n, "-", b) for k in OBJ for n, b in SUB9], 2, 0),
        S("Draw to solve", "Draw circles.", "draw_solve", [(a, "+", b) for a, b in ADD9]
          + [(n, "-", b) for n, b in SUB9], 2, 0),
        S("Add and take away", None, "eq3", eqs(ADD5 + ADD9, "+") + eqs(SUB5 + SUB9, "-"), 9, 0),
        S("How many dots? What is its buddy?", None, "frame_buddy", list(rng(1, 9)), 2, 1),
        S("Fill in the buddy", None, "eq3", buddy_eqs(), 6, 1),
        S("Are they Ten Buddies?", "Circle yes or no.", "buddy_yesno",
          [(f"{a} and {b}", a + b == 10) for a in rng(1, 9) for b in rng(1, 9)], 4, 1),
        S("Ten and some more", None, "teen", [(f"10 + {n} = [{10 + n}]", n) for n in rng(1, 9)], 2, 2),
        S("Teen numbers", None, "eq3", teen_eqs(), 6, 2),
        S("Find the buddies first, then add", None, "three",
          [(a, 10 - a, c) for a in rng(1, 9) for c in rng(1, 9)] + [(c, a, 10 - a) for a in rng(1, 9) for c in rng(1, 9)],
          2, 2),
        S("Word problems", None, "word", stories("kw", "add", ADD9)[:6] + stories("kw2", "sub", SUB9)[:6]
          + stories("kw3", "make10", rng(1, 9)), 3, "0–2"),
    ]),
    ("grade-1", "Grade 1", "Packets 3–9", [
        S("Break it apart", None, "ba", OVER10, 2, 3),
        S("Over ten", None, "eq3", eqs(OVER10_ANY, "+"), 6, 3),
        S("Up to the next ten, then over", None, "ladder", NEXT10, 2, 4),
        S("Over the next ten", None, "eq3", eqs(NEXT10, "+"), 6, 4),
        S("Jump through ten", None, "jump", TEEN_SUB, 2, 5),
        S("Back through ten", None, "eq3", eqs(TEEN_SUB, "-"), 6, 5),
        S("Near doubles with dots", None, "near_dots", [(n, n + 1) for n in rng(2, 9)], 2, 6),
        S("Doubles and near doubles", None, "eq3", eqs([(n, n) for n in rng(2, 10)] + NEAR, "+"), 6, 6),
        S("Count the tens and ones", None, "count_to", [n for n in TWO_DIG if n < 70], 2, 7),
        S("Tens and ones", None, "eq2", [f"[{n // 10}] tens [{n % 10}] ones = {n}" for n in TWO_DIG]
          + [f"{n // 10} tens {n % 10} ones = [{n}]" for n in TWO_DIG], 4, 7),
        S("Which is more?", "Circle the bigger number.", "which_more",
          [(a, b) for a in TWO_DIG for b in TWO_DIG if a // 10 != b // 10][:500], 2, 7),
        S("10 less and 10 more", None, "side", [n for n in TWO_DIG if n < 90], 2, 8),
        S("Ten more, ten less", None, "eq3", eqs([(n, 10) for n in TWO_DIG if n < 90], "+")
          + eqs([(n, 10) for n in TWO_DIG], "-"), 6, 8),
        S("Split it", "Fill in every box.", "add_split", TWO_ADD_NO + TWO_ADD_NEW, 2, 9),
        S("Adding two-digit numbers", None, "eq3", eqs(TWO_ADD_NO + TWO_ADD_NEW, "+"), 6, 9),
        S("Word problems", None, "word", stories("g1a", "add", OVER10)[:6] + stories("g1b", "sub", TEEN_SUB)[:6]
          + stories("g1c", "tens", TWO_DIG)[:6] + stories("g1d", "add", TWO_ADD_NEW)[:6], 4, "3–9"),
    ]),
    ("grade-2", "Grade 2", "Packets 10–32", [
        S("Enough ones?", "Circle yes or no. Don’t solve it.", "enough", TWO_SUB_NO + TWO_SUB_BRK, 2, 10),
        S("Subtracting two-digit numbers", None, "eq3", eqs(TWO_SUB_NO, "-"), 3, 10),
        S("Jump up", "Fill in the jumps. Add them up.", "jump_up", [(a, a + b) for a, b in TWO_ADD_NEW], 1, 11),
        S("Missing numbers", None, "eq3", [f"{a} + [{b}] = {a + b}" for a, b in OVER10 + TWO_ADD_NEW], 3, 11),
        S("Break a ten", None, "break_ten", TWO_DIG, 2, 12),
        S("Subtracting with borrowing", None, "eq3", eqs(TWO_SUB_BRK, "-"), 3, 12),
        S("Adding in columns", None, "col_add", TWO_ADD_NEW, 5, 13),
        S("Subtracting in columns", None, "col_sub", TWO_SUB_BRK + TWO_SUB_NO, 5, 14),
        S("Count them", None, "count_hto", [n for n in THREE_DIG if n < 400 and n // 10 % 10 <= 5 and n % 10 <= 6], 2, 15),
        S("What is it worth?", None, "worth", [(n, int(str(n)[i])) for n in THREE_DIG for i in range(3)
                                              if len(set(str(n))) == 3], 2, 15),
        S("Write the number", None, "eq2", [f"{n // 100} hundreds {n // 10 % 10} tens {n % 10} ones = [{n}]"
                                            for n in THREE_DIG] + [f"{n // 100 * 100} + {n // 10 % 10 * 10} + {n % 10} = [{n}]"
                                                                   for n in THREE_DIG], 2, 15),
        S("Skip counting", "Fill in the missing numbers.", "seq",
          [(s, st, (1, 3)) for st in (5, 10, 100) for s in rng(5, 400) if s % 5 == 0], 4, 16),
        S("Comparing numbers", "Write <, > or =.", "eq3", compare_eqs([(a, b) for a in THREE_DIG[::5]
                                                                       for b in THREE_DIG[::9] if a != b][:3000]), 6, 17, balance=is_less),
        S("10 or 100 more or less", None, "eq3", [E(n, op, d) for n in THREE_DIG[::3] for d in (10, 100)
                                                   for op in "+-" if n - d > 0 and n + d < 1000], 6, 18),
        S("Adding three-digit numbers", None, "col_add3", THREE_ADD, 4, 19),
        S("Subtracting three-digit numbers", None, "col_sub3", THREE_SUB, 4, 20),
        S("Arrays", None, "array", [(r, c) for r in rng(2, 5) for c in rng(2, 5)], 2, 21),
        S("Equal groups", None, "eq2", [f"{r} rows of {c} = [{r * c}]" for r in rng(2, 5) for c in rng(2, 5)]
          + [" + ".join([str(n)] * g) + f" = [{n * g}]" for g in rng(2, 5) for n in rng(2, 5)], 2, 21),
        S("Even or odd?", "Write even or odd.", "eo_word", list(rng(11, 299)), 6, 22),
        S("Word problems", None, "word", stories("g2a", "sub", TWO_SUB_BRK)[:6] + stories("g2b", "add", THREE_ADD)[:6]
          + stories("g2c", "groups", [(g, n) for g in rng(3, 5) for n in rng(3, 5)])[:6]
          + stories("g2d", "compare", [(a + b, a) for a, b in TWO_ADD_NEW])[:6], 4, "10–22"),
    ]),
]


# ---------------------------------------------------------------------- building them

def score_tag(bk, total):
    """Top right of the first page: a score line, or the mastery bar on the key."""
    c = bk.c
    if bk.key:
        need = -(-total * 4 // 5)
        c.setFillColor(T.answer)
        c.setFont("AvD", 11)
        c.drawRightString(W - M, H - 103, f"Mastery: {need} of {total} (80%)")
    else:
        c.setFillColor(T.text2)
        c.setFont("Av", 11)
        c.drawRightString(W - M, H - 103, f"Score: _______ / {total}")


def spread(items):
    """Reorder equations so no two in a row start with the same number."""
    if not items or not isinstance(items[0], str):
        return items
    first = lambda t: re.match(r"\[?(\d+)", t).group(1) if re.match(r"\[?(\d+)", t) else t
    rest, out = list(items), []
    while rest:
        k = next((i for i, t in enumerate(rest) if not out or first(t) != first(out[-1])), 0)
        out.append(rest.pop(k))
    return out


def place_sections(bk, title, y, picked, record=None):
    """Draws each section's cards. record (a list) gets one entry per problem, in number order, for
    curriculum.json: (section, item, answers written in its boxes)."""
    num = 1
    for i, (s, items) in enumerate(picked):
        kind = KINDS[s.kind]

        def draw(x, cy, w, it, k=kind, s=s):
            bk.rec = [] if record is not None else None
            k.draw(bk, x, cy, w, it)
            if record is not None:
                record.append((s, it, bk.rec))
            bk.rec = None
        y, num = flow(bk, title, y, i + 1, s.name, s.sub, spread(items), num, kind.cols, kind.h, kind.gap, draw)
    return y


def build_check_in(packet, ink_folder, key, picker, manifest=None, into=None):
    """The Check-In as its own PDF. into = the packet's open Book: the same Check-In is also added at the end
    of the packet (or of its answer key), so it prints with the packet."""
    folder, slug, name = packet[:3]
    sections = CHECKINS[folder]
    path = ROOT / folder / ink_folder / f"{slug}-check-in{'-key' if key else ''}.pdf"
    bk = Book(path, key, subtitle=f"{name} Check-In", asked={})
    bk.c.setTitle(f"{name}: Check-In" + (" Answer Key" if key else ""))
    doc = set()
    picked = [(s, picker.pick(s.kind, s.pool, s.count, doc)) for s in sections]
    total = sum(len(items) for _, items in picked)
    title = f"Check-In: {name}"
    record = [] if manifest is not None else None
    for target, rec in ((bk, record), (into, None)):
        if target is None:
            continue
        first = target.page
        asked, target.asked = target.asked, {}  # the packet's no-repeat registry doesn't apply to its Check-In
        target.subtitle = f"{name} Check-In"  # the header names the Check-In, as in its own PDF
        y = target.new_page(title, "Show what you know. No help this time.", footer=f"WeMath  ·  {name} Check-In")
        score_tag(target, total)
        place_sections(target, title, y, picked, rec)
        target.asked = asked
        if target is bk and bk.page - first > 1:
            print(f"WARNING: {folder} check-in runs onto {bk.page - first} pages")
    bk.save()
    if record is not None:
        manifest.append(manifest_entry(f"check-in:{folder.split('-', 1)[1]}", "check-in", f"{name} Check-In",
                                       record, packet=int(folder.split("-")[0]),
                                       file=f"{folder}/color/{slug}-check-in-key.pdf"))
    return path


def build_assessment(grade, when, ink_folder, key, picker, manifest=None):
    slug, name, packets, sections = grade
    path = ROOT / "assessments" / ink_folder / f"{slug}-{when}-assessment{'-key' if key else ''}.pdf"
    label_ = "Pre-Assessment" if when == "pre" else "Post-Assessment"
    bk = Book(path, key, subtitle=f"{name} {label_}", asked={})
    bk.c.setTitle(f"{name} {label_}" + (": Answer Key" if key else ""))
    doc = set()
    picked = [(s, picker.pick(s.kind, s.pool, s.count, doc)) for s in sections]
    total = sum(len(items) for _, items in picked)
    title = f"{name} {label_}"
    goal = ("Do your best. It’s okay to skip a problem you don’t know yet." if when == "pre"
            else "Show everything you learned this year.")
    y = bk.new_page(title, goal, footer=f"WeMath  ·  {name} {label_}  ·  {packets}")
    score_tag(bk, total)
    record = [] if manifest is not None else None
    place_sections(bk, title, y, picked, record)
    if key:
        scoring_sheet(bk, title, picked, total, when)
    bk.save()
    if record is not None:
        manifest.append(manifest_entry(f"{slug}-{when}", when, title, record, grade=GRADE_CODE[slug],
                                       file=f"assessments/color/{slug}-{when}-assessment-key.pdf"))
    return path


def scoring_sheet(bk, title, picked, total, when):
    """Answer key only: a table of parts, the packet each one checks, and a box for the score."""
    y = bk.new_page(f"{title}: Scoring", "Count correct answers in each part. Each problem is 1 point.",
                    name_line=False)
    c = bk.c
    cols = [M, M + 44, M + 300, M + 380, M + 450]
    c.setFillColor(T.text2)
    c.setFont("AvD", 10)
    for x_, head in zip(cols, ["Part", "Skill", "Packet", "Problems", "Score"]):
        c.drawString(x_, y, head)
    y -= 8
    num = 1
    pitch = min(24, (y - 150) / len(picked))  # tighter rows when there are many parts, so it stays on one page
    for i, (s, items) in enumerate(picked):
        c.setStrokeColor(T.line)
        c.setLineWidth(0.6)
        c.line(M, y, W - M, y)
        y -= pitch * 17 / 24
        c.setFillColor(T.ink)
        c.setFont("AvM", 10.5)
        c.drawString(cols[0], y, str(i + 1))
        c.drawString(cols[1], y, s.name)
        c.drawString(cols[2], y, str(s.packet))
        c.drawString(cols[3], y, f"{num}–{num + len(items) - 1}" if len(items) > 1 else str(num))
        c.drawString(cols[4], y, f"____ / {len(items)}")
        num += len(items)
        y -= pitch * 7 / 24
    c.line(M, y, W - M, y)
    y -= 20
    c.setFont("AvB", 11)
    c.drawString(cols[1], y, "Total")
    c.drawString(cols[4], y, f"____ / {total}")
    y -= 34
    tip = ("Use the pre-assessment to place students: start each student at the first packet where they miss "
           "more than 1 problem in its parts. Skip packets they already show mastery on (all or all but one "
           "correct)." if when == "pre" else
           "Compare with the pre-assessment, part by part. A part with more than 1 miss means that packet "
           "needs a review before moving on. 80% overall shows the grade is mastered.")
    bk.paragraph(M, y, CW, tip, size=10.5, leading=15)




# ====================================================================== 23. Hundred Buddies


def hundred_grid(bk, x, y, cell, a, show_b=False):
    """A 10 × 10 grid (one hundred). The first a cells hold blue dots, filled row by row from the
    top; with show_b the rest hold orange dots (its buddy). y = bottom."""
    c = bk.c
    s = cell * 10
    c.setStrokeColor(T.muted)
    c.setLineWidth(0.5)
    for i in range(1, 10):
        c.line(x + i * cell, y, x + i * cell, y + s)
        c.line(x, y + i * cell, x + s, y + i * cell)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.2)
    c.line(x + 5 * cell, y, x + 5 * cell, y + s)
    c.rect(x, y, s, s, stroke=1, fill=0)
    for i in range(100):
        r, col = divmod(i, 10)
        kind = "a" if i < a else ("b" if show_b else None)
        if kind:
            bk.dot(x + col * cell + cell / 2, y + s - r * cell - cell / 2, cell * 0.32, kind)


def c_hgrid(bk, x, cy, w, a):
    hundred_grid(bk, x + GUT, cy + 12, 8, a, show_b=bk.key)
    bk.fit_eq(x + GUT + 94, cy + 40, w - GUT - 102, f"{a} + [{100 - a}] = 100", size=18)


def c_nines(bk, x, cy, w, a):
    """Tens make 9, ones make 10."""
    t, o = divmod(a, 10)
    c = bk.c
    for i, (lab, text) in enumerate([("tens", f"{t} + [{9 - t}] = 9"), ("ones", f"{o} + [{10 - o}] = 10")]):
        yy = cy + 74 - i * 30
        c.setFillColor(T.text2)
        c.setFont("AvD", 10)
        c.drawString(x + GUT, yy + 1, lab)
        bk.eq(x + GUT + 38, yy, text, size=15)
    c.setFillColor(T.text2)
    c.setFont("AvM", 10)
    c.drawString(x + GUT, cy + 15, "so")
    bk.fit_eq(x + GUT + 22, cy + 14, w - GUT - 30, f"{a} + [{100 - a}] = 100", size=18)


def learn_hundred_buddies(bk):
    y = bk.new_page("Hundred Buddies", "Two numbers that make 100.", name_line=False, big=True,
                    footer="WeMath  ·  Hundred Buddies")
    c = bk.c
    label(bk, M, y - 6, "64 and 36 fill the hundred")
    hundred_grid(bk, M + 14, y - 140, 12, 64, show_b=True)
    color_eq(bk, M + 160, y - 62, [("64", "a"), ("+", "op"), ("36", "b"), ("=", "op"), ("100", None)], 34)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 160, y - 92, "6 full rows and 4 more is 64.")
    c.drawString(M + 160, y - 110, "The rest is 36. Together they fill all 100.")
    y -= 160

    label(bk, M, y - 6, "Jump up: 64 to 70 is 6. 70 to 100 is 30.")
    jump_up(bk, M + 40, y - 84, [64, 70, 100], 120, size=24, H=30, r=15, vsize=16, example=True)
    color_eq(bk, M + 330, y - 66, [("6", "b"), ("+", "op"), ("30", "b"), ("=", "op"), ("36", None)], 28)
    y -= 112

    label(bk, M, y - 6, "Quick check: the tens make 9, the ones make 10")
    for i, (num, buddy) in enumerate([("64", "36")]):
        color_eq(bk, M + 30, y - 46, [("6", "a"), ("4", "b", "tight")], 30)
        color_eq(bk, M + 30, y - 80, [("3", "a"), ("6", "b", "tight")], 30)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.2)
    c.line(M + 26, y - 88, M + 74, y - 88)
    color_eq(bk, M + 130, y - 50, [("tens:", None), ("6", "a"), ("+", "op"), ("3", "a"), ("=", "op"), ("9", None)], 20)
    color_eq(bk, M + 130, y - 82, [("ones:", None), ("4", "b"), ("+", "op"), ("6", "b"), ("=", "op"), ("10", None)], 20)
    y -= 108

    bottom = your_turn(bk, y, h=110)
    bk.ask("45 + [] = 100")
    hundred_grid(bk, M + 120, bottom + 12, 8.5, 45, show_b=bk.key)
    bk.eq(M + 250, bottom + 44, "45 + [55] = 100", size=24)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: say the buddy of any number to 100 quickly. Jump up to the next ten, then up to 100. "
                     "Check: the tens add to 9 and the ones add to 10 (unless the ones are 0: 30 + 70). "
                     "Buddies of 100 make change from a dollar later.")


def practice_hundred_buddies(bk):
    title = "Hundred Buddies: Practice"
    y = bk.new_page(title, "Find the buddy that makes 100.")
    num = 1
    y, num = flow(bk, title, y, 1, "Fill the hundred", "Count the blue dots. How many more fill the hundred?",
                  [58, 33, 81, 24, 62, 17], num, 2, 100, 10, lambda x, cy, w, a: (bk.ask(f"{a} + [] = 100"),
                                                                              c_hgrid(bk, x, cy, w, a)))
    y, num = flow(bk, title, y, 2, "Tens buddies", "Ten buddies, but with tens.",
                  [f"{a} + [{100 - a}] = 100" for a in (30, 80, 10, 60, 90, 40, 20, 70, 50)], num, 3, 42, 8,
                  lambda x, cy, w, t: (bk.ask(t), c_eq(bk, x, cy, w, t)))
    y, num = flow(bk, title, y, 3, "Jump up to 100", "Jump to the next ten, then to 100. Add the jumps.",
                  [(37, 100), (52, 100), (19, 100), (76, 100)], num, 2, 152, 10,
                  lambda x, cy, w, it: (bk.ask(f"{it[0]} + [] = 100"), c_jump_up(bk, x, cy, w, it)))
    y, num = flow(bk, title, y, 4, "Find the stop", "Write the ten you jump to.",
                  [(68, 100), (41, 100), (85, 100), (14, 100)], num, 2, 152, 10,
                  lambda x, cy, w, it: (bk.ask(f"{it[0]} + [] = 100"), c_jump_up(bk, x, cy, w, it, given=False)))
    y, num = flow(bk, title, y, 5, "Tens make 9, ones make 10", "Find each buddy, then the buddy of 100.",
                  [53, 29, 74, 92, 38, 65], num, 2, 104, 10,
                  lambda x, cy, w, a: (bk.ask(f"{a} + [] = 100"), c_nines(bk, x, cy, w, a)))
    plain = lambda x, cy, w, t: (bk.ask(t), c_eq(bk, x, cy, w, t))
    y, num = flow(bk, title, y, 6, "Buddies of 100", "No help this time.",
                  ["27 + [73] = 100", "[44] + 56 = 100", "16 + [84] = 100", "89 + [11] = 100", "[63] + 37 = 100",
                   "42 + [58] = 100", "[75] + 25 = 100", "31 + [69] = 100", "98 + [2] = 100", "[57] + 43 = 100",
                   "12 + [88] = 100", "[39] + 61 = 100"], num, 3, 42, 8, plain)
    y, num = flow(bk, title, y, 7, "Buddies of 50", "No help this time. Jump to the next ten, then to 50.",
                  ["35 + [15] = 50", "12 + [38] = 50", "[26] + 24 = 50", "41 + [9] = 50", "18 + [32] = 50",
                   "[44] + 6 = 50", "27 + [23] = 50", "33 + [17] = 50", "[15] + 35 = 50"], num, 3, 42, 8, plain)
    y, num = flow(bk, title, y, 8, "Buddies of 1000", "No help this time. The hundreds make 9, the tens make 10.",
                  ["400 + [600] = 1000", "750 + [250] = 1000", "[300] + 700 = 1000", "850 + [150] = 1000",
                   "620 + [380] = 1000", "[900] + 100 = 1000", "550 + [450] = 1000", "180 + [820] = 1000",
                   "[350] + 650 = 1000"], num, 3, 42, 8, plain)
    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Jump up to 100.")
    words(bk, y, [
        ("A snack costs 65 cents. You pay with a dollar, which is 100 cents. How much change do you get?",
         "65 + 35 = 100", "35", "cents"),
        ("A game ends at 100 points. Mia has 72 points. How many more points does she need?",
         "72 + 28 = 100", "28", "points"),
        ("A jar holds 50 marbles. It has 34 marbles in it. How many more marbles will fill the jar?",
         "34 + 16 = 50", "16", "marbles"),
        ("The class wants to collect 100 cans. They have 58 cans. How many more cans do they need?",
         "58 + 42 = 100", "42", "cans"),
        ("Challenge: You have 100 cents. You spend 25 cents, then 40 cents. How many cents are left?",
         "25 + 40 + 35 = 100", "35", "cents"),
    ], num)


# ====================================================================== 24. Counting Forward and Backward


def c_direction(bk, x, cy, w, seq):
    step = seq[1] - seq[0]
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("Rnd", 16)
    c.drawString(x + GUT, cy + 16, ",  ".join(map(str, seq)))
    bx = x + GUT + 210
    c.setFillColor(T.text2)
    c.setFont("AvD", 12)
    c.drawString(bx, cy + 17, "Count")
    bk.box(bx + 42, cy + 8, 78, 28, "forward" if step > 0 else "back", size=14)
    c.setFillColor(T.text2)
    c.setFont("AvD", 12)
    c.drawString(bx + 128, cy + 17, "by")
    bk.box(bx + 148, cy + 8, 46, 28, abs(step), size=16)


def countby_key(n):
    def key(it):
        start, step, blanks = it
        seq = [start + step * i for i in range(n)]
        return f"count by {step} from {start}: {', '.join(str(seq[i]) for i in blanks)}"
    return key


def learn_counting(bk):
    y = bk.new_page("Counting Forward and Backward", "Count by any number, from any number, either way.",
                    name_line=False, big=True, footer="WeMath  ·  Counting Forward and Backward")
    label(bk, M, y - 6, "Count forward by 3s")
    count_chain(bk, M + 26, y - 74, [4, 7, 10, 13, 16, 19], step="+3", spacing=84, size=24)
    y -= 104
    label(bk, M, y - 6, "Count backward by 2s")
    count_chain(bk, M + 26, y - 74, [20, 18, 16, 14, 12, 10], step="−2", spacing=84, size=24)
    y -= 104
    label(bk, M, y - 6, "Count by 25s, like quarters: 25 cents each")
    count_chain(bk, M + 26, y - 74, [25, 50, 75, 100, 125, 150], step="+25", spacing=84, size=24)
    y -= 104
    bottom = your_turn(bk, y, h=100)
    bk.ask("count by -4 from 30: 22, 18, 14")
    count_chain(bk, M + 140, bottom + 26, [30, 26, 22, 18, 14], blanks=(2, 3, 4), step="−4", spacing=74, size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: count from any number, by any number, forward and backward, in your head. Say it "
                     "out loud while pointing at each jump. Counting by 3s, 4s and 25s gets kids ready for "
                     "multiplication and money.")


def practice_counting(bk):
    title = "Counting Forward and Backward: Practice"
    y = bk.new_page(title, "Jump by the same amount each time.")
    num = 1
    chain = lambda x, cy, w, it: (bk.ask(countby_key(7)(it)), c_chain(bk, x, cy, w, it))
    y, num = flow(bk, title, y, 1, "Forward by 2s, 3s and 4s", "Fill in the next numbers.",
                  [(5, 3, (3, 4, 5, 6)), (12, 4, (2, 4, 5, 6)), (21, 2, (3, 4, 5, 6)), (40, 3, (2, 3, 5, 6)),
                   (8, 4, (3, 4, 5, 6)), (63, 2, (2, 4, 5, 6))], num, 1, 64, 8, chain)
    y, num = flow(bk, title, y, 2, "Backward", "Jump back each time. The numbers get smaller.",
                  [(30, -2, (3, 4, 5, 6)), (50, -5, (2, 3, 5, 6)), (95, -10, (3, 4, 5, 6)), (27, -3, (2, 4, 5, 6)),
                   (40, -4, (3, 4, 5, 6)), (64, -2, (2, 3, 5, 6))], num, 1, 64, 8, chain)
    y, num = flow(bk, title, y, 3, "By 25s", "25, 50, 75, 100 … like counting quarters.",
                  [(25, 25, (3, 4, 5, 6)), (200, -25, (2, 3, 5, 6)), (75, 25, (2, 4, 5, 6)),
                   (300, -25, (3, 4, 5, 6))], num, 1, 64, 8, chain)
    y, num = flow(bk, title, y, 4, "Across a hundred", "Keep going past 100, or back below it.",
                  [(88, 3, (3, 4, 5, 6)), (112, -4, (2, 3, 5, 6)), (93, 2, (3, 4, 5, 6)), (106, -3, (2, 4, 5, 6))],
                  num, 1, 64, 8, chain)
    y, num = flow(bk, title, y, 5, "Forward or backward?", "Which way? By how much?",
                  [[3, 6, 9, 12], [40, 36, 32, 28], [50, 45, 40, 35], [11, 13, 15, 17], [100, 75, 50, 25],
                   [22, 25, 28, 31]], num, 1, 44, 8,
                  lambda x, cy, w, s: (bk.ask(f"direction: {'-'.join(map(str, s))}"), c_direction(bk, x, cy, w, s)))
    seq = lambda x, cy, w, it: (bk.ask(countby_key(5)(it)), c_seq(bk, x, cy, w, it))
    y, num = flow(bk, title, y, 6, "Count forward", "No help this time.",
                  [(6, 3, (2, 4)), (14, 4, (1, 3)), (35, 5, (2, 3)), (9, 2, (3, 4)), (50, 25, (1, 4)), (17, 3, (2, 4)),
                   (72, 4, (1, 3)), (110, 10, (2, 3))], num, 2, 46, 8, seq)
    y, num = flow(bk, title, y, 7, "Count backward", "No help this time.",
                  [(20, -2, (2, 4)), (45, -5, (1, 3)), (33, -3, (2, 3)), (28, -4, (3, 4)), (100, -10, (1, 4)),
                   (150, -25, (2, 4)), (61, -2, (1, 3)), (39, -3, (2, 3))], num, 2, 46, 8, seq)
    y, num = flow(bk, title, y, 8, "Jumps in your head", "No help this time. Count the jumps.",
                  ["5 + 3 + 3 + 3 = [14]", f"40 {MINUS} 4 {MINUS} 4 {MINUS} 4 = [28]", "25 + 25 + 25 = [75]",
                   "9 + 2 + 2 + 2 + 2 = [17]", f"50 {MINUS} 5 {MINUS} 5 {MINUS} 5 = [35]",
                   f"100 {MINUS} 25 {MINUS} 25 = [50]", "12 + 4 + 4 + 4 = [24]",
                   f"30 {MINUS} 3 {MINUS} 3 {MINUS} 3 {MINUS} 3 = [18]"], num, 2, 42, 8,
                  lambda x, cy, w, t: (bk.ask(t), c_eq(bk, x, cy, w, t)))
    y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Count forward or backward.")
    words(bk, y, [
        ("A frog sits on step 2. It hops up 3 steps at a time. What step is it on after 4 hops?",
         "2, 5, 8, 11, 14", "14", ""),
        ("A jar has 40 cookies. Each day 5 cookies are eaten. How many cookies are left after 3 days?",
         "40, 35, 30, 25", "25", "cookies"),
        ("You have 3 quarters. A quarter is 25 cents. How many cents do you have?", "25, 50, 75", "75", "cents"),
        ("Sam has 30 stickers. He gives 4 stickers to each of 3 friends. How many stickers does he have left?",
         "30, 26, 22, 18", "18", "stickers"),
        ("Challenge: Count back by 3s from 50. What is the first number you say that is less than 40?",
         "50, 47, 44, 41, 38", "38", ""),
    ], num)


# ====================================================================== 25. Halves


def half_str(n):
    whole = str(n // 2) if n // 2 or n % 2 == 0 else ""
    return whole + ("\u00bd" if n % 2 else "")


def half_cut(bk, cx, cy, s):
    """A dashed line down the middle of an object: it is cut in half."""
    c = bk.c
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.3)
    c.setDash(2.5, 2)
    c.line(cx, cy - s * 0.55, cx, cy + s * 0.55)
    c.setDash()


def plates(bk, x, y, w, h, kind, n_each, s=13):
    """Two plates side by side; on the key each shows n_each objects. y = bottom."""
    c = bk.c
    for i in range(2):
        px = x + i * (w + 14)
        c.setStrokeColor(T.muted)
        c.setLineWidth(1)
        c.ellipse(px, y, px + w, y + h, stroke=1, fill=0)
        if bk.key:
            k = min(n_each, 5)
            step = s + 3
            x0 = px + w / 2 - (k - 1) * step / 2
            for j in range(n_each):
                r, col = divmod(j, 5)
                icon(bk, kind, x0 + col * step, y + h / 2 + (6 if n_each > 5 else 0) - r * 13, s)


def c_share(bk, x, cy, w, item):
    kind, n = item
    objects(bk, kind, x + GUT, cy + 122, n, s=18, step=21, per_row=10 if n <= 6 else 5)
    plates(bk, x + GUT, cy + 40, 88, 34, kind, n // 2)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"half of {n} = [{n // 2}]", size=17)


def c_half_double(bk, x, cy, w, n):
    dot_pair(bk, x + GUT, cy + 92, n, n, r=5, step=14)
    bk.eq(x + GUT, cy + 44, f"double {n} = {2 * n}", size=16, color=T.text2)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvM", 10)
    bk.c.drawString(x + GUT, cy + 15, "so")
    bk.fit_eq(x + GUT + 22, cy + 14, w - GUT - 30, f"half of {2 * n} = [{n}]", size=18)


def c_half_tens(bk, x, cy, w, n):
    """Ten-sticks split down the middle by a dashed line (it cuts a stick when the tens are odd)."""
    t = n // 10
    sw_, gap = 10, 5
    for i in range(t):
        ten_stick(bk, x + GUT + i * (sw_ + gap), cy + 80, 38, sw_)
    mid = x + GUT + (t * (sw_ + gap) - gap) / 2
    c = bk.c
    c.setStrokeColor(T.accent)
    c.setLineWidth(1.6)
    c.setDash(3, 2.5)
    c.line(mid, cy + 74, mid, cy + 124)
    c.setDash()
    bk.fit_eq(x + GUT, cy + 46, w - GUT - 10, f"half of {n - 10} = [{(n - 10) // 2}] and half of 10 = [5]", size=14)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"half of {n} = [{n // 2}]", size=18)


def c_half_split(bk, x, cy, w, n):
    tens, o = n // 10 * 10, n % 10
    bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"half of {n} = [{n // 2}]", size=18)
    rows = [("tens", f"half of {tens} = [{tens // 2}]"), ("ones", f"half of {o} = [{o // 2}]"),
            ("total", f"[{tens // 2}] + [{o // 2}] = [{n // 2}]")]
    for i, (lab, text) in enumerate(rows):
        yy = cy + 66 - i * 27
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 10)
        bk.c.drawString(x + GUT, yy + 1, lab)
        bk.eq(x + GUT + 38, yy, text, size=13)


def c_half_odd(bk, x, cy, w, item):
    kind, n = item
    s, step = 24, 29
    objects(bk, kind, x + GUT, cy + 84, n, s=s, step=step, per_row=5)
    r, col = divmod(n - 1, 5)
    half_cut(bk, x + GUT + s / 2 + col * step, cy + 84 - s / 2 - r * step, s)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"half of {n} = [{half_str(n)}]", size=18)


def learn_halves(bk):
    y = bk.new_page("Halves", "Half means 2 parts the same.", name_line=False, big=True,
                    footer="WeMath  ·  Halves")
    c = bk.c
    label(bk, M, y - 6, "Share fairly: 6 cookies, 2 plates")
    objects(bk, "cookie", M + 14, y - 26, 6, s=28, step=33, per_row=6)
    bk.arrow(M + 214, y - 40, M + 250, y - 40)
    for i in range(2):
        px = M + 264 + i * 112
        c.setStrokeColor(T.muted)
        c.setLineWidth(1)
        c.ellipse(px, y - 62, px + 100, y - 18, stroke=1, fill=0)
        for j in range(3):
            icon(bk, "cookie", px + 22 + j * 28, y - 40, 22)
    color_eq(bk, M + 14, y - 96, [("half", None), ("of", None), ("6", "a"), ("=", "op"), ("3", "b")], 28)
    y -= 120

    label(bk, M, y - 6, "Half undoes double")
    dot_pair(bk, M + 20, y - 30, 4, 4, r=7, step=19)
    color_eq(bk, M + 160, y - 38, [("double", None), ("4", "b"), ("=", "op"), ("8", "a")], 24)
    color_eq(bk, M + 160, y - 70, [("half", None), ("of", None), ("8", "a"), ("=", "op"), ("4", "b")], 24)
    y -= 96

    label(bk, M, y - 6, "Big numbers: half the tens, half the ones")
    color_eq(bk, M + 14, y - 40, [("half", None), ("of", None), ("46", "a"), ("=", "op"), ("20", "b"),
                                  ("+", "op"), ("3", "b"), ("=", "op"), ("23", None)], 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 14, y - 64, "Half of 40 is 20. Half of 6 is 3.")
    y -= 86

    label(bk, M, y - 6, "Odd numbers: cut one in half")
    objects(bk, "cookie", M + 14, y - 22, 7, s=28, step=33, per_row=7)
    half_cut(bk, M + 14 + 14 + 6 * 33, y - 36, 28)
    color_eq(bk, M + 280, y - 44, [("half", None), ("of", None), ("7", "a"), ("=", "op"), ("3½", "b")], 26)
    y -= 72

    bottom = your_turn(bk, y, h=100)
    bk.ask("share: candy 10")
    objects(bk, "candy", M + 120, bottom + 82, 10, s=20, step=24, per_row=10)
    bk.eq(M + 120, bottom + 20, "half of 10 = [5]", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: half means 2 parts the same. Share real snacks fairly first. Ask both ways: "
                     "\u201chalf of 8?\u201d and \u201chalf of what is 4?\u201d Big numbers: half the tens, half the "
                     "ones. Odd numbers leave a half: half of 7 is 3\u00bd.")


def practice_halves(bk):
    title = "Halves: Practice"
    y = bk.new_page(title, "Half means 2 parts the same.")
    num = 1
    y, num = flow(bk, title, y, 1, "Share fairly", "Draw the same number on each plate.",
                  [("apple", 8), ("star", 4), ("cupcake", 10), ("fish", 6), ("ladybug", 2), ("egg", 8)], num, 2, 130,
                  10, lambda x, cy, w, it: (bk.ask(f"share: {it[0]} {it[1]}"), c_share(bk, x, cy, w, it)))
    y, num = flow(bk, title, y, 2, "Half undoes double", "Two rows the same. Half is one row.",
                  [7, 5, 9, 3, 8, 6], num, 2, 110, 10,
                  lambda x, cy, w, n: (bk.ask(f"half double {n}"), c_half_double(bk, x, cy, w, n)))
    y, num = flow(bk, title, y, 3, "Half of tens", "An odd number of tens? Cut one ten in half: half of 10 is 5.",
                  [30, 50, 70, 90], num, 2, 132, 10,
                  lambda x, cy, w, n: (bk.ask(f"half of {n} = []"), c_half_tens(bk, x, cy, w, n)))
    y, num = flow(bk, title, y, 4, "Split it", "Half the tens. Half the ones. Put them together.",
                  [46, 68, 84, 26, 34, 56, 72, 58], num, 2, 122, 10,
                  lambda x, cy, w, n: (bk.ask(f"half of {n} = []"), c_half_split(bk, x, cy, w, n)))
    y, num = flow(bk, title, y, 5, "Halves of odd numbers", "Cut the last one in half.",
                  [("cookie", 5), ("apple", 9), ("cupcake", 3), ("candy", 7)], num, 2, 100, 10,
                  lambda x, cy, w, it: (bk.ask(f"half pic: {it[0]} {it[1]}"), c_half_odd(bk, x, cy, w, it)))
    plain = lambda x, cy, w, t: (bk.ask(t), c_eq(bk, x, cy, w, t))
    y, num = flow(bk, title, y, 6, "Half of what?", "Think: double it.",
                  [f"half of [{2 * n}] = {n}" for n in (7, 10, 8, 15, 25, 9, 50, 20, 11)], num, 3, 42, 8, plain)
    y, num = flow(bk, title, y, 7, "Half of", "No help this time.",
                  [f"half of {n} = [{n // 2}]" for n in (14, 20, 16, 80, 40, 62, 48, 96, 24, 100, 88, 36)],
                  num, 3, 42, 8, plain)
    y, num = flow(bk, title, y, 8, "Odd numbers", "No help this time. There is a half left over.",
                  [f"half of {n} = [{half_str(n)}]" for n in (9, 15, 3, 11, 25, 19, 13, 21, 17)], num, 3, 42, 8, plain)
    y, num = flow(bk, title, y, 9, "Big halves", "No help this time.",
                  [f"half of {n} = [{n // 2}]" for n in (200, 500, 300, 1000, 400, 700, 150, 900, 60)],
                  num, 3, 42, 8, plain)
    y = bk.new_page(title, first=False)
    y = bk.part(y, 10, "Word problems", "Share it fairly.")
    words(bk, y, [
        ("Mom cuts a pizza into 8 slices. You eat half of them. How many slices do you eat?",
         "half of 8 = 4", "4", "slices"),
        ("Two friends share 14 grapes fairly. How many grapes does each friend get?", "half of 14 = 7", "7", "grapes"),
        ("There are 30 kids in a class. Half of them go outside to play. How many kids go outside?",
         "half of 30 = 15", "15", "kids"),
        ("Ben has 9 apples. He gives half of them to Mia. How many apples does Mia get?",
         "half of 9 = 4½", "4½", "apples"),
        ("Challenge: Half the cookies are eaten, then half of the rest. Now 3 are left. How many were there?",
         "3 + 3 = 6, 6 + 6 = 12", "12", "cookies"),
    ], num)


# ---------------------------------------------------------------------- check-ins and assessment parts for 23-25

KINDS.update({
    "hgrid": Kind(100, 2, lambda a: f"{a} + [] = 100", c_hgrid),
    "nines": Kind(104, 2, lambda a: f"{a} + [] = 100", c_nines),
    "chain_any": Kind(64, 1, countby_key(7), lambda bk, x, cy, w, it: c_chain(bk, x, cy, w, it), 8),
    "seq_any": Kind(46, 2, countby_key(5), lambda bk, x, cy, w, it: c_seq(bk, x, cy, w, it), 8),
    "direction": Kind(44, 1, lambda s: f"direction: {'-'.join(map(str, s))}", c_direction, 8),
    "share": Kind(130, 2, lambda it: f"share: {it[0]} {it[1]}", c_share),
    "half_double": Kind(110, 2, lambda n: f"half double {n}", c_half_double),
    "half_split": Kind(122, 2, lambda n: f"half of {n} = []", c_half_split),
    "half_odd": Kind(100, 2, lambda it: f"half pic: {it[0]} {it[1]}", c_half_odd),
})

NOT_TENS = [n for n in rng(11, 89) if n % 10]
COUNT_ANY = ([(s, st, (3, 4, 5, 6)) for st in (2, 3, 4, 25) for s in rng(3, 75)]
             + [(s, -st, (3, 4, 5, 6)) for st in (2, 3, 4, 5, 10, 25) for s in rng(40, 200) if s - 6 * st >= 0])
SEQ_ANY = [(s, st, (1, 3)) for st in (2, 3, 4, -2, -3, -4, -5, -10, 25, -25) for s in rng(30, 150)
           if s + 4 * st >= 0]
DIRECTIONS = [[s + st * i for i in range(4)] for st in (2, 3, 4, 5, -2, -3, -4, -5, 25, -25) for s in rng(30, 120, 7)
              if s + 3 * st > 0]
HALF_EVEN = [f"half of {n} = [{n // 2}]" for n in list(rng(4, 98, 2)) + [120, 140, 160, 180, 200, 300, 500, 700]]
HALF_ODD = [f"half of {n} = [{half_str(n)}]" for n in rng(3, 31, 2)]
HALF_OF_WHAT = [f"half of [{2 * n}] = {n}" for n in rng(3, 50)]
BUDDY100 = [f"{a} + [{100 - a}] = 100" for a in NOT_TENS] + [f"[{a}] + {100 - a} = 100" for a in NOT_TENS]
BUDDY50 = [f"{a} + [{50 - a}] = 50" for a in rng(6, 44) if a % 10]

CHECKINS.update({
    "23-hundred-buddies": [
        S("Fill the hundred", None, "hgrid", NOT_TENS, 2),
        S("Jump up to 100", "Fill in the jumps.", "jump_up", [(a, 100) for a in NOT_TENS], 2),
        S("Buddies of 100 and 50", None, "eq3", [x for pair in zip(shuf("b100", BUDDY100), shuf("b50", BUDDY50)) for x in pair], 6),
        S("Word problem", None, "word", stories("w23", "make100", NOT_TENS), 1),
    ],
    "24-counting-forward-and-backward": [
        S("Keep counting", None, "chain_any", COUNT_ANY, 2),
        S("Forward or backward?", None, "direction", DIRECTIONS, 2),
        S("Fill in the missing numbers", None, "seq_any", SEQ_ANY, 6),
    ],
    "25-halves": [
        S("Share fairly", "Draw the same number on each plate.", "share", [(k, n) for k in OBJ for n in (4, 6, 8, 10)], 2),
        S("Split it", None, "half_split", [n for n in rng(22, 98, 2) if n % 10], 2),
        S("Half of", None, "eq3", HALF_EVEN, 3),
        S("Odd numbers", None, "eq3", HALF_ODD, 3),
        S("Half of what?", None, "eq3", HALF_OF_WHAT, 3),
    ],
})

_g2 = next(g for g in GRADES if g[0] == "grade-2")[3]
_g2[-1:-1] = [
    S("Hundred buddies", None, "eq3", BUDDY100, 3, 23),
    S("Counting forward and backward", "Fill in the missing numbers.", "seq_any", SEQ_ANY, 2, 24),
    S("Halves", None, "eq3", HALF_EVEN + HALF_ODD, 3, 25),
]


# ====================================================================== 26. Halves, Thirds and Fourths (of shapes)

SHARE_NAME = {1: ("whole", "wholes"), 2: ("half", "halves"), 3: ("third", "thirds"), 4: ("fourth", "fourths"),
              5: ("fifth", "fifths"), 6: ("sixth", "sixths"), 8: ("eighth", "eighths"), 10: ("tenth", "tenths")}


def _uneven(n):
    """Cut points (0 … 1) for n parts that look almost fair but aren't."""
    wts = [1 + (0.42 if i % 3 == 0 else -0.24 if i % 3 == 1 else 0.06) for i in range(n)]
    t, out = sum(wts), [0.0]
    for w_ in wts:
        out.append(out[-1] + w_ / t)
    return out


def share_word(n, k=1):
    """share_word(3, 2) = "2 thirds"."""
    return f"{k} {SHARE_NAME[n][0 if k == 1 else 1]}"


def share_size(kind, s):
    return {"rect": (s * 1.5, s * 0.9), "tall": (s * 0.9, s * 1.3)}.get(kind, (s, s))


def share_parts(kind, x, y, s, n, equal=True):
    """Polygons for a shape cut into n parts; (x, y) = bottom-left, s = size.
    kind: circle, rect (wide, cut top to bottom), tall (cut across), square (cut top to bottom),
    hsquare (cut across), grid (square in 2 × 2), diag (square cut corner to corner).
    equal=False gives a cut that looks fair at a glance but isn't."""
    w, h = share_size(kind, s)
    if kind == "circle":
        cx, cy, r = x + s / 2, y + s / 2, s / 2

        def arc(a0, a1, k=40):
            return [(cx + r * math.cos(a0 + (a1 - a0) * i / k), cy + r * math.sin(a0 + (a1 - a0) * i / k))
                    for i in range(k + 1)]
        if n == 1:
            return [arc(0, 2 * math.pi)]
        if not equal and n == 2:  # one straight cut that misses the middle
            a = math.acos(0.42)
            return [arc(-a, a), arc(a, 2 * math.pi - a)]
        fr = [i / n for i in range(n)] if equal else {3: (0, 0.22, 0.55), 4: (0, 0.18, 0.5, 0.7)}.get(n) or _uneven(n)[:-1]
        cuts = [math.pi / 2 - 2 * math.pi * f for f in fr] + [math.pi / 2 - 2 * math.pi]
        return [[(cx, cy)] + arc(cuts[i], cuts[i + 1]) for i in range(n)]
    if kind == "grid":
        h2 = s / 2
        return [[(x + i * h2, y + j * h2), (x + (i + 1) * h2, y + j * h2), (x + (i + 1) * h2, y + (j + 1) * h2),
                 (x + i * h2, y + (j + 1) * h2)] for j in (1, 0) for i in (0, 1)]
    if kind == "diag":
        a, b, c_, d = (x, y), (x + s, y), (x + s, y + s), (x, y + s)
        if n == 2:
            return [[a, b, c_], [a, c_, d]]
        o = (x + s / 2, y + s / 2)
        return [[d, c_, o], [c_, b, o], [b, a, o], [a, d, o]]
    fr = [i / n for i in range(n + 1)] if equal else ({2: [0, .32, 1], 3: [0, .2, .55, 1], 4: [0, .15, .45, .7, 1]}.get(n)
                                                      or _uneven(n))
    if kind in ("tall", "hsquare"):  # cut across, top part first
        return [[(x, y + h * (1 - fr[i + 1])), (x + w, y + h * (1 - fr[i + 1])), (x + w, y + h * (1 - fr[i])),
                 (x, y + h * (1 - fr[i]))] for i in range(n)]
    return [[(x + w * fr[i], y), (x + w * fr[i + 1], y), (x + w * fr[i + 1], y + h), (x + w * fr[i], y + h)]
            for i in range(n)]


def _poly(c, pts):
    p = c.beginPath()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    return p


def shade(bk, pts, answer=False):
    """Fill one part: a light colour, or diagonal hatching in black-and-white."""
    c = bk.c
    fill = T.share_ans if answer else T.share
    if fill is not None:
        c.setFillColor(fill)
        c.drawPath(_poly(c, pts), stroke=0, fill=1)
        return
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    c.saveState()
    c.clipPath(_poly(c, pts), stroke=0, fill=0)
    c.setStrokeColor(T.ink)
    c.setLineWidth(0.8)
    x0, y0, span = min(xs), min(ys), (max(xs) - min(xs)) + (max(ys) - min(ys))
    t = -span
    while t < span:
        c.line(x0 + t, y0, x0 + t + span, y0 + span)
        t += 4.5
    c.restoreState()


def share_shape(bk, kind, x, y, s, n, shaded=(), equal=True, answer=(), lines=True, lw=1.6):
    """A shape cut into n parts. shaded = parts filled now; answer = parts filled only on the key.
    lines=False draws only the outline (the key adds the cuts in the answer colour). Returns (w, h)."""
    c = bk.c
    parts = share_parts(kind, x, y, s, n, equal)
    for i in shaded:
        shade(bk, parts[i])
    if bk.key:
        for i in answer:
            shade(bk, parts[i], answer=True)
    c.setLineJoin(1)
    if lines or bk.key:
        c.setStrokeColor(T.ink if lines else T.answer)
        c.setLineWidth(lw if lines else lw * 0.9)
        for pts in parts:
            c.drawPath(_poly(c, pts), stroke=1, fill=0)
    c.setStrokeColor(T.ink)
    c.setLineWidth(lw)
    c.drawPath(_poly(c, share_parts(kind, x, y, s, 1)[0]) if kind == "circle" else
               _poly(c, [(x, y), (x + share_size(kind, s)[0], y), (x + share_size(kind, s)[0], y + share_size(kind, s)[1]),
                         (x, y + share_size(kind, s)[1])]), stroke=1, fill=0)
    c.setLineJoin(0)
    return share_size(kind, s)


def circle_choice(bk, x, y, words, right, size=12, gap=10):
    """Words in a row; the key rings the right one. y = baseline. Returns the width."""
    c = bk.c
    x0 = x
    for word in words:
        ww = sw(word, "AvD", size)
        c.setFillColor(T.text2)
        c.setFont("AvD", size)
        c.drawString(x, y, word)
        if bk.key and word == right:
            c.setStrokeColor(T.answer)
            c.setLineWidth(1.5)
            c.ellipse(x - 5, y - 6, x + ww + 5, y + size + 2, stroke=1, fill=0)
        x += ww + gap
    return x - gap - x0


def yes_no_choice(bk, x, cy, w, yes):
    """yes on top, no below (always this order); the key rings the right one."""
    for j, word in enumerate(["yes", "no"]):
        px, py = x + w - 40, cy + 36 - j * 24
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 13)
        bk.c.drawCentredString(px, py, word)
        if bk.key and (word == "yes") == yes:
            bk.c.setStrokeColor(T.answer)
            bk.c.setLineWidth(1.6)
            bk.c.ellipse(px - 19, py - 7, px + 19, py + 14, stroke=1, fill=0)


def c_eq_share(bk, x, cy, w, item):
    kind, n, equal = item
    s = 44 if kind not in ("rect", "tall") else 32
    sw_, sh_ = share_size(kind, s)
    share_shape(bk, kind, x + GUT + 6, cy + (64 - sh_) / 2, s, n, equal=equal)
    yes_no_choice(bk, x, cy, w, equal)


def c_name_share(bk, x, cy, w, item):
    kind, n, i = item
    s = 54 if kind not in ("rect", "tall") else 48
    sw_, sh_ = share_size(kind, s)
    share_shape(bk, kind, x + GUT, cy + (96 - sh_) / 2 - 2, s, n, shaded=[i])
    tx = x + GUT + 92
    bk.fit_eq(tx, cy + 58, w - (tx - x) - 8, f"[{n}] equal shares", size=14)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("Av", 9)
    bk.c.drawString(tx, cy + 36, "The shaded part is 1")
    circle_choice(bk, tx, cy + 15, ["half", "third", "fourth"], SHARE_NAME[n][0], size=11.5, gap=12)


def c_shade(bk, x, cy, w, item):
    kind, n, k = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 92, f"Shade {share_word(n, k)}.")
    s = 58 if kind not in ("rect", "tall") else 46
    sw_, sh_ = share_size(kind, s)
    share_shape(bk, kind, x + GUT, cy + 76 - sh_, s, n, answer=range(k))


CUT_LOOK = {("square", 4): "grid"}  # what the key draws for a cut


def c_cut(bk, x, cy, w, item):
    kind, n = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 92, f"{n} equal shares")
    s = 58 if kind not in ("rect", "tall") else 46
    sw_, sh_ = share_size(kind, s)
    share_shape(bk, CUT_LOOK.get((kind, n), kind), x + GUT, cy + 76 - sh_, s, n, lines=False)


def c_bigger_share(bk, x, cy, w, item):
    """Two copies of the same shape, cut into a and b parts with one part shaded. The key rings the bigger share."""
    kind, a, b = item
    s = 54 if kind not in ("rect", "tall") else 44
    sw_, sh_ = share_size(kind, s)
    for j, n in enumerate((a, b)):
        sx = x + GUT + j * (sw_ + 34)
        share_shape(bk, kind, sx, cy + 30, s, n, shaded=[0])
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 11)
        bk.c.drawCentredString(sx + sw_ / 2, cy + 12, share_word(n))
        if bk.key and n == min(a, b):
            bk.c.setStrokeColor(T.answer)
            bk.c.setLineWidth(1.6)
            bk.c.roundRect(sx - 8, cy + 5, sw_ + 16, sh_ + 31, 10, stroke=1, fill=0)


def square_grid(bk, x, y, rows, cols, cell, lines=True):
    """A rectangle of rows × cols squares; y = bottom. lines=False: outline only (the key draws the lines)."""
    c = bk.c
    if lines or bk.key:
        c.setStrokeColor(T.ink if lines else T.answer)
        c.setLineWidth(1)
        for i in range(1, cols):
            c.line(x + i * cell, y, x + i * cell, y + rows * cell)
        for j in range(1, rows):
            c.line(x, y + j * cell, x + cols * cell, y + j * cell)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.6)
    c.rect(x, y, cols * cell, rows * cell, stroke=1, fill=0)


def c_rows_squares(bk, x, cy, w, item):
    rows, cols = item
    cell = 15
    square_grid(bk, x + GUT, cy + (96 - rows * cell) / 2, rows, cols, cell)
    tx = x + GUT + 5 * cell + 18
    bk.fit_eq(tx, cy + 58, w - (tx - x) - 8, f"[{rows}] rows of [{cols}]", size=14)
    bk.fit_eq(tx, cy + 22, w - (tx - x) - 8, f"[{rows * cols}] squares", size=14)


def c_draw_squares(bk, x, cy, w, item):
    rows, cols = item
    cell = 17
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 92, f"Draw lines: {rows} rows of {cols} squares.")
    square_grid(bk, x + GUT, cy + 74 - rows * cell, rows, cols, cell, lines=False)
    bk.fit_eq(x + GUT + cols * cell + 24, cy + 30, w - GUT - cols * cell - 32, f"[{rows * cols}] squares", size=14)


def learn_shares(bk):
    y = bk.new_page("Halves, Thirds and Fourths", "Equal shares are the same size.", name_line=False,
                    big=True, footer="WeMath  ·  Halves, Thirds and Fourths")
    c = bk.c
    label(bk, M, y - 6, "Fair to share? The shares must be the same size.")
    for i, (kind, n, eq_) in enumerate([("circle", 2, True), ("circle", 2, False), ("rect", 3, True),
                                        ("rect", 3, False)]):
        sx = M + 14 + i * 128
        share_shape(bk, kind, sx, y - 80, 54 if kind == "circle" else 42, n, equal=eq_)
        c.setFillColor(T.ink if eq_ else T.text2)
        c.setFont("Rnd", 13)
        c.drawString(sx, y - 94, "equal" if eq_ else "not equal")
    y -= 112

    label(bk, M, y - 6, "Name the shares")
    for i, n in enumerate((2, 3, 4)):
        sx = M + 14 + i * 172
        share_shape(bk, "circle", sx, y - 86, 64, n, shaded=[0])
        color_eq(bk, sx + 78, y - 50, [("1", "b"), (SHARE_NAME[n][0], None)], 20)
        c.setFillColor(T.text2)
        c.setFont("Rnd", 11)
        c.drawString(sx + 78, y - 70, f"{n} {SHARE_NAME[n][1]} make")
        c.drawString(sx + 78, y - 84, "1 whole")
    y -= 108

    label(bk, M, y - 6, "More shares, smaller shares")
    for i, n in enumerate((2, 3, 4)):
        by = y - 44 - i * 30
        parts = [[(M + 14 + 210 * j / n, by), (M + 14 + 210 * (j + 1) / n, by), (M + 14 + 210 * (j + 1) / n, by + 22),
                  (M + 14 + 210 * j / n, by + 22)] for j in range(n)]
        shade(bk, parts[0])
        c.setStrokeColor(T.ink)
        c.setLineWidth(1.4)
        for pts in parts:
            c.drawPath(_poly(c, pts), stroke=1, fill=0)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 13)
        c.drawString(M + 236, by + 6, share_word(n))
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 330, y - 54, "Cut the same bar")
    c.drawString(M + 330, y - 72, "into more shares:")
    c.drawString(M + 330, y - 90, "each share gets smaller.")
    y -= 120

    label(bk, M, y - 6, "Halves can look different")
    for i, kind in enumerate(("square", "hsquare", "diag")):
        share_shape(bk, kind, M + 14 + i * 84, y - 82, 58, 2, shaded=[i % 2])
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 290, y - 44, "Each square is cut in half.")
    c.drawString(M + 290, y - 62, "Each shaded part is 1 half.")
    y -= 100

    bottom = your_turn(bk, y, h=90)
    bk.ask("shade: rect 4 1 your turn")
    c.setFillColor(T.ink)
    c.setFont("Rnd", 14)
    c.drawString(M + 130, bottom + 62, "Shade 1 fourth.")
    share_shape(bk, "rect", M + 130, bottom + 12, 42, 4, answer=[0])
    bk.eq(M + 300, bottom + 36, "[4] fourths make 1 whole", size=17)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: cut shapes into 2, 3 or 4 equal shares and name them (2.G.3). Ask “Are the "
                     "shares the same size?” before naming them. Say “the more shares, the smaller each "
                     "share,” so 1 fourth is smaller than 1 half. No fraction numbers (½) yet.")


def practice_shares(bk):
    title = "Halves, Thirds and Fourths: Practice"
    y = bk.new_page(title, "Equal shares first. Then name them.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    part(1, "Equal shares?", "Are all the shares the same size? Circle yes or no.",
         [("circle", 2, False), ("rect", 2, True), ("grid", 4, True), ("tall", 3, False), ("circle", 3, True),
          ("square", 2, False), ("diag", 4, True), ("rect", 4, False), ("circle", 4, True), ("tall", 4, True),
          ("circle", 3, False), ("rect", 3, True)], 3, 64, 8, c_eq_share, KINDS_26["eq_share"].key)
    part(2, "Name the share", "Count the equal shares. Circle the name of the shaded part.",
         [("circle", 3, 0), ("rect", 2, 1), ("grid", 4, 2), ("tall", 3, 1), ("circle", 4, 3), ("diag", 2, 0),
          ("rect", 4, 2), ("square", 3, 2)], 2, 96, 10, c_name_share, KINDS_26["name_share"].key)
    part(3, "Shade it", None,
         [("rect", 2, 1), ("circle", 4, 1), ("tall", 3, 1), ("grid", 4, 3), ("circle", 3, 2), ("hsquare", 2, 1),
          ("rect", 4, 2), ("circle", 2, 1), ("tall", 4, 3)], 3, 110, 10, c_shade, KINDS_26["shade"].key)
    part(4, "Cut it", "Draw lines to cut the shape into equal shares.",
         [("circle", 2), ("rect", 3), ("square", 4), ("circle", 4), ("tall", 2), ("rect", 4)], 3, 110, 10,
         c_cut, lambda it: f"cut: {it[0]} {it[1]}")
    part(5, "Which share is bigger?", "Same shape, same size. Circle the bigger shaded share.",
         [("circle", 2, 4), ("rect", 3, 2), ("circle", 4, 3), ("tall", 2, 3), ("square", 3, 4), ("circle", 3, 2)],
         2, 104, 10, c_bigger_share, KINDS_26["bigger_share"].key)
    part(6, "Rows and columns", "Count the rows, the squares in each row, then all the squares.",
         [(2, 3), (3, 4), (4, 3), (2, 5), (5, 2), (3, 3)], 2, 96, 10, c_rows_squares, KINDS_26["rows_squares"].key)
    part(7, "Draw the squares", "Draw lines to make the rows and columns.",
         [(2, 4), (3, 2), (2, 3), (4, 3)], 2, 110, 10, c_draw_squares, lambda it: f"draw squares {it[0]} rows of {it[1]}")

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(8, "Make a whole", "No help this time.",
         ["1 half + 1 half = [1] whole", "2 fourths + [2] fourths = 1 whole", "1 third + [2] thirds = 1 whole",
          "3 fourths + [1] fourth = 1 whole", "1 fourth + 1 fourth = [2] fourths", "2 thirds + [1] third = 1 whole",
          "1 third + 1 third = [2] thirds", "2 fourths + 1 fourth = [3] fourths", "1 half + [1] half = 1 whole",
          "1 fourth + [3] fourths = 1 whole", "1 third + [1] third = 2 thirds",
          "1 fourth + 2 fourths = [3] fourths"], 2, 42, 8, plain, lambda t: t)
    part(9, "Wholes and shares", "No help this time. Picture the shapes.",
         ["1 whole = [2] halves", "2 wholes = [8] fourths", "1 whole = [3] thirds", "3 wholes = [6] halves",
          "1 whole = [4] fourths", "2 wholes = [6] thirds", "4 halves = [2] wholes", "9 thirds = [3] wholes",
          "8 fourths = [2] wholes", "3 wholes = [9] thirds"], 2, 42, 8, plain, lambda t: t)
    part(10, "Bigger or smaller?", "No help this time. Write <, > or =. Same size wholes.",
         ["1 half [>] 1 fourth", "1 third [<] 1 half", "2 halves [=] 1 whole", "1 fourth [<] 1 third",
          "1 whole [>] 2 thirds", "1 half [=] 2 fourths", "3 fourths [<] 1 whole", "1 third [>] 1 fourth",
          "3 thirds [=] 4 fourths", "1 fourth [<] 1 half"], 2, 42, 8, plain, lambda t: t)
    part(11, "Remember?", "Problems from earlier packets.",
         REVIEW_26, 3, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 12, "Word problems", "Draw the shapes. Share them fairly.")
    for i, story in enumerate(WORDS_26):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 12, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_26 = ["half of 74 = [37]", "36 + [64] = 100", "double 14 = [28]", "58 + 10 = [68]", "half of 92 = [46]",
             "6 + 6 + 6 = [18]"]

WORDS_26 = [
    ("Ava and Ben share a sandwich fairly. How much of the sandwich does each one get?",
     "1 half + 1 half = 1 whole", "half", "of the sandwich"),
    ("4 kids share a pizza fairly. Each kid gets 1 fourth. How many fourths make the whole pizza?",
     "4 fourths = 1 whole", "4", "fourths"),
    ("Dad cuts a cake into 3 equal shares. You eat 1 share. How many shares are left?",
     "1 third + 2 thirds = 1 whole", "2", "thirds"),
    ("A garden has 3 rows of 4 square beds. How many beds are there?", "4 + 4 + 4 = 12", "12", "beds"),
    ("Challenge: Sam eats 1 fourth of a pizza. Kim eats 1 half of the same pizza. Who eats more?",
     "1 half > 1 fourth", "Kim", ""),
]


# check-in cards for 26 (also used by the practice pages for their question keys)
KINDS_26 = {
    "eq_share": Kind(64, 3, lambda it: f"equal shares? {it[0]} {it[1]} {'yes' if it[2] else 'no'}", c_eq_share, 8),
    "name_share": Kind(96, 2, lambda it: f"name share: {it[0]} {it[1]} {it[2]}", c_name_share),
    "shade": Kind(110, 3, lambda it: f"shade: {it[0]} {it[1]} {it[2]}", c_shade),
    "bigger_share": Kind(104, 2, lambda it: f"bigger share: {it[0]} {it[1]} {it[2]}", c_bigger_share),
    "rows_squares": Kind(96, 2, lambda it: f"squares {it[0]} rows of {it[1]}", c_rows_squares),
}
KINDS.update(KINDS_26)
BALANCE["eq_share"] = lambda it: it[2]
BALANCE["bigger_share"] = lambda it: it[1] < it[2]

_SHAPES = ("circle", "rect", "tall", "square")
EQ_SHARE = ([(k, n, True) for k in _SHAPES + ("hsquare",) for n in (2, 3, 4)] + [("grid", 4, True), ("diag", 2, True),
            ("diag", 4, True)] + [(k, n, False) for k in _SHAPES for n in (2, 3, 4)])
NAME_SHARE = [(k, n, i) for k in _SHAPES + ("hsquare", "grid", "diag") for n in (2, 3, 4) for i in range(n)
              if (k, n) not in (("grid", 2), ("grid", 3), ("diag", 3))]
SHADE = [(k, n, j) for k in _SHAPES + ("hsquare", "grid") for n in (2, 3, 4) for j in range(1, n)
         if (k, n) not in (("grid", 2), ("grid", 3))]


def _share_value(text):
    k, word = text.split()
    n = next(n for n, names in SHARE_NAME.items() if word in names)
    return Fraction(int(k), n)


_SHARE_TERMS = ["1 half", "1 third", "1 fourth", "1 whole", "2 halves", "3 thirds", "4 fourths", "2 fourths",
                "2 thirds", "3 fourths"]
MAKE_WHOLE = ([f"{share_word(n, a)} + [{n - a}] {SHARE_NAME[n][n - a > 1]} = 1 whole" for n in (2, 3, 4)
               for a in range(1, n)]
              + [f"{share_word(n, a)} + {share_word(n, n - a)} = [1] whole" for n in (2, 3, 4) for a in range(1, n)]
              + [f"{share_word(n, a)} + {share_word(n, b)} = [{a + b}] {SHARE_NAME[n][1]}" for n in (3, 4)
                 for a in range(1, n) for b in range(1, n - a)])
COMPARE_SHARES = [f"{a} [{sign_of(_share_value(a), _share_value(b))}] {b}" for a in _SHARE_TERMS for b in _SHARE_TERMS
                  if a != b and ((_share_value(a).numerator == 1 and _share_value(b).numerator == 1)
                                 or _share_value(a) == 1 or _share_value(b) == 1 or {a, b} == {"1 half", "2 fourths"})]

CHECKINS["26-halves-thirds-and-fourths"] = [
    S("Equal shares?", "Circle yes or no.", "eq_share", EQ_SHARE, 3),
    S("Name the share", "Circle the name of the shaded part.", "name_share", NAME_SHARE, 2),
    S("Shade it", None, "shade", SHADE, 3),
    S("Make a whole", None, "eq2", MAKE_WHOLE, 2),
    S("Bigger or smaller?", "Write <, > or =.", "eq2", COMPARE_SHARES, 2, balance=is_less),
]
_g2[-1:-1] = [
    S("Equal shares", "Circle the name of the shaded part.", "name_share", NAME_SHARE, 2, 26),
    S("Halves, thirds and fourths", None, "eq2", MAKE_WHOLE + COMPARE_SHARES, 2, 26),
]


# ====================================================================== 27. Telling Time


def sector_pts(cx, cy, r, a0, a1, k=48):
    """A pie slice from angle a0 to a1 (degrees, counter-clockwise from 3 o'clock)."""
    return [(cx, cy)] + [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / k)),
                          cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / k))) for i in range(k + 1)]


CLOCK_SHADE = {"half": (-90, 90), "quarter": (0, 90), "three": (180, 450)}  # half past, quarter past, quarter to


def clock_hands(bk, cx, cy, R, h, m, color=None):
    """Short thick hour hand (blue), long thin minute hand (orange). color= draws both in one colour."""
    c = bk.c
    c.setLineCap(1)
    for length, width, ang, col in ((0.5, 0.085, 90 - 30 * (h % 12 + m / 60), T.dot_a),
                                    (0.8, 0.045, 90 - 6 * m, T.accent)):
        c.setStrokeColor(color or col)
        c.setLineWidth(max(1.4, R * width))
        a = math.radians(ang)
        c.line(cx, cy, cx + R * length * math.cos(a), cy + R * length * math.sin(a))
    c.setLineCap(0)
    c.setFillColor(color or T.ink)
    c.circle(cx, cy, max(2, R * 0.06), stroke=0, fill=1)


def clock(bk, cx, cy, R, time=None, ring=None, shaded=None, answer=False):
    """A clock face. time = (h, m). ring = "full" (5, 10, … 55 outside the face), "quarters" (15, 30, 45)
    or None. shaded = "half", "quarter" or "three" (the part the minute hand has swept). answer=True
    draws the hands only on the key, in the answer colour."""
    c = bk.c
    if shaded:
        shade(bk, sector_pts(cx, cy, R, *CLOCK_SHADE[shaded]))
    c.setStrokeColor(T.ink)
    c.setLineWidth(max(1.2, R * 0.035))
    c.circle(cx, cy, R, stroke=1, fill=0)
    for i in range(60):
        a = math.radians(90 - 6 * i)
        big = i % 5 == 0
        c.setStrokeColor(T.ink if big else T.muted)
        c.setLineWidth(1 if big else 0.5)
        r0 = R * (0.86 if big else 0.92)
        c.line(cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + R * 0.98 * math.cos(a), cy + R * 0.98 * math.sin(a))
    c.setFillColor(T.ink)
    size = max(7, R * 0.2)
    c.setFont("Rnd", size)
    for n in range(1, 13):
        a = math.radians(90 - 30 * n)
        c.drawCentredString(cx + R * 0.7 * math.cos(a), cy + R * 0.7 * math.sin(a) - size * 0.36, str(n))
    if ring:
        rs = max(6.5, R * 0.16)
        c.setFillColor(T.accent)
        c.setFont("AvD", rs)
        for n in range(1, 12):
            if ring == "quarters" and n not in (3, 6, 9):
                continue
            a = math.radians(90 - 30 * n)
            c.drawCentredString(cx + (R + rs * 0.95) * math.cos(a), cy + (R + rs * 0.95) * math.sin(a) - rs * 0.36,
                                str(5 * n))
    if time and (not answer or bk.key):
        clock_hands(bk, cx, cy, R, *time, color=T.answer if answer else None)
    elif not time or answer:
        c.setFillColor(T.ink)
        c.circle(cx, cy, max(2, R * 0.06), stroke=0, fill=1)


def tstr(h, m):
    return f"{h}:{m:02d}"


def time_words(h, m):
    nxt = h % 12 + 1
    return {0: f"{h} o'clock", 15: f"quarter past {h}", 30: f"half past {h}", 45: f"quarter to {nxt}"}[m]


def c_read_clock(bk, x, cy, w, item):
    """item = (h, m, ring): read the clock, write the time."""
    h, m, ring = item
    R = 30
    clock(bk, x + GUT + R + 6, cy + 43, R, (h, m), ring)
    bk.eq(x + GUT + 2 * R + (40 if ring else 26), cy + 34, f"[{tstr(h, m)}]", size=18)


def c_half_past(bk, x, cy, w, item):
    h, m = item
    R = 30
    clock(bk, x + GUT + R + 6, cy + 43, R, (h, m), shaded={30: "half", 15: "quarter", 45: "three"}[m])
    tx = x + GUT + 2 * R + 26
    words = time_words(h, m).split()
    hour = words.pop()
    bk.fit_eq(tx, cy + 54, w - (tx - x) - 8, " ".join(words) + f" [{hour}]", size=14)
    bk.fit_eq(tx, cy + 18, w - (tx - x) - 8, f"[{tstr(h, m)}]", size=16)


def c_draw_hands(bk, x, cy, w, item):
    h, m, ring = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 14)
    bk.c.drawString(x + GUT, cy + 100, f"Draw {tstr(h, m)}")
    R = 32
    clock(bk, x + GUT + R + 20, cy + 48, R, (h, m), ring, answer=True)


AMPM = [("Eat breakfast at 7:30", "a.m."), ("Go to bed at 8:00", "p.m."), ("Wake up at 6:45", "a.m."),
        ("Eat dinner at 6:00", "p.m."), ("Start school at 8:15", "a.m."), ("See the stars at 9:00", "p.m."),
        ("Recess at 10:30", "a.m."), ("Soccer after school at 4:00", "p.m."), ("Brush teeth before school at 7:10",
                                                                                  "a.m."),
        ("The sun sets at 7:45", "p.m."), ("Eat lunch at 12:30", "p.m."), ("The sun comes up at 6:20", "a.m."),
        ("Read a bedtime story at 7:50", "p.m."), ("Walk the dog before school at 7:05", "a.m."),
        ("Get out of school at 3:10", "p.m."), ("Eat a snack in the morning at 9:40", "a.m.")]


def c_ampm(bk, x, cy, w, item):
    text, right = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 16, text)
    circle_choice(bk, x + w - 92, cy + 16, ["a.m.", "p.m."], right, size=12.5, gap=14)


def sun_icon(bk, cx, cy, r):
    c = bk.c
    c.setStrokeColor(T.accent if T.color else T.ink)
    c.setLineWidth(1.4)
    for i in range(8):
        a = math.radians(45 * i)
        c.line(cx + r * 1.3 * math.cos(a), cy + r * 1.3 * math.sin(a), cx + r * 1.75 * math.cos(a), cy + r * 1.75 * math.sin(a))
    if T.color:
        c.setFillColor(T.accent)
        c.circle(cx, cy, r, stroke=0, fill=1)
    else:
        c.setFillColor(white)
        c.circle(cx, cy, r, stroke=1, fill=1)


def moon_icon(bk, cx, cy, r):
    c = bk.c
    pts = ([(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(60, 301, 6)]
           + [(cx + r * 0.35 + r * 0.8 * math.cos(math.radians(a)), cy + r * 0.8 * math.sin(math.radians(a)))
              for a in range(255, 104, -6)])
    c.setFillColor(T.dot_a if T.color else white)
    c.setStrokeColor(T.dot_a if T.color else T.ink)
    c.setLineWidth(1.2)
    c.drawPath(_poly(c, pts), stroke=1, fill=1)


def learn_time(bk):
    y = bk.new_page("Telling Time", "The short hand tells the hour. The long hand tells the minutes.",
                    name_line=False, big=True, footer="WeMath  ·  Telling Time")
    c = bk.c
    label(bk, M, y - 6, "Two hands")
    clock(bk, M + 70, y - 72, 46, (3, 0))
    c.setFillColor(T.dot_a)
    c.setFont("Rnd", 13)
    c.drawString(M + 140, y - 64, "short hand: the hour")
    c.setFillColor(T.accent)
    c.drawString(M + 140, y - 84, "long hand: the minutes")
    color_eq(bk, M + 330, y - 82, [("3", "a"), ("o'clock", None), ("=", "op"), ("3", "a"), (":00", None, "tight")], 24)
    y -= 132

    label(bk, M, y - 6, "Count by 5s around the clock")
    clock(bk, M + 74, y - 80, 46, (2, 20), ring="full")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 154, y - 56, "The long hand is on the 4.")
    c.drawString(M + 154, y - 76, "Count by 5s: 5, 10, 15, 20.")
    c.drawString(M + 154, y - 96, "The short hand is past the 2.")
    color_eq(bk, M + 380, y - 82, [("2", "a"), (":", None, "tight"), ("20", "b", "tight")], 30)
    y -= 154

    label(bk, M, y - 6, "Half past and quarters")
    for i, (h, m) in enumerate(((6, 30), (9, 15), (4, 45))):
        cx = M + 52 + i * 172
        clock(bk, cx, y - 58, 34, (h, m), shaded={30: "half", 15: "quarter", 45: "three"}[m])
        c.setFillColor(T.ink)
        c.setFont("Rnd", 12.5)
        c.drawString(cx + 42, y - 52, time_words(h, m))
        color_eq(bk, cx + 42, y - 74, [(str(h), "a"), (":", None, "tight"), (f"{m:02d}", "b", "tight")], 18)
    y -= 112

    bottom = your_turn(bk, y, h=104)
    bk.ask("clock read 5:10 your turn")
    clock(bk, M + 170, bottom + 52, 36, (5, 10), ring="full")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 232, bottom + 62, "What time is it?")
    bk.eq(M + 232, bottom + 28, "[5:10]", size=20)
    sun_icon(bk, M + 372, bottom + 62, 8)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 11)
    c.drawString(M + 390, bottom + 58, "a.m. = morning")
    moon_icon(bk, M + 372, bottom + 32, 9)
    c.drawString(M + 390, bottom + 28, "p.m. = afternoon")
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: tell and write time to 5 minutes, with a.m. and p.m. (2.MD.7). Read the short hand "
                     "first (“past the 2”), then count the long hand by 5s. Half past and quarters "
                     "are the halves and fourths of a circle (packet 26).")


TIME_FIVES = [(h, m) for h in rng(1, 12) for m in rng(5, 55, 5) if m not in (15, 30, 45)]


def practice_time(bk):
    title = "Telling Time: Practice"
    y = bk.new_page(title, "Short hand: the hour. Long hand: count by 5s.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    read = KINDS_27["read_clock"].key
    part(1, "O'clock", "The long hand is on the 12.",
         [(3, 0, None), (7, 0, None), (12, 0, None), (9, 0, None), (5, 0, None), (10, 0, None)], 2, 86, 10,
         c_read_clock, read)
    part(2, "Half past", "The long hand went halfway around: 30 minutes.",
         [(4, 30), (11, 30), (1, 30), (8, 30)], 2, 86, 10, c_half_past, KINDS_27["half_past"].key)
    part(3, "Count by 5s", "Count by 5s to the long hand.",
         [(2, 25), (8, 10), (11, 40), (1, 55), (6, 5), (3, 35), (10, 50), (7, 20)], 2, 86, 10,
         lambda bk_, x, cy, w, it: c_read_clock(bk_, x, cy, w, (*it, "full")), lambda it: read((*it, None)))
    part(4, "Quarter past and quarter to", "A quarter of the clock is 15 minutes.",
         [(9, 15), (2, 45), (6, 15), (11, 45), (3, 15), (7, 45)], 2, 86, 10, c_half_past, KINDS_27["half_past"].key)
    part(5, "The short hand is between", "Not at the next number yet? Use the number it passed.",
         [(2, 50), (9, 40), (5, 55), (12, 45), (4, 35), (8, 50)], 2, 86, 10,
         lambda bk_, x, cy, w, it: c_read_clock(bk_, x, cy, w, (*it, "quarters")), lambda it: read((*it, None)))
    part(6, "Draw the hands", "Short hand for the hour, long hand for the minutes.",
         [(7, 15, "full"), (10, 0, "full"), (1, 45, "full"), (4, 25, "quarters"), (11, 10, "quarters"),
          (6, 50, "quarters")], 3, 120, 10, c_draw_hands, KINDS_27["draw_hands"].key)
    part(7, "Read the clock", "No help this time.",
         [(5, 20), (12, 10), (9, 55), (3, 40), (8, 25), (2, 5), (6, 35), (10, 20)], 2, 86, 10,
         lambda bk_, x, cy, w, it: c_read_clock(bk_, x, cy, w, (*it, None)), lambda it: read((*it, None)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(8, "Half past and quarters", "No help this time.",
         ["half past 8 = [8:30]", "quarter past 2 = [2:15]", "quarter to 11 = [10:45]", "half past 12 = [12:30]",
          "quarter to 3 = [2:45]", "quarter past 10 = [10:15]", "half past 5 = [5:30]", "quarter to 7 = [6:45]",
          "quarter past 4 = [4:15]", "half past 9 = [9:30]"], 2, 42, 8, plain, lambda t: t)
    part(9, "Count the minutes", "No help this time. Count by 5s.",
         [f"long hand on {n} = [{5 * n}] minutes" for n in (4, 9, 2, 11, 7, 3, 10, 5, 8, 1)], 2, 42, 8, plain,
         lambda t: t)
    part(10, "Hours and minutes", "No help this time.",
         ["1 hour = [60] minutes", "half an hour = [30] minutes", "a quarter hour = [15] minutes",
          "2 half hours = [1] hour", "15 + 15 = [30] minutes", "30 + 30 = [60] minutes"],
         2, 42, 8, plain, lambda t: t)
    part(11, "a.m. or p.m.?", "Morning is a.m. Afternoon and night are p.m.",
         [AMPM[i] for i in (0, 1, 2, 3, 4, 5, 6, 7)], 1, 40, 6, c_ampm, KINDS_27["ampm"].key)
    part(12, "Remember?", "Problems from earlier packets.", REVIEW_27, 3, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 13, "Word problems", "Draw a clock if it helps.")
    for i, story in enumerate(WORDS_27):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 13, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_27 = ["15 + 15 + 15 = [45]", "60 + 30 = [90]", "55 + [45] = 100", "25 + 25 = [50]",
             "double 30 = [60]", "50 + 25 = [75]"]

WORDS_27 = [
    ("Mia wakes up. The short hand is on the 7. The long hand is on the 12. What time is it?",
     "7 o'clock = 7:00", "7:00", "a.m."),
    ("Lunch starts at half past 11 in the morning. Write the time.", "half past 11 = 11:30", "11:30", "a.m."),
    ("Ben's piano lesson is at quarter to 5 in the afternoon. Write the time.", "quarter to 5 = 4:45", "4:45",
     "p.m."),
    ("The long hand is on the 8. The short hand is just past the 3. What time is it?", "3:40", "3:40", ""),
    ("Challenge: The bus should come at 3:00. It is half an hour late. What time does it come?",
     "3:00 + 30 minutes = 3:30", "3:30", "p.m."),
]

KINDS_27 = {
    "read_clock": Kind(86, 2, lambda it: f"clock read {tstr(it[0], it[1])}", c_read_clock),
    "half_past": Kind(86, 2, lambda it: f"clock quarter {tstr(*it)}", c_half_past),
    "draw_hands": Kind(120, 3, lambda it: f"draw hands {tstr(it[0], it[1])}", c_draw_hands),
    "ampm": Kind(40, 1, lambda it: f"ampm: {it[0]}", c_ampm, 6),
}
KINDS.update(KINDS_27)
BALANCE["ampm"] = lambda it: it[1] == "a.m."

TIME_QUARTERS = [(h, m) for h in rng(1, 12) for m in (15, 30, 45)]
TIME_WORDS = ([f"{time_words(h, m)} = [{tstr(h, m)}]" for h, m in TIME_QUARTERS]
              + [f"long hand on {n} = [{5 * n}] minutes" for n in rng(1, 11)])

CHECKINS["27-telling-time"] = [
    S("Read the clock", None, "read_clock", [(h, m, None) for h, m in TIME_FIVES], 2),
    S("Draw the hands", None, "draw_hands", [(h, m, None) for h, m in TIME_FIVES + TIME_QUARTERS], 3),
    S("Write the time", None, "eq2", TIME_WORDS, 4),
    S("a.m. or p.m.?", None, "ampm", AMPM, 2),
]
_g2[-1:-1] = [
    S("Telling time", None, "read_clock", [(h, m, None) for h, m in TIME_FIVES], 2, 27),
    S("Half past and quarters", None, "eq2", TIME_WORDS[:36], 2, 27),
]


# ====================================================================== 28. Money

COIN = {  # letter: (value in cents, real diameter in mm, name, plural)
    "Q": (25, 24.3, "quarter", "quarters"), "D": (10, 17.9, "dime", "dimes"),
    "N": (5, 21.2, "nickel", "nickels"), "P": (1, 19.05, "penny", "pennies"),
}


def cents(coins):
    return sum(COIN[k][0] for k in coins)


def coin(bk, cx, cy, kind, k=1.3):
    """One coin at its real relative size (k points per mm), value printed on it. Returns the radius."""
    c = bk.c
    value, mm = COIN[kind][:2]
    r = mm * k / 2
    fill = T.copper if kind == "P" else T.silver
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.1)
    c.setFillColor(fill if fill is not None else white)
    c.circle(cx, cy, r, stroke=1, fill=1)
    c.setStrokeColor(T.muted)
    c.setLineWidth(0.5)
    c.circle(cx, cy, r * 0.84, stroke=1, fill=0)
    size = r * 0.74 if value < 10 else r * (0.7 if value == 10 else 0.6)
    c.setFillColor(T.ink)
    c.setFont("Rnd", size)
    c.drawCentredString(cx, cy - size * 0.36, f"{value}¢")
    return r


def coin_row(bk, x, cy, coins, k=1.3, step=None, totals=None, box_y=None, tsize=11):
    """Coins left to right, centred on cy. totals: None, "boxes" (running totals to fill in; shown on the key)
    or "given" (running totals printed). Returns the width."""
    step = step or 24.3 * k + 7
    run = 0
    for i, kind in enumerate(coins):
        cx = x + 24.3 * k / 2 + i * step
        coin(bk, cx, cy, kind, k)
        run += COIN[kind][0]
        if totals:
            bw, bh = step - 6, tsize * 1.7
            by = box_y if box_y is not None else cy - 24.3 * k / 2 - bh - 6
            if totals == "boxes":
                bk.box(cx - bw / 2, by, bw, bh, run, size=tsize)
            else:
                bk.c.setFillColor(T.text2)
                bk.c.setFont("Rnd", tsize)
                bk.c.drawCentredString(cx, by + bh / 2 - tsize * 0.36, str(run))
    return (len(coins) - 1) * step + 24.3 * k


def bill(bk, x, y, value, w=58, h=28):
    """A dollar bill; (x, y) = bottom-left."""
    c = bk.c
    c.setStrokeColor(T.ink)
    c.setLineWidth(1)
    c.setFillColor(T.bill if T.bill is not None else white)
    c.roundRect(x, y, w, h, 3, stroke=1, fill=1)
    c.setStrokeColor(T.muted)
    c.setLineWidth(0.5)
    c.roundRect(x + 3, y + 3, w - 6, h - 6, 2, stroke=1, fill=0)
    c.setFillColor(T.ink)
    c.setFont("Rnd", 13)
    c.drawCentredString(x + w / 2, y + h / 2 - 4.5, f"${value}")


def greedy(amount):
    out = ""
    for kind in "QDNP":
        while amount >= COIN[kind][0]:
            out += kind
            amount -= COIN[kind][0]
    return out


def c_coins_running(bk, x, cy, w, coins):
    """Coins in order (biggest first) with a running-total box under each, then the total."""
    coin_row(bk, x + GUT, cy + 50, coins, totals="boxes", box_y=cy + 10)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvM", 10)
    bk.c.drawString(x + w - 140, cy + 46, "In all:")
    bk.eq(x + w - 100, cy + 40, f"[{cents(coins)}¢]", size=18)


def c_coins(bk, x, cy, w, coins):
    """Coins in any order, no help: sort them in your head, then count on."""
    k = 1.15
    width = coin_row(bk, x + GUT, cy + 58, coins, k=k, step=24.3 * k + 4)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{cents(coins)}¢]", size=18)


def c_show_amount(bk, x, cy, w, amount):
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 14)
    bk.c.drawString(x + GUT, cy + 92, f"Show {amount}¢.")
    bk.work(x + GUT, cy + 10, w - GUT - 12, 70, "Draw the coins")
    if bk.key:
        coin_row(bk, x + GUT + 12, cy + 44, greedy(amount), k=1.05)


def c_bills(bk, x, cy, w, bills):
    for i, v in enumerate(bills):
        bill(bk, x + GUT + i * 64, cy + 44, v)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[${sum(bills)}]", size=18)


def c_compare_coins(bk, x, cy, w, item):
    a, b = item
    k = 1.05
    wa = coin_row(bk, x + GUT, cy + 52, a, k=k, step=24.3 * k + 3)
    bk.eq(x + GUT + wa / 2 - 20, cy + 14, f"[{cents(a)}¢]", size=15)
    sx = x + GUT + 250
    bk.eq(sx - 66, cy + 36, f"[{sign_of(cents(a), cents(b))}]", size=18)
    wb = coin_row(bk, sx, cy + 52, b, k=k, step=24.3 * k + 3)
    bk.eq(sx + wb / 2 - 20, cy + 14, f"[{cents(b)}¢]", size=15)


def c_symbol(bk, x, cy, w, item):
    text, sym = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 15, text)
    circle_choice(bk, x + w - 64, cy + 15, ["¢", "$"], sym, size=15, gap=18)


def learn_money(bk):
    y = bk.new_page("Money", "Count the biggest coins first. Then count on.", name_line=False, big=True,
                    footer="WeMath  ·  Money")
    c = bk.c
    label(bk, M, y - 6, "Meet the coins")
    for i, kind in enumerate("PNDQ"):
        cx = M + 44 + i * 112
        coin(bk, cx, y - 46, kind, k=2.1)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 13)
        c.drawCentredString(cx, y - 90, COIN[kind][2])
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 440, y - 40, "A dime is small,")
    c.drawString(M + 440, y - 56, "but it is worth")
    c.drawString(M + 440, y - 72, "more than a nickel.")
    y -= 116

    label(bk, M, y - 6, "Same coins: count by the coin")
    coin_row(bk, M + 14, y - 40, "DDD", k=1.6, totals="given", tsize=14)
    color_eq(bk, M + 170, y - 46, [("10,", None), ("20,", None), ("30", "b"), ("=", "op"), ("30¢", None)], 20)
    y -= 108

    label(bk, M, y - 6, "Mixed coins: biggest first, then count on")
    coin_row(bk, M + 14, y - 42, "QDDNPP", k=1.6, step=46, totals="given", tsize=14)
    color_eq(bk, M + 300, y - 50, [("25,", "a"), ("35,", None), ("45,", None), ("50,", None), ("51,", None),
                                   ("52¢", "b")], 20)
    y -= 108

    label(bk, M, y - 6, "100¢ is 1 dollar")
    coin_row(bk, M + 14, y - 42, "QQQQ", k=1.6, step=46, totals="given", tsize=14)
    color_eq(bk, M + 210, y - 50, [("100¢", "a"), ("=", "op"), ("$1", "b")], 24)
    bill(bk, M + 330, y - 64, 1, w=72, h=34)
    y -= 102

    bottom = your_turn(bk, y, h=96)
    bk.ask("coins: DDNPPP your turn")
    coin_row(bk, M + 130, bottom + 58, "DDNPPP", k=1.4, totals="boxes", box_y=bottom + 14)
    bk.eq(M + 400, bottom + 42, "[38¢]", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: count coins and bills and write ¢ and $ (2.MD.8). Size is not value: a dime is "
                     "small but worth 10¢. Sort the coins biggest first, say the running total out loud, then "
                     "count on by 5s and 1s. Real coins help a lot.")


def practice_money(bk):
    title = "Money: Practice"
    y = bk.new_page(title, "Biggest coins first. Say the running total.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    run_key = lambda co: f"coins running: {co}"
    part(1, "Same coins", "Count by the coin. Write the running totals.",
         ["NNNNNN", "DDDDD", "QQQ", "PPPPPPP", "DDDDDDD", "NNNNNNN"], 1, 84, 8, c_coins_running, run_key)
    part(2, "Count on", "Start with the big coin. Then count on.",
         ["QPPPP", "DNNN", "QDDD", "QNNN", "DDPPP", "QQNN"], 1, 84, 8, c_coins_running, run_key)
    part(3, "Mixed coins", "Biggest first. Write the running totals.",
         ["QDNPP", "DDNNP", "QQDPP", "QDDNN", "DNPPPP", "QQDDN"], 1, 84, 8, c_coins_running, run_key)
    part(4, "Count the coins", "No help this time. Find the biggest coins first.",
         ["PDNQ", "NPDD", "PPQN", "DQPD", "NNPQ", "PDQD", "QPNPD", "DPNQQ"], 2, 96, 10, c_coins,
         KINDS_28["coins"].key)
    part(5, "Show the amount", "Draw the fewest coins you can.", [35, 60, 42, 76], 2, 110, 10, c_show_amount, KINDS_28["show_amount"].key)
    part(6, "Dollars", "Count the bills. Biggest first.",
         [(5, 1, 1), (10, 5, 1), (10, 5, 5), (5, 5, 1)], 2, 84, 10, c_bills, lambda b: f"bills: {b}")
    part(7, "Which is more?", "Count each side. Write <, > or =.",
         [("QD", "DDDN"), ("QNP", "DDD"), ("DDD", "QN"), ("QQ", "DDDDN")], 1, 84, 8, c_compare_coins,
         KINDS_28["compare_coins"].key)

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(8, "Coins in words", "No help this time.",
         ["3 dimes + 2 nickels = [40¢]", "1 quarter + 3 pennies = [28¢]", "4 nickels + 1 dime = [30¢]",
          "2 quarters + 1 dime = [60¢]", "5 dimes + 4 pennies = [54¢]", "1 quarter + 2 nickels = [35¢]",
          "3 quarters + 1 nickel = [80¢]", "6 nickels + 2 pennies = [32¢]", "2 dimes + 7 pennies = [27¢]",
          "4 quarters = [100¢]"], 2, 42, 8, plain, lambda t: t)
    part(9, "Add the prices", "No help this time. Write ¢ in your answer.",
         ["25¢ + 30¢ = [55¢]", "40¢ + 35¢ = [75¢]", "15¢ + 50¢ = [65¢]",
          "45¢ + 25¢ = [70¢]", "60¢ + 18¢ = [78¢]", "35¢ + 35¢ = [70¢]",
          "22¢ + 45¢ = [67¢]", "50¢ + 50¢ = [100¢]", "75¢ + 15¢ = [90¢]"],
         3, 42, 8, plain, lambda t: t)
    part(10, "Make a dollar", "No help this time. 100¢ = $1.",
         ["65¢ + [35¢] = 100¢", "40¢ + [60¢] = 100¢", "85¢ + [15¢] = 100¢",
          "20¢ + [80¢] = 100¢", "55¢ + [45¢] = 100¢", "90¢ + [10¢] = 100¢",
          "45¢ + [55¢] = 100¢", "30¢ + [70¢] = 100¢", "95¢ + [5¢] = 100¢"],
         3, 42, 8, plain, lambda t: t)
    part(11, "¢ or $?", "Cents for small prices. Dollars for big ones.",
         SYMBOLS[:8], 2, 42, 8, c_symbol, KINDS_28["symbol"].key)
    part(12, "Remember?", "Problems from earlier packets.", REVIEW_28, 3, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 13, "Word problems", "Draw the coins.")
    for i, story in enumerate(WORDS_28):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 13, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


SYMBOLS = [("A pencil costs 40", "¢"), ("A bike costs 90", "$"), ("A gumball costs 25", "¢"),
           ("A new TV costs 300", "$"), ("A sticker costs 10", "¢"), ("A bed costs 200", "$"),
           ("An apple costs 60", "¢"), ("A tablet costs 150", "$"), ("A swing set costs 250", "$"),
           ("A stamp costs 70", "¢"), ("A big tent costs 80", "$"), ("A banana costs 30", "¢"),
           ("New shoes cost 45", "$"), ("An eraser costs 15", "¢")]

REVIEW_28 = ["half past 3 = [3:30]", "double 25 = [50]", "46 + 25 = [71]", "double 35 = [70]", "37 + 25 = [62]",
             "75 + 25 = [100]"]

WORDS_28 = [
    ("Ava has 2 dimes and 3 nickels. How much money does she have?", "20¢ + 15¢ = 35¢", "35¢", ""),
    ("A juice costs 45¢. A cookie costs 30¢. How much do they cost together?", "45¢ + 30¢ = 75¢", "75¢", ""),
    ("Leo pays with $1 for a ball that costs 65¢. How much change does he get?", "65¢ + 35¢ = 100¢", "35¢", ""),
    ("Mia has a $5 bill and three $1 bills. How many dollars does she have?", "$5 + $3 = $8", "$8", ""),
    ("Challenge: Kim has 3 quarters. A toy costs 90¢. How much more money does she need?",
     "75¢ + 15¢ = 90¢", "15¢", ""),
]

KINDS_28 = {
    "coins": Kind(96, 2, lambda co: f"coins: {co}", c_coins),
    "show_amount": Kind(110, 2, lambda a: f"show {a} cents", c_show_amount),
    "compare_coins": Kind(84, 1, lambda it: f"compare coins: {it[0]} {it[1]}", c_compare_coins, 8),
    "symbol": Kind(42, 2, lambda it: f"symbol: {it[0]}", c_symbol, 8),
}
KINDS.update(KINDS_28)
BALANCE["symbol"] = lambda it: it[1] == "$"

COIN_SETS = ["".join(p) for q in range(3) for d in range(4) for n in range(3) for p_ in range(5)
             if 3 <= q + d + n + p_ <= 6 and len({x for x, k in zip("QDNP", (q, d, n, p_)) if k}) >= 2
             for p in [shuf(f"cs{q}{d}{n}{p_}", "Q" * q + "D" * d + "N" * n + "P" * p_)]]
PRICES = [f"{a}¢ + {b}¢ = [{a + b}¢]" for a in rng(15, 70, 5) for b in rng(12, 45) if a + b <= 100]
DOLLAR_BUDDIES = [f"{a}¢ + [{100 - a}¢] = 100¢" for a in rng(5, 95, 5)]

CHECKINS["28-money"] = [
    S("Count the coins", None, "coins", COIN_SETS, 4),
    S("¢ or $?", None, "symbol", SYMBOLS, 2),
    S("Add the prices", None, "eq3", PRICES, 3),
    S("Make a dollar", None, "eq3", DOLLAR_BUDDIES, 3),
]
_g2[-1:-1] = [
    S("Money", "Count the coins.", "coins", COIN_SETS, 2, 28),
    S("Adding money", None, "eq3", PRICES, 2, 28),
]


# ====================================================================== 29. Subtracting Across Zeros


def tens_break(a, b):
    """403 − 157: 403 is 40 tens 3 ones; not enough ones, so 39 tens 13 ones. Returns (tens, ones)."""
    t, o = a // 10, a % 10
    if o < b % 10:
        t, o = t - 1, o + 10
    return t, o


def zero_rows(bk, x, top, a, b, helped=False, size=13, gap=27, maxw=None):
    """break / tens / ones / total rows, thinking of the top number as tens and ones."""
    t, o = tens_break(a, b)
    bt, bo = b // 10, b % 10
    fmt = (lambda v: str(v)) if helped else (lambda v: f"[{v}]")
    rows = [("break", f"{a} = {fmt(t)} tens + {fmt(o)} ones"),
            ("tens", f"[{t}] {MINUS} {bt} = [{t - bt}]"),
            ("ones", f"[{o}] {MINUS} {bo} = [{o - bo}]"),
            ("total", f"[{(t - bt) * 10}] + [{o - bo}] = [{a - b}]")]
    for i, (lab, text) in enumerate(rows):
        yy = top - i * gap
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 9.5)
        bk.c.drawString(x, yy + 1, lab)
        bk.fit_eq(x + 44, yy, (maxw or 400) - 44, text, size=size)
    return top - (len(rows) - 1) * gap


def c_zero_rows(bk, x, cy, w, item, helped=False):
    a, b = item
    bk.fit_eq(x + GUT, cy + 136, w - GUT - 10, f"{a} {MINUS} {b} = [{a - b}]", size=18)
    zero_rows(bk, x + GUT, cy + 103, a, b, helped=helped, size=12, gap=27, maxw=w - GUT - 8)


def c_tens_ones(bk, x, cy, w, n):
    """403 = 40 tens + 3 ones = 39 tens + 13 ones."""
    bk.fit_eq(x + GUT, cy + 46, w - GUT - 10, f"{n} = [{n // 10}] tens + [{n % 10}] ones", size=15)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"{n} = [{n // 10 - 1}] tens + [{n % 10 + 10}] ones", size=15)


def learn_across_zeros(bk):
    y = bk.new_page("Subtracting Across Zeros", "No tens to break? Think of the number as tens and ones.",
                    name_line=False, big=True, footer="WeMath  ·  Subtracting Across Zeros")
    c = bk.c
    label(bk, M, y - 6, f"403 {MINUS} 157: 3 {MINUS} 7? Break a ten. But there are 0 tens!")
    quick_hto(bk, M + 14, y - 66, 4, 0, 3, size=18, line_h=40)
    bk.arrow(M + 150, y - 46, M + 196, y - 46)
    quick_hto(bk, M + 214, y - 66, 3, 9, 13, size=18, line_h=40)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 11.5)
    c.drawString(M + 14, y - 86, "4 hundreds, 3 ones")
    c.drawString(M + 214, y - 86, "Break a hundred into 10 tens, then a ten into 10 ones.")
    y -= 112

    label(bk, M, y - 6, "The shortcut: 403 is 40 tens and 3 ones")
    color_eq(bk, M + 14, y - 40, [("403", None), ("=", "op"), ("40", "a"), ("tens", None), ("+", "op"), ("3", "b"),
                                  ("ones", None)], 22)
    color_eq(bk, M + 14, y - 72, [("403", None), ("=", "op"), ("39", "a"), ("tens", None), ("+", "op"), ("13", "b"),
                                  ("ones", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 330, y - 38, "Take 1 ten from the 40 tens.")
    c.drawString(M + 330, y - 56, "Now there are 39 tens")
    c.drawString(M + 330, y - 74, "and 13 ones. One break!")
    y -= 100

    label(bk, M, y - 6, f"Now subtract: 157 is 15 tens and 7 ones")
    for i, (lab, parts) in enumerate([
            ("tens", [("39", "a"), (MINUS, "op"), ("15", None), ("=", "op"), ("24", None), ("tens", None)]),
            ("ones", [("13", "b"), (MINUS, "op"), ("7", None), ("=", "op"), ("6", None)]),
            ("total", [("240", None), ("+", "op"), ("6", None), ("=", "op"), ("246", None)])]):
        yy = y - 34 - i * 28
        c.setFillColor(T.text2)
        c.setFont("AvD", 10)
        c.drawString(M + 14, yy + 2, lab)
        color_eq(bk, M + 64, yy, parts, 17)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 330, y - 40, "Check by adding:")
    color_eq(bk, M + 330, y - 66, [("246", None), ("+", "op"), ("157", None), ("=", "op"), ("403", "a")], 18)
    y -= 116

    bottom = your_turn(bk, y, h=150)
    bk.ask(f"302 {MINUS} 145 = []")
    bk.eq(M + 120, bottom + 116, f"302 {MINUS} 145 = [157]", size=20)
    zero_rows(bk, M + 120, bottom + 84, 302, 145, size=13, gap=24, maxw=300)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: subtract when the top number has zeros (2.NBT.7). Say “403 is 40 tens and 3 "
                     "ones,” then break one ten: 39 tens and 13 ones. Watch for 0 − 7 = 7 (the 0 can’t "
                     "give). Check every answer by adding.")


def practice_across_zeros(bk):
    title = "Subtracting Across Zeros: Practice"
    y = bk.new_page(title, "Think of the top number as tens and ones. Break once.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    sub_key = lambda it: f"{it[0]} {MINUS} {it[1]} = []"
    part(1, "Tens and ones", "Write it as tens and ones, then break one ten.",
         [403, 702, 305, 600, 801, 506, 900, 204], 2, 78, 10, c_tens_ones, KINDS_29["tens_ones"].key)
    part(2, "Break, then subtract", "The break row is done for you.",
         [(402, 135), (703, 248), (500, 164), (610, 253)], 2, 160, 10,
         lambda bk_, x, cy, w, it: c_zero_rows(bk_, x, cy, w, it, helped=True), sub_key)
    part(3, "Fill in every box", None,
         [(804, 376), (301, 127), (900, 465), (520, 148)], 2, 160, 10, c_zero_rows, sub_key)
    part(4, "Stack it", "Cross out the tens, write the new tens and ones on top, then subtract.",
         [(503, 276), (400, 218), (730, 364), (901, 452)], 4, 120, 8,
         lambda bk_, x, cy, w, it: c_col_sub3(bk_, x, cy, w, it, "boxes", True), sub_key)
    for k, (name, sub, probs) in enumerate([
            ("Zero in the tens", "No help this time.",
             [(403, 157), (605, 238), (802, 465), (704, 329), (501, 286), (906, 547), (308, 159), (207, 148)]),
            ("Zero in the ones", "No help this time.",
             [(510, 234), (720, 385), (640, 172), (830, 456), (450, 187), (910, 538), (370, 194), (260, 175)]),
            ("Two zeros", "No help this time.",
             [(300, 128), (500, 246), (700, 351), (400, 163), (800, 472), (600, 289), (900, 537), (200, 146)]),
            ("Mixed", "Break only when you need to.",
             [(605, 302), (803, 267), (540, 315), (700, 425), (406, 138), (960, 580), (302, 185), (850, 624)])]):
        part(5 + k, name, sub, probs, 4, 112, 8, c_col_sub3, sub_key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(9, "Check by adding", "No help this time. Do you get the top number back?",
         [f"{a} + {b} = [{a + b}]" for a, b in ((246, 157), (177, 128), (365, 245), (226, 274), (318, 282),
                                                (459, 141))], 3, 42, 8, plain, lambda t: t)
    part(10, "Remember?", "Problems from earlier packets.", REVIEW_29, 3, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 11, "Word problems", "Break once. Check by adding.")
    for i, story in enumerate(WORDS_29):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 11, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_29 = ["65¢ + 25¢ = [90¢]", "half past 7 = [7:30]", "352 + 216 = [568]", "64 + [36] = 100",
             "half of 86 = [43]", "2 halves = [1] whole"]

WORDS_29 = [
    ("A school has 400 pencils. The kids use 156 of them. How many pencils are left?",
     f"400 {MINUS} 156 = 244", "244", "pencils"),
    ("A book has 305 pages. Mia has read 128 pages. How many pages are left to read?",
     f"305 {MINUS} 128 = 177", "177", "pages"),
    ("There were 610 people at a game. Then 245 people went home. How many people stayed?",
     f"610 {MINUS} 245 = 365", "365", "people"),
    ("A jar holds 500 beads. 274 beads are red and the rest are blue. How many beads are blue?",
     f"500 {MINUS} 274 = 226", "226", "beads"),
    ("Challenge: A game needs 1000 points. Kim has 455. How many more points does she need?",
     "455 + 545 = 1000", "545", "points"),
]

KINDS_29 = {
    "tens_ones": Kind(78, 2, lambda n: f"{n} = [] tens + [] ones", c_tens_ones),
}
KINDS.update(KINDS_29)

ZERO_SUB = [(a, b) for a in rng(200, 990) if a % 100 and ("0" in str(a)[1:]) and a % 7 in (1, 4)
            for b in rng(112, a - 60) if b % 13 == 5 and a % 10 < b % 10 and (a // 10 % 10) <= b // 10 % 10
            and b % 10 and b // 10 % 10]
ZERO_SUB += [(a, b) for a in rng(200, 900, 100) for b in rng(112, a - 60) if b % 17 == 3 and b % 10 and b // 10 % 10]

CHECKINS["29-subtracting-across-zeros"] = [
    S("Tens and ones", None, "tens_ones", [n for n in rng(201, 909) if "0" in str(n)[1:] and n % 10 != 0
                                           and n // 10 % 10 == 0] + list(rng(200, 900, 100)), 2),
    S("Subtract", "Break once.", "col_sub3", ZERO_SUB, 4),
    S("Check by adding", None, "eq3", [f"{a - b} + {b} = [{a}]" for a, b in ZERO_SUB], 3),
]
_g2[-1:-1] = [
    S("Subtracting across zeros", None, "col_sub3", ZERO_SUB, 2, 29),
]


# ====================================================================== 30. Two-Step Word Problems (bar models)


def bar_piece(bk, x, y, w, h, value, shown, kind, size=13):
    """One piece of a bar: a number, or a box to fill in (the answer shows on the key)."""
    c = bk.c
    fill = (T.band if kind == "a" else T.strip) if T.color else None
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.1)
    if fill is not None:
        c.setFillColor(fill)
    c.rect(x, y, w, h, stroke=1, fill=1 if fill is not None else 0)
    if shown:
        c.setFillColor(T.ink)
        c.setFont("Rnd", size)
        c.drawCentredString(x + w / 2, y + h / 2 - size * 0.36, str(value))
    else:
        bw = max(28, sw(str(value), "Rnd", size) + 12)
        bk.box(x + w / 2 - bw / 2, y + (h - size * 1.45) / 2, bw, size * 1.45, value, size=size)


def bar_model(bk, x, y, w, parts, whole, h=24, size=13):
    """Part-part-whole bar. parts = [(value, shown)], whole = (value, shown) on a bracket above.
    y = bottom of the bar. Returns the top of the bracket label."""
    c = bk.c
    total = sum(v for v, _ in parts)
    widths = [max(40, w * v / total) for v, _ in parts]
    k = w / sum(widths)
    px = x
    for i, ((v, shown), pw) in enumerate(zip(parts, widths)):
        bar_piece(bk, px, y, pw * k, h, v, shown, "a" if i % 2 == 0 else "b", size)
        px += pw * k
    by = y + h + 7
    c.setStrokeColor(T.text2)
    c.setLineWidth(1)
    c.line(x, by, x + w, by)
    c.line(x, by, x, by - 5)
    c.line(x + w, by, x + w, by - 5)
    v, shown = whole
    if shown:
        c.setFillColor(T.ink)
        c.setFont("Rnd", size)
        c.drawCentredString(x + w / 2, by + 5, str(v))
    else:
        bw = max(28, sw(str(v), "Rnd", size) + 12)
        bk.box(x + w / 2 - bw / 2, by + 3, bw, size * 1.45, v, size=size)
    return by + 3 + size * 1.45


def compare_bars(bk, x, y, w, big, small, unknown, h=22, size=13, names=None):
    """Two bars, the bigger one on top. The gap at the end of the smaller bar is the difference (dashed).
    unknown: "diff", "big" or "small". names = (top label, bottom label), drawn left of the bars."""
    c = bk.c
    lw = 0
    if names:
        c.setFillColor(T.text2)
        c.setFont("AvD", 9.5)
        lw = max(sw(n, "AvD", 9.5) for n in names) + 8
        c.drawString(x, y + h + 8 + h / 2 - 3.5, names[0])
        c.drawString(x, y + h / 2 - 3.5, names[1])
    x += lw
    w -= lw
    ws = max(40, w * small / big)
    bar_piece(bk, x, y + h + 8, w, h, big, unknown != "big", "a", size)
    bar_piece(bk, x, y, ws, h, small, unknown != "small", "b", size)
    c.setStrokeColor(T.text2)
    c.setLineWidth(1)
    c.setDash(3, 2.5)
    c.rect(x + ws, y, w - ws, h, stroke=1, fill=0)
    c.setDash()
    d = big - small
    if unknown == "diff":
        bw = max(28, sw(str(d), "Rnd", size) + 12)
        bk.box(x + ws + (w - ws) / 2 - bw / 2, y + (h - size * 1.45) / 2, bw, size * 1.45, d, size=size)
    else:
        c.setFillColor(T.text2)
        c.setFont("Rnd", size)
        c.drawCentredString(x + ws + (w - ws) / 2, y + h / 2 - size * 0.36, str(d))
    return y + 2 * h + 8


def draw_model(bk, x, y, w, model, size=13):
    """model = ("pw", a, b, unknown) with unknown "whole" or "part" (the second part),
    or ("cmp", big, small, unknown, names), or ("eq", pieces, each, unknown) with unknown "whole" or "each"
    (equal pieces, packet 42)."""
    if model[0] == "eq":
        return equal_bar(bk, x, y, w, model[1], model[2], model[3], size=size)
    if model[0] == "pw":
        _, a, b, unknown = model
        return bar_model(bk, x, y, w, [(a, True), (b, unknown != "part")], (a + b, unknown != "whole"), size=size)
    _, big, small, unknown, *names = model
    return compare_bars(bk, x, y, w, big, small, unknown, size=size, names=names[0] if names else None)


def model_answer(model):
    if model[0] == "eq":
        return model[1] * model[2] if model[3] == "whole" else model[2]
    if model[0] == "pw":
        return model[1] + model[2] if model[3] == "whole" else model[2]
    _, big, small, unknown, *_ = model
    return {"diff": big - small, "big": big, "small": small}[unknown]


def c_bar(bk, x, cy, w, model):
    draw_model(bk, x + GUT, cy + 16, w - GUT - 16, model)


def sentence_line(bk, x, y, w, label_, sentence):
    c = bk.c
    c.setFillColor(T.text2)
    c.setFont("AvM", 8.5)
    c.drawString(x, y, label_)
    lx = x + sw(label_, "AvM", 8.5) + 6
    c.setStrokeColor(T.muted)
    c.setLineWidth(0.7)
    c.line(lx, y - 2, x + w, y - 2)
    if bk.key:
        bk.fit_eq(lx + 4, y + 1, x + w - lx - 4, sentence, size=12, color=T.answer)


def answer_box(bk, x, y, answer, unit):
    c = bk.c
    c.setFillColor(T.text2)
    c.setFont("AvM", 8.5)
    c.drawString(x, y + 9, "Answer")
    bw = max(46, sw(str(answer), "Rnd", 17) + 16)
    bk.box(x + 38, y, bw, 28, answer, size=17)
    c.setFillColor(T.ink)
    c.setFont("AvM", 11)
    c.drawString(x + 46 + bw, y + 10, unit)


def c_story_bar(bk, x, cy, w, item):
    """A one-step story with its bar model drawn (some numbers missing), a number sentence and an answer."""
    story, model, sentence, unit = item
    tx = x + GUT
    bk.paragraph(tx, cy + 122, w - GUT - 16, story, size=11.5, leading=15, font="AvM")
    draw_model(bk, tx, cy + 18, 246, model)
    rx = tx + 270
    sentence_line(bk, rx, cy + 58, w - (rx - x) - 14, "Number sentence", sentence)
    answer_box(bk, rx, cy + 14, model_answer(model), unit)


def c_two_step(bk, x, cy, w, item):
    """Two steps: bars for each step (or a space to draw them), two number sentences, the answer."""
    story, (s1, m1), (s2, m2), answer, unit, bars = item
    tx = x + GUT
    bk.paragraph(tx, cy + 208, w - GUT - 16, story, size=11.5, leading=15, font="AvM")
    c = bk.c
    if bars:
        for j, (m, yy) in enumerate(((m1, cy + 96), (m2, cy + 18))):
            c.setFillColor(T.text2)
            c.setFont("AvD", 9)
            c.drawString(tx, yy + 56 if m[0] == "cmp" else yy + 60, f"Step {j + 1}")
            draw_model(bk, tx, yy, 246, m)
    else:
        bk.work(tx, cy + 12, 250, 140, "Draw the bars")
    rx = tx + 270
    sentence_line(bk, rx, cy + 120, w - (rx - x) - 14, "Step 1", s1)
    sentence_line(bk, rx, cy + 80, w - (rx - x) - 14, "Step 2", s2)
    answer_box(bk, rx, cy + 22, answer, unit)


def learn_bar_models(bk):
    y = bk.new_page("Two-Step Word Problems", "Draw a bar. Find the missing part. Then do the next step.",
                    name_line=False, big=True, footer="WeMath  ·  Two-Step Word Problems")
    c = bk.c
    label(bk, M, y - 6, "Part + part = whole")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 26, "Mia has 35 red beads and 27 blue beads. How many beads?")
    bar_model(bk, M + 14, y - 82, 300, [(35, True), (27, True)], (62, True), size=14)
    color_eq(bk, M + 350, y - 76, [("35", "a"), ("+", "op"), ("27", "b"), ("=", "op"), ("62", None)], 22)
    y -= 104

    label(bk, M, y - 6, "Compare: how many more?")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 26, "Ben has 52 cards. Kim has 34 cards. How many more does Ben have?")
    compare_bars(bk, M + 14, y - 92, 300, 52, 34, "diff", size=14, names=("Ben", "Kim"))
    color_eq(bk, M + 350, y - 76, [("34", "b"), ("+", "op"), ("18", None), ("=", "op"), ("52", "a")], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 11)
    c.drawString(M + 350, y - 96, "Jump up from 34 to 52.")
    y -= 118

    label(bk, M, y - 6, "Two steps: the first answer is a part of the second bar")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 26, "Leo has 24 stickers. He gets 18 more. Then he gives 15 away. How many now?")
    c.setFont("AvD", 9.5)
    c.drawString(M + 14, y - 48, "Step 1")
    bar_model(bk, M + 60, y - 84, 220, [(24, True), (18, True)], (42, True), size=13)
    color_eq(bk, M + 330, y - 76, [("24", "a"), ("+", "op"), ("18", "b"), ("=", "op"), ("42", None)], 18)
    c.setFillColor(T.text2)
    c.setFont("AvD", 9.5)
    c.drawString(M + 14, y - 106, "Step 2")
    bar_model(bk, M + 60, y - 142, 220, [(27, True), (15, True)], (42, True), size=13)
    color_eq(bk, M + 330, y - 134, [("42", "a"), (MINUS, "op"), ("15", "b"), ("=", "op"), ("27", None)], 18)
    y -= 164

    bottom = your_turn(bk, y, h=96)
    bk.ask("bar: your turn pw 46 ? 80")
    c.setFillColor(T.ink)
    c.setFont("Rnd", 12.5)
    c.drawString(M + 120, bottom + 70, "80 kids. 46 are boys. How many girls?")
    bar_model(bk, M + 120, bottom + 14, 240, [(46, True), (34, False)], (80, True), size=14)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 11)
    c.drawString(M + 390, bottom + 40, "Read. Draw.")
    c.drawString(M + 390, bottom + 24, "Write. Answer.")
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: solve one- and two-step word problems within 100 with a bar model (2.OA.1). Ask "
                     "“What is the whole? What are the parts?” “Fewer” can mean add. In two steps, "
                     "the first answer is a part of the second bar.")


def practice_bar_models(bk):
    title = "Two-Step Word Problems: Practice"
    y = bk.new_page(title, "Read. Draw the bar. Write the number sentence. Answer.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    part(1, "Read the bar", "Find the number that goes in the box.",
         [("pw", 34, 25, "whole"), ("cmp", 64, 39, "diff"), ("pw", 45, 27, "part"), ("cmp", 45, 28, "big"),
          ("pw", 48, 37, "whole"), ("cmp", 81, 55, "small"), ("pw", 36, 54, "part"), ("cmp", 70, 46, "diff")],
         2, 84, 10, c_bar, KINDS_30["bar"].key)
    story_key = lambda it: f"story: {it[2]}"
    part(2, "Part and part", "The bar is drawn for you.", [
        ("Ava has 38 red beads and 26 blue beads. How many beads does she have?",
         ("pw", 38, 26, "whole"), "38 + 26 = 64", "beads"),
        ("There are 52 kids at the park. 27 kids are on the swings. The rest are in the sandbox. How many are in "
         "the sandbox?", ("pw", 27, 25, "part"), f"52 {MINUS} 27 = 25", "kids"),
        ("Leo picked 45 apples. Then he picked some more. Now he has 81 apples. How many more did he pick?",
         ("pw", 45, 36, "part"), "45 + 36 = 81", "apples"),
        ("Some birds sat in a tree. 18 birds flew away. Now 47 birds are left. How many birds were there at first?",
         ("pw", 47, 18, "whole"), "47 + 18 = 65", "birds"),
    ], 1, 132, 10, c_story_bar, story_key)
    part(3, "Compare", "The longer bar is the bigger number.", [
        ("Mia has 63 stickers. Sam has 38 stickers. How many more stickers does Mia have?",
         ("cmp", 63, 38, "diff", ("Mia", "Sam")), "38 + 25 = 63", "stickers"),
        ("Ben scored 56 points. Kim scored 19 fewer points than Ben. How many points did Kim score?",
         ("cmp", 56, 37, "small", ("Ben", "Kim")), f"56 {MINUS} 19 = 37", "points"),
        ("Zoe read 28 books. Omar read 17 more books than Zoe. How many books did Omar read?",
         ("cmp", 45, 28, "big", ("Omar", "Zoe")), "28 + 17 = 45", "books"),
        ("Room 2 has 41 kids. That is 16 fewer kids than Room 3. How many kids are in Room 3?",
         ("cmp", 57, 41, "big", ("Room 3", "Room 2")), "41 + 16 = 57", "kids"),
    ], 1, 132, 10, c_story_bar, story_key)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 4, "Draw the bar", "Draw it yourself. Is the whole missing, or a part?")
    for i, story in enumerate(WORDS_30_ONE):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 4, "Draw the bar", "(continued)")
        y = word_card(bk, y, num + i, *story)
    num += len(WORDS_30_ONE)
    y -= 22

    two_key = lambda it: f"story: {it[1][0]}; {it[2][0]}"
    part(5, "Two steps", "The bars are drawn for you. Step 1 helps with step 2.", [
        ("Ava had 25 stickers. She got 18 more. Then she gave 9 away. How many stickers does she have now?",
         ("25 + 18 = 43", ("pw", 25, 18, "whole")), (f"43 {MINUS} 9 = 34", ("pw", 34, 9, "part")), 34, "stickers",
         True),
        ("A class has 14 boys and 16 girls. Then 8 kids go home. How many kids are left?",
         ("14 + 16 = 30", ("pw", 14, 16, "whole")), (f"30 {MINUS} 8 = 22", ("pw", 22, 8, "part")), 22, "kids",
         True),
        ("Sam has 32 marbles. Leo has 15 more than Sam. How many marbles do they have together?",
         ("32 + 15 = 47", ("cmp", 47, 32, "big", ("Leo", "Sam"))), ("32 + 47 = 79", ("pw", 32, 47, "whole")), 79,
         "marbles", True),
    ], 1, 218, 10, c_two_step, two_key)
    part(6, "Two steps on your own", "Draw a bar for each step.", [
        ("A baker made 40 rolls in the morning and 35 in the afternoon. She sold 58. How many rolls are left?",
         ("40 + 35 = 75", None), (f"75 {MINUS} 58 = 17", None), 17, "rolls", False),
        ("Kim had 50¢. She bought a pencil for 25¢ and an eraser for 15¢. How much money is left?",
         ("25¢ + 15¢ = 40¢", None), (f"50¢ {MINUS} 40¢ = 10¢", None), "10¢", "",
         False),
        ("There were 36 kids on a bus. At the first stop, 12 got off. At the next stop, 9 got on. How many kids "
         "are on the bus now?", (f"36 {MINUS} 12 = 24", None), ("24 + 9 = 33", None), 33, "kids", False),
        ("Mia read 23 pages on Monday and 19 pages on Tuesday. Her book has 60 pages. How many pages are left?",
         ("23 + 19 = 42", None), (f"60 {MINUS} 42 = 18", None), 18, "pages", False),
        ("Challenge: Ben has 28 cards. Kai has 9 more than Ben. Zoe has 5 fewer than Kai. How many cards does "
         "Zoe have?", ("28 + 9 = 37", None), (f"37 {MINUS} 5 = 32", None), 32, "cards", False),
    ], 1, 218, 10, c_two_step, two_key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(7, "Remember?", "Problems from earlier packets.", REVIEW_30, 3, 42, 8, plain, lambda t: t)


WORDS_30_ONE = [
    ("A box has 75 crayons. 48 of them are broken. How many crayons are not broken?",
     f"75 {MINUS} 48 = 27", "27", "crayons"),
    ("Nia had some shells. She found 26 more. Now she has 60 shells. How many did she have at first?",
     f"60 {MINUS} 26 = 34", "34", "shells"),
    ("Jay has 37 cards. Kai has 29 more cards than Jay. How many cards does Kai have?", "37 + 29 = 66", "66",
     "cards"),
    ("A train has 92 seats. 55 seats are full. How many seats are empty?", f"92 {MINUS} 55 = 37", "37", "seats"),
]

REVIEW_30 = ["503 − 268 = [235]", "quarter to 9 = [8:45]", "45¢ + 45¢ = [90¢]", "6 thirds = [2] wholes",
             "half of 64 = [32]", "406 − 179 = [227]"]

TWO_STEP = []
for _i, (_a, _b, _c) in enumerate([(a, b, c) for a in rng(14, 48, 3) for b in rng(11, 29, 4) for c in rng(6, 19, 4)
                                   if c < a + b]):
    _n = NAMES[_i % len(NAMES)]
    _t = THINGS[_i % len(THINGS)]
    TWO_STEP.append((f"{_n} had {_a} {_t}. {_n} got {_b} more, then gave {_c} away. How many {_t} are left?",
                     (f"{_a} + {_b} = {_a + _b}", ("pw", _a, _b, "whole")),
                     (f"{_a + _b} {MINUS} {_c} = {_a + _b - _c}", ("pw", _a + _b - _c, _c, "part")),
                     _a + _b - _c, _t, True))

KINDS_30 = {
    "bar": Kind(84, 2, lambda m: f"bar: {' '.join(map(str, m[:4]))}", c_bar),
    "two_step": Kind(218, 1, lambda it: f"story: {it[1][0]}; {it[2][0]}", c_two_step, 8),
}
KINDS.update(KINDS_30)

BARS = ([("pw", a, b, u) for a in rng(23, 58, 5) for b in rng(14, 41, 3) for u in ("whole", "part")]
        + [("cmp", big, small, u) for big in rng(41, 95, 6) for small in rng(17, 38, 4) if big - small > 8
           for u in ("diff", "big", "small")])

CHECKINS["30-two-step-word-problems"] = [
    S("Read the bar", "Find the number that goes in the box.", "bar", BARS, 4),
    S("Two steps", None, "two_step", TWO_STEP, 1),
    S("One step", "Draw a bar if it helps.", "word", stories("w30a", "compare", [(a, b) for a in rng(40, 95, 7) for b in rng(15, 38, 5)])
      + stories("w30b", "sub", [(a, b) for a in rng(41, 96, 5) for b in rng(13, 39, 6)]), 1),
]
_g2[-1:-1] = [
    S("Read the bar", None, "bar", BARS, 2, 30),
]


# ====================================================================== 31. Measuring Length

INCH = 72.0            # a PDF point is 1/72 inch, so these are true size when printed at 100%
CM = 72.0 / 2.54
UNIT = {"in": (INCH, "inches", "inch"), "cm": (CM, "centimeters", "centimeter")}
LENGTH_COLORS = {"pencil": ("#ffd43b", "#c99a00"), "crayon": ("#4c8df6", "#2a62c9"), "ribbon": ("#f783ac", "#c2255c"),
                 "straw": ("#69db7c", "#2b8a3e"), "tape": ("#fff3bf", "#d9a400")}


def length_object(bk, kind, x, y, length, h=12):
    """Something to measure, lying flat: its left end at x, centred on y."""
    c = bk.c
    fill, line = LENGTH_COLORS[kind]
    _paint(c, fill, line, 1)
    if kind == "pencil":
        tip = min(14, length * 0.2)
        c.rect(x, y - h / 2, 6, h, stroke=1, fill=0)                    # eraser end
        c.rect(x + 6, y - h / 2, length - tip - 6, h, stroke=1, fill=1)
        c.drawPath(_poly(c, [(x + length - tip, y - h / 2), (x + length, y), (x + length - tip, y + h / 2)]),
                   stroke=1, fill=0)
    elif kind == "crayon":
        tip = min(10, length * 0.15)
        c.roundRect(x, y - h / 2, length - tip, h, 2, stroke=1, fill=1)
        c.drawPath(_poly(c, [(x + length - tip, y - h / 2 + 2), (x + length, y), (x + length - tip, y + h / 2 - 2)]),
                   stroke=1, fill=1)
        c.setStrokeColor(white if T.color else T.ink)
        c.line(x + 8, y - h / 2 + 2, x + 8, y + h / 2 - 2)
    elif kind == "ribbon":
        c.drawPath(_poly(c, [(x, y - h / 2), (x + length, y - h / 2), (x + length - 5, y), (x + length, y + h / 2),
                             (x, y + h / 2), (x + 5, y)]), stroke=1, fill=1)
    else:  # straw
        c.roundRect(x, y - h * 0.3, length, h * 0.6, h * 0.3, stroke=1, fill=1)


def tape_measure(bk, x, y, n, unit, h=24, start_label=True):
    """A measuring tape from 0 to n, its 0 at x; y = bottom. Halves get short ticks."""
    c = bk.c
    u = UNIT[unit][0]
    fill, line = LENGTH_COLORS["tape"]
    _paint(c, fill, line, 0.9)
    c.rect(x - 6, y, n * u + 12, h, stroke=1, fill=1)
    c.setStrokeColor(T.ink)
    for i in range(2 * n + 1):
        tx = x + i * u / 2
        whole = i % 2 == 0
        c.setLineWidth(0.9 if whole else 0.6)
        c.line(tx, y + h, tx, y + h - (h * 0.45 if whole else h * 0.25))
    c.setFillColor(T.ink)
    size = 9 if unit == "cm" else 10
    c.setFont("AvD", size)
    for i in range(n + 1):
        c.drawCentredString(x + i * u, y + 4, str(i))
    c.setFillColor(T.text2)
    c.setFont("Av", 7.5)
    c.drawString(x + n * u + 10, y + h / 2 - 3, unit)


def clip(bk, x, y, w=36, h=11):
    """A paper clip lying flat; left end at x, centred on y."""
    c = bk.c
    c.setStrokeColor(T.text2)
    c.setLineWidth(1.3)
    c.roundRect(x, y - h / 2, w, h, h / 2, stroke=1, fill=0)
    c.roundRect(x + 4, y - h / 2 + 2.5, w - 11, h - 5, (h - 5) / 2, stroke=1, fill=0)


def c_clips(bk, x, cy, w, item):
    kind, n = item
    clip_w = 36
    length_object(bk, kind, x + GUT, cy + 52, n * clip_w)
    for i in range(n):
        clip(bk, x + GUT + i * clip_w, cy + 34, clip_w)
    bk.fit_eq(x + GUT, cy + 8, w - GUT - 10, f"[{n}] paper clips", size=15)


def c_read_tape(bk, x, cy, w, item):
    """Read the length off a tape. item = (kind, length, unit, start)."""
    kind, n, unit, start = item
    u = UNIT[unit][0]
    tape_measure(bk, x + GUT, cy + 10, max(start + n + 1, 6 if unit == "in" else 12), unit)
    length_object(bk, kind, x + GUT + start * u, cy + 48, n * u)
    for sx in (start, start + n):
        bk.c.setStrokeColor(T.muted)
        bk.c.setLineWidth(0.6)
        bk.c.setDash(2, 2)
        bk.c.line(x + GUT + sx * u, cy + 34, x + GUT + sx * u, cy + 56)
        bk.c.setDash()
    bk.eq(x + GUT, cy + 70, f"[{n}] {UNIT[unit][1]}", size=15)


def c_two_units(bk, x, cy, w, item):
    """The same thing on an inch tape and a centimeter tape."""
    kind, inches = item
    cms = round(inches * 2.54)
    length_object(bk, kind, x + GUT, cy + 128, inches * INCH)
    tape_measure(bk, x + GUT, cy + 92, 6, "in", h=22)
    tape_measure(bk, x + GUT, cy + 62, 15, "cm", h=22)
    bk.eq(x + GUT, cy + 38, f"[{inches}] inches", size=14)
    bk.eq(x + GUT + 120, cy + 38, f"about [{cms}] centimeters", size=14)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("Av", 10)
    bk.c.drawString(x + GUT, cy + 12, "Which needs more units?")
    circle_choice(bk, x + GUT + 130, cy + 12, ["inches", "centimeters"], "centimeters", size=11, gap=12)


def c_measure_real(bk, x, cy, w, item):
    """True size: measure with a real ruler or tape measure."""
    kind, n, unit = item
    length_object(bk, kind, x + GUT, cy + 22, n * UNIT[unit][0], h=10)
    bk.eq(x + w - 84, cy + 15, f"[{n}] {'in' if unit == 'in' else 'cm'}", size=16)


def c_unit_choice(bk, x, cy, w, item):
    text, choices, right = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 15, text)
    circle_choice(bk, x + w - 166, cy + 15, choices, right, size=11.5, gap=12)


def c_longer(bk, x, cy, w, item):
    """Two things on one centimeter tape: read both, then how much longer."""
    (k1, a), (k2, b) = item
    tape_measure(bk, x + GUT, cy + 8, 15, "cm")
    length_object(bk, k1, x + GUT, cy + 62, a * CM)
    length_object(bk, k2, x + GUT, cy + 42, b * CM)
    bk.eq(x + GUT, cy + 86, f"{k1} [{a}] cm", size=13)
    bk.eq(x + GUT + 130, cy + 86, f"{k2} [{b}] cm", size=13)
    bk.eq(x + GUT + 260, cy + 86, f"The {k1} is [{a - b}] cm longer", size=13)


def learn_length(bk):
    y = bk.new_page("Measuring Length", "Line up the end with 0. Count the units.", name_line=False, big=True,
                    footer="WeMath  ·  Measuring Length")
    c = bk.c
    label(bk, M, y - 6, "Start at 0")
    length_object(bk, "pencil", M + 20, y - 28, 4 * INCH, h=13)
    tape_measure(bk, M + 20, y - 66, 5, "in", h=26)
    color_eq(bk, M + 430, y - 50, [("4", "b"), ("inches", None)], 22)
    y -= 92

    label(bk, M, y - 6, "No gaps, no overlaps")
    length_object(bk, "crayon", M + 20, y - 28, 3 * 36)
    for i in range(3):
        clip(bk, M + 20 + i * 36, y - 46, 36)
    color_eq(bk, M + 200, y - 44, [("3", "b"), ("paper clips", None)], 22)
    y -= 80

    label(bk, M, y - 6, "Same ribbon, two units")
    length_object(bk, "ribbon", M + 20, y - 28, 2 * INCH, h=13)
    tape_measure(bk, M + 20, y - 64, 3, "in", h=22)
    tape_measure(bk, M + 20, y - 94, 7, "cm", h=22)
    color_eq(bk, M + 260, y - 46, [("2", "a"), ("inches", None)], 20)
    color_eq(bk, M + 260, y - 76, [("about", None), ("5", "b"), ("centimeters", None)], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 11.5)
    c.drawString(M + 260, y - 96, "Smaller units, so more of them.")
    y -= 118

    label(bk, M, y - 6, "Not at 0? Count the units")
    tape_measure(bk, M + 20, y - 66, 10, "cm", h=24)
    length_object(bk, "straw", M + 20 + 3 * CM, y - 30, 5 * CM, h=13)
    color_eq(bk, M + 340, y - 50, [("8", None), (MINUS, "op"), ("3", None), ("=", "op"), ("5", "b"), ("cm", None)], 20)
    y -= 88

    bottom = your_turn(bk, y, h=92)
    bk.ask("tape: crayon 7 cm your turn")
    tape_measure(bk, M + 120, bottom + 14, 9, "cm", h=24)
    length_object(bk, "crayon", M + 120, bottom + 54, 7 * CM)
    bk.eq(M + 120 + 9 * CM + 36, bottom + 30, "[7] cm", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: measure in inches and centimeters with a ruler or tape measure (2.MD.1–4). Line "
                     "the end up with 0, not 1. Print at 100% so the true-size problems match a real ruler. Say: "
                     "“smaller units, so more of them.”")


def practice_length(bk):
    title = "Measuring Length: Practice"
    y = bk.new_page(title, "Line up the end with 0. Count the units.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    part(1, "Paper clips", "Count the clips. No gaps, no overlaps.",
         [("pencil", 4), ("straw", 3), ("crayon", 5), ("ribbon", 2), ("pencil", 3), ("straw", 5)], 2, 74, 10, c_clips,
         lambda it: f"clips: {it[0]} {it[1]}")
    tape_key = KINDS_31["read_tape"].key
    part(2, "Inches", "Read the tape at the end of the object.",
         [("pencil", 5, "in", 0), ("ribbon", 3, "in", 0), ("straw", 4, "in", 0), ("crayon", 2, "in", 0)],
         1, 92, 8, c_read_tape, tape_key)
    part(3, "Centimeters", None,
         [("crayon", 9, "cm", 0), ("pencil", 13, "cm", 0), ("ribbon", 6, "cm", 0), ("straw", 11, "cm", 0)],
         1, 92, 8, c_read_tape, tape_key)
    part(4, "Not at 0", "Count the units between the ends.",
         [("straw", 6, "cm", 2), ("pencil", 3, "in", 1), ("ribbon", 8, "cm", 4), ("crayon", 4, "cm", 5)],
         1, 92, 8, c_read_tape, tape_key)
    part(5, "Two units", "Same thing, two tapes. Which needs more units?",
         [("ribbon", 4), ("straw", 6), ("pencil", 2)], 1, 150, 8, c_two_units, KINDS_31["two_units"].key)
    part(6, "Measure with your ruler", "Use a ruler or a tape measure. Start at 0.",
         [("pencil", 3, "in"), ("straw", 12, "cm"), ("ribbon", 5, "in"), ("crayon", 8, "cm"), ("pencil", 10, "cm"),
          ("straw", 2, "in")], 1, 44, 8, c_measure_real, lambda it: f"measure: {it[0]} {it[1]} {it[2]}")
    part(7, "How much longer?", "Read both. Then find how much longer.",
         [(("ribbon", 12), ("straw", 7)), (("pencil", 14), ("crayon", 9)), (("straw", 10), ("ribbon", 4))],
         1, 108, 8, c_longer, lambda it: f"longer: {it[0][1]} {it[1][1]}")
    part(8, "Which unit?", "Circle the unit that makes sense.", ESTIMATES[:10], 1, 40, 6, c_unit_choice,
         KINDS_31["unit_choice"].key)

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(9, "Add and subtract lengths", "No help this time. Keep the unit.",
         ["12 cm + 9 cm = [21] cm", "35 in + 18 in = [53] in", f"40 cm {MINUS} 16 cm = [24] cm",
          "27 cm + 27 cm = [54] cm", f"60 in {MINUS} 35 in = [25] in", "48 cm + 15 cm = [63] cm",
          f"91 cm {MINUS} 46 cm = [45] cm", "19 in + 33 in = [52] in", f"75 cm {MINUS} 38 cm = [37] cm"],
         2, 42, 8, plain, lambda t: t)
    part(10, "Feet, inches and meters", "No help this time.",
         ["1 foot = [12] inches", "1 meter = [100] centimeters", "6 inches + 6 inches = [1] foot",
          "50 cm + 50 cm = [1] meter", "1 foot + 1 foot = [24] inches", "1 yard = [3] feet"], 2, 42, 8, plain,
         lambda t: t)
    part(11, "Remember?", "Problems from earlier packets.", REVIEW_31, 3, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 12, "Word problems", "Draw a bar. Keep the unit.")
    for i, story in enumerate(WORDS_31):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 12, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


ESTIMATES = [("A door is about 2", ["centimeters", "meters"], "meters"),
             ("A crayon is about 9", ["centimeters", "meters"], "centimeters"),
             ("A car is about 4", ["centimeters", "meters"], "meters"),
             ("A book is about 10", ["inches", "feet"], "inches"),
             ("A bed is about 6", ["inches", "feet"], "feet"),
             ("A paper clip is about 3", ["centimeters", "meters"], "centimeters"),
             ("A classroom is about 30", ["inches", "feet"], "feet"),
             ("A spoon is about 6", ["inches", "feet"], "inches"),
             ("A school bus is about 12", ["centimeters", "meters"], "meters"),
             ("A shoe is about 8", ["inches", "feet"], "inches"),
             ("A tall tree is about 15", ["centimeters", "meters"], "meters"),
             ("An eraser is about 5", ["centimeters", "meters"], "centimeters"),
             ("A couch is about 7", ["inches", "feet"], "feet"),
             ("A cell phone is about 6", ["inches", "feet"], "inches")]

REVIEW_31 = ["quarter past 11 = [11:15]", "70¢ + 25¢ = [95¢]", f"600 {MINUS} 237 = [363]",
             "2 thirds + 1 third = [1] whole", "57 + [43] = 100", "half of 38 = [19]"]

WORDS_31 = [
    ("A red ribbon is 45 cm long. A blue ribbon is 28 cm long. How much longer is the red ribbon?",
     "28 cm + 17 cm = 45 cm", "17", "cm"),
    ("Mia's desk is 36 inches tall. Her chair is 18 inches tall. How much taller is the desk?",
     f"36 in {MINUS} 18 in = 18 in", "18", "inches"),
    ("Leo tapes two strings together. One is 24 cm and the other is 39 cm. How long is the new string?",
     "24 cm + 39 cm = 63 cm", "63", "cm"),
    ("A plant was 15 cm tall. Now it is 42 cm tall. How many centimeters did it grow?",
     "15 cm + 27 cm = 42 cm", "27", "cm"),
    ("Challenge: A path is 80 m long. Ben walks 35 m, then 25 m more. How far is the rest of the path?",
     "35 + 25 = 60, 80 − 60 = 20", "20", "m"),
]

KINDS_31 = {
    "read_tape": Kind(92, 1, lambda it: f"tape: {it[0]} {it[1]} {it[2]} from {it[3]}", c_read_tape, 8),
    "two_units": Kind(150, 1, lambda it: f"two units: {it[0]} {it[1]}", c_two_units, 8),
    "unit_choice": Kind(40, 1, lambda it: f"unit: {it[0]}", c_unit_choice, 6),
}
KINDS.update(KINDS_31)
BALANCE["unit_choice"] = lambda it: it[2] == it[1][0]

TAPES = ([(k, n, "cm", s) for k in ("pencil", "crayon", "ribbon", "straw") for n in rng(3, 12) for s in (0, 0, 2, 3)
          if s + n <= 14] + [(k, n, "in", s) for k in ("pencil", "crayon", "ribbon", "straw") for n in rng(2, 5)
                             for s in (0, 1) if s + n <= 6])
LENGTH_EQS = ([f"{a} cm + {b} cm = [{a + b}] cm" for a in rng(13, 58, 5) for b in rng(11, 39, 4)]
              + [f"{a} cm {MINUS} {b} cm = [{a - b}] cm" for a in rng(41, 96, 5) for b in rng(12, 38, 3)])

CHECKINS["31-measuring-length"] = [
    S("Read the tape", None, "read_tape", TAPES, 3),
    S("Which unit?", None, "unit_choice", ESTIMATES, 3),
    S("Add and subtract lengths", None, "eq2", LENGTH_EQS, 2),
]
_g2[-1:-1] = [
    S("Measuring length", None, "read_tape", TAPES, 2, 31),
    S("Adding and subtracting lengths", None, "eq2", LENGTH_EQS, 2, 31),
]


# ====================================================================== 32. Graphs


def tally(bk, x, y, n, h=18, step=6, color=None):
    """Tally marks: groups of 5 (four lines and a slash). y = bottom. Returns the width."""
    c = bk.c
    c.setStrokeColor(color or T.ink)
    c.setLineWidth(1.5)
    c.setLineCap(1)
    cx = x
    for g in range(0, n, 5):
        k = min(5, n - g)
        for i in range(min(k, 4)):
            c.line(cx + i * step, y, cx + i * step, y + h)
        if k == 5:
            c.line(cx - 3, y + 3, cx + 3 * step + 3, y + h - 3)
        cx += 4 * step + 10
    c.setLineCap(0)
    return cx - x - 10


def picture_graph(bk, x, top, title, cats, counts, kind, cell=17, labw=56, show=True):
    """Rows of icons, one row per category, each icon = 1. show=False leaves the rows empty (the key
    fills them). Returns the bottom y."""
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("AvD", 10.5)
    c.drawString(x, top - 10, title)
    y = top - 22
    for cat, n in zip(cats, counts):
        y -= cell + 4
        c.setFillColor(T.text2)
        c.setFont("AvM", 10)
        c.drawString(x, y + cell / 2 - 3.5, cat)
        c.setStrokeColor(T.line)
        c.setLineWidth(0.6)
        c.line(x + labw - 6, y - 2, x + labw + 10 * cell, y - 2)
        if show or bk.key:
            for i in range(n):
                icon(bk, kind, x + labw + cell / 2 + i * cell, y + cell / 2, cell * 0.82)
    c.setFillColor(T.text2)
    c.setFont("Av", 8.5)
    c.drawString(x, y - 16, "Each")
    icon(bk, kind, x + 30, y - 13, 11)
    c.setFillColor(T.text2)
    c.setFont("Av", 8.5)
    c.drawString(x + 40, y - 16, "= 1")
    return y - 22


def bar_graph(bk, x, top, title, cats, counts, maxv=10, cell=11, barw=34, show=True):
    """Bars on a square grid with a 0–maxv scale. show=False: an empty grid (the key colours the bars).
    Returns the bottom y."""
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("AvD", 10.5)
    c.drawString(x, top - 10, title)
    gx, gy = x + 20, top - 24 - maxv * cell
    gw = len(cats) * (barw + 10) + 10
    if show or bk.key:
        for i, n in enumerate(counts):
            bx = gx + 10 + i * (barw + 10)
            fill = (T.band if show else T.share_ans) if T.color else None
            if fill is not None:
                c.setFillColor(fill)
                c.rect(bx, gy, barw, n * cell, stroke=0, fill=1)
            elif not show:  # black-and-white key: hatch the bar
                shade(bk, [(bx, gy), (bx + barw, gy), (bx + barw, gy + n * cell), (bx, gy + n * cell)], answer=True)
            c.setStrokeColor(T.dot_a if show and T.color else T.answer if not show else T.ink)
            c.setLineWidth(1.2)
            c.rect(bx, gy, barw, n * cell, stroke=1, fill=0)
    c.setStrokeColor(T.line)
    c.setLineWidth(0.5)
    for j in range(1, maxv + 1):
        c.line(gx, gy + j * cell, gx + gw, gy + j * cell)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1)
    c.line(gx, gy, gx + gw, gy)
    c.line(gx, gy, gx, gy + maxv * cell)
    c.setFillColor(T.text2)
    c.setFont("AvD", 7.5)
    for j in range(0, maxv + 1, 2):
        c.drawRightString(gx - 4, gy + j * cell - 2.5, str(j))
    c.setFont("AvM", 8.5)
    for i, cat in enumerate(cats):
        c.drawCentredString(gx + 10 + i * (barw + 10) + barw / 2, gy - 11, cat)
    return gy - 16


def x_chart(bk, x, top, title, labels, counts, colw=40, cell=13, show=True):
    """A line plot without the line: a labelled box for each value, with an X above it for each one."""
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("AvD", 10.5)
    c.drawString(x, top - 10, title)
    by = top - 30 - max(counts) * cell - 4
    for i, (lab, n) in enumerate(zip(labels, counts)):
        bx = x + i * colw
        c.setStrokeColor(T.ink)
        c.setLineWidth(0.9)
        c.rect(bx, by - 16, colw, 16, stroke=1, fill=0)
        c.setFillColor(T.text2)
        c.setFont("AvM", 8.5)
        c.drawCentredString(bx + colw / 2, by - 11.5, lab)
        if show or bk.key:
            c.setFillColor(T.ink if show else T.answer)
            c.setFont("AvD", 12)
            for j in range(n):
                c.drawCentredString(bx + colw / 2, by + 3 + j * cell, "X")
    return by - 20


def graph_questions(bk, x, top, w, qs, size=12.5, gap=30):
    """Questions with answer boxes, one per line."""
    for i, (text, ans) in enumerate(qs):
        yy = top - i * gap
        bk.c.setFillColor(T.ink)
        bk.c.setFont("AvM", 10.5)
        bk.c.drawString(x, yy, text)
        bw = max(30, sw(str(ans), "Rnd", size) + 14)
        bk.box(x + w - bw, yy - 6, bw, size * 1.55, ans, size=size)


def graph_qs(cats, counts, noun, rng_seed):
    """Four questions about a graph: how many, how many more, in all, two together."""
    r = random.Random(rng_seed)
    order = sorted(range(len(cats)), key=lambda i: -counts[i])
    big, small = order[0], order[-1]
    a, b = r.sample(range(len(cats)), 2)
    one = r.choice([i for i in range(len(cats)) if i not in (big, small)] or [a])
    return [(f"How many {noun} {cats[one]}?", counts[one]),
            (f"How many more {cats[big]} than {cats[small]}?", counts[big] - counts[small]),
            (f"{cats[a].capitalize()} and {cats[b]} together?", counts[a] + counts[b]),
            ("How many in all?", sum(counts))]


def c_graph(bk, x, cy, w, item):
    """A graph and four questions. item = (type, title, cats, counts, noun_or_kind, qs)."""
    gtype, title, cats, counts, extra, qs = item
    gx = x + GUT + 14  # room for a "24–27)" problem number
    if gtype == "pic":
        picture_graph(bk, gx, cy + 168, title, cats, counts, extra)
    elif gtype == "bar":
        bar_graph(bk, gx, cy + 168, title, cats, counts)
    else:
        x_chart(bk, gx, cy + 168, title, cats, counts)
    graph_questions(bk, x + GUT + 236, cy + 140, w - GUT - 248, qs)


def c_make_graph(bk, x, cy, w, item):
    """A tally table on the left, an empty graph on the right to fill in."""
    gtype, title, cats, counts, kind = item
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("AvD", 10.5)
    c.drawString(x + GUT, cy + 158, title)
    for i, (cat, n) in enumerate(zip(cats, counts)):
        yy = cy + 128 - i * 28
        c.setFillColor(T.text2)
        c.setFont("AvM", 10)
        c.drawString(x + GUT, yy + 4, cat)
        tally(bk, x + GUT + 64, yy, n, h=16)
    if gtype == "pic":
        picture_graph(bk, x + GUT + 200, cy + 168, "Make the picture graph", cats, counts, kind, cell=16, labw=56,
                      show=False)
    else:
        bar_graph(bk, x + GUT + 210, cy + 168, "Make the bar graph", cats, counts, show=False)


def c_tally_read(bk, x, cy, w, n):
    tally(bk, x + GUT, cy + 12, n, h=18)
    bk.eq(x + w - 60, cy + 14, f"[{n}]", size=17)


def c_tally_draw(bk, x, cy, w, n):
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 15)
    bk.c.drawString(x + GUT, cy + 18, str(n))
    if bk.key:
        tally(bk, x + GUT + 36, cy + 12, n, h=18, color=T.answer)


def c_mini_bar(bk, x, cy, w, item):
    """Check-in card: a small bar graph and one question."""
    title, cats, counts, (q, ans), _ = item
    bar_graph(bk, x + GUT, cy + 168, title, cats, counts, cell=9, barw=26)
    graph_questions(bk, x + GUT, cy + 18, w - GUT - 12, [(q, ans)])


def learn_graphs(bk):
    y = bk.new_page("Graphs", "Count. Show it in a graph. Ask questions.", name_line=False, big=True,
                    footer="WeMath  ·  Graphs")
    c = bk.c
    cats, counts = ["apples", "cookies", "cupcakes"], [7, 4, 5]
    label(bk, M, y - 6, "Tally marks: count by 5s")
    for i, (cat, n) in enumerate(zip(cats, counts)):
        yy = y - 32 - i * 24
        c.setFillColor(T.text2)
        c.setFont("AvM", 11)
        c.drawString(M + 14, yy + 3, cat)
        tally(bk, M + 90, yy, n, h=16)
        color_eq(bk, M + 170, yy + 2, [(str(n), "a")], 15)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 240, y - 34, "4 lines and a slash is 5.")
    c.drawString(M + 240, y - 52, "Count 5, then count on: 5, 6, 7.")
    y -= 104

    label(bk, M, y - 6, "Picture graph")
    picture_graph(bk, M + 14, y - 14, "Our favorite snack", cats, counts, "star", cell=17)
    label(bk, M + 280, y - 6, "Bar graph")
    bar_graph(bk, M + 294, y - 14, "Our favorite snack", cats, counts, maxv=8, cell=11)
    y -= 150

    label(bk, M, y - 6, "Ask questions")
    color_eq(bk, M + 14, y - 36, [("7", "a"), (MINUS, "op"), ("4", "b"), ("=", "op"), ("3", None)], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 120, y - 36, "3 more apples than cookies")
    color_eq(bk, M + 14, y - 64, [("7", "a"), ("+", "op"), ("4", "b"), ("+", "op"), ("5", "a"), ("=", "op"),
                                  ("16", None)], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 190, y - 64, "16 kids in all")
    y -= 86

    bottom = your_turn(bk, y, h=96)
    bk.ask("graph your turn: cupcakes and cookies")
    c.setFillColor(T.ink)
    c.setFont("AvM", 12)
    c.drawString(M + 130, bottom + 62, "How many more cupcakes than cookies?")
    c.drawString(M + 130, bottom + 30, "How many like cupcakes or cookies?")
    bk.box(M + 400, bottom + 54, 34, 22, 1, size=14)
    bk.box(M + 400, bottom + 22, 34, 22, 9, size=14)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: read and make tally charts, picture graphs and bar graphs, and answer how many, how "
                     "many more and how many in all (2.MD.10). X charts show lengths (2.MD.9). Make graphs of the "
                     "group's real data.")


GRAPHS_32 = [
    ("pic", "Pets at home", ["dogs", "cats", "fish"], [6, 4, 7], "star", "kids have"),
    ("pic", "Fruit we ate", ["apples", "pears", "plums"], [8, 3, 5], "apple", "kids ate"),
    ("bar", "Favorite color", ["red", "blue", "green", "pink"], [5, 9, 3, 6], None, "kids like"),
    ("bar", "Books we read", ["Mon", "Tue", "Wed", "Thu"], [4, 7, 8, 2], None, "books on"),
    ("bar", "Birds we saw", ["robins", "crows", "ducks"], [10, 6, 3], None, "were"),
]
X_CHARTS_32 = [
    ("Pencil lengths (inches)", ["3 in", "4 in", "5 in", "6 in", "7 in"], [2, 5, 3, 1, 2],
     [("How many pencils are 4 in long?", 5), ("How many are longer than 5 in?", 3),
      ("How many pencils in all?", 13)]),
    ("Leaf lengths (cm)", ["5 cm", "6 cm", "7 cm", "8 cm", "9 cm"], [1, 3, 4, 4, 2],
     [("How many leaves are 7 cm long?", 4), ("How many are shorter than 7 cm?", 4),
      ("How many leaves in all?", 14)]),
]


def practice_graphs(bk):
    title = "Graphs: Practice"
    y = bk.new_page(title, "Read the graph carefully. Count the rows or the squares.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    part(1, "Count the tally marks", None, [7, 13, 4, 18, 11, 9, 17, 6], 2, 44, 8, c_tally_read,
         lambda n: f"tally read {n}")
    part(2, "Draw tally marks", "Make groups of 5.", [8, 14, 3, 12, 19, 10], 2, 44, 8, c_tally_draw,
         lambda n: f"tally draw {n}")

    def graph_items(gtype):
        out = []
        for i, (t, title_, cats, counts, kind, noun) in enumerate(GRAPHS_32):
            if t == gtype:
                out.append((t, title_, cats, counts, kind, graph_qs(cats, counts, noun, title_)))
        return out

    def graph_part(n, name, sub, items):
        nonlocal y, num
        if y - 14 - 180 < 46:
            y = bk.new_page(title, first=False)
        y = bk.part(y, n, name, sub)
        for item in items:
            if y - 180 < 46:
                y = bk.new_page(title, first=False)
                y = bk.part(y, n, name, "(continued)")
            for q, _ in item[5]:
                bk.ask(f"graph {item[1]}: {q}")
            bk.card(M, y - 180, CW, 180, f"{num}–{num + len(item[5]) - 1}")
            c_graph(bk, M, y - 180, CW, item)
            num += len(item[5])
            y -= 190
        y -= 22

    graph_part(3, "Picture graphs", "Each picture is 1.", graph_items("pic"))
    part(4, "Make a picture graph", "Draw a circle for each tally mark.",
         [("pic", "Toys in the box", ["cars", "balls", "dolls"], [5, 8, 3], "star")], 1, 180, 10, c_make_graph,
         lambda it: f"make graph: {it[1]}")
    graph_part(5, "Bar graphs", "Read across from the top of the bar.", graph_items("bar"))
    part(6, "Make a bar graph", "Color one square for each tally mark.",
         [("bar", "Snacks sold", ["chips", "fruit", "milk", "nuts"], [6, 9, 4, 7], None)], 1, 180, 10,
         c_make_graph, lambda it: f"make graph: {it[1]}")
    graph_part(7, "X charts", "Each X is one thing that was measured.",
               [("x", t, labels, counts, None, qs) for t, labels, counts, qs in X_CHARTS_32])
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(8, "Remember?", "Problems from earlier packets.", REVIEW_32, 3, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Make a tally chart if it helps.")
    for i, story in enumerate(WORDS_32):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_32 = ["30 cm + 25 cm = [55] cm", "half past 4 = [4:30]", "3 quarters = [75¢]", f"800 {MINUS} 356 = [444]",
             "4 fourths = [1] whole", "half of 78 = [39]"]

WORDS_32 = [
    ("A bar graph shows 9 kids like soccer and 6 kids like tag. How many more kids like soccer?",
     "6 + 3 = 9", "3", "kids"),
    ("A tally chart shows 3 groups of 5 and 2 more marks. How many marks is that?", "5 + 5 + 5 + 2 = 17", "17",
     "marks"),
    ("A picture graph shows 7 cats and 8 dogs. How many pets in all?", "7 + 8 = 15", "15", "pets"),
    ("A class voted: 12 for pizza, 5 for tacos. How many fewer votes did tacos get?", "5 + 7 = 12", "7", "votes"),
    ("Challenge: 20 kids voted: 8 for red, 5 for blue, the rest for green. How many voted for green?",
     "8 + 5 = 13, 13 + 7 = 20", "7", "kids"),
]

KINDS_32 = {
    "tally_read": Kind(44, 2, lambda n: f"tally read {n}", c_tally_read, 8),
    "tally_draw": Kind(44, 2, lambda n: f"tally draw {n}", c_tally_draw, 8),
    "mini_bar": Kind(170, 2, lambda it: f"mini graph {it[4]}: {it[3][0]}", c_mini_bar),
}
KINDS.update(KINDS_32)

_MINI_DATA = [("Pets", ["dogs", "cats", "fish"]), ("Recess games", ["tag", "ball", "jump"]),
              ("Lunch", ["pizza", "tacos", "soup"]), ("Weather", ["sun", "rain", "snow"])]
MINI_BARS = []
for _i, (_t, _cats) in enumerate(_MINI_DATA * 4):
    _r = random.Random(f"mini{_i}")
    _counts = _r.sample(range(2, 11), 3)
    _q = graph_qs(_cats, _counts, "kids picked", f"mini{_i}")[_i % 4]
    MINI_BARS.append((_t, _cats, _counts, _q, _i))

CHECKINS["32-graphs"] = [
    S("Count the tally marks", None, "tally_read", list(rng(6, 18)), 3),
    S("Draw tally marks", None, "tally_draw", list(rng(6, 18)), 3),
    S("Read the bar graph", None, "mini_bar", MINI_BARS, 2),
]
_g2[-1:-1] = [
    S("Graphs", None, "mini_bar", MINI_BARS, 2, 32),
]


# ====================================================================== 33. Multiplication

TIMES = "×"


def X(a, b):
    """'3 × 4 = [12]'"""
    return f"{a} {TIMES} {b} = [{a * b}]"


def c_times_groups(bk, x, cy, w, item):
    g, n = item
    groups_picture(bk, x + GUT, cy + 82, [n] * g, R=15, gap=7)
    bk.fit_eq(x + GUT, cy + 42, w - GUT - 10, f"[{g}] groups of [{n}]", size=15)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"[{g}] {TIMES} [{n}] = [{g * n}]", size=15)


def c_times_add(bk, x, cy, w, item):
    n, g = item
    bk.fit_eq(x + GUT, cy + 40, w - GUT - 10, " + ".join([str(n)] * g) + f" = [{n * g}]", size=15)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"[{g}] {TIMES} [{n}] = [{n * g}]", size=15)


def c_times_array(bk, x, cy, w, item):
    r, k = item
    array_picture(bk, x + GUT, cy + 74, r, k, step=13, r=4.4)
    tx = x + GUT + 90
    bk.fit_eq(tx, cy + 50, w - (tx - x) - 8, f"[{r}] rows of [{k}]", size=15)
    bk.fit_eq(tx, cy + 18, w - (tx - x) - 8, f"[{r}] {TIMES} [{k}] = [{r * k}]", size=15)


def c_times_turn(bk, x, cy, w, item):
    r, k = item
    array_picture(bk, x + GUT, cy + 84, r, k, step=13, r=4.4)
    tx = x + GUT + 112
    for j, (lab, a, b) in enumerate((("rows", r, k), ("columns", k, r))):
        bk.c.setFillColor(T.text2)
        bk.c.setFont("AvD", 9)
        bk.c.drawString(tx, cy + 66 - j * 36, lab)
        bk.fit_eq(tx, cy + 48 - j * 36, w - (tx - x) - 8, f"{a} {TIMES} {b} = [{a * b}]", size=14)


def c_times_draw(bk, x, cy, w, item):
    g, n = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 100, f"Draw {g} groups of {n}.")
    bk.work(x + GUT, cy + 42, w - GUT - 12, 50, "Draw it")
    if bk.key:
        groups_picture(bk, x + GUT + 10, cy + 66, [n] * g, R=13, gap=6)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"[{g}] {TIMES} [{n}] = [{g * n}]", size=15)


def c_times_count(bk, x, cy, w, item):
    n, g = item
    seq = [n * (i + 1) for i in range(g)]
    blanks = tuple(i for i in range(g) if i % 2 == 1 or i == g - 1)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvD", 10)
    bk.c.drawString(x + GUT, cy + 44, f"Count by {n}s, {g} times:")
    count_chain(bk, x + GUT + 130, cy + 42, seq, blanks, spacing=42, size=15, bw=34, arcs=False)
    bk.eq(x + GUT, cy + 12, f"{g} {TIMES} {n} = [{g * n}]", size=16)


def learn_multiplication(bk):
    y = bk.new_page("Multiplication", "Equal groups: count the groups, then how many in each.", name_line=False,
                    big=True, footer="WeMath  ·  Multiplication")
    c = bk.c
    label(bk, M, y - 6, "3 groups of 4")
    groups_picture(bk, M + 14, y - 46, [4, 4, 4], R=22, gap=14)
    color_eq(bk, M + 230, y - 38, [("4", "a"), ("+", "op"), ("4", "b"), ("+", "op"), ("4", "a"), ("=", "op"),
                                   ("12", None)], 22)
    color_eq(bk, M + 230, y - 70, [("3", "a"), (TIMES, "op"), ("4", "b"), ("=", "op"), ("12", None)], 26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 360, y - 70, "say “3 groups of 4”")
    y -= 104

    label(bk, M, y - 6, "An array: rows × how many in each row")
    w_, h_ = array_picture(bk, M + 20, y - 22, 2, 5, step=20, r=6.5, color_by="row")
    color_eq(bk, M + 230, y - 46, [("2", "a"), (TIMES, "op"), ("5", "b"), ("=", "op"), ("10", None)], 26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 360, y - 46, "2 rows of 5")
    y -= 80

    label(bk, M, y - 6, "Turn it around: same dots, same answer")
    array_picture(bk, M + 20, y - 22, 2, 5, step=20, r=6.5, color_by="col")
    color_eq(bk, M + 230, y - 46, [("5", "a"), (TIMES, "op"), ("2", "b"), ("=", "op"), ("10", None)], 26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 360, y - 46, "5 columns of 2")
    y -= 80

    label(bk, M, y - 6, "Count by to multiply")
    count_chain(bk, M + 30, y - 58, [5, 10, 15, 20], (), step="+5", spacing=56, size=20)
    color_eq(bk, M + 270, y - 58, [("4", "a"), (TIMES, "op"), ("5", "b"), ("=", "op"), ("20", None)], 26)
    y -= 88

    bottom = your_turn(bk, y, h=96)
    bk.ask("times groups 4 groups of 2 your turn")
    groups_picture(bk, M + 120, bottom + 62, [2, 2, 2, 2], R=15, gap=8)
    bk.eq(M + 120, bottom + 20, f"[4] {TIMES} [2] = [8]", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: multiplication means equal groups (3.OA.1). Read 3 × 4 as “3 groups of 4.” "
                     "Build on packet 21: 4 + 4 + 4 is 3 × 4. Turnarounds give the same answer. Learn ×2, "
                     "×5 and ×10 by counting by.")


def practice_multiplication(bk):
    title = "Multiplication: Practice"
    y = bk.new_page(title, "Count the groups. Count how many in each. Multiply.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    part(1, "Groups of", "Write the groups, then the multiplication.",
         [(3, 4), (5, 2), (4, 5), (2, 3), (4, 3), (5, 5)], 2, 110, 10, c_times_groups,
         KINDS_33["times_groups"].key)
    part(2, "Add, then multiply", "The same groups, written two ways.",
         [(5, 3), (2, 4), (10, 3), (3, 5), (4, 2), (6, 3), (10, 2), (2, 6)], 2, 70, 10, c_times_add,
         lambda it: f"times add {it[0]} {it[1]}")
    part(3, "Arrays", "Rows times how many in each row.",
         [(2, 4), (3, 5), (4, 4), (5, 2), (2, 6), (3, 3)], 2, 92, 10, c_times_array, KINDS_33["times_array"].key)
    part(4, "Turn it around", "Read the rows, then the columns.",
         [(4, 3), (2, 7), (3, 6), (5, 4)], 2, 100, 10, c_times_turn, lambda it: f"times turn {it[0]} {it[1]}")
    part(5, "Draw it", None, [(2, 5), (3, 2), (5, 3), (4, 4)], 2, 120, 10, c_times_draw,
         lambda it: f"times draw {it[0]} {it[1]}")
    part(6, "Count by", "Fill in the count. The last number is the answer.",
         [(5, 6), (10, 4), (2, 8), (5, 7), (10, 7), (2, 6)], 1, 66, 8, c_times_count,
         lambda it: f"times count {it[0]} {it[1]}")
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(7, "Times 2", "No help this time. Times 2 is a double.",
         [X(*p) for p in ((2, 6), (7, 2), (2, 9), (4, 2), (2, 3), (8, 2), (2, 7), (6, 2), (2, 4))], 3, 42, 8,
         plain, lambda t: t)
    part(8, "Times 10", "No help this time. Count by 10s.",
         [X(*p) for p in ((10, 4), (6, 10), (10, 8), (3, 10), (10, 7), (9, 10), (10, 2), (5, 10), (10, 6))], 3, 42,
         8, plain, lambda t: t)
    part(9, "Times 5", "No help this time. Times 5 is half of times 10.",
         [X(*p) for p in ((5, 3), (8, 5), (5, 6), (4, 5), (5, 9), (7, 5), (5, 2), (6, 5), (5, 8))], 3, 42, 8,
         plain, lambda t: t)
    part(10, "Mixed", "No help this time.",
         [X(*p) for p in ((10, 10), (9, 2), (5, 7), (10, 3), (2, 2), (5, 5), (7, 10), (3, 2), (5, 4), (10, 9),
                          (2, 8), (9, 5))], 3, 42, 8, plain, lambda t: t)
    part(11, "Remember?", "Problems from earlier packets.", REVIEW_33, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 12, "Word problems", "Find the groups and how many in each.")
    for i, story in enumerate(WORDS_33):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 12, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_33 = ["36 cm + 47 cm = [83] cm", "quarter to 2 = [1:45]", "2 quarters + 2 dimes = [70¢]",
             f"900 {MINUS} 418 = [482]", "3 thirds = [1] whole", "57 + 38 = [95]"]

WORDS_33 = [
    ("Mia has 4 bags. Each bag has 5 apples. How many apples does she have?", f"4 {TIMES} 5 = 20", "20", "apples"),
    ("A box of crayons has 3 rows with 10 crayons in each row. How many crayons are in the box?",
     f"3 {TIMES} 10 = 30", "30", "crayons"),
    ("6 kids each wear 2 shoes. How many shoes is that?", f"6 {TIMES} 2 = 12", "12", "shoes"),
    ("Ben buys 7 packs of gum. Each pack has 5 pieces. How many pieces does he have?", f"7 {TIMES} 5 = 35", "35",
     "pieces"),
    ("Challenge: A spider has 8 legs and an ant has 6. How many legs do 2 spiders and 1 ant have?",
     f"2 {TIMES} 8 = 16, 16 + 6 = 22", "22", "legs"),
]

KINDS_33 = {
    "times_groups": Kind(110, 2, lambda it: f"times groups {it[0]} groups of {it[1]}", c_times_groups),
    "times_array": Kind(92, 2, lambda it: f"times array {it[0]} rows of {it[1]}", c_times_array),
}
KINDS.update(KINDS_33)

FACTS_2_5_10 = [X(a, b) for a in rng(2, 10) for b in (2, 5, 10)] + [X(b, a) for a in rng(2, 10) for b in (2, 5, 10)]

CHECKINS["33-multiplication"] = [
    S("Groups of", None, "times_groups", [(g, n) for g in rng(2, 5) for n in rng(2, 5)], 2),
    S("Arrays", None, "times_array", [(r, k) for r in rng(2, 5) for k in rng(2, 6)], 2),
    S("Times 2, 5 and 10", None, "eq3", FACTS_2_5_10, 6),
]


# ====================================================================== 34. Multiplication Strategies

# How to break each hard factor into facts from packet 33: (first part, how)
STRATEGY = {3: (2, "add"), 4: (2, "add"), 6: (5, "add"), 7: (5, "add"), 8: (4, "add"), 9: (10, "sub")}
STRATEGY_WORDS = {3: "×2 and one more group", 4: "double, then double again", 6: "×5 and one more group",
                  7: "×5 and ×2", 8: "×4, then double", 9: "×10, take one group away"}


def split_array(bk, x, top, rows, cols, split, step=8, r=3, cross_from=None):
    """rows × cols dots; the first `split` rows blue, the rest orange, a dashed line between.
    cross_from: rows from here on are crossed out (the ×10 − one group picture). Returns (w, h)."""
    c = bk.c
    for i in range(rows):
        for j in range(cols):
            bk.dot(x + r + j * step, top - r - i * step, r, "a" if i < split else "b")
    w, h = r * 2 + (cols - 1) * step, r * 2 + (rows - 1) * step
    ly = top - r - (split - 0.5) * step
    c.setStrokeColor(T.text2)
    c.setLineWidth(0.9)
    c.setDash(2.5, 2)
    c.line(x - 3, ly, x + w + 3, ly)
    c.setDash()
    if cross_from is not None:
        c.setStrokeColor(T.accent)
        c.setLineWidth(1.6)
        for i in range(cross_from, rows):
            yy = top - r - i * step
            c.line(x - 3, yy, x + w + 3, yy)
    return w, h


def break_lines(a, b):
    """The number sentences for breaking a × b apart (a is the hard factor)."""
    s, how = STRATEGY[a]
    if how == "sub":
        return [f"10 {TIMES} {b} = [{10 * b}]", f"[{10 * b}] {MINUS} {b} = [{a * b}]"]
    return [f"{s} {TIMES} {b} = [{s * b}]", f"{a - s} {TIMES} {b} = [{(a - s) * b}]",
            f"[{s * b}] + [{(a - s) * b}] = [{a * b}]"]


def c_break_array(bk, x, cy, w, item):
    a, b = item
    s, how = STRATEGY[a]
    bk.fit_eq(x + GUT, cy + 126, w - GUT - 10, f"{a} {TIMES} {b} = [{a * b}]", size=16)
    if how == "sub":
        split_array(bk, x + GUT, cy + 104, 10, b, 9, step=8.5, r=3, cross_from=9)
    else:
        split_array(bk, x + GUT, cy + 104, a, b, s, step=8.5, r=3)
    tx = x + GUT + 84
    for i, line in enumerate(break_lines(a, b)):
        bk.fit_eq(tx, cy + 82 - i * 28, w - (tx - x) - 8, line, size=13)


def learn_strategies(bk):
    y = bk.new_page("Multiplication Strategies", "Break a hard fact into facts you know.", name_line=False,
                    big=True, footer="WeMath  ·  Multiplication Strategies")
    c = bk.c
    label(bk, M, y - 6, f"6 {TIMES} 7: 5 rows and 1 more row")
    split_array(bk, M + 20, y - 24, 6, 7, 5, step=15, r=5)
    color_eq(bk, M + 160, y - 42, [("5", "a"), (TIMES, "op"), ("7", None), ("=", "op"), ("35", "a")], 22)
    color_eq(bk, M + 160, y - 72, [("1", "b"), (TIMES, "op"), ("7", None), ("=", "op"), ("7", "b")], 22)
    color_eq(bk, M + 160, y - 102, [("35", "a"), ("+", "op"), ("7", "b"), ("=", "op"), ("42", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 44, "×5 is easy: half of ×10.")
    c.drawString(M + 340, y - 62, "Then add one more row.")
    y -= 130

    label(bk, M, y - 6, f"9 {TIMES} 4: 10 rows, then take one away")
    split_array(bk, M + 20, y - 22, 10, 4, 9, step=10.5, r=3.6, cross_from=9)
    color_eq(bk, M + 160, y - 52, [("10", "a"), (TIMES, "op"), ("4", None), ("=", "op"), ("40", "a")], 22)
    color_eq(bk, M + 160, y - 82, [("40", "a"), (MINUS, "op"), ("4", "b"), ("=", "op"), ("36", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 52, "The crossed-out row")
    c.drawString(M + 340, y - 70, "is the group taken away.")
    y -= 144

    label(bk, M, y - 6, "A strategy for every fact")
    for i, a in enumerate((3, 4, 6, 7, 8, 9)):
        col, row = divmod(i, 3)
        xx, yy = M + 14 + col * 258, y - 30 - row * 24
        color_eq(bk, xx, yy, [(TIMES + str(a), "a")], 15)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 12.5)
        c.drawString(xx + 40, yy, "= " + STRATEGY_WORDS[a])
    y -= 100

    bottom = your_turn(bk, y, h=112)
    bk.ask("break array 3 8 your turn")
    split_array(bk, M + 130, bottom + 92, 3, 8, 2, step=13, r=4.5)
    tx = M + 260
    for i, line in enumerate(break_lines(3, 8)):
        bk.eq(tx, bottom + 80 - i * 28, line, size=16)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: use ×2, ×5 and ×10 to find the other facts by breaking an array apart "
                     "(3.OA.5, 3.OA.7). Draw the dashed line, solve each part, then add (or take away for ×9). "
                     "Practice a few facts a day until they are quick.")


def practice_strategies(bk):
    title = "Multiplication Strategies: Practice"
    y = bk.new_page(title, "Break the array. Solve each part. Put them together.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    key = KINDS_34["break_array"].key
    for n, (a, items) in enumerate([(3, (6, 4, 9, 7)), (4, (7, 3, 9, 6)), (6, (4, 9, 7, 3)), (9, (3, 7, 4)),
                                    (8, (3, 6, 7)), (7, (4, 8, 7))]):
        part(n + 1, f"Times {a}", f"{TIMES}{a} = {STRATEGY_WORDS[a]}.", [(a, b) for b in items], 2, 146, 10,
             c_break_array, key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    for n, (name, facts) in enumerate(FACT_PARTS_34):
        part(7 + n, name, "No help this time.", [X(a, b) for a, b in facts], 3, 42, 8, plain, lambda t: t)
    part(11, "Remember?", "Problems from earlier packets.", REVIEW_34, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 12, "Word problems", "Find the groups and how many in each.")
    for i, story in enumerate(WORDS_34):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 12, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


def _fact_parts():
    hard = (3, 4, 6, 7, 8, 9)
    pairs = [(a, b) for a in hard for b in hard]
    groups = [("Times 3", lambda p: 3 in p), ("Times 4", lambda p: 4 in p), ("Times 6", lambda p: 6 in p),
              ("Times 7, 8 and 9", lambda p: True)]
    out, used = [], set()
    for name, test in groups:
        facts = [p for p in pairs if test(p) and p not in used]
        used.update(facts)
        facts = shuf(name, facts)
        ordered = []
        while facts:  # no two in a row starting with the same number
            k = next((i for i, p in enumerate(facts) if not ordered or p[0] != ordered[-1][0]), 0)
            ordered.append(facts.pop(k))
        out.append((name, ordered))
    return out


FACT_PARTS_34 = _fact_parts()

REVIEW_34 = ["6 groups of 5 = [30]", "half past 2 = [2:30]", "3 dimes + 4 nickels = [50¢]",
             "8 groups of 2 = [16]", f"502 {MINUS} 267 = [235]", "45 cm + 38 cm = [83] cm"]

WORDS_34 = [
    ("A garden has 6 rows with 7 carrots in each row. How many carrots are there?", f"6 {TIMES} 7 = 42", "42",
     "carrots"),
    ("A spider has 8 legs. How many legs do 4 spiders have?", f"4 {TIMES} 8 = 32", "32", "legs"),
    ("A pack has 9 markers. How many markers are in 3 packs?", f"3 {TIMES} 9 = 27", "27", "markers"),
    ("There are 7 days in a week. How many days are in 8 weeks?", f"8 {TIMES} 7 = 56", "56", "days"),
    ("Challenge: A theater has 9 rows of 8 seats. 15 seats are empty. How many seats are full?",
     f"9 {TIMES} 8 = 72, 72 {MINUS} 15 = 57", "57", "seats"),
]

KINDS_34 = {
    "break_array": Kind(146, 2, lambda it: f"break array {it[0]} {it[1]}", c_break_array),
}
KINDS.update(KINDS_34)

HARD_FACTS = [X(a, b) for a in (3, 4, 6, 7, 8, 9) for b in (3, 4, 6, 7, 8, 9)]

CHECKINS["34-multiplication-strategies"] = [
    S("Break it apart", None, "break_array", [(a, b) for a in (3, 4, 6, 7, 8, 9) for b in rng(3, 9)], 2),
    S("Multiply", None, "eq3", HARD_FACTS, 9),
]


# ====================================================================== 35. Division

DIV = "÷"


def D(p, d):
    """'12 ÷ 3 = [4]'"""
    return f"{p} {DIV} {d} = [{p // d}]"


def plate_row(bk, x, y, k, each, w=50, h=34, gap=12, kind=None):
    """k plates in a row (y = bottom). On the key each plate shows `each` things (dots, or icons of kind)."""
    c = bk.c
    for i in range(k):
        px = x + i * (w + gap)
        c.setStrokeColor(T.muted)
        c.setLineWidth(1)
        c.ellipse(px, y, px + w, y + h, stroke=1, fill=0)
        if bk.key:
            cx, cy = px + w / 2, y + h / 2
            if each <= 5 and kind is None:
                for ox, oy in DICE[each]:
                    bk.dot(cx + ox * 8, cy + oy * 8, 3.6, "a")
            else:
                cols = min(each, 3)
                for j in range(each):
                    r, col = divmod(j, cols)
                    px_, py_ = cx + (col - (cols - 1) / 2) * 12, cy + 6 - r * 11
                    if kind:
                        icon(bk, kind, px_, py_, 10)
                    else:
                        bk.dot(px_, py_, 3.4, "a")
    return k * (w + gap) - gap


def c_share_div(bk, x, cy, w, item):
    kind, n, k = item
    objects(bk, kind, x + GUT, cy + 112, n, s=15, step=18, per_row=n)
    plate_row(bk, x + GUT, cy + 44, k, n // k)
    bk.eq(x + GUT, cy + 14, f"[{n}] {DIV} [{k}] = [{n // k}]", size=16)
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvM", 10)
    bk.c.drawString(x + GUT + 180, cy + 16, f"Share {n} on {k} plates.")


def c_make_groups(bk, x, cy, w, item):
    n, g = item
    step = 18
    for i in range(n):
        bk.dot(x + GUT + 6 + i * step, cy + 48, 5, "a")
    if bk.key:
        c = bk.c
        c.setStrokeColor(T.answer)
        c.setLineWidth(1.3)
        for j in range(n // g):
            x0 = x + GUT + 6 + j * g * step - 7
            c.roundRect(x0, cy + 38, (g - 1) * step + 14, 20, 9, stroke=1, fill=0)
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 12, f"Circle groups of {g}.")
    bk.eq(x + GUT + 170, cy + 12, f"[{n}] {DIV} [{g}] = [{n // g}]", size=15)


def c_think_times(bk, x, cy, w, item):
    p, d = item
    bk.fit_eq(x + GUT, cy + 42, w - GUT - 10, f"{d} {TIMES} [{p // d}] = {p}", size=16)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"so {p} {DIV} {d} = [{p // d}]", size=16)


def c_fact_family(bk, x, cy, w, item):
    a, b = item
    p = a * b
    c = bk.c
    for i, n in enumerate((a, b, p)):
        cx = x + GUT + 14 + i * 40
        c.setStrokeColor(T.dot_a if i < 2 else T.accent)
        c.setLineWidth(1.3)
        c.circle(cx, cy + 128, 14, stroke=1, fill=0)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 12)
        c.drawCentredString(cx, cy + 124, str(n))
    for i, line in enumerate((f"[{a}] {TIMES} [{b}] = [{p}]", f"[{b}] {TIMES} [{a}] = [{p}]",
                              f"[{p}] {DIV} [{a}] = [{b}]", f"[{p}] {DIV} [{b}] = [{a}]")):
        bk.fit_eq(x + GUT, cy + 88 - i * 26, w - GUT - 10, line, size=13)


def learn_division(bk):
    y = bk.new_page("Division", "Share equally, or make equal groups.", name_line=False, big=True,
                    footer="WeMath  ·  Division")
    c = bk.c
    label(bk, M, y - 6, "Share 12 cookies on 3 plates")
    objects(bk, "cookie", M + 14, y - 30, 12, s=17, step=20, per_row=12)
    for i in range(3):
        px = M + 14 + i * 96
        c.setStrokeColor(T.muted)
        c.setLineWidth(1)
        c.ellipse(px, y - 92, px + 84, y - 56, stroke=1, fill=0)
        for j in range(4):
            icon(bk, "cookie", px + 15 + j * 18, y - 74, 15)
    color_eq(bk, M + 320, y - 82, [("12", "a"), (DIV, "op"), ("3", None), ("=", "op"), ("4", "b")], 26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 320, y - 104, "4 on each plate")
    y -= 124

    label(bk, M, y - 6, "How many 3s in 12? Make groups of 3")
    for i in range(12):
        bk.dot(M + 24 + i * 18 + (i // 3) * 12, y - 34, 6, "a" if (i // 3) % 2 == 0 else "b")
    c.setStrokeColor(T.text2)
    c.setLineWidth(1.1)
    for j in range(4):
        c.roundRect(M + 13 + j * 66, y - 46, 58, 24, 11, stroke=1, fill=0)
    color_eq(bk, M + 320, y - 42, [("12", "a"), (DIV, "op"), ("3", None), ("=", "op"), ("4", "b")], 26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 320, y - 64, "4 groups of 3")
    y -= 86

    label(bk, M, y - 6, "Think multiplication")
    color_eq(bk, M + 14, y - 38, [("3", None), (TIMES, "op"), ("4", "b"), ("=", "op"), ("12", "a")], 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 150, y - 38, "so")
    color_eq(bk, M + 180, y - 38, [("12", "a"), (DIV, "op"), ("3", None), ("=", "op"), ("4", "b")], 24)
    y -= 60

    label(bk, M, y - 6, "A fact family: 3, 4 and 12")
    for i, line in enumerate([[("3", None), (TIMES, "op"), ("4", None), ("=", "op"), ("12", "a")],
                              [("4", None), (TIMES, "op"), ("3", None), ("=", "op"), ("12", "a")],
                              [("12", "a"), (DIV, "op"), ("3", None), ("=", "op"), ("4", None)],
                              [("12", "a"), (DIV, "op"), ("4", None), ("=", "op"), ("3", None)]]):
        color_eq(bk, M + 14 + (i % 2) * 150, y - 34 - (i // 2) * 28, line, 20)
    y -= 92

    bottom = your_turn(bk, y, h=98)
    bk.ask("share: star 10 on 2 your turn")
    objects(bk, "star", M + 130, bottom + 80, 10, s=15, step=18, per_row=10)
    plate_row(bk, M + 130, bottom + 14, 2, 5, w=70, h=40, kind="star")
    bk.eq(M + 330, bottom + 26, f"10 {DIV} 2 = [5]", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: division as sharing and as making groups (3.OA.2), and as a missing factor "
                     "(3.OA.6). Read 12 ÷ 3 as “12 shared by 3” or “how many 3s in 12.” "
                     "Every division fact has a multiplication partner.")


def practice_division(bk):
    title = "Division: Practice"
    y = bk.new_page(title, "Share equally, or make groups. Think multiplication.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    part(1, "Share it", "Draw the same number on each plate.",
         [("apple", 10, 5), ("cupcake", 12, 4), ("candy", 8, 2), ("egg", 15, 3), ("fish", 18, 6), ("flower", 20, 5)],
         1, 132, 8, c_share_div, KINDS_35["share_div"].key)
    part(2, "Make groups", "Circle groups. Count the groups.",
         [(15, 3), (12, 2), (20, 4), (18, 6), (16, 8), (14, 7)], 1, 70, 8, c_make_groups,
         lambda it: f"make groups {it[0]} by {it[1]}")
    part(3, "Think multiplication", "Find the missing factor. It is the answer.",
         [(20, 4), (42, 6), (27, 9), (35, 7), (24, 8), (18, 3), (40, 5), (32, 4)], 2, 70, 10, c_think_times,
         KINDS_35["think_times"].key)
    part(4, "Fact families", "Use all three numbers. Write 4 facts.", [(3, 7), (4, 9), (6, 8), (5, 6)], 2, 150, 10,
         c_fact_family, lambda it: f"fact family {it[0]} {it[1]}")
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    for n, (name, facts) in enumerate(DIV_PARTS):
        part(5 + n, name, "No help this time.", facts, 3, 42, 8, plain, lambda t: t)
    part(8, "Missing factors", "No help this time.",
         [f"{a} {TIMES} [{b}] = {a * b}" for a, b in ((6, 9), (8, 4), (3, 9), (7, 8), (4, 6), (9, 5), (2, 8),
                                                       (6, 6), (5, 7))], 3, 42, 8, plain, lambda t: t)
    part(9, "Remember?", "Problems from earlier packets.", REVIEW_35, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 10, "Word problems", "Share it, or make groups?")
    for i, story in enumerate(WORDS_35):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 10, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


def _div_parts():
    parts = [("Divide by 2, 5 and 10", (2, 5, 10)), ("Divide by 3 and 4", (3, 4)), ("Divide by 6, 7, 8 and 9", (6, 7, 8, 9))]
    out = []
    for name, ds in parts:
        pool = shuf(name, [(d * q, d) for d in ds for q in rng(2, 10)])
        picked, seen_ans = [], []
        for p, d in pool:
            if len(picked) == 12:
                break
            if picked and (p == picked[-1][0] or p // d == picked[-1][0] // picked[-1][1]):
                continue
            picked.append((p, d))
        out.append((name, [D(p, d) for p, d in picked]))
    return out


DIV_PARTS = _div_parts()

REVIEW_35 = ["7 groups of 3 = [21]", "quarter to 12 = [11:45]", "66¢ + 25¢ = [91¢]", f"701 {MINUS} 345 = [356]",
             f"52 cm {MINUS} 17 cm = [35] cm", "double 45 = [90]"]

WORDS_35 = [
    ("4 kids share 24 stickers equally. How many stickers does each kid get?", f"24 {DIV} 4 = 6", "6", "stickers"),
    ("30 chairs are set up in rows of 6. How many rows are there?", f"30 {DIV} 6 = 5", "5", "rows"),
    ("Mom has 18 cookies. She puts 3 cookies in each bag. How many bags does she fill?", f"18 {DIV} 3 = 6", "6",
     "bags"),
    ("56 crayons are packed into 8 boxes equally. How many crayons go in each box?", f"56 {DIV} 8 = 7", "7",
     "crayons"),
    ("Challenge: 28 kids make teams of 4. Each team gets 2 balls. How many balls are needed?",
     f"28 {DIV} 4 = 7, 7 {TIMES} 2 = 14", "14", "balls"),
]

KINDS_35 = {
    "share_div": Kind(132, 1, lambda it: f"share: {it[0]} {it[1]} on {it[2]}", c_share_div, 8),
    "think_times": Kind(70, 2, lambda it: f"{it[1]} {TIMES} [] = {it[0]}", c_think_times),
}
KINDS.update(KINDS_35)

DIV_FACTS = [D(d * q, d) for d in rng(2, 10) for q in rng(2, 10)]

CHECKINS["35-division"] = [
    S("Share it", None, "share_div", [(k, n * q, n) for k in ("apple", "star", "cookie", "candy")
                                     for n in rng(3, 5) for q in rng(3, 5)], 1),
    S("Think multiplication", None, "think_times", [(d * q, d) for d in rng(3, 9) for q in rng(3, 9)], 2),
    S("Divide", None, "eq3", DIV_FACTS, 9),
]


# ====================================================================== 39–44. Fractions


def frac_width(tok, size):
    ns = size * 0.8
    num, den = tok.split("/")
    part = lambda t: ns * 1.5 if t.startswith("[") else sw(t, "Rnd", ns)
    return max(part(num), part(den)) + 6


def frac_expr(bk, x, base, text, size=18, color=None, measure=False):
    """An expression with stacked fractions: "3/4 [<] 7/8", "1/2 = [2]/4", "6/6 = [1]".
    a/b is a fraction (either part can be a [blank]); [x] alone is an answer box; signs are grey.
    measure=True draws nothing and returns the end x (for fitting)."""
    c = bk.c
    color = color or T.ink
    gap = size * 0.34
    ns = size * 0.8
    for tok in text.split():
        if "/" in tok:
            num, den = tok.split("/")
            fw = frac_width(tok, size)
            if not measure:
                cx = x + fw / 2
                ly = base + size * 0.3
                c.setStrokeColor(color)
                c.setLineWidth(max(1, size / 14))
                c.line(x + 1, ly, x + fw - 1, ly)
                for part, top in ((num, True), (den, False)):
                    if part.startswith("["):
                        bw, bh = ns * 1.5, ns * 1.3
                        by = ly + 3 if top else ly - 3 - bh
                        bk.box(cx - bw / 2, by, bw, bh, part[1:-1], size=ns * 0.85)
                    else:
                        c.setFillColor(color)
                        c.setFont("Rnd", ns)
                        c.drawCentredString(cx, ly + 4 if top else ly - ns * 0.95, part)
            x += fw
        elif tok.startswith("["):
            ans = tok[1:-1]
            bw = size * 1.6 + max(len(ans) - 1, 0) * size * 0.5
            if not measure:
                bk.box(x, base - size * 0.42, bw, size * 1.5, ans, size=size * 0.9)
            x += bw
        elif tok in OPS or tok in ("<", ">"):
            if not measure:
                c.setFillColor(T.text2)
                c.setFont("AvD", size)
                c.drawString(x, base, tok)
            x += sw(tok, "AvD", size)
        else:
            if not measure:
                c.setFillColor(color)
                c.setFont("Rnd", size)
                c.drawString(x, base, tok)
            x += sw(tok, "Rnd", size)
        x += gap
    return x - gap


def frac_fit(bk, x, base, max_w, text, size=18):
    """frac_expr, shrunk until it fits in max_w."""
    while size > 10 and frac_expr(bk, 0, 0, text, size, measure=True) > max_w:
        size -= 0.5
    return frac_expr(bk, x, base, text, size)


def strip(bk, x, y, w, h, n, shaded=0, answer=0, lw=1.2):
    """A fraction strip: a bar cut into n equal parts; the first `shaded` filled, or `answer` filled on the key.
    shaded and answer can also be lists of part numbers."""
    c = bk.c
    parts = [[(x + w * i / n, y), (x + w * (i + 1) / n, y), (x + w * (i + 1) / n, y + h), (x + w * i / n, y + h)]
             for i in range(n)]
    for i in (range(shaded) if isinstance(shaded, int) else shaded):
        shade(bk, parts[i])
    if bk.key:
        for i in (range(answer) if isinstance(answer, int) else answer):
            shade(bk, parts[i], answer=True)
    c.setStrokeColor(T.ink)
    c.setLineWidth(lw)
    for pts in parts:
        c.drawPath(_poly(c, pts), stroke=1, fill=0)


def c_compare_frac(bk, x, cy, w, item):
    """Two strips (same whole) and a sign to fill in."""
    (a, b), (p, q) = item
    sw_ = w - GUT - 160
    strip(bk, x + GUT, cy + 50, sw_, 20, b, shaded=a)
    strip(bk, x + GUT, cy + 20, sw_, 20, q, shaded=p)
    frac_expr(bk, x + GUT + sw_ + 18, cy + 38, f"{a}/{b} [{sign_of(Fraction(a, b), Fraction(p, q))}] {p}/{q}", size=22)


def c_equiv_frac(bk, x, cy, w, item):
    (a, b), q = item
    sw_ = w - GUT - 160
    strip(bk, x + GUT, cy + 50, sw_, 20, b, shaded=a)
    strip(bk, x + GUT, cy + 20, sw_, 20, q, shaded=a * q // b)
    frac_expr(bk, x + GUT + sw_ + 18, cy + 38, f"{a}/{b} = [{a * q // b}]/{q}", size=22)


def c_frac(bk, x, cy, w, text):
    frac_fit(bk, x + GUT, cy + 16, w - GUT - 10, text, size=17)


def frac_pic(bk, kind, x, y, n, shaded=(), answer=(), s=None):
    """A fraction picture: a strip (kind "strip") or a packet 26 shape cut into n equal parts.
    (x, y) = bottom-left. Returns (w, h)."""
    if kind == "strip":
        w = s or 120
        strip(bk, x, y, w, 24, n, shaded=list(shaded), answer=list(answer))
        return w, 24
    s = s or {"circle": 54, "rect": 46, "tall": 42, "square": 50}[kind]
    return share_shape(bk, kind, x, y, s, n, shaded=shaded, answer=answer)


FRAC_PIC_H = {"strip": 24, "circle": 54, "rect": 41, "tall": 55, "square": 50}


def unit_word(n):
    return f"one {SHARE_NAME[n][0]}"


def c_unit_name(bk, x, cy, w, item):
    """Name the unit fraction: one part shaded."""
    kind, n, i = item
    ph = FRAC_PIC_H[kind]
    frac_pic(bk, kind, x + GUT, cy + (72 - ph) / 2, n, shaded=[i])
    frac_expr(bk, x + w - 74, cy + 30, f"[1]/[{n}]", size=20)


def c_shade_unit(bk, x, cy, w, item):
    """Shade one part: the key fills it."""
    kind, n, i = item
    ph = FRAC_PIC_H[kind]
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 31, "Shade")
    frac_expr(bk, x + GUT + 46, cy + 30, f"1/{n}", size=18)
    frac_pic(bk, kind, x + GUT + 92, cy + (72 - ph) / 2, n, answer=[i], s=100 if kind == "strip" else None)


def c_find_whole(bk, x, cy, w, item):
    """One piece of a bar is shown; draw the whole bar (the key draws the other pieces)."""
    n = item
    whole = 216
    pw = whole / n
    c = bk.c
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(x + GUT, cy + 58, "This piece is")
    frac_expr(bk, x + GUT + 82, cy + 57, f"1/{n}", size=15)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(x + GUT + 108, cy + 58, "of a bar. Draw the whole bar.")
    strip(bk, x + GUT, cy + 18, pw, 24, 1, shaded=1)
    if bk.key:
        c.setStrokeColor(T.answer)
        c.setLineWidth(1.2)
        c.setDash(3, 2)
        for j in range(1, n):
            c.rect(x + GUT + j * pw, cy + 18, pw, 24, stroke=1, fill=0)
        c.setDash()
    bk.fit_eq(x + GUT + whole + 24, cy + 24, w - GUT - whole - 34, f"[{n}] pieces make the whole", size=14)


def c_bigger_piece(bk, x, cy, w, item):
    """Two unit fractions; the key rings the bigger piece. With pics, a strip (same whole) over each one."""
    a, b, pics = item
    c = bk.c
    if pics:
        sw_ = w - GUT - 50
        for j, n in enumerate((a, b)):
            yy = cy + 48 - j * 36
            fx = x + GUT
            frac_expr(bk, fx, yy + 3, f"1/{n}", size=14)
            strip(bk, x + GUT + 32, yy, sw_ - 6, 18, n, shaded=1)
            if bk.key and n == min(a, b):
                c.setStrokeColor(T.answer)
                c.setLineWidth(1.5)
                c.ellipse(fx - 8, yy - 8, fx + 22, yy + 26, stroke=1, fill=0)
        return
    fx = x + GUT + 6
    for j, n in enumerate((a, b)):
        frac_expr(bk, fx, cy + 16, f"1/{n}", size=18)
        if bk.key and n == min(a, b):
            c.setStrokeColor(T.answer)
            c.setLineWidth(1.5)
            c.ellipse(fx - 9, cy + 2, fx + 27, cy + 42, stroke=1, fill=0)
        if j == 0:
            c.setFillColor(T.text2)
            c.setFont("Rnd", 13)
            c.drawString(fx + 34, cy + 17, "or")
        fx += 66


def learn_unit_fractions(bk):
    y = bk.new_page("Unit Fractions", "Cut one whole into equal parts. One part is a unit fraction.",
                    name_line=False, big=True, footer="WeMath  ·  Unit Fractions")
    c = bk.c
    label(bk, M, y - 6, "1 whole, 4 equal parts")
    strip(bk, M + 14, y - 58, 220, 32, 4, shaded=1)
    frac_expr(bk, M + 268, y - 50, "1/4", size=36)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 318, y - 30, "1 part shaded")
    c.drawString(M + 318, y - 64, "4 equal parts in the whole")
    c.drawString(M + 318, y - 84, "Say: one fourth.")
    y -= 108

    label(bk, M, y - 6, "The parts must be equal")
    share_shape(bk, "rect", M + 20, y - 76, 40, 4, shaded=[0])
    share_shape(bk, "rect", M + 200, y - 76, 40, 4, shaded=[0], equal=False)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 20, y - 94, "Equal parts: 1/4")
    c.drawString(M + 200, y - 94, "Not equal: not fourths")
    c.drawString(M + 372, y - 40, "Same size pieces?")
    c.drawString(M + 372, y - 58, "Then each one is 1/4.")
    y -= 120

    label(bk, M, y - 6, "More parts, smaller pieces")
    for i, n in enumerate((2, 3, 4, 6, 8)):
        yy = y - 40 - i * 24
        strip(bk, M + 54, yy, 260, 18, n, shaded=1, lw=1)
        frac_expr(bk, M + 14, yy + 3, f"1/{n}", size=12)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 40, "Same whole bar.")
    c.drawString(M + 340, y - 58, "Cut it into more parts,")
    c.drawString(M + 340, y - 76, "and each piece is smaller.")
    frac_expr(bk, M + 340, y - 110, "1/2 is bigger than 1/8", size=14)
    y -= 168

    bottom = your_turn(bk, y, h=96)
    bk.ask("unit fraction: circle 6 parts your turn")
    share_shape(bk, "circle", M + 150, bottom + 18, 58, 6, shaded=[0])
    frac_expr(bk, M + 270, bottom + 40, "[1]/[6]", size=26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, bottom + 44, "How many equal parts?")
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: 1/b is one of b equal parts of a whole (3.NF.1, 3.G.2). Say “How many equal parts? "
                     "That's the bottom number. One part is one fourth.” Check the parts are equal first. "
                     "More parts means smaller pieces.")


def practice_unit_fractions(bk):
    title = "Unit Fractions: Practice"
    y = bk.new_page(title, "The bottom number tells how many equal parts.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Equal parts?", "Circle yes or no.", "eq_share",
         [("rect", 6, True), ("circle", 8, False), ("tall", 5, True), ("square", 6, False), ("circle", 5, True),
          ("rect", 8, False), ("tall", 6, False), ("circle", 10, True), ("square", 5, True)])
    part(2, "Name the unit fraction", "Count the equal parts. One part is shaded.", "unit_name",
         [("strip", 5, 2), ("circle", 8, 0), ("rect", 3, 1), ("tall", 6, 4), ("circle", 10, 3), ("square", 4, 2),
          ("strip", 8, 5), ("circle", 6, 2), ("rect", 10, 7), ("tall", 2, 1), ("strip", 3, 0), ("circle", 4, 1)])
    part(3, "Shade one part", None, "shade_unit",
         [("circle", 3, 1), ("strip", 6, 3), ("rect", 5, 0), ("square", 8, 6), ("tall", 4, 2), ("circle", 2, 0),
          ("strip", 10, 4), ("rect", 6, 5)])
    part(4, "Find the whole", "Draw the other pieces. They are all the same size.", "find_whole",
         [3, 6, 2, 5, 8, 4])
    part(5, "Which piece is bigger?", "Same whole bar. Circle the bigger piece.", "bigger_unit",
         [(5, 3, True), (2, 6, True), (4, 8, True), (6, 5, True), (3, 10, True), (8, 10, True), (6, 3, True),
          (4, 2, True)])
    part(6, "How many equal parts?", "No help this time.", "frac2",
         [f"1/{n} is 1 of [{n}] equal parts" for n in (6, 3, 10, 2, 8, 5, 4)])
    part(7, "Make one whole", "No help this time. How many pieces fill the whole?", "frac2",
         [f"[{n}] pieces of 1/{n} make 1 whole" for n in (4, 8, 2, 5, 10, 3, 6)])
    part(8, "Words and numbers", "No help this time.", "frac2",
         [f"{unit_word(n)} = 1/[{n}]" for n in (8, 3, 5, 10, 2, 6, 4)])
    part(9, "Bigger piece", "No help this time. Circle the bigger piece.", "bigger_unit_plain",
         [(6, 4, False), (2, 5, False), (8, 5, False), (3, 4, False), (10, 6, False), (5, 4, False), (2, 8, False),
          (4, 10, False), (2, 3, False)])
    part(10, "Remember?", "Problems from earlier packets.", "eq2", REVIEW_UNIT)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 11, "Word problems", "Draw a picture.")
    for i, story in enumerate(WORDS_UNIT):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 11, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_UNIT = ["9 × 50 = [450]", "7 cm by 4 cm: area = [28] sq cm", "Round 268 to the nearest hundred: [300]",
             "3 sixths = [1] half", "5 groups of 9 = [45]", "Round 83 to the nearest ten: [80]"]

WORDS_UNIT = [
    ("A pizza is cut into 6 equal slices. Ana eats 1 slice. What fraction of the pizza does she eat?",
     "1 of 6 equal parts = 1/6", "1/6", "of the pizza"),
    ("A garden has 4 equal parts. Carrots grow in 1 part. What fraction of the garden is carrots?",
     "1 of 4 equal parts = 1/4", "1/4", "of the garden"),
    ("Two same-size cakes. Leo cuts his into 3 equal pieces, Max into 8. Whose piece is bigger?",
     "1/3 is bigger than 1/8", "Leo's", "piece"),
    ("A ribbon is cut into equal pieces. Each piece is 1/5 of the ribbon. How many pieces are there?",
     "5 pieces of 1/5 make 1 whole", "5", "pieces"),
    ("Challenge: Cut a bar in half. Then cut each half in half. What fraction of the bar is one piece?",
     "4 equal pieces, 1 piece = 1/4", "1/4", "of the bar"),
]

KINDS_UNIT = {
    "unit_name": Kind(72, 2, lambda it: f"name the unit fraction: {it[0]} cut in {it[1]}, part {it[2] + 1} shaded",
                      c_unit_name),
    "shade_unit": Kind(72, 2, lambda it: f"shade the unit fraction: {it[0]} cut in {it[1]}, part {it[2] + 1}",
                       c_shade_unit),
    "find_whole": Kind(76, 1, lambda n: f"find the whole: 1/{n} piece", c_find_whole, 8),
    "bigger_unit": Kind(84, 2, lambda it: f"bigger piece{' (strips)' if it[2] else ''}: 1/{it[0]} or 1/{it[1]}",
                        c_bigger_piece),
    "frac2": Kind(48, 2, lambda t: t, c_frac, 8),
}
KINDS.update(KINDS_UNIT)


def c_rev(bk, x, cy, w, text):
    """A "Remember?" problem: fractions drawn stacked, everything else as a plain equation."""
    if "/" in text:
        frac_fit(bk, x + GUT, cy + 15, w - GUT - 8, text, size=18)
    else:
        c_eq(bk, x, cy, w, text)


KINDS["rev2"] = Kind(42, 2, lambda t: t, c_rev, 8)
KINDS["bigger_unit_plain"] = Kind(48, 3, KINDS_UNIT["bigger_unit"].key, c_bigger_piece, 8)
BALANCE["bigger_unit"] = BALANCE["bigger_unit_plain"] = lambda it: it[0] < it[1]

_UNIT_DENS = (2, 3, 4, 5, 6, 8, 10)
_UNIT_KINDS = {"strip": _UNIT_DENS, "circle": _UNIT_DENS, "rect": _UNIT_DENS, "tall": (2, 3, 4, 5, 6),
               "square": (2, 3, 4, 5, 6, 8)}
UNIT_NAME = [(k, n, i) for k, ns in _UNIT_KINDS.items() for n in ns for i in range(n)]
UNIT_FACTS = ([f"1/{n} is 1 of [{n}] equal parts" for n in _UNIT_DENS]
              + [f"[{n}] pieces of 1/{n} make 1 whole" for n in _UNIT_DENS]
              + [f"{unit_word(n)} = 1/[{n}]" for n in _UNIT_DENS])
# One order per pair (no 1/3-or-1/8 next to 1/8-or-1/3), with the bigger piece first or second about half the time.
UNIT_BIGGER = [(a, b, False) for a in _UNIT_DENS for b in _UNIT_DENS if a != b and (a < b) == ((a + b) % 2 == 1)]

CHECKINS["39-unit-fractions"] = [
    S("Name the unit fraction", None, "unit_name", UNIT_NAME, 2),
    S("Find the whole", None, "find_whole", list(_UNIT_DENS), 1),
    S("Bigger piece", "Circle the bigger piece.", "bigger_unit_plain", UNIT_BIGGER, 3),
    S("How many equal parts?", None, "frac2", UNIT_FACTS, 4),
]


NUM_WORD = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
            10: "ten", 11: "eleven", 12: "twelve"}


def frac_words(k, n):
    """frac_words(3, 4) = "three fourths"."""
    return f"{NUM_WORD[k]} {SHARE_NAME[n][0 if k == 1 else 1]}"


def c_count_pieces(bk, x, cy, w, item):
    """k pieces of 1/n shaded: count them, then write the fraction."""
    kind, n, k = item
    ph = FRAC_PIC_H[kind]
    pw, _ = frac_pic(bk, kind, x + GUT, cy + (64 - ph) / 2, n, shaded=range(k))
    frac_fit(bk, x + GUT + 154, cy + 26, w - GUT - 164, f"[{k}] pieces of 1/{n} = [{k}]/{n}", size=17)


def c_frac_name(bk, x, cy, w, item):
    kind, n, k = item
    ph = FRAC_PIC_H[kind]
    frac_pic(bk, kind, x + GUT, cy + (72 - ph) / 2, n, shaded=range(k))
    frac_expr(bk, x + w - 74, cy + 30, f"[{k}]/[{n}]", size=20)


def c_frac_shade(bk, x, cy, w, item):
    kind, n, k = item
    ph = FRAC_PIC_H[kind]
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 31, "Shade")
    frac_expr(bk, x + GUT + 46, cy + 30, f"{k}/{n}", size=18)
    frac_pic(bk, kind, x + GUT + 92, cy + (72 - ph) / 2, n, answer=range(k), s=100 if kind == "strip" else None)


def c_shaded_not(bk, x, cy, w, item):
    """How much is shaded, how much is not."""
    kind, n, k = item
    ph = FRAC_PIC_H[kind]
    frac_pic(bk, kind, x + GUT, cy + (84 - ph) / 2, n, shaded=range(k), s=76 if kind == "strip" else None)
    tx = x + w - 118
    for j, (word, v) in enumerate((("shaded", k), ("not shaded", n - k))):
        yy = cy + 52 - j * 36
        bk.c.setFillColor(T.text2)
        bk.c.setFont("Rnd", 11)
        bk.c.drawRightString(tx + 50, yy + 2, word)
        frac_expr(bk, tx + 58, yy, f"[{v}]/{n}", size=16)


def learn_counting_fractions(bk):
    y = bk.new_page("Counting Fractions", "Count the pieces. 3 pieces of 1/4 is 3/4.", name_line=False, big=True,
                    footer="WeMath  ·  Counting Fractions")
    c = bk.c
    label(bk, M, y - 6, "Put unit fractions together")
    for j in range(3):
        strip(bk, M + 14 + j * 62, y - 56, 52, 30, 1, shaded=1)
        frac_expr(bk, M + 30 + j * 62, y - 82, "1/4", size=14)
    c.setFillColor(T.text2)
    c.setFont("AvD", 26)
    c.drawString(M + 206, y - 50, "=")
    strip(bk, M + 236, y - 56, 208, 30, 4, shaded=3)
    frac_expr(bk, M + 462, y - 50, "3/4", size=34)
    y -= 112

    label(bk, M, y - 6, "Count by fourths")
    for i in range(4):
        yy = y - 40 - i * 34
        strip(bk, M + 14, yy, 208, 24, 4, shaded=i + 1)
        frac_expr(bk, M + 238, yy + 4, f"{i + 1}/4", size=18)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 310, y - 36, "Top number: how many pieces.")
    c.drawString(M + 310, y - 56, "Bottom number: how many equal")
    c.drawString(M + 310, y - 72, "parts make the whole.")
    c.drawString(M + 310, y - 100, "4 pieces of 1/4 fill the bar:")
    c.drawString(M + 310, y - 116, "that's the whole.")
    y -= 174

    label(bk, M, y - 6, "Say it in words")
    frac_expr(bk, M + 14, y - 46, "2/3", size=26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 14)
    c.drawString(M + 56, y - 42, "two thirds")
    frac_expr(bk, M + 214, y - 46, "5/8", size=26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 14)
    c.drawString(M + 256, y - 42, "five eighths")
    y -= 72

    bottom = your_turn(bk, y, h=96)
    bk.ask("count the pieces: strip cut in 6, 5 shaded your turn")
    strip(bk, M + 130, bottom + 34, 180, 28, 6, shaded=5)
    frac_expr(bk, M + 350, bottom + 40, "[5]/[6]", size=26)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: a/b is a pieces of size 1/b (3.NF.1). Point at each piece and count: “one fourth, two "
                     "fourths, three fourths.” The top number counts pieces; the bottom number names their size.")


def practice_counting_fractions(bk):
    title = "Counting Fractions: Practice"
    y = bk.new_page(title, "Top: how many pieces. Bottom: how many equal parts in the whole.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Count the pieces", "How many pieces are shaded? What size is each one?", "count_pieces",
         [("strip", 5, 3), ("circle", 8, 5), ("rect", 4, 3), ("strip", 10, 7), ("circle", 6, 4), ("tall", 3, 2),
          ("strip", 8, 6), ("square", 5, 2)])
    part(2, "Name the fraction", None, "frac_name",
         [("circle", 4, 3), ("strip", 6, 5), ("rect", 8, 3), ("tall", 5, 4), ("circle", 10, 3), ("square", 6, 4),
          ("strip", 3, 2), ("circle", 5, 2), ("rect", 10, 9), ("tall", 6, 2), ("strip", 8, 7), ("circle", 6, 5)])
    part(3, "Shade it", None, "frac_shade",
         [("circle", 8, 3), ("strip", 5, 4), ("rect", 6, 5), ("square", 4, 2), ("tall", 6, 3), ("circle", 3, 2),
          ("strip", 10, 6), ("rect", 8, 7)])
    part(4, "Count by fractions", "No help this time. Fill in the missing fractions.", "frac2",
         ["1/5 2/5 [3]/5 [4]/5 5/5", "1/8 2/8 3/8 [4]/8 [5]/8", "2/6 3/6 [4]/6 [5]/6 6/6",
          "1/3 [2]/3 3/3", "4/10 5/10 [6]/10 [7]/10 8/10", "[1]/4 2/4 3/4 [4]/4",
          "3/8 4/8 5/8 [6]/8 [7]/8", "1/6 [2]/6 [3]/6 4/6"])
    part(5, "Shaded and not shaded", "Together they make the whole.", "shaded_not",
         [("strip", 8, 3), ("circle", 5, 4), ("rect", 6, 1), ("tall", 4, 1), ("circle", 10, 6), ("strip", 6, 2)])
    part(6, "Pieces to fractions", "No help this time.", "frac2",
         [f"{k} pieces of 1/{n} = [{k}]/{n}" for k, n in ((4, 6), (2, 3), (7, 8), (3, 5), (6, 10), (2, 4),
                                                          (5, 8), (9, 10), (3, 6), (4, 5), (2, 8), (5, 10))])
    part(7, "Fractions to pieces", "No help this time.", "frac2",
         [f"{k}/{n} = [{k}] pieces of 1/{n}" for k, n in ((3, 8), (5, 6), (2, 5), (3, 10), (6, 8), (2, 6),
                                                          (3, 4), (8, 10), (4, 8), (2, 10), (4, 10), (7, 10))])
    part(8, "Words and numbers", "No help this time.", "frac2",
         [f"{frac_words(k, n)} = [{k}]/{n}" for k, n in ((2, 5), (5, 6), (3, 8), (7, 10), (3, 4), (4, 6),
                                                          (2, 3), (5, 8), (6, 10), (4, 5))])
    part(9, "How much is left?", "No help this time. Shaded and not shaded make the whole.", "frac2",
         [f"{k}/{n} shaded, [{n - k}]/{n} not shaded" for k, n in ((3, 8), (1, 6), (4, 10), (2, 5), (1, 4),
                                                                    (5, 8), (2, 3), (3, 6))])
    part(10, "Remember?", "Problems from earlier packets.", "eq2", REVIEW_COUNTF)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 11, "Word problems", "Draw a picture.")
    for i, story in enumerate(WORDS_COUNTF):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 11, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_COUNTF = ["8 groups of 3 = [24]", "6 cm by 8 cm: area = [48] sq cm", "Round 547 to the nearest ten: [550]",
                 "4 groups of 7 = [28]", "Round 351 to the nearest hundred: [400]", "Round 762 to the nearest ten: [760]"]

WORDS_COUNTF = [
    ("A pizza has 8 equal slices. Tom eats 3 slices. What fraction of the pizza does he eat?",
     "3 pieces of 1/8 = 3/8", "3/8", "of the pizza"),
    ("A garden has 5 equal rows. 2 rows are beans. What fraction of the garden is beans?",
     "2 pieces of 1/5 = 2/5", "2/5", "of the garden"),
    ("A chocolate bar has 6 equal pieces. Ben eats 1 piece. What fraction of the bar is left?",
     "1/6 eaten, 5/6 left", "5/6", "of the bar"),
    ("Mia paints 4 of the 10 equal parts of a fence. What fraction is not painted yet?",
     "4/10 painted, 6/10 not painted", "6/10", "of the fence"),
    ("Challenge: Sam eats 2/8 of a pie. Kim eats 3/8 of it. How much of the pie do they eat in all?",
     "2 eighths and 3 eighths = 5 eighths", "5/8", "of the pie"),
]

KINDS_COUNTF = {
    "count_pieces": Kind(64, 1, lambda it: f"count the pieces: {it[0]} cut in {it[1]}, {it[2]} shaded", c_count_pieces, 8),
    "frac_name": Kind(72, 2, lambda it: f"name the fraction: {it[0]} cut in {it[1]}, {it[2]} shaded", c_frac_name),
    "frac_shade": Kind(72, 2, lambda it: f"shade the fraction: {it[0]} cut in {it[1]}, {it[2]} parts", c_frac_shade),
    "shaded_not": Kind(84, 2, lambda it: f"shaded and not: {it[0]} cut in {it[1]}, {it[2]} shaded", c_shaded_not),
}
KINDS.update(KINDS_COUNTF)

_CF_DENS = (3, 4, 5, 6, 8, 10)
_CF_KINDS = {"strip": _CF_DENS, "circle": _CF_DENS, "rect": _CF_DENS, "tall": (3, 4, 5, 6), "square": (3, 4, 5, 6, 8)}
FRAC_PICS = [(k, n, a) for k, ns in _CF_KINDS.items() for n in ns for a in rng(2, n - 1)]
COUNT_BY = ([" ".join(f"{i}/{n}" if i not in (b, b + 1) else f"[{i}]/{n}" for i in rng(s, s + 3))
             for n in (5, 6, 8, 10) for s in rng(1, n - 3) for b in (s + 1, s + 2) if b + 1 <= s + 3])
COUNTF_FACTS = ([f"{k} pieces of 1/{n} = [{k}]/{n}" for n in _CF_DENS for k in rng(2, n - 1)]
                + [f"{k}/{n} = [{k}] pieces of 1/{n}" for n in _CF_DENS for k in rng(2, n - 1)]
                + [f"{frac_words(k, n)} = [{k}]/{n}" for n in _CF_DENS for k in rng(2, n - 1)])
LEFT_FACTS = [f"{k}/{n} shaded, [{n - k}]/{n} not shaded" for n in _CF_DENS for k in rng(1, n - 1)]

CHECKINS["40-counting-fractions"] = [
    S("Name the fraction", None, "frac_name", FRAC_PICS, 2),
    S("Shade it", None, "frac_shade", FRAC_PICS, 2),
    S("Count by fractions", None, "frac2", COUNT_BY, 2),
    S("Pieces and fractions", None, "frac2", COUNTF_FACTS, 2),
    S("How much is left?", None, "frac2", LEFT_FACTS, 2),
]


def strips(bk, x, top, w, n, count, shaded=0, answer=0, h=18, gap=6):
    """count strips of n parts stacked from y = top down; the first `shaded` parts filled across them
    (or `answer` parts on the key). Returns the height used."""
    for j in range(count):
        strip(bk, x, top - h - j * (h + gap), w, h, n, shaded=max(0, min(n, shaded - j * n)),
              answer=max(0, min(n, answer - j * n)))
    return count * h + (count - 1) * gap


def whole_text(t, n):
    """7/4 -> "1 whole and [3]/4"; 11/4 -> "2 wholes and [3]/4"."""
    q, r = divmod(t, n)
    return f"{q} whole{'s' if q > 1 else ''} and [{r}]/{n}"


def c_one_whole(bk, x, cy, w, item):
    kind, n = item
    ph = FRAC_PIC_H[kind]
    frac_pic(bk, kind, x + GUT, cy + (72 - ph) / 2, n, shaded=range(n), s=96 if kind == "strip" else None)
    frac_expr(bk, x + w - 96, cy + 30, f"[{n}]/{n} = 1", size=18)


def c_wholes(bk, x, cy, w, item):
    """k full strips of n: how many pieces, how many wholes."""
    n, k = item
    hh = strips(bk, x + GUT, cy + 42 + k * 12, 108, n, k, shaded=n * k, h=16, gap=6)
    frac_fit(bk, x + GUT + 124, cy + 36, w - GUT - 132, f"[{n * k}]/{n} = [{k}]", size=18)


def c_more_whole(bk, x, cy, w, item):
    """Fractions bigger than 1: full strips, then a part strip."""
    n, t = item
    k = -(-t // n)
    strips(bk, x + GUT, cy + 40 + k * 12, 150, n, k, shaded=t, h=16, gap=6)
    frac_fit(bk, x + GUT + 172, cy + 34, w - GUT - 182, f"[{t}]/{n} = " + whole_text(t, n), size=17)


def c_shade_more(bk, x, cy, w, item):
    n, t = item
    k = -(-t // n)
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 38, "Shade")
    frac_expr(bk, x + GUT + 46, cy + 37, f"{t}/{n}", size=18)
    strips(bk, x + GUT + 94, cy + 42 + k * 12, w - GUT - 106, n, k, answer=t, h=16, gap=6)


ONE_WORDS = ("less than 1", "= 1", "more than 1")


def one_side(a, b):
    return ONE_WORDS[0] if a < b else ONE_WORDS[1] if a == b else ONE_WORDS[2]


def c_vs_one(bk, x, cy, w, item):
    a, b = item
    frac_expr(bk, x + GUT, cy + 16, f"{a}/{b}", size=18)
    circle_choice(bk, x + GUT + 40, cy + 17, ONE_WORDS, one_side(a, b), size=11, gap=13)


def learn_fractions_wholes(bk):
    y = bk.new_page("Fractions and Wholes", "All the pieces make 1 whole. More pieces go past 1.", name_line=False,
                    big=True, footer="WeMath  ·  Fractions and Wholes")
    c = bk.c
    label(bk, M, y - 6, "All the pieces: 1 whole")
    strip(bk, M + 14, y - 54, 200, 28, 4, shaded=4)
    frac_expr(bk, M + 236, y - 48, "4/4 = 1", size=24)
    strip(bk, M + 14, y - 92, 200, 28, 6, shaded=6)
    frac_expr(bk, M + 236, y - 86, "6/6 = 1", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 370, y - 50, "Top and bottom the same?")
    c.drawString(M + 370, y - 68, "Then it's 1 whole.")
    y -= 118

    label(bk, M, y - 6, "More than 1 whole")
    strips(bk, M + 14, y - 22, 200, 4, 2, shaded=7, h=26, gap=8)
    frac_expr(bk, M + 236, y - 58, "7/4 = 1 whole and 3/4", size=20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 236, y - 86, "Count on past 4/4: 5/4, 6/4, 7/4.")
    y -= 112

    label(bk, M, y - 6, "Whole numbers are fractions too")
    strips(bk, M + 14, y - 22, 200, 4, 2, shaded=8, h=22, gap=6)
    frac_expr(bk, M + 236, y - 50, "8/4 = 2", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 46, "8 fourths fill 2 bars.")
    for j in range(3):
        strip(bk, M + 14 + j * 70, y - 104, 60, 22, 1, shaded=1)
    frac_expr(bk, M + 236, y - 98, "3/1 = 3", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 94, "3 pieces, each a whole.")
    y -= 126

    bottom = your_turn(bk, y, h=100)
    bk.ask("how many wholes: 2 strips of 3 your turn")
    strips(bk, M + 130, bottom + 72, 160, 3, 2, shaded=6, h=20, gap=6)
    frac_expr(bk, M + 320, bottom + 44, "[6]/3 = [2]", size=24)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: b/b = 1, fractions bigger than 1, and whole numbers as fractions (3.NF.3c). Say "
                     "“How many pieces make one whole bar? Count on past it.” No mixed-number rules yet: 7/4 is "
                     "1 whole and 3/4.")


def practice_fractions_wholes(bk):
    title = "Fractions and Wholes: Practice"
    y = bk.new_page(title, "When the top number matches the bottom, that's 1 whole.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "One whole", "Every part is shaded. How many pieces?", "one_whole",
         [("circle", 6), ("strip", 5), ("rect", 8), ("tall", 3), ("circle", 10), ("square", 4)])
    part(2, "How many wholes?", "Count the pieces, then the whole bars.", "wholes",
         [(3, 2), (4, 3), (2, 3), (6, 2), (5, 2), (8, 2), (2, 2), (3, 3)])
    part(3, "More than one whole", "Full bars first, then the pieces left.", "more_whole",
         [(4, 5), (3, 5), (6, 8), (8, 11), (5, 7), (2, 3), (4, 10), (3, 7)])
    part(4, "Shade it", None, "shade_more",
         [(3, 4), (4, 6), (6, 9), (2, 5), (5, 8), (8, 10)])
    part(5, "Less than, equal to, or more than 1?", "Circle one.", "vs_one",
         [(5, 4), (3, 8), (6, 6), (2, 3), (9, 8), (10, 10), (7, 5), (4, 6), (3, 3), (12, 10)])
    part(6, "One whole", "No help this time.", "frac3",
         ["5/5 = [1]", "[8]/8 = 1", "10/10 = [1]", "[3]/3 = 1", "2/2 = [1]", "[6]/6 = 1"])
    part(7, "Whole numbers", "No help this time.", "frac3",
         ["12/4 = [3]", "10/5 = [2]", "6/2 = [3]", "9/3 = [3]", "16/8 = [2]", "12/6 = [2]", "8/2 = [4]",
          "15/5 = [3]", "20/10 = [2]", "4/1 = [4]", "18/6 = [3]", "6/3 = [2]"])
    part(8, "Write the whole number as a fraction", "No help this time.", "frac3",
         ["[8]/2 = 4", "[12]/3 = 4", "[16]/4 = 4", "[10]/2 = 5", "[24]/8 = 3", "[30]/10 = 3", "[6]/1 = 6",
          "[20]/5 = 4", "[24]/6 = 4"])
    part(9, "More than one whole", "No help this time.", "frac2",
         ["9/8 = 1 whole and [1]/8", "7/5 = 1 whole and [2]/5", "11/4 = 2 wholes and [3]/4",
          "8/6 = 1 whole and [2]/6", "13/10 = 1 whole and [3]/10", "5/2 = 2 wholes and [1]/2",
          "10/3 = 3 wholes and [1]/3", "11/6 = 1 whole and [5]/6", "17/8 = 2 wholes and [1]/8",
          "9/4 = 2 wholes and [1]/4"])
    part(10, "Count past 1", "No help this time.", "frac2",
         ["3/4 4/4 [5]/4 [6]/4 7/4", "4/5 5/5 [6]/5 [7]/5", "2/3 3/3 4/3 [5]/3 [6]/3", "7/8 8/8 [9]/8 [10]/8",
          "1/2 2/2 [3]/2 [4]/2 5/2", "5/6 6/6 7/6 [8]/6 [9]/6"])
    part(11, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_WHOLES)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 12, "Word problems", "Draw the bars.")
    for i, story in enumerate(WORDS_WHOLES):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 12, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_WHOLES = ["9 cm by 3 cm: area = [27] sq cm", "Round 436 to the nearest ten: [440]", "two tenths = [2]/10",
                 "6 groups of 8 = [48]", "4 pieces of 1/8 = [4]/8", "Round 819 to the nearest hundred: [800]"]

WORDS_WHOLES = [
    ("Ana has 2 pizzas. Each one is cut into 4 equal slices. How many fourths are there in all?",
     "2 wholes = 8/4", "8", "fourths"),
    ("Lee needs 1 cup of milk but only has a 1/3 cup scoop. How many scoops make 1 cup?",
     "3/3 = 1", "3", "scoops"),
    ("Max eats 6 halves of apples. How many whole apples is that?", "6/2 = 3", "3", "apples"),
    ("Sam has 7 pieces of two same-size bars. Each bar has 4 pieces. Is that more than 1 bar?",
     "7/4 = 1 whole and 3/4", "yes", ""),
    ("Challenge: Jo has 10 eighths of a pie. How many whole pies is that, and how many eighths?",
     "10/8 = 1 whole and 2/8", "1 and 2/8", "pies"),
]

KINDS_WHOLES = {
    "one_whole": Kind(72, 2, lambda it: f"one whole: {it[0]} cut in {it[1]}, all shaded", c_one_whole),
    "wholes": Kind(84, 2, lambda it: f"how many wholes: {it[1]} strips of {it[0]}", c_wholes),
    "more_whole": Kind(84, 1, lambda it: f"more than one whole: {it[1]}/{it[0]} in strips", c_more_whole, 8),
    "shade_more": Kind(84, 2, lambda it: f"shade more than one: {it[1]}/{it[0]}", c_shade_more),
    "vs_one": Kind(48, 2, lambda it: f"less, equal or more than 1: {it[0]}/{it[1]}", c_vs_one, 8),
}
KINDS.update(KINDS_WHOLES)
BALANCE["vs_one"] = lambda it: it[0] > it[1]

_W_DENS = (2, 3, 4, 5, 6, 8, 10)
WHOLE_FACTS = ([f"{n * k}/{n} = [{k}]" for n in _W_DENS for k in rng(2, 4)]
               + [f"[{n * k}]/{n} = {k}" for n in _W_DENS for k in rng(2, 5)]
               + [f"{n}/{n} = [1]" for n in _W_DENS] + [f"{k}/1 = [{k}]" for k in rng(2, 9)])
MORE_FACTS = [f"{t}/{n} = " + whole_text(t, n) for n in _W_DENS for t in rng(n + 1, 3 * n - 1) if t % n]
VS_ONE = [(a, b) for b in (3, 4, 5, 6, 8) for a in rng(1, 2 * b) if a != b]

CHECKINS["41-fractions-and-wholes"] = [
    S("How many wholes?", None, "wholes", [(n, k) for n in (2, 3, 4, 5, 6, 8) for k in (2, 3)], 2),
    S("More than one whole", None, "more_whole", [(n, t) for n in (3, 4, 5, 6) for t in rng(n + 1, 2 * n - 1)], 1),
    S("Less than, equal to, or more than 1?", None, "vs_one", VS_ONE, 2),
    S("Wholes", None, "frac3", WHOLE_FACTS, 3),
    S("Past one whole", None, "frac2", MORE_FACTS, 2),
]


def fraction_wall(bk, x, top, w, dens=(1, 2, 3, 4, 6, 8), row=20, gap=4, labels=True, size=11):
    """The fraction wall: one strip per denominator, all the same length, each piece labelled."""
    c = bk.c
    for i, n in enumerate(dens):
        yy = top - row - i * (row + gap)
        strip(bk, x, yy, w, row, n, lw=1)
        if labels:
            for j in range(n):
                frac_expr(bk, x + w * (j + 0.5) / n - (size * 0.8 + 6) / 2 if n > 1 else x + w / 2 - 4,
                          yy + row / 2 - size * 0.2, f"1/{n}" if n > 1 else "1", size=size * (0.85 if n >= 8 else 1))
    return len(dens) * (row + gap) - gap


def c_same_amount(bk, x, cy, w, item):
    """Two strips of the same whole: same amount shaded? The key rings yes or no."""
    a, b, p, q = item
    sw_ = w - GUT - 112
    for j, (k, n) in enumerate(((a, b), (p, q))):
        yy = cy + 46 - j * 30
        frac_expr(bk, x + GUT, yy + 2, f"{k}/{n}", size=14)
        strip(bk, x + GUT + 30, yy, sw_, 18, n, shaded=k)
    yes_no_choice(bk, x, cy + 6, w, a * q == b * p)


def c_match_frac(bk, x, cy, w, item):
    """Top strip shaded; the bottom strip has different pieces. Shade the same amount, then name it."""
    (a, b), q = item
    k = a * q // b
    sw_ = w - GUT - 170
    strip(bk, x + GUT, cy + 50, sw_, 20, b, shaded=a)
    strip(bk, x + GUT, cy + 20, sw_, 20, q, answer=k)
    frac_expr(bk, x + GUT + sw_ + 22, cy + 38, f"{a}/{b} = [{k}]/{q}", size=22)


def learn_equal_fractions(bk):
    y = bk.new_page("Equal Fractions", "Different pieces, same amount.", name_line=False, big=True,
                    footer="WeMath  ·  Equal Fractions")
    c = bk.c
    label(bk, M, y - 6, "The fraction wall")
    hh = fraction_wall(bk, M + 14, y - 20, 300)
    c.setStrokeColor(T.accent)
    c.setLineWidth(1.4)
    c.setDash(3, 2.5)
    c.line(M + 164, y - 16, M + 164, y - 24 - hh)
    c.setDash()
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 36, "Follow the dashed line:")
    frac_expr(bk, M + 340, y - 66, "1/2 = 2/4 = 3/6 = 4/8", size=16)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 100, "Same length, so they are")
    c.drawString(M + 340, y - 116, "equal fractions.")
    y -= hh + 44

    label(bk, M, y - 6, "Cut every piece in two")
    strip(bk, M + 14, y - 52, 240, 26, 3, shaded=1)
    frac_expr(bk, M + 272, y - 46, "1/3", size=22)
    strip(bk, M + 14, y - 88, 240, 26, 6, shaded=2)
    frac_expr(bk, M + 272, y - 82, "2/6", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 330, y - 42, "Twice as many pieces,")
    c.drawString(M + 330, y - 58, "each half as big.")
    frac_expr(bk, M + 330, y - 90, "1/3 = 2/6", size=18)
    y -= 112

    bottom = your_turn(bk, y, h=104)
    bk.ask("equal fractions: 3/4 in eighths your turn")
    strip(bk, M + 130, bottom + 58, 200, 22, 4, shaded=3)
    strip(bk, M + 130, bottom + 26, 200, 22, 8, answer=6)
    frac_expr(bk, M + 360, bottom + 44, "3/4 = [6]/8", size=24)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: equal fractions name the same amount of the same whole (3.NF.3a–b). Line the strips up: "
                     "“Is the shaded part the same length?” Cutting every piece in two doubles the top and the "
                     "bottom.")


def practice_equal_fractions(bk):
    title = "Equal Fractions: Practice"
    y = bk.new_page(title, "Same whole, same amount shaded: the fractions are equal.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Same amount?", "Same whole. Is the same amount shaded? Circle yes or no.", "same_amount",
         [(1, 2, 3, 6), (2, 3, 3, 4), (1, 4, 2, 8), (3, 5, 6, 10), (2, 6, 1, 4), (3, 4, 6, 8), (1, 3, 3, 8),
          (4, 10, 2, 5)])
    part(2, "Line them up", "Count the shaded pieces in the second strip.", "equiv_frac",
         [((1, 2), 4), ((1, 3), 6), ((3, 4), 8), ((2, 5), 10), ((2, 3), 6), ((1, 4), 8)])
    part(3, "Shade to match", "Shade the same amount in the second strip, then write the fraction.", "match_frac",
         [((1, 2), 8), ((1, 5), 10), ((2, 4), 8), ((1, 2), 6), ((3, 5), 10), ((1, 2), 10)])
    part(4, "Find the top number", "No help this time. Picture the wall.", "frac3",
         ["1/2 = [4]/8", "2/3 = [4]/6", "1/4 = [2]/8", "4/5 = [8]/10", "1/2 = [5]/10", "3/4 = [6]/8",
          "1/5 = [2]/10", "1/3 = [2]/6", "2/4 = [4]/8", "3/5 = [6]/10", "1/2 = [3]/6", "2/5 = [4]/10"])
    part(5, "Fewer, bigger pieces", "No help this time. Same amount with bigger pieces.", "frac3",
         ["4/8 = [1]/2", "2/6 = [1]/3", "6/8 = [3]/4", "8/10 = [4]/5", "2/8 = [1]/4", "5/10 = [1]/2",
          "4/6 = [2]/3", "6/10 = [3]/5", "3/6 = [1]/2", "2/10 = [1]/5", "2/4 = [1]/2", "4/10 = [2]/5"])
    part(6, "Find the bottom number", "No help this time.", "frac3",
         ["1/2 = 2/[4]", "1/3 = 2/[6]", "3/4 = 6/[8]", "1/5 = 2/[10]", "2/3 = 4/[6]", "1/2 = 4/[8]",
          "4/8 = 1/[2]", "6/10 = 3/[5]", "2/8 = 1/[4]"])
    part(7, "Halves in disguise", "No help this time. Each one is the same as 1/2.", "frac3",
         ["2/4 = [3]/6", "3/6 = [4]/8", "4/8 = [5]/10", "2/4 = [5]/10", "3/6 = [5]/10", "5/10 = [4]/8"])
    part(8, "Keep going", "No help this time.", "frac2",
         ["1/2 = [2]/4 = [4]/8", "3/6 = [2]/4 = [1]/2", "1/2 = [3]/6 = [5]/10", "8/8 = [4]/4 = [2]/2",
          "1/2 = [2]/4 = [3]/6 = [4]/8", "2/2 = [3]/3 = [5]/5"])
    part(9, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_EQUALF)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 10, "Word problems", "Draw strips to check.")
    for i, story in enumerate(WORDS_EQUALF):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 10, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_EQUALF = ["Round 655 to the nearest ten: [660]", "8 m by 6 m: area = [48] sq m", "three fifths = [3]/5",
                 "10/2 = [5]", "7/4 = 1 whole and [3]/4", "8 groups of 6 = [48]"]

WORDS_EQUALF = [
    ("Ana ate 2/4 of a pizza. Ben ate 1/2 of a same-size pizza. Did they eat the same amount?",
     "2/4 = 1/2", "yes", ""),
    ("A ribbon has 8 equal parts. Mia uses 4 of them. What fraction of the ribbon is that, in halves?",
     "4/8 = 1/2", "1/2", "of the ribbon"),
    ("Leo shades 1/3 of a bar. Kim's same-size bar has 6 parts. How many should Kim shade?",
     "1/3 = 2/6", "2", "parts"),
    ("A cake is cut into 10 equal slices. Half of the cake is eaten. How many slices is that?",
     "1/2 = 5/10", "5", "slices"),
    ("Challenge: Sam ran 3/4 of a mile. Jo ran 6/8 of a mile. Who ran farther?", "3/4 = 6/8",
     "same", "distance"),
]

KINDS_EQUALF = {
    "same_amount": Kind(78, 2, lambda it: f"same amount? {it[0]}/{it[1]} and {it[2]}/{it[3]}", c_same_amount),
    "match_frac": Kind(84, 1, lambda it: f"shade to match: {it[0][0]}/{it[0][1]} in {it[1]}ths", c_match_frac, 8),
}
KINDS.update(KINDS_EQUALF)
BALANCE["same_amount"] = lambda it: it[0] * it[3] == it[1] * it[2]

_E_PAIRS = [(n, m) for n in (2, 3, 4, 5) for m in (4, 6, 8, 10) if m % n == 0 and m > n]
EQUAL_TOP = [f"{a}/{n} = [{a * m // n}]/{m}" for n, m in _E_PAIRS for a in rng(1, n - 1)]
EQUAL_DOWN = [f"{a * m // n}/{m} = [{a}]/{n}" for n, m in _E_PAIRS for a in rng(1, n - 1)]
EQUAL_BOTTOM = ([f"{a}/{n} = {a * m // n}/[{m}]" for n, m in _E_PAIRS for a in rng(1, n - 1)]
                + [f"{a * m // n}/{m} = {a}/[{n}]" for n, m in _E_PAIRS for a in rng(1, n - 1)])
SAME_AMOUNT = ([(a, n, a * m // n, m) for n, m in _E_PAIRS for a in rng(1, n - 1)]
               + [(a, n, b, m) for n, m in _E_PAIRS for a in rng(1, n - 1) for b in rng(1, m - 1)
                  if b * n != a * m and abs(b * n - a * m) <= n])

CHECKINS["42-equal-fractions"] = [
    S("Same amount?", "Circle yes or no.", "same_amount", SAME_AMOUNT, 2),
    S("Shade to match", None, "match_frac", [((a, n), m) for n, m in _E_PAIRS for a in rng(1, n - 1)], 1),
    S("Find the top number", None, "frac3", EQUAL_TOP + EQUAL_DOWN, 3),
    S("Find the bottom number", None, "frac3", EQUAL_BOTTOM, 3),
]


def frac_sign(a, b, p, q):
    return sign_of(Fraction(a, b), Fraction(p, q))


def c_compare_shapes(bk, x, cy, w, item):
    """Two same-size shapes, a sign box between, each fraction written under its shape."""
    kind, (a, b), (p, q) = item
    s = 50 if kind == "circle" else 44
    sw_, sh_ = share_size(kind, s)
    x1 = x + GUT
    x2 = x1 + sw_ + 66
    share_shape(bk, kind, x1, cy + 30, s, b, shaded=range(a))
    share_shape(bk, kind, x2, cy + 30, s, q, shaded=range(p))
    bk.box(x1 + sw_ + 15, cy + 30 + sh_ / 2 - 14, 36, 28, frac_sign(a, b, p, q), size=18)
    frac_expr(bk, x1 + sw_ / 2 - 9, cy + 9, f"{a}/{b}", size=13)
    frac_expr(bk, x2 + sw_ / 2 - 9, cy + 9, f"{p}/{q}", size=13)


def c_biggest(bk, x, cy, w, item):
    """Three fractions; the key rings the biggest."""
    c = bk.c
    best = max(item, key=lambda f: Fraction(*f))
    fx = x + GUT + 6
    for a, b in item:
        frac_expr(bk, fx, cy + 16, f"{a}/{b}", size=18)
        if bk.key and (a, b) == best:
            c.setStrokeColor(T.answer)
            c.setLineWidth(1.5)
            c.ellipse(fx - 9, cy + 2, fx + 27, cy + 42, stroke=1, fill=0)
        fx += 56


def learn_comparing_fractions(bk):
    y = bk.new_page("Comparing Fractions", "Same whole? Then look at the pieces.", name_line=False, big=True,
                    footer="WeMath  ·  Comparing Fractions")
    c = bk.c
    label(bk, M, y - 6, "Same bottom number: same size pieces")
    strip(bk, M + 14, y - 46, 200, 22, 8, shaded=3)
    strip(bk, M + 14, y - 76, 200, 22, 8, shaded=5)
    frac_expr(bk, M + 236, y - 62, "3/8 < 5/8", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 370, y - 50, "More pieces of the")
    c.drawString(M + 370, y - 66, "same size is more.")
    y -= 98

    label(bk, M, y - 6, "Same top number: look at the size")
    strip(bk, M + 14, y - 46, 200, 22, 3, shaded=2)
    strip(bk, M + 14, y - 76, 200, 22, 6, shaded=2)
    frac_expr(bk, M + 236, y - 62, "2/3 > 2/6", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 370, y - 50, "Same number of pieces,")
    c.drawString(M + 370, y - 66, "but thirds are bigger.")
    y -= 98

    label(bk, M, y - 6, "Only compare the same whole")
    share_shape(bk, "circle", M + 20, y - 66, 40, 2, shaded=[0])
    share_shape(bk, "circle", M + 100, y - 86, 70, 2, shaded=[0])
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 236, y - 40, "Half of a small pizza is less")
    c.drawString(M + 236, y - 56, "than half of a big pizza.")
    c.drawString(M + 236, y - 80, "Compare fractions of the same whole.")
    y -= 104

    label(bk, M, y - 6, "Equal? The strips line up.")
    frac_expr(bk, M + 14, y - 42, "2/4 = 1/2", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 160, y - 38, "Use the fraction wall from Equal Fractions.")
    y -= 62

    bottom = your_turn(bk, y, h=94)
    bk.ask("compare fractions: 3/5 and 4/5 your turn")
    strip(bk, M + 130, bottom + 50, 160, 18, 5, shaded=3)
    strip(bk, M + 130, bottom + 22, 160, 18, 5, shaded=4)
    frac_expr(bk, M + 320, bottom + 38, "3/5 [<] 4/5", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: compare two fractions of the same whole with <, > or = (3.NF.3d). Ask “Same size "
                     "pieces? Then who has more pieces?” or “Same number of pieces? Then whose pieces are bigger?”")


def practice_comparing_fractions(bk):
    title = "Comparing Fractions: Practice"
    y = bk.new_page(title, "Same whole. Write <, > or =.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Compare with strips", "Look at how much is shaded.", "compare_frac",
         [((3, 8), (5, 8)), ((2, 3), (2, 6)), ((4, 5), (2, 5)), ((1, 2), (2, 4)), ((3, 10), (3, 4)),
          ((5, 6), (1, 6)), ((2, 8), (2, 3)), ((3, 6), (1, 2))])
    part(2, "Compare with shapes", "Same size shapes.", "compare_shapes",
         [("circle", (2, 4), (3, 4)), ("rect", (1, 3), (1, 5)), ("circle", (5, 6), (4, 6)),
          ("square", (2, 4), (2, 3)), ("circle", (1, 2), (3, 6)), ("rect", (3, 5), (4, 5))])
    plain = "frac3"
    part(3, "Same bottom number", "No help this time. Same size pieces: more pieces is more.", plain,
         ["4/6 [>] 3/6", "2/5 [<] 3/5", "7/8 [>] 3/8", "1/4 [<] 3/4", "6/10 [>] 4/10", "2/3 [>] 1/3",
          "3/10 [<] 9/10", "5/8 [>] 1/8", "1/5 [<] 4/5", "5/6 [>] 2/6", "2/8 [<] 6/8", "7/10 [>] 2/10"])
    part(4, "Same top number", "No help this time. Same number of pieces: bigger pieces is more.", plain,
         ["2/5 [>] 2/8", "3/10 [<] 3/4", "3/8 [<] 3/5", "2/3 [>] 2/4", "4/6 [>] 4/10", "2/10 [<] 2/6",
          "4/8 [<] 4/5", "3/4 [>] 3/6", "3/6 [<] 3/5", "2/4 [>] 2/10", "2/8 [<] 2/5", "5/8 [>] 5/10"])
    part(5, "Unit fractions", "No help this time.", plain,
         ["1/3 [>] 1/8", "1/10 [<] 1/2", "1/6 [<] 1/3", "1/4 [>] 1/5", "1/2 [>] 1/4", "1/8 [<] 1/6",
          "1/3 [<] 1/2", "1/5 [>] 1/10", "1/6 [>] 1/8"])
    part(6, "Equal or not?", "No help this time. Some are equal fractions.", plain,
         ["2/4 [=] 1/2", "3/8 [<] 4/8", "2/6 [=] 1/3", "4/5 [>] 3/5", "6/8 [=] 3/4", "5/10 [=] 1/2",
          "2/10 [=] 1/5", "4/8 [=] 2/4", "5/8 [>] 3/8"])
    part(7, "Circle the biggest", "No help this time.", "biggest",
         [((5, 6), (2, 6), (3, 6)), ((1, 4), (1, 8), (1, 2)), ((3, 10), (3, 4), (3, 5)), ((7, 8), (4, 8), (2, 8)),
          ((2, 5), (2, 10), (2, 3)), ((1, 6), (1, 3), (1, 10))])
    part(8, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_COMPAREF)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Draw strips to compare.")
    for i, story in enumerate(WORDS_COMPAREF):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_COMPAREF = ["4/5 = 8/[10]", "12/3 = [4]", "Round 384 to the nearest hundred: [400]", "3 groups of 8 = [24]",
                   "9 m by 4 m: area = [36] sq m", "two eighths = [2]/8"]

WORDS_COMPAREF = [
    ("Kim ate 3/8 of a pizza. Leo ate 5/8 of the same pizza. Who ate more?", "3/8 < 5/8", "Leo", ""),
    ("Ana ran 2/3 of a mile. Ben ran 2/6 of a mile. Who ran farther?", "2/3 > 2/6", "Ana", ""),
    ("A red ribbon is 1/4 of a yard. A blue ribbon is 1/2 of a yard. Which one is shorter?", "1/4 < 1/2",
     "red", "ribbon"),
    ("Mia's glass is 4/6 full. Sam's same-size glass is 2/3 full. Who has more juice?", "4/6 = 2/3", "same", ""),
    ("Challenge: Jo says half of a small pizza is as much as half of a big pizza. Is Jo right?",
     "1/2 of different wholes", "no", ""),
]

KINDS_COMPAREF = {
    "compare_shapes": Kind(90, 2, lambda it: f"compare shapes: {it[0]} {it[1][0]}/{it[1][1]} and {it[2][0]}/{it[2][1]}",
                           c_compare_shapes),
    "biggest": Kind(48, 2, lambda it: "biggest: " + " ".join(f"{a}/{b}" for a, b in it), c_biggest, 8),
}
KINDS.update(KINDS_COMPAREF)
BALANCE["compare_shapes"] = lambda it: frac_sign(*it[1], *it[2]) == "<"

_C_DENS = (3, 4, 5, 6, 8, 10)
SAME_BOTTOM = [f"{a}/{n} [{sign_of(a, b)}] {b}/{n}" for n in _C_DENS for a in rng(1, n - 1) for b in rng(1, n - 1)
               if a != b]
SAME_TOP = [f"{a}/{n} [{frac_sign(a, n, a, m)}] {a}/{m}" for a in (1, 2, 3, 4, 5) for n in _C_DENS for m in _C_DENS
            if n != m and a < min(n, m)]
BIGGEST = [tuple((a, n) for a in t) for n in (5, 6, 8, 10) for t in ((1, 4, 2), (3, 1, 2), (2, 3, 4)) if max(t) < n]

CHECKINS["43-comparing-fractions"] = [
    S("Compare with strips", None, "compare_frac", [((a, n), (b, n)) for n in (4, 5, 6, 8) for a in rng(1, n - 1)
                                                    for b in rng(1, n - 1) if a < b] +
      [((a, n), (a, m)) for a in (1, 2, 3) for n in (3, 4, 6, 8) for m in (3, 4, 6, 8) if n < m and a < n], 1),
    S("Same bottom number", "Write <, > or =.", "frac3", SAME_BOTTOM, 3, balance=is_less),
    S("Same top number", "Write <, > or =.", "frac3", SAME_TOP, 3, balance=is_less),
    S("Circle the biggest", None, "biggest", BIGGEST, 2),
]


def group_rings(bk, x, cy, d, each, mark=0, rings=True, answer_k=0, r=4.2, step=12):
    """d equal groups of `each` dots in a row, each group in a rounded ring (rings=False: the key draws them).
    The first `mark` groups are drawn in the second colour (the groups you count); on the key the first
    `answer_k` rings are drawn in red. cy = centre line. Returns the width."""
    c = bk.c
    cols = min(each, 3)
    rows = -(-each // cols)
    gw, gh = cols * step + 8, rows * step + 8
    gx = x
    for g in range(d):
        for j in range(each):
            rr, cc = divmod(j, cols)
            bk.dot(gx + 4 + step / 2 + cc * step, cy + gh / 2 - 4 - step / 2 - rr * step, r, "b" if g < mark else "a")
        if rings or bk.key:
            red = bk.key and (g < answer_k or not rings)
            c.setStrokeColor(T.answer if red else T.muted)
            c.setLineWidth(1.5 if red else 1)
            c.roundRect(gx, cy - gh / 2, gw, gh, 7, stroke=1, fill=0)
        gx += gw + (8 if rings else 4)
    return gx - x


def c_group_frac(bk, x, cy, w, item):
    """Fraction of a group: n dots in d rings; find k of them."""
    n, d, k, mode = item
    each = n // d
    gw = group_rings(bk, x + GUT, cy + 35, d, each, mark=k if mode == "marked" else 0,
                     rings=mode != "ring", answer_k=k if mode != "marked" else 0)
    tail = f"{k}/{d} of {n} = [{n // d * k}]"
    tx = x + GUT + max(gw, 150) + 26
    frac_fit(bk, tx, cy + 28, x + w - tx - 10, tail, size=18)


def learn_fraction_of_group(bk):
    y = bk.new_page("Fractions of a Group", "Share the group into equal parts, then count the parts you need.",
                    name_line=False, big=True, footer="WeMath  ·  Fractions of a Group")
    c = bk.c
    label(bk, M, y - 6, "1/3 of 12: make 3 equal groups")
    group_rings(bk, M + 14, y - 46, 3, 4, mark=1)
    frac_expr(bk, M + 230, y - 54, "1/3 of 12 = 4", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 410, y - 40, "One group")
    c.drawString(M + 410, y - 56, "out of 3.")
    y -= 92

    label(bk, M, y - 6, "Think division")
    color_eq(bk, M + 14, y - 42, [("12", None), (DIV, "op"), ("3", None), ("=", "op"), ("4", "b")], 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 230, y - 38, "The bottom number tells how many groups.")
    y -= 66

    label(bk, M, y - 6, "2/3 of 12: two of the groups")
    group_rings(bk, M + 14, y - 46, 3, 4, mark=2)
    frac_expr(bk, M + 230, y - 54, "2/3 of 12 = 8", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 410, y - 40, "4 + 4 = 8,")
    c.drawString(M + 410, y - 56, "two groups.")
    y -= 92

    label(bk, M, y - 6, "The steps")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 13)
    c.drawString(M + 14, y - 34, "1. Divide by the bottom number: that's one group.")
    c.drawString(M + 14, y - 56, "2. Times the top number: that many groups.")
    frac_expr(bk, M + 14, y - 92, "3/4 of 20: 20 ÷ 4 = 5, 3 × 5 = 15", size=18)
    y -= 118

    bottom = your_turn(bk, y, h=92)
    bk.ask("fraction of a group: 1/4 of 8 your turn")
    group_rings(bk, M + 130, bottom + 40, 4, 2)
    frac_expr(bk, M + 330, bottom + 34, "1/4 of 8 = [2]", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: find a fraction of a group (a bridge to 4.NF.4). Say “Share it into equal groups: the "
                     "bottom number says how many. One group is one third. Two groups are two thirds.”")


def practice_fraction_of_group(bk):
    title = "Fractions of a Group: Practice"
    y = bk.new_page(title, "Bottom number: how many equal groups. Top number: how many groups to count.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "One group", "The rings show the equal groups. How many in one group?", "group_frac",
         [(15, 3, 1, "given"), (8, 2, 1, "given"), (20, 5, 1, "given"), (18, 6, 1, "given"), (16, 4, 1, "given"),
          (12, 6, 1, "given")])
    part(2, "Count the groups", "Count the dots in the marked groups.", "group_frac",
         [(12, 4, 3, "marked"), (15, 5, 2, "marked"), (18, 3, 2, "marked"), (20, 4, 3, "marked"),
          (10, 5, 4, "marked"), (24, 6, 5, "marked")])
    part(3, "Make the groups", "Circle equal groups first. The bottom number says how many.", "group_frac",
         [(9, 3, 2, "ring"), (12, 4, 1, "ring"), (10, 2, 1, "ring"), (15, 5, 3, "ring"), (16, 4, 3, "ring"),
          (14, 7, 2, "ring")])
    part(4, "Divide, then multiply", "One group first, then the groups you need.", "frac2",
         [f"{n} {DIV} {d} = [{n // d}] so {k}/{d} of {n} = [{n // d * k}]" for n, d, k in
          ((24, 4, 3), (30, 5, 2), (21, 3, 2), (32, 8, 3), (36, 6, 5), (28, 4, 3), (40, 10, 7), (27, 9, 4))])
    part(5, "One group", "No help this time.", "frac3",
         [f"1/{d} of {n} = [{n // d}]" for n, d in ((20, 4), (35, 5), (18, 3), (48, 8), (30, 6), (14, 2),
                                                     (60, 10), (45, 9), (28, 7), (40, 8), (24, 3), (42, 6))])
    part(6, "More than one group", "No help this time.", "frac2",
         [f"{k}/{d} of {n} = [{n // d * k}]" for n, d, k in ((20, 5, 3), (24, 6, 5), (16, 4, 3), (40, 8, 5),
                                                              (30, 3, 2), (50, 10, 9), (36, 9, 2), (35, 7, 4),
                                                              (32, 4, 3), (18, 6, 5), (45, 5, 4), (56, 8, 3))])
    part(7, "Hours and dollars", "No help this time. 1 hour = 60 minutes, 1 dollar = 100 cents.", "frac2",
         ["1/4 of an hour = [15] minutes", "1/2 of a dollar = [50] cents", "3/4 of an hour = [45] minutes",
          "1/4 of a dollar = [25] cents", "1/3 of an hour = [20] minutes", "1/10 of a dollar = [10] cents",
          "2/3 of an hour = [40] minutes", "3/4 of a dollar = [75] cents"])
    part(8, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_GROUPF)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Draw the groups.")
    for i, story in enumerate(WORDS_GROUPF):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_GROUPF = ["4/10 [<] 7/10", "4/10 = 2/[5]", "15/3 = [5]", "Round 917 to the nearest hundred: [900]",
                 "9 groups of 2 = [18]", "1/6 [>] 1/10"]

WORDS_GROUPF = [
    ("There are 12 kids. 1/3 of them wear hats. How many kids wear hats?", f"12 {DIV} 3 = 4", "4", "kids"),
    ("Ana has 20 stickers. She gives away 1/4 of them. How many stickers does she give away?",
     f"20 {DIV} 4 = 5", "5", "stickers"),
    ("A box has 18 crayons. 2/3 of them are new. How many crayons are new?", f"18 {DIV} 3 = 6, 2 {TIMES} 6 = 12",
     "12", "crayons"),
    ("Leo has 30 marbles. 3/5 of them are blue. How many marbles are blue?", f"30 {DIV} 5 = 6, 3 {TIMES} 6 = 18",
     "18", "marbles"),
    ("Challenge: Mia read 3/4 of a 40-page book. How many pages does she have left to read?",
     f"40 {DIV} 4 = 10, 1/4 is left", "10", "pages"),
]

KINDS_GROUPF = {
    "group_frac": Kind(70, 1, lambda it: f"fraction of a group ({it[3]}): {it[2]}/{it[1]} of {it[0]}", c_group_frac, 8),
}
KINDS.update(KINDS_GROUPF)

_G_PAIRS = [(d * e, d) for d in rng(2, 10) for e in rng(2, 9)]
GROUP_UNIT = [f"1/{d} of {n} = [{n // d}]" for n, d in _G_PAIRS]
GROUP_MORE = [f"{k}/{d} of {n} = [{n // d * k}]" for n, d in _G_PAIRS if d > 2 for k in rng(2, d - 1)]

CHECKINS["44-fractions-of-a-group"] = [
    S("Count the groups", None, "group_frac", [(d * e, d, k, "marked") for d in (3, 4, 5) for e in (2, 3, 4)
                                               for k in rng(1, d - 1)], 1),
    S("Make the groups", None, "group_frac", [(d * e, d, k, "ring") for d in (2, 3, 4) for e in (2, 3, 4)
                                              for k in rng(1, d - 1)], 1),
    S("One group", None, "frac3", GROUP_UNIT, 3),
    S("More than one group", None, "frac2", GROUP_MORE, 4),
]


KINDS_36 = {
    "compare_frac": Kind(84, 1, lambda it: f"compare with strips: {it[0][0]}/{it[0][1]} and {it[1][0]}/{it[1][1]}",
                         c_compare_frac, 8),
    "equiv_frac": Kind(84, 1, lambda it: f"line them up: {it[0][0]}/{it[0][1]} in {it[1]}ths", c_equiv_frac, 8),
    "frac3": Kind(48, 3, lambda t: t, c_frac, 8),
}
KINDS.update(KINDS_36)


# ---------------------------------------------------------------------- grade 3 assessments (packets 33-52)


def stories_x(seed, kind, items):
    """Multiplication and division story problems (grade 3)."""
    r = random.Random(seed)
    items = list(items)
    r.shuffle(items)
    out = []
    for g, k in items:
        n = r.choice(NAMES)
        t = r.choice(THINGS)
        if kind == "times":
            out.append((f"{n} has {g} bags with {k} {t} in each bag. How many {t} are there in all?",
                        f"{g} {TIMES} {k} = {g * k}", g * k, t))
        else:
            out.append((f"{n} shares {g * k} {t} equally among {g} friends. How many {t} does each friend get?",
                        f"{g * k} {DIV} {g} = {k}", k, t))
    return out


GRADES.append(("grade-3", "Grade 3", "Packets 33–52", [
    S("Groups of", None, "times_groups", [(g, n) for g in rng(2, 5) for n in rng(2, 5)], 2, 33),
    S("Times 2, 5 and 10", None, "eq3", FACTS_2_5_10, 6, 33),
    S("Break it apart", None, "break_array", [(a, b) for a in (3, 4, 6, 7, 8, 9) for b in rng(3, 9)], 2, 34),
    S("Multiply", None, "eq3", HARD_FACTS, 9, 34),
    S("Think multiplication", None, "think_times", [(d * q, d) for d in rng(3, 9) for q in rng(3, 9)], 2, 35),
    S("Divide", None, "eq3", DIV_FACTS, 9, 35),
    S("Word problems", None, "word", stories_x("g3a", "times", [(g, k) for g in rng(3, 9) for k in rng(3, 9)])[:8]
      + stories_x("g3b", "share", [(g, k) for g in rng(3, 9) for k in rng(3, 9)])[:8], 4, "33–35"),
]))


# ====================================================================== 36. Rounding


def round_to(n, place):
    return (n + place // 2) // place * place


def between(bk, x, y, w, n, place, given=False, size=16, bw=44):
    """The rounding picture: [ten below] <- n -> [ten above]. The key rings the closer one.
    y = baseline of the number row. given=True prints the tens below and above."""
    c = bk.c
    lo, hi = n // place * place, n // place * place + place
    bh = size * 1.6
    lx, rx = x, x + w - bw
    for bx, v in ((lx, lo), (rx, hi)):
        bk.box(bx, y - size * 0.42, bw, bh, nf(v), size=size * 0.85, reveal=T.ink if given else None)
        if bk.key and v == round_to(n, place):
            c.setStrokeColor(T.answer)
            c.setLineWidth(1.6)
            c.ellipse(bx - 6, y - size * 0.42 - 6, bx + bw + 6, y - size * 0.42 + bh + 6, stroke=1, fill=0)
    mx = x + w / 2
    c.setFillColor(T.ink)
    c.setFont("Rnd", size * 1.15)
    c.drawCentredString(mx, y, nf(n))
    nw = sw(nf(n), "Rnd", size * 1.15) / 2 + 6
    ay = y + size * 0.35
    bk.arrow(mx - nw, ay, lx + bw + 4, ay)
    bk.arrow(mx + nw, ay, rx - 4, ay)
    return lo, hi


def c_between(bk, x, cy, w, item):
    """Round one number: the ten (or hundred) below and above, circle the closer one."""
    n, place, level = item
    between(bk, x + GUT, cy + 52, w - GUT - 14, n, place, given=level == "closer", size=15)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"{nf(n)} rounds to [{nf(round_to(n, place))}]", size=14)


def learn_rounding(bk):
    y = bk.new_page("Rounding", "Find the ten below and the ten above. Which one is closer?", name_line=False,
                    big=True, footer="WeMath  ·  Rounding")
    c = bk.c
    label(bk, M, y - 6, "Round 47 to the nearest ten")
    between(bk, M + 14, y - 54, 300, 47, 10, given=True, size=22, bw=56)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 36, "The ten below is 40.")
    c.drawString(M + 340, y - 54, "The ten above is 50.")
    c.drawString(M + 340, y - 72, "47 is closer to 50.")
    color_eq(bk, M + 340, y - 104, [("47", None), ("rounds to", None), ("50", "b")], 20)
    y -= 132

    label(bk, M, y - 6, "Round 362 to the nearest hundred")
    between(bk, M + 14, y - 54, 300, 362, 100, given=True, size=22, bw=56)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 36, "The hundred below is 300.")
    c.drawString(M + 340, y - 54, "The hundred above is 400.")
    c.drawString(M + 340, y - 72, "362 is closer to 400.")
    color_eq(bk, M + 340, y - 104, [("362", None), ("rounds to", None), ("400", "b")], 20)
    y -= 132

    label(bk, M, y - 6, "Exactly in the middle? Round up.")
    color_eq(bk, M + 14, y - 40, [("45", None), ("rounds to", None), ("50", "b")], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 280, y - 40, "45 is right in the middle of 40 and 50.")
    y -= 66

    bottom = your_turn(bk, y, h=112)
    bk.ask("round: 23 to 10 your turn")
    between(bk, M + 130, bottom + 72, 230, 23, 10, size=18, bw=48)
    bk.eq(M + 170, bottom + 22, "23 rounds to [20]", size=16)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: round to the nearest 10 or 100 (3.NBT.1). Say “What is the ten below? The ten "
                     "above? Which is closer?” Most kids can see which is closer, so there is no counting. Exactly in "
                     "the middle rounds up.")


def practice_rounding(bk):
    title = "Rounding: Practice"
    y = bk.new_page(title, "Ten below, ten above. Which one is closer?")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(1, "Between which tens?", "Write the ten below and the ten above.",
         [f"{n} is between [{n // 10 * 10}] and [{n // 10 * 10 + 10}]" for n in (36, 82, 59, 14, 73, 28, 91, 65)],
         2, 42, 8, plain, lambda t: t)
    key = KINDS_37["round_card"].key
    part(2, "Which ten is closer?", "Circle the closer ten.",
         [(43, 10, "closer"), (68, 10, "closer"), (27, 10, "closer"), (85, 10, "closer"), (52, 10, "closer"),
          (39, 10, "closer")], 2, 84, 10, c_between, key)
    part(3, "Fill in every box", "Write both tens, circle the closer one, then round.",
         [(74, 10, "boxes"), (16, 10, "boxes"), (95, 10, "boxes"), (31, 10, "boxes"), (247, 10, "boxes"),
          (563, 10, "boxes")], 2, 84, 10, c_between, key)
    part(4, "Round to the nearest hundred", "Circle the closer hundred.",
         [(418, 100, "closer"), (276, 100, "closer"), (650, 100, "closer"), (134, 100, "closer"),
          (581, 100, "closer"), (749, 100, "closer")], 2, 84, 10, c_between, key)
    part(5, "Nearest ten", "No help this time.",
         [f"{n} rounds to [{round_to(n, 10)}]" for n in (22, 48, 63, 87, 55, 11, 79, 34, 96, 41, 17, 66)], 3, 42, 8,
         plain, lambda t: t)
    part(6, "Big numbers to the nearest ten", "No help this time.",
         [f"{n} rounds to [{round_to(n, 10)}]" for n in (123, 456, 785, 312, 639, 991, 205, 574, 868, 437)], 2, 42, 8,
         plain, lambda t: t)
    part(7, "Nearest hundred", "No help this time.",
         [f"{n} rounds to [{round_to(n, 100)}]" for n in (349, 712, 450, 188, 826, 561, 274, 935, 607, 143, 381, 666)],
         2, 42, 8, plain, lambda t: t)
    part(8, "Ten or hundred?", "No help this time. Read which one.",
         [f"Round {n} to the nearest {p}: [{round_to(n, p)}]" for n, p in ((83, 10), (615, 100), (255, 10), (97, 100),
                                                                          (438, 10), (850, 100))], 2, 42, 8, plain,
         lambda t: t)
    part(9, "Remember?", "Problems from earlier packets.", REVIEW_37, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 10, "Word problems", "About how many? Round.")
    for i, story in enumerate(WORDS_37):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 10, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_37 = ["4 groups of 9 = [36]", f"63 {DIV} 9 = [7]",
             "half past 11 = [11:30]", "55¢ + 35¢ = [90¢]", f"604 {MINUS} 258 = [346]", "7 groups of 5 = [35]"]

WORDS_37 = [
    ("A book has 48 pages. About how many pages is that, to the nearest ten?", "48 rounds to 50", "50", "pages"),
    ("A school has 371 kids. About how many kids is that, to the nearest hundred?", "371 rounds to 400", "400",
     "kids"),
    ("A bike costs $129. About how much is that, to the nearest ten dollars?", "$129 rounds to $130", "$130", ""),
    ("A farm has 85 cows. About how many cows is that, to the nearest ten?", "85 rounds to 90", "90", "cows"),
    ("Challenge: Mia had 38 stickers and got 24 more. About how many now, to the nearest ten?",
     "38 + 24 = 62, 62 rounds to 60", "60", "stickers"),
]

KINDS_37 = {
    "round_card": Kind(84, 2, lambda it: f"round: {it[0]} to {it[1]} {it[2]}", c_between),
}
KINDS.update(KINDS_37)

ROUND_10 = [f"{n} rounds to [{round_to(n, 10)}]" for n in list(rng(11, 98)) + list(rng(102, 988, 7)) if n % 10]
ROUND_100 = [f"{n} rounds to [{round_to(n, 100)}]" for n in rng(105, 985, 11) if n % 100]
ROUND_MIXED = [f"Round {n} to the nearest {p}: [{round_to(n, p)}]" for n in rng(112, 988, 13) for p in (10, 100)
               if n % 10]

CHECKINS["36-rounding"] = [
    S("Which ten is closer?", None, "round_card", [(n, 10, "closer") for n in rng(12, 98) if n % 10 and n not in (23, 47)], 2),
    S("Nearest ten", None, "eq2", ROUND_10, 2),
    S("Nearest hundred", None, "eq2", ROUND_100, 2),
    S("Ten or hundred?", None, "eq2", ROUND_MIXED, 2),
]
_g3 = next(g for g in GRADES if g[0] == "grade-3")[3]
_g3[-1:-1] = [
    S("Rounding", None, "eq2", ROUND_MIXED, 4, 36),
]


# ====================================================================== 37. Multiplying by Tens


def tens_groups(bk, x, y, groups, tens, h=60, w=STICK_W, gap=5, ggap=18):
    """`groups` rings of `tens` ten-sticks, the rings alternating blue and orange. y = bottom of the sticks.
    Returns the width."""
    c = bk.c
    gw = tens * w + (tens - 1) * gap
    for g in range(groups):
        gx = x + g * (gw + ggap)
        c.setStrokeColor(T.line)
        c.setLineWidth(0.9)
        c.roundRect(gx - 4, y - 4, gw + 8, h + 8, 6, stroke=1, fill=0)
        for i in range(tens):
            ten_stick(bk, gx + i * (w + gap), y, h, w, kind="a" if g % 2 == 0 else "b")
    return groups * gw + (groups - 1) * ggap


def c_tens_groups(bk, x, cy, w, item):
    g, t = item
    tens_groups(bk, x + GUT, cy + 74, g, t, h=40, w=9, gap=3.5, ggap=12)
    bk.fit_eq(x + GUT, cy + 38, w - GUT - 10, f"[{g}] groups of [{t}] tens = [{g * t}] tens", size=14)
    bk.fit_eq(x + GUT, cy + 12, w - GUT - 10, f"[{g}] {TIMES} [{t * 10}] = [{g * t * 10}]", size=14)


def tens_fact(g, t):
    """'6 × 4 = [24] so 6 × 40 = [240]'"""
    return f"{g} {TIMES} {t} = [{g * t}] so {g} {TIMES} {t * 10} = [{g * t * 10}]"


def learn_times_tens(bk):
    y = bk.new_page("Multiplying by Tens", "Groups of tens: use the fact you know, then count tens.",
                    name_line=False, big=True, footer="WeMath  ·  Multiplying by Tens")
    c = bk.c
    label(bk, M, y - 6, "3 groups of 4 tens")
    tens_groups(bk, M + 18, y - 92, 3, 4, h=60)
    color_eq(bk, M + 300, y - 50, [("3", "a"), (TIMES, "op"), ("40", "b"), ("=", "op"), ("120", None)], 26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 300, y - 76, "3 groups of 4 tens = 12 tens")
    c.drawString(M + 300, y - 94, "12 tens is 120.")
    y -= 124

    label(bk, M, y - 6, "Use a fact you know")
    color_eq(bk, M + 14, y - 42, [("6", "a"), (TIMES, "op"), ("7", "b"), ("=", "op"), ("42", None)], 24)
    color_eq(bk, M + 14, y - 78, [("6", "a"), (TIMES, "op"), ("70", "b"), ("=", "op"), ("42 tens", None),
                                  ("=", "op"), ("420", None)], 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 330, y - 42, "Same fact, but now")
    c.drawString(M + 330, y - 60, "it counts tens.")
    y -= 108

    label(bk, M, y - 6, "Careful with 5s")
    color_eq(bk, M + 14, y - 42, [("5", "a"), (TIMES, "op"), ("4", "b"), ("=", "op"), ("20", None)], 24)
    color_eq(bk, M + 14, y - 78, [("5", "a"), (TIMES, "op"), ("40", "b"), ("=", "op"), ("20 tens", None),
                                  ("=", "op"), ("200", None)], 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 330, y - 42, "The fact already ends in 0.")
    c.drawString(M + 330, y - 60, "20 tens is 200: two zeros.")
    y -= 112

    bottom = your_turn(bk, y, h=118)
    bk.ask("tens groups 2 3 your turn")
    bk.ask(f"2 {TIMES} 30 = [60]")
    tens_groups(bk, M + 110, bottom + 30, 2, 3, h=52, w=12, gap=5, ggap=16)
    bk.fit_eq(M + 270, bottom + 72, CW - 270 - 16, f"[2] groups of [3] tens = [6] tens", size=15)
    bk.eq(M + 270, bottom + 34, f"2 {TIMES} 30 = [60]", size=18)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: multiply a one-digit number by a multiple of 10 (3.NBT.3). Say “6 × 70 is 6 groups "
                     "of 7 tens. 6 × 7 = 42, so it is 42 tens, 420.” Avoid “just add a zero”: 5 × 40 = 20 tens "
                     "= 200 shows why.")


def practice_times_tens(bk):
    title = "Multiplying by Tens: Practice"
    y = bk.new_page(title, "Use the fact you know. Count the tens.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(1, "Groups of tens", "Count the groups and the tens in each group.",
         [(2, 4), (3, 3), (2, 6), (5, 2), (4, 3), (2, 5)], 2, 134, 10, c_tens_groups, KINDS_38["tens_groups"].key)
    part(2, "How many tens?", "Multiply, then write how many tens.",
         [f"{g} {TIMES} {t} tens = [{g * t}] tens" for g, t in
          ((3, 5), (4, 4), (6, 2), (7, 3), (2, 8), (5, 3), (8, 2), (3, 7), (4, 6))], 3, 42, 8, plain, lambda t: t)
    part(3, "The fact, then the tens", "The first answer helps with the second.",
         [tens_fact(g, t) for g, t in ((6, 4), (3, 8), (7, 5), (4, 9), (9, 3), (5, 6), (8, 7), (6, 8))],
         2, 42, 8, plain, lambda t: t)
    for n, (name, sub, pairs) in enumerate(TENS_PARTS_38):
        part(4 + n, name, sub, [f"{a} {TIMES} {b} = [{a * b}]" for a, b in pairs], 3, 42, 8, plain, lambda t: t)
    part(8, "Remember?", "Problems from earlier packets.", REVIEW_38, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "How many groups? How many in each?")
    for i, story in enumerate(WORDS_38):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


TENS_PARTS_38 = [
    ("Times 2 and times 5", "No help this time.",
     [(2, 70), (5, 80), (9, 20), (5, 50), (2, 90), (7, 20), (5, 90), (4, 50), (6, 50)]),
    ("Harder facts", "No help this time. Find the fact first.",
     [(6, 70), (8, 40), (7, 90), (9, 60), (3, 60), (8, 80), (4, 70), (9, 90), (7, 60), (6, 90), (3, 90), (8, 30)]),
    ("Tens first", "No help this time. 30 × 4 is the same as 4 × 30.",
     [(30, 4), (60, 3), (70, 8), (90, 4), (80, 5), (20, 3), (50, 7), (40, 8), (60, 6)]),
    ("Mixed", "No help this time.",
     [(7, 70), (4, 80), (9, 40), (2, 20), (8, 90), (3, 40), (6, 30), (9, 70), (5, 70), (8, 50), (7, 40), (3, 20)]),
]

REVIEW_38 = ["7 groups of 6 = [42]", "Round 64 to the nearest ten: [60]", "half of 18 = [9]",
             f"703 {MINUS} 245 = [458]", "348 + 275 = [623]", "4 groups of 8 = [32]"]

WORDS_38 = [
    ("A box holds 50 crayons. How many crayons are in 3 boxes?", f"3 {TIMES} 50 = 150", "150", "crayons"),
    ("Each train car holds 70 people. How many people fit in 3 cars?", f"3 {TIMES} 70 = 210", "210", "people"),
    ("A game gives 20 points for each star. Ben gets 6 stars. How many points is that?", f"6 {TIMES} 20 = 120",
     "120", "points"),
    ("A farmer plants 4 rows with 60 seeds in each row. How many seeds is that?", f"4 {TIMES} 60 = 240", "240",
     "seeds"),
    ("Challenge: A store has 9 boxes of 50 pencils. It sells 75 pencils. How many pencils are left?",
     f"9 {TIMES} 50 = 450, 450 {MINUS} 75 = 375", "375", "pencils"),
]

KINDS_38 = {
    "tens_groups": Kind(134, 2, lambda it: f"tens groups {it[0]} {it[1]}", c_tens_groups),
}
KINDS.update(KINDS_38)

TENS_FACTS = [f"{g} {TIMES} {t * 10} = [{g * t * 10}]" for g in rng(2, 9) for t in rng(2, 9)]

CHECKINS["37-multiplying-by-tens"] = [
    S("Groups of tens", None, "tens_groups", [(g, t) for g in rng(2, 4) for t in rng(2, 6) if g * t <= 12 and (g, t) != (2, 3)], 2),
    S("The fact, then the tens", None, "eq2", [tens_fact(g, t) for g in rng(2, 9) for t in rng(2, 9)], 2),
    S("Multiply", None, "eq3", TENS_FACTS, 6),
]
_g3[-1:-1] = [
    S("Multiply by tens", None, "eq3", TENS_FACTS, 3, 37),
]


# ====================================================================== 38. Area


def side_label(bk, x, y, text, anchor="center", size=10):
    c = bk.c
    c.setFillColor(T.text2)
    c.setFont("AvD", size)
    if anchor == "center":
        c.drawCentredString(x, y, text)
    else:
        c.drawString(x, y, text)


def area_rect(bk, x, y, rows, cols, cell, grid=True, unit=None, split=None, numbers=False, fill=None):
    """A rows × cols rectangle of unit squares; y = bottom. grid=False draws only the outline.
    unit: label the bottom and right sides ("6 cm"). split: a dashed line after that many columns, the two
    parts shaded blue and orange (colour only), each part labelled on the bottom. numbers: count the squares.
    fill: "a" or "b" shades the whole rectangle. Returns (width, height)."""
    c = bk.c
    w, h = cols * cell, rows * cell
    fills = []
    if split:
        fills = [(x, split * cell, T.band), (x + split * cell, (cols - split) * cell, T.strip)]
    elif fill:
        fills = [(x, w, T.band if fill == "a" else T.strip)]
    for fx, fw, col in fills:
        if T.color and col is not None:
            c.setFillColor(col)
            c.rect(fx, y, fw, h, stroke=0, fill=1)
    if grid:
        c.setStrokeColor(T.text2)
        c.setLineWidth(0.7)
        for i in range(1, cols):
            c.line(x + i * cell, y, x + i * cell, y + h)
        for j in range(1, rows):
            c.line(x, y + j * cell, x + w, y + j * cell)
    if split:
        c.setStrokeColor(T.ink)
        c.setLineWidth(1.4)
        c.setDash(3, 2.5)
        c.line(x + split * cell, y - 4, x + split * cell, y + h + 4)
        c.setDash()
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.6)
    c.rect(x, y, w, h, stroke=1, fill=0)
    if numbers:
        c.setFillColor(T.text2)
        c.setFont("AvD", cell * 0.38)
        for j in range(rows):
            for i in range(cols):
                c.drawCentredString(x + (i + 0.5) * cell, y + h - (j + 0.5) * cell - cell * 0.14,
                                    str(j * cols + i + 1))
    if unit:
        if split:
            side_label(bk, x + split * cell / 2, y - 12, f"{split} {unit}")
            side_label(bk, x + split * cell + (cols - split) * cell / 2, y - 12, f"{cols - split} {unit}")
        else:
            side_label(bk, x + w / 2, y - 12, f"{cols} {unit}")
        side_label(bk, x + w + 5, y + h / 2 - 3.5, f"{rows} {unit}", anchor="left")
    return w, h


def area_L(bk, x, y, r1, c1, r2, c2, cell):
    """Two rectangles side by side, bottoms lined up (an L shape): the left one blue, the right one orange,
    a dashed line between. Returns the width."""
    area_rect(bk, x, y, r1, c1, cell, fill="a")
    area_rect(bk, x + c1 * cell, y, r2, c2, cell, fill="b")
    c = bk.c
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.4)
    c.setDash(3, 2.5)
    c.line(x + c1 * cell, y, x + c1 * cell, y + r2 * cell)
    c.setDash()
    return (c1 + c2) * cell


def c_area_count(bk, x, cy, w, item):
    rows, cols = item
    cell = 12
    bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"Area = [{rows * cols}] square units", size=15)
    area_rect(bk, x + GUT, cy + 12 + (64 - rows * cell) / 2, rows, cols, cell)


def c_area_rows(bk, x, cy, w, item):
    rows, cols = item
    cell = 11
    bk.fit_eq(x + GUT, cy + 104, w - GUT - 10, f"[{rows}] {TIMES} [{cols}] = [{rows * cols}] square units", size=15)
    area_rect(bk, x + GUT, cy + 24 + (60 - rows * cell) / 2, rows, cols, cell, unit="units")


def c_area_sides(bk, x, cy, w, item):
    rows, cols, unit = item
    cell = min(11, 120 / cols, 60 / rows)
    bk.fit_eq(x + GUT, cy + 104, w - GUT - 10, f"[{rows}] {TIMES} [{cols}] = [{rows * cols}] square {unit}",
              size=15)
    area_rect(bk, x + GUT, cy + 24 + (60 - rows * cell) / 2, rows, cols, cell, grid=False, unit=unit)


def c_area_split(bk, x, cy, w, item):
    rows, a, b = item
    cell = 10
    area_rect(bk, x + GUT, cy + 12 + (80 - rows * cell) / 2, rows, a + b, cell, split=a)
    tx = x + GUT + 130
    lines = [f"{rows} {TIMES} {a} = [{rows * a}]", f"{rows} {TIMES} {b} = [{rows * b}]",
             f"[{rows * a}] + [{rows * b}] = [{rows * (a + b)}]"]
    bk.fit_eq(x + GUT, cy + 112, w - GUT - 10, f"{rows} {TIMES} {a + b} = [{rows * (a + b)}]", size=16)
    for i, line in enumerate(lines):
        bk.fit_eq(tx, cy + 76 - i * 30, w - (tx - x) - 8, line, size=15)


def c_area_L(bk, x, cy, w, item):
    r1, c1, r2, c2 = item
    cell = 12
    area_L(bk, x + GUT, cy + 18 + (90 - r1 * cell) / 2, r1, c1, r2, c2, cell)
    tx = x + GUT + 130
    lines = [f"[{r1}] {TIMES} [{c1}] = [{r1 * c1}]", f"[{r2}] {TIMES} [{c2}] = [{r2 * c2}]",
             f"[{r1 * c1}] + [{r2 * c2}] = [{r1 * c1 + r2 * c2}]"]
    for i, line in enumerate(lines):
        bk.fit_eq(tx, cy + 92 - i * 34, w - (tx - x) - 8, line, size=16)


def learn_area(bk):
    y = bk.new_page("Area", "Area is how many squares cover a shape.", name_line=False, big=True,
                    footer="WeMath  ·  Area")
    c = bk.c
    label(bk, M, y - 6, "Cover it with squares, then count")
    area_rect(bk, M + 20, y - 92, 3, 5, 24, numbers=True)
    color_eq(bk, M + 220, y - 50, [("Area", None), ("=", "op"), ("15", "b"), ("square units", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 220, y - 76, "Each square is 1 square unit.")
    y -= 118

    label(bk, M, y - 6, "Rows × columns: no need to count one by one")
    area_rect(bk, M + 20, y - 102, 4, 6, 18, unit="cm")
    color_eq(bk, M + 220, y - 50, [("4", "a"), (TIMES, "op"), ("6", "b"), ("=", "op"), ("24", None)], 26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 220, y - 76, "4 rows of 6 squares: 24 square cm.")
    c.drawString(M + 220, y - 94, "Multiply the side lengths.")
    y -= 132

    label(bk, M, y - 6, "Break it apart: 4 × 8 is 4 × 5 and 4 × 3")
    area_rect(bk, M + 20, y - 94, 4, 8, 16, unit="cm", split=5)
    color_eq(bk, M + 220, y - 38, [("4", None), (TIMES, "op"), ("5", "a"), ("=", "op"), ("20", "a")], 20)
    color_eq(bk, M + 220, y - 64, [("4", None), (TIMES, "op"), ("3", "b"), ("=", "op"), ("12", "b")], 20)
    color_eq(bk, M + 220, y - 90, [("20", "a"), ("+", "op"), ("12", "b"), ("=", "op"), ("32", None),
                                   ("square cm", None)], 20)
    y -= 124

    bottom = your_turn(bk, y, h=104)
    bk.ask("area rows 3 7 your turn")
    area_rect(bk, M + 130, bottom + 26, 3, 7, 16)
    bk.fit_eq(M + 280, bottom + 46, CW - 280 - 16, f"[3] {TIMES} [7] = [21] square units", size=16)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: area as unit squares that cover a shape, then rows × columns (3.MD.5–7). Say "
                     "“How many rows? How many in each row?” Area is inside; the edge is perimeter (next "
                     "packet). Link breaking apart to packet 34.")


def practice_area(bk):
    title = "Area: Practice"
    y = bk.new_page(title, "Count the squares, or multiply rows × columns.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(1, "Count the squares", "Each square is 1 square unit.",
         [(3, 4), (2, 7), (4, 5), (3, 7), (5, 3), (2, 8)], 2, 116, 10, c_area_count,
         lambda it: f"area count {it[0]} {it[1]}")
    part(2, "Rows times columns", "Multiply instead of counting.",
         [(3, 6), (5, 4), (4, 7), (6, 3), (2, 9), (5, 5)], 2, 126, 10, c_area_rows, KINDS_39["area_rows"].key)
    part(3, "Use the side lengths", "No squares drawn this time. Multiply the sides.",
         [(5, 8, "cm"), (7, 4, "in"), (6, 9, "m"), (3, 8, "ft"), (9, 7, "cm"), (8, 6, "in")], 2, 126, 10,
         c_area_sides, lambda it: f"area sides {it[0]} {it[1]} {it[2]}")
    part(4, "Break it apart", "Find the area of each part. Add them.",
         [(7, 5, 2), (6, 5, 3), (3, 5, 4), (8, 5, 1)], 1, 136, 10, c_area_split, KINDS_39["area_split"].key)
    part(5, "Two rectangles", "Find each area. Add them.",
         [(4, 3, 2, 4), (5, 2, 3, 4), (3, 4, 1, 3), (4, 5, 2, 2)], 1, 120, 10, c_area_L,
         lambda it: "area L " + " ".join(map(str, it)))
    part(6, "Rectangles", "No help this time. Multiply the sides.",
         [area_eq(a, b, "cm") for a, b in ((6, 7), (8, 3), (9, 4), (5, 6), (7, 8), (3, 9), (5, 9), (2, 8), (4, 8),
                                            (9, 8))], 2, 42, 8, plain, lambda t: t)
    part(7, "Squares", "No help this time. All four sides are the same.",
         [square_area_eq(s, u) for s, u in ((6, "m"), (3, "in"), (8, "cm"), (4, "ft"), (9, "m"), (7, "in"))],
         2, 42, 8, plain, lambda t: t)
    part(8, "Find the missing side", "No help this time. Side × side = area. What is the other side?",
         [missing_side_eq(A, a) for A, a in ((24, 4), (35, 5), (27, 3), (48, 6), (28, 7), (45, 9), (16, 2), (42, 6))],
         2, 42, 8, plain, lambda t: t)
    part(9, "Remember?", "Problems from earlier packets.", REVIEW_39, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 10, "Word problems", "Draw the rectangle if it helps.")
    for i, story in enumerate(WORDS_39):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 10, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


def area_eq(a, b, unit):
    return f"{a} {unit} by {b} {unit}: area = [{a * b}] sq {unit}"


def square_area_eq(s, unit):
    return f"{s} {unit} by {s} {unit} square: area = [{s * s}] sq {unit}"


def missing_side_eq(A, a, unit="cm"):
    return f"{a} {unit} {TIMES} [{A // a}] {unit} = {A} sq {unit}"


REVIEW_39 = ["8 × 60 = [480]", "Round 347 to the nearest hundred: [300]", "9 groups of 4 = [36]",
             "6 sixths = [1] whole", f"618 {MINUS} 349 = [269]", "2 fourths = [1] half"]

WORDS_39 = [
    ("A rug is 7 feet long and 3 feet wide. What is its area?", f"7 {TIMES} 3 = 21", "21", "square feet"),
    ("A patio has 8 rows of square tiles with 4 tiles in each row. How many tiles cover it?", f"8 {TIMES} 4 = 32",
     "32", "tiles"),
    ("A poster is 9 inches long and 6 inches wide. What is its area?", f"9 {TIMES} 6 = 54", "54", "square inches"),
    ("A room is 10 feet long and 9 feet wide. What is its area?", f"10 {TIMES} 9 = 90", "90", "square feet"),
    ("Challenge: A room is 8 feet by 6 feet. A rug covers 20 square feet. How much floor is not covered?",
     f"8 {TIMES} 6 = 48, 48 {MINUS} 20 = 28", "28", "square feet"),
]

KINDS_39 = {
    "area_rows": Kind(126, 2, lambda it: f"area rows {it[0]} {it[1]}", c_area_rows),
    "area_split": Kind(136, 1, lambda it: f"area split {it[0]} {it[1]} {it[2]}", c_area_split),
}
KINDS.update(KINDS_39)

AREA_EQS = [area_eq(a, b, u) for a in rng(3, 9) for b in rng(3, 9) if a != b for u in ("cm", "in", "m", "ft")]
MISSING_SIDES = [missing_side_eq(a * b, a, u) for a in rng(3, 9) for b in rng(3, 9) for u in ("cm", "in")]

CHECKINS["38-area"] = [
    S("Rows times columns", None, "area_rows", [(r, k) for r in rng(2, 6) for k in rng(3, 8) if (r, k) != (3, 7)], 2),
    S("Break it apart", None, "area_split", [(r, 5, b) for r in rng(3, 8) for b in rng(1, 4)], 1),
    S("Area", None, "eq2", AREA_EQS, 4),
    S("Find the missing side", None, "eq2", MISSING_SIDES, 2),
]
_g3[-1:-1] = [
    S("Area", None, "eq2", AREA_EQS, 2, 38),
    S("Unit fractions", None, "unit_name", UNIT_NAME, 2, 39),
    S("Bigger piece", "Circle the bigger piece.", "bigger_unit_plain", UNIT_BIGGER, 3, 39),
    S("Name the fraction", None, "frac_name", FRAC_PICS, 2, 40),
    S("Pieces and fractions", None, "frac2", COUNTF_FACTS, 2, 40),
    S("Less than, equal to, or more than 1?", None, "vs_one", VS_ONE, 2, 41),
    S("Fractions and wholes", None, "frac3", WHOLE_FACTS, 3, 41),
    S("Equal fractions", None, "frac3", EQUAL_TOP + EQUAL_DOWN + EQUAL_BOTTOM, 3, 42),
    S("Compare fractions", "Write <, > or =.", "frac3", SAME_BOTTOM + SAME_TOP, 3, 43, balance=is_less),
    S("Fractions of a group", None, "frac3", GROUP_UNIT, 3, 44),
    S("More than one group", None, "frac2", GROUP_MORE, 2, 44),
]


# ====================================================================== 45. Perimeter


def edge_numbers(bk, x, y, rows, cols, cell, size=9):
    """Number the unit lengths around a rectangle (1, 2, 3 … clockwise from the top-left), just outside it."""
    c = bk.c
    c.setFillColor(T.accent)
    c.setFont("AvB", size)
    k = 0
    top, right = y + rows * cell, x + cols * cell
    for i in range(cols):
        k += 1
        c.drawCentredString(x + (i + 0.5) * cell, top + 4, str(k))
    for j in range(rows):
        k += 1
        c.drawString(right + 4, top - (j + 0.5) * cell - size * 0.36, str(k))
    for i in range(cols):
        k += 1
        c.drawCentredString(right - (i + 0.5) * cell, y - size - 3, str(k))
    for j in range(rows):
        k += 1
        c.drawRightString(x - 4, y + (j + 0.5) * cell - size * 0.36, str(k))


def rect_sides(bk, x, y, w, h, top, right, bottom, left, size=10):
    """A rectangle (no grid) with a label on every side; y = bottom."""
    c = bk.c
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.6)
    c.rect(x, y, w, h, stroke=1, fill=0)
    side_label(bk, x + w / 2, y + h + 5, top, size=size)
    side_label(bk, x + w / 2, y - 12, bottom, size=size)
    side_label(bk, x + w + 5, y + h / 2 - 3.5, right, anchor="left", size=size)
    c.setFillColor(T.text2)
    c.setFont("AvD", size)
    c.drawRightString(x - 5, y + h / 2 - 3.5, left)


def polygon_sides(bk, cx, cy, R, sides, unit, size=10):
    """A shape with len(sides) sides (drawn regular, flat bottom), each side labelled outside."""
    c = bk.c
    n = len(sides)
    start = -90 - 180 / n
    pts = [(cx + R * math.cos(math.radians(start + 360 * i / n)), cy + R * math.sin(math.radians(start + 360 * i / n)))
           for i in range(n)]
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.6)
    c.drawPath(_poly(c, pts), stroke=1, fill=0)
    for i, s in enumerate(sides):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        d = math.hypot(mx - cx, my - cy) or 1
        nx, ny = (mx - cx) / d, (my - cy) / d
        text = f"{s} {unit}"
        tw = sw(text, "AvD", size)
        lx, ly = mx + nx * (6 + tw / 2 * abs(nx)), my + ny * (6 + size * 0.5 * abs(ny))
        c.setFillColor(T.text2)
        c.setFont("AvD", size)
        c.drawCentredString(lx, ly - size * 0.36, text)


def perimeter(a, b):
    return 2 * (a + b)


def c_perim_count(bk, x, cy, w, item):
    rows, cols = item
    cell = 12
    bk.fit_eq(x + GUT, cy + 94, w - GUT - 10, f"Perimeter = [{perimeter(rows, cols)}] units", size=15)
    area_rect(bk, x + GUT, cy + 12 + (64 - rows * cell) / 2, rows, cols, cell)


def c_perim_add(bk, x, cy, w, item):
    a, b, unit = item
    bk.fit_eq(x + GUT, cy + 104, w - GUT - 10, f"[{a}] + [{b}] + [{a}] + [{b}] = [{perimeter(a, b)}] {unit}", size=15)
    rw, rh = min(110, 9 * a), min(46, 7 * b)
    rect_sides(bk, x + GUT + 44, cy + 24 + (50 - rh) / 2, rw, rh, f"{a} {unit}", f"{b} {unit}", f"{a} {unit}",
               f"{b} {unit}")


def c_perim_poly(bk, x, cy, w, item):
    sides, unit = item
    bk.fit_eq(x + GUT, cy + 116, w - GUT - 10, " + ".join(map(str, sides)) + f" = [{sum(sides)}] {unit}", size=15)
    polygon_sides(bk, x + GUT + 90, cy + 50, 30, sides, unit)


def c_perim_missing(bk, x, cy, w, item):
    a, b, unit = item
    P = perimeter(a, b)
    rw, rh = 9 * a, 9 * b
    ry = cy + 18 + (70 - rh) / 2
    rect_sides(bk, x + GUT + 40, ry, rw, rh, "", "", f"{a} {unit}", "")
    c = bk.c
    c.setFillColor(T.accent)
    c.setFont("AvB", 15)
    c.drawString(x + GUT + 40 + rw + 6, ry + rh / 2 - 5, "?")
    c.setFillColor(T.ink)
    c.setFont("Rnd", 13)
    c.drawString(x + GUT, cy + 98, f"Perimeter = {P} {unit}. Find the missing side.")
    tx = x + GUT + 200
    lines = [f"{a} + {a} = [{2 * a}]", f"{P} {MINUS} [{2 * a}] = [{2 * b}]", f"half of [{2 * b}] = [{b}] {unit}"]
    for i, line in enumerate(lines):
        bk.fit_eq(tx, cy + 70 - i * 28, w - (tx - x) - 8, line, size=15)


def c_area_perim(bk, x, cy, w, item):
    rows, cols = item
    cell = 11
    bk.fit_eq(x + GUT, cy + 116, w - GUT - 10, f"Area = [{rows * cols}] square units", size=14)
    bk.fit_eq(x + GUT, cy + 86, w - GUT - 10, f"Perimeter = [{perimeter(rows, cols)}] units", size=14)
    area_rect(bk, x + GUT, cy + 12 + (56 - rows * cell) / 2, rows, cols, cell)


def learn_perimeter(bk):
    y = bk.new_page("Perimeter", "Perimeter is the distance all the way around.", name_line=False, big=True,
                    footer="WeMath  ·  Perimeter")
    c = bk.c
    label(bk, M, y - 6, "Walk around the edge and count")
    area_rect(bk, M + 34, y - 100, 3, 5, 22)
    edge_numbers(bk, M + 34, y - 100, 3, 5, 22, size=10)
    color_eq(bk, M + 240, y - 54, [("Perimeter", None), ("=", "op"), ("16", "b"), ("units", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 240, y - 80, "Count each edge of a square once.")
    y -= 132

    label(bk, M, y - 6, "Add the sides")
    rect_sides(bk, M + 50, y - 96, 120, 60, "6 cm", "4 cm", "6 cm", "4 cm", size=11)
    color_eq(bk, M + 240, y - 54, [("6", "a"), ("+", "op"), ("4", "b"), ("+", "op"), ("6", "a"), ("+", "op"),
                                   ("4", "b"), ("=", "op"), ("20", None), ("cm", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 240, y - 80, "Opposite sides are the same length.")
    y -= 128

    label(bk, M, y - 6, "Area is inside. Perimeter is around.")
    area_rect(bk, M + 50, y - 96, 3, 4, 20, fill="a")
    edge_numbers(bk, M + 50, y - 96, 3, 4, 20, size=9)
    color_eq(bk, M + 240, y - 44, [("Area", None), ("=", "op"), ("12", "a"), ("square units", None)], 20)
    color_eq(bk, M + 240, y - 76, [("Perimeter", None), ("=", "op"), ("14", "b"), ("units", None)], 20)
    y -= 122

    bottom = your_turn(bk, y, h=104)
    bk.ask("perimeter add 7 2 cm your turn")
    rect_sides(bk, M + 140, bottom + 30, 84, 26, "7 cm", "2 cm", "7 cm", "2 cm")
    bk.fit_eq(M + 300, bottom + 40, CW - 300 - 16, "[7] + [2] + [7] + [2] = [18] cm", size=16)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: perimeter is the length around a shape (3.MD.8). Trace the edge with a finger "
                     "while counting. Then add the side lengths. Keep asking “inside or around?” so area and "
                     "perimeter don't get mixed up.")


def practice_perimeter(bk):
    title = "Perimeter: Practice"
    y = bk.new_page(title, "Go all the way around. Add every side.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(1, "Count around", "Count every edge on the outside.",
         [(2, 5), (3, 3), (4, 6), (1, 7), (3, 6), (2, 9)], 2, 116, 10, c_perim_count,
         lambda it: f"perimeter count {it[0]} {it[1]}")
    part(2, "Add the sides", "Write each side, then add.",
         [(8, 3, "cm"), (6, 5, "in"), (9, 4, "m"), (7, 7, "ft"), (12, 5, "cm"), (10, 6, "in")], 2, 126, 10,
         c_perim_add, KINDS_40["perim_add"].key)
    part(3, "More sides", "Add all the sides.",
         [((5, 7, 6), "cm"), ((4, 4, 4, 4, 4), "in"), ((8, 6, 9), "m"), ((5, 9, 4, 7), "cm"), ((3, 3, 3, 3, 3, 3), "ft"),
          ((6, 5, 7, 4, 8), "cm")], 2, 140, 10, c_perim_poly,
         lambda it: "perimeter shape " + "-".join(map(str, it[0])) + f" {it[1]}")
    part(4, "Find the missing side", "The perimeter is given. Take away the sides you know.",
         [(8, 5, "cm"), (6, 3, "in"), (9, 7, "m"), (10, 4, "cm")], 1, 120, 10, c_perim_missing,
         lambda it: f"perimeter missing {it[0]} {it[1]} {it[2]}")
    part(5, "Area and perimeter", "Inside, then around.",
         [(2, 6), (4, 5), (3, 7), (5, 5)], 2, 140, 10, c_area_perim, KINDS_40["area_perim"].key)
    part(6, "Rectangles", "No help this time. Add all four sides.",
         [perim_eq(a, b, "cm") for a, b in ((5, 3), (9, 2), (7, 4), (12, 6), (11, 3), (6, 4), (15, 5), (10, 7), (9, 6),
                                            (14, 2))], 2, 42, 8, plain, lambda t: t)
    part(7, "Squares", "No help this time. All four sides are the same.",
         [square_perim_eq(s, u) for s, u in ((5, "m"), (8, "in"), (3, "cm"), (10, "ft"), (6, "m"), (9, "cm"))],
         2, 42, 8, plain, lambda t: t)
    part(8, "Add the sides", "No help this time.",
         ["15 + 8 + 15 + 8 = [46]", "7 + 9 + 11 = [27]", "13 + 6 + 13 + 6 = [38]", "12 + 12 + 12 = [36]",
          "9 + 14 + 9 + 14 = [46]", "6 + 8 + 5 + 9 = [28]"], 2, 42, 8, plain, lambda t: t)
    part(9, "Find the missing side", "No help this time. Rectangles only.",
         [perim_missing_eq(a, b, u) for a, b, u in ((7, 3, "cm"), (5, 4, "in"), (9, 2, "m"), (8, 6, "ft"),
                                                    (11, 4, "cm"), (6, 5, "in"))], 2, 42, 8, plain, lambda t: t)
    part(10, "Remember?", "Problems from earlier packets.", REVIEW_40, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 11, "Word problems", "Draw the shape and label the sides.")
    for i, story in enumerate(WORDS_40):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 11, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


def perim_eq(a, b, unit):
    return f"{a} {unit} by {b} {unit}: perimeter = [{perimeter(a, b)}] {unit}"


def square_perim_eq(s, unit):
    return f"{s} {unit} by {s} {unit} square: perimeter = [{4 * s}] {unit}"


def perim_missing_eq(a, b, unit):
    return f"{a} {unit} by [{b}] {unit}: perimeter = {perimeter(a, b)} {unit}"


REVIEW_40 = ["9 × 30 = [270]", "Round 452 to the nearest ten: [450]", "5 cm by 7 cm: area = [35] sq cm",
             "8 eighths = [1] whole", f"500 {MINUS} 238 = [262]", "8 groups of 7 = [56]"]

WORDS_40 = [
    ("A garden is 9 feet long and 5 feet wide. How much fence goes all the way around it?",
     "9 + 5 + 9 + 5 = 28", "28", "feet"),
    ("A square picture frame has sides of 9 inches. What is its perimeter?", "9 + 9 + 9 + 9 = 36", "36", "inches"),
    ("A triangle has sides of 6 cm, 8 cm and 10 cm. What is its perimeter?", "6 + 8 + 10 = 24", "24", "cm"),
    ("A rug is 6 feet long. Its perimeter is 20 feet. How wide is it?", f"20 {MINUS} 12 = 8, half of 8 = 4", "4",
     "feet"),
    ("Challenge: A playground is 10 m long and 8 m wide. Kim walks around it 2 times. How far does Kim walk?",
     "10 + 8 + 10 + 8 = 36, 36 + 36 = 72", "72", "m"),
]

KINDS_40 = {
    "perim_add": Kind(126, 2, lambda it: f"perimeter add {it[0]} {it[1]} {it[2]}", c_perim_add),
    "area_perim": Kind(140, 2, lambda it: f"area perimeter {it[0]} {it[1]}", c_area_perim),
}
KINDS.update(KINDS_40)

PERIM_EQS = [perim_eq(a, b, u) for a in rng(3, 15) for b in rng(2, 9) if a > b for u in ("cm", "in", "m", "ft")]
PERIM_MISSING = [perim_missing_eq(a, b, u) for a in rng(4, 12) for b in rng(2, 8) if a > b for u in ("cm", "m")]

CHECKINS["45-perimeter"] = [
    S("Add the sides", None, "perim_add", [(a, b, u) for a in rng(5, 12) for b in rng(2, 6) if a > b
                                            for u in ("cm", "in", "m", "ft")], 2),
    S("Area and perimeter", None, "area_perim", [(r, k) for r in rng(2, 5) for k in rng(3, 8) if r < k], 2),
    S("Perimeter", None, "eq2", PERIM_EQS, 4),
    S("Find the missing side", None, "eq2", PERIM_MISSING, 2),
]
_g3[-1:-1] = [
    S("Perimeter", None, "eq2", PERIM_EQS, 2, 45),
]


# ====================================================================== 46. Elapsed Time


def tadd(t, mins):
    """(h, m) + minutes on a 12-hour clock."""
    total = (t[0] % 12) * 60 + t[1] + mins
    return (total // 60 % 12 or 12, total % 60)


def tdiff(a, b):
    """Minutes from a to b (forward, less than 12 hours)."""
    return ((b[0] % 12) * 60 + b[1] - (a[0] % 12) * 60 - a[1]) % 720


def time_stops(start, end):
    """Jumping up in time: the start, the next o'clock (when the hour changes), the end."""
    if start[1] == 0 or tdiff(start, end) <= 60 - start[1]:
        return [start, end]
    return [start, tadd(start, 60 - start[1]), end]


def jump_times(bk, x, base, stops, spacing, size=15, given=None, example=False, H=18, r=11, vsize=11):
    """Packet 11's jump picture with times: the stops in a row, a curved arrow over each jump with the
    minutes in a bubble. given = indices of the stops printed (the others are boxes); default all."""
    c = bk.c
    given = range(len(stops)) if given is None else given
    xs = [x + i * spacing for i in range(len(stops))]
    for i, (sx, t) in enumerate(zip(xs, stops)):
        if i in given:
            c.setFillColor(T.ink)
            c.setFont("Rnd", size)
            c.drawCentredString(sx, base, tstr(*t))
        else:
            bw = sw(tstr(*t), "Rnd", size) + 14
            bk.box(sx - bw / 2, base - size * 0.42, bw, size * 1.5, tstr(*t), size=size * 0.85)
    lift = size * 1.2
    reveal = T.accent if example else None
    for i in range(len(stops) - 1):
        p0 = (xs[i] + size * 0.6, base + lift)
        p3 = (xs[i + 1] - size * 0.6, base + lift)
        p1 = (p0[0] + 4, base + lift + H)
        p2 = (p3[0] - 4, base + lift + H)
        curve_arrow(bk, p0, p1, p2, p3)
        bx, by = bezier_point(p0, p1, p2, p3, 0.5)
        c.setFillColor(white)
        c.setStrokeColor(T.accent)
        c.setLineWidth(1.4)
        c.circle(bx, by, r, stroke=1, fill=1)
        bk.value(bx, by, tdiff(stops[i], stops[i + 1]), vsize, reveal)


def c_jump_time(bk, x, cy, w, item):
    """mode "given": every time printed, find the jumps. "find": the o'clock is a box too.
    "end": start + minutes, find the o'clock and the end time."""
    start, b, mode = item
    end = tadd(start, b) if mode == "end" else b
    stops = time_stops(start, end)
    total = tdiff(start, end)
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("Rnd", 13)
    head = (f"Start at {tstr(*start)}. {total} minutes later?" if mode == "end"
            else f"From {tstr(*start)} to {tstr(*end)}. How long?")
    c.drawString(x + GUT, cy + 118, head)
    given = {"given": None, "find": (0, len(stops) - 1), "end": (0,)}[mode]
    spacing = (w - GUT - 70) / max(1, len(stops) - 1)
    jump_times(bk, x + GUT + 22, cy + 52, stops, spacing, given=given)
    jumps = [f"[{tdiff(p, q)}]" for p, q in zip(stops, stops[1:])]
    if mode == "end":
        line = " + ".join(jumps) + f" = {total} minutes"
    else:
        line = " + ".join(jumps) + f" = [{total}] minutes"
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, line, size=14)


def c_how_long(bk, x, cy, w, item):
    """Two clocks in the same hour: how many minutes from the first to the second?"""
    a, b = item
    R = 32
    c = bk.c
    for i, (t, lab) in enumerate(((a, "start"), (b, "end"))):
        cx = x + GUT + 40 + i * 130
        clock(bk, cx, cy + 102, R, t, "quarters")
        c.setFillColor(T.text2)
        c.setFont("AvD", 10)
        c.drawCentredString(cx, cy + 44, lab)
    bk.arrow(x + GUT + 40 + R + 16, cy + 102, x + GUT + 170 - R - 16, cy + 102)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{tdiff(a, b)}] minutes", size=15)


def c_read_minute(bk, x, cy, w, item):
    """A big clock to read to the minute."""
    h, m, ring = item
    clock(bk, x + GUT + 52, cy + 58, 42, (h, m), ring)
    bk.eq(x + GUT + 130, cy + 50, f"[{tstr(h, m)}]", size=20)


def elapsed_eq(a, b):
    return f"{tstr(*a)} to {tstr(*b)} = [{tdiff(a, b)}] minutes"


def later_eq(a, mins):
    return f"{mins} minutes after {tstr(*a)} = [{tstr(*tadd(a, mins))}]"


def learn_elapsed(bk):
    y = bk.new_page("Elapsed Time", "How long? Jump to the next o'clock, then to the end.", name_line=False,
                    big=True, footer="WeMath  ·  Elapsed Time")
    c = bk.c
    label(bk, M, y - 6, "Tell time to the minute")
    clock(bk, M + 70, y - 72, 46, (4, 37), "full")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 160, y - 44, "Count by 5s to the 7: 5, 10, 15 … 35.")
    c.drawString(M + 160, y - 62, "Then count the little marks: 36, 37.")
    color_eq(bk, M + 160, y - 98, [("4", "a"), (":", None, "tight"), ("37", "b", "tight")], 28)
    y -= 146

    label(bk, M, y - 6, "How long from 3:40 to 4:25?")
    jump_times(bk, M + 40, y - 84, [(3, 40), (4, 0), (4, 25)], 110, size=20, example=True, H=24, r=14, vsize=13)
    color_eq(bk, M + 300, y - 50, [("20", "b"), ("+", "op"), ("25", "b"), ("=", "op"), ("45 minutes", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 300, y - 76, "Jump to 4:00 first. Then to the end.")
    y -= 116

    label(bk, M, y - 6, "What time is it 25 minutes after 2:50?")
    jump_times(bk, M + 40, y - 84, [(2, 50), (3, 0), (3, 15)], 110, size=20, example=True, H=24, r=14, vsize=13)
    color_eq(bk, M + 300, y - 50, [("10", "b"), ("+", "op"), ("15", "b"), ("=", "op"), ("25", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 300, y - 76, "10 minutes gets to 3:00.")
    c.drawString(M + 300, y - 94, "15 more: it is 3:15.")
    y -= 120

    bottom = your_turn(bk, y, h=108)
    bk.ask("elapsed given 5:35 6:10 your turn")
    jump_times(bk, M + 140, bottom + 40, [(5, 35), (6, 0), (6, 10)], 80, size=17)
    bk.fit_eq(M + 330, bottom + 40, CW - 330 - 16, "[25] + [10] = [35] minutes", size=16)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: time to the minute and intervals in minutes (3.MD.1). Same route as packet 11: jump "
                     "to the next o'clock, then to the end, and add the jumps. Ask “How many minutes to the next "
                     "o'clock?”")


def practice_elapsed(bk):
    title = "Elapsed Time: Practice"
    y = bk.new_page(title, "Jump to the next o'clock. Then jump to the end. Add the jumps.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(1, "Time to the minute", "Count by 5s, then by 1s.",
         [(4, 37, "full"), (9, 12, "full"), (2, 48, "full"), (7, 3, "full"), (11, 26, "full"), (6, 54, "full"),
          (1, 19, "full"), (8, 41, "full")], 2, 116, 10, c_read_minute, KINDS_41["read_minute"].key)
    part(2, "Draw the hands", "The long hand points to the minute mark.",
         [(3, 22, "full"), (10, 8, "full"), (5, 46, "full")], 3, 120, 10, c_draw_hands, KINDS_27["draw_hands"].key)
    part(3, "How long? Same hour", "Count the minutes from start to end.",
         [((1, 10), (1, 45)), ((8, 5), (8, 30)), ((4, 20), (4, 40)), ((10, 15), (10, 55))], 2, 154, 10,
         c_how_long, lambda it: f"how long {tstr(*it[0])} {tstr(*it[1])}")
    key = KINDS_41["jump_time"].key
    part(4, "Jump to the hour", "The stops are given. How big is each jump?",
         [((2, 45), (3, 20), "given"), ((6, 30), (7, 15), "given"), ((9, 50), (10, 30), "given"),
          ((11, 35), (12, 5), "given")], 2, 140, 10, c_jump_time, key)
    part(5, "Find the stops", "Write the o'clock. Then find the jumps.",
         [((1, 25), (2, 10), "find"), ((7, 55), (8, 20), "find"), ((4, 15), (5, 5), "find"),
          ((12, 40), (1, 15), "find")], 2, 140, 10, c_jump_time, key)
    part(6, "What time will it be?", "Jump to the o'clock, then the rest of the minutes.",
         [((5, 45), 30, "end"), ((8, 50), 20, "end"), ((3, 35), 40, "end"), ((10, 40), 35, "end")], 2, 140, 10,
         c_jump_time, key)
    part(7, "How long?", "No help this time.",
         [elapsed_eq(a, b) for a, b in (((4, 5), (4, 50)), ((2, 40), (3, 15)), ((9, 25), (9, 55)),
                                        ((6, 50), (7, 30)), ((12, 10), (12, 45)), ((3, 55), (4, 35)),
                                        ((7, 15), (8, 0)), ((1, 35), (2, 20)), ((5, 20), (5, 48)),
                                        ((10, 45), (11, 12)))], 2, 42, 8, plain, lambda t: t)
    part(8, "What time will it be?", "No help this time.",
         [later_eq(a, n) for a, n in (((2, 15), 30), ((6, 45), 25), ((11, 20), 35), ((4, 50), 40), ((8, 35), 45),
                                      ((1, 5), 50), ((9, 40), 15), ((3, 25), 55), ((7, 50), 30), ((12, 30), 45))],
         2, 42, 8, plain, lambda t: t)
    part(9, "Hours and minutes", "No help this time. 1 hour is 60 minutes.",
         ["1 hour 15 minutes = [75] minutes", "1 hour 40 minutes = [100] minutes", "2 hours = [120] minutes",
          "90 minutes = 1 hour [30] minutes", "1 hour 25 minutes = [85] minutes", "70 minutes = 1 hour [10] minutes"],
         2, 42, 8, plain, lambda t: t)
    part(10, "Remember?", "Problems from earlier packets.", REVIEW_41, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 11, "Word problems", "Jump to the o'clock if it helps.")
    for i, story in enumerate(WORDS_41):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 11, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_41 = ["7 × 80 = [560]", "4 m by 9 m: area = [36] sq m", "8 in by 3 in: perimeter = [22] in",
             "Round 75 to the nearest ten: [80]", "3 groups of 9 = [27]", f"804 {MINUS} 367 = [437]"]

WORDS_41 = [
    ("Soccer practice starts at 3:15 and ends at 4:00. How long is practice?", "3:15 to 4:00 = 45 minutes", "45",
     "minutes"),
    ("A movie starts at 6:40. It lasts 50 minutes. What time does it end?", "20 + 30 = 50, so 7:30", "7:30", "p.m."),
    ("Mia gets on the bus at 7:52 and gets to school at 8:15. How long is the ride?", "8 + 15 = 23", "23",
     "minutes"),
    ("Ben starts reading at 4:35. He reads for 35 minutes. What time does he stop?", "25 + 10 = 35, so 5:10", "5:10",
     "p.m."),
    ("Challenge: School starts at 8:30. Kim needs 10 minutes to get ready and 25 minutes to walk. When should she "
     "start?", f"10 + 25 = 35, 8:30 {MINUS} 35 minutes = 7:55", "7:55", "a.m."),
]

KINDS_41 = {
    "read_minute": Kind(116, 2, KINDS_27["read_clock"].key, c_read_minute),
    "jump_time": Kind(140, 2, lambda it: f"elapsed {it[2]} {tstr(*it[0])} "
                      + (str(it[1]) if it[2] == "end" else tstr(*it[1])), c_jump_time),
}
KINDS.update(KINDS_41)

ELAPSED_EQS = [elapsed_eq((h, m), tadd((h, m), d)) for h in rng(1, 12) for m in rng(5, 55, 5) for d in rng(15, 55, 10)]
LATER_EQS = [later_eq((h, m), d) for h in rng(1, 12) for m in rng(10, 55, 5) for d in rng(20, 50, 5) if m + d > 60]

CHECKINS["46-elapsed-time"] = [
    S("Time to the minute", None, "read_minute", [(h, m, "full") for h in rng(1, 12) for m in rng(1, 59) if m % 5], 2),
    S("Find the stops", None, "jump_time", [((h, m), tadd((h, m), d), "find") for h in rng(1, 11) for m in rng(35, 55, 5)
                                       for d in rng(25, 45, 5) if m + d > 60], 2),
    S("How long?", None, "eq2", ELAPSED_EQS, 2),
    S("What time will it be?", None, "eq2", LATER_EQS, 2),
]
_g3[-1:-1] = [
    S("Elapsed time", None, "eq2", ELAPSED_EQS, 2, 46),
]


# ====================================================================== 47. Word Problems with All Four Operations


def equal_bar(bk, x, y, w, n, each, unknown, h=24, size=13, show_all=False):
    """A bar cut into n equal pieces (packet 30's bars, now for × and ÷). unknown "whole": every piece shows
    `each`, the whole is a box on the bracket. unknown "each": the whole is shown, the first piece is a box.
    show_all prints every number (learning page). y = bottom. Returns the top of the bracket label."""
    c = bk.c
    pw = w / n
    for i in range(n):
        if unknown == "whole" or show_all:
            value, shown = each, True
        else:
            value, shown = (each, False) if i == 0 else ("", True)
        if not shown and pw < 36:  # a narrow piece: a smaller box that stays inside it
            bar_piece(bk, x + i * pw, y, pw, h, "", True, "a" if i % 2 == 0 else "b", size)
            bk.box(x + i * pw + 3, y + 3, pw - 6, h - 6, value, size=size * 0.9)
            continue
        bar_piece(bk, x + i * pw, y, pw, h, value, shown, "a" if i % 2 == 0 else "b", size)
    by = y + h + 7
    c.setStrokeColor(T.text2)
    c.setLineWidth(1)
    c.line(x, by, x + w, by)
    c.line(x, by, x, by - 5)
    c.line(x + w, by, x + w, by - 5)
    whole = n * each
    if unknown == "each" or show_all:
        c.setFillColor(T.ink)
        c.setFont("Rnd", size)
        c.drawCentredString(x + w / 2, by + 5, str(whole))
    else:
        bw = max(28, sw(str(whole), "Rnd", size) + 12)
        bk.box(x + w / 2 - bw / 2, by + 3, bw, size * 1.45, whole, size=size)
    return by + 3 + size * 1.45


def two_step_x(seed):
    """Two-step stories with × or ÷ first (check-ins)."""
    r = random.Random(seed)
    out = []
    for n, e, k in [(n, e, k) for n in rng(3, 7) for e in rng(4, 9) for k in rng(5, 13, 4) if k < n * e]:
        name, t = r.choice(NAMES), r.choice(THINGS)
        out.append((f"{name} has {n} bags with {e} {t} in each bag. {name} gives away {k} {t}. How many {t} are "
                    f"left?", (f"{n} {TIMES} {e} = {n * e}", ("eq", n, e, "whole")),
                    (f"{n * e} {MINUS} {k} = {n * e - k}", ("pw", k, n * e - k, "part")), n * e - k, t, True))
    r.shuffle(out)
    return out


def stories_two(seed):
    """Two-step word problems, no help (assessments): multiply then subtract, or share then add."""
    r = random.Random(seed)
    out = []
    for n, e, k in [(n, e, k) for n in rng(3, 8) for e in rng(3, 9) for k in rng(4, 16, 3) if k < n * e]:
        name, t = r.choice(NAMES), r.choice(THINGS)
        if (n + e + k) % 2 or k > 10:
            out.append((f"{name} has {n} boxes of {e} {t}. {name} uses {k} of them. How many {t} are left?",
                        f"{n} {TIMES} {e} = {n * e}, {n * e} {MINUS} {k} = {n * e - k}", n * e - k, t))
        else:
            out.append((f"{n * e} {t} are shared equally by {n} kids. Then each kid gets {k} more. How many does "
                        f"each kid have now?", f"{n * e} {DIV} {n} = {e}, {e} + {k} = {e + k}", e + k, t))
    r.shuffle(out)
    return out


def about_eq(a, op, b):
    ra, rb = round_to(a, 10), round_to(b, 10)
    return f"{a} {op} {b} is about [{ra + rb if op == '+' else ra - rb}]"


def learn_four_ops(bk):
    y = bk.new_page("All Four Operations", "Two-step problems with +, −, × and ÷. Draw the bar.",
                    name_line=False, big=True, footer="WeMath  ·  All Four Operations")
    c = bk.c
    label(bk, M, y - 6, "4 bags with 6 apples in each: equal pieces")
    equal_bar(bk, M + 14, y - 72, 240, 4, 6, "whole", h=28, size=15, show_all=True)
    color_eq(bk, M + 300, y - 50, [("4", "a"), (TIMES, "op"), ("6", "b"), ("=", "op"), ("24", None)], 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 300, y - 72, "Know the pieces? Multiply.")
    y -= 92

    label(bk, M, y - 6, "30 stickers shared by 5 kids")
    equal_bar(bk, M + 14, y - 72, 240, 5, 6, "each", h=28, size=15, show_all=True)
    color_eq(bk, M + 300, y - 50, [("30", None), (DIV, "op"), ("5", "a"), ("=", "op"), ("6", "b")], 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 300, y - 72, "Know the whole? Divide.")
    y -= 92

    label(bk, M, y - 6, "Two steps: 3 packs of 8 pencils. 5 get lost. How many are left?")
    c.setFillColor(T.text2)
    c.setFont("AvD", 9)
    c.drawString(M + 14, y - 30, "Step 1")
    equal_bar(bk, M + 14, y - 76, 200, 3, 8, "whole", size=13, show_all=True)
    c.setFillColor(T.text2)
    c.setFont("AvD", 9)
    c.drawString(M + 264, y - 30, "Step 2")
    bar_model(bk, M + 264, y - 76, 200, [(5, True), (19, True)], (24, True))
    color_eq(bk, M + 14, y - 104, [("3", "a"), (TIMES, "op"), ("8", "b"), ("=", "op"), ("24", None)], 18)
    color_eq(bk, M + 264, y - 104, [("24", None), (MINUS, "op"), ("5", "a"), ("=", "op"), ("19", "b")], 18)
    y -= 126

    label(bk, M, y - 6, "Does it make sense? Round to check.")
    color_eq(bk, M + 14, y - 38, [("38", None), ("+", "op"), ("47", None), ("=", "op"), ("85", None)], 20)
    color_eq(bk, M + 200, y - 38, [("about", None), ("40", "a"), ("+", "op"), ("50", "b"), ("=", "op"),
                                   ("90", None)], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 60, "85 is close to 90, so it makes sense. 58 would not.")
    y -= 78

    bottom = your_turn(bk, y, h=96)
    bk.ask("bar: eq 5 7 whole your turn")
    equal_bar(bk, M + 120, bottom + 22, 220, 5, 7, "whole")
    bk.fit_eq(M + 370, bottom + 30, CW - 370 - 16, f"[5] {TIMES} [7] = [35]", size=17)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: two-step problems with +, −, × and ÷ (3.OA.8). Equal pieces mean × (whole missing) "
                     "or ÷ (a piece missing). Solve step 1, then use it in step 2. Round to check the answer "
                     "makes sense.")


def practice_four_ops(bk):
    title = "All Four Operations: Practice"
    y = bk.new_page(title, "Read. Draw the bar. Write the number sentence. Answer.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    story_key = lambda it: f"story: {it[2]}"
    part(1, "Equal pieces: find the whole", "Every piece is the same. Multiply.", [
        ("Tia buys 8 boxes of crayons. Each box has 6 crayons. How many crayons does she have?",
         ("eq", 8, 6, "whole"), f"8 {TIMES} 6 = 48", "crayons"),
        ("There are 4 tables. 7 kids sit at each table. How many kids are there?", ("eq", 4, 7, "whole"),
         f"4 {TIMES} 7 = 28", "kids"),
        ("There are 9 vases with 7 flowers in each vase. How many flowers is that?", ("eq", 9, 7, "whole"),
         f"9 {TIMES} 7 = 63", "flowers"),
        ("Each pack has 8 juice boxes. Ms. Lee buys 5 packs. How many juice boxes is that?", ("eq", 5, 8, "whole"),
         f"5 {TIMES} 8 = 40", "juice boxes"),
    ], 1, 132, 10, c_story_bar, story_key)
    part(2, "Equal pieces: find one piece", "The whole is shared equally. Divide.", [
        ("27 kids make 3 equal teams. How many kids are on each team?", ("eq", 3, 9, "each"), f"27 {DIV} 3 = 9",
         "kids"),
        ("A ribbon 40 inches long is cut into 5 equal pieces. How long is each piece?", ("eq", 5, 8, "each"),
         f"40 {DIV} 5 = 8", "inches"),
        ("63 apples are packed into 9 equal bags. How many apples are in each bag?", ("eq", 9, 7, "each"),
         f"63 {DIV} 9 = 7", "apples"),
        ("Dad shares 48 grapes equally among 6 kids. How many grapes does each kid get?", ("eq", 6, 8, "each"),
         f"48 {DIV} 6 = 8", "grapes"),
    ], 1, 132, 10, c_story_bar, story_key)
    two_key = lambda it: f"story: {it[1][0]}; {it[2][0]}"
    part(3, "Two steps", "The bars are drawn for you. Step 1 helps with step 2.", [
        ("Ben buys 4 packs of 6 cookies. He eats 5 cookies. How many cookies are left?",
         (f"4 {TIMES} 6 = 24", ("eq", 4, 6, "whole")), (f"24 {MINUS} 5 = 19", ("pw", 5, 19, "part")), 19,
         "cookies", True),
        ("28 kids sit at 4 tables, the same number at each. Then 3 more kids join each table. How many kids are at "
         "each table now?", (f"28 {DIV} 4 = 7", ("eq", 4, 7, "each")), ("7 + 3 = 10", ("pw", 7, 3, "whole")), 10,
         "kids", True),
        ("Mia has 3 bags of 9 marbles. Sam has 15 marbles. How many more marbles does Mia have?",
         (f"3 {TIMES} 9 = 27", ("eq", 3, 9, "whole")), ("15 + 12 = 27", ("cmp", 27, 15, "diff", ("Mia", "Sam"))),
         12, "marbles", True),
    ], 1, 218, 10, c_two_step, two_key)
    part(4, "Two steps on your own", "Draw a bar for each step.", [
        ("A class has 5 rows of 6 desks. 8 desks are empty. How many desks have kids at them?",
         (f"5 {TIMES} 6 = 30", None), (f"30 {MINUS} 8 = 22", None), 22, "desks", False),
        ("Kim shares 45 beads equally among 5 friends. Each friend uses 3 beads. How many beads does each friend "
         "have left?", (f"45 {DIV} 5 = 9", None), (f"9 {MINUS} 3 = 6", None), 6, "beads", False),
        ("Stickers cost $4 a pack. Leo buys 6 packs and pays with $30. How much change does he get?",
         (f"6 {TIMES} $4 = $24", None), (f"$30 {MINUS} $24 = $6", None), "$6", "", False),
        ("A farmer has 7 rows of 8 corn plants and 20 tomato plants. How many plants are there in all?",
         (f"7 {TIMES} 8 = 56", None), ("56 + 20 = 76", None), 76, "plants", False),
    ], 1, 218, 10, c_two_step, two_key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(5, "Does it make sense?", "Round each number to the nearest ten. About how much?",
         [about_eq(a, op, b) for a, op, b in ((38, "+", 47), (24, "+", 33), (82, MINUS, 37), (56, "+", 41),
                                              (93, MINUS, 21), (66, "+", 12), (58, MINUS, 33), (71, MINUS, 49))],
         2, 42, 8, plain, lambda t: t)
    part(6, "Remember?", "Problems from earlier packets.", REVIEW_42, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 7, "Word problems", "No help this time. Two steps each.")
    for i, story in enumerate(WORDS_42):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 7, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_42 = ["3 × 80 = [240]", "6 cm by 9 cm: area = [54] sq cm", "7 m by 2 m: perimeter = [18] m",
             "20 minutes after 3:50 = [4:10]", "Round 438 to the nearest hundred: [400]",
             "1 hour 30 minutes = [90] minutes"]

WORDS_42 = [
    ("A box holds 6 eggs. Mom buys 5 boxes and uses 12 eggs. How many eggs are left?",
     f"5 {TIMES} 6 = 30, 30 {MINUS} 12 = 18", "18", "eggs"),
    ("Ana has 32 stickers. She gives 4 friends 5 stickers each. How many stickers are left?",
     f"4 {TIMES} 5 = 20, 32 {MINUS} 20 = 12", "12", "stickers"),
    ("24 kids stand in 3 equal lines. 2 kids leave each line. How many kids are in each line now?",
     f"24 {DIV} 3 = 8, 8 {MINUS} 2 = 6", "6", "kids"),
    ("Tickets cost $7 each. Ben buys 3 tickets and a $9 snack. How much does he spend?",
     f"3 {TIMES} $7 = $21, $21 + $9 = $30", "$30", ""),
    ("A garden has 9 rows of 4 plants. Then 10 more plants are added. How many plants are there now?",
     f"9 {TIMES} 4 = 36, 36 + 10 = 46", "46", "plants"),
    ("Challenge: Leo reads 8 pages a day for 7 days. His book has 100 pages. How many pages are left?",
     f"7 {TIMES} 8 = 56, 100 {MINUS} 56 = 44", "44", "pages"),
]

EQUAL_BARS = [("eq", n, e, u) for n in rng(3, 8) for e in rng(3, 9) for u in ("whole", "each") if (n, e) != (5, 7)]

CHECKINS["47-four-operations"] = [
    S("Equal pieces", "Find the number that goes in the box.", "bar", EQUAL_BARS, 4),
    S("Two steps", None, "two_step", two_step_x("c42"), 1),
    S("Two-step word problems", None, "word", stories_two("w42"), 1),
]
_g3[-1:-1] = [
    S("Equal pieces", None, "bar", EQUAL_BARS, 2, 47),
    S("Two-step word problems", None, "word", stories_two("g42"), 2, 47),
]


# ====================================================================== 48. Patterns in the Times Table


def times_table(bk, x, top, n=10, cell=20, hl_rows=(), hl_cols=(), hl_cells=(), blanks=(), hide=False, size=None):
    """A multiplication table 1..n. hl_* shade rows, columns or cells (light blue / orange). blanks = cells drawn as
    answer boxes; hide=True leaves every product blank except the shaded ones. Returns (width, height)."""
    c = bk.c
    size = size or cell * 0.5
    W = (n + 1) * cell
    for i in range(n + 1):
        for j in range(n + 1):
            cx, cy = x + j * cell, top - (i + 1) * cell
            head = i == 0 or j == 0
            fill = None
            if not head and ((i in hl_rows) or (j in hl_cols)):
                fill = T.band
            if not head and (i, j) in hl_cells:
                fill = T.strip
            if head:
                fill = T.panel
            if fill is not None and T.color:
                c.setFillColor(fill)
                c.rect(cx, cy, cell, cell, stroke=0, fill=1)
            c.setStrokeColor(T.line if T.color else T.muted)
            c.setLineWidth(0.6)
            c.rect(cx, cy, cell, cell, stroke=1, fill=0)
            if i == 0 and j == 0:
                c.setFillColor(T.text2)
                c.setFont("AvD", size)
                c.drawCentredString(cx + cell / 2, cy + cell / 2 - size * 0.36, TIMES)
                continue
            v = j if i == 0 else i if j == 0 else i * j
            if (i, j) in blanks:
                bk.value(cx + cell / 2, cy + cell / 2, v, size=size)
                continue
            shaded = (i in hl_rows) or (j in hl_cols) or ((i, j) in hl_cells)
            if hide and not head and not shaded:
                continue
            c.setFillColor(T.ink if not head else T.text2)
            c.setFont("AvB" if head else "Rnd", size)
            c.drawCentredString(cx + cell / 2, cy + cell / 2 - size * 0.36, str(v))
    c.setStrokeColor(T.ink)
    c.setLineWidth(1)
    c.rect(x, top - (n + 1) * cell, W, (n + 1) * cell, stroke=1, fill=0)
    return W, (n + 1) * cell


def c_table_row(bk, x, cy, w, item):
    """One row of the table, n × 1 … n × 10, some products blank."""
    n, blanks = item
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("Rnd", 15)
    c.drawString(x + GUT, cy + 15, f"{TIMES}{n}")
    step = (w - GUT - 60) / 10
    for k in range(1, 11):
        bx = x + GUT + 44 + (k - 1) * step
        if k in blanks:
            bk.box(bx, cy + 9, step - 6, 26, n * k, size=14)
        else:
            c.setFillColor(T.ink)
            c.setFont("Rnd", 14)
            c.drawCentredString(bx + (step - 6) / 2, cy + 17, str(n * k))


def c_table_piece(bk, x, cy, w, item):
    """A piece of the table: rows r0.., columns c0.., some products blank."""
    r0, c0, rows, cols, blanks = item
    c = bk.c
    cell = 30
    x0, top = x + GUT, cy + 18 + (rows + 1) * cell
    for i in range(rows + 1):
        for j in range(cols + 1):
            cx_, cy_ = x0 + j * cell, top - (i + 1) * cell
            head = i == 0 or j == 0
            if head and T.color:
                c.setFillColor(T.panel)
                c.rect(cx_, cy_, cell, cell, stroke=0, fill=1)
            c.setStrokeColor(T.line if T.color else T.muted)
            c.setLineWidth(0.7)
            c.rect(cx_, cy_, cell, cell, stroke=1, fill=0)
            if i == 0 and j == 0:
                c.setFillColor(T.text2)
                c.setFont("AvD", 13)
                c.drawCentredString(cx_ + cell / 2, cy_ + 10, TIMES)
                continue
            r, k = r0 + i - 1, c0 + j - 1
            v = k if i == 0 else r if j == 0 else r * k
            if not head and (i - 1, j - 1) in blanks:
                bk.value(cx_ + cell / 2, cy_ + cell / 2, v, size=13)
                continue
            c.setFillColor(T.text2 if head else T.ink)
            c.setFont("AvB" if head else "Rnd", 13)
            c.drawCentredString(cx_ + cell / 2, cy_ + 10, str(v))


def c_eo_product(bk, x, cy, w, item):
    a, b = item
    bk.eq(x + GUT, cy + 40, f"{a} {TIMES} {b}", size=17)
    even_odd_choice(bk, x + GUT + 4, cy + 12, a * b)


def learn_patterns(bk):
    y = bk.new_page("Patterns in the Times Table", "Look for patterns. They help you remember the facts.",
                    name_line=False, big=True, footer="WeMath  ·  Patterns in the Times Table")
    c = bk.c
    label(bk, M, y - 6, "The times table")
    times_table(bk, M + 6, y - 18, 10, 20, hl_rows=(4,), hl_cells=((3, 7), (7, 3)))
    tx = M + 250
    notes = [("Row 4 is all even:", "4 × anything is even.", "a"),
             ("3 × 7 and 7 × 3 match:", "turnarounds mirror across the table.", "b"),
             ("Going down a column:", "add the top number each time.", None),
             ("Odd × odd is odd:", "3 × 5 = 15, 7 × 9 = 63.", None)]
    for i, (head, text, kind) in enumerate(notes):
        yy = y - 30 - i * 46
        if kind and T.color:
            c.setFillColor(T.band if kind == "a" else T.strip)
            c.rect(tx, yy - 2, 12, 12, stroke=0, fill=1)
        c.setFillColor(T.ink)
        c.setFont("AvB", 12)
        c.drawString(tx + (18 if kind else 0), yy, head)
        c.setFillColor(T.text2)
        c.setFont("Rnd", 12)
        c.drawString(tx + (18 if kind else 0), yy - 17, text)
    y -= 250

    label(bk, M, y - 6, "Double a number, double the answer")
    color_eq(bk, M + 14, y - 40, [("3", "a"), (TIMES, "op"), ("6", None), ("=", "op"), ("18", "a")], 22)
    color_eq(bk, M + 14, y - 72, [("6", "b"), (TIMES, "op"), ("6", None), ("=", "op"), ("36", "b")], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 220, y - 40, "6 is double 3,")
    c.drawString(M + 220, y - 58, "so 36 is double 18.")
    y -= 96

    bottom = your_turn(bk, y, h=96)
    bk.ask("table row 4 your turn")
    for k in range(1, 7):
        bx = M + 130 + (k - 1) * 52
        if k in (3, 5, 6):
            bk.box(bx, bottom + 28, 42, 30, 4 * k, size=17)
        else:
            c.setFillColor(T.ink)
            c.setFont("Rnd", 17)
            c.drawCentredString(bx + 21, bottom + 37, str(4 * k))
    c.setFillColor(T.ink)
    c.setFont("Rnd", 17)
    c.drawString(M + 80, bottom + 37, f"{TIMES}4")
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: find patterns in the times table and explain them (3.OA.9). Ask “Why is every number "
                     "in the 4s row even?” and “What do you notice about 3 × 7 and 7 × 3?” Patterns make the "
                     "hard facts easier to remember.")


def practice_patterns(bk):
    title = "Patterns in the Times Table: Practice"
    y = bk.new_page(title, "Use the patterns. Check with the table if you need to.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(1, "Fill in the row", "Add the same number each time.",
         [(3, (2, 5, 7, 10)), (6, (3, 4, 8, 9)), (8, (2, 5, 6, 9)), (7, (3, 6, 7, 10)), (9, (2, 4, 8, 9)),
          (4, (5, 7, 8, 10))], 1, 46, 8, c_table_row, KINDS_43["table_row"].key)
    part(2, "Pieces of the table", "Fill in the missing products.",
         [(3, 4, 3, 4, ((0, 2), (1, 0), (2, 3))), (6, 2, 3, 4, ((0, 1), (1, 3), (2, 0))),
          (5, 6, 3, 4, ((0, 3), (1, 1), (2, 2))), (7, 5, 3, 4, ((0, 0), (1, 2), (2, 3)))], 2, 150, 10, c_table_piece,
         KINDS_43["table_piece"].key)
    part(3, "Even or odd?", "Even × any number is even. Odd × odd is odd.",
         shuf("eo43", [(3, 8), (5, 7), (6, 9), (9, 3), (4, 7), (7, 7), (2, 9), (5, 5), (8, 3)]), 3, 66, 8,
         c_eo_product, KINDS_43["eo_product"].key)
    part(4, "Double it", "No help this time. Double one number, double the answer.",
         [double_fact(a, b) for a, b in ((2, 7), (3, 9), (4, 6), (2, 8), (3, 4), (5, 7), (4, 9), (2, 6), (3, 7),
                                         (4, 8))], 2, 42, 8, plain, lambda t: t)
    part(5, "Times 9 from times 10", "No help this time. Take away one group.",
         [f"10 {TIMES} {n} = {10 * n} so 9 {TIMES} {n} = [{9 * n}]" for n in (6, 3, 8, 4, 7, 9)], 2, 42, 8, plain,
         lambda t: t)
    part(6, "Times 5 from times 10", "No help this time. Times 5 is half of times 10.",
         [f"10 {TIMES} {n} = {10 * n} so 5 {TIMES} {n} = [{5 * n}]" for n in (8, 3, 6, 9, 4, 7)], 2, 42, 8, plain,
         lambda t: t)
    part(7, "Remember?", "Problems from earlier packets.", REVIEW_43, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Look for a pattern.")
    for i, story in enumerate(WORDS_43):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


def double_fact(a, b):
    return f"{a} {TIMES} {b} = {a * b} so {2 * a} {TIMES} {b} = [{2 * a * b}]"


REVIEW_43 = ["7 m by 6 m: area = [42] sq m", "40 minutes after 2:35 = [3:15]", "Round 481 to the nearest hundred: [500]",
             "3 × 70 = [210]", f"72 {MINUS} 38 = [34]", f"64 {MINUS} 27 = [37]"]

WORDS_43 = [
    ("Each table has 4 legs. Is the number of legs on 7 tables even or odd?", f"7 {TIMES} 4 = 28, even", "even", ""),
    ("A pack has 6 juice boxes. 3 packs have 18. How many juice boxes are in 6 packs?", "double 18 = 36", "36",
     "juice boxes"),
    ("9 boxes hold 8 crayons each. How many crayons is that?", f"10 {TIMES} 8 = 80, 80 {MINUS} 8 = 72", "72",
     "crayons"),
    ("Ben counts by 5s, 8 times. What number does he say last?", f"8 {TIMES} 5 = 40", "40", ""),
    ("Challenge: Kim says 7 × 9 = 64. Odd × odd is odd, so that can't be right. What is 7 × 9?",
     f"7 {TIMES} 9 = 63, odd", "63", ""),
]

KINDS_43 = {
    "table_row": Kind(46, 1, lambda it: f"table row {it[0]} " + "-".join(map(str, it[1])), c_table_row),
    "table_piece": Kind(150, 2, lambda it: "table piece " + " ".join(map(str, it[:4])) + " "
                        + "-".join(f"{a}.{b}" for a, b in it[4]), c_table_piece),
    "eo_product": Kind(66, 3, lambda it: f"even odd product {it[0]} {it[1]}", c_eo_product),
}
KINDS.update(KINDS_43)
BALANCE["eo_product"] = lambda it: it[0] * it[1] % 2 == 0

EO_PRACTICE = [(3, 8), (5, 7), (6, 9), (9, 3), (4, 7), (7, 7), (2, 9), (5, 5), (8, 3)]
# The pool leaves out the practice ones, so the check-in's even/odd answers really alternate.
EO_POOL = [(a, b) for a in rng(2, 9) for b in rng(2, 9) if (a, b) not in EO_PRACTICE]

CHECKINS["48-patterns-in-the-times-table"] = [
    S("Fill in the row", None, "table_row", [(n, b) for n in rng(3, 9) for b in ((2, 5, 7, 9), (3, 4, 8, 10))
                                             if (n, b) != (4, (3, 5, 6))], 1),
    S("Pieces of the table", None, "table_piece", [(r, k, 3, 4, ((0, 1), (1, 3), (2, 0))) for r in rng(2, 7)
                                                   for k in rng(2, 6)], 2),
    S("Even or odd?", None, "eo_product", EO_POOL, 3),
    S("Double it", None, "eq2", [double_fact(a, b) for a in rng(2, 5) for b in rng(2, 9)], 2),
]
_g3[-1:-1] = [
    S("Times table patterns", None, "eo_product", EO_POOL, 2, 48),
]


# ====================================================================== 49. Mass and Liquid Volume


def weight_label(v, unit):
    return f"{v} {unit}"


def balance(bk, cx, by, obj, weights, unit="g", obj_label=None):
    """A pan balance, level: the object on the left pan, weights stacked on the right pan. by = bottom of the stand.
    obj = an icon kind, or None with obj_label for a labelled box (e.g. "1 kg")."""
    c = bk.c
    top = by + 92
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.3)
    c.drawPath(_poly(c, [(cx - 16, by), (cx + 16, by), (cx + 3, top - 4), (cx - 3, top - 4)]), stroke=1, fill=0)
    c.setLineWidth(2)
    c.line(cx - 78, top, cx + 78, top)
    c.setFillColor(T.ink)
    c.circle(cx, top, 3.2, stroke=0, fill=1)
    for side in (-1, 1):
        px = cx + side * 64
        c.setStrokeColor(T.text2)
        c.setLineWidth(0.8)
        c.line(px, top, px - 26, by + 18)
        c.line(px, top, px + 26, by + 18)
        c.setStrokeColor(T.ink)
        c.setLineWidth(2.2)
        c.line(px - 30, by + 18, px + 30, by + 18)
    lx = cx - 64
    if obj:
        icon(bk, obj, lx, by + 34, 28)
    else:
        bw = max(34, sw(obj_label, "AvD", 9) + 12)
        c.setStrokeColor(T.ink)
        c.setLineWidth(1)
        if T.color:
            c.setFillColor(T.strip)
            c.rect(lx - bw / 2, by + 20, bw, 26, stroke=1, fill=1)
        else:
            c.rect(lx - bw / 2, by + 20, bw, 26, stroke=1, fill=0)
        c.setFillColor(T.ink)
        c.setFont("AvD", 9)
        c.drawCentredString(lx, by + 29.5, obj_label)
    rx = cx + 64
    for i, v in enumerate(weights):
        wy = by + 20 + i * 14
        text = weight_label(v, unit)
        bw = max(34, sw(text, "AvD", 7.5) + 10)
        c.setStrokeColor(T.ink)
        c.setLineWidth(0.9)
        if T.color:
            c.setFillColor(T.band)
            c.rect(rx - bw / 2, wy, bw, 13, stroke=1, fill=1)
        else:
            c.rect(rx - bw / 2, wy, bw, 13, stroke=1, fill=0)
        c.setFillColor(T.ink)
        c.setFont("AvD", 7.5)
        c.drawCentredString(rx, wy + 3.6, text)


def beaker(bk, x, y, h, maxv, level, w=44, label_every=1):
    """A measuring beaker with a mark for every liter, filled to `level`. x, y = bottom left of the beaker."""
    c = bk.c
    lh = h * level / maxv
    if T.color:
        c.setFillColor(T.band)
        c.rect(x, y, w, lh, stroke=0, fill=1)
    else:
        shade(bk, [(x, y), (x + w, y), (x + w, y + lh), (x, y + lh)])
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.4)
    c.line(x, y + h + 6, x, y)
    c.line(x, y, x + w, y)
    c.line(x + w, y, x + w, y + h + 6)
    c.line(x + w, y + h + 6, x + w + 5, y + h + 10)
    c.setLineWidth(0.8)
    for k in range(1, maxv + 1):
        ty = y + h * k / maxv
        c.line(x + w - (12 if k % label_every == 0 else 6), ty, x + w, ty)
        if k % label_every == 0:
            c.setFillColor(T.text2)
            c.setFont("AvD", 7.5)
            c.drawRightString(x - 4, ty - 2.5, str(k))
    c.setFillColor(T.text2)
    c.setFont("AvD", 8)
    c.drawString(x + w + 8, y + h + 4, "L")


def c_balance(bk, x, cy, w, item):
    obj, weights, unit = item
    balance(bk, x + GUT + 84, cy + 14, obj, weights, unit)
    tx = x + GUT + 196
    bk.fit_eq(tx, cy + 58, w - (tx - x) - 8, " + ".join(map(str, weights)) + f" = [{sum(weights)}] {unit}", size=14)


def c_beaker(bk, x, cy, w, item):
    level, maxv = item
    beaker(bk, x + GUT + 20, cy + 46, 76, maxv, level, label_every=1 if maxv <= 10 else 2)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 8, f"[{level}] liters", size=15)


def c_beaker_cmp(bk, x, cy, w, item):
    a, b, maxv = item
    c = bk.c
    for i, (lev, name) in enumerate(((a, "A"), (b, "B"))):
        bx = x + GUT + 22 + i * 90
        beaker(bk, bx, cy + 46, 76, maxv, lev)
        c.setFillColor(T.ink)
        c.setFont("AvB", 10)
        c.drawCentredString(bx + 22, cy + 32, name)
    tx = x + GUT + 200
    bk.c.setFillColor(T.text2)
    bk.c.setFont("AvM", 10)
    bk.c.drawString(tx, cy + 96, "How much more is in B?")
    bk.fit_eq(tx, cy + 62, w - (tx - x) - 8, f"[{b}] L {MINUS} [{a}] L = [{b - a}] L", size=14)


def learn_mass_volume(bk):
    y = bk.new_page("Mass and Liquid Volume", "How heavy is it? How much does it hold?", name_line=False, big=True,
                    footer="WeMath  ·  Mass and Liquid Volume")
    c = bk.c
    label(bk, M, y - 6, "Grams for light things, kilograms for heavy things")
    clip(bk, M + 14, y - 40, 40, 12)
    c.setFillColor(T.ink)
    c.setFont("Rnd", 13)
    c.drawString(M + 64, y - 45, "A paper clip is about 1 gram (g).")
    balance(bk, M + 120, y - 160, None, [500, 200, 200, 100], "g", obj_label="1 kg")
    color_eq(bk, M + 260, y - 100, [("1 kilogram", "a"), ("=", "op"), ("1000 grams", "b")], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 260, y - 124, "The pans are level: they weigh the same.")
    y -= 186

    label(bk, M, y - 6, "Read the balance: add the weights")
    balance(bk, M + 100, y - 132, "apple", [100, 50, 20], "g")
    color_eq(bk, M + 14, y - 154, [("100", "a"), ("+", "op"), ("50", "a"), ("+", "op"), ("20", "a"), ("=", "op"),
                                   ("170 g", "b")], 18)
    label(bk, M + 290, y - 6, "Read the beaker: count the marks")
    beaker(bk, M + 320, y - 124, 90, 10, 6)
    color_eq(bk, M + 400, y - 70, [("6", "b"), ("liters (L)", None)], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 11)
    c.drawString(M + 400, y - 90, "Each mark is 1 liter.")
    y -= 178

    bottom = your_turn(bk, y, h=124)
    bk.ask("beaker 4 of 10 your turn")
    beaker(bk, M + 150, bottom + 14, 80, 10, 4)
    bk.eq(M + 300, bottom + 50, "[4] liters", size=18)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: measure mass in grams and kilograms and liquid volume in liters, and solve problems "
                     "with them (3.MD.2). Hold a paper clip (1 g) and a big book (about 1 kg). Say “Is it light "
                     "or heavy? Grams or kilograms?”")


def practice_mass_volume(bk):
    title = "Mass and Liquid Volume: Practice"
    y = bk.new_page(title, "Grams, kilograms and liters.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(1, "Grams or kilograms?", "Light things are grams. Heavy things are kilograms.", MASS_UNITS[:8], 1, 40, 6,
         c_unit_choice, KINDS_31["unit_choice"].key)
    part(2, "Read the balance", "Add the weights on the other pan.",
         [("egg", (50, 10), "g"), ("cupcake", (50, 20, 5), "g"), ("duck", (200, 100, 50), "g"),
          ("car", (100, 20, 20), "g"), ("fish", (500, 200), "g"), ("frog", (20, 10, 5, 5), "g")], 1, 128, 10,
         c_balance, KINDS_44["balance"].key)
    part(3, "Read the beaker", "Find the top of the water. Count the marks.",
         [(7, 10), (3, 10), (9, 10), (12, 20), (5, 10), (16, 20)], 3, 136, 10, c_beaker, KINDS_44["beaker"].key)
    part(4, "How much more?", "Take away the smaller amount.",
         [(3, 8, 10), (5, 9, 10), (2, 7, 10), (4, 10, 10)], 1, 140, 10, c_beaker_cmp, KINDS_44["beaker_cmp"].key)
    part(5, "Add and take away grams", "No help this time.",
         ["350 g + 240 g = [590] g", f"800 g {MINUS} 350 g = [450] g", "125 g + 475 g = [600] g",
          f"1000 g {MINUS} 400 g = [600] g", "460 g + 270 g = [730] g", f"900 g {MINUS} 625 g = [275] g",
          "3 kg + 6 kg = [9] kg", f"15 kg {MINUS} 8 kg = [7] kg"], 2, 42, 8, plain, lambda t: t)
    part(6, "Liters", "No help this time.",
         ["4 bottles of 2 L = [8] L", "3 jugs of 5 L = [15] L", "12 L in 3 equal jugs = [4] L each",
          "7 L + 8 L = [15] L", f"20 L {MINUS} 6 L = [14] L", "6 buckets of 4 L = [24] L"], 2, 42, 8, plain,
         lambda t: t)
    part(7, "Remember?", "Problems from earlier packets.", REVIEW_44, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Draw a bar if it helps.")
    for i, story in enumerate(WORDS_44):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


MASS_UNITS = [("A grape is about 5", ["grams", "kilograms"], "grams"),
              ("A big dog is about 30", ["grams", "kilograms"], "kilograms"),
              ("A paper clip is about 1", ["grams", "kilograms"], "grams"),
              ("A bike is about 12", ["grams", "kilograms"], "kilograms"),
              ("A strawberry is about 15", ["grams", "kilograms"], "grams"),
              ("A bag of rice is about 2", ["grams", "kilograms"], "kilograms"),
              ("A pencil is about 6", ["grams", "kilograms"], "grams"),
              ("A watermelon is about 5", ["grams", "kilograms"], "kilograms"),
              ("A coin is about 3", ["grams", "kilograms"], "grams"),
              ("A cat is about 4", ["grams", "kilograms"], "kilograms"),
              ("An eraser is about 20", ["grams", "kilograms"], "grams"),
              ("A box of books is about 15", ["grams", "kilograms"], "kilograms")]

REVIEW_44 = ["6 × 8 = 48 so 6 × 4 = [24]", "4 m by 7 m: area = [28] sq m", "25 minutes after 9:50 = [10:15]",
             "Round 638 to the nearest ten: [640]", f"81 {DIV} 9 = [9]", "306 + 495 = [801]"]

WORDS_44 = [
    ("A bag of apples weighs 3 kg. How much do 4 bags weigh?", f"4 {TIMES} 3 = 12", "12", "kg"),
    ("A pitcher holds 2 liters. How many pitchers fill an 18-liter tub?", f"18 {DIV} 2 = 9", "9", "pitchers"),
    ("Mia's backpack weighs 4 kg. Her lunch adds 1 kg and a book adds 2 kg. What is the total?", "4 + 1 + 2 = 7",
     "7", "kg"),
    ("A fish tank holds 40 liters. It has 23 liters in it now. How much more water will fill it?",
     "23 + 17 = 40", "17", "liters"),
    ("Challenge: A box holds 6 bags of flour. Each bag is 2 kg. The empty box is 1 kg. How heavy is the full box?",
     f"6 {TIMES} 2 = 12, 12 + 1 = 13", "13", "kg"),
]

KINDS_44 = {
    "balance": Kind(128, 1, lambda it: f"balance {it[0]} " + "-".join(map(str, it[1])) + f" {it[2]}", c_balance),
    "beaker": Kind(136, 3, lambda it: f"beaker {it[0]} of {it[1]}", c_beaker),
    "beaker_cmp": Kind(140, 1, lambda it: f"beaker compare {it[0]} {it[1]} of {it[2]}", c_beaker_cmp),
}
KINDS.update(KINDS_44)

CHECKINS["49-mass-and-liquid-volume"] = [
    S("Grams or kilograms?", None, "unit_choice", MASS_UNITS, 2),
    S("Read the balance", None, "balance", [(k, ws, "g") for k in ("apple", "egg", "duck", "cupcake", "fish")
                                             for ws in ((100, 50, 10), (200, 20, 5), (50, 20, 20), (500, 100))], 1),
    S("Read the beaker", None, "beaker", [(n, 10) for n in rng(1, 9) if n not in (4, 6)], 3),
]
_g3[-1:-1] = [
    S("Mass and liquid volume", None, "beaker", [(n, 10) for n in rng(1, 9) if n not in (4, 6)], 2, 49),
]


# ====================================================================== 50. Scaled Graphs


def scaled_picture_graph(bk, x, top, title, cats, counts, kind, per, cell=17, labw=58, show=True):
    """Picture graph where each picture stands for `per` (counts are multiples of per). Returns the bottom y."""
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("AvD", 10.5)
    c.drawString(x, top - 10, title)
    y = top - 22
    for cat, n in zip(cats, counts):
        y -= cell + 4
        c.setFillColor(T.text2)
        c.setFont("AvM", 10)
        c.drawString(x, y + cell / 2 - 3.5, cat)
        c.setStrokeColor(T.line)
        c.setLineWidth(0.6)
        c.line(x + labw - 6, y - 2, x + labw + 10 * cell, y - 2)
        if show or bk.key:
            for i in range(n // per):
                icon(bk, kind, x + labw + cell / 2 + i * cell, y + cell / 2, cell * 0.82)
    c.setFillColor(T.ink)
    c.setFont("AvB", 9.5)
    c.drawString(x, y - 17, "Each")
    icon(bk, kind, x + 34, y - 13.5, 12)
    c.setFillColor(T.ink)
    c.setFont("AvB", 9.5)
    c.drawString(x + 44, y - 17, f"= {per}")
    return y - 22


def scaled_bar_graph(bk, x, top, title, cats, counts, step, rows=10, cell=11, barw=34, show=True):
    """Bar graph whose scale counts by `step` (each grid line is `step` more). show=False: empty grid."""
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("AvD", 10.5)
    c.drawString(x, top - 10, title)
    gx, gy = x + 24, top - 24 - rows * cell
    gw = len(cats) * (barw + 10) + 10
    if show or bk.key:
        for i, n in enumerate(counts):
            bx = gx + 10 + i * (barw + 10)
            hgt = n / step * cell
            fill = (T.band if show else T.share_ans) if T.color else None
            if fill is not None:
                c.setFillColor(fill)
                c.rect(bx, gy, barw, hgt, stroke=0, fill=1)
            elif not show:
                shade(bk, [(bx, gy), (bx + barw, gy), (bx + barw, gy + hgt), (bx, gy + hgt)], answer=True)
            c.setStrokeColor(T.dot_a if show and T.color else T.answer if not show else T.ink)
            c.setLineWidth(1.2)
            c.rect(bx, gy, barw, hgt, stroke=1, fill=0)
    c.setStrokeColor(T.line)
    c.setLineWidth(0.5)
    for j in range(1, rows + 1):
        c.line(gx, gy + j * cell, gx + gw, gy + j * cell)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1)
    c.line(gx, gy, gx + gw, gy)
    c.line(gx, gy, gx, gy + rows * cell)
    c.setFillColor(T.text2)
    c.setFont("AvD", 7.5)
    for j in range(0, rows + 1, 2 if step < 5 else 1):
        c.drawRightString(gx - 4, gy + j * cell - 2.5, str(j * step))
    c.setFont("AvM", 8.5)
    for i, cat in enumerate(cats):
        c.drawCentredString(gx + 10 + i * (barw + 10) + barw / 2, gy - 11, cat)
    return gy - 16


def c_sgraph(bk, x, cy, w, item):
    """A scaled graph and four questions. item = (type, title, cats, counts, kind, per, qs)."""
    gtype, title, cats, counts, kind, per, qs = item
    gx = x + GUT + 14
    if gtype == "pic":
        scaled_picture_graph(bk, gx, cy + 178, title, cats, counts, kind, per)
    else:
        scaled_bar_graph(bk, gx, cy + 178, title, cats, counts, per)
    graph_questions(bk, x + GUT + 250, cy + 150, w - GUT - 262, qs)


def c_make_sgraph(bk, x, cy, w, item):
    """Counts on the left, an empty scaled bar graph on the right to fill in."""
    title, cats, counts, step = item
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("AvD", 10.5)
    c.drawString(x + GUT, cy + 168, title)
    for i, (cat, n) in enumerate(zip(cats, counts)):
        yy = cy + 138 - i * 26
        c.setFillColor(T.text2)
        c.setFont("AvM", 10.5)
        c.drawString(x + GUT, yy, cat)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 13)
        c.drawString(x + GUT + 80, yy, str(n))
    scaled_bar_graph(bk, x + GUT + 190, cy + 178, f"Make the bar graph (count by {step}s)", cats, counts, step,
                     show=False)


def sgraph_item(gtype, title, cats, counts, kind, per, noun, seed):
    return (gtype, title, cats, counts, kind, per, graph_qs(cats, counts, noun, seed))


def learn_scaled_graphs(bk):
    y = bk.new_page("Scaled Graphs", "One picture or one square can stand for more than 1.", name_line=False,
                    big=True, footer="WeMath  ·  Scaled Graphs")
    c = bk.c
    label(bk, M, y - 6, "Each picture stands for 2")
    scaled_picture_graph(bk, M + 14, y - 14, "Fish we saw", ["Mon", "Tue", "Wed"], [6, 10, 4], "fish", 2)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 290, y - 44, "Monday has 3 fish pictures.")
    color_eq(bk, M + 290, y - 76, [("3", "a"), (TIMES, "op"), ("2", "b"), ("=", "op"), ("6", None), ("fish", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 290, y - 104, "Count by 2s: 2, 4, 6.")
    y -= 158

    label(bk, M, y - 6, "A bar graph that counts by 5s")
    scaled_bar_graph(bk, M + 14, y - 14, "Books read", ["Ana", "Ben", "Kim"], [25, 40, 15], 5, rows=8, cell=12)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 290, y - 44, "Each line is 5 more.")
    c.drawString(M + 290, y - 62, "Ben read 40. Kim read 15.")
    color_eq(bk, M + 290, y - 96, [("15", "a"), ("+", "op"), ("25", "b"), ("=", "op"), ("40", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 290, y - 122, "Ben read 25 more than Kim.")
    y -= 158

    bottom = your_turn(bk, y, h=112)
    bk.ask("scaled graph your turn star 5")
    scaled_picture_graph(bk, M + 130, bottom + 104, "Stars earned", ["Leo"], [20], "star", 5)
    bk.fit_eq(M + 340, bottom + 50, CW - 340 - 16, "Leo has [20] stars", size=16)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: read and draw picture and bar graphs where one picture or square stands for 2, 5 or 10 "
                     "(3.MD.3), and answer how many more or less. Ask “What does one picture stand for?” before "
                     "counting.")


def practice_scaled_graphs(bk):
    title = "Scaled Graphs: Practice"
    y = bk.new_page(title, "Find what one picture or one square stands for. Then count by it.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    key = KINDS_45["sgraph"].key
    part(1, "Each picture stands for 2", "Count by 2s.", [
        sgraph_item("pic", "Apples picked", ["Mia", "Sam", "Zoe", "Max"], [8, 14, 6, 10], "apple", 2, "apples by",
                    "g45a"),
        sgraph_item("pic", "Birds at the feeder", ["Mon", "Tue", "Wed", "Thu"], [12, 4, 16, 10], "bird", 2, "birds on",
                    "g45b"),
    ], 1, 196, 10, c_sgraph, key)
    part(2, "Each picture stands for 5 or 10", "Count by 5s or 10s.", [
        sgraph_item("pic", "Stickers", ["Ava", "Leo", "Kim", "Jay"], [25, 40, 15, 30], "star", 5, "stickers for",
                    "g45c"),
        sgraph_item("pic", "Cupcakes sold", ["Fri", "Sat", "Sun"], [60, 90, 40], "cupcake", 10, "cupcakes on", "g45d"),
    ], 1, 196, 10, c_sgraph, key)
    part(3, "Bar graphs", "Each line is 2 or 5 more.", [
        sgraph_item("bar", "Laps run (by 2s)", ["Ben", "Nia", "Omar", "Lily"], [14, 8, 18, 10], None, 2, "laps by",
                    "g45e"),
        sgraph_item("bar", "Votes for a pet (by 5s)", ["dog", "cat", "fish", "frog"], [35, 25, 10, 20], None, 5,
                    "votes for", "g45f"),
    ], 1, 196, 10, c_sgraph, key)
    part(4, "Make the graph", "Draw each bar to the right line.",
         [("Pages read", ["Ana", "Ravi", "Ella"], [30, 45, 20], 5), ("Shells found", ["Mon", "Tue", "Wed"], [12, 6, 16], 2)],
         1, 186, 10, c_make_sgraph, KINDS_45["make_sgraph"].key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(5, "How many?", "No help this time.",
         [pictures_eq(p, n) for p, n in ((5, 7), (2, 9), (10, 6), (5, 4), (2, 8), (10, 3), (5, 9), (2, 6), (10, 8),
                                         (5, 6))], 2, 42, 8, plain, lambda t: t)
    part(6, "How many pictures?", "No help this time. How many groups?",
         [count_pictures_eq(p, n) for p, n in ((2, 7), (5, 8), (10, 4), (2, 5), (5, 3), (10, 9))], 2, 42, 8, plain,
         lambda t: t)
    part(7, "Remember?", "Problems from earlier packets.", REVIEW_45, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Draw a graph if it helps.")
    for i, story in enumerate(WORDS_45):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


def pictures_eq(per, n):
    return f"each picture = {per}: {n} pictures = [{per * n}]"


def count_pictures_eq(per, n):
    return f"each picture = {per}: [{n}] pictures = {per * n}"


REVIEW_45 = ["9 × 4 = 36 so 9 × 8 = [72]", "500 g + 350 g = [850] g", "6 cm by 5 cm: area = [30] sq cm",
             "15 minutes after 7:50 = [8:05]", f"56 {DIV} 7 = [8]", f"700 {MINUS} 365 = [335]"]

WORDS_45 = [
    ("On a picture graph each star stands for 5. Kim has 6 stars. How many points is that?", f"6 {TIMES} 5 = 30",
     "30", "points"),
    ("Each picture stands for 2 kids. The soccer row has 8 pictures. How many kids like soccer?",
     f"8 {TIMES} 2 = 16", "16", "kids"),
    ("A bar graph counts by 10s. The red bar reaches 70 and the blue bar reaches 40. How many more is red?",
     "40 + 30 = 70", "30", "more"),
    ("Each apple picture stands for 10 apples. A farm picked 90 apples. How many pictures?", f"90 {DIV} 10 = 9", "9",
     "pictures"),
    ("Challenge: Each picture is 5 votes. Pizza has 7 pictures and tacos have 4. How many votes in all?",
     f"7 + 4 = 11, 11 {TIMES} 5 = 55", "55", "votes"),
]

KINDS_45 = {
    "sgraph": Kind(196, 1, lambda it: f"scaled graph {it[0]} {it[1]} " + "-".join(map(str, it[3])), c_sgraph),
    "make_sgraph": Kind(186, 1, lambda it: f"make scaled graph {it[0]} " + "-".join(map(str, it[2])), c_make_sgraph),
}
KINDS.update(KINDS_45)

PICTURE_EQS = [pictures_eq(p, n) for p in (2, 5, 10) for n in rng(3, 9)]

CHECKINS["50-scaled-graphs"] = [
    S("Read the graph", None, "sgraph", [
        sgraph_item("pic", "Kites flown", ["Mon", "Tue", "Wed", "Thu"], [10, 25, 15, 30], "star", 5, "kites on", "c45a"),
        sgraph_item("bar", "Laps swum (by 2s)", ["Ava", "Ben", "Kim", "Max"], [12, 6, 16, 10], None, 2, "laps by",
                    "c45b")], 1),
    S("How many?", None, "eq2", PICTURE_EQS, 4),
    S("How many pictures?", None, "eq2", [count_pictures_eq(p, n) for p in (2, 5, 10) for n in rng(3, 9)], 2),
]
_g3[-1:-1] = [
    S("Scaled graphs", None, "eq2", PICTURE_EQS, 2, 50),
]


# ====================================================================== 51. Measuring to the Quarter Inch

QUARTER = {0: "", 1: "¼", 2: "½", 3: "¾"}


def qstr(q):
    """A length in quarter inches as text: 11 -> '2¾', 8 -> '2'."""
    whole, part_ = divmod(q, 4)
    return (str(whole) if whole or not part_ else "") + QUARTER[part_]


def ruler_q(bk, x, y, n, h=24):
    """An inch ruler from 0 to n with half-inch and quarter-inch marks; its 0 at x; y = bottom. True size."""
    c = bk.c
    fill, line = LENGTH_COLORS["tape"]
    _paint(c, fill, line, 0.9)
    c.rect(x - 6, y, n * INCH + 12, h, stroke=1, fill=1)
    c.setStrokeColor(T.ink)
    for i in range(4 * n + 1):
        tx = x + i * INCH / 4
        k = 1.0 if i % 4 == 0 else 0.62 if i % 2 == 0 else 0.4
        c.setLineWidth(0.9 if i % 4 == 0 else 0.6)
        c.line(tx, y + h, tx, y + h - h * 0.48 * k)
    c.setFillColor(T.ink)
    c.setFont("AvD", 10)
    for i in range(n + 1):
        c.drawCentredString(x + i * INCH, y + 4, str(i))
    c.setFillColor(T.text2)
    c.setFont("Av", 7.5)
    c.drawString(x + n * INCH + 10, y + h / 2 - 3, "in")


def c_quarter(bk, x, cy, w, item):
    """Read a length to the quarter inch. item = (kind, quarters)."""
    kind, q = item
    ruler_q(bk, x + GUT, cy + 10, 6)
    length_object(bk, kind, x + GUT, cy + 48, q * INCH / 4)
    bk.c.setStrokeColor(T.muted)
    bk.c.setLineWidth(0.6)
    bk.c.setDash(2, 2)
    ex = x + GUT + q * INCH / 4
    bk.c.line(ex, cy + 34, ex, cy + 56)
    bk.c.setDash()
    bk.eq(x + GUT, cy + 70, f"[{qstr(q)}] inches", size=15)


def c_measure_q(bk, x, cy, w, item):
    """True size: measure with a real ruler to the nearest quarter inch."""
    kind, q = item
    length_object(bk, kind, x + GUT, cy + 22, q * INCH / 4, h=10)
    bk.eq(x + w - 96, cy + 15, f"[{qstr(q)}] in", size=16)


def c_make_xchart(bk, x, cy, w, item):
    """A list of lengths on the left, an empty X chart on the right to fill in."""
    title, lengths = item
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("AvD", 10.5)
    c.drawString(x + GUT, cy + 148, title)
    for i, q in enumerate(lengths):
        col, row = divmod(i, 4)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 13)
        c.drawString(x + GUT + col * 56, cy + 118 - row * 24, f"{qstr(q)} in")
    labels = sorted(set(lengths))
    lo, hi = min(labels), max(labels)
    span = list(range(lo, hi + 1))
    x_chart(bk, x + GUT + 200, cy + 168, "Make the X chart (inches)", [qstr(q) for q in span],
            [lengths.count(q) for q in span], colw=38, show=False)


def c_read_xchart(bk, x, cy, w, item):
    title, span, counts, qs = item
    x_chart(bk, x + GUT + 10, cy + 168, title, [qstr(q) for q in span], counts, colw=38)
    graph_questions(bk, x + GUT + 250, cy + 140, w - GUT - 262, qs)


def learn_quarter_inch(bk):
    y = bk.new_page("Measuring to the Quarter Inch", "Between the inches: halves and quarters.", name_line=False,
                    big=True, footer="WeMath  ·  Measuring to the Quarter Inch")
    c = bk.c
    label(bk, M, y - 6, "Each inch is cut into 4 quarters")
    ruler_q(bk, M + 14, y - 60, 4, h=30)
    for k, txt in ((1, "¼"), (2, "½"), (3, "¾")):
        c.setFillColor(T.accent)
        c.setFont("AvB", 11)
        c.drawCentredString(M + 14 + INCH + k * INCH / 4, y - 24, "1" + txt)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 40, "Long marks: inches.")
    c.drawString(M + 340, y - 58, "Middle marks: halves.")
    c.drawString(M + 340, y - 76, "Short marks: quarters.")
    y -= 108

    label(bk, M, y - 6, "Line up the end with 0, read the other end")
    ruler_q(bk, M + 14, y - 92, 4, h=26)
    length_object(bk, "crayon", M + 14, y - 50, 11 * INCH / 4, h=14)
    c.setStrokeColor(T.muted)
    c.setLineWidth(0.6)
    c.setDash(2, 2)
    c.line(M + 14 + 11 * INCH / 4, y - 64, M + 14 + 11 * INCH / 4, y - 40)
    c.setDash()
    color_eq(bk, M + 340, y - 60, [("2¾", "b"), ("inches", None)], 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 84, "2 inches and 3 quarters.")
    y -= 122

    label(bk, M, y - 6, "Show many lengths in an X chart")
    x_chart(bk, M + 14, y - 14, "Pencils (inches)", ["4", "4¼", "4½", "4¾", "5"], [1, 3, 2, 0, 1],
            colw=44)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 50, "Each X is one pencil.")
    c.drawString(M + 340, y - 68, "3 pencils are 4¼ inches.")
    y -= 122

    bottom = your_turn(bk, y, h=100)
    bk.ask("quarter inch your turn straw 9")
    ruler_q(bk, M + 120, bottom + 14, 4, h=22)
    length_object(bk, "straw", M + 120, bottom + 50, 9 * INCH / 4)
    bk.eq(M + 450, bottom + 40, "[2¼] in", size=17)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: measure to the nearest half and quarter inch and show the data in an X chart "
                     "(3.MD.4). Use a real ruler too: the measuring part prints true size at 100%. Say “Which "
                     "mark is the end closest to?”")


def practice_quarter_inch(bk):
    title = "Measuring to the Quarter Inch: Practice"
    y = bk.new_page(title, "Line up 0. Read the mark at the other end.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    key = KINDS_46["quarter"].key
    part(1, "Halves", "The end is on an inch or a half inch.",
         [("pencil", 14), ("ribbon", 6), ("crayon", 10), ("straw", 18), ("pencil", 20), ("ribbon", 8)], 1, 92, 8,
         c_quarter, key)
    part(2, "Quarters", "The end can be on a quarter mark.",
         [("crayon", 7), ("pencil", 17), ("straw", 13), ("ribbon", 5), ("pencil", 19), ("crayon", 15)], 1, 92, 8,
         c_quarter, key)
    part(3, "Measure with a real ruler", "These are true size. Print at 100%. Measure to the nearest quarter inch.",
         [("pencil", 15), ("crayon", 9), ("straw", 22), ("ribbon", 11), ("pencil", 18), ("straw", 7)], 1, 40, 6,
         c_measure_q, KINDS_46["measure_q"].key)
    part(4, "Make an X chart", "Put an X above each length.",
         [("Crayons we measured", [12, 13, 13, 14, 12, 13, 15, 14]), ("Worms in the garden", [6, 7, 6, 8, 9, 7, 7, 6])],
         1, 176, 10, c_make_xchart, KINDS_46["make_xchart"].key)
    part(5, "Read the X chart", "Each X is one thing measured.", [
        ("Leaves (inches)", [9, 10, 11, 12, 13], [2, 4, 1, 3, 1],
         [("How many leaves are 2½ in?", 4), ("How many leaves in all?", 11), ("How many are 3 in or more?", 4),
          ("How many more 2½ than 2¾?", 3)]),
        ("Shells (inches)", [4, 5, 6, 7, 8], [1, 3, 5, 2, 1],
         [("How many shells are 1½ in?", 5), ("How many shells in all?", 12), ("How many are 1¼ in?", 3),
          ("How many more 1½ than 1¾?", 3)]),
    ], 1, 186, 10, c_read_xchart, KINDS_46["read_xchart"].key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(6, "Which is longer?", "No help this time.",
         [longer_eq(a, b) for a, b in ((10, 11), (13, 12), (6, 7), (17, 18), (9, 10), (15, 14), (5, 6), (19, 21))], 2,
         42, 8, plain, lambda t: t)
    part(7, "Quarter inches", "No help this time. 1 inch is 4 quarter inches.",
         [f"{qstr(q)} inches = [{q}] quarter inches" for q in (8, 12, 6, 14, 10, 5)], 2, 42, 8, plain, lambda t: t)
    part(8, "Remember?", "Problems from earlier packets.", REVIEW_46, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Draw a ruler if it helps.")
    for i, story in enumerate(WORDS_46):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


def longer_eq(a, b):
    return f"{qstr(a)} in or {qstr(b)} in: longer is [{qstr(max(a, b))}] in"


REVIEW_46 = ["each picture = 5: 8 pictures = [40]", "6 L + 7 L = [13] L", "7 × 3 = 21 so 7 × 6 = [42]",
             "9 cm by 4 cm: perimeter = [26] cm", f"63 {DIV} 7 = [9]", "45 minutes after 1:30 = [2:15]"]

WORDS_46 = [
    ("A worm is 2½ inches long. A caterpillar is 3 inches long. Which is longer?", "3 in > 2½ in", "3",
     "inches"),
    ("Mia's pencil is 5¼ inches. How many quarter inches is that?", "5 inches = 20 quarters, 20 + 1 = 21",
     "21", "quarter inches"),
    ("A ribbon is 1¾ inches long. Is it longer or shorter than 2 inches?", "1¾ in < 2 in", "shorter", ""),
    ("Kim measured 3 leaves: 2¼, 2½ and 2¼ inches. How many were 2¼ inches?", "2¼ twice",
     "2", "leaves"),
    ("Challenge: A crayon is 3½ inches. A marker is 2 inches longer. How long is the marker?",
     "3½ + 2 = 5½", "5½", "inches"),
]

KINDS_46 = {
    "quarter": Kind(92, 1, lambda it: f"quarter inch {it[0]} {it[1]}", c_quarter, 8),
    "measure_q": Kind(40, 1, lambda it: f"measure quarter {it[0]} {it[1]}", c_measure_q, 6),
    "make_xchart": Kind(176, 1, lambda it: f"make x chart {it[0]} " + "-".join(map(str, it[1])), c_make_xchart),
    "read_xchart": Kind(186, 1, lambda it: f"read x chart {it[0]} " + "-".join(map(str, it[2])), c_read_xchart),
}
KINDS.update(KINDS_46)

QUARTER_EQS = [f"{qstr(q)} inches = [{q}] quarter inches" for q in rng(5, 23) if q % 4]

CHECKINS["51-measuring-to-the-quarter-inch"] = [
    S("Read the ruler", None, "quarter", [(k, q) for k in ("pencil", "crayon", "straw", "ribbon") for q in rng(5, 22)
                                         if q % 2], 3),
    S("Which is longer?", None, "eq2", [longer_eq(a, a + d) for a in rng(5, 20) for d in (1, 2) if a % 4], 2),
    S("Quarter inches", None, "eq2", QUARTER_EQS, 2),
]
_g3[-1:-1] = [
    S("Quarter inches", None, "eq2", QUARTER_EQS, 2, 51),
]


# ====================================================================== 52. Shapes and Quadrilaterals

SHAPES = {
    "square": [(-1, -1), (1, -1), (1, 1), (-1, 1)],
    "rectangle": [(-1.5, -0.8), (1.5, -0.8), (1.5, 0.8), (-1.5, 0.8)],
    "rhombus": [(0, -1.25), (0.85, 0), (0, 1.25), (-0.85, 0)],
    "parallelogram": [(-1.4, -0.8), (0.8, -0.8), (1.4, 0.8), (-0.8, 0.8)],
    "trapezoid": [(-1.4, -0.8), (1.4, -0.8), (0.7, 0.8), (-0.7, 0.8)],
    "rtrap": [(-1.2, -0.8), (1.3, -0.8), (0.4, 0.8), (-1.2, 0.8)],
    "kite": [(0, -1.3), (0.8, 0.35), (0, 0.95), (-0.8, 0.35)],
    "quad": [(-1.2, -0.9), (1.1, -0.6), (0.7, 1.0), (-0.9, 0.6)],
    "triangle": [(-1.2, -0.8), (1.2, -0.8), (0, 1.0)],
    "rtri": [(-1.0, -0.9), (1.2, -0.9), (-1.0, 1.0)],
    "pentagon": [(math.cos(math.radians(90 + 72 * i)), math.sin(math.radians(90 + 72 * i))) for i in range(5)],
    "hexagon": [(math.cos(math.radians(60 * i)), math.sin(math.radians(60 * i))) for i in range(6)],
}
SHAPE_NAME = {"square": "square", "rectangle": "rectangle", "rhombus": "rhombus"}


def shape_pts(kind, cx, cy, s, rot=0):
    a = math.radians(rot)
    return [(cx + s * (px * math.cos(a) - py * math.sin(a)), cy + s * (px * math.sin(a) + py * math.cos(a)))
            for px, py in SHAPES[kind]]


def right_angles(pts):
    """Indexes of corners that are right angles."""
    out = []
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[(i + 1) % n]
        ax, ay, bx, by = x0 - x1, y0 - y1, x2 - x1, y2 - y1
        if abs(ax * bx + ay * by) < 1e-6 * (math.hypot(ax, ay) * math.hypot(bx, by) + 1):
            out.append(i)
    return out


def draw_shape(bk, kind, cx, cy, s, rot=0, marks=True):
    """A shape, outlined, with a small square in each right-angle corner and ticks on equal sides of a rhombus or
    square."""
    c = bk.c
    pts = shape_pts(kind, cx, cy, s, rot)
    if T.color:
        c.setFillColor(T.panel)
        c.setStrokeColor(T.dot_a)
        c.setLineWidth(1.6)
        c.drawPath(_poly(c, pts), stroke=1, fill=1)
    else:
        c.setStrokeColor(T.ink)
        c.setLineWidth(1.6)
        c.drawPath(_poly(c, pts), stroke=1, fill=0)
    if not marks:
        return pts
    n = len(pts)
    c.setStrokeColor(T.ink)
    c.setLineWidth(0.8)
    for i in right_angles(pts):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[(i + 1) % n]
        d = 7
        ux, uy = (x0 - x1) / math.hypot(x0 - x1, y0 - y1), (y0 - y1) / math.hypot(x0 - x1, y0 - y1)
        vx, vy = (x2 - x1) / math.hypot(x2 - x1, y2 - y1), (y2 - y1) / math.hypot(x2 - x1, y2 - y1)
        p = c.beginPath()
        p.moveTo(x1 + ux * d, y1 + uy * d)
        p.lineTo(x1 + ux * d + vx * d, y1 + uy * d + vy * d)
        p.lineTo(x1 + vx * d, y1 + vy * d)
        c.drawPath(p, stroke=1, fill=0)
    if n == 4:
        lens = [math.hypot(pts[(i + 1) % 4][0] - pts[i][0], pts[(i + 1) % 4][1] - pts[i][1]) for i in range(4)]
        if max(lens) - min(lens) < 0.01 * max(lens):
            for i in range(4):
                (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 4]
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                L = math.hypot(x1 - x0, y1 - y0)
                nx, ny = -(y1 - y0) / L * 4, (x1 - x0) / L * 4
                c.line(mx - nx, my - ny, mx + nx, my + ny)
    return pts


def c_shape_count(bk, x, cy, w, item):
    kind, rot = item
    n = len(SHAPES[kind])
    draw_shape(bk, kind, x + GUT + 30, cy + 74, 24, rot)
    bk.eq(x + GUT, cy + 30, f"sides [{n}]", size=13)
    bk.eq(x + GUT, cy + 8, f"corners [{n}]", size=13)


def c_is_quad(bk, x, cy, w, item):
    kind, rot = item
    draw_shape(bk, kind, x + GUT + 30, cy + 38, 22, rot)
    yes_no_choice(bk, x, cy, w, len(SHAPES[kind]) == 4)


def c_right_count(bk, x, cy, w, item):
    kind, rot = item
    pts = shape_pts(kind, 0, 0, 1, rot)
    draw_shape(bk, kind, x + GUT + 34, cy + 66, 24, rot)
    bk.eq(x + GUT, cy + 12, f"right angles [{len(right_angles(pts))}]", size=13)


def c_name_quad(bk, x, cy, w, item):
    kind, rot, choices = item
    draw_shape(bk, kind, x + GUT + 36, cy + 50, 24, rot)
    circle_choice(bk, x + GUT + 90, cy + 46, choices, quad_name(kind), size=11.5, gap=14)


def quad_name(kind):
    return SHAPE_NAME.get(kind, "other")


def c_quad_fact(bk, x, cy, w, item):
    text, yes = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 13)
    bk.c.drawString(x + GUT, cy + 26, text)
    yes_no_choice(bk, x, cy, w, yes)


def dot_grid(bk, x, y, cols, rows, step=16):
    for i in range(cols):
        for j in range(rows):
            bk.c.setFillColor(T.muted)
            bk.c.circle(x + i * step, y + j * step, 1.4, stroke=0, fill=1)


def c_draw_quad(bk, x, cy, w, item):
    text, kind = item
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("Rnd", 12.5)
    c.drawString(x + GUT, cy + 128, text)
    dot_grid(bk, x + GUT + 6, cy + 14, 14, 7)
    if bk.key:
        pts = {"rectangle": [(2, 1), (9, 1), (9, 5), (2, 5)], "trapezoid": [(2, 1), (11, 1), (8, 5), (4, 5)],
               "parallelogram": [(2, 1), (9, 1), (11, 5), (4, 5)]}[kind]
        c.setStrokeColor(T.answer)
        c.setLineWidth(1.6)
        c.drawPath(_poly(c, [(x + GUT + 6 + px * 16, cy + 14 + py * 16) for px, py in pts]), stroke=1, fill=0)


def learn_quadrilaterals(bk):
    y = bk.new_page("Shapes and Quadrilaterals", "A quadrilateral has 4 sides and 4 corners.", name_line=False,
                    big=True, footer="WeMath  ·  Shapes and Quadrilaterals")
    c = bk.c
    label(bk, M, y - 6, "These are all quadrilaterals")
    row = [("square", "4 right angles,", "4 equal sides"), ("rectangle", "4 right angles", ""),
           ("rhombus", "4 equal sides", ""), ("trapezoid", "4 sides", "")]
    for i, (kind, a, b) in enumerate(row):
        cx = M + 60 + i * 128
        draw_shape(bk, kind, cx, y - 62, 26 if kind != "square" else 24)
        c.setFillColor(T.ink)
        c.setFont("AvB", 11)
        c.drawCentredString(cx, y - 112, kind)
        c.setFillColor(T.text2)
        c.setFont("Rnd", 10)
        c.drawCentredString(cx, y - 127, a)
        if b:
            c.drawCentredString(cx, y - 140, b)
    y -= 160

    label(bk, M, y - 6, "Not quadrilaterals: count the sides")
    for i, (kind, txt) in enumerate((("triangle", "3 sides"), ("pentagon", "5 sides"), ("hexagon", "6 sides"))):
        cx = M + 60 + i * 128
        draw_shape(bk, kind, cx, y - 54, 26)
        c.setFillColor(T.text2)
        c.setFont("Rnd", 11)
        c.drawCentredString(cx, y - 100, txt)
    y -= 118

    label(bk, M, y - 6, "A square is a rectangle AND a rhombus")
    draw_shape(bk, "square", M + 60, y - 54, 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 110, y - 40, "It has 4 right angles, like a rectangle.")
    c.drawString(M + 110, y - 58, "It has 4 equal sides, like a rhombus.")
    c.drawString(M + 110, y - 76, "The little square in a corner means a right angle.")
    y -= 104

    bottom = your_turn(bk, y, h=96)
    bk.ask("shape count parallelogram your turn")
    draw_shape(bk, "parallelogram", M + 150, bottom + 46, 22)
    bk.eq(M + 230, bottom + 52, "sides [4]", size=15)
    bk.eq(M + 230, bottom + 18, "Quadrilateral? [yes]", size=15)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: shapes share attributes; quadrilaterals have 4 sides and 4 corners; squares, "
                     "rectangles and rhombuses are kinds of quadrilaterals (3.G.1). Ask “How many sides? Any "
                     "right angles? Are the sides equal?”")


def practice_quadrilaterals(bk):
    title = "Shapes and Quadrilaterals: Practice"
    y = bk.new_page(title, "Count the sides. Look for right angles and equal sides.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    part(1, "Sides and corners", "Count them.",
         [("pentagon", 0), ("trapezoid", 0), ("rtri", 0), ("hexagon", 15), ("kite", 0), ("triangle", 20)], 3, 110, 10,
         c_shape_count, KINDS_47["shape_count"].key)
    part(2, "Quadrilateral or not?", "Is it a quadrilateral? A quadrilateral has exactly 4 sides.",
         shuf("q47", [("quad", 0), ("pentagon", 10), ("rhombus", 0), ("triangle", 0), ("parallelogram", 0),
                      ("hexagon", 0), ("kite", 20), ("rtri", 0), ("rtrap", 0)]), 3, 72, 10, c_is_quad,
         KINDS_47["is_quad"].key)
    part(3, "Right angles", "Count the corners with a little square.",
         [("rectangle", 0), ("rtrap", 0), ("rhombus", 20), ("square", 15), ("rtri", 0), ("parallelogram", 0)], 3, 104,
         10, c_right_count, KINDS_47["right_count"].key)
    choices = ["square", "rectangle", "rhombus", "other"]
    part(4, "Name it", "Circle the best name.",
         [("rectangle", 90, choices), ("rhombus", 30, choices), ("trapezoid", 0, choices), ("square", 25, choices),
          ("kite", 0, choices), ("rectangle", 0, choices), ("rhombus", 0, choices), ("quad", 0, choices)], 1, 76, 8,
         c_name_quad, KINDS_47["name_quad"].key)
    part(5, "True or not?", "Think about the sides and corners.", QUAD_FACTS[:6], 1, 60, 8, c_quad_fact,
         KINDS_47["quad_fact"].key)
    part(6, "Draw it", "Use the dots. Use a ruler for straight sides.",
         [("Draw a quadrilateral with 4 right angles that is not a square.", "rectangle"),
          ("Draw a quadrilateral with no right angles.", "parallelogram")], 1, 148, 10, c_draw_quad,
         KINDS_47["draw_quad"].key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(7, "Remember?", "Problems from earlier packets.", REVIEW_47, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Draw the shapes if it helps.")
    for i, story in enumerate(WORDS_47):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


QUAD_FACTS = [("Every square is a rectangle.", True), ("Every rectangle is a square.", False),
              ("A rhombus has 4 equal sides.", True), ("A triangle is a quadrilateral.", False),
              ("Every square is a rhombus.", True), ("A trapezoid has 5 corners.", False),
              ("A rectangle has 4 right angles.", True), ("A pentagon has 4 sides.", False),
              ("A kite is a quadrilateral.", True), ("Every rhombus has 4 right angles.", False)]

REVIEW_47 = ["3¼ inches = [13] quarter inches", "each picture = 10: 4 pictures = [40]", "250 g + 400 g = [650] g",
             "5 × 9 = 45 so 10 × 9 = [90]", "8 m by 3 m: area = [24] sq m", f"603 {MINUS} 275 = [328]"]

WORDS_47 = [
    ("Ana draws 3 squares. How many sides does she draw in all?", f"3 {TIMES} 4 = 12", "12", "sides"),
    ("A shape has 4 sides and 4 right angles. Two sides are long and two are short. What is it?",
     "4 right angles, not all equal", "rectangle", ""),
    ("Ben has 5 triangles and 2 rectangles. How many corners do they have in all?", f"5 {TIMES} 3 = 15, 2 {TIMES} 4 = 8, 15 + 8 = 23",
     "23", "corners"),
    ("A square garden has sides of 6 m. What is its perimeter?", "6 + 6 + 6 + 6 = 24", "24", "m"),
    ("Challenge: A shape has 4 equal sides but no right angles. What is the best name for it?",
     "4 equal sides, no right angles", "rhombus", ""),
]

KINDS_47 = {
    "shape_count": Kind(110, 3, lambda it: f"shape count {it[0]} {it[1]}", c_shape_count),
    "is_quad": Kind(72, 3, lambda it: f"is quadrilateral {it[0]} {it[1]}", c_is_quad),
    "right_count": Kind(104, 3, lambda it: f"right angles {it[0]} {it[1]}", c_right_count),
    "name_quad": Kind(76, 1, lambda it: f"name quad {it[0]} {it[1]}", c_name_quad, 8),
    "quad_fact": Kind(60, 1, lambda it: f"quad fact: {it[0]}", c_quad_fact, 8),
    "draw_quad": Kind(148, 1, lambda it: f"draw quad: {it[0]}", c_draw_quad),
}
KINDS.update(KINDS_47)
BALANCE["is_quad"] = lambda it: len(SHAPES[it[0]]) == 4
BALANCE["quad_fact"] = lambda it: it[1]

CHECKINS["52-shapes-and-quadrilaterals"] = [
    S("Quadrilateral or not?", None, "is_quad", [(k, r) for k in SHAPES for r in (0, 10, 25)], 3),
    S("Right angles", None, "right_count", [(k, r) for k in ("rectangle", "rtrap", "square", "rtri", "rhombus")
                                            for r in (5, 30)], 3),
    S("Name it", None, "name_quad", [(k, r, ["square", "rectangle", "rhombus", "other"])
                                     for k in ("square", "rectangle", "rhombus", "trapezoid", "kite") for r in (10, 40)], 2),
    S("True or not?", None, "quad_fact", QUAD_FACTS, 2),
]
_g3[-1:-1] = [
    S("Quadrilaterals", None, "is_quad", [(k, r) for k in SHAPES for r in (0, 10, 25)], 2, 52),
]


# ====================================================================== 53. Thousands (grade 4 starts)


def nf(n):
    """1000 and up get a comma: 4372 -> '4,372'."""
    return f"{n:,}"


def thousand_cube(bk, x, y, s=40):
    """A thousand: a cube drawn in 3D (front square with a 10 × 10 grid, top and side faces). y = bottom."""
    c = bk.c
    d = s * 0.35
    front = [(x, y), (x + s, y), (x + s, y + s), (x, y + s)]
    top = [(x, y + s), (x + s, y + s), (x + s + d, y + s + d), (x + d, y + s + d)]
    side = [(x + s, y), (x + s + d, y + d), (x + s + d, y + s + d), (x + s, y + s)]
    for pts, col in ((front, T.band), (top, T.panel), (side, T.strip)):
        if T.color:
            c.setFillColor(col)
            c.drawPath(_poly(c, pts), stroke=0, fill=1)
    c.setStrokeColor(T.dot_a if T.color else T.muted)
    c.setLineWidth(0.35)
    for i in range(1, 10):
        c.line(x + i * s / 10, y, x + i * s / 10, y + s)
        c.line(x, y + i * s / 10, x + s, y + i * s / 10)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.1)
    for pts in (front, top, side):
        c.drawPath(_poly(c, pts), stroke=1, fill=0)


def mini_cube(bk, x, y, s=14):
    """The quick-drawing mark for a thousand: a small cube outline. y = bottom."""
    c = bk.c
    d = s * 0.4
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.4)
    c.rect(x, y, s, s, stroke=1, fill=0)
    c.drawPath(_poly(c, [(x, y + s), (x + d, y + s + d), (x + s + d, y + s + d), (x + s, y + s)]), stroke=1, fill=0)
    c.line(x + s, y, x + s + d, y + d)
    c.line(x + s + d, y + d, x + s + d, y + s + d)


def quick_th(bk, x, y, th, h, t, o):
    """Quick drawing: a cube for each thousand, then squares, lines and dots (packet 15). y = bottom. Returns width."""
    cx = x
    for i in range(th):
        mini_cube(bk, cx, y + 14, 16)
        cx += 26
    if th:
        cx += 6
    return cx - x + quick_hto(bk, cx, y, h, t, o, size=13, line_h=32)


def digits4(n):
    return n // 1000, n // 100 % 10, n // 10 % 10, n % 10


def c_quick_th(bk, x, cy, w, n):
    th, h, t, o = digits4(n)
    quick_th(bk, x + GUT, cy + 52, th, h, t, o)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{th}] thousands [{h}] hundreds [{t}] tens [{o}] ones = [{nf(n)}]",
              size=14)


def expanded_parts(n):
    th, h, t, o = digits4(n)
    return [v for v in (th * 1000, h * 100, t * 10, o) if v]


def expanded_eq(n):
    return " + ".join(nf(v) for v in expanded_parts(n)) + f" = [{nf(n)}]"


def expand_eq(n):
    return " + ".join(f"[{nf(v)}]" for v in expanded_parts(n)) + f" = {nf(n)}"


def worth_eq(n, digit_place):
    d = n // digit_place % 10
    return f"in {nf(n)} the {d} is worth [{nf(d * digit_place)}]"


def learn_thousands(bk):
    y = bk.new_page("Thousands", "10 hundreds make a thousand. Each place is worth 10 times the next.",
                    name_line=False, big=True, footer="WeMath  ·  Thousands")
    c = bk.c
    label(bk, M, y - 6, "10 hundreds = 1 thousand")
    for i in range(10):
        hundred_flat(bk, M + 14 + i * 22, y - 52, 18)
    c.setFillColor(T.text2)
    c.setFont("AvD", 22)
    c.drawString(M + 240, y - 46, "=")
    thousand_cube(bk, M + 270, y - 68, 44)
    color_eq(bk, M + 360, y - 46, [("1,000", "a")], 26)
    y -= 100

    label(bk, M, y - 6, "Read a big number: thousands, hundreds, tens, ones")
    quick_th(bk, M + 14, y - 64, 3, 4, 2, 6)
    color_eq(bk, M + 270, y - 42, [("3", "a"), (",", None, "tight"), ("4", "b", "tight"), ("2", None, "tight"),
                                   ("6", None, "tight")], 30)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 270, y - 66, "3,000 + 400 + 20 + 6")
    c.drawString(M + 270, y - 84, "A cube is a thousand, a square is a hundred.")
    y -= 108

    label(bk, M, y - 6, "Each place is 10 times the place to its right")
    vals = [3, 30, 300, 3000]
    for i, v in enumerate(vals):
        cx = M + 40 + i * 110
        color_eq(bk, cx, y - 50, [(nf(v), "a" if i == 3 else None)], 22, anchor="center")
        if i < 3:
            curve_arrow(bk, (cx + 20, y - 30), (cx + 36, y - 16), (cx + 74, y - 16), (cx + 90, y - 30))
            c.setFillColor(T.accent)
            c.setFont("AvB", 11)
            c.drawCentredString(cx + 55, y - 6, f"{TIMES}10")
    y -= 80

    bottom = your_turn(bk, y, h=100)
    bk.ask("quick thousands 2053 your turn")
    quick_th(bk, M + 120, bottom + 40, 2, 0, 5, 3)
    bk.eq(M + 300, bottom + 50, "[2,053]", size=20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 11)
    c.drawString(M + 300, bottom + 20, "No hundreds? A 0 holds the place.")
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: read, write and compare numbers to 9,999 and see that each place is worth 10 times "
                     "the place to its right (4.NBT.1–2). Say “How many thousands? Hundreds? Tens? Ones?” A 0 "
                     "holds an empty place.")


def practice_thousands(bk):
    title = "Thousands: Practice"
    y = bk.new_page(title, "Thousands, hundreds, tens, ones.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(1, "Read the quick drawing", "A cube is 1,000. A square is 100. A line is 10. A dot is 1.",
         [1352, 4207, 2534, 5061, 3340, 1815], 1, 92, 8, c_quick_th, KINDS_48["quick_th"].key)
    part(2, "Put the parts together", "No help this time.",
         [expanded_eq(n) for n in (4372, 6815, 2049, 7530, 9264, 3608, 5197, 8023)], 2, 42, 8, plain, lambda t: t)
    part(3, "Break it into parts", "No help this time. One box for each place.",
         [expand_eq(n) for n in (5283, 7416, 3905, 6052, 8341, 2760)], 2, 42, 8, plain, lambda t: t)
    part(4, "What is the digit worth?", "No help this time.",
         [worth_eq(n, p) for n, p in ((6482, 100), (3715, 1000), (9254, 10), (4839, 100), (7166, 1000), (5378, 10),
                                      (2693, 100), (8521, 1000))], 2, 42, 8, plain, lambda t: t)
    part(5, "Ten times as much", "No help this time.",
         [f"10 {TIMES} {nf(v)} = [{nf(10 * v)}]" for v in (300, 45, 700, 260, 900, 58)], 3, 42, 8, plain, lambda t: t)
    part(6, "Compare", "No help this time. Write <, > or =.",
         compare_big([(4372, 4723), (6018, 6008), (3999, 4001), (7250, 7205), (5555, 5555), (2840, 2804),
                      (8106, 8160), (9031, 9130)]), 2, 42, 8, plain, lambda t: t)
    part(7, "1,000 more and 1,000 less", "No help this time.",
         [f"1,000 more than {nf(n)} = [{nf(n + 1000)}]" for n in (4372, 2915, 6048, 8760)]
         + [f"1,000 less than {nf(n)} = [{nf(n - 1000)}]" for n in (5384, 7206, 3950, 9117)], 2, 42, 8, plain,
         lambda t: t)
    part(8, "Remember?", "Problems from earlier packets.", REVIEW_48, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Think about the places.")
    for i, story in enumerate(WORDS_48):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_48 = ["100 more than 467 = [567]", "Round 845 to the nearest hundred: [800]", "2 × 80 = [160]",
             "each picture = 2: 7 pictures = [14]", f"906 {MINUS} 358 = [548]", "4¼ inches = [17] quarter inches"]

WORDS_48 = [
    ("A school has 3 boxes of 1,000 stickers and 4 packs of 100. How many stickers is that?", "3,000 + 400 = 3,400",
     "3,400", "stickers"),
    ("A town has 4,850 people. Another town has 4,580. Which town has more people?", "4,850 > 4,580", "4,850", ""),
    ("A book has 1,265 pages. Mia's book has 1,000 more. How many pages does Mia's book have?",
     "1,265 + 1,000 = 2,265", "2,265", "pages"),
    ("In 7,309, what is the 3 worth?", "3 hundreds = 300", "300", ""),
    ("Challenge: Use the digits 4, 0, 9 and 2 once each. What is the biggest number you can make?",
     "9 thousands, 4 hundreds, 2 tens, 0 ones", "9,420", ""),
]

KINDS_48 = {
    "quick_th": Kind(92, 1, lambda n: f"quick thousands {n}", c_quick_th, 8),
}
KINDS.update(KINDS_48)

EXPANDED = [expanded_eq(n) for n in rng(1203, 9876, 97)]
def compare_big(pairs):
    return [f"{nf(a)} [{sign_of(a, b)}] {nf(b)}" for a, b in pairs]


COMPARE_4 = compare_big([(a, b) for a in rng(2105, 9850, 389) for b in (a + 90, a - 90, a + 900, a - 9) if b > 999])

CHECKINS["53-thousands"] = [
    S("Read the quick drawing", None, "quick_th", [n for n in rng(1124, 5832, 137) if n % 10], 2),
    S("Put the parts together", None, "eq2", EXPANDED, 2),
    S("What is the digit worth?", None, "eq2", [worth_eq(n, p) for n in rng(2134, 9876, 271) for p in (10, 100, 1000)
                                                if n // p % 10], 2),
    S("Compare", "Write <, > or =.", "eq2", COMPARE_4, 2, balance=is_less),
]


# ====================================================================== 54. Rounding Big Numbers


def learn_round_big(bk):
    y = bk.new_page("Rounding Big Numbers", "Same as before: the one below, the one above. Which is closer?",
                    name_line=False, big=True, footer="WeMath  ·  Rounding Big Numbers")
    c = bk.c
    label(bk, M, y - 6, "Round 4,372 to the nearest thousand")
    between(bk, M + 14, y - 54, 300, 4372, 1000, given=True, size=20, bw=64)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 36, "The thousand below is 4,000.")
    c.drawString(M + 340, y - 54, "The thousand above is 5,000.")
    c.drawString(M + 340, y - 72, "4,372 is closer to 4,000.")
    color_eq(bk, M + 340, y - 104, [("4,372", None), ("rounds to", None), ("4,000", "b")], 18)
    y -= 132

    label(bk, M, y - 6, "Round 4,372 to the nearest hundred")
    between(bk, M + 14, y - 54, 300, 4372, 100, given=True, size=20, bw=64)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 36, "The hundred below is 4,300.")
    c.drawString(M + 340, y - 54, "The hundred above is 4,400.")
    c.drawString(M + 340, y - 72, "4,372 is closer to 4,400.")
    color_eq(bk, M + 340, y - 104, [("4,372", None), ("rounds to", None), ("4,400", "b")], 18)
    y -= 132

    label(bk, M, y - 6, "Exactly in the middle? Round up.")
    color_eq(bk, M + 14, y - 40, [("2,500", None), ("rounds to", None), ("3,000", "b")], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 280, y - 40, "2,500 is right in the middle.")
    y -= 62

    bottom = your_turn(bk, y, h=116)
    bk.ask("round: 6815 to 1000 your turn")
    between(bk, M + 130, bottom + 76, 260, 6815, 1000, size=17, bw=56)
    bk.eq(M + 170, bottom + 24, "6,815 rounds to [7,000]", size=16)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: round numbers to 9,999 to the nearest 10, 100 or 1,000 (4.NBT.3), the founder's way: "
                     "“What is the thousand below? The thousand above? Which is closer?” No counting: kids "
                     "can see which one is closer.")


PLACE_WORD = {10: "ten", 100: "hundred", 1000: "thousand"}


def round_eq(n, p):
    return f"{nf(n)} to the nearest {PLACE_WORD[p]} = [{nf(round_to(n, p))}]"


def practice_round_big(bk):
    title = "Rounding Big Numbers: Practice"
    y = bk.new_page(title, "The one below, the one above. Which one is closer?")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(1, "Between which thousands?", "Write the thousand below and the thousand above.",
         [f"{nf(n)} is between [{nf(n // 1000 * 1000)}] and [{nf(n // 1000 * 1000 + 1000)}]"
          for n in (3604, 7285, 1930, 5472, 8126, 2759, 6341, 4818)], 2, 42, 8, plain, lambda t: t)
    key = KINDS_37["round_card"].key
    part(2, "Which thousand is closer?", "Circle the closer thousand.",
         [(3604, 1000, "closer"), (7285, 1000, "closer"), (1930, 1000, "closer"), (5472, 1000, "closer"),
          (8126, 1000, "closer"), (2759, 1000, "closer")], 2, 84, 10, c_between, key)
    part(3, "Which hundred is closer?", "Circle the closer hundred.",
         [(3648, 100, "closer"), (7215, 100, "closer"), (1983, 100, "closer"), (5427, 100, "closer"),
          (8162, 100, "closer"), (2794, 100, "closer")], 2, 84, 10, c_between, key)
    part(4, "Fill in every box", "Write both, circle the closer one, then round.",
         [(6341, 1000, "boxes"), (4818, 1000, "boxes"), (9473, 100, "boxes"), (2056, 100, "boxes")], 2, 84, 10,
         c_between, key)
    part(5, "Nearest thousand", "No help this time.",
         [round_eq(n, 1000) for n in (2317, 6845, 4502, 8190, 3678, 5049, 7731, 1465, 9206, 2981, 6123, 4567)], 2, 42,
         8, plain, lambda t: t)
    part(6, "Nearest hundred", "No help this time.",
         [round_eq(n, 100) for n in (2317, 6845, 4562, 8190, 3678, 5049, 7731, 1465, 9216, 2981)], 2, 42, 8, plain,
         lambda t: t)
    part(7, "Which place?", "No help this time. Read which one.",
         [f"Round {nf(n)} to the nearest {nf(p)}: [{nf(round_to(n, p))}]"
          for n, p in ((5286, 10), (3741, 1000), (8452, 100), (6097, 10), (2508, 1000), (7364, 100))], 2, 42, 8,
         plain, lambda t: t)
    part(8, "About how much?", "No help this time. Round each number to the nearest thousand, then add or take away.",
         [about_k(a, op, b) for a, op, b in ((3872, "+", 2145), (6204, MINUS, 1893), (4710, "+", 3088),
                                             (8925, MINUS, 4170), (2390, "+", 5612), (7481, MINUS, 2763))], 2, 42, 8,
         plain, lambda t: t)
    part(9, "Remember?", "Problems from earlier packets.", REVIEW_49, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 10, "Word problems", "About how many? Round.")
    for i, story in enumerate(WORDS_49):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 10, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


def about_k(a, op, b):
    ra, rb = round_to(a, 1000), round_to(b, 1000)
    return f"{nf(a)} {op} {nf(b)} is about [{nf(ra + rb if op == '+' else ra - rb)}]"


REVIEW_49 = ["in 5,826 the 8 is worth [800]", "1,000 more than 3,471 = [4,471]", "125 g + 250 g = [375] g",
             "4 bottles of 3 L = [12] L", f"{nf(3000)} + 600 + 40 + 2 = [3,642]", "8 cm by 5 cm: area = [40] sq cm"]

WORDS_49 = [
    ("A stadium has 6,382 seats. About how many is that, to the nearest thousand?", "6,382 rounds to 6,000", "6,000",
     "seats"),
    ("A plane flew 2,749 miles. About how far is that, to the nearest hundred?", "2,749 rounds to 2,700", "2,700",
     "miles"),
    ("A library has 4,500 books. Rounded to the nearest thousand, about how many?", "4,500 rounds to 5,000", "5,000",
     "books"),
    ("A farm has 1,873 chickens and 3,240 ducks. About how many birds, to the nearest thousand?",
     "2,000 + 3,000 = 5,000", "5,000", "birds"),
    ("Challenge: A number rounds to 3,000. It is between 2,000 and 3,000. Is it more than 2,500?",
     "closer to 3,000 means 2,500 or more", "yes", ""),
]

ROUND_K = [round_eq(n, 1000) for n in rng(1102, 9898, 83) if n % 100]

CHECKINS["54-rounding-big-numbers"] = [
    S("Which thousand is closer?", None, "round_card", [(n, 1000, "closer") for n in rng(1150, 9850, 113) if n % 500],
      2),
    S("Nearest thousand", None, "eq2", ROUND_K, 2),
    S("Nearest hundred", None, "eq2", [round_eq(n, 100) for n in rng(1103, 9897, 89) if n % 50], 2),
    S("About how much?", None, "eq2", [about_k(a, "+", b) for a in rng(1210, 5900, 517) for b in rng(1150, 3900, 431)],
      2),
]


# ====================================================================== 55. Adding and Subtracting Big Numbers


def c_big_stack(bk, x, cy, w, item):
    a, b, op, mode = item
    stacked(bk, x + GUT + 20, cy + 12, a, b, op=op, mode=mode, size=18)


def big_eq(a, op, b):
    return f"{nf(a)} {op} {nf(b)} = [{nf(a + b if op == '+' else a - b)}]"


def learn_big_add_sub(bk):
    y = bk.new_page("Adding and Subtracting Big Numbers", "Line up the places. Start with the ones.",
                    name_line=False, big=True, footer="WeMath  ·  Adding and Subtracting Big Numbers")
    c = bk.c
    label(bk, M, y - 6, "Add: carry a new ten, hundred or thousand")
    stacked(bk, M + 40, y - 150, 3486, 2795, op="+", mode="shown", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    for i, line in enumerate(("Ones: 6 + 5 = 11. Write 1, carry 1 ten.", "Tens: 1 + 8 + 9 = 18. Write 8, carry 1.",
                              "Hundreds: 1 + 4 + 7 = 12. Write 2, carry 1.", "Thousands: 1 + 3 + 2 = 6.")):
        c.drawString(M + 260, y - 46 - i * 20, line)
    y -= 178

    label(bk, M, y - 6, "Subtract: break a bigger place when you need to")
    stacked(bk, M + 40, y - 150, 6253, 2718, op=MINUS, mode="shown", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    for i, line in enumerate(("Ones: 3 is less than 8. Break a ten: 13 − 8 = 5.", "Tens: 4 − 1 = 3.",
                              "Hundreds: 2 is less than 7. Break a thousand:", "12 − 7 = 5. Thousands: 5 − 2 = 3.")):
        c.drawString(M + 260, y - 46 - i * 20, line)
    y -= 178

    bottom = your_turn(bk, y, h=150)
    bk.ask("big stack 4518 1367 + your turn")
    stacked(bk, M + 200, bottom + 14, 4518, 1367, op="+", mode="boxes", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: add and subtract numbers to 9,999 in columns (4.NBT.4), the same way as packets 13, 14 "
                     "and 29 with one more place. Say “Line up the places. Start with the ones. Do I need to carry "
                     "or break?”")


def practice_big_add_sub(bk):
    title = "Adding and Subtracting Big Numbers: Practice"
    y = bk.new_page(title, "Line up the places. Start with the ones.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    key = KINDS_50["big_stack"].key
    part(1, "Add with carry boxes", "Write each carried 1 in its box.",
         [(2746, 1538, "+", "boxes"), (4185, 3427, "+", "boxes"), (3659, 2873, "+", "boxes"),
          (5308, 2694, "+", "boxes"), (1874, 6258, "+", "boxes"), (6427, 1586, "+", "boxes")], 2, 120, 10,
         c_big_stack, key)
    part(2, "Subtract with boxes", "Cross out and write the new digit in the box.",
         [(7253, 2618, MINUS, "boxes"), (5420, 1873, MINUS, "boxes"), (8316, 4592, MINUS, "boxes"),
          (6045, 2731, MINUS, "boxes"), (9182, 3475, MINUS, "boxes"), (4731, 2856, MINUS, "boxes")], 2, 120, 10,
         c_big_stack, key)
    part(3, "Add", "No boxes this time. Carry above the digits.",
         [(3758, 2465, "+", "plain"), (1946, 5387, "+", "plain"), (4629, 3854, "+", "plain"), (2587, 6519, "+", "plain")],
         2, 120, 10, c_big_stack, key)
    part(4, "Subtract", "No boxes this time.",
         [(8124, 3567, MINUS, "plain"), (6352, 4178, MINUS, "plain"), (7516, 2839, MINUS, "plain"),
          (9263, 5478, MINUS, "plain")], 2, 120, 10, c_big_stack, key)
    part(5, "Across zeros", "Break the thousand first when the next places are 0.",
         [(5003, 2478, MINUS, "boxes"), (7000, 3624, MINUS, "boxes"), (4006, 1837, MINUS, "boxes"),
          (8000, 5259, MINUS, "boxes")], 2, 120, 10, c_big_stack, key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(6, "Add", "No help this time. Write them in columns on scrap paper if it helps.",
         [big_eq(a, "+", b) for a, b in ((4576, 2849), (3218, 5694), (6735, 1987), (2468, 3759), (5189, 2936),
                                         (1897, 4365), (7342, 1789), (3906, 4597))], 2, 42, 8, plain, lambda t: t)
    part(7, "Subtract", "No help this time.",
         [big_eq(a, MINUS, b) for a, b in ((7425, 2849), (6031, 3785), (9104, 4567), (5280, 1694), (8352, 6478),
                                           (4019, 2563), (7600, 3825), (6243, 1876))], 2, 42, 8, plain, lambda t: t)
    part(8, "Remember?", "Problems from earlier packets.", REVIEW_50, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Draw a bar if it helps.")
    for i, story in enumerate(WORDS_50):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_50 = ["5,628 to the nearest thousand = [6,000]", "in 4,217 the 2 is worth [200]", "450 g + 300 g = [750] g",
             "1,000 less than 6,250 = [5,250]", "each picture = 10: 7 pictures = [70]", "2¾ inches = [11] quarter inches"]

WORDS_50 = [
    ("A school collected 2,478 cans in fall and 3,865 cans in spring. How many cans in all?", "2,478 + 3,865 = 6,343",
     "6,343", "cans"),
    ("A mountain trail is 5,280 feet long. Kim has walked 2,645 feet. How far is left?", "5,280 − 2,645 = 2,635",
     "2,635", "feet"),
    ("A zoo had 4,906 visitors on Saturday and 3,958 on Sunday. How many more came on Saturday?",
     "3,958 + 948 = 4,906", "948", "visitors"),
    ("A truck carries 1,875 pounds. It picks up 2,340 more. How heavy is the load now?", "1,875 + 2,340 = 4,215",
     "4,215", "pounds"),
    ("Challenge: A store had 6,000 pencils. It sold 1,250 on Monday and 2,375 on Tuesday. How many are left?",
     "1,250 + 2,375 = 3,625, 6,000 − 3,625 = 2,375", "2,375", "pencils"),
]

KINDS_50 = {
    "big_stack": Kind(120, 2, lambda it: f"big stack {it[0]} {it[1]} {it[2]} {it[3]}", c_big_stack),
}
KINDS.update(KINDS_50)

BIG_ADD = [big_eq(a, "+", b) for a in rng(1236, 6890, 479) for b in rng(1158, 3870, 367)]
BIG_SUB = [big_eq(a, MINUS, b) for a in rng(5213, 9890, 451) for b in rng(1347, 4980, 389)]

CHECKINS["55-adding-and-subtracting-big-numbers"] = [
    S("Add in columns", None, "big_stack", [(a, b, "+", "plain") for a in rng(1347, 6789, 683) for b in rng(1258, 3790, 421)],
      2),
    S("Subtract in columns", None, "big_stack", [(a, b, MINUS, "plain") for a in rng(5124, 9870, 593)
                                                 for b in rng(1376, 4890, 457)], 2),
    S("Add", None, "eq2", BIG_ADD, 2),
    S("Subtract", None, "eq2", BIG_SUB, 2),
]


# ====================================================================== 56. Multiplying by One Digit


def place_parts(n):
    """23 -> [20, 3]; 146 -> [100, 40, 6] (zeros left out)."""
    s = str(n)
    return [int(d) * 10 ** (len(s) - i - 1) for i, d in enumerate(s) if d != "0"]


def area_model(bk, x, y, w, h, n, f, labels=True, products=False, size=14):
    """The area model for n × f: one rectangle cut into a piece for each place of n (blue, orange, blue…), the place
    values on top, f on the left, and each piece's product inside. labels=False makes the top numbers boxes;
    products=True prints the products (worked example) instead of answer boxes. y = bottom."""
    c = bk.c
    parts = place_parts(n)
    weights = [max(0.32, p / n) for p in parts]
    k = w / sum(weights)
    px = x
    for i, (p, wt) in enumerate(zip(parts, weights)):
        pw = wt * k
        col = T.band if i % 2 == 0 else T.strip
        if T.color:
            c.setFillColor(col)
            c.rect(px, y, pw, h, stroke=0, fill=1)
        c.setStrokeColor(T.ink)
        c.setLineWidth(1.3)
        c.rect(px, y, pw, h, stroke=1, fill=0)
        if labels:
            c.setFillColor(T.ink)
            c.setFont("Rnd", size)
            c.drawCentredString(px + pw / 2, y + h + 6, nf(p))
        else:
            bw = max(30, sw(nf(p), "Rnd", size) + 12)
            bk.box(px + pw / 2 - bw / 2, y + h + 3, bw, size * 1.45, nf(p), size=size * 0.9)
        prod = p * f
        if products:
            c.setFillColor(T.ink)
            c.setFont("Rnd", size)
            c.drawCentredString(px + pw / 2, y + h / 2 - size * 0.36, nf(prod))
        else:
            bw = max(32, sw(nf(prod), "Rnd", size) + 12)
            bk.box(px + pw / 2 - bw / 2, y + h / 2 - size * 0.75, bw, size * 1.5, nf(prod), size=size * 0.9)
        px += pw
    c.setFillColor(T.ink)
    c.setFont("Rnd", size)
    c.drawRightString(x - 6, y + h / 2 - size * 0.36, str(f))


def c_area_mult(bk, x, cy, w, item):
    n, f, mode = item
    parts = place_parts(n)
    bk.fit_eq(x + GUT, cy + 140, w - GUT - 10, f"{n} {TIMES} {f} = [{nf(n * f)}]", size=16)
    area_model(bk, x + GUT + 24, cy + 54, min(380, w - GUT - 60), 40, n, f, labels=mode == "given")
    bk.fit_eq(x + GUT + 24, cy + 16, w - GUT - 34, " + ".join(f"[{nf(p * f)}]" for p in parts) + f" = [{nf(n * f)}]",
              size=15)


def partial_lines(n, f):
    parts = place_parts(n)
    return ([f"{f} {TIMES} {nf(p)} = [{nf(p * f)}]" for p in parts]
            + [" + ".join(f"[{nf(p * f)}]" for p in parts) + f" = [{nf(n * f)}]"])


def c_partial(bk, x, cy, w, item):
    n, f = item
    bk.fit_eq(x + GUT, cy + 100, w - GUT - 10, f"{n} {TIMES} {f}", size=16)
    for i, line in enumerate(partial_lines(n, f)):
        bk.fit_eq(x + GUT + 10, cy + 70 - i * 28, w - GUT - 20, line, size=14)


def mult_eq(n, f):
    return f"{n} {TIMES} {f} = [{nf(n * f)}]"


def learn_mult_one_digit(bk):
    y = bk.new_page("Multiplying by One Digit", "Break the big number into tens and ones. Multiply each part. Add.",
                    name_line=False, big=True, footer="WeMath  ·  Multiplying by One Digit")
    c = bk.c
    label(bk, M, y - 6, "23 × 4: break 23 into 20 and 3")
    area_model(bk, M + 40, y - 92, 300, 52, 23, 4, products=True, size=18)
    color_eq(bk, M + 380, y - 46, [("4", None), (TIMES, "op"), ("20", "a"), ("=", "op"), ("80", "a")], 20)
    color_eq(bk, M + 380, y - 74, [("4", None), (TIMES, "op"), ("3", "b"), ("=", "op"), ("12", "b")], 20)
    color_eq(bk, M + 380, y - 102, [("80", "a"), ("+", "op"), ("12", "b"), ("=", "op"), ("92", None)], 20)
    y -= 136

    label(bk, M, y - 6, "Three digits work the same way: 146 × 3")
    area_model(bk, M + 40, y - 92, 300, 52, 146, 3, products=True, size=17)
    color_eq(bk, M + 380, y - 60, [("300", "a"), ("+", "op"), ("120", "b"), ("+", "op"), ("18", "a"), ("=", "op"),
                                   ("438", None)], 18)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 380, y - 86, "Hundreds, tens and ones.")
    y -= 128

    label(bk, M, y - 6, "No picture? Write the parts in a list")
    for i, line in enumerate(("5 × 30 = 150", "5 × 7 = 35", "150 + 35 = 185")):
        color_eq(bk, M + 40, y - 36 - i * 26, [(line, None)], 18)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 300, y - 50, "37 × 5 = 185")
    c.drawString(M + 300, y - 68, "Tens times 5, ones times 5, then add.")
    y -= 104

    bottom = your_turn(bk, y, h=110)
    bk.ask("area mult 34 2 your turn")
    area_model(bk, M + 140, bottom + 22, 220, 40, 34, 2)
    bk.eq(M + 400, bottom + 36, "[68]", size=18)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: multiply a two- or three-digit number by one digit with the area model, then partial "
                     "products (4.NBT.5). It is packet 39's break-it-apart area with packet 38's tens. Say “Tens "
                     "times 4, ones times 4, then add.”")


def practice_mult_one_digit(bk):
    title = "Multiplying by One Digit: Practice"
    y = bk.new_page(title, "Break it apart. Multiply each part. Add the parts.")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    key = KINDS_51["area_mult"].key
    part(1, "The area model", "The parts are on top. Multiply each part.",
         [(26, 3, "given"), (42, 5, "given"), (17, 6, "given"), (35, 4, "given")], 1, 160, 10, c_area_mult, key)
    part(2, "Split it yourself", "Write the tens and ones on top first.",
         [(48, 2, "split"), (63, 7, "split"), (29, 8, "split"), (54, 6, "split")], 1, 160, 10, c_area_mult, key)
    part(3, "Three digits", "Hundreds, tens and ones.",
         [(213, 4, "given"), (152, 6, "split"), (324, 3, "given"), (241, 5, "split")], 1, 160, 10, c_area_mult, key)
    part(4, "Write the parts", "No picture this time.",
         [(36, 4), (71, 3), (58, 6), (124, 7)], 2, 132, 10, c_partial, KINDS_51["partial"].key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(5, "Two digits", "No help this time.",
         [mult_eq(n, f) for n, f in ((32, 4), (57, 3), (46, 5), (83, 2), (19, 7), (64, 3), (38, 6), (75, 4), (91, 8),
                                     (27, 9), (44, 7), (66, 5))], 3, 42, 8, plain, lambda t: t)
    part(6, "Three digits", "No help this time.",
         [mult_eq(n, f) for n, f in ((214, 3), (132, 4), (305, 6), (421, 5), (163, 2), (247, 3), (512, 7), (138, 4))],
         2, 42, 8, plain, lambda t: t)
    part(7, "Remember?", "Problems from earlier packets.", REVIEW_51, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Draw the area model if it helps.")
    for i, story in enumerate(WORDS_51):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_51 = ["3,846 to the nearest hundred = [3,800]", "2,457 + 1,386 = [3,843]", "in 7,062 the 7 is worth [7,000]",
             "4 × 20 = [80]", "6 L + 9 L = [15] L", f"5,000 {MINUS} 1,246 = [3,754]"]

WORDS_51 = [
    ("A box holds 24 crayons. How many crayons are in 6 boxes?", f"24 {TIMES} 6 = 144", "144", "crayons"),
    ("A bus has 48 seats. How many seats are on 4 buses?", f"48 {TIMES} 4 = 192", "192", "seats"),
    ("Tickets cost $35 each. How much do 4 tickets cost?", f"35 {TIMES} 4 = 140", "$140", ""),
    ("A farmer plants 7 rows of 126 corn plants. How many plants is that?", f"126 {TIMES} 7 = 882", "882", "plants"),
    ("Challenge: A school has 5 classes of 28 kids and 4 classes of 31 kids. How many kids in all?",
     f"28 {TIMES} 5 = 140, 31 {TIMES} 4 = 124, 140 + 124 = 264", "264", "kids"),
]

KINDS_51 = {
    "area_mult": Kind(160, 1, lambda it: f"area mult {it[0]} {it[1]} {it[2]}", c_area_mult),
    "partial": Kind(132, 2, lambda it: f"partial products {it[0]} {it[1]}", c_partial),
}
KINDS.update(KINDS_51)

MULT_2 = [mult_eq(n, f) for n in rng(12, 98) if n % 10 for f in rng(3, 9) if (n + f) % 5 == 0]
MULT_3 = [mult_eq(n, f) for n in rng(112, 487, 29) for f in rng(2, 7)]

CHECKINS["56-multiplying-by-one-digit"] = [
    S("The area model", None, "area_mult", [(n, f, "given") for n in rng(13, 87, 7) if n % 10 for f in rng(3, 8)], 1),
    S("Write the parts", None, "partial", [(n, f) for n in rng(23, 89, 11) for f in rng(3, 8)], 2),
    S("Multiply", None, "eq3", MULT_2, 3),
    S("Three digits", None, "eq2", MULT_3, 2),
]


# ====================================================================== 57. Division with Remainders


def rem_eq(n, d):
    return f"{n} {DIV} {d} = [{n // d}] R [{n % d}]"


def c_share_rem(bk, x, cy, w, item):
    """Share n dots on k plates as evenly as you can; what is left over?"""
    n, k = item
    c = bk.c
    for i in range(n):
        bk.dot(x + GUT + 6 + i * 14, cy + 112, 4.6, "a")
    plate_row(bk, x + GUT, cy + 50, k, n // k, w=54, h=36, gap=12)
    lx = x + GUT + k * 66 + 10
    c.setFillColor(T.text2)
    c.setFont("AvM", 10)
    c.drawString(lx, cy + 76, "left over")
    bk.box(lx, cy + 50, 40, 24, n % k, size=15)
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{n}] {DIV} [{k}] = [{n // k}] R [{n % k}]", size=15)


def c_groups_rem(bk, x, cy, w, item):
    """Circle groups of g; some are left over."""
    n, g = item
    c = bk.c
    step = 16
    for i in range(n):
        bk.dot(x + GUT + 6 + i * step, cy + 56, 5, "a")
    if bk.key:
        c.setStrokeColor(T.answer)
        c.setLineWidth(1.3)
        for j in range(n // g):
            x0 = x + GUT + 6 + j * g * step - 7
            c.roundRect(x0, cy + 46, (g - 1) * step + 14, 20, 9, stroke=1, fill=0)
    c.setFillColor(T.ink)
    c.setFont("Rnd", 13)
    c.drawString(x + GUT, cy + 86, f"Circle groups of {g}.")
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"[{n // g}] groups of {g}, [{n % g}] left over", size=15)


def c_rem_think(bk, x, cy, w, item):
    n, d = item
    q = n // d
    lines = [f"{d} {TIMES} [{q}] = [{d * q}]", f"{n} {MINUS} [{d * q}] = [{n % d}]", f"so {n} {DIV} {d} = [{q}] R [{n % d}]"]
    bk.fit_eq(x + GUT, cy + 100, w - GUT - 10, f"{n} {DIV} {d}: the biggest fact up to {n}", size=13)
    for i, line in enumerate(lines):
        bk.fit_eq(x + GUT + 6, cy + 70 - i * 28, w - GUT - 16, line, size=14)


def learn_remainders(bk):
    y = bk.new_page("Division with Remainders", "Share fairly. What is left over is the remainder.", name_line=False,
                    big=True, footer="WeMath  ·  Division with Remainders")
    c = bk.c
    label(bk, M, y - 6, "14 cookies on 4 plates")
    objects(bk, "cookie", M + 14, y - 22, 14, s=20, step=24, per_row=14)
    for i in range(4):
        px = M + 14 + i * 74
        c.setStrokeColor(T.muted)
        c.setLineWidth(1)
        c.ellipse(px, y - 106, px + 64, y - 64, stroke=1, fill=0)
        for j in range(3):
            icon(bk, "cookie", px + 14 + j * 18, y - 85, 15)
    for j in range(2):
        icon(bk, "cookie", M + 330 + j * 22, y - 85, 17)
    c.setFillColor(T.accent)
    c.setFont("AvB", 11)
    c.drawString(M + 320, y - 112, "2 left over")
    color_eq(bk, M + 14, y - 140, [("14", None), (DIV, "op"), ("4", "a"), ("=", "op"), ("3", "a"), ("R", None),
                                   ("2", "b")], 24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 220, y - 140, "3 on each plate, remainder 2. Check: 4 × 3 + 2 = 14.")
    y -= 166

    label(bk, M, y - 6, "Use a times fact: the biggest one that fits")
    for i, line in enumerate((f"23 {DIV} 5:", f"5 {TIMES} 4 = 20  (5 × 5 = 25 is too big)", f"23 {MINUS} 20 = 3",
                              f"23 {DIV} 5 = 4 R 3")):
        bk.eq(M + 14, y - 34 - i * 22, line, size=15 if i in (0, 3) else 13)
    y -= 122

    label(bk, M, y - 6, "What does the remainder mean?")
    for i, line in enumerate(("14 kids, 4 in each car: 3 cars are full and 2 kids still need a ride, so 4 cars.",
                              "14 cookies shared by 4 friends: each gets 3, and 2 are left.")):
        c.setFillColor(T.text2)
        c.setFont("Rnd", 12)
        c.drawString(M + 14, y - 32 - i * 20, line)
    y -= 70

    bottom = your_turn(bk, y, h=96)
    bk.ask("remainder think 17 3 your turn")
    bk.eq(M + 130, bottom + 56, f"3 {TIMES} [5] = [15]", size=16)
    bk.eq(M + 130, bottom + 22, f"17 {DIV} 3 = [5] R [2]", size=16)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: divide with a remainder and decide what it means in a story (4.OA.3). Share real "
                     "objects first. Say “What is the biggest times fact that fits? What is left?” The remainder "
                     "is always less than the divisor.")


def practice_remainders(bk):
    title = "Division with Remainders: Practice"
    y = bk.new_page(title, "Share fairly. What is left over?")
    num = 1

    def part(n, name, sub, items, cols, h, gap, draw, key):
        nonlocal y, num
        y, num = flow(bk, title, y, n, name, sub, items, num, cols, h, gap,
                      lambda x, cy, w, it: (bk.ask(key(it)), draw(bk, x, cy, w, it)))

    part(1, "Share on plates", "Share the dots on the plates. Write what is left over.",
         [(13, 3), (17, 5), (11, 2), (19, 4), (16, 3), (22, 5)], 1, 128, 10, c_share_rem, KINDS_52["share_rem"].key)
    part(2, "Make groups", "Circle the groups. Count the leftovers.",
         [(14, 4), (17, 3), (23, 5), (13, 2), (20, 6), (19, 4)], 1, 100, 10, c_groups_rem, KINDS_52["groups_rem"].key)
    part(3, "Use a times fact", "Find the biggest fact that fits, then what is left.",
         [(29, 4), (38, 5), (45, 7), (26, 3), (53, 6), (61, 8)], 2, 132, 10, c_rem_think, KINDS_52["rem_think"].key)
    plain = lambda bk_, x, cy, w, t: c_eq(bk_, x, cy, w, t)
    part(4, "Divide", "No help this time.",
         [rem_eq(n, d) for n, d in ((17, 5), (23, 4), (31, 6), (44, 7), (19, 2), (38, 9), (27, 8), (50, 6), (35, 4),
                                    (47, 5), (62, 7), (29, 3))], 3, 42, 8, plain, lambda t: t)
    part(5, "Bigger numbers", "No help this time.",
         [rem_eq(n, d) for n, d in ((73, 8), (58, 9), (66, 7), (85, 9), (79, 8), (52, 6))], 2, 42, 8, plain,
         lambda t: t)
    part(6, "Remember?", "Problems from earlier packets.", REVIEW_52, 2, 42, 8, plain, lambda t: t)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 7, "Word problems", "What does the remainder mean in the story?")
    for i, story in enumerate(WORDS_52):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 7, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_52 = ["43 × 6 = [258]", "7,281 to the nearest thousand = [7,000]", f"6,304 {MINUS} 2,857 = [3,447]",
             "in 3,519 the 5 is worth [500]", "each picture = 10: 9 pictures = [90]", "7 m by 4 m: perimeter = [22] m"]

WORDS_52 = [
    ("26 kids go on a trip. Each van holds 6 kids. How many vans do they need?", f"26 {DIV} 6 = 4 R 2, so 5 vans",
     "5", "vans"),
    ("Mia shares 30 stickers equally with 4 friends. How many stickers does each friend get?",
     f"30 {DIV} 4 = 7 R 2, 7 each", "7", "stickers"),
    ("Ben puts 45 eggs in cartons of 12. How many eggs are left over?", f"45 {DIV} 12 = 3 R 9", "9", "eggs"),
    ("A ribbon is 50 inches long. Kim cuts pieces 8 inches long. How many whole pieces can she cut?",
     f"50 {DIV} 8 = 6 R 2, 6 pieces", "6", "pieces"),
    ("Challenge: 58 books go on shelves that hold 9 each. How many shelves are full, and how many books are left?",
     f"58 {DIV} 9 = 6 R 4", "6 R 4", ""),
]

KINDS_52 = {
    "share_rem": Kind(128, 1, lambda it: f"share remainder {it[0]} {it[1]}", c_share_rem),
    "groups_rem": Kind(100, 1, lambda it: f"groups remainder {it[0]} {it[1]}", c_groups_rem),
    "rem_think": Kind(132, 2, lambda it: f"remainder think {it[0]} {it[1]}", c_rem_think),
}
KINDS.update(KINDS_52)

REM_EQS = [rem_eq(n, d) for d in rng(3, 9) for n in rng(d * 3 + 1, d * 9 + d - 1) if n % d]

CHECKINS["57-division-with-remainders"] = [
    S("Make groups", None, "groups_rem", [(n, g) for g in rng(3, 5) for n in rng(g * 3 + 1, 22) if n % g], 1),
    S("Use a times fact", None, "rem_think", [(n, d) for d in rng(3, 9) for n in rng(d * 4 + 1, d * 8) if n % d], 2),
    S("Divide", None, "eq3", REM_EQS, 6),
]


# ---------------------------------------------------------------------- grade 4 assessments (packets 48-52)


def stories_rem(seed, pairs):
    """Division stories with a remainder to interpret (grade 4)."""
    r = random.Random(seed)
    out = []
    for n, d in pairs:
        name, t = r.choice(NAMES), r.choice(THINGS)
        out.append((f"{name} puts {n} {t} into bags of {d}. How many {t} are left over?",
                    f"{n} {DIV} {d} = {n // d} R {n % d}", n % d, t))
    r.shuffle(out)
    return out


GRADES.append(("grade-4", "Grade 4", "Packets 53–70", [
    S("Read big numbers", None, "eq2", EXPANDED, 3, 53),
    S("Compare", "Write <, > or =.", "eq2", COMPARE_4, 3, 53, balance=is_less),
    S("Round", None, "eq2", ROUND_K, 4, 54),
    S("Add", None, "eq2", BIG_ADD, 3, 55),
    S("Subtract", None, "eq2", BIG_SUB, 3, 55),
    S("Multiply", None, "eq3", MULT_2, 6, 56),
    S("Multiply three digits", None, "eq2", MULT_3, 2, 56),
    S("Divide", None, "eq3", REM_EQS, 6, 57),
    S("Word problems", None, "word", stories_x("g4a", "times", [(g, k) for g in rng(3, 8) for k in rng(13, 48, 7)])[:6]
      + stories_rem("g4b", [(n, d) for d in rng(3, 9) for n in rng(d * 3 + 1, d * 9) if n % d])[:6], 4, "56–57"),
]))


# ====================================================================== 58. Multiplying Two-Digit Numbers


def area_model2(bk, x, y, w, h, a, b, labels=True, products=False, size=14):
    """The area model for a × b (both two-digit): a's tens and ones across the top, b's down the left, one piece
    for each pair with its product inside. labels=False makes the outside numbers boxes; products=True prints the
    products (worked example). y = bottom."""
    c = bk.c
    cols, rows = place_parts(a), place_parts(b)
    cw = [max(0.3, p / a) for p in cols]
    rh = [max(0.38, p / b) for p in rows]
    kx, ky = w / sum(cw), h / sum(rh)
    yy = y + h
    for j, (q, rw) in enumerate(zip(rows, rh)):
        ph = rw * ky
        yy -= ph
        xx = x
        for i, (p, cwt) in enumerate(zip(cols, cw)):
            pw = cwt * kx
            if T.color:
                c.setFillColor(T.band if (i + j) % 2 == 0 else T.strip)
                c.rect(xx, yy, pw, ph, stroke=0, fill=1)
            c.setStrokeColor(T.ink)
            c.setLineWidth(1.3)
            c.rect(xx, yy, pw, ph, stroke=1, fill=0)
            prod = nf(p * q)
            if products:
                c.setFillColor(T.ink)
                c.setFont("Rnd", size)
                c.drawCentredString(xx + pw / 2, yy + ph / 2 - size * 0.36, prod)
            else:
                bw = max(34, sw(prod, "Rnd", size) + 12)
                bk.box(xx + pw / 2 - bw / 2, yy + ph / 2 - size * 0.75, bw, size * 1.5, prod, size=size * 0.9)
            if j == 0:
                if labels:
                    c.setFillColor(T.ink)
                    c.setFont("Rnd", size)
                    c.drawCentredString(xx + pw / 2, y + h + 6, str(p))
                else:
                    bk.box(xx + pw / 2 - 18, y + h + 4, 36, size * 1.45, p, size=size * 0.9)
            xx += pw
        if labels:
            c.setFillColor(T.ink)
            c.setFont("Rnd", size)
            c.drawRightString(x - 6, yy + ph / 2 - size * 0.36, str(q))
        else:
            bk.box(x - 44, yy + ph / 2 - size * 0.72, 36, size * 1.45, q, size=size * 0.9)


def parts2(a, b):
    return [p * q for q in place_parts(b) for p in place_parts(a)]


def c_area2(bk, x, cy, w, item):
    a, b, mode = item
    bk.fit_eq(x + GUT, cy + 168, w - GUT - 10, f"{a} {TIMES} {b} = [{nf(a * b)}]", size=16)
    area_model2(bk, x + GUT + 50, cy + 52, min(330, w - GUT - 70), 82, a, b, labels=mode == "given")
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, " + ".join(f"[{nf(p)}]" for p in parts2(a, b)) + f" = [{nf(a * b)}]",
              size=15)


def partial_lines2(a, b):
    lines = [f"{p} {TIMES} {q} = [{nf(p * q)}]" for q in place_parts(b) for p in place_parts(a)]
    return lines + [" + ".join(f"[{nf(p)}]" for p in parts2(a, b)) + f" = [{nf(a * b)}]"]


def c_partial2(bk, x, cy, w, item):
    a, b = item
    bk.fit_eq(x + GUT, cy + 156, w - GUT - 10, f"{a} {TIMES} {b}", size=16)
    for i, line in enumerate(partial_lines2(a, b)):
        bk.fit_eq(x + GUT + 10, cy + 124 - i * 27, w - GUT - 20, line, size=14)


def learn_mult_two_digit(bk):
    y = bk.new_page("Multiplying Two-Digit Numbers", "Break both numbers into tens and ones. Four pieces, then add.",
                    name_line=False, big=True, footer="WeMath  ·  Multiplying Two-Digit Numbers")
    c = bk.c
    label(bk, M, y - 6, "Tens times tens")
    color_eq(bk, M + 14, y - 42, [("20", "a"), (TIMES, "op"), ("30", "b"), ("=", "op"), ("600", None)], 22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 220, y - 30, "2 tens × 3 tens: 2 × 3 = 6,")
    c.drawString(M + 220, y - 46, "and tens times tens are hundreds.")
    y -= 66

    label(bk, M, y - 6, "23 × 14: four pieces")
    area_model2(bk, M + 44, y - 128, 270, 96, 23, 14, products=True, size=17)
    for i, line in enumerate(("10 × 20 = 200", "10 × 3 = 30", "4 × 20 = 80", "4 × 3 = 12")):
        color_eq(bk, M + 350, y - 40 - i * 24, [(line, None)], 16)
    color_eq(bk, M + 350, y - 140, [("200 + 30 + 80 + 12 = 322", None)], 15)
    y -= 168

    label(bk, M, y - 6, "No picture? List the four parts")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 30, "Tens × tens, tens × ones, ones × tens, ones × ones. Then add.")
    color_eq(bk, M + 14, y - 60, [("31 × 26 = 600 + 20 + 180 + 6 = 806", None)], 17)
    y -= 84

    bottom = your_turn(bk, y, h=148)
    bk.ask("area model two digits: 12 x 13 your turn")
    area_model2(bk, M + 160, bottom + 22, 190, 84, 12, 13)
    bk.eq(M + 380, bottom + 60, "12 × 13 = [156]", size=17)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: two-digit × two-digit with the area model, then partial products (4.NBT.5). It is "
                     "packet 56's model with both numbers split. Say “Tens times tens first: those are hundreds.”")


def practice_mult_two_digit(bk):
    title = "Multiplying Two-Digit Numbers: Practice"
    y = bk.new_page(title, "Split both numbers. Four pieces. Add them.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Tens times tens", "2 tens × 3 tens = 6 hundreds.", "eq3",
         [f"{a} {TIMES} {b} = [{nf(a * b)}]" for a, b in ((30, 40), (20, 70), (50, 60), (80, 30), (40, 90), (60, 20),
                                                          (70, 70), (20, 50), (90, 30), (40, 40), (60, 80), (30, 50))])
    part(2, "The area model", "The tens and ones are on the outside. Fill in each piece.", "area2",
         [(24, 13, "given"), (32, 21, "given"), (15, 42, "given"), (43, 26, "given")])
    part(3, "Split them yourself", "Write the tens and ones on the outside first.", "area2",
         [(36, 12, "split"), (27, 31, "split"), (52, 18, "split"), (41, 35, "split")])
    part(4, "Write the four parts", "No picture this time.", "partial2",
         [(34, 21), (16, 45), (53, 32), (28, 17)])
    part(5, "Times a tens number", "No help this time.", "eq3",
         [f"{a} {TIMES} {b} = [{nf(a * b)}]" for a, b in ((34, 20), (17, 30), (46, 40), (23, 60), (58, 20),
                                                          (19, 50), (62, 30), (35, 40), (71, 20))])
    part(6, "Two digits times two digits", "No help this time.", "eq3",
         [f"{a} {TIMES} {b} = [{nf(a * b)}]" for a, b in ((23, 15), (41, 12), (36, 24), (52, 13), (18, 27), (64, 11),
                                                          (33, 32), (47, 21), (26, 35), (72, 14), (15, 19), (38, 43),
                                                          (54, 26), (29, 31), (61, 47))])
    part(7, "Estimate, then multiply", "No help this time. Round each number to the nearest ten first.", "eq2",
         [f"{a} {TIMES} {b} is about [{nf(round_to(a, 10) * round_to(b, 10))}]" for a, b in
          ((38, 21), (49, 32), (61, 19), (27, 42), (52, 48), (73, 29))])
    part(8, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_58)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Draw the area model if it helps.")
    for i, story in enumerate(WORDS_58):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_58 = ["136 × 4 = [544]", f"47 {DIV} 6 = [7] R [5]", "6,284 to the nearest thousand = [6,000]",
             "3/4 of 24 = [18]", "3,508 + 2,694 = [6,202]", "7/10 [>] 3/10"]

WORDS_58 = [
    ("A theater has 24 rows with 18 seats in each row. How many seats are there?", f"24 {TIMES} 18 = 432", "432",
     "seats"),
    ("A baker makes 36 trays of muffins. Each tray holds 12 muffins. How many muffins is that?",
     f"36 {TIMES} 12 = 432", "432", "muffins"),
    ("A book has 15 chapters of 23 pages each. How many pages does it have?", f"15 {TIMES} 23 = 345", "345", "pages"),
    ("Each of 27 kids reads 30 minutes. How many minutes do they read in all?", f"27 {TIMES} 30 = 810", "810",
     "minutes"),
    ("Challenge: 12 boxes of 24 pens and 15 boxes of 20 pencils. How many more pencils than pens?",
     f"15 {TIMES} 20 = 300, 12 {TIMES} 24 = 288, 300 {MINUS} 288 = 12", "12", "more pencils"),
]

KINDS_58 = {
    "area2": Kind(190, 1, lambda it: f"area model two digits: {it[0]} x {it[1]} ({it[2]})", c_area2, 10),
    "partial2": Kind(176, 2, lambda it: f"four parts: {it[0]} x {it[1]}", c_partial2, 10),
}
KINDS.update(KINDS_58)

MULT_22 = [f"{a} {TIMES} {b} = [{nf(a * b)}]" for a in rng(12, 89, 7) for b in rng(11, 49, 5) if a % 10 and b % 10]
TENS_TENS = [f"{a} {TIMES} {b} = [{nf(a * b)}]" for a in rng(20, 90, 10) for b in rng(20, 90, 10)]

CHECKINS["58-multiplying-two-digit-numbers"] = [
    S("The area model", None, "area2", [(a, b, "given") for a in rng(13, 47, 6) for b in rng(12, 36, 5)
                                        if a % 10 and b % 10], 1),
    S("Tens times tens", None, "eq3", TENS_TENS, 3),
    S("Multiply", None, "eq3", MULT_22, 6),
]
_g4 = next(g for g in GRADES if g[0] == "grade-4")[3]
_g4[-1:-1] = [
    S("Two digits times two digits", None, "eq3", MULT_22, 3, 58),
]


# ====================================================================== 59. Dividing Bigger Numbers


def div_area(bk, x, y, w, h, d, chunks, given=True, size=14):
    """Division as an area model: the side d on the left, the total split into chunks (each a multiple of d) inside,
    and the other side of each piece (chunk ÷ d) in a box on top. given=False leaves the chunks as boxes too."""
    c = bk.c
    total = sum(chunks)
    wts = [max(0.22, ch / total) for ch in chunks]
    k = w / sum(wts)
    px = x
    for i, (ch, wt) in enumerate(zip(chunks, wts)):
        pw = wt * k
        if T.color:
            c.setFillColor(T.band if i % 2 == 0 else T.strip)
            c.rect(px, y, pw, h, stroke=0, fill=1)
        c.setStrokeColor(T.ink)
        c.setLineWidth(1.3)
        c.rect(px, y, pw, h, stroke=1, fill=0)
        if given:
            c.setFillColor(T.ink)
            c.setFont("Rnd", size)
            c.drawCentredString(px + pw / 2, y + h / 2 - size * 0.36, nf(ch))
        else:
            bw = max(36, sw(nf(ch), "Rnd", size) + 12)
            bk.box(px + pw / 2 - bw / 2, y + h / 2 - size * 0.75, bw, size * 1.5, nf(ch), size=size * 0.9)
        q = nf(ch // d)
        bw = max(34, sw(q, "Rnd", size) + 12)
        bk.box(px + pw / 2 - bw / 2, y + h + 4, bw, size * 1.45, q, size=size * 0.9)
        px += pw
    c.setFillColor(T.ink)
    c.setFont("Rnd", size)
    c.drawRightString(x - 6, y + h / 2 - size * 0.36, str(d))


def c_div_area(bk, x, cy, w, item):
    n, d, chunks, mode = item
    bk.fit_eq(x + GUT, cy + 140, w - GUT - 10, f"{nf(n)} {DIV} {d} = [{nf(n // d)}]", size=16)
    div_area(bk, x + GUT + 30, cy + 52, min(340, w - GUT - 60), 40, d, chunks, given=mode == "given")
    bk.fit_eq(x + GUT + 30, cy + 14, w - GUT - 40,
              " + ".join(f"[{nf(ch // d)}]" for ch in chunks) + f" = [{nf(n // d)}]", size=15)


def c_partial_q(bk, x, cy, w, item):
    """Partial quotients: n is split into chunks; divide each, then add."""
    n, d, chunks = item
    bk.fit_eq(x + GUT, cy + 128, w - GUT - 10, f"{nf(n)} = " + " + ".join(nf(ch) for ch in chunks), size=15)
    for i, ch in enumerate(chunks):
        bk.fit_eq(x + GUT + 10, cy + 96 - i * 28, w - GUT - 20, f"{nf(ch)} {DIV} {d} = [{nf(ch // d)}]", size=14)
    bk.fit_eq(x + GUT + 10, cy + 96 - len(chunks) * 28, w - GUT - 20,
              " + ".join(f"[{nf(ch // d)}]" for ch in chunks) + f" = [{nf(n // d)}]", size=14)


def div_eq(n, d):
    return f"{nf(n)} {DIV} {d} = [{nf(n // d)}]"


def learn_dividing_big(bk):
    y = bk.new_page("Dividing Bigger Numbers", "Split the big number into parts you can divide. Then add.",
                    name_line=False, big=True, footer="WeMath  ·  Dividing Bigger Numbers")
    c = bk.c
    label(bk, M, y - 6, "84 ÷ 4: split 84 into 80 and 4")
    div_area(bk, M + 40, y - 90, 260, 46, 4, [80, 4], size=18)
    for i, (line, kind) in enumerate((("80 ÷ 4 = 20", "a"), ("4 ÷ 4 = 1", "b"), ("20 + 1 = 21", None))):
        color_eq(bk, M + 340, y - 40 - i * 26, [(line, kind)], 18)
    y -= 124

    label(bk, M, y - 6, "Pick parts that divide easily: 96 ÷ 4")
    div_area(bk, M + 40, y - 90, 260, 46, 4, [80, 16], size=18)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 36, "80 is 4 × 20, and 16 is 4 × 4.")
    color_eq(bk, M + 340, y - 66, [("20 + 4 = 24", None)], 18)
    y -= 124

    label(bk, M, y - 6, "Big numbers: 3,648 ÷ 3")
    color_eq(bk, M + 14, y - 40, [("3,000 ÷ 3 = 1,000", "a")], 16)
    color_eq(bk, M + 14, y - 64, [("600 ÷ 3 = 200", "b")], 16)
    color_eq(bk, M + 14, y - 88, [("48 ÷ 3 = 16", "a")], 16)
    color_eq(bk, M + 270, y - 64, [("1,000 + 200 + 16 = 1,216", None)], 16)
    y -= 112

    bottom = your_turn(bk, y, h=118)
    bk.ask("divide with the area model: 72 / 3 your turn")
    div_area(bk, M + 160, bottom + 30, 200, 40, 3, [60, 12])
    bk.eq(M + 390, bottom + 44, "72 ÷ 3 = [24]", size=17)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: divide up to four digits by one digit (4.NBT.6) by splitting the number into parts that "
                     "divide easily. Say “What part can you share easily? Tens first. Then what's left.”")


def practice_dividing_big(bk):
    title = "Dividing Bigger Numbers: Practice"
    y = bk.new_page(title, "Split the number into easy parts. Divide each one. Add.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Divide tens and hundreds", "Use a fact you know: 12 ÷ 3 = 4, so 120 ÷ 3 = 40.", "eq3",
         [div_eq(n, d) for n, d in ((80, 4), (150, 3), (240, 6), (90, 3), (350, 7), (480, 8), (60, 2), (2400, 6),
                                    (560, 8), (3600, 9), (200, 5), (1800, 2))])
    part(2, "The area model", "The parts are inside. Find the side of each piece.", "div_area",
         [(63, 3, (60, 3), "given"), (85, 5, (50, 35), "given"), (78, 6, (60, 18), "given"),
          (936, 4, (800, 120, 16), "given"), (92, 4, (80, 12), "given")])
    part(3, "Split it yourself", "Write the parts inside first.", "div_area",
         [(48, 2, (40, 8), "split"), (75, 3, (60, 15), "split"), (96, 8, (80, 16), "split"),
          (655, 5, (500, 150, 5), "split")])
    part(4, "Divide each part", "No picture this time.", "partial_q",
         [(84, 7, (70, 14)), (138, 6, (120, 18)), (464, 4, (400, 64)), (2856, 4, (2800, 56))])
    part(5, "Two digits", "No help this time.", "eq3",
         [div_eq(n, d) for n, d in ((52, 4), (87, 3), (72, 6), (95, 5), (68, 2), (91, 7), (64, 4), (84, 6),
                                    (98, 7), (76, 2), (57, 3), (96, 6))])
    part(6, "Three digits", "No help this time.", "eq3",
         [div_eq(n, d) for n, d in ((636, 6), (248, 2), (455, 5), (372, 3), (816, 8), (595, 7), (432, 4), (738, 9),
                                    (264, 2))])
    part(7, "Four digits", "No help this time.", "eq2",
         [div_eq(n, d) for n, d in ((4826, 2), (3696, 3), (5025, 5), (8448, 4), (7266, 6), (2835, 7))])
    part(8, "With a remainder", "No help this time. What is left over?", "eq3",
         [rem_eq(n, d) for n, d in ((97, 4), (85, 6), (79, 3), (127, 5), (98, 8), (157, 7), (203, 4), (89, 2),
                                    (311, 6))])
    part(9, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_59)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 10, "Word problems", "Share it, or make groups.")
    for i, story in enumerate(WORDS_59):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 10, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_59 = ["26 × 14 = [364]", "40 × 70 = [2,800]", "5,729 to the nearest hundred = [5,700]",
             "2/5 of 30 = [12]", f"6,000 {MINUS} 2,385 = [3,615]", "14/4 = 3 wholes and [2]/4"]

WORDS_59 = [
    ("96 stickers are shared equally by 4 friends. How many stickers does each friend get?", f"96 {DIV} 4 = 24",
     "24", "stickers"),
    ("A farmer packs 252 eggs into cartons of 6. How many cartons does she fill?", f"252 {DIV} 6 = 42", "42",
     "cartons"),
    ("A school has 1,575 books to put on 5 shelves equally. How many books go on each shelf?",
     f"1,575 {DIV} 5 = 315", "315", "books"),
    ("98 kids ride in vans that hold 8 kids each. How many vans are full? How many kids are left?",
     f"98 {DIV} 8 = 12 R 2", "12 R 2", ""),
    ("Challenge: 135 kids go on a trip. Each van holds 8 kids. How many vans do they need for everyone?",
     f"135 {DIV} 8 = 16 R 7, so 17 vans", "17", "vans"),
]

KINDS_59 = {
    "div_area": Kind(162, 1, lambda it: f"divide with the area model: {it[0]} / {it[1]} ({it[3]})", c_div_area, 10),
    "partial_q": Kind(152, 2, lambda it: f"divide each part: {it[0]} / {it[1]}", c_partial_q, 10),
}
KINDS.update(KINDS_59)

DIV_2 = [div_eq(d * q, d) for d in rng(2, 9) for q in rng(11, 49) if d * q < 100 and (d + q) % 3 == 0]
DIV_3 = [div_eq(d * q, d) for d in rng(2, 9) for q in rng(102, 489, 13) if d * q < 1000]
DIV_4 = [div_eq(d * q, d) for d in rng(2, 9) for q in rng(1013, 4489, 263) if 1000 <= d * q < 10000]
REM_BIG = [rem_eq(n, d) for d in rng(3, 9) for n in rng(61, 499, 37) if n % d]

CHECKINS["59-dividing-bigger-numbers"] = [
    S("The area model", None, "div_area", [(d * (t + o), d, (d * t, d * o), "given") for d in rng(3, 7)
                                           for t in (10, 20) for o in rng(2, 6)], 1),
    S("Two and three digits", None, "eq3", DIV_2 + DIV_3, 3),
    S("Four digits", None, "eq2", DIV_4, 2),
    S("With a remainder", None, "eq3", REM_BIG, 3),
]
_g4[-1:-1] = [
    S("Divide bigger numbers", None, "eq3", DIV_2 + DIV_3, 3, 59),
]


# ====================================================================== 60. Factors and Multiples


def factors(n):
    return [d for d in range(1, n + 1) if n % d == 0]


def is_prime(n):
    return n > 1 and len(factors(n)) == 2


def c_factor_array(bk, x, cy, w, item):
    """An array of dots: rows × columns is one factor pair."""
    r, k = item
    step = min(13, 120 / max(k, 1))
    rad = min(4.2, step * 0.34)
    for i in range(r):
        for j in range(k):
            bk.dot(x + GUT + rad + j * step, cy + 64 - rad - i * step * 0.95, rad, "a" if i % 2 == 0 else "b")
    bk.fit_eq(x + GUT + 190, cy + 28, w - GUT - 200, f"{r} {TIMES} [{k}] = {r * k}", size=18)


def c_yes_text(bk, x, cy, w, item):
    """A yes/no question in words. The key rings the answer."""
    text, yes = item
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 14)
    bk.c.drawString(x + GUT, cy + 26, text)
    yes_no_choice(bk, x, cy - 2, w, yes)


def c_prime(bk, x, cy, w, n):
    bk.c.setFillColor(T.ink)
    bk.c.setFont("Rnd", 20)
    bk.c.drawString(x + GUT, cy + 15, str(n))
    circle_choice(bk, x + GUT + 44, cy + 17, ["prime", "composite"], "prime" if is_prime(n) else "composite",
                  size=12, gap=14)


def factor_pairs_eq(n):
    pairs = [(d, n // d) for d in factors(n) if d * d <= n]
    return f"{n} = " + " and ".join(f"{a} {TIMES} [{b}]" for a, b in pairs)


def learn_factors(bk):
    y = bk.new_page("Factors and Multiples", "Factors make the number. Multiples come from counting by it.",
                    name_line=False, big=True, footer="WeMath  ·  Factors and Multiples")
    c = bk.c
    label(bk, M, y - 6, "Every rectangle for 12")
    xx = M + 14
    for r, k in ((1, 12), (2, 6), (3, 4)):
        array_picture(bk, xx, y - 22, r, k, step=11, r=3.6)
        c.setFillColor(T.text2)
        c.setFont("Rnd", 12)
        c.drawString(xx, y - 74, f"{r} × {k}")
        xx += k * 11 + 26
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 96, "Factor pairs of 12: 1 and 12, 2 and 6, 3 and 4.")
    color_eq(bk, M + 14, y - 124, [("Factors of 12:", None), ("1, 2, 3, 4, 6, 12", "a")], 17)
    y -= 150

    label(bk, M, y - 6, "Multiples: count by the number")
    color_eq(bk, M + 14, y - 40, [("Multiples of 4:", None), ("4, 8, 12, 16, 20, …", "b")], 17)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 64, "12 is a multiple of 4, and 4 is a factor of 12.")
    y -= 88

    label(bk, M, y - 6, "Prime or composite?")
    array_picture(bk, M + 14, y - 22, 1, 7, step=13, r=4)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 120, y - 30, "7 has only one rectangle: 1 × 7. It is prime.")
    array_picture(bk, M + 14, y - 50, 2, 4, step=13, r=4)
    c.setFillColor(T.text2)
    c.drawString(M + 120, y - 62, "8 has more: 2 × 4 and 1 × 8. It is composite.")
    y -= 96

    bottom = your_turn(bk, y, h=84)
    bk.ask("factor pairs of 15 your turn")
    bk.eq(M + 130, bottom + 34, "15 = 1 × [15] and 3 × [5]", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: factor pairs, multiples, prime and composite for numbers to 100 (4.OA.4). Say “Can you "
                     "make a rectangle with this many dots? How many rows?” Start at 1 and stop when the pairs turn "
                     "around.")


def practice_factors(bk):
    title = "Factors and Multiples: Practice"
    y = bk.new_page(title, "A factor divides the number with nothing left over.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Rectangles", "How many in each row?", "factor_array",
         [(2, 9), (3, 6), (4, 5), (2, 8), (3, 7), (4, 4)])
    part(2, "Factor pairs", "Start with 1. Stop when the pairs turn around.", "pairs",
         [factor_pairs_eq(n) for n in (18, 20, 28, 16, 30, 21, 36, 27)])
    part(3, "Is it a factor?", "Circle yes or no.", "yes_text",
         [(f"Is {a} a factor of {n}?", n % a == 0) for a, n in ((6, 42), (4, 30), (9, 48), (7, 56), (8, 72),
                                                              (3, 51), (5, 32), (6, 50), (4, 26), (7, 84))])
    part(4, "All the factors", "No help this time. List them from smallest to biggest.", "factor_list",
         [24, 40, 32, 45, 50, 60])
    part(5, "Multiples", "No help this time. Count by the number.", "eq2",
         [f"Multiples of {n}: {n} {2 * n} [{3 * n}] [{4 * n}] [{5 * n}]" for n in (6, 9, 7, 12, 8, 11, 15, 25)])
    part(6, "Is it a multiple?", "Circle yes or no.", "yes_text",
         [(f"Is {m} a multiple of {n}?", m % n == 0) for m, n in ((63, 9), (44, 6), (35, 5), (81, 3), (52, 8),
                                                                (70, 4), (96, 8), (58, 7), (74, 9), (90, 6))])
    part(7, "Prime or composite?", "Circle one.", "prime",
         [17, 21, 9, 13, 2, 27, 39, 11, 31, 29, 51, 49])
    part(8, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_60)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Draw the rectangles.")
    for i, story in enumerate(WORDS_60):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


def c_factor_list(bk, x, cy, w, n):
    bk.fit_eq(x + GUT, cy + 14, w - GUT - 10, f"Factors of {n}: " + " ".join(f"[{d}]" for d in factors(n)), size=17)


REVIEW_60 = ["846 ÷ 3 = [282]", "31 × 22 = [682]", "4,568 to the nearest ten = [4,570]", "2/3 of 15 = [10]",
             "2,705 + 4,198 = [6,903]", "5/6 of 30 = [25]"]

WORDS_60 = [
    ("A teacher wants 24 desks in equal rows. Will rows of 5 work, or rows of 6?",
     "24 = 4 × 6, 24 ÷ 5 = 4 R 4", "rows of 6", ""),
    ("Ana packs 36 cookies into bags with the same number in each. Should she put 7 or 9 in a bag?",
     "36 = 4 × 9", "9", "in a bag"),
    ("Buses come every 6 minutes. Does a bus come at 42 minutes after the hour?", "42 = 7 × 6, a multiple of 6",
     "yes", ""),
    ("Leo has 29 tiles. Can he make a rectangle with more than one row?", "29 is prime: only 1 × 29", "no", ""),
    ("Challenge: What is the smallest number that is a multiple of both 4 and 6?",
     "4, 8, 12 and 6, 12: both have 12", "12", ""),
]

KINDS_60 = {
    "factor_array": Kind(72, 1, lambda it: f"rectangle of dots: {it[0]} rows, {it[0] * it[1]} dots", c_factor_array),
    "yes_text": Kind(62, 2, lambda it: it[0], c_yes_text),
    "prime": Kind(48, 2, lambda n: f"prime or composite: {n}", c_prime, 8),
    "factor_list": Kind(48, 1, lambda n: f"all the factors of {n}", c_factor_list, 8),
    "pairs": Kind(44, 1, lambda t: t, lambda bk_, x, cy, w, t: bk_.fit_eq(x + GUT, cy + 14, w - GUT - 10, t, size=17), 8),
}
KINDS.update(KINDS_60)
BALANCE["yes_text"] = lambda it: it[1]
BALANCE["prime"] = is_prime

FACTOR_Q = [(f"Is {a} a factor of {n}?", n % a == 0) for n in rng(24, 96, 6) for a in (3, 4, 6, 7, 8, 9)]
MULTIPLE_Q = [(f"Is {m} a multiple of {n}?", m % n == 0) for n in (3, 4, 6, 7, 8, 9) for m in rng(41, 99, 7)]
PRIME_POOL = [n for n in rng(2, 99) if n > 3]

CHECKINS["60-factors-and-multiples"] = [
    S("Factor pairs", None, "pairs", [factor_pairs_eq(n) for n in (12, 14, 22, 24, 26, 32, 33, 35, 40, 42, 44, 45, 48)],
      2),
    S("Is it a factor?", "Circle yes or no.", "yes_text", FACTOR_Q, 2),
    S("Is it a multiple?", "Circle yes or no.", "yes_text", MULTIPLE_Q, 2),
    S("Prime or composite?", "Circle one.", "prime", PRIME_POOL, 3),
]
_g4[-1:-1] = [
    S("Prime or composite?", "Circle one.", "prime", PRIME_POOL, 3, 60),
    S("Is it a factor?", "Circle yes or no.", "yes_text", FACTOR_Q, 2, 60),
]


# ====================================================================== 61. Equivalent Fractions


def cut_strip(bk, x, y, w, h, n, a, k, answer_cuts=False):
    """A strip of n parts with a shaded, every part cut into k smaller pieces with dashed lines
    (answer_cuts: the dashed lines only on the key, in the answer colour)."""
    c = bk.c
    strip(bk, x, y, w, h, n, shaded=a)
    if answer_cuts and not bk.key:
        return
    c.setStrokeColor(T.answer if answer_cuts else T.ink)
    c.setLineWidth(0.9)
    c.setDash(2.5, 2)
    for i in range(n):
        for j in range(1, k):
            xx = x + w * (i + j / k) / n
            c.line(xx, y + 1, xx, y + h - 1)
    c.setDash()


def c_cut_strip(bk, x, cy, w, item):
    a, b, k = item
    bk.c.setFillColor(T.text2)
    bk.c.setFont("Rnd", 11)
    bk.c.drawString(x + GUT, cy + 52, f"Each piece is cut into {k}.")
    cut_strip(bk, x + GUT, cy + 14, 220, 26, b, a, k)
    frac_expr(bk, x + GUT + 250, cy + 22, f"{a}/{b} = [{a * k}]/[{b * k}]", size=22)


def c_equal_q(bk, x, cy, w, item):
    """Are these two fractions equal? The key rings yes or no."""
    (a, b), (p, q) = item
    frac_expr(bk, x + GUT, cy + 22, f"{a}/{b} and {p}/{q}", size=19)
    yes_no_choice(bk, x, cy - 2, w, a * q == b * p)


def learn_equivalent(bk):
    y = bk.new_page("Equivalent Fractions", "Cut every piece the same way: more pieces, same amount.",
                    name_line=False, big=True, footer="WeMath  ·  Equivalent Fractions")
    c = bk.c
    label(bk, M, y - 6, "2/3: cut every piece into 4")
    cut_strip(bk, M + 14, y - 54, 260, 30, 3, 2, 4)
    frac_expr(bk, M + 300, y - 46, "2/3 = 8/12", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 72, "4 times as many pieces, and 4 times as many shaded.")
    y -= 96

    label(bk, M, y - 6, "Multiply the top and the bottom by the same number")
    color_eq(bk, M + 14, y - 42, [("top:", None), ("2 × 4 = 8", "a")], 18)
    color_eq(bk, M + 14, y - 68, [("bottom:", None), ("3 × 4 = 12", "b")], 18)
    frac_expr(bk, M + 300, y - 60, "2/3 = 8/12", size=24)
    y -= 92

    label(bk, M, y - 6, "Divide to get bigger pieces")
    strip(bk, M + 14, y - 54, 260, 30, 10, shaded=6)
    frac_expr(bk, M + 300, y - 46, "6/10 = 3/5", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 72, "Put the pieces in pairs: top ÷ 2 and bottom ÷ 2.")
    y -= 96

    label(bk, M, y - 6, "Hundredths: tenths cut into 10")
    frac_expr(bk, M + 14, y - 40, "3/10 = 30/100", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 170, y - 36, "Every tenth is 10 hundredths.")
    y -= 62

    bottom = your_turn(bk, y, h=96)
    bk.ask("cut the pieces: 3/4 into 3 your turn")
    cut_strip(bk, M + 130, bottom + 30, 200, 26, 4, 3, 3)
    frac_expr(bk, M + 360, bottom + 36, "3/4 = [9]/[12]", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: equivalent fractions by multiplying or dividing the top and bottom by the same number "
                     "(4.NF.1). Say “Cut every piece into 4. How many pieces now? How many are shaded?”")


def practice_equivalent(bk):
    title = "Equivalent Fractions: Practice"
    y = bk.new_page(title, "Do the same to the top and the bottom.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Cut the pieces", "Count the small pieces, then the shaded ones.", "cut_strip",
         [(1, 3, 4), (3, 5, 2), (2, 4, 3), (5, 6, 2), (1, 2, 6), (3, 4, 2)])
    part(2, "Times the top and the bottom", "Multiply both by the number shown.", "frac2",
         [f"times {k}: {a}/{b} = [{a * k}]/[{b * k}]" for a, b, k in ((2, 5, 2), (1, 4, 3), (5, 6, 2), (2, 3, 4),
                                                                     (1, 3, 4), (3, 10, 10), (1, 2, 6), (4, 5, 20),
                                                                     (1, 6, 2), (9, 10, 10))])
    part(3, "Find the top number", "No help this time.", "frac3",
         ["3/4 = [9]/12", "1/3 = [4]/12", "5/6 = [10]/12", "1/4 = [3]/12", "7/10 = [70]/100", "1/2 = [50]/100",
          "2/3 = [8]/12", "3/5 = [60]/100", "1/6 = [2]/12", "1/4 = [25]/100", "1/2 = [6]/12", "2/5 = [40]/100"])
    part(4, "Find the bottom number", "No help this time.", "frac3",
         ["3/4 = 75/[100]", "2/3 = 8/[12]", "1/5 = 20/[100]", "5/6 = 10/[12]", "3/10 = 30/[100]", "1/2 = 6/[12]",
          "3/4 = 9/[12]", "4/5 = 80/[100]", "9/10 = 90/[100]"])
    part(5, "Fewer, bigger pieces", "No help this time. Divide the top and the bottom by the same number.", "frac3",
         ["8/12 = [2]/3", "60/100 = [3]/5", "9/12 = [3]/4", "50/100 = [1]/2", "10/12 = [5]/6", "40/100 = [2]/5",
          "4/12 = [1]/3", "75/100 = [3]/4", "6/12 = [1]/2", "20/100 = [1]/5", "2/12 = [1]/6", "70/100 = [7]/10"])
    part(6, "Equal or not?", "Circle yes or no.", "equal_q",
         [((2, 3), (8, 12)), ((3, 4), (6, 12)), ((1, 5), (20, 100)), ((5, 6), (10, 12)), ((2, 5), (25, 100)),
          ((3, 10), (30, 100)), ((1, 4), (4, 12)), ((7, 10), (70, 100))])
    part(7, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_61)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Draw a strip and cut the pieces.")
    for i, story in enumerate(WORDS_61):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_61 = ["1,248 ÷ 4 = [312]", "42 × 13 = [546]", "784 ÷ 4 = [196]",
             "3/8 [<] 5/8", "5,912 to the nearest hundred = [5,900]", "4/5 of 25 = [20]"]

WORDS_61 = [
    ("Mia ate 3/4 of a pizza cut in 12 slices. How many slices did she eat?", "3/4 = 9/12", "9", "slices"),
    ("A fence has 100 boards. 3/10 of them are painted. How many boards are painted?", "3/10 = 30/100", "30",
     "boards"),
    ("Leo read 8/12 of his book. Kim read 2/3 of the same book. Did they read the same amount?", "8/12 = 2/3",
     "yes", ""),
    ("60 of 100 seats are full. What fraction is that, in fifths?", "60/100 = 3/5", "3/5", "full"),
    ("Challenge: Sam says 2/5 = 4/10 = 40/100. Is he right? What would 2/5 be in twentieths?",
     "2/5 = 8/20", "8/20", ""),
]

KINDS_61 = {
    "cut_strip": Kind(72, 1, lambda it: f"cut the pieces: {it[0]}/{it[1]} into {it[2]}", c_cut_strip, 8),
    "equal_q": Kind(62, 2, lambda it: f"equal or not: {it[0][0]}/{it[0][1]} and {it[1][0]}/{it[1][1]}", c_equal_q),
}
KINDS.update(KINDS_61)
BALANCE["equal_q"] = lambda it: it[0][0] * it[1][1] == it[0][1] * it[1][0]

_EQ4 = [(2, 4), (2, 6), (2, 8), (2, 10), (2, 12), (2, 100), (3, 6), (3, 12), (4, 8), (4, 12), (4, 100), (5, 10),
        (5, 100), (6, 12), (10, 100)]
EQUIV_TOP = [f"{a}/{n} = [{a * m // n}]/{m}" for n, m in _EQ4 for a in rng(1, n - 1)]
EQUIV_DOWN = [f"{a * m // n}/{m} = [{a}]/{n}" for n, m in _EQ4 for a in rng(1, n - 1)]
EQUIV_Q = ([((a, n), (a * m // n, m)) for n, m in _EQ4 for a in rng(1, n - 1)]
           + [((a, n), (a * m // n + 1, m)) for n, m in _EQ4 for a in rng(1, n - 1) if a * m // n + 1 < m])

CHECKINS["61-equivalent-fractions"] = [
    S("Cut the pieces", None, "cut_strip", [(a, n, k) for n in (2, 3, 4, 5) for a in rng(1, n - 1) for k in (2, 3, 4)],
      1),
    S("Find the top number", None, "frac3", EQUIV_TOP, 3),
    S("Fewer, bigger pieces", None, "frac3", EQUIV_DOWN, 3),
    S("Equal or not?", "Circle yes or no.", "equal_q", EQUIV_Q, 2),
]
_g4[-1:-1] = [
    S("Equivalent fractions", None, "frac3", EQUIV_TOP + EQUIV_DOWN, 3, 61),
]


# ====================================================================== 62. Comparing Unlike Fractions


HALF_WORDS = ("less than 1/2", "= 1/2", "more than 1/2")


def half_side(a, b):
    return HALF_WORDS[0] if 2 * a < b else HALF_WORDS[1] if 2 * a == b else HALF_WORDS[2]


def c_vs_half(bk, x, cy, w, item):
    a, b = item
    frac_expr(bk, x + GUT, cy + 16, f"{a}/{b}", size=18)
    circle_choice(bk, x + GUT + 40, cy + 17, HALF_WORDS, half_side(a, b), size=11, gap=11)


def same_bottom_line(a, b, p, q):
    from math import lcm
    m = lcm(b, q)
    return (f"{a}/{b} = [{a * m // b}]/{m} and {p}/{q} = [{p * m // q}]/{m} "
            f"so {a}/{b} [{frac_sign(a, b, p, q)}] {p}/{q}")


def c_smallest(bk, x, cy, w, item):
    """Three fractions; the key rings the smallest."""
    c = bk.c
    low = min(item, key=lambda f: Fraction(*f))
    fx = x + GUT + 6
    for a, b in item:
        frac_expr(bk, fx, cy + 16, f"{a}/{b}", size=18)
        if bk.key and (a, b) == low:
            c.setStrokeColor(T.answer)
            c.setLineWidth(1.5)
            c.ellipse(fx - 9, cy + 2, fx + 27, cy + 42, stroke=1, fill=0)
        fx += 56


def learn_comparing_unlike(bk):
    y = bk.new_page("Comparing Unlike Fractions", "Use 1/2, or make the pieces the same size.",
                    name_line=False, big=True, footer="WeMath  ·  Comparing Unlike Fractions")
    c = bk.c
    label(bk, M, y - 6, "Compare with 1/2")
    strip(bk, M + 14, y - 46, 220, 22, 8, shaded=3)
    strip(bk, M + 14, y - 76, 220, 22, 6, shaded=4)
    c.setStrokeColor(T.accent)
    c.setLineWidth(1.4)
    c.setDash(3, 2.5)
    c.line(M + 124, y - 18, M + 124, y - 80)
    c.setDash()
    frac_expr(bk, M + 260, y - 62, "3/8 < 4/6", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 380, y - 46, "3/8 is less than half.")
    c.drawString(M + 380, y - 64, "4/6 is more than half.")
    y -= 104

    label(bk, M, y - 6, "Make the bottom numbers the same")
    cut_strip(bk, M + 14, y - 46, 220, 22, 3, 2, 4)
    cut_strip(bk, M + 14, y - 76, 220, 22, 4, 3, 3)
    frac_expr(bk, M + 260, y - 46, "2/3 = 8/12", size=18)
    frac_expr(bk, M + 260, y - 80, "3/4 = 9/12", size=18)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 380, y - 46, "Now the pieces match:")
    frac_expr(bk, M + 380, y - 80, "2/3 < 3/4", size=18)
    y -= 110

    label(bk, M, y - 6, "Close to 1? Look at the missing piece")
    strip(bk, M + 14, y - 46, 220, 22, 8, shaded=7)
    strip(bk, M + 14, y - 76, 220, 22, 10, shaded=9)
    frac_expr(bk, M + 260, y - 62, "7/8 < 9/10", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 380, y - 46, "7/8 misses 1/8.")
    c.drawString(M + 380, y - 64, "9/10 misses only 1/10.")
    y -= 102

    bottom = your_turn(bk, y, h=80)
    bk.ask("compare to one half: 2/5 and 5/8 your turn")
    frac_expr(bk, M + 150, bottom + 28, "2/5 [<] 5/8", size=26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 320, bottom + 34, "Which one is more than half?")
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: compare fractions with different tops and bottoms (4.NF.2). Ask “Is each one more or "
                     "less than half?” If that doesn't settle it, cut the pieces so the bottoms match.")


def practice_comparing_unlike(bk):
    title = "Comparing Unlike Fractions: Practice"
    y = bk.new_page(title, "Same whole. Write <, > or =.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "More or less than half?", "Half of the bottom number is the middle.", "vs_half",
         [(3, 8), (4, 6), (5, 10), (2, 5), (7, 12), (3, 4), (6, 12), (1, 3), (4, 5), (5, 12)])
    part(2, "Compare with strips", "Look at how much is shaded.", "compare_frac",
         [((2, 3), (3, 5)), ((3, 8), (2, 3)), ((5, 6), (7, 8)), ((2, 4), (5, 10)), ((3, 5), (1, 4)),
          ((7, 12), (3, 4))])
    part(3, "Use 1/2", "No help this time. One is less than half, one is more.", "frac3",
         ["3/8 [<] 4/6", "5/6 [>] 2/5", "5/8 [>] 2/6", "1/3 [<] 7/10", "4/10 [<] 2/3", "7/12 [>] 3/8",
          "4/6 [>] 1/4", "2/5 [<] 3/4", "3/10 [<] 5/8"])
    part(4, "Make the bottoms the same", "Then compare the tops.", "frac1",
         [same_bottom_line(a, b, p, q) for a, b, p, q in ((2, 3, 3, 4), (3, 5, 7, 10), (5, 6, 3, 4), (3, 8, 1, 4),
                                                          (5, 12, 1, 3), (2, 5, 3, 10), (1, 2, 5, 12),
                                                          (4, 6, 7, 12))])
    part(5, "Close to 1", "No help this time. Which one misses less?", "frac3",
         ["7/8 [<] 9/10", "5/6 [>] 3/4", "11/12 [>] 4/5", "2/3 [<] 5/6", "9/10 [>] 3/4", "4/5 [<] 7/8"])
    part(6, "Compare", "No help this time.", "frac3",
         ["3/4 [>] 5/8", "7/12 [<] 5/6", "4/5 [>] 7/10", "5/12 [<] 1/2", "3/10 [<] 2/5", "1/4 [<] 3/8",
          "5/6 [>] 7/12", "6/10 [=] 3/5", "7/10 [>] 1/2", "1/3 [<] 5/12", "2/4 [<] 7/12", "3/8 [<] 2/4"])
    part(7, "Circle the smallest", "No help this time.", "smallest",
         [((3, 4), (1, 3), (5, 8)), ((7, 10), (4, 5), (1, 2)), ((5, 6), (2, 3), (7, 12)), ((3, 5), (1, 2), (9, 10)),
          ((2, 6), (5, 8), (1, 4)), ((3, 8), (1, 2), (2, 3))])
    part(8, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_62)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Draw strips to compare.")
    for i, story in enumerate(WORDS_62):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_62 = ["9/10 = [90]/100", "56 × 12 = [672]", "1,515 ÷ 5 = [303]", "4,816 to the nearest ten = [4,820]",
             "2/3 of 27 = [18]", "8,003 − 2,457 = [5,546]".replace("−", MINUS)]

WORDS_62 = [
    ("Mia ran 3/4 of a mile. Ben ran 2/3 of a mile. Who ran farther?", "3/4 = 9/12, 2/3 = 8/12", "Mia", ""),
    ("A red jug is 3/8 full. A blue jug is 5/6 full. Which jug has more?", "3/8 < 1/2 < 5/6", "blue", "jug"),
    ("Kim ate 4/10 of a pizza. Leo ate 2/5 of the same pizza. Who ate more?", "4/10 = 2/5", "same", ""),
    ("Sam's ribbon is 7/12 of a yard. Jo's ribbon is 1/2 of a yard. Whose ribbon is longer?", "7/12 > 6/12",
     "Sam's", "ribbon"),
    ("Challenge: Ana did 5/6 of her homework. Max did 7/8 of his. Who has less left to do?",
     "1/8 left < 1/6 left", "Max", ""),
]

KINDS_62 = {
    "vs_half": Kind(44, 1, lambda it: f"more or less than half: {it[0]}/{it[1]}", c_vs_half, 8),
    "smallest": Kind(48, 2, lambda it: "smallest: " + " ".join(f"{a}/{b}" for a, b in it), c_smallest, 8),
}
KINDS.update(KINDS_62)
KINDS["frac1"] = Kind(48, 1, lambda t: t, c_frac, 8)
BALANCE["vs_half"] = lambda it: 2 * it[0] > it[1]

_UNLIKE = [(a, b, p, q) for b in (3, 4, 5, 6, 8, 10, 12) for q in (3, 4, 5, 6, 8, 10, 12) if b < q
           for a in rng(1, b - 1) for p in rng(1, q - 1) if a != p and a * q != b * p]
UNLIKE_HALF = [f"{a}/{b} [{frac_sign(a, b, p, q)}] {p}/{q}" for a, b, p, q in _UNLIKE
               if (2 * a - b) * (2 * p - q) < 0]
# Both fractions change: the shared bottom is 6, 10 or 12 and neither bottom is already it (2/3 and 3/4 -> 12).
UNLIKE_SAME = [same_bottom_line(a, b, p, q) for a, b, p, q in _UNLIKE
               if math.lcm(b, q) in (6, 10, 12) and math.lcm(b, q) not in (b, q)]
VS_HALF = [(a, b) for b in (4, 5, 6, 8, 10, 12) for a in rng(1, b - 1)]

CHECKINS["62-comparing-unlike-fractions"] = [
    S("More or less than half?", None, "vs_half", VS_HALF, 2),
    S("Make the bottoms the same", None, "frac1", UNLIKE_SAME, 2),
    S("Compare", "Write <, > or =.", "frac3", UNLIKE_HALF, 6, balance=is_less),
]
_g4[-1:-1] = [
    S("Compare fractions", "Write <, > or =.", "frac3", UNLIKE_HALF, 3, 62, balance=is_less),
]


# ====================================================================== 63. Adding and Subtracting Fractions


def add_strip(bk, x, y, w, h, n, a, b, take=False):
    """A strip of n parts. Adding: a parts shaded, then b parts with a dot (the second number).
    Taking away (take=True): a parts shaded, the last b of them crossed out."""
    c = bk.c
    strip(bk, x, y, w, h, n, shaded=a)
    pw = w / n
    for i in range(b):
        j = (a + i) if not take else (a - b + i)
        cx = x + pw * (j + 0.5)
        if take:
            c.setStrokeColor(T.ink)
            c.setLineWidth(1.3)
            c.line(cx - pw * 0.3, y + h * 0.2, cx + pw * 0.3, y + h * 0.8)
            c.line(cx - pw * 0.3, y + h * 0.8, cx + pw * 0.3, y + h * 0.2)
        else:
            bk.dot(cx, y + h / 2, min(5, pw * 0.22), "b")


def c_add_strip(bk, x, cy, w, item):
    a, b, n, op = item
    take = op == "-"
    add_strip(bk, x + GUT, cy + 18, 220, 26, n, a, b, take=take)
    sign = MINUS if take else "+"
    ans = a - b if take else a + b
    frac_fit(bk, x + GUT + 246, cy + 24, w - GUT - 256, f"{a}/{n} {sign} {b}/{n} = [{ans}]/{n}", size=20)


def fsum(a, b, n):
    return f"{a}/{n} + {b}/{n} = [{a + b}]/{n}"


def fdiff(a, b, n):
    return f"{a}/{n} {MINUS} {b}/{n} = [{a - b}]/{n}"


def learn_add_fractions(bk):
    y = bk.new_page("Adding and Subtracting Fractions", "Same size pieces: add or take away the tops.",
                    name_line=False, big=True, footer="WeMath  ·  Adding and Subtracting Fractions")
    c = bk.c
    label(bk, M, y - 6, "2/8 + 3/8: count the eighths")
    add_strip(bk, M + 14, y - 54, 260, 30, 8, 2, 3)
    frac_expr(bk, M + 300, y - 46, "2/8 + 3/8 = 5/8", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 72, "2 eighths and 3 more eighths make 5 eighths. The bottom number stays.")
    y -= 96

    label(bk, M, y - 6, "5/6 − 2/6: take away sixths")
    add_strip(bk, M + 14, y - 54, 260, 30, 6, 5, 2, take=True)
    frac_expr(bk, M + 300, y - 46, f"5/6 {MINUS} 2/6 = 3/6", size=22)
    y -= 80

    label(bk, M, y - 6, "Split a fraction into parts")
    frac_expr(bk, M + 14, y - 42, "3/5 = 1/5 + 1/5 + 1/5", size=20)
    frac_expr(bk, M + 14, y - 86, "3/5 = 1/5 + 2/5", size=20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 290, y - 40, "Any way you split the pieces,")
    c.drawString(M + 290, y - 56, "they add up to the same amount.")
    y -= 112

    label(bk, M, y - 6, "Fraction buddies make one whole")
    frac_expr(bk, M + 14, y - 42, "3/8 + 5/8 = 8/8 = 1", size=20)
    y -= 66

    bottom = your_turn(bk, y, h=88)
    bk.ask("add with strips: 3/10 + 4/10 your turn")
    add_strip(bk, M + 130, bottom + 30, 200, 24, 10, 3, 4)
    frac_expr(bk, M + 350, bottom + 36, "3/10 + 4/10 = [7]/10", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: add and subtract fractions with the same bottom number, and split a fraction into "
                     "parts (4.NF.3a, b, d). Say “What size are the pieces? How many pieces now?” Never add the "
                     "bottom numbers.")


def practice_add_fractions(bk):
    title = "Adding and Subtracting Fractions: Practice"
    y = bk.new_page(title, "The bottom number tells the size of the pieces. It stays the same.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Add with strips", "Shaded pieces, then the dotted pieces.", "add_strip",
         [(3, 2, 6, "+"), (1, 4, 8, "+"), (2, 5, 10, "+"), (1, 1, 3, "+"), (4, 3, 12, "+"), (2, 2, 5, "+")])
    part(2, "Take away with strips", "Cross out the pieces you take away.", "add_strip",
         [(5, 3, 8, "-"), (4, 1, 6, "-"), (9, 4, 10, "-"), (3, 2, 4, "-"), (7, 5, 12, "-"), (4, 2, 5, "-")])
    part(3, "Split it up", "Find the missing part.", "frac2",
         ["5/8 = 2/8 + [3]/8", "4/6 = 1/6 + [3]/6", "7/10 = 3/10 + [4]/10", "3/4 = 2/4 + [1]/4",
          "9/12 = 4/12 + [5]/12", "4/5 = 1/5 + [3]/5", "6/8 = 1/8 + [5]/8", "8/10 = 6/10 + [2]/10",
          "5/6 = 3/6 + [2]/6", "11/12 = 5/12 + [6]/12"])
    part(4, "Add", "No help this time.", "frac3",
         [fsum(a, b, n) for a, b, n in ((3, 4, 8), (2, 3, 5), (5, 2, 10), (1, 3, 6), (7, 4, 12), (1, 2, 4),
                                        (4, 5, 10), (2, 1, 3), (3, 3, 8), (5, 6, 12), (1, 4, 6), (2, 4, 10),
                                        (1, 1, 5), (6, 1, 8), (3, 8, 12))])
    part(5, "Take away", "No help this time.", "frac3",
         [fdiff(a, b, n) for a, b, n in ((7, 3, 8), (4, 2, 5), (9, 5, 10), (5, 1, 6), (11, 6, 12), (3, 1, 4),
                                         (6, 4, 8), (8, 3, 10), (2, 1, 3), (10, 7, 12), (6, 2, 6), (3, 2, 5))])
    part(6, "Fraction buddies", "No help this time. Together they make 1 whole.", "frac3",
         ["5/8 + [3]/8 = 1", "2/5 + [3]/5 = 1", "7/10 + [3]/10 = 1", "1/6 + [5]/6 = 1", "5/12 + [7]/12 = 1",
          "1/4 + [3]/4 = 1", "4/10 + [6]/10 = 1", "2/3 + [1]/3 = 1", "7/8 + [1]/8 = 1"])
    part(7, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_63)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Draw a strip.")
    for i, story in enumerate(WORDS_63):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_63 = ["3/4 = [75]/100", "2/3 [<] 7/8", "64 × 15 = [960]", "1,035 ÷ 5 = [207]", "4/5 of 40 = [32]",
             "2,999 + 1,436 = [4,435]"]

WORDS_63 = [
    ("Mia ate 2/8 of a pizza. Ben ate 3/8 of it. How much of the pizza did they eat?", "2/8 + 3/8 = 5/8",
     "5/8", "of the pizza"),
    ("A jug is 7/10 full. Sam drinks 3/10 of the jug. How full is it now?", f"7/10 {MINUS} 3/10 = 4/10", "4/10",
     "full"),
    ("Leo walked 1/4 mile to the park and 2/4 mile to school. How far did he walk?", "1/4 + 2/4 = 3/4", "3/4",
     "mile"),
    ("A ribbon is 5/6 of a yard. Kim cuts off 4/6 of a yard. How much is left?", f"5/6 {MINUS} 4/6 = 1/6", "1/6",
     "of a yard"),
    ("Ana painted 5/12 of a wall. How much more must she paint to finish the wall?", "5/12 + 7/12 = 1", "7/12",
     "of the wall"),
    ("Challenge: Jo read 2/10 of a book on Monday and 5/10 on Tuesday. How much is left to read?",
     f"2/10 + 5/10 = 7/10, 1 {MINUS} 7/10 = 3/10", "3/10", "of the book"),
]

KINDS_63 = {
    "add_strip": Kind(62, 1, lambda it: f"{'add' if it[3] == '+' else 'take away'} with strips: {it[0]}/{it[2]} "
                                         f"and {it[1]}/{it[2]}", c_add_strip, 8),
}
KINDS.update(KINDS_63)

_A_DENS = (3, 4, 5, 6, 8, 10, 12)
FRAC_ADD = [fsum(a, b, n) for n in _A_DENS for a in rng(1, n - 1) for b in rng(1, n - a)]
FRAC_SUB = [fdiff(a, b, n) for n in _A_DENS for a in rng(2, n) for b in rng(1, a - 1)]
FRAC_SPLIT = [f"{a + b}/{n} = {a}/{n} + [{b}]/{n}" for n in _A_DENS for a in rng(1, n - 2) for b in rng(1, n - 1 - a)]

CHECKINS["63-adding-and-subtracting-fractions"] = [
    S("Add with strips", None, "add_strip", [(a, b, n, "+") for n in (5, 6, 8, 10) for a in rng(1, 3)
                                             for b in rng(1, 3) if a + b < n], 1),
    S("Split it up", None, "frac2", FRAC_SPLIT, 2),
    S("Add", None, "frac3", FRAC_ADD, 3),
    S("Take away", None, "frac3", FRAC_SUB, 3),
]
_g4[-1:-1] = [
    S("Add and subtract fractions", None, "frac3", FRAC_ADD[::2] + FRAC_SUB[::2], 3, 63),
]


# ====================================================================== 64. Mixed Numbers


def mixed(t, n):
    """7, 4 -> "1 3/4" (or "2" when there are no pieces left)."""
    q, r = divmod(t, n)
    return f"{q} {r}/{n}" if r else str(q)


def mixed_box(t, n):
    """7, 4 -> "[1] [3]/4": the answer as boxes."""
    q, r = divmod(t, n)
    return f"[{q}] [{r}]/{n}"


def mx(text, answer):
    """A mixed-number question: (text drawn with frac_expr, the answer for curriculum.json)."""
    return (text, answer)


def c_mixed_q(bk, x, cy, w, item):
    frac_fit(bk, x + GUT, cy + 16, w - GUT - 10, item[0], size=17)


def c_to_mixed(bk, x, cy, w, item):
    """Full bars, then a part bar: name it as a fraction and as a mixed number."""
    n, t = item
    k = -(-t // n)
    strips(bk, x + GUT, cy + 40 + k * 12, 150, n, k, shaded=t, h=16, gap=6)
    frac_fit(bk, x + GUT + 172, cy + 34, w - GUT - 182, f"[{t}]/{n} = " + mixed_box(t, n), size=19)


def learn_mixed_numbers(bk):
    y = bk.new_page("Mixed Numbers", "Whole ones and pieces: 1 3/4 means 1 whole and 3/4.", name_line=False,
                    big=True, footer="WeMath  ·  Mixed Numbers")
    c = bk.c
    label(bk, M, y - 6, "7/4 is 1 whole and 3/4 more")
    strips(bk, M + 14, y - 22, 220, 4, 2, shaded=7, h=24, gap=8)
    frac_expr(bk, M + 260, y - 52, "7/4 = 1 3/4", size=26)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 410, y - 40, "Say: one and")
    c.drawString(M + 410, y - 56, "three fourths.")
    y -= 96

    label(bk, M, y - 6, "Back to a fraction: count all the pieces")
    frac_expr(bk, M + 14, y - 42, "2 1/3 = 3/3 + 3/3 + 1/3 = 7/3", size=20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 70, "Each whole is 3 thirds: 2 wholes are 6 thirds, plus 1 more is 7 thirds.")
    y -= 94

    label(bk, M, y - 6, "Add: wholes with wholes, pieces with pieces")
    frac_expr(bk, M + 14, y - 42, "2 1/5 + 1 3/5 = 3 4/5", size=20)
    frac_expr(bk, M + 14, y - 84, "1 3/4 + 2 2/4 = 3 5/4 = 4 1/4", size=20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 340, y - 78, "5/4 is another whole and 1/4.")
    y -= 108

    label(bk, M, y - 6, "Take away the same way")
    frac_expr(bk, M + 14, y - 42, f"3 4/6 {MINUS} 1 1/6 = 2 3/6", size=20)
    y -= 64

    bottom = your_turn(bk, y, h=84)
    bk.ask("write the mixed number: 5/3 in strips your turn")
    strips(bk, M + 130, bottom + 66, 160, 3, 2, shaded=5, h=18, gap=6)
    frac_expr(bk, M + 320, bottom + 34, "5/3 = [1] [2]/3", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: mixed numbers with the same bottom number: rename, add and subtract (4.NF.3c). Say "
                     "“How many whole bars? How many pieces left over?” Add the wholes, then the pieces.")


def practice_mixed_numbers(bk):
    title = "Mixed Numbers: Practice"
    y = bk.new_page(title, "Whole ones first, then the pieces.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Write the mixed number", "Count the pieces, then the whole bars.", "to_mixed",
         [(4, 9), (3, 7), (6, 10), (5, 8), (8, 11), (2, 5)])
    part(2, "Fraction to mixed number", "No help this time.", "mixed3",
         [mx(f"{t}/{n} = " + mixed_box(t, n), mixed(t, n)) for t, n in
          ((9, 2), (13, 4), (8, 3), (12, 5), (15, 4), (11, 3), (17, 6), (23, 10), (14, 5), (19, 8), (10, 6),
           (25, 12))])
    part(3, "Mixed number to fraction", "No help this time. How many pieces in all?", "mixed3",
         [mx(f"{mixed(t, n)} = [{t}]/{n}", f"{t}/{n}") for t, n in
          ((7, 2), (11, 4), (10, 3), (13, 5), (17, 4), (14, 3), (11, 6), (27, 10), (17, 5), (21, 8), (19, 6),
           (13, 12))])
    part(4, "Add mixed numbers", "No help this time. Wholes, then pieces.", "mixed2",
         [mx(f"{mixed(a, n)} + {mixed(b, n)} = " + mixed_box(a + b, n), mixed(a + b, n)) for a, b, n in
          ((9, 6, 4), (7, 6, 5), (11, 12, 8), (7, 4, 3), (13, 15, 6), (21, 32, 10), (7, 8, 6), (10, 5, 4),
           (16, 13, 12))])
    part(5, "Make a new whole", "The pieces make more than 1. Turn them into a whole.", "mixed1",
         [mx(f"{mixed(a, n)} + {mixed(b, n)} = {(a // n) + (b // n)} [{a % n + b % n}]/{n} = " + mixed_box(a + b, n),
             mixed(a + b, n)) for a, b, n in ((7, 11, 4), (8, 9, 5), (13, 14, 8), (5, 8, 3), (11, 9, 6),
                                              (17, 29, 10))])
    part(6, "Take away mixed numbers", "No help this time.", "mixed2",
         [mx(f"{mixed(a, n)} {MINUS} {mixed(b, n)} = " + mixed_box(a - b, n), mixed(a - b, n)) for a, b, n in
          ((19, 6, 5), (15, 5, 4), (31, 12, 8), (11, 4, 3), (23, 8, 6), (37, 12, 10), (27, 13, 6), (19, 6, 4),
           (41, 15, 12))])
    part(7, "Break a whole first", "Not enough pieces? Turn one whole into pieces.", "mixed1",
         [mx(f"{mixed(a, n)} {MINUS} {mixed(b, n)} = {a // n - 1} [{a % n + n}]/{n} {MINUS} {mixed(b, n)} = "
             + mixed_box(a - b, n), mixed(a - b, n)) for a, b, n in ((14, 7, 4), (16, 9, 5), (25, 15, 8),
                                                                    (19, 11, 6))])
    part(8, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_64)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Draw the bars.")
    for i, story in enumerate(WORDS_64):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_64 = ["5/8 + 2/8 = [7]/8", "9/10 − 4/10 = [5]/10".replace("−", MINUS), "7/12 [>] 1/2", "72 × 21 = [1,512]",
             "2,448 ÷ 4 = [612]", "Round 6,550 to the nearest hundred: [6,600]"]

WORDS_64 = [
    ("Mia ran 1 2/4 miles on Monday and 2 1/4 miles on Tuesday. How far did she run?", "1 2/4 + 2 1/4 = 3 3/4",
     "3 3/4", "miles"),
    ("A pizza has 8 slices. Ben's family ate 11 slices from two pizzas. How many pizzas is that?",
     "11/8 = 1 3/8", "1 3/8", "pizzas"),
    ("A ribbon is 4 5/6 feet long. Leo cuts off 2 1/6 feet. How long is the rest?", f"4 5/6 {MINUS} 2 1/6 = 2 4/6",
     "2 4/6", "feet"),
    ("Kim baked 2 3/4 pans of bread and then 1 3/4 pans more. How many pans in all?",
     "2 3/4 + 1 3/4 = 3 6/4 = 4 2/4", "4 2/4", "pans"),
    ("Challenge: A jug holds 3 1/4 liters. Sam pours out 1 3/4 liters. How much is left in the jug?",
     f"3 1/4 {MINUS} 1 3/4 = 1 2/4", "1 2/4", "liters"),
]

KINDS_64 = {
    "to_mixed": Kind(84, 1, lambda it: f"write the mixed number: {it[1]}/{it[0]} in strips", c_to_mixed, 8),
    "mixed3": Kind(48, 3, lambda it: it[0], c_mixed_q, 8),
    "mixed2": Kind(48, 2, lambda it: it[0], c_mixed_q, 8),
    "mixed1": Kind(48, 1, lambda it: it[0], c_mixed_q, 8),
}
KINDS.update(KINDS_64)

_M_DENS = (2, 3, 4, 5, 6, 8, 10, 12)
TO_MIXED = [mx(f"{t}/{n} = " + mixed_box(t, n), mixed(t, n)) for n in _M_DENS for t in rng(n + 1, 4 * n) if t % n]
TO_FRAC = [mx(f"{mixed(t, n)} = [{t}]/{n}", f"{t}/{n}") for n in _M_DENS for t in rng(n + 1, 4 * n) if t % n]
MIXED_ADD = [mx(f"{mixed(a, n)} + {mixed(b, n)} = " + mixed_box(a + b, n), mixed(a + b, n))
             for n in (3, 4, 5, 6, 8) for a in rng(n + 1, 3 * n - 1, 2) for b in rng(n + 1, 2 * n - 1)
             if a % n and b % n and (a + b) % n and a % n + b % n < n]
MIXED_SUB = [mx(f"{mixed(a, n)} {MINUS} {mixed(b, n)} = " + mixed_box(a - b, n), mixed(a - b, n))
             for n in (3, 4, 5, 6, 8) for a in rng(2 * n + 1, 4 * n - 1, 2) for b in rng(n + 1, 2 * n - 1)
             if a % n > b % n > 0]

CHECKINS["64-mixed-numbers"] = [
    S("Write the mixed number", None, "to_mixed", [(n, t) for n in (3, 4, 5, 6) for t in rng(n + 1, 2 * n - 1)], 1),
    S("Fraction to mixed number", None, "mixed3", TO_MIXED, 3),
    S("Mixed number to fraction", None, "mixed3", TO_FRAC, 3),
    S("Add and take away", None, "mixed2", MIXED_ADD[::3] + MIXED_SUB[::3], 2),
]
_g4[-1:-1] = [
    S("Mixed numbers", None, "mixed3", TO_MIXED + TO_FRAC, 3, 64),
]


# ====================================================================== 65. Fractions Times Whole Numbers


def c_groups_frac(bk, x, cy, w, item):
    """k strips, each with a/n shaded: k groups of a/n."""
    k, a, n = item
    top = cy + 22 + k * 22
    for j in range(k):
        strip(bk, x + GUT, top - 18 - j * 22, 150, 16, n, shaded=a)
    frac_fit(bk, x + GUT + 176, cy + 22 + k * 11 - 6, w - GUT - 186, f"{k} {TIMES} {a}/{n} = [{k * a}]/{n}", size=20)


def ftimes(k, a, n):
    return f"{k} {TIMES} {a}/{n} = [{k * a}]/{n}"


def learn_frac_times(bk):
    y = bk.new_page("Fractions Times Whole Numbers", "3 × 2/5 means 3 groups of 2/5.", name_line=False,
                    big=True, footer="WeMath  ·  Fractions Times Whole Numbers")
    c = bk.c
    label(bk, M, y - 6, "3 groups of 2/5")
    for j in range(3):
        strip(bk, M + 14, y - 40 - j * 26, 200, 20, 5, shaded=2)
    frac_expr(bk, M + 240, y - 72, f"3 {TIMES} 2/5 = 6/5", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 240, y - 104, "2 fifths, 3 times: 6 fifths.")
    y -= 128

    label(bk, M, y - 6, "It's the same as adding")
    frac_expr(bk, M + 14, y - 42, "2/5 + 2/5 + 2/5 = 6/5 = 1 1/5", size=20)
    y -= 66

    label(bk, M, y - 6, "Every fraction is unit fractions put together")
    frac_expr(bk, M + 14, y - 42, f"5/4 = 5 {TIMES} 1/4", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 200, y - 38, "5 pieces, each one 1/4.")
    y -= 66

    label(bk, M, y - 6, "Multiply the top. The bottom stays.")
    frac_expr(bk, M + 14, y - 42, f"4 {TIMES} 3/8 = 12/8", size=22)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 200, y - 38, "4 × 3 = 12 eighths. The pieces are still eighths.")
    y -= 66

    bottom = your_turn(bk, y, h=96)
    bk.ask("groups of a fraction: 2 x 3/4 your turn")
    for j in range(2):
        strip(bk, M + 130, bottom + 56 - j * 24, 160, 18, 4, shaded=3)
    frac_expr(bk, M + 320, bottom + 38, f"2 {TIMES} 3/4 = [6]/4", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: a whole number times a fraction (4.NF.4): 3 × 2/5 is 3 groups of 2/5. Say “How many "
                     "groups? How many pieces in each? What size are the pieces?” Only the top number grows.")


def practice_frac_times(bk):
    title = "Fractions Times Whole Numbers: Practice"
    y = bk.new_page(title, "Groups of a fraction: multiply the top. The bottom stays.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Groups of a fraction", "Count all the shaded pieces.", "groups_frac",
         [(2, 2, 5), (3, 1, 4), (4, 2, 6), (2, 3, 8), (3, 2, 3), (4, 3, 10)])
    part(2, "Unit fractions", "No help this time.", "frac3",
         [f"{k} {TIMES} 1/{n} = [{k}]/{n}" for k, n in ((5, 4), (3, 8), (7, 10), (2, 3), (6, 5), (4, 12), (9, 6),
                                                        (3, 2), (11, 8))]
         + [f"{k}/{n} = [{k}] {TIMES} 1/{n}" for k, n in ((7, 3), (5, 6), (9, 10), (4, 5), (11, 12), (3, 4))])
    part(3, "Add it up", "Write it as adding, then multiply.", "frac1",
         [f"{k} {TIMES} {a}/{n} = " + " + ".join([f"{a}/{n}"] * k) + f" = [{k * a}]/{n}"
          for k, a, n in ((3, 2, 6), (4, 3, 5), (2, 5, 8), (3, 4, 10), (5, 2, 12), (2, 2, 3))])
    part(4, "Multiply", "No help this time.", "frac3",
         [ftimes(k, a, n) for k, a, n in ((4, 3, 8), (2, 3, 5), (5, 2, 10), (3, 5, 6), (6, 2, 12), (2, 7, 8),
                                          (3, 3, 4), (4, 2, 5), (7, 3, 10), (2, 5, 12), (5, 1, 3), (3, 7, 10),
                                          (4, 5, 6), (6, 3, 8), (8, 1, 5))])
    part(5, "As a mixed number", "No help this time. Then turn it into a mixed number.", "mixed2",
         [mx(f"{k} {TIMES} {a}/{n} = [{k * a}]/{n} = " + mixed_box(k * a, n), mixed(k * a, n))
          for k, a, n in ((3, 3, 4), (2, 4, 5), (5, 2, 3), (3, 5, 8), (4, 4, 6), (3, 7, 10), (2, 5, 6),
                          (5, 3, 4))])
    part(6, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_65)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 7, "Word problems", "Draw the groups.")
    for i, story in enumerate(WORDS_65):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 7, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_65 = ["2 3/8 + 1 4/8 = [3] [7]/8", "11/4 = [2] [3]/4", "3/12 [<] 1/2",
             "45 × 13 = [585]", "3,654 ÷ 6 = [609]", "5/8 [<] 3/4"]

WORDS_65 = [
    ("Each pancake uses 3/4 cup of milk. How much milk do 2 pancakes use?", f"2 {TIMES} 3/4 = 6/4", "6/4",
     "cups"),
    ("Mia walks 2/5 of a mile to school each day. How far does she walk in 4 days?", f"4 {TIMES} 2/5 = 8/5",
     "8/5", "miles"),
    ("Each of 5 kids eats 1/8 of a pizza. How much of the pizza do they eat?", f"5 {TIMES} 1/8 = 5/8", "5/8",
     "of the pizza"),
    ("A plant grows 3/10 of an inch each week. How much does it grow in 3 weeks?", f"3 {TIMES} 3/10 = 9/10",
     "9/10", "inch"),
    ("Challenge: A recipe needs 2/3 cup of flour. Leo makes it 4 times. Is that more than 2 cups?",
     f"4 {TIMES} 2/3 = 8/3 = 2 2/3", "yes", ""),
]

KINDS_65 = {
    "groups_frac": Kind(118, 1, lambda it: f"groups of a fraction: {it[0]} x {it[1]}/{it[2]}", c_groups_frac, 8),
}
KINDS.update(KINDS_65)

FRAC_TIMES = [ftimes(k, a, n) for n in (3, 4, 5, 6, 8, 10, 12) for a in rng(1, n - 1) for k in rng(2, 6)
              if a > 1 or k > 3]
FRAC_TIMES_MIXED = [mx(f"{k} {TIMES} {a}/{n} = [{k * a}]/{n} = " + mixed_box(k * a, n), mixed(k * a, n))
                    for n in (3, 4, 5, 6, 8) for a in rng(2, n - 1) for k in rng(2, 5) if k * a > n and k * a % n]

CHECKINS["65-fractions-times-whole-numbers"] = [
    S("Groups of a fraction", None, "groups_frac", [(k, a, n) for k in (2, 3) for n in (4, 5, 6, 8) for a in (1, 2, 3)
                                                    if a < n], 1),
    S("Multiply", None, "frac3", FRAC_TIMES, 6),
    S("As a mixed number", None, "mixed2", FRAC_TIMES_MIXED, 2),
]
_g4[-1:-1] = [
    S("Fraction times a whole number", None, "frac3", FRAC_TIMES, 3, 65),
]


# ====================================================================== 66. Tenths and Hundredths


def dec(k, places=2):
    """dec(27) = "0.27", dec(3, 1) = "0.3", dec(140) = "1.40"."""
    return f"{k // 10 ** places}.{k % 10 ** places:0{places}d}"


def grid_100(bk, x, y, s, k, answer=False):
    """A whole as a 10 × 10 grid; the first k small squares shaded row by row (a full row is a tenth).
    answer=True shades them only on the key."""
    c = bk.c
    cell = s / 10
    for i in range(k):
        r, col = divmod(i, 10)
        pts = [(x + col * cell, y + s - (r + 1) * cell), (x + (col + 1) * cell, y + s - (r + 1) * cell),
               (x + (col + 1) * cell, y + s - r * cell), (x + col * cell, y + s - r * cell)]
        if answer:
            if bk.key:
                shade(bk, pts, answer=True)
        else:
            shade(bk, pts)
    c.setStrokeColor(T.muted)
    c.setLineWidth(0.5)
    for i in range(1, 10):
        c.line(x, y + i * cell, x + s, y + i * cell)
        c.line(x + i * cell, y, x + i * cell, y + s)
    c.setStrokeColor(T.ink)
    c.setLineWidth(1.3)
    c.rect(x, y, s, s, stroke=1, fill=0)


def c_read_grid(bk, x, cy, w, k):
    grid_100(bk, x + GUT, cy + 10, 76, k)
    frac_fit(bk, x + GUT + 96, cy + 42, w - GUT - 104, f"[{k}]/100 = [{dec(k)}]", size=19)


def c_read_tenths(bk, x, cy, w, k):
    strip(bk, x + GUT, cy + 15, 150, 24, 10, shaded=k)
    frac_fit(bk, x + GUT + 180, cy + 20, w - GUT - 190, f"[{k}]/10 = [{dec(k, 1)}]", size=19)


def learn_decimals(bk):
    y = bk.new_page("Tenths and Hundredths", "Cut one whole into 10 or 100 equal parts. Write it as a decimal.",
                    name_line=False, big=True, footer="WeMath  ·  Tenths and Hundredths")
    c = bk.c
    label(bk, M, y - 6, "Tenths")
    strip(bk, M + 14, y - 52, 220, 26, 10, shaded=3)
    frac_expr(bk, M + 260, y - 46, "3/10 = 0.3", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 400, y - 42, "three tenths")
    y -= 76

    label(bk, M, y - 6, "Hundredths")
    grid_100(bk, M + 14, y - 108, 96, 45)
    frac_expr(bk, M + 140, y - 54, "45/100 = 0.45", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 140, y - 82, "45 hundredths: 4 full rows (tenths) and 5 more squares.")
    c.drawString(M + 140, y - 100, "The first digit after the point is tenths, the second hundredths.")
    y -= 128

    label(bk, M, y - 6, "A tenth is 10 hundredths")
    frac_expr(bk, M + 14, y - 42, "3/10 = 30/100", size=20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 180, y - 36, "So you can add them:")
    frac_expr(bk, M + 320, y - 42, "3/10 + 45/100 = 75/100", size=18)
    y -= 66

    label(bk, M, y - 6, "Money works the same way")
    for i, kind in enumerate("DDDPPPP"):
        coin(bk, M + 30 + i * 30, y - 36, kind, k=1.0)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 250, y - 40, "3 dimes and 4 pennies: $0.34")
    y -= 70

    bottom = your_turn(bk, y, h=96)
    bk.ask("read the grid: 27 hundredths your turn")
    grid_100(bk, M + 140, bottom + 12, 72, 27)
    frac_expr(bk, M + 240, bottom + 44, "[27]/100 = [0.27]", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: tenths and hundredths as fractions and decimals (4.NF.5–6). Say “How many equal parts "
                     "make the whole? How many are shaded?” A full row of the grid is one tenth. No number lines.")


def practice_decimals(bk):
    title = "Tenths and Hundredths: Practice"
    y = bk.new_page(title, "One place after the point: tenths. Two places: hundredths.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Tenths", "Write the fraction and the decimal.", "read_tenths", [7, 2, 9, 5, 1, 6])
    part(2, "Hundredths", "Full rows are tenths. Count the rows, then the squares.", "read_grid",
         [36, 52, 8, 71, 90, 15, 63, 4])
    part(3, "Fraction to decimal", "No help this time.", "frac3",
         [f"{k}/10 = [{dec(k, 1)}]" for k in (4, 8, 1)]
         + [f"{k}/100 = [{dec(k)}]" for k in (35, 83, 4, 17, 60, 9, 48, 99, 21, 6, 70, 55)])
    part(4, "Decimal to fraction", "No help this time.", "frac3",
         [f"{dec(k, 1)} = [{k}]/10" for k in (6, 3, 9)]
         + [f"{dec(k)} = [{k}]/100" for k in (83, 27, 5, 64, 40, 11, 98, 7, 32)])
    part(5, "Tenths are hundredths too", "No help this time.", "eq2",
         [f"{dec(k, 1)} = [{10 * k}] hundredths" for k in (4, 7, 2, 9, 5, 1, 8, 6)])
    part(6, "Add tenths and hundredths", "No help this time. Make the tenths into hundredths first.", "frac2",
         [f"{a}/10 + {b}/100 = [{10 * a + b}]/100" for a, b in ((3, 45), (6, 12), (2, 7), (5, 38), (1, 61),
                                                               (7, 25), (4, 9), (8, 14))])
    part(7, "Money", "No help this time. A dime is a tenth of a dollar; a penny is a hundredth.", "eq2",
         [f"{d} dimes and {p} pennies = [${dec(10 * d + p)}]" for d, p in ((3, 4), (6, 2), (8, 3), (5, 7), (7, 5),
                                                                           (2, 9), (9, 1), (4, 6))])
    part(8, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_66)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 9, "Word problems", "Draw a grid or a strip.")
    for i, story in enumerate(WORDS_66):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 9, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_66 = ["3 × 2/5 = [6]/5", "1 3/8 + 2 2/8 = [3] [5]/8", "2/3 [<] 3/4", "84 × 12 = [1,008]",
             "5,082 ÷ 6 = [847]", "26 × 30 = [780]"]

WORDS_66 = [
    ("A garden has 100 equal squares. 37 of them have flowers. What decimal part has flowers?", "37/100 = 0.37",
     "0.37", "of the garden"),
    ("Mia ran 7/10 of a mile. Write that as a decimal.", "7/10 = 0.7", "0.7", "mile"),
    ("Ben has 4 dimes and 3 pennies. How much money is that, in dollars?", "4/10 + 3/100 = 0.43", "$0.43", ""),
    ("A jug is 6/10 full. Kim adds 25/100 of a jug more. How full is it now?", "60/100 + 25/100 = 85/100",
     "85/100", "full"),
    ("Challenge: Leo has 0.5 of a dollar. Sam has 45 hundredths of a dollar. Who has more?",
     "0.5 = 50/100 > 45/100", "Leo", ""),
]

KINDS_66 = {
    "read_grid": Kind(96, 2, lambda k: f"read the grid: {k} hundredths", c_read_grid),
    "read_tenths": Kind(56, 1, lambda k: f"read the strip: {k} tenths", c_read_tenths, 8),
}
KINDS.update(KINDS_66)

DEC_TO = ([f"{k}/10 = [{dec(k, 1)}]" for k in rng(1, 9)] + [f"{k}/100 = [{dec(k)}]" for k in rng(1, 99) if k % 10])
DEC_FROM = ([f"{dec(k, 1)} = [{k}]/10" for k in rng(1, 9)] + [f"{dec(k)} = [{k}]/100" for k in rng(1, 99) if k % 10])
DEC_ADD = [f"{a}/10 + {b}/100 = [{10 * a + b}]/100" for a in rng(1, 8) for b in rng(3, 89, 7) if 10 * a + b < 100]

CHECKINS["66-tenths-and-hundredths"] = [
    S("Hundredths", None, "read_grid", [k for k in rng(3, 97, 4) if k % 10], 2),
    S("Fraction to decimal", None, "frac3", DEC_TO, 3),
    S("Decimal to fraction", None, "frac3", DEC_FROM, 3),
    S("Add tenths and hundredths", None, "frac2", DEC_ADD, 2),
]
_g4[-1:-1] = [
    S("Tenths and hundredths", None, "frac3", DEC_TO + DEC_FROM, 3, 66),
]


# ====================================================================== 67. Comparing Decimals


def dsign(a, b):
    return "<" if a < b else ">" if a > b else "="


def dstr(k):
    """Hundredths k as the shortest decimal: 40 -> "0.4", 37 -> "0.37"."""
    return dec(k // 10, 1) if k % 10 == 0 else dec(k)


def c_compare_grids(bk, x, cy, w, item):
    a, b = item
    grid_100(bk, x + GUT, cy + 26, 62, a)
    grid_100(bk, x + GUT + 118, cy + 26, 62, b)
    bk.box(x + GUT + 72, cy + 44, 36, 28, dsign(a, b), size=18)
    for gx, k in ((x + GUT, a), (x + GUT + 118, b)):
        bk.c.setFillColor(T.ink)
        bk.c.setFont("Rnd", 13)
        bk.c.drawCentredString(gx + 31, cy + 8, dstr(k))


def c_biggest_dec(bk, x, cy, w, item):
    c = bk.c
    best = max(item)
    fx = x + GUT + 6
    for k in item:
        t = dstr(k)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 17)
        c.drawString(fx, cy + 16, t)
        tw = sw(t, "Rnd", 17)
        if bk.key and k == best:
            c.setStrokeColor(T.answer)
            c.setLineWidth(1.5)
            c.ellipse(fx - 7, cy + 6, fx + tw + 7, cy + 36, stroke=1, fill=0)
        fx += 62


def dcmp(a, b, money=False):
    pa, pb = (f"${dec(a)}", f"${dec(b)}") if money else (dstr(a), dstr(b))
    return f"{pa} [{dsign(a, b)}] {pb}"


def learn_compare_decimals(bk):
    y = bk.new_page("Comparing Decimals", "Same whole? Make both hundredths, then compare.", name_line=False,
                    big=True, footer="WeMath  ·  Comparing Decimals")
    c = bk.c
    label(bk, M, y - 6, "0.4 or 0.37?")
    grid_100(bk, M + 14, y - 104, 84, 40)
    grid_100(bk, M + 150, y - 104, 84, 37)
    bk.box(M + 105, y - 72, 38, 28, ">", size=18, reveal=T.ink)
    c.setFillColor(T.ink)
    c.setFont("Rnd", 14)
    c.drawCentredString(M + 56, y - 122, "0.4")
    c.drawCentredString(M + 192, y - 122, "0.37")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 270, y - 40, "0.4 is 4 tenths: 4 full rows.")
    c.drawString(M + 270, y - 58, "That's 40 hundredths.")
    c.drawString(M + 270, y - 76, "40 hundredths > 37 hundredths.")
    color_eq(bk, M + 270, y - 108, [("0.4", "a"), ("=", "op"), ("0.40", "a"), (">", "op"), ("0.37", "b")], 20)
    y -= 146

    label(bk, M, y - 6, "Longer is not always bigger")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 30, "0.37 has more digits than 0.4, but fewer hundredths.")
    c.drawString(M + 14, y - 48, "Compare the tenths first. If they match, compare the hundredths.")
    color_eq(bk, M + 14, y - 80, [("0.65", "a"), ("<", "op"), ("0.68", "b")], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 160, y - 76, "Same tenths (6), so look at the hundredths.")
    y -= 104

    label(bk, M, y - 6, "Money helps")
    color_eq(bk, M + 14, y - 40, [("$0.50", "a"), (">", "op"), ("$0.45", "b")], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 170, y - 36, "5 dimes is more than 4 dimes and 5 pennies.")
    y -= 64

    bottom = your_turn(bk, y, h=82)
    bk.ask("compare decimals: 0.3 and 0.29 your turn")
    bk.eq(M + 150, bottom + 32, "0.3 [>] 0.29", size=24)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 330, bottom + 36, "Write 0.3 as hundredths first.")
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: compare decimals to hundredths (4.NF.7). Say “How many hundredths is each one?” "
                     "Watch for the mix-up that 0.37 > 0.4 because it is longer.")


def practice_compare_decimals(bk):
    title = "Comparing Decimals: Practice"
    y = bk.new_page(title, "Same whole. Write <, > or =.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Compare with grids", "Which grid has more shaded?", "compare_grids",
         [(50, 46), (28, 30), (73, 70), (60, 66), (9, 20), (85, 58)])
    part(2, "Make them hundredths", "Write the tenths as hundredths, then compare.", "eq2",
         [f"{dstr(a)} = [{dec(a)}] so {dstr(a)} [{dsign(a, b)}] {dstr(b)}" for a, b in
          ((60, 58), (30, 34), (70, 69), (20, 21), (80, 85), (50, 49), (90, 91), (10, 7))])
    part(3, "Compare", "No help this time.", "eq3",
         [dcmp(a, b) for a, b in ((64, 59), (33, 38), (40, 4), (72, 27), (15, 50), (90, 89), (61, 16), (25, 30),
                                    (8, 80), (44, 40), (57, 75), (99, 90), (12, 21), (30, 3), (68, 86))])
    part(4, "Money", "No help this time.", "eq3",
         [dcmp(a, b, money=True) for a, b in ((45, 54), (90, 85), (30, 3), (65, 56), (20, 19), (7, 70))])
    part(5, "Circle the biggest", "No help this time.", "biggest_dec",
         [(40, 37, 9), (52, 60, 25), (18, 81, 80), (70, 7, 69), (33, 30, 39), (5, 50, 45)])
    part(6, "Fractions and decimals", "No help this time.", "frac3",
         ["3/10 [<] 0.35", "0.6 [=] 60/100", "45/100 [>] 0.4", "0.09 [<] 1/10", "7/10 [>] 0.68", "0.5 [=] 1/2",
          "0.25 [<] 3/10", "8/10 [>] 0.79"])
    part(7, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_67)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Draw grids if it helps.")
    for i, story in enumerate(WORDS_67):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_67 = ["47/100 = [0.47]", "0.3 = [30] hundredths", "4 × 2/3 = [8]/3", "3 2/5 − 1 1/5 = [2] [1]/5",
             "53 × 24 = [1,272]", "2,856 ÷ 7 = [408]"]

WORDS_67 = [
    ("Mia ran 0.6 of a mile. Ben ran 0.58 of a mile. Who ran farther?", "0.6 = 0.60 > 0.58", "Mia", ""),
    ("A red pencil is 0.15 of a meter long. A blue one is 0.2 of a meter. Which is longer?", "0.15 < 0.20",
     "blue", "pencil"),
    ("Kim has $0.75. A toy costs $0.80. Does she have enough money?", "0.75 < 0.80", "no", ""),
    ("Leo's jug is 0.5 full. Sam's same jug is 0.50 full. Who has more?", "0.5 = 0.50", "same", ""),
    ("Challenge: Put 0.4, 0.38 and 0.09 in order from smallest to biggest.", "0.09 < 0.38 < 0.40",
     "0.09, 0.38, 0.4", ""),
]

KINDS_67 = {
    "compare_grids": Kind(96, 2, lambda it: f"compare grids: {dstr(it[0])} and {dstr(it[1])}", c_compare_grids),
    "biggest_dec": Kind(48, 2, lambda it: "biggest decimal: " + " ".join(dstr(k) for k in it), c_biggest_dec, 8),
}
KINDS.update(KINDS_67)
BALANCE["compare_grids"] = lambda it: it[0] < it[1]

DEC_CMP = [dcmp(a, b) for a in rng(3, 97, 7) for b in rng(2, 98, 9) if a != b and abs(a - b) < 40]

CHECKINS["67-comparing-decimals"] = [
    S("Compare with grids", None, "compare_grids", [(a, b) for a in rng(15, 85, 10) for b in (a - 4, a + 6, a // 10 * 10)
                                                   if b != a and 0 < b < 100], 2),
    S("Compare", "Write <, > or =.", "eq3", DEC_CMP, 6, balance=is_less),
    S("Circle the biggest", None, "biggest_dec", [(a, b, c) for a, b, c in ((38, 40, 9), (60, 55, 7), (8, 27, 30),
                                                                            (68, 9, 70), (15, 20, 3), (79, 8, 80))],
      2),
]
_g4[-1:-1] = [
    S("Compare decimals", "Write <, > or =.", "eq3", DEC_CMP, 3, 67, balance=is_less),
]


# ====================================================================== 68. Measurement Conversions


CONV = {("m", "cm"): 100, ("km", "m"): 1000, ("kg", "g"): 1000, ("L", "mL"): 1000, ("ft", "in"): 12,
        ("yd", "ft"): 3, ("yd", "in"): 36, ("lb", "oz"): 16, ("hr", "min"): 60, ("min", "sec"): 60,
        ("week", "day"): 7, ("day", "hr"): 24}


def unit_plural(u, n):
    """Plural for the units that are words (3 weeks, 2 days); abbreviations stay the same."""
    return {"week": "weeks", "day": "days"}.get(u, u) if n != 1 else u


def conv_eq(n, big, small):
    m = n * CONV[(big, small)]
    return f"{n} {unit_plural(big, n)} = [{nf(m)}] {unit_plural(small, m)}"


def c_conv_table(bk, x, cy, w, item):
    """A conversion table: the big unit on the left, the small unit on the right; the first row is given."""
    big, small, ns = item[:3]
    given = len(item) > 3 and item[3]
    c = bk.c
    f = CONV[(big, small)]
    cw, rh = 80, 22
    tx, top = x + GUT + 10, cy + 20 + rh * (len(ns) + 1)
    c.setStrokeColor(T.line)
    c.setLineWidth(0.8)
    for i in range(len(ns) + 2):
        c.line(tx, top - i * rh, tx + 2 * cw, top - i * rh)
    for j in range(3):
        c.line(tx + j * cw, top, tx + j * cw, top - (len(ns) + 1) * rh)
    c.setFillColor(T.ink)
    c.setFont("AvB", 12)
    c.drawCentredString(tx + cw / 2, top - rh + 7, big)
    c.drawCentredString(tx + 1.5 * cw, top - rh + 7, small)
    for i, n in enumerate(ns):
        yy = top - (i + 2) * rh
        c.setFillColor(T.ink)
        c.setFont("Rnd", 13)
        c.drawCentredString(tx + cw / 2, yy + 6, str(n))
        v = nf(n * f)
        if i == 0 or given:
            c.setFillColor(T.ink)
            c.setFont("Rnd", 13)
            c.drawCentredString(tx + 1.5 * cw, yy + 6, v)
        else:
            bw = max(40, sw(v, "Rnd", 13) + 12)
            bk.box(tx + 1.5 * cw - bw / 2, yy + 2, bw, rh - 4, v, size=12)


def learn_conversions(bk):
    y = bk.new_page("Measurement Conversions", "A big unit holds many small units. Multiply to change units.",
                    name_line=False, big=True, footer="WeMath  ·  Measurement Conversions")
    c = bk.c
    label(bk, M, y - 6, "1 meter is 100 centimeters")
    color_eq(bk, M + 14, y - 42, [("3 m", "a"), ("=", "op"), ("3 × 100", None), ("=", "op"), ("300 cm", "b")], 20)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 330, y - 38, "Big unit to small unit: multiply.")
    y -= 64

    label(bk, M, y - 6, "Make a table")
    c_conv_table(bk, M - GUT - 10 + 14, y - 176, 300, ("ft", "in", (1, 2, 3, 4, 5), True))
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 220, y - 40, "1 foot = 12 inches.")
    c.drawString(M + 220, y - 58, "Each row adds 12 more.")
    c.drawString(M + 220, y - 76, "5 ft = 5 × 12 = 60 in.")
    y -= 172

    label(bk, M, y - 6, "Units to know")
    rows = ("1 km = 1,000 m      1 m = 100 cm      1 kg = 1,000 g      1 L = 1,000 mL",
            "1 yd = 3 ft      1 ft = 12 in      1 lb = 16 oz",
            "1 hr = 60 min      1 min = 60 sec      1 day = 24 hr      1 week = 7 days")
    for i, r in enumerate(rows):
        c.setFillColor(T.ink)
        c.setFont("Rnd", 12)
        c.drawString(M + 14, y - 32 - i * 20, r)
    y -= 100

    label(bk, M, y - 6, "Mixed units")
    color_eq(bk, M + 14, y - 40, [("2 m 35 cm", "a"), ("=", "op"), ("200 cm + 35 cm", None), ("=", "op"),
                                  ("235 cm", "b")], 18)
    y -= 62

    bottom = your_turn(bk, y, h=70)
    bk.ask("conversion: 4 ft your turn")
    bk.eq(M + 150, bottom + 26, "4 ft = [48] in", size=22)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: change a bigger unit into a smaller one and solve measurement word problems "
                     "(4.MD.1–2). Say “How many small units in one big unit? Then how many in 3?” Make a table.")


def practice_conversions(bk):
    title = "Measurement Conversions: Practice"
    y = bk.new_page(title, "Big unit to small unit: multiply by how many fit in one.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Fill in the table", "The first row is done.", "conv_table",
         [("m", "cm", (1, 2, 4, 6, 9)), ("yd", "ft", (1, 3, 5, 7, 10)), ("lb", "oz", (1, 2, 3, 5, 8)),
          ("hr", "min", (1, 2, 4, 5, 10))])
    part(2, "Metric units", "No help this time.", "eq3",
         [conv_eq(n, b, s) for n, b, s in ((4, "m", "cm"), (3, "kg", "g"), (5, "L", "mL"), (2, "km", "m"),
                                           (7, "m", "cm"), (9, "kg", "g"), (6, "km", "m"), (8, "L", "mL"),
                                           (12, "m", "cm"), (4, "kg", "g"), (3, "L", "mL"), (10, "km", "m"))])
    part(3, "Feet, pounds and time", "No help this time.", "eq3",
         [conv_eq(n, b, s) for n, b, s in ((3, "ft", "in"), (4, "yd", "ft"), (2, "lb", "oz"), (5, "min", "sec"),
                                           (3, "hr", "min"), (2, "yd", "in"), (6, "ft", "in"), (3, "week", "day"),
                                           (4, "lb", "oz"), (2, "day", "hr"), (8, "yd", "ft"), (7, "min", "sec"))])
    part(4, "Mixed units", "No help this time. Change the big unit, then add.", "eq2",
         ["3 m 42 cm = [342] cm", "1 kg 250 g = [1,250] g",
          "3 ft 4 in = [40] in", "2 hr 15 min = [135] min", "4 m 8 cm = [408] cm", "2 L 600 mL = [2,600] mL",
          "5 ft 6 in = [66] in", "1 hr 45 min = [105] min", "2 yd 1 ft = [7] ft", "3 lb 5 oz = [53] oz"])
    part(5, "Which is more?", "No help this time. Change to the same unit first.", "eq3",
         ["3 ft [<] 40 in", "2 m [>] 150 cm", "1 kg [<] 1,200 g", "5 yd [>] 14 ft", "2 hr [>] 100 min",
          "3 L [=] 3,000 mL", "2 lb [<] 40 oz", "4 min [>] 200 sec"])
    part(6, "Add and take away", "No help this time. Use the small unit.", "eq2",
         [f"1 L {MINUS} 350 mL = [650] mL", "2 m + 45 cm = [245] cm", f"3 ft {MINUS} 8 in = [28] in",
          "1 hr + 25 min = [85] min", f"1 kg {MINUS} 375 g = [625] g", "2 yd + 2 ft = [8] ft",
          f"1 km {MINUS} 400 m = [600] m", "1 lb + 9 oz = [25] oz"])
    part(7, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_68)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Change to the same unit first.")
    for i, story in enumerate(WORDS_68):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_68 = ["0.7 [>] 0.65", "38/100 = [0.38]", "5 × 3/4 = [15]/4", "2 5/6 + 1 3/6 = [4] [2]/6",
             "36 × 25 = [900]", "4,568 ÷ 8 = [571]"]

WORDS_68 = [
    ("A rope is 3 m long. Leo cuts off 75 cm. How long is the rope now, in centimeters?",
     f"300 cm {MINUS} 75 cm = 225 cm", "225", "cm"),
    ("A movie is 2 hours long. Ana has watched 85 minutes. How many minutes are left?",
     f"120 {MINUS} 85 = 35", "35", "minutes"),
    ("A bag of apples weighs 2 kg. Each apple is about 200 g. About how many apples are in the bag?",
     f"2,000 {DIV} 200 = 10", "10", "apples"),
    ("Mia drinks 250 mL of milk each day. How much does she drink in a week?", f"7 {TIMES} 250 = 1,750",
     "1,750", "mL"),
    ("A desk is 4 ft long. A shelf is 50 in long. Which is longer?", "4 ft = 48 in < 50 in", "shelf", ""),
    ("Challenge: Ben runs 400 m around the track 6 times. Is that more than 2 km?",
     f"6 {TIMES} 400 = 2,400 m > 2,000 m", "yes", ""),
]

KINDS_68 = {
    "conv_table": Kind(156, 2, lambda it: f"conversion table: {it[0]} to {it[1]}: " + "-".join(map(str, it[2])),
                       c_conv_table),
}
KINDS.update(KINDS_68)

CONV_POOL = [conv_eq(n, b, s) for (b, s) in CONV for n in rng(2, 12)]
MIXED_UNITS = ([f"{a} m {b} cm = [{100 * a + b}] cm" for a in rng(1, 6) for b in (5, 12, 27, 48, 60, 83)]
               + [f"{a} ft {b} in = [{12 * a + b}] in" for a in rng(1, 6) for b in (1, 3, 5, 7, 9, 11)]
               + [f"{a} hr {b} min = [{60 * a + b}] min" for a in rng(1, 4) for b in (10, 20, 35, 40, 50)])

CHECKINS["68-measurement-conversions"] = [
    S("Fill in the table", None, "conv_table", [(b, s, (1, 2, 3, 6, 8)) for (b, s) in CONV], 1),
    S("Change the unit", None, "eq3", CONV_POOL, 6),
    S("Mixed units", None, "eq2", MIXED_UNITS, 2),
]
_g4[-1:-1] = [
    S("Measurement conversions", None, "eq3", CONV_POOL, 3, 68),
]


# ====================================================================== 69. Area and Perimeter Formulas


def area_f(l, w, u):
    return f"area: {l} {TIMES} {w} = [{nf(l * w)}] sq {u}"


def perim_f(l, w, u):
    return f"perimeter: 2 {TIMES} {l} + 2 {TIMES} {w} = [{2 * (l + w)}] {u}"


def c_rect_formula(bk, x, cy, w, item):
    """A labelled rectangle (not to scale beyond its shape) with the area and perimeter formulas beside it."""
    l, wd, u = item
    rw = 96 if l >= wd else 60
    rh = 60 if l >= wd else 90
    rect_sides(bk, x + GUT + 10, cy + 22, rw, min(rh, 66), f"{l} {u}", "", "", f"{wd} {u}", size=11)
    tx = x + GUT + 160
    bk.fit_eq(tx, cy + 62, w - (tx - x) - 10, area_f(l, wd, u), size=16)
    bk.fit_eq(tx, cy + 24, w - (tx - x) - 10, perim_f(l, wd, u), size=16)


def learn_area_formulas(bk):
    y = bk.new_page("Area and Perimeter Formulas", "Area: length × width. Perimeter: all the way around.",
                    name_line=False, big=True, footer="WeMath  ·  Area and Perimeter Formulas")
    c = bk.c
    label(bk, M, y - 6, "A rectangle 8 m long and 5 m wide")
    rect_sides(bk, M + 30, y - 110, 160, 80, "8 m", "5 m", "8 m", "5 m", size=12)
    color_eq(bk, M + 250, y - 46, [("Area:", None), ("8 × 5", "a"), ("=", "op"), ("40 sq m", None)], 18)
    color_eq(bk, M + 250, y - 80, [("Perimeter:", None), ("8 + 5 + 8 + 5", "b"), ("=", "op"), ("26 m", None)], 18)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 250, y - 104, "or 2 × 8 + 2 × 5 = 26: two long sides, two short.")
    y -= 140

    label(bk, M, y - 6, "Find a missing side from the area")
    color_eq(bk, M + 14, y - 42, [("8 cm × ? cm", "a"), ("=", "op"), ("48 sq cm", None)], 18)
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 270, y - 38, "48 ÷ 8 = 6, so the width is 6 cm.")
    y -= 66

    label(bk, M, y - 6, "Find a missing side from the perimeter")
    c.setFillColor(T.text2)
    c.setFont("Rnd", 12)
    c.drawString(M + 14, y - 32, "Perimeter 30 ft, length 9 ft.")
    c.drawString(M + 14, y - 50, "The two lengths are 18 ft, so the two widths are 30 minus 18 = 12 ft.")
    c.drawString(M + 14, y - 68, "One width is half of 12: 6 ft.")
    y -= 92

    bottom = your_turn(bk, y, h=100)
    bk.ask("area and perimeter: 7 by 4 your turn")
    rect_sides(bk, M + 140, bottom + 24, 100, 56, "7 in", "", "", "4 in", size=11)
    bk.eq(M + 290, bottom + 62, "area: [28] sq in", size=17)
    bk.eq(M + 290, bottom + 28, "perimeter: [22] in", size=17)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: area = length × width and perimeter = 2 × length + 2 × width, also to find a missing side (4.MD.3). It is "
                     "packets 38 and 45 without the squares. Say “Area covers it; perimeter walks around it.”")


def practice_area_formulas(bk):
    title = "Area and Perimeter Formulas: Practice"
    y = bk.new_page(title, "Area in square units, perimeter in units.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Both formulas", "Two sides are labelled. The other two match them.", "rect_formula",
         [(12, 5, "cm"), (9, 7, "m"), (15, 4, "ft"), (6, 6, "in"), (20, 3, "yd"), (11, 8, "m")])
    part(2, "Area", "No help this time.", "eq2",
         [area_f(l, w, u) for l, w, u in ((14, 6, "m"), (23, 4, "cm"), (18, 10, "ft"), (25, 3, "in"), (16, 7, "yd"),
                                          (32, 5, "m"), (12, 12, "cm"), (40, 6, "ft"), (19, 8, "in"), (45, 2, "m"))])
    part(3, "Perimeter", "No help this time.", "eq2",
         [perim_f(l, w, u) for l, w, u in ((14, 6, "m"), (23, 4, "cm"), (18, 10, "ft"), (25, 3, "in"),
                                           (16, 7, "yd"), (32, 5, "m"), (30, 20, "cm"), (40, 6, "ft"),
                                           (19, 8, "in"), (45, 2, "m"))])
    part(4, "Missing side from the area", "No help this time. Divide.", "eq2",
         [f"{a} {u} {TIMES} [{A // a}] {u} = {A} sq {u}" for A, a, u in ((54, 9, "cm"), (72, 8, "m"), (65, 5, "ft"),
                                                                       (84, 7, "in"), (96, 12, "yd"),
                                                                       (120, 10, "m"), (91, 7, "cm"),
                                                                       (150, 15, "ft"))])
    part(5, "Missing side from the perimeter", "No help this time. Take away both lengths, then halve it.", "eq1",
         [f"P = {2 * (l + w)} {u}, length {l} {u}: width = [{w}] {u}" for l, w, u in
          ((9, 6, "ft"), (12, 4, "m"), (15, 10, "cm"), (20, 5, "in"), (8, 7, "yd"), (25, 15, "m"))])
    part(6, "Squares", "No help this time. All four sides match.", "eq2",
         [f"square, side {s} {u}: A = [{s * s}] sq {u}" for s, u in ((9, "in"), (11, "m"), (15, "cm"))]
         + [f"square, side {s} {u}: P = [{4 * s}] {u}" for s, u in ((9, "in"), (11, "m"), (15, "cm"))])
    part(7, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_69)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 8, "Word problems", "Draw the rectangle and label the sides.")
    for i, story in enumerate(WORDS_69):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 8, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_69 = ["8 ft = [96] in", "7 kg = [7,000] g", "0.45 [<] 0.5",
             "29/100 = [0.29]", "3 × 4/5 = [12]/5", "64 × 32 = [2,048]"]

WORDS_69 = [
    ("A garden is 15 m long and 8 m wide. How much fence goes all the way around it?",
     f"2 {TIMES} 15 + 2 {TIMES} 8 = 46", "46", "m"),
    ("A rug is 11 ft long and 6 ft wide. What is its area?", f"11 {TIMES} 6 = 66", "66", "sq ft"),
    ("A poster has an area of 72 sq in. It is 9 in wide. How long is it?", f"72 {DIV} 9 = 8", "8", "in"),
    ("A square room has sides of 12 ft. How much carpet covers the floor?", f"12 {TIMES} 12 = 144", "144", "sq ft"),
    ("Challenge: A pen has 40 m of fence around it. It is 12 m long. How wide is it?",
     f"40 {MINUS} 24 = 16, 16 {DIV} 2 = 8", "8", "m"),
]

KINDS_69 = {
    "rect_formula": Kind(96, 1, lambda it: f"both formulas: {it[0]} {it[2]} by {it[1]} {it[2]}", c_rect_formula, 8),
    "eq1": Kind(44, 1, lambda t: t, c_eq, 8),
}
KINDS.update(KINDS_69)

AREA_F = [area_f(l, w, u) for l in rng(11, 49, 3) for w in rng(3, 9) for u in ("cm", "m") if (l + w) % 3 == 0]
PERIM_F = [perim_f(l, w, u) for l in rng(11, 49, 3) for w in rng(3, 9) for u in ("ft", "in") if (l + w) % 3 == 1]
MISSING_A = [f"{a} m {TIMES} [{b}] m = {a * b} sq m" for a in rng(6, 12) for b in rng(6, 12) if a != b]

CHECKINS["69-area-and-perimeter-formulas"] = [
    S("Both formulas", None, "rect_formula", [(l, w, "m") for l in rng(10, 16) for w in (3, 4, 6)], 1),
    S("Area", None, "eq2", AREA_F, 2),
    S("Perimeter", None, "eq2", PERIM_F, 2),
    S("Missing side", None, "eq2", MISSING_A, 2),
    S("Missing side from the perimeter", None, "eq1", [f"P = {2 * (l + w)} m, length {l} m: width = [{w}] m"
                                                        for l in rng(10, 30, 4) for w in rng(3, 9)], 2),
]
_g4[-1:-1] = [
    S("Area and perimeter", None, "eq2", AREA_F[::2] + PERIM_F[::2], 2, 69),
]


# ====================================================================== 70. Line Plots with Fractions


def e8(k):
    """k eighths as a label: 5 -> "5/8", 8 -> "1", 11 -> "1 3/8"."""
    q, r = divmod(k, 8)
    if not q:
        return f"{r}/8"
    return f"{q} {r}/8" if r else str(q)


def c_make_x8(bk, x, cy, w, item):
    """Lengths in eighths on the left; an empty X chart to fill in on the right."""
    title, lengths = item
    c = bk.c
    c.setFillColor(T.ink)
    c.setFont("AvD", 10.5)
    c.drawString(x + GUT, cy + 148, title)
    for i, k in enumerate(lengths):
        col, row = divmod(i, 4)
        c.setFillColor(T.ink)
        c.setFont("Rnd", 12)
        c.drawString(x + GUT + col * 52, cy + 120 - row * 24, f"{e8(k)} in")
    span = list(range(min(lengths), max(lengths) + 1))
    x_chart(bk, x + GUT + 168, cy + 168, "Make the X chart (inches)", [e8(k) for k in span],
            [lengths.count(k) for k in span], colw=36, show=False)


def x8_questions(lengths, seed):
    span = list(range(min(lengths), max(lengths) + 1))
    r = random.Random(seed)
    common = max(span, key=lengths.count)
    one = r.choice([k for k in span if lengths.count(k)])
    return [(f"How many are {e8(one)} in?", lengths.count(one)),
            ("Longest minus shortest?", e8(max(lengths) - min(lengths))),
            (f"All the {e8(common)} in ones together?", e8(common * lengths.count(common))),
            ("How many in all?", len(lengths))]


def c_read_x8(bk, x, cy, w, item):
    title, lengths, seed = item
    span = list(range(min(lengths), max(lengths) + 1))
    x_chart(bk, x + GUT + 6, cy + 168, title, [e8(k) for k in span], [lengths.count(k) for k in span], colw=36)
    graph_questions(bk, x + GUT + 250, cy + 140, w - GUT - 262, x8_questions(lengths, seed))


def learn_line_plots(bk):
    y = bk.new_page("Line Plots with Fractions", "Put an X for each one. Then add and take away fractions.",
                    name_line=False, big=True, footer="WeMath  ·  Line Plots with Fractions")
    c = bk.c
    lengths = [6, 7, 7, 8, 9, 9, 9, 11]
    label(bk, M, y - 6, "8 bugs, measured to the eighth of an inch")
    for i, k in enumerate(lengths):
        c.setFillColor(T.ink)
        c.setFont("Rnd", 13)
        c.drawString(M + 14 + (i % 4) * 54, y - 36 - (i // 4) * 22, f"{e8(k)} in")
    span = list(range(6, 12))
    x_chart(bk, M + 260, y - 22, "Bug lengths (inches)", [e8(k) for k in span], [lengths.count(k) for k in span],
            colw=40)
    y -= 128

    label(bk, M, y - 6, "Questions you can answer")
    lines = (("Longest minus shortest:", "1 3/8 − 6/8 = 5/8 in"),
             ("All the 1 1/8 in bugs end to end:", "3 × 1 1/8 = 3 3/8 in"),
             ("How many are shorter than 1 in?", "3 bugs"))
    for i, (q, a) in enumerate(lines):
        c.setFillColor(T.text2)
        c.setFont("Rnd", 12)
        c.drawString(M + 14, y - 34 - i * 30, q)
        frac_expr(bk, M + 250, y - 36 - i * 30, a.replace("−", MINUS), size=15)
    y -= 128

    bottom = your_turn(bk, y, h=92)
    bk.ask("x chart eighths your turn")
    c.setFillColor(T.ink)
    c.setFont("Rnd", 13)
    c.drawString(M + 130, bottom + 56, "Longest 1 2/8 in, shortest 5/8 in.")
    frac_expr(bk, M + 130, bottom + 22, f"1 2/8 {MINUS} 5/8 = [5]/8", size=20)
    if bottom < 112:
        print(f"WARNING: learning page content ends at y={bottom:.0f}, under the teacher note")
    teacher_note(bk, "Goal: X charts (line plots) of measurements in halves, quarters and eighths, then add and "
                     "subtract the fractions to answer questions (4.MD.4). Say “Find the biggest and smallest X "
                     "first.”")


def practice_line_plots(bk):
    title = "Line Plots with Fractions: Practice"
    y = bk.new_page(title, "One X for each measurement.")
    num = 1

    def part(n, name, sub, kind, items):
        nonlocal y, num
        k = KINDS[kind]
        y, num = flow(bk, title, y, n, name, sub, items, num, k.cols, k.h, k.gap,
                      lambda x, cy, w, it: (bk.ask(k.key(it)), k.draw(bk, x, cy, w, it)))

    part(1, "Make the X chart", "Put an X above the length for each one.", "make_x8",
         [("Ribbon pieces", [5, 6, 6, 7, 7, 7, 9, 9]), ("Leaves", [9, 10, 10, 12, 12, 12, 13, 14]),
          ("Snails", [3, 4, 4, 4, 5, 7, 7, 8])])
    part(2, "Read the X chart", "Answer the questions.", "read_x8",
         [("Feathers (inches)", [8, 9, 9, 10, 10, 10, 12, 13], 1), ("Shells (inches)", [4, 5, 5, 5, 6, 8, 8, 9], 2),
          ("Pencils (inches)", [17, 18, 18, 19, 20, 20, 20, 22], 3)])
    part(3, "Add the X's", "No help this time. Same length, many times.", "frac2",
         [f"{n} {TIMES} {e8(k)} = [{n * k}]/8" for n, k in ((3, 3), (4, 5), (5, 3), (5, 2), (3, 6), (6, 1), (2, 5),
                                                             (3, 7))])
    part(4, "How far apart?", "No help this time. Longest minus shortest.", "mixed2",
         [mx(f"{e8(a)} {MINUS} {e8(b)} = " + (f"[{a - b}]/8" if a - b < 8 else mixed_box(a - b, 8)), e8(a - b))
          for a, b in ((13, 6), (15, 4), (11, 4), (14, 9), (20, 7), (10, 5), (17, 2), (12, 10))])
    part(5, "Put them together", "No help this time. Two pieces end to end.", "mixed2",
         [mx(f"{e8(a)} + {e8(b)} = " + (f"[{a + b}]/8" if a + b < 8 else mixed_box(a + b, 8)), e8(a + b))
          for a, b in ((9, 4), (5, 6), (10, 11), (3, 2), (12, 7), (6, 9), (17, 3), (1, 5))])
    part(6, "Remember?", "Problems from earlier packets.", "rev2", REVIEW_70)

    if y - 14 - 110 < 46:
        y = bk.new_page(title, first=False)
    y = bk.part(y, 7, "Word problems", "Use eighths.")
    for i, story in enumerate(WORDS_70):
        if y - 110 < 46:
            y = bk.new_page(title, first=False)
            y = bk.part(y, 7, "Word problems", "(continued)")
        y = word_card(bk, y, num + i, *story)


REVIEW_70 = ["area: 13 × 6 = [78] sq m", "5 ft = [60] in", "0.8 [>] 0.75", "5 × 3/10 = [15]/10",
             "3 1/8 − 1 2/8 = [1] [7]/8", "75 × 12 = [900]"]

WORDS_70 = [
    ("Two worms are 1 4/8 in and 7/8 in long. How much longer is the first one?", f"1 4/8 {MINUS} 7/8 = 5/8",
     "5/8", "in"),
    ("Four beads are each 3/8 in long. How long are they in a row?", f"4 {TIMES} 3/8 = 12/8 = 1 4/8", "1 4/8",
     "in"),
    ("Ana's X chart shows 3 X's at 5/8 in and 2 X's at 7/8 in. How many things did she measure?", "3 + 2 = 5",
     "5", "things"),
    ("A ribbon is 2 1/8 in. Another is 1 4/8 in. How long are they together?", "2 1/8 + 1 4/8 = 3 5/8", "3 5/8",
     "in"),
    ("Challenge: The longest leaf is 1 7/8 in and the shortest is 6/8 in. How far apart are they?",
     f"1 7/8 {MINUS} 6/8 = 1 1/8", "1 1/8", "in"),
]

KINDS_70 = {
    "make_x8": Kind(176, 1, lambda it: f"make the x chart: {it[0]}", c_make_x8, 10),
    "read_x8": Kind(176, 1, lambda it: f"read the x chart: {it[0]}", c_read_x8, 10),
}
KINDS.update(KINDS_70)

X8_TIMES = [f"{n} {TIMES} {e8(k)} = [{n * k}]/8" for n in rng(2, 6) for k in rng(1, 7)]
X8_APART = [mx(f"{e8(a)} {MINUS} {e8(b)} = " + (f"[{a - b}]/8" if a - b < 8 else mixed_box(a - b, 8)), e8(a - b))
            for a in rng(9, 19, 2) for b in rng(2, 8) if (a - b) % 8]

CHECKINS["70-line-plots-with-fractions"] = [
    S("Read the X chart", None, "read_x8", [("Crayons (inches)", [10, 11, 11, 12, 12, 12, 14, 15], 7),
                                            ("Sticks (inches)", [5, 6, 6, 6, 7, 9, 9, 10], 8)], 1),
    S("Add the X's", None, "frac2", X8_TIMES, 3),
    S("How far apart?", None, "mixed2", X8_APART, 3),
]
_g4[-1:-1] = [
    S("Line plot questions", None, "mixed2", X8_APART, 2, 70),
]


# ====================================================================== curriculum.json (for the website)
# Every check-in and assessment question, numbered as printed, with the packet it checks and its answer,
# so tutors can mark them question by question online and the site can recommend packets. Written by every
# full build, so it always matches the PDFs.

import hashlib
import json

# Teaching order (packets 23–25 slot in earlier, see CLAUDE.md).
TEACHING_ORDER = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 23, 12, 13, 14, 15, 16, 24, 17, 18, 19, 20, 21, 22, 25,
                  26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50,
                  51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70]
GRADE_CODE = {"kindergarten": "K", "grade-1": "1", "grade-2": "2", "grade-3": "3", "grade-4": "4"}

# Cards whose key circles a choice (no answer box): the answer in words.
_yes = lambda b: "yes" if b else "no"
ANSWER_OF = {
    "buddy_yesno": lambda it: _yes(it[1]),
    "enough": lambda it: _yes(it[0] % 10 >= it[1] % 10),
    "which_more": lambda it: str(max(it)),
    "eq_groups": lambda it: _yes(len(set(it)) == 1),
    "pairs_eo": lambda n: "even" if n % 2 == 0 else "odd",
    "eo_ones": lambda n: "even" if n % 2 == 0 else "odd",
    "eq_share": lambda it: _yes(it[2]),
    "name_share": lambda it: SHARE_NAME[it[1]][0],
    "bigger_share": lambda it: share_word(min(it[1], it[2])),
    "shade": lambda it: f"{it[2]} of {it[1]} parts shaded",
    "ampm": lambda it: it[1],
    "symbol": lambda it: it[1],
    "unit_choice": lambda it: it[2],
    "draw_hands": lambda it: f"hands at {tstr(it[0], it[1])}",
    "tally_draw": lambda n: f"{n} tally marks",
    "show_amount": lambda a: " ".join(COIN[k][2] for k in greedy(a)),
    "round_card": lambda it: nf(round_to(it[0], it[1])),
    "unit_name": lambda it: f"1/{it[1]}",
    "shade_unit": lambda it: f"1 of {it[1]} parts shaded",
    "find_whole": lambda n: f"{n} pieces",
    "bigger_unit": lambda it: f"1/{min(it[0], it[1])}",
    "bigger_unit_plain": lambda it: f"1/{min(it[0], it[1])}",
    "count_pieces": lambda it: f"{it[2]}/{it[1]}",
    "frac_name": lambda it: f"{it[2]}/{it[1]}",
    "frac_shade": lambda it: f"{it[2]} of {it[1]} parts shaded",
    "shaded_not": lambda it: f"{it[2]}/{it[1]} shaded, {it[1] - it[2]}/{it[1]} not",
    "one_whole": lambda it: f"{it[1]}/{it[1]} = 1",
    "wholes": lambda it: f"{it[0] * it[1]}/{it[0]} = {it[1]}",
    "more_whole": lambda it: f"{it[1]}/{it[0]} = " + whole_text(it[1], it[0]).replace('[', '').replace(']', ''),
    "shade_more": lambda it: f"{it[1]} of the {it[0]}-part pieces shaded",
    "vs_one": lambda it: one_side(it[0], it[1]),
    "same_amount": lambda it: _yes(it[0] * it[3] == it[1] * it[2]),
    "match_frac": lambda it: f"{it[0][0] * it[1] // it[0][1]}/{it[1]}",
    "compare_frac": lambda it: frac_sign(*it[0], *it[1]),
    "compare_shapes": lambda it: frac_sign(*it[1], *it[2]),
    "biggest": lambda it: "%d/%d" % max(it, key=lambda f: Fraction(*f)),
    "area2": lambda it: nf(it[0] * it[1]),
    "partial2": lambda it: nf(it[0] * it[1]),
    "div_area": lambda it: nf(it[0] // it[1]),
    "partial_q": lambda it: nf(it[0] // it[1]),
    "factor_array": lambda it: f"{it[0]} × {it[1]}",
    "yes_text": lambda it: _yes(it[1]),
    "prime": lambda n: "prime" if is_prime(n) else "composite",
    "cut_strip": lambda it: f"{it[0] * it[2]}/{it[1] * it[2]}",
    "equal_q": lambda it: _yes(it[0][0] * it[1][1] == it[0][1] * it[1][0]),
    "vs_half": lambda it: half_side(it[0], it[1]),
    "smallest": lambda it: "%d/%d" % min(it, key=lambda f: Fraction(*f)),
    "add_strip": lambda it: f"{it[0] + it[1] if it[3] == chr(43) else it[0] - it[1]}/{it[2]}",
    "to_mixed": lambda it: f"{it[1]}/{it[0]} = " + mixed(it[1], it[0]),
    "mixed3": lambda it: it[1],
    "mixed2": lambda it: it[1],
    "mixed1": lambda it: it[1],
    "groups_frac": lambda it: f"{it[0] * it[1]}/{it[2]}",
    "read_grid": lambda k: f"{k}/100 = {dec(k)}",
    "read_tenths": lambda k: f"{k}/10 = {dec(k, 1)}",
    "compare_grids": lambda it: dsign(it[0], it[1]),
    "biggest_dec": lambda it: dstr(max(it)),
    "conv_table": lambda it: ", ".join(f"{n} {it[0]} = {nf(n * CONV[(it[0], it[1])])} {it[1]}" for n in it[2][1:]),
    "rect_formula": lambda it: f"area {nf(it[0] * it[1])} sq {it[2]}, perimeter {2 * (it[0] + it[1])} {it[2]}",
    "make_x8": lambda it: "X chart: " + ", ".join(f"{lengths_n} at {e8(k)}" for k in sorted(set(it[1])) for lengths_n in [it[1].count(k)]),
    "read_x8": lambda it: " · ".join(str(a) for _, a in x8_questions(it[1], it[2])),
    "group_frac": lambda it: str(it[0] // it[1] * it[2]),
    "tens_groups": lambda it: f"{it[0] * it[1]} tens = {it[0] * it[1] * 10}",
    "area_rows": lambda it: f"{it[0] * it[1]} square units",
    "area_split": lambda it: str(it[0] * (it[1] + it[2])),
    "perim_add": lambda it: f"{perimeter(it[0], it[1])} {it[2]}",
    "area_perim": lambda it: f"area {it[0] * it[1]}, perimeter {perimeter(it[0], it[1])}",
    "read_minute": lambda it: tstr(it[0], it[1]),
    "eo_product": lambda it: "even" if it[0] * it[1] % 2 == 0 else "odd",
    "is_quad": lambda it: _yes(len(SHAPES[it[0]]) == 4),
    "quad_fact": lambda it: _yes(it[1]),
    "name_quad": lambda it: quad_name(it[0]),
    "shape_count": lambda it: f"{len(SHAPES[it[0]])} sides, {len(SHAPES[it[0]])} corners",
    "quarter": lambda it: f"{qstr(it[1])} inches",
    "measure_q": lambda it: f"{qstr(it[1])} in",
    "beaker": lambda it: f"{it[0]} liter{'s' if it[0] != 1 else ''}",
    "balance": lambda it: f"{sum(it[1])} {it[2]}",
    "quick_th": lambda n: nf(n),
    "big_stack": lambda it: nf(it[0] + it[1] if it[2] == "+" else it[0] - it[1]),
    "area_mult": lambda it: nf(it[0] * it[1]),
    "partial": lambda it: nf(it[0] * it[1]),
    "groups_rem": lambda it: f"{it[0] // it[1]} groups, {it[0] % it[1]} left over",
    "rem_think": lambda it: f"{it[0] // it[1]} R {it[0] % it[1]}",
    "share_rem": lambda it: f"{it[0] // it[1]} R {it[0] % it[1]}",
    "jump_time": lambda it: (tstr(*tadd(it[0], it[1])) if it[2] == "end" else f"{tdiff(it[0], it[1])} minutes"),
}


def packet_grades():
    """Packet number -> grade code, from the grade assessments' sections."""
    out = {}
    for slug, _, _, sections in GRADES:
        for s in sections:
            if isinstance(s.packet, int):
                out[s.packet] = GRADE_CODE[slug]
    return out


def solve(prompt):
    """The answer to a plain arithmetic prompt like "25 + 29 = ?", "28 + ? = 47" or "6 × ? = 48"."""
    m = re.fullmatch(r"(\d+|\?) ([+\u2212\u00d7\u00f7]) (\d+|\?) = (\d+|\?)", prompt.strip())
    if not m or [m.group(1), m.group(3), m.group(4)].count("?") != 1:
        return None
    a, op, b, c = m.group(1), m.group(2), m.group(3), m.group(4)
    f = {"+": lambda x, y: x + y, "\u2212": lambda x, y: x - y, "\u00d7": lambda x, y: x * y,
         "\u00f7": lambda x, y: x // y}[op]
    if c == "?":
        return str(f(int(a), int(b)))
    if b == "?":  # a op ? = c
        return str(int(a) - int(c) if op == "\u2212" else int(a) // int(c) if op == "\u00f7"
                   else {"+": lambda: int(c) - int(a), "\u00d7": lambda: int(c) // int(a)}[op]())
    return str({"+": lambda: int(c) - int(b), "\u2212": lambda: int(c) + int(b), "\u00d7": lambda: int(c) // int(b),
                "\u00f7": lambda: int(c) * int(b)}[op]())


def manifest_entry(id_, type_, title, record, packet=None, grade=None, file=None):
    parts, num = [], 0
    for s, item, answers in record:
        num += 1
        if not parts or parts[-1]["name"] != s.name:
            p = s.packet if s.packet is not None else packet
            parts.append({"part": len(parts) + 1, "name": s.name, "kind": s.kind,
                          "packet": p if isinstance(p, int) else None,
                          "packets": str(p) if p is not None else None, "questions": []})
        prompt = KINDS[s.kind].key(item)
        if s.kind == "word":
            prompt = item[0]
        prompt = re.sub(r"\[[^\]]*\]", "?", re.sub(r"^story: ", "", prompt))
        solved = solve(prompt.replace(",", ""))
        if solved and len(answers) == 1:
            if answers[0].replace(",", "") != solved:
                raise ValueError(f"{id_} #{num}: the key says {answers[0]} but {prompt} is {solved}")
            solved = answers[0]  # keep the key's comma (1,724)
        answer = ANSWER_OF[s.kind](item) if s.kind in ANSWER_OF else solved or " · ".join(answers)
        if " R ?" in prompt and len(answers) == 2:
            answer = f"{answers[0]} R {answers[1]}"  # 17 ÷ 5 = 3 R 2
        if s.kind == "word":
            answer = f"{item[2]} {item[3]}".strip()
        parts[-1]["questions"].append({"n": num, "prompt": prompt, "answer": answer})
    entry = {"id": id_, "type": type_, "title": title, "total": num, "file": file, "parts": parts}
    if packet is not None:
        entry["packet"] = packet
    if grade is not None:
        entry["grade"] = grade
    return entry


def write_manifest(entries):
    grades = packet_grades()
    by_number = {int(p[0].split("-")[0]): p for p in PACKETS}
    packets = [{"number": n, "slug": by_number[n][0].split("-", 1)[1], "folder": by_number[n][0],
                "file": by_number[n][1], "title": by_number[n][2], "grade": grades.get(n)}
               for n in TEACHING_ORDER if n in by_number]
    missing = set(by_number) - set(TEACHING_ORDER)
    if missing:
        raise ValueError(f"Packets {sorted(missing)} are missing from TEACHING_ORDER")
    order = {"pre": 0, "post": 1, "check-in": 2}
    tests = sorted(entries, key=lambda e: (order[e["type"]], e.get("grade") or "", e["id"]))
    body = {"packets": packets, "tests": tests}
    data = json.dumps(body, ensure_ascii=False, sort_keys=True)
    body = {"version": hashlib.sha256(data.encode()).hexdigest()[:12], **body}
    path = ROOT / "curriculum.json"
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n")
    return path


# ====================================================================== build

PACKETS = [
    ("0-adding-and-taking-away", "adding-and-taking-away", "Adding and Taking Away", learn_adding_taking_away,
     practice_adding_taking_away, False),
    ("1-ten-buddies", "ten-buddies", "Ten Buddies", learn_buddies, practice_buddies, False),
    ("2-ten-and-some-more", "ten-and-some-more", "Ten and Some More", learn_ten_and_more, practice_ten_and_more, False),
    ("3-up-to-and-over-ten", "up-to-and-over-ten", "Up to and Over Ten", learn_over_ten, practice_over_ten, True),
    ("4-over-the-next-ten", "over-the-next-ten", "Over the Next Ten", learn_over_tens, practice_over_tens, True),
    ("5-back-through-ten", "back-through-ten", "Back Through Ten", learn_back_through_ten,
     practice_back_through_ten, False),
    ("6-doubles-and-near-doubles", "doubles", "Doubles and Near Doubles", learn_doubles,
     practice_doubles, False),
    ("7-tens-and-ones", "tens-and-ones", "Tens and Ones", learn_tens_and_ones,
     practice_tens_and_ones, False),
    ("8-ten-more-ten-less", "ten-more-ten-less", "Ten More, Ten Less", learn_ten_more_less,
     practice_ten_more_less, False),
    ("9-adding-two-digit-numbers", "adding-two-digit", "Adding Two-Digit Numbers", learn_adding_two_digit,
     practice_adding_two_digit, False),
    ("10-subtracting-two-digit-numbers", "subtracting-two-digit", "Subtracting Two-Digit Numbers",
     learn_subtracting_two_digit, practice_subtracting_two_digit, False),
    ("11-missing-numbers", "missing-numbers", "Missing Numbers", learn_missing_numbers,
     practice_missing_numbers, False),
    ("12-subtracting-with-borrowing", "subtracting-with-borrowing", "Subtracting with Borrowing",
     learn_borrowing, practice_borrowing, False),
    ("13-adding-in-columns", "adding-in-columns", "Adding in Columns", learn_adding_columns,
     practice_adding_columns, False),
    ("14-subtracting-in-columns", "subtracting-in-columns", "Subtracting in Columns", learn_subtracting_columns,
     practice_subtracting_columns, False),
    ("15-hundreds-tens-and-ones", "hundreds-tens-and-ones", "Hundreds, Tens and Ones", learn_hundreds,
     practice_hundreds, False),
    ("16-skip-counting", "skip-counting", "Skip Counting", learn_skip_counting, practice_skip_counting, False),
    ("17-comparing-numbers", "comparing-numbers", "Comparing Numbers", learn_comparing, practice_comparing, False),
    ("18-10-and-100-more-or-less", "10-and-100-more-or-less", "10 and 100 More or Less", learn_more_less_100,
     practice_more_less_100, False),
    ("19-adding-three-digit-numbers", "adding-three-digit", "Adding Three-Digit Numbers", learn_adding_three_digit,
     practice_adding_three_digit, False),
    ("20-subtracting-three-digit-numbers", "subtracting-three-digit", "Subtracting Three-Digit Numbers",
     learn_subtracting_three_digit, practice_subtracting_three_digit, False),
    ("21-equal-groups-and-arrays", "equal-groups-and-arrays", "Equal Groups and Arrays", learn_arrays,
     practice_arrays, False),
    ("22-even-and-odd", "even-and-odd", "Even and Odd", learn_even_odd, practice_even_odd, False),
    ("23-hundred-buddies", "hundred-buddies", "Hundred Buddies", learn_hundred_buddies, practice_hundred_buddies,
     False),
    ("24-counting-forward-and-backward", "counting-forward-and-backward", "Counting Forward and Backward",
     learn_counting, practice_counting, False),
    ("25-halves", "halves", "Halves", learn_halves, practice_halves, False),
    ("26-halves-thirds-and-fourths", "halves-thirds-and-fourths", "Halves, Thirds and Fourths", learn_shares,
     practice_shares, False),
    ("27-telling-time", "telling-time", "Telling Time", learn_time, practice_time, False),
    ("28-money", "money", "Money", learn_money, practice_money, False),
    ("29-subtracting-across-zeros", "subtracting-across-zeros", "Subtracting Across Zeros", learn_across_zeros,
     practice_across_zeros, False),
    ("30-two-step-word-problems", "two-step-word-problems", "Two-Step Word Problems", learn_bar_models,
     practice_bar_models, False),
    ("31-measuring-length", "measuring-length", "Measuring Length", learn_length, practice_length, False),
    ("32-graphs", "graphs", "Graphs", learn_graphs, practice_graphs, False),
    ("33-multiplication", "multiplication", "Multiplication", learn_multiplication, practice_multiplication, False),
    ("34-multiplication-strategies", "multiplication-strategies", "Multiplication Strategies", learn_strategies,
     practice_strategies, False),
    ("35-division", "division", "Division", learn_division, practice_division, False),
    ("36-rounding", "rounding", "Rounding", learn_rounding, practice_rounding, False),
    ("37-multiplying-by-tens", "multiplying-by-tens", "Multiplying by Tens", learn_times_tens,
     practice_times_tens, False),
    ("38-area", "area", "Area", learn_area, practice_area, False),
    ("39-unit-fractions", "unit-fractions", "Unit Fractions", learn_unit_fractions, practice_unit_fractions,
     False),
    ("40-counting-fractions", "counting-fractions", "Counting Fractions", learn_counting_fractions, practice_counting_fractions,
     False),
    ("41-fractions-and-wholes", "fractions-and-wholes", "Fractions and Wholes", learn_fractions_wholes, practice_fractions_wholes,
     False),
    ("42-equal-fractions", "equal-fractions", "Equal Fractions", learn_equal_fractions, practice_equal_fractions,
     False),
    ("43-comparing-fractions", "comparing-fractions", "Comparing Fractions", learn_comparing_fractions, practice_comparing_fractions,
     False),
    ("44-fractions-of-a-group", "fractions-of-a-group", "Fractions of a Group", learn_fraction_of_group, practice_fraction_of_group,
     False),
    ("45-perimeter", "perimeter", "Perimeter", learn_perimeter, practice_perimeter, False),
    ("46-elapsed-time", "elapsed-time", "Elapsed Time", learn_elapsed, practice_elapsed, False),
    ("47-four-operations", "four-operations", "All Four Operations", learn_four_ops, practice_four_ops, False),
    ("48-patterns-in-the-times-table", "times-table-patterns", "Patterns in the Times Table", learn_patterns,
     practice_patterns, False),
    ("49-mass-and-liquid-volume", "mass-and-liquid-volume", "Mass and Liquid Volume", learn_mass_volume,
     practice_mass_volume, False),
    ("50-scaled-graphs", "scaled-graphs", "Scaled Graphs", learn_scaled_graphs, practice_scaled_graphs, False),
    ("51-measuring-to-the-quarter-inch", "quarter-inch", "Measuring to the Quarter Inch", learn_quarter_inch,
     practice_quarter_inch, False),
    ("52-shapes-and-quadrilaterals", "quadrilaterals", "Shapes and Quadrilaterals", learn_quadrilaterals,
     practice_quadrilaterals, False),
    ("53-thousands", "thousands", "Thousands", learn_thousands, practice_thousands, False),
    ("54-rounding-big-numbers", "rounding-big-numbers", "Rounding Big Numbers", learn_round_big, practice_round_big,
     False),
    ("55-adding-and-subtracting-big-numbers", "big-add-subtract", "Adding and Subtracting Big Numbers",
     learn_big_add_sub, practice_big_add_sub, False),
    ("56-multiplying-by-one-digit", "multiplying-by-one-digit", "Multiplying by One Digit", learn_mult_one_digit,
     practice_mult_one_digit, False),
    ("57-division-with-remainders", "division-with-remainders", "Division with Remainders", learn_remainders,
     practice_remainders, False),
    ("58-multiplying-two-digit-numbers", "multiplying-two-digit", "Multiplying Two-Digit Numbers", learn_mult_two_digit, practice_mult_two_digit,
     False),
    ("59-dividing-bigger-numbers", "dividing-bigger-numbers", "Dividing Bigger Numbers", learn_dividing_big, practice_dividing_big,
     False),
    ("60-factors-and-multiples", "factors-and-multiples", "Factors and Multiples", learn_factors, practice_factors,
     False),
    ("61-equivalent-fractions", "equivalent-fractions", "Equivalent Fractions", learn_equivalent, practice_equivalent,
     False),
    ("62-comparing-unlike-fractions", "comparing-unlike-fractions", "Comparing Unlike Fractions", learn_comparing_unlike, practice_comparing_unlike,
     False),
    ("63-adding-and-subtracting-fractions", "adding-and-subtracting-fractions", "Adding and Subtracting Fractions", learn_add_fractions, practice_add_fractions,
     False),
    ("64-mixed-numbers", "mixed-numbers", "Mixed Numbers", learn_mixed_numbers, practice_mixed_numbers,
     False),
    ("65-fractions-times-whole-numbers", "fractions-times-whole-numbers", "Fractions Times Whole Numbers", learn_frac_times, practice_frac_times,
     False),
    ("66-tenths-and-hundredths", "tenths-and-hundredths", "Tenths and Hundredths", learn_decimals, practice_decimals,
     False),
    ("67-comparing-decimals", "comparing-decimals", "Comparing Decimals", learn_compare_decimals, practice_compare_decimals,
     False),
    ("68-measurement-conversions", "measurement-conversions", "Measurement Conversions", learn_conversions, practice_conversions,
     False),
    ("69-area-and-perimeter-formulas", "area-and-perimeter-formulas", "Area and Perimeter Formulas", learn_area_formulas, practice_area_formulas,
     False),
    ("70-line-plots-with-fractions", "line-plots-with-fractions", "Line Plots with Fractions", learn_line_plots, practice_line_plots,
     False),
]

# Packets built in more than one version for the founder to choose from. Each option gets its own
# copy of the no-repeat registry, so the options don't collide with each other.
OPTIONS = []  # e.g. packet 12 was built as "rows" and "columns"; the founder chose rows


def build_packet(packet, ink_folder, key, asked, suffix="", save=True):
    folder, slug, name, learn, practice, _ = packet
    out = ROOT / folder / ink_folder
    path = out / f"{slug}-{'answer-key' if key else 'packet'}{suffix}.pdf"
    bk = Book(path, key, subtitle=name, asked=asked)
    bk.c.setTitle(f"{name}: " + ("Answer Key" if key else "Packet"))
    learn(bk)
    practice(bk)
    if not save:
        return bk  # still open: the Check-In is added at the end, then saved
    bk.save()
    return path


if __name__ == "__main__":
    for color, ink_folder in [(True, "color"), (False, "black-and-white")]:
        T = theme(color)
        for key in (False, True):
            asked = {}  # one registry across all four packets: no question twice
            books = [build_packet(packet, ink_folder, key, asked, save=False) for packet in PACKETS]
            for packet in OPTIONS:
                print(build_packet(packet, ink_folder, key, dict(asked)))
            picker = Picker(asked)  # check-ins and assessments: fresh problems first, none repeated
            manifest = [] if color and key else None
            for packet, bk in zip(PACKETS, books):
                build_check_in(packet, ink_folder, key, picker, manifest, into=bk)  # also ends the packet
                bk.save()
                print(bk.path if hasattr(bk, "path") else packet[0])
            for grade in GRADES:
                for when in ("pre", "post"):
                    print(build_assessment(grade, when, ink_folder, key, picker, manifest))
            if manifest is not None:
                print(write_manifest(manifest))
        for packet in PACKETS:
            if packet[5]:
                print(build_template(ROOT / packet[0] / ink_folder))

