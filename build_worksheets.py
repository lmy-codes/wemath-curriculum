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
    )


T = theme(True)

W, H = letter
M = 48
CW = W - 2 * M
OPS = {"+", "−", "=", "-"}
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
    ("grade-2", "Grade 2", "Packets 10–22", [
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


def place_sections(bk, title, y, picked):
    num = 1
    for i, (s, items) in enumerate(picked):
        kind = KINDS[s.kind]
        y, num = flow(bk, title, y, i + 1, s.name, s.sub, spread(items), num, kind.cols, kind.h, kind.gap,
                      lambda x, cy, w, it, k=kind: k.draw(bk, x, cy, w, it))
    return y


def build_check_in(packet, ink_folder, key, picker):
    folder, slug, name = packet[:3]
    sections = CHECKINS[folder]
    path = ROOT / folder / ink_folder / f"{slug}-check-in{'-key' if key else ''}.pdf"
    bk = Book(path, key, subtitle=f"{name} Check-In", asked={})
    bk.c.setTitle(f"{name}: Check-In" + (" Answer Key" if key else ""))
    doc = set()
    picked = [(s, picker.pick(s.kind, s.pool, s.count, doc)) for s in sections]
    total = sum(len(items) for _, items in picked)
    title = f"Check-In: {name}"
    y = bk.new_page(title, "Show what you know. No help this time.", footer=f"WeMath  ·  {name} Check-In")
    score_tag(bk, total)
    place_sections(bk, title, y, picked)
    if bk.page > 1:
        print(f"WARNING: {folder} check-in runs onto {bk.page} pages")
    bk.save()
    return path


def build_assessment(grade, when, ink_folder, key, picker):
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
    place_sections(bk, title, y, picked)
    if key:
        scoring_sheet(bk, title, picked, total, when)
    bk.save()
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
    for i, (s, items) in enumerate(picked):
        c.setStrokeColor(T.line)
        c.setLineWidth(0.6)
        c.line(M, y, W - M, y)
        y -= 17
        c.setFillColor(T.ink)
        c.setFont("AvM", 10.5)
        c.drawString(cols[0], y, str(i + 1))
        c.drawString(cols[1], y, s.name)
        c.drawString(cols[2], y, str(s.packet))
        c.drawString(cols[3], y, f"{num}–{num + len(items) - 1}" if len(items) > 1 else str(num))
        c.drawString(cols[4], y, f"____ / {len(items)}")
        num += len(items)
        y -= 7
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

SHARE_NAME = {1: ("whole", "wholes"), 2: ("half", "halves"), 3: ("third", "thirds"), 4: ("fourth", "fourths")}


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
        fr = [i / n for i in range(n)] if equal else {3: (0, 0.22, 0.55), 4: (0, 0.18, 0.5, 0.7)}[n]
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
    fr = [i / n for i in range(n + 1)] if equal else {2: [0, .32, 1], 3: [0, .2, .55, 1], 4: [0, .15, .45, .7, 1]}[n]
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
]

# Packets built in more than one version for the founder to choose from. Each option gets its own
# copy of the no-repeat registry, so the options don't collide with each other.
OPTIONS = []  # e.g. packet 12 was built as "rows" and "columns"; the founder chose rows


def build_packet(packet, ink_folder, key, asked, suffix=""):
    folder, slug, name, learn, practice, _ = packet
    out = ROOT / folder / ink_folder
    path = out / f"{slug}-{'answer-key' if key else 'packet'}{suffix}.pdf"
    bk = Book(path, key, subtitle=name, asked=asked)
    bk.c.setTitle(f"{name}: " + ("Answer Key" if key else "Packet"))
    learn(bk)
    practice(bk)
    bk.save()
    return path


if __name__ == "__main__":
    for color, ink_folder in [(True, "color"), (False, "black-and-white")]:
        T = theme(color)
        for key in (False, True):
            asked = {}  # one registry across all four packets: no question twice
            for packet in PACKETS:
                print(build_packet(packet, ink_folder, key, asked))
            for packet in OPTIONS:
                print(build_packet(packet, ink_folder, key, dict(asked)))
            picker = Picker(asked)  # check-ins and assessments: fresh problems first, none repeated
            for packet in PACKETS:
                build_check_in(packet, ink_folder, key, picker)
            for grade in GRADES:
                for when in ("pre", "post"):
                    print(build_assessment(grade, when, ink_folder, key, picker))
        for packet in PACKETS:
            if packet[5]:
                print(build_template(ROOT / packet[0] / ink_folder))

