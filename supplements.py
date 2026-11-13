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

NAME = {p[0]: p[2] for p in W.PACKETS}
CAP_K1 = W.PAGE_CAP_K1


def fit(kind):
    """(columns, card height, gap) as drawn on a K-1 page: one-line cards grow to big print, two to a row."""
    k = KINDS[kind]
    if k.h == 42:
        return min(k.cols, 2), 66, 10
    return k.cols, k.h, k.gap


def max_per_page(kind):
    """How many cards of this kind fit on one page under a part header."""
    cols, h, gap = fit(kind)
    room = (H - 104 - 14 - 20) - 46
    rows = max(1, int((room + gap) // (h + gap)))
    return rows * cols


def default_per_page(kind):
    cols = fit(kind)[0]
    n = min(max_per_page(kind), CAP_K1)
    return max(cols, n // cols * cols)


def catalog():
    """Every packet's problem types for the website: id, label, help level, default and most per page."""
    out = {}
    for folder, types in TYPES.items():
        slug = folder.split("-", 1)[1]
        out[slug] = {"folder": folder, "title": NAME[folder],
                     "types": [{"id": t.id, "label": t.label, "help": t.help,
                                "perPage": default_per_page(t.kind), "maxPerPage": max_per_page(t.kind)}
                               for t in types]}
    return out


# ---------------------------------------------------------------------- building the PDFs

def _rng(spec, *salt):
    return random.Random(":".join([str(spec.get("seed", "")), spec["packet"], *map(str, salt)]))


def _plan(spec):
    """[(QType, per_page, items)] for the pages, and [(Section, items)] for the Check-In (no repeats of the pages)."""
    types = {t.id: t for t in TYPES[spec["packet"]]}
    pages, check = [], []
    chosen = [s for s in spec["types"] if s["id"] in types and int(s.get("pages", 0)) > 0]
    for s in chosen:
        t = types[s["id"]]
        cols = fit(t.kind)[0]
        per = int(s.get("per_page") or default_per_page(t.kind))
        per = max(cols, min(per, max_per_page(t.kind)) // cols * cols)
        n_pages = min(int(s["pages"]), 40)
        items = t.make(_rng(spec, t.id), per * n_pages)
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
        raise ValueError("Choose at least one problem type with at least one page")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "supplement.pdf"
        bk = Book(path, key, subtitle=f"{name} · Supplemental", asked={})
        bk.c.setTitle(f"{name}: Supplemental " + ("Answer Key" if key else "Practice"))
        if kind in ("packet", "answer-key"):
            title = f"{name}: Extra Practice"
            num = 1
            bk.big_print = True
            bk.repeat_ok = True
            for i, (t, per, items) in enumerate(pages):
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
    elif cmd == "checkin":
        json.dump(checkin(json.loads(Path(sys.argv[2]).read_text())), sys.stdout, ensure_ascii=False)
