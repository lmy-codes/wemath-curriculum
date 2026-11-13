"""Supplemental packets on demand: extra pages of one packet's problem types, made fresh from rules.

Every problem type is a card drawer the printed packets already use (build_worksheets.KINDS) plus a rule that
deals numbers that make sense for it (the same fact pools the packets use: OVER10, TEEN_SUB, NEXT10, ...).
A supplement is just a spec, so the same spec (with its seed) always prints the same pages:

    {"packet": "3-up-to-and-over-ten", "seed": "a1b2c3",
     "types": [{"id": "plain_big", "pages": 4}, {"id": "ba", "pages": 2, "per_page": 6}]}

Each page holds one problem type, with that type's usual number of problems unless per_page says otherwise.
The Check-In (last page, also on its own) takes a few problems of each chosen type, none from the pages.

    python supplements.py catalog                       # problem types for every packet that has them (JSON)
    python supplements.py pdf spec.json packet color    # writes the PDF to stdout
        (kinds: packet, answer-key, check-in, check-in-key; inks: color, black-and-white)
    python supplements.py checkin spec.json             # the Check-In's questions and answers (JSON)

Kindergarten and grade 1 (packets 0-9) for now; repeats are allowed there, never twice in a row.
"""
import io
import json
import random
import re
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

from reportlab import rl_config

import build_worksheets as W

rl_config.invariant = 1  # no timestamps or random ids in the PDF: the same spec gives the same file
from build_worksheets import (ADD5, GUT, KINDS, MINUS, NEXT10, OBJ, OVER10, OVER10_ANY, SUB5, TEEN_SUB, TWO_ADD_NEW,
                              TWO_ADD_NO, TWO_DIG, H, Book, Kind, Section, flow, objects, place_sections, score_tag,
                              stories, together)

QType = namedtuple("QType", "id label help kind make check")  # make(rng, n) -> n items; check = Check-In count


# ---------------------------------------------------------------------- full-width picture cards (up to 9)

def c_sp_wide_add(bk, x, cy, w, item):
    kind, a, b = item
    together(bk, kind, x + GUT, cy + 68, a, b, s=23, step=27, per_row=5, gap=34, outline=True)
    text = f"{a} + {b} = [{a + b}]"
    bk.eq(x + w - 16 - bk.eq_width(text, 20), cy + 30, text, size=20)


def c_sp_wide_take(bk, x, cy, w, item):
    kind, n, b = item
    bk.c.setFillColor(W.T.text2)
    bk.c.setFont("AvD", 11)
    bk.c.drawString(x + GUT + 175, cy + 54, f"Cross out {b}.")
    objects(bk, kind, x + GUT, cy + 68, n, s=23, step=27, crossed=b, cross_color=W.T.answer if bk.key else None)
    text = f"{n} {MINUS} {b} = [{n - b}]"
    bk.eq(x + w - 16 - bk.eq_width(text, 20), cy + 30, text, size=20)


KINDS["sp_wide_add"] = Kind(80, 1, lambda it: f"pic: {it[0]} {it[1]} + {it[2]}", c_sp_wide_add, 8)
KINDS["sp_wide_take"] = Kind(80, 1, lambda it: f"pic: {it[0]} {it[1]} - {it[2]}", c_sp_wide_take, 8)


# ---------------------------------------------------------------------- dealing numbers by rule

def deal(r, pool, n):
    """n items from pool: every item once in a shuffled order before any repeats, never the same one twice in
    a row, and never two in a row that start with the same number when that can be avoided."""
    pool = list(pool)
    out = []
    while len(out) < n:
        batch = pool[:]
        r.shuffle(batch)
        out += batch
    out = out[:n]

    def head(it):
        t = it if isinstance(it, (tuple, list)) else (it,)
        return str(t[0] if not isinstance(t[0], str) or len(t) == 1 else t[1])
    for i in range(1, len(out)):
        if out[i] == out[i - 1] or head(out[i]) == head(out[i - 1]):
            for j in range(i + 1, len(out)):
                if out[j] != out[i - 1] and head(out[j]) != head(out[i - 1]):
                    out[i], out[j] = out[j], out[i]
                    break
    return out


def with_obj(r, facts):
    objs = list(OBJ)
    r.shuffle(objs)
    return [(objs[i % len(objs)],) + tuple(f) for i, f in enumerate(facts)]


def eqs(pairs, op):
    return [f"{a} + {b} = [{a + b}]" if op == "+" else f"{a} {MINUS} {b} = [{a - b}]" for a, b in pairs]


def T(id_, label, help_, kind, pool=None, make=None, check=2):
    """A problem type. pool: a list of items dealt by `deal`; or make(r, n) for anything else."""
    return QType(id_, label, help_, kind, make or (lambda r, n, p=pool: deal(r, p, n)), check)


def balanced_yesno(r, n, yes_pool, no_pool):
    """Half yes, half no, in a shuffled order (so the right answers don't follow the grid)."""
    ys, ns = deal(r, yes_pool, (n + 1) // 2), deal(r, no_pool, n // 2)
    out = ys + ns
    r.shuffle(out)
    return out


def words(kind, facts):
    def make(r, n):
        return stories(r.random(), kind, deal(r, facts, n))
    return make


UP9_ADD = [(a, b) for a in range(1, 9) for b in range(1, 9) if 6 <= a + b <= 9]
UP9_SUB = [(n, b) for n in range(6, 10) for b in range(1, n)]
BUDDY_PAIRS = [(a, 10 - a) for a in range(1, 10)]
BIG_BACK = [(a, b) for a in range(21, 99) for b in range(11, 99) if a % 10 < b % 10 and 2 <= a - b <= 9]
TENS = [n for n in range(10, 100, 10)]

# ---------------------------------------------------------------------- the problem types of each packet
# help: "pictures" / "diagram" (the most help), "less help", "no help", "words". Ordered most help first.

TYPES = {
    "0-adding-and-taking-away": [
        T("add5_pic", "Put together, up to 5 (pictures)", "pictures", "pic_add",
          make=lambda r, n: with_obj(r, deal(r, ADD5, n))),
        T("take5_pic", "Take away, up to 5 (pictures)", "pictures", "pic_take",
          make=lambda r, n: with_obj(r, deal(r, SUB5, n))),
        T("add9_pic", "Put together, up to 9 (pictures)", "pictures", "sp_wide_add",
          make=lambda r, n: with_obj(r, deal(r, UP9_ADD, n))),
        T("take9_pic", "Take away, up to 9 (pictures)", "pictures", "sp_wide_take",
          make=lambda r, n: with_obj(r, deal(r, UP9_SUB, n))),
        T("story_pic", "Story problems with pictures", "pictures", "wide_story",
          make=lambda r, n: with_obj(r, deal(r, [(a, "+", b) for a, b in UP9_ADD] +
                                             [(a, "-", b) for a, b in UP9_SUB], n)), check=1),
        T("draw", "Draw to solve", "less help", "draw_solve",
          pool=[(a, "+", b) for a, b in UP9_ADD] + [(a, "-", b) for a, b in UP9_SUB]),
        T("add_plain", "Adding up to 9", "no help", "kbig",
          pool=eqs([(a, b) for a in range(0, 10) for b in range(0, 10) if 1 <= a + b <= 9], "+"), check=3),
        T("sub_plain", "Taking away within 9", "no help", "kbig",
          pool=eqs([(a, b) for a in range(1, 10) for b in range(0, a + 1)], "-"), check=3),
        T("words", "Word problems", "words", "word",
          make=lambda r, n: (words("add", UP9_ADD)(r, (n + 1) // 2) + words("sub", UP9_SUB)(r, n // 2)), check=1),
    ],
    "1-ten-buddies": [
        T("frame", "How many dots? What is its buddy?", "pictures", "frame_buddy", pool=list(range(1, 10))),
        T("fill_frame", "Fill the ten-frame", "pictures", "kframe", pool=list(range(0, 11))),
        T("more10", "How many more to make 10?", "pictures", "more10",
          pool=[(f"{a} + [{10 - a}] = 10", a, 10 - a) for a in range(1, 10)]),
        T("yesno", "Are they Ten Buddies?", "less help", "buddy_yesno",
          make=lambda r, n: balanced_yesno(r, n, [(f"{a} and {b}", True) for a, b in BUDDY_PAIRS],
                                           [(f"{a} and {b}", False) for a in range(1, 10) for b in range(1, 10)
                                            if a + b != 10])),
        T("buddy_plain", "Fill in the buddy", "no help", "kbig",
          pool=[f"{a} + [{10 - a}] = 10" for a in range(11)] + [f"[{a}] + {10 - a} = 10" for a in range(11)], check=3),
        T("words", "Word problems", "words", "word", make=words("make10", range(1, 10)), check=1),
    ],
    "2-ten-and-some-more": [
        T("teen", "Ten and some more (ten-frames)", "pictures", "teen",
          pool=[(f"10 + {n} = [{10 + n}]", n) for n in range(1, 10)] + [(f"10 + [{n}] = {10 + n}", n) for n in range(1, 10)]),
        T("kteen", "A full ten and some more", "pictures", "kteen", pool=list(range(1, 10))),
        T("three", "Find the buddies first, then add", "less help", "three",
          pool=[(a, 10 - a, c) for a in range(1, 10) for c in range(1, 10)] +
               [(c, a, 10 - a) for a in range(1, 10) for c in range(1, 10)]),
        T("teen_plain", "Teen numbers", "no help", "kbig",
          pool=[f"10 + {n} = [{10 + n}]" for n in range(10)] + [f"10 + [{n}] = {10 + n}" for n in range(1, 10)], check=3),
        T("words", "Word problems", "words", "word", make=words("add", [(10, n) for n in range(1, 10)]), check=1),
    ],
    "3-up-to-and-over-ten": [
        T("ba", "Break it apart (full diagram)", "diagram", "ba", pool=OVER10),
        T("ladder", "Buddy first, then the rest", "less help", "ladder", pool=OVER10),
        T("plain_big", "On your own: bigger number first", "no help", "kbig", pool=eqs(OVER10, "+"), check=3),
        T("plain_any", "On your own: either order", "no help", "kbig", pool=eqs(OVER10_ANY, "+"), check=3),
        T("up_or_over", "Up to ten or over ten?", "no help", "kbig", pool=eqs(BUDDY_PAIRS + OVER10_ANY, "+")),
        T("words", "Word problems", "words", "word", make=words("add", OVER10), check=1),
    ],
    "4-over-the-next-ten": [
        T("ladder", "Up to the next ten, then over", "diagram", "ladder", pool=NEXT10),
        T("ba", "Break it apart (two-digit)", "diagram", "ba", pool=NEXT10),
        T("hint", "Less help: write the next ten", "less help", "hint", pool=NEXT10),
        T("plain", "On your own", "no help", "kbig", pool=eqs(NEXT10, "+"), check=3),
        T("words", "Word problems", "words", "word", make=words("add", NEXT10), check=1),
    ],
    "5-back-through-ten": [
        T("jump_dots", "See the jumps (with dots)", "pictures", "jump_dots", pool=TEEN_SUB),
        T("jump", "Jump through ten", "diagram", "jump", pool=TEEN_SUB),
        T("jump_less", "Less help: fill in the two jumps", "less help", "jump_less", pool=TEEN_SUB),
        T("jump_big", "Bigger numbers: jump to the ten", "diagram", "jump_big", pool=BIG_BACK),
        T("plain", "On your own", "no help", "kbig", pool=eqs(TEEN_SUB, "-"), check=3),
        T("plain_big", "On your own: big numbers", "no help", "kbig", pool=eqs(BIG_BACK, "-"), check=3),
        T("words", "Word problems", "words", "word", make=words("sub", TEEN_SUB), check=1),
    ],
    "6-doubles-and-near-doubles": [
        T("double_dots", "Doubles with dots", "pictures", "double_dots", pool=list(range(1, 11))),
        T("near_dots", "Near doubles with dots", "pictures", "near_dots", pool=[(n, n + 1) for n in range(1, 10)]),
        T("doubles", "Doubles", "no help", "kbig", pool=[f"{n} + {n} = [{2 * n}]" for n in range(1, 11)], check=3),
        T("near", "Near doubles", "no help", "kbig",
          pool=[f"{n} + {n + 1} = [{2 * n + 1}]" for n in range(1, 10)] + [f"{n + 1} + {n} = [{2 * n + 1}]" for n in range(1, 10)],
          check=3),
        T("missing", "Find the missing double", "no help", "kbig",
          pool=[f"[{n}] + {n} = {2 * n}" for n in range(1, 11)] + [f"{n} + [{n}] = {2 * n}" for n in range(1, 11)]),
        T("big", "Big doubles and near doubles", "no help", "kbig",
          pool=[f"{a} + {b} = [{a + b}]" for a in range(11, 16) for b in range(11, 16) if abs(a - b) <= 1]),
        T("words", "Word problems", "words", "word",
          make=words("add", [(n, n) for n in range(2, 11)] + [(n, n + 1) for n in range(2, 10)]), check=1),
    ],
    "7-tens-and-ones": [
        T("count_to", "Count the tens and ones (pictures)", "pictures", "count_to", pool=[n for n in TWO_DIG if n < 70]),
        T("draw_qt", "Draw quick tens", "less help", "draw_qt", pool=[n for n in TWO_DIG if n < 60]),
        T("count_tens", "Count the tens", "pictures", "count_tens", pool=TENS),
        T("tens_plus", "Tens plus ones", "no help", "kbig",
          pool=[f"{n // 10 * 10} + {n % 10} = [{n}]" for n in TWO_DIG], check=3),
        T("tens_ones", "Tens and ones", "no help", "kbig",
          pool=[f"[{n // 10}] tens [{n % 10}] ones = {n}" for n in TWO_DIG] +
               [f"{n // 10} tens {n % 10} ones = [{n}]" for n in TWO_DIG], check=3),
        T("which_more", "Which is more?", "no help", "which_more",
          make=lambda r, n: deal(r, [(a, b) for a in r.sample(TWO_DIG, 30) for b in r.sample(TWO_DIG, 3)
                                     if a // 10 != b // 10], n)),
        T("words", "Word problems", "words", "word", make=words("tens", TWO_DIG), check=1),
    ],
    "8-ten-more-ten-less": [
        T("ten_pic", "10 more and 10 less (pictures)", "pictures", "ten_pic",
          pool=[(n, "+") for n in TWO_DIG if n < 70] + [(n, "-") for n in TWO_DIG if 20 < n < 80]),
        T("side", "10 less and 10 more", "less help", "side", pool=[n for n in TWO_DIG if 20 < n < 90]),
        T("chain10", "Keep going by tens", "less help", "chain10",
          pool=[("+", n) for n in range(2, 39)] + [("−", n) for n in range(60, 99)]),
        T("more", "Ten more", "no help", "kbig", pool=[f"{n} + 10 = [{n + 10}]" for n in TWO_DIG if n < 90], check=3),
        T("less", "Ten less", "no help", "kbig", pool=[f"{n} {MINUS} 10 = [{n - 10}]" for n in TWO_DIG], check=3),
        T("words", "Word problems", "words", "word", make=words("add", [(n, 10) for n in TWO_DIG if n < 90]), check=1),
    ],
    "9-adding-two-digit-numbers": [
        T("add_tens_pic", "Add tens (pictures)", "pictures", "add_tens_pic",
          pool=[(a, b) for a in range(12, 46) for b in (20, 30, 40) if a % 10]),
        T("split", "Split it: tens, ones, total", "diagram", "add_split", pool=TWO_ADD_NO + TWO_ADD_NEW),
        T("add_tens", "Add tens", "no help", "kbig",
          pool=eqs([(a, b) for a in range(11, 70) for b in (10, 20, 30) if a % 10 and a + b < 100], "+")),
        T("no_new", "No new ten", "no help", "kbig", pool=eqs(TWO_ADD_NO, "+"), check=3),
        T("new_ten", "Make a new ten", "no help", "kbig", pool=eqs(TWO_ADD_NEW, "+"), check=3),
        T("words", "Word problems", "words", "word", make=words("add", TWO_ADD_NO + TWO_ADD_NEW), check=1),
    ],
}

# ---------------------------------------------------------------------- every other packet: from its own sections
# Packets 10 and up get their problem types from what the packet already has: each Check-In section (its card kind
# and its pool of problems) and each extra-practice section (EXTRA: big pools made by rules). Sections asking the
# same kind of question are merged, so a type's pool is as big as it can be.

PLAIN_KINDS = {"eq1", "eq2", "eq3", "frac1", "frac2", "frac3", "rev2", "kbig", "mixed1", "mixed2", "mixed3", "pow",
               "pow6"}
WORD_KINDS = {"word", "two_step"}


def _help(kind):
    return "no help" if kind in PLAIN_KINDS else "words" if kind in WORD_KINDS else "guided"


def _shape(item):
    """What a problem looks like with the numbers taken out: problems with the same shape are the same type."""
    t = item if isinstance(item, str) else repr(item)
    return re.sub(r"\[[^\]]*\]", "[]", re.sub(r"\d+(?:[.,]\d+)*", "#", t))


def _label(name):
    name = re.sub(r"^(More|Every)\s+(?!than\b|or\b)", "", name.strip())
    return name[:1].upper() + name[1:]


def _sections(folder):
    """(label, kind, pool) for every Check-In and extra-practice section of a packet."""
    out = [(s.name, s.kind, list(s.pool)) for s in W.CHECKINS.get(folder, [])]
    ex = W.EXTRA.get(folder)
    for block in ([ex] if isinstance(ex, tuple) else ex or []):
        for sec in block[1]:
            out.append((sec[0], sec[2], list(sec[3])))
    return out


def _auto_types(folder):
    merged = []  # [label, kind, pool, shapes]
    for name, kind, pool in _sections(folder):
        if kind not in KINDS or not pool:
            continue
        shapes = {_shape(it) for it in pool}
        for m in merged:
            if m[1] == kind and (m[0].lower() == _label(name).lower() or
                                 len(shapes & m[3]) >= 0.5 * min(len(shapes), len(m[3]))):
                seen = set(map(repr, m[2]))
                m[2] += [it for it in pool if repr(it) not in seen]
                m[3] |= shapes
                break
        else:
            merged.append([_label(name), kind, list(pool), shapes])
    order = {"guided": 0, "no help": 1, "words": 2}
    merged.sort(key=lambda m: order[_help(m[1])])
    types, ids = [], set()
    labels = [m[0].lower() for m in merged]
    for label, kind, pool, _ in merged:
        if labels.count(label.lower()) > 1 and _help(kind) == "no help":
            label += " (no help)"
        base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:28] or kind
        tid, k = base, 2
        while tid in ids:
            tid, k = f"{base}_{k}", k + 1
        ids.add(tid)
        h = _help(kind)
        types.append(T(tid, label, h, kind, pool=pool, check=3 if h == "no help" else 1 if h == "words" else 2))
    return types


for _p in W.PACKETS:
    if _p[0] not in TYPES:
        TYPES[_p[0]] = _auto_types(_p[0])

NAME = {p[0]: p[2] for p in W.PACKETS}
CAP_K1 = W.PAGE_CAP_K1


def number(folder):
    return int(folder.split("-")[0])


def big_print(folder):
    """Kindergarten and grade 1 print one-line problems big, two to a row (as their packets do)."""
    return number(folder) <= 9


def page_cap(folder):
    """The founder's limit on problems a practice page: 10 (K-1), 15 (easier work), 12 (harder work)."""
    n = number(folder)
    return CAP_K1 if n <= 9 else W.PAGE_CAP_EASY if n <= 32 else W.PAGE_CAP_HARD


def fit(kind, folder):
    """(columns, card height, gap) as drawn on this packet's pages."""
    k = KINDS[kind]
    if k.h == 42 and big_print(folder):
        return min(k.cols, 2), 66, 10
    return k.cols, k.h, k.gap


def max_per_page(kind, folder):
    """How many cards of this kind fit on one page under a part header (never more than the page limit)."""
    cols, h, gap = fit(kind, folder)
    room = (H - 104 - 14 - 20) - 46
    rows = max(1, int((room + gap) // (h + gap)))
    return max(1, min(rows * cols, page_cap(folder)))


def default_per_page(kind, folder):
    cols = fit(kind, folder)[0]
    n = max_per_page(kind, folder)
    return max(min(cols, n), n // cols * cols)



# ---------------------------------------------------------------------- rules for packets 10 and up
# The auto types above take their problems from the packet's own lists. Where a list is short (a few graphs,
# a handful of pictures), a rule below makes every sensible problem of that kind instead, so a supplement
# can run for pages without repeating. Each rule keeps to the sizes the cards were drawn for.

import math as _m
from decimal import Decimal as _D
from fractions import Fraction as _F


def _pool(seed, make, n):
    """n different items from make(r), made with a fixed seed (the supplement's own seed then deals them)."""
    r, out, seen = random.Random(seed), [], set()
    for _ in range(n * 40):
        it = make(r)
        if it is not None and repr(it) not in seen:
            seen.add(repr(it))
            out.append(it)
        if len(out) == n:
            break
    return out


def _dec(r, whole_max, places):
    w = r.randint(0, whole_max)
    f = r.randint(1, 10 ** places - 1)
    if f % 10 == 0:
        return None
    return f"{w}.{f:0{places}d}"


def _x8(r):
    base = r.randint(3, 12)
    span = r.randint(4, 6)
    vals = sorted(r.randint(base, base + span - 1) for _ in range(8))
    counts = [vals.count(k) for k in set(vals)]
    if max(counts) > 4 or counts.count(max(counts)) > 1 or max(vals) == min(vals):
        return None
    title = r.choice(["Crayons", "Sticks", "Ribbons", "Leaves", "Pencils", "Shells", "Worms", "Feathers"])
    return (f"{title} (inches)", vals, r.randint(1, 999))


def _share(r):
    vals = sorted(r.randint(1, 10) for _ in range(6))
    counts = [vals.count(k) for k in set(vals)]
    if sum(vals) % 6 or max(vals) - min(vals) > 6 or counts.count(max(counts)) > 1 or max(counts) > 4:
        return None
    what, unit = r.choice([("Flour in 6 bowls (cups)", "cups"), ("Paint in 6 cans (gal)", "gal"),
                           ("Juice in 6 jugs (L)", "L"), ("Water in 6 bottles (cups)", "cups"),
                           ("Sand in 6 pails (lb)", "lb"), ("Milk in 6 jars (pints)", "pints")])
    return (what, vals, unit)


GRAPHS = [("Kites flown", ["Mon", "Tue", "Wed", "Thu"], "kites on", "star"),
          ("Flowers picked", ["Ava", "Ben", "Kim", "Max"], "flowers by", "flower"),
          ("Apples picked", ["Jo", "Lee", "Sam", "Tia"], "apples by", "apple"),
          ("Birds seen", ["Mon", "Tue", "Wed", "Thu"], "birds on", "star"),
          ("Laps swum", ["Ava", "Ben", "Kim", "Max"], "laps by", None),
          ("Cans collected", ["Room 1", "Room 2", "Room 3", "Room 4"], "cans in", None),
          ("Tickets sold", ["Fri", "Sat", "Sun", "Mon"], "tickets on", None)]


def _graph(r):
    title, cats, noun, pic = r.choice(GRAPHS)
    if pic and r.random() < 0.6:
        per = r.choice([2, 5, 10])
        counts = [per * r.randint(1, 6) for _ in cats]
        if len(set(counts)) < 4:
            return None
        return W.sgraph_item("pic", title, cats, counts, pic, per, noun, r.randint(1, 999))
    per = r.choice([2, 5, 10])
    counts = [per * r.randint(1, 9) for _ in cats]
    if len(set(counts)) < 4:
        return None
    return W.sgraph_item("bar", f"{title} (by {per}s)", cats, counts, None, per, noun, r.randint(1, 999))


def _grid_pts(r):
    pts, names = [], r.choice(["ABCD", "PQRS", "EFGH", "JKLM", "WXYZ"])
    while len(pts) < 4:
        p = (r.randint(0, 10), r.randint(0, 10))
        if p not in [q[:2] for q in pts] and p != (0, 0):
            pts.append(p + (names[len(pts)],))
    return pts


def _order(r):
    w = r.randint(0, 9)
    a, b = r.sample(range(1, 10), 2)
    nums = r.choice([[f"{w}.{a}", f"{w}.0{a}", f"{w}.{a}{b}"], [f"{w}.{a}{b}", f"{w}.{b}{a}", f"{w}.{a}0{b}"],
                     [f"{w}.{a}", f"{w}.{b}", f"{w}.{min(a, b)}{max(a, b)}"]])
    if len({_D(n) for n in nums}) < 3:
        return None
    r.shuffle(nums)
    return tuple(nums)


def _round(r):
    places = r.choice([0, 1, 2])
    x = _dec(r, 9, places + 1)
    if x is None:
        return None
    digits = x.replace(".", "")
    if digits[-2] == "9":  # keeps the rounding inside the same ten / tenth / hundredth
        return None
    return (x, places, "boxes")


def _dstack(r):
    op = r.choice("+-")
    a = r.choice([_dec(r, 9, 1), _dec(r, 9, 2), str(r.randint(2, 9))])
    b = r.choice([_dec(r, 9, 1), _dec(r, 9, 2)])
    if a is None or b is None or a.count(".") and b.count(".") and len(a.split(".")[1]) == len(b.split(".")[1]):
        return None
    if op == "-" and _D(a) <= _D(b):
        return None
    return (a, b, op, False)


def _thousandths(r):
    k = r.choice([1, 2, 3])
    if k == 1:
        t = r.randint(1, 9)
        return f"0.{t} = [{t * 100}] thousandths"
    if k == 2:
        t = r.randint(11, 99)
        return None if t % 10 == 0 else f"0.{t} = [{t * 10}] thousandths"
    t = r.randint(1, 9)
    return f"0.{t} = [{t * 10}] hundredths"


def _words_dec(r):
    x = _dec(r, 19, r.choice([1, 2, 3]))
    return None if x is None else f"{W.dec_words(x)} = [{x}]"


def _left(r):
    small, big, f = r.choice([("min", "hr", 60), ("in", "ft", 12), ("oz", "lb", 16), ("cm", "m", 100),
                              ("ft", "yd", 3), ("days", "weeks", 7)])
    n = r.randint(f + 1, 4 * f)
    return None if n % f == 0 else W.left_eq(n, small, big, f)


def _ops_words(r):
    a, b, c = r.randint(3, 9), r.randint(3, 9), r.randint(2, 9)
    k = r.randint(0, 3)
    if k == 0:
        return None if a * b <= c else f"Multiply {a} by {b}, then take away {c}: [{a * b - c}]"
    if k == 1:
        return f"Add {a} and {b}, then multiply by {c}: [{(a + b) * c}]"
    if k == 2:
        return f"Multiply {a} by {b}, then add {c}: [{a * b + c}]"
    return None if (a * b) % c else f"Multiply {a} by {b}, then divide by {c}: [{a * b // c}]"


def _rules_cmp(r):
    a = r.randint(2, 6)
    k = r.randint(2, 6)
    return f"A: add {a}, B: add {a * k}. Each B term is [{k}] times the A term"


RATE_WORDS = [("pages", "day"), ("miles", "hour"), ("cookies", "batch"), ("dollars", "hour"), ("laps", "day"),
              ("words", "minute"), ("cups", "jug")]


def _use_rate(r):
    what, per = r.choice(RATE_WORDS)
    return W.use_rate(r.randint(3, 25), what, per, r.randint(2, 9))


def _is_true(r):
    x = r.randint(2, 30)
    if r.random() < 0.5:
        a = r.randint(2, 20)
        shown = x + r.choice([0, 0, -2, -1, 1, 2])
        return (f"x = {shown} in x + {a} = {x + a}", shown == x)
    a = r.randint(2, 9)
    x = r.randint(2, 12)
    shown = x + r.choice([0, 0, -1, 1])
    return (f"x = {shown} in {a}x = {a * x}", shown == x)


def _ratio_tab(r):
    la, lb = r.choice([("cups", "people"), ("pages", "minutes"), ("eggs", "cakes"), ("boys", "girls"),
                       ("red", "blue"), ("laps", "minutes"), ("cans", "dollars")])
    a, b = r.sample(range(2, 10), 2)
    if _m.gcd(a, b) > 1:
        return None
    ks = tuple([1] + sorted(r.sample(range(2, 11), 3)))
    if max(a, b) * ks[-1] > 99:
        return None
    return (la, lb, a, b, ks)


def _rate_tab(r):
    la, lb = r.choice([("boxes", "pens"), ("hours", "dollars"), ("bags", "apples"), ("packs", "cards"),
                       ("days", "miles"), ("jars", "cookies")])
    n, u = r.randint(2, 6), r.randint(2, 15)
    ks = tuple(sorted(r.sample([k for k in range(2, 10) if k != n], 2)))
    return None if u * ks[-1] > 150 else (la, lb, n, n * u, ks)


def _pct(r):
    out_of = r.choice([2, 4, 5, 10, 20, 25, 50])
    k = r.randint(1, out_of - 1)
    return f"{k} out of {out_of} = [{k * 100 // out_of}] %"


def _rem(lo, hi, dlo, dhi):
    def make(r):
        d = r.randint(dlo, dhi)
        n = r.randint(lo, hi)
        return None if n % d == 0 else W.rem_eq2(n, d)
    return make


def _dec_addsub(r):
    a, b = _dec(r, 30, r.choice([1, 2])), _dec(r, 9, r.choice([1, 2]))
    if a is None or b is None:
        return None
    if r.random() < 0.5:
        return W.dec_add(a, b)
    return None if _D(a) <= _D(b) else W.dec_sub(a, b)


def _gcf(r):
    a, b = sorted(r.sample(range(12, 61), 2))
    g = _m.gcd(a, b)
    return None if g < 2 or g == a or len(W.factors(b)) > 10 else (a, b)


def _pow(r):
    b, e = r.randint(2, 10), r.randint(2, 5)
    if b ** e > 10000 or (b == 10 and e > 4):
        return None
    return (f"{b}^{e} = " + f" {W.TIMES} ".join([str(b)] * e), W.nf(b ** e))


def _scale(r):
    b = r.randint(2, 9)
    a = r.randint(1, 2 * b)
    if a == b or _m.gcd(a, b) != 1:
        return None
    n = b * r.randint(1, 4)
    if a > b:  # a mixed number
        return W.scale_q(a % b, b, n, a // b) if a % b else None
    return W.scale_q(a, b, n)


def _mixed_unlike(r):
    b, q = r.sample([2, 3, 4, 5, 6, 8], 2)
    a, p = r.randint(1, b - 1), r.randint(1, q - 1)
    w1, w2 = r.randint(1, 5), r.randint(1, 4)
    if _m.lcm(b, q) > 24 or _m.gcd(a, b) > 1 or _m.gcd(p, q) > 1:
        return None
    s_ = _F(a, b) + _F(p, q)
    if s_ == 1 or (_F(a, b) - _F(p, q)) == 0:
        return None
    if r.random() < 0.5:
        return W.unlike_mixed(w1, a, b, w2, p, q, "+")
    if _F(w1 * b + a, b) <= _F(w2 * q + p, q) or _F(a, b) < _F(p, q):
        return None
    return W.unlike_mixed(w1, a, b, w2, p, q, "-")


def _unlike_bottoms(r):
    b, q = r.sample([2, 3, 4, 5, 6, 8, 10], 2)
    a, p = r.randint(1, b - 1), r.randint(1, q - 1)
    if _m.lcm(b, q) > 24 or _m.gcd(a, b) > 1 or _m.gcd(p, q) > 1:
        return None
    if r.random() < 0.6:
        return None if _F(a, b) + _F(p, q) >= 1 else W.unlike_mx(a, b, p, q, "+")
    return None if _F(a, b) <= _F(p, q) else W.unlike_mx(a, b, p, q, "-")


def _between(r):
    n = r.randint(3, 9)
    k = r.randint(n + 1, 9 * n)
    return None if k % n == 0 else W.between_w(k, n)


def _opp(r):
    k = r.randint(1, 99) * r.choice([1, -1])
    return f"opposite of {W.neg(k)} = [{W.neg(-k)}]"


def _biggest(r):
    t = r.randint(2, 9)
    if r.random() < 0.5:  # the short one is biggest: 0.8, 0.75, 0.09
        trio = [10 * t, 10 * (t - 1) + r.randint(1, 9), r.randint(1, 9)]
    else:  # the long one is biggest: 0.45, 0.4, 0.09
        trio = [10 * t + r.randint(1, 9), 10 * t, r.randint(1, 9)]
    r.shuffle(trio)
    return tuple(trio)


R = range
RULES = {
    ("16", "count_the_fives"): list(R(2, 9)),
    ("37", "groups_of_tens"): [(g, t) for g in R(2, 7) for t in R(2, 10) if g * t <= 12],
    ("39", "find_the_whole"): list(R(2, 11)),
    ("49", "read_the_beaker"): [(l, 10) for l in R(1, 10)] + [(l, 20) for l in R(2, 20)],
    ("50", "read_the_graph"): _pool("g50", _graph, 60),
    ("67", "circle_the_biggest"): _pool("g67", _biggest, 60),
    ("70", "read_the_x_chart"): _pool("g70", _x8, 60),
    ("72", "segment_ray_or_line"): [(k, d) for k in ("segment", "ray", "line") for d in (-35, -25, -15, 10, 20, 30, 40)],
    ("72", "parallel_perpendicular_or_ne"): [(k, d) for k in ("parallel", "perpendicular", "neither")
                                             for d in (-30, -15, 10, 25, 40, 50)],
    ("74", "fill_the_chart"): _pool("g74a", lambda r: _dec(r, r.choice([9, 99]), r.choice([2, 3])), 80),
    ("74", "words_to_numbers"): _pool("g74b", _words_dec, 80),
    ("74", "how_many_thousandths"): _pool("g74c", _thousandths, 80),
    ("75", "put_them_in_order"): _pool("g75a", _order, 80),
    ("75", "round_with_the_picture"): _pool("g75b", _round, 80),
    ("76", "add_and_subtract_in_columns"): _pool("g76", _dstack, 80),
    ("77", "two_rows"): [(a, b) for a in R(112, 500, 37) for b in R(13, 50, 7) if "0" not in str(a) + str(b)],
    ("78", "divide_each_part"): [(d * q, d, [d * (q // 10 * 10), d * (q % 10)]) for d in R(12, 40, 3)
                                 for q in R(21, 50, 4) if q % 10],
    ("78", "what_is_left"): _pool("g78", _rem(300, 999, 12, 39), 80),
    ("79", "count_the_tenths"): [W.times_tenths(n, k) for n in R(2, 10) for k in R(2, 10)],
    ("80", "same_bottoms"): _pool("g80a", _unlike_bottoms, 80),
    ("80", "mixed_numbers"): _pool("g80b", _mixed_unlike, 80),
    ("81", "shade_and_multiply"): [(a, b, p, q, "shade") for b in R(2, 7) for a in R(1, b) for q in R(2, 7)
                                   for p in R(1, q) if _m.gcd(a, b) == 1 and _m.gcd(p, q) == 1],
    ("81", "smaller_or_bigger"): _pool("g81", _scale, 80),
    ("82", "count_the_cubes"): [(L, Wd, H) for L in R(2, 6) for Wd in R(2, 4) for H in R(2, 5)
                                if H * 14 + Wd * 7 <= 77],
    ("83", "share_the_strips"): [(k, n) for k in R(2, 6) for n in R(k + 1, 9) if _m.gcd(k, n) == 1],
    ("83", "between_which_wholes"): _pool("g83", _between, 80),
    ("84", "share_a_piece"): [(b, k) for b in R(2, 7) for k in R(2, 6) if b * k <= 24],
    ("85", "words_to_numbers"): _pool("g85", _ops_words, 80),
    ("86", "two_rules"): [(a, a * k) for a in R(2, 7) for k in R(2, 7) if a * k <= 24],
    ("86", "compare_the_rules"): _pool("g86", _rules_cmp, 40),
    ("87", "left_over"): _pool("g87", _left, 80),
    ("88", "read_the_x_chart"): _pool("g88", _share, 60),
    ("89", "read_the_points"): _pool("g89a", _grid_pts, 60),
    ("89", "plot_the_points"): _pool("g89b", _grid_pts, 60),
    ("90", "name_that_fits"): [(k, rot) for k in W.FITS for rot in (0, 10, 20, 30, -15)],
    ("91", "write_the_ratio"): [(a, b) for a in R(1, 8) for b in R(1, 8) if a != b and a + b <= 7],
    ("91", "ratio_tables"): _pool("g91", _ratio_tab, 60),
    ("92", "find_1_in_the_table"): _pool("g92a", _rate_tab, 60),
    ("92", "use_the_rate"): _pool("g92b", _use_rate, 80),
    ("93", "read_the_grid"): [k for k in R(3, 98) if k % 10],
    ("93", "what_percent"): _pool("g93", _pct, 60),
    ("94", "how_many_fit"): [(a, b, 1, b * m) for b in R(2, 7) for a in R(1, b) for m in R(2, 5) if b * m <= 24 and _m.gcd(a, b) == 1],
    ("95", "what_is_left"): _pool("g95", _rem(1000, 9999, 12, 49), 80),
    ("96", "add_and_subtract"): _pool("g96", _dec_addsub, 80),
    ("97", "common_factors"): _pool("g97", _gcf, 60),
    ("98", "read_the_thermometer"): [t for t in R(-14, 15) if t],
    ("98", "opposites"): _pool("g98", _opp, 80),
    ("99", "exponents"): _pool("g99", _pow, 40),
    ("100", "find_the_missing_part"): [(a, b) for a in R(4, 41, 3) for b in R(5, 41, 4) if a + b <= 60],
}
YESNO_RULES = {("100", "is_it_true"): _pool("g100", _is_true, 120)}

for _f, _types in TYPES.items():
    if number(_f) <= 9:
        continue
    for _i, _t in enumerate(_types):
        _k = (str(number(_f)), _t.id)
        if _k in RULES:
            _types[_i] = _t._replace(make=lambda r, n, p=RULES[_k]: deal(r, p, n))
        elif _k in YESNO_RULES:
            _ys = [it for it in YESNO_RULES[_k] if it[1]]
            _ns = [it for it in YESNO_RULES[_k] if not it[1]]
            _types[_i] = _t._replace(make=lambda r, n, y=_ys, no=_ns: balanced_yesno(r, n, y, no))
    # a type with too few problems for a page of its own is left out (a supplement would only repeat it)
    TYPES[_f] = [t for t in _types if len({repr(i) for i in t.make(random.Random(0), 60)}) >= 7]


def catalog():
    """Every packet's problem types for the website: id, label, help level, default and most per page."""
    out = {}
    for folder, types in TYPES.items():
        slug = folder.split("-", 1)[1]
        out[slug] = {"folder": folder, "title": NAME[folder],
                     "types": [{"id": t.id, "label": t.label, "help": t.help,
                                "perPage": default_per_page(t.kind, folder), "maxPerPage": max_per_page(t.kind, folder)}
                               for t in types]}
    return out


# ---------------------------------------------------------------------- building the PDFs

def _rng(spec, *salt):
    return random.Random(":".join([str(spec.get("seed", "")), spec["packet"], *map(str, salt)]))


def _plan(spec):
    """[(QType, per_page, items)] for the pages, and [(Section, items)] for the Check-In (no repeats of the pages)."""
    types = {t.id: t for t in TYPES[spec["packet"]]}
    pages, check = [], []
    # A chosen type with 0 pages has no practice pages but is still on the Check-In.
    chosen = [s for s in spec["types"] if s["id"] in types and int(s.get("pages", 0)) >= 0]
    for s in chosen:
        t = types[s["id"]]
        cols = fit(t.kind, spec["packet"])[0]
        mx = max_per_page(t.kind, spec["packet"])
        per = int(s.get("per_page") or default_per_page(t.kind, spec["packet"]))
        per = max(min(cols, mx), min(per, mx) // cols * cols)
        n_pages = max(0, min(int(s["pages"]), 40))
        items = t.make(_rng(spec, t.id), per * n_pages) if n_pages else []
        pages.append((t, per, items))
    number = int(spec["packet"].split("-")[0])
    many = len(chosen) > 4
    for t, _, used in pages:
        n = 1 if (many and t.check > 1 and t.help != "no help") else t.check
        pool = t.make(_rng(spec, t.id, "check-in"), 60)
        fresh = [it for it in pool if it not in used] or pool
        items, seen = [], []
        for it in fresh:
            if it not in seen:
                seen.append(it)
                items.append(it)
            if len(items) == n:
                break
        ck = "eq3" if t.kind == "kbig" else t.kind  # plain problems print normal size on the Check-In
        check.append((Section(t.label, None, ck, None, n, number), items))
    # all the no-help one-liners share one part, so the Check-In has few part headers
    plain = [it for sec, items in check if sec.kind == "eq3" for it in items]
    others = [(sec, items) for sec, items in check if sec.kind != "eq3"]
    if plain:
        words_ = [c for c in others if c[0].kind == "word"]
        others = [c for c in others if c[0].kind != "word"]
        others.append((Section("On your own", None, "eq3", None, len(plain), number), plain))
        others += words_
    return pages, others


def _draw_check_in(bk, name, check, record=None):
    total = sum(len(items) for _, items in check)
    ci_title = f"Check-In: {name} (Supplemental)"
    bk.subtitle = f"{name} · Supplemental Check-In"
    y = bk.new_page(ci_title, "Show what you know. No help this time.",
                    footer=f"WeMath  ·  {name}  ·  Supplemental Check-In")
    score_tag(bk, total)
    place_sections(bk, ci_title, y, check, record)


def _fit_one_page(name, check):
    """Trim the biggest sections (never below 1 problem) until the Check-In really fits on one page."""
    check = [(s, list(items)) for s, items in check]
    for _ in range(40):
        with tempfile.TemporaryDirectory() as tmp:
            bk = Book(Path(tmp) / "x.pdf", True, subtitle=name, asked={})
            _draw_check_in(bk, name, check)
            pages = bk.page
        if pages <= 1:
            break
        sec, items = max(check, key=lambda c: (len(c[1]) - (c[0].kind == "eq3") * 2, KINDS[c[0].kind].h))
        if len(items) > 1:
            items.pop()
            continue
        # one problem each and still too long: drop the tallest picture section (keep plain and word problems)
        tall = [c for c in check if c[0].kind not in ("eq3", "word")]
        if len(check) <= 1 or not tall:
            break
        check.remove(max(tall, key=lambda c: KINDS[c[0].kind].h))
    return check


def build(spec, kind="packet", ink="color", record=None):
    """The supplement as PDF bytes. kind: packet / answer-key (pages + Check-In), check-in / check-in-key."""
    folder = spec["packet"]
    if folder not in TYPES:
        raise ValueError(f"No supplemental problem types for {folder}")
    W.T = W.theme(ink == "color")
    key = kind.endswith("key")
    name = NAME[folder]
    pages, check = _plan(spec)
    check = _fit_one_page(name, check)
    if not pages:
        raise ValueError("Choose at least one problem type")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "supplement.pdf"
        bk = Book(path, key, subtitle=f"{name} · Supplemental", asked={})
        bk.c.setTitle(f"{name}: Supplemental " + ("Answer Key" if key else "Practice"))
        if kind in ("packet", "answer-key"):
            title = f"{name}: Extra Practice"
            num = 1
            bk.big_print = big_print(folder)
            bk.repeat_ok = True
            drawn = 0
            for t, per, items in pages:
                if not items:
                    continue  # 0 pages: on the Check-In only
                i, drawn = drawn, drawn + 1
                bk.cap = per
                k = KINDS[t.kind]
                if i == 0:
                    y = bk.new_page(title, spec.get("goal") or "Extra practice, one kind of problem a page.",
                                    footer=f"WeMath  ·  {name}  ·  Supplemental")
                else:
                    y = bk.new_page(title, first=False, force=True)
                y, num = flow(bk, title, y, i + 1, t.label, None, items, num, k.cols, k.h, k.gap,
                              lambda x, cy, w, it, k=k: k.draw(bk, x, cy, w, it))
            bk.cap = None
            bk.big_print = False
        _draw_check_in(bk, name, check, record)
        bk.save()
        return path.read_bytes()


def example_pdf(folder, type_id, ink="color"):
    """One row of a problem type's cards (the student's version), for the website's "what is this?" preview."""
    t = next(t for t in TYPES[folder] if t.id == type_id)
    W.T = W.theme(ink == "color")
    k = KINDS[t.kind]
    cols = fit(t.kind, folder)[0]
    items = t.make(random.Random(f"example:{folder}:{type_id}"), cols)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "example.pdf"
        bk = Book(path, False, subtitle=NAME[folder], asked={})
        bk.repeat_ok = True
        bk.big_print = big_print(folder)
        y = bk.new_page(NAME[folder], first=False, force=True)
        flow(bk, NAME[folder], y, 1, t.label, None, items, 1, k.cols, k.h, k.gap,
             lambda x, cy, w, it: k.draw(bk, x, cy, w, it))
        bk.save()
        return path.read_bytes()


def examples(out_dir):
    """A PNG of every problem type (out_dir/<slug>/<type id>.png): what each choice looks like on the page."""
    import pypdfium2 as pdfium
    from PIL import ImageChops, Image
    out = Path(out_dir)
    for folder, types in TYPES.items():
        slug = folder.split("-", 1)[1]
        (out / slug).mkdir(parents=True, exist_ok=True)
        for t in types:
            page = pdfium.PdfDocument(example_pdf(folder, t.id))[0]
            img = page.render(scale=2).to_pil().convert("RGB")
            top = int(95 * 2)  # below the page header line
            body = img.crop((0, top, img.width, img.height - 50 * 2))
            box = ImageChops.difference(body, Image.new("RGB", body.size, "white")).getbbox()
            if box:
                body = body.crop((max(0, box[0] - 16), max(0, box[1] - 12), min(body.width, box[2] + 16),
                                  min(body.height, box[3] + 16)))
            body.save(out / slug / f"{t.id}.png", optimize=True)


def checkin(spec):
    """The Check-In's questions and answers, in the curriculum.json test format (the website marks it)."""
    record = []
    build(spec, "check-in-key", "color", record)
    folder = spec["packet"]
    entry = W.manifest_entry("supp", "supplement", f"{NAME[folder]} Supplemental Check-In", record,
                             packet=int(folder.split("-")[0]))
    return entry


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "catalog"
    if cmd == "catalog":
        json.dump(catalog(), sys.stdout, ensure_ascii=False)
    elif cmd == "pdf":
        spec = json.loads(Path(sys.argv[2]).read_text())
        sys.stdout.buffer.write(build(spec, sys.argv[3], sys.argv[4]))
    elif cmd == "examples":
        examples(sys.argv[2])
    elif cmd == "checkin":
        json.dump(checkin(json.loads(Path(sys.argv[2]).read_text())), sys.stdout, ensure_ascii=False)
