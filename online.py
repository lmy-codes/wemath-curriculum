"""WeMath Online: the supplement problem types as on-screen practice, with a worked explanation for every problem.

    python online.py export <out_dir>     writes <out_dir>/index.json and one <slug>.json per packet
    python online.py report               how many problems each skill has and which explanations fell back

Each skill is a supplement problem type (supplements.TYPES) whose card is plain text: equations with answer boxes,
fraction problems, word problems and yes/no questions. Picture cards (ten-frames, break-apart diagrams, clocks …)
are left out for now: they need drawings on the screen.

A problem is exported as tokens the website draws (text, answer boxes, stacked fractions, powers), the answers, a
difficulty tier (1–3, by the size of its numbers) and the explanation: steps worked out from that problem's own
numbers, following the method the packet teaches (make ten, jump through ten, tens and ones, …).
"""

import json
import math
import random
import re
import sys
from decimal import Decimal as D
from fractions import Fraction as F
from pathlib import Path

import supplements as S

W = S.W
MINUS, TIMES, DIV = "−", "×", "÷"

TEXT_KINDS = {"eq1", "eq2", "eq3", "frac1", "frac2", "frac3", "rev2", "kbig", "mixed1", "mixed2", "mixed3", "pow",
              "pow6", "word", "yes_text", "yes_text1"}
POOL = 150  # problems per skill (fewer when the rule can't make that many different ones)

# ---------------------------------------------------------------------------------------------------- numbers

NUM = r"[−-]?\d[\d,]*(?:\.\d+)?"


def num(t):
    """'1,234' -> 1234, '−7' -> -7, '0.45' -> Decimal('0.45')."""
    t = str(t).replace(",", "").replace(MINUS, "-").strip()
    return D(t) if "." in t else int(t)


def fmt(x):
    """A number as it's printed on the packets: commas, − for negatives, no trailing zeros."""
    if isinstance(x, F):
        return frac_str(x)
    if isinstance(x, D):
        x = x.normalize()
        if x == x.to_integral():
            x = int(x)
        else:
            s = format(x, "f")
            whole, _, part = s.lstrip("-").partition(".")
            return (MINUS if x < 0 else "") + f"{int(whole):,}.{part}"
    return (MINUS if x < 0 else "") + f"{abs(int(x)):,}"


def frac_str(f, mixed=False):
    f = F(f)
    if f.denominator == 1:
        return fmt(f.numerator)
    if mixed and f > 1:
        q, r = divmod(f.numerator, f.denominator)
        return f"{q} {r}/{f.denominator}"
    return f"{f.numerator}/{f.denominator}"


def parse_frac(t):
    """'3/4' -> 3/4, '2 1/3' -> 7/3, '5' -> 5."""
    t = t.strip()
    m = re.fullmatch(r"(\d+) (\d+)/(\d+)", t)
    if m:
        return int(m.group(1)) + F(int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d+)/(\d+)", t)
    if m:
        return F(int(m.group(1)), int(m.group(2)))
    return F(num(t))


def places(n):
    """345 -> [(300, 'hundreds'), (40, 'tens'), (5, 'ones')] (zero places left out)."""
    names = ["ones", "tens", "hundreds", "thousands", "ten thousands", "hundred thousands"]
    out, k = [], 0
    while n:
        n, d = divmod(n, 10)
        if d:
            out.append((d * 10 ** k, names[k]))
        k += 1
    return out[::-1]


# ---------------------------------------------------------------------------------------------------- arithmetic


def add_steps(a, b, packet=0):
    c = a + b
    if isinstance(a, D) or isinstance(b, D):
        return dec_add_sub(a, b, "+")
    big, small = max(a, b), min(a, b)
    if c == 10 and big < 10:
        return [f"{a} and {b} are Ten Buddies: together they make 10."]
    if big == 10 and small < 10:
        return [f"10 and {small} more is {c}: a ten and {small} ones."]
    if small in (10, 100) and big > small and big % small:
        place = "tens" if small == 10 else "hundreds"
        return [f"{small} more: one more {place[:-1]}, so the {place} digit goes up by 1.", f"{fmt(big)} + {small} = {fmt(c)}."]
    if big % 10 == 0 and 0 < small < 10 and big < 100:
        return [f"{big} is {big // 10} tens. {big // 10} tens and {small} ones is {c}."]
    if a == b and a <= 20 and packet >= 6:  # doubles are taught in packet 6
        return [f"{a} + {a} is a double.", f"Double {a} is {c}."]
    if abs(a - b) == 1 and big <= 20 and packet >= 6:
        return [f"{small} and {big} are 1 apart: a near double.", f"Double {small} is {2 * small}.",
                f"One more: {2 * small} + 1 = {c}."]
    if big < 10 and c < 10:
        return [f"Start at {big} and count on {small}: " + ", ".join(str(big + i) for i in range(1, small + 1)) + ".",
                f"So {a} + {b} = {c}."]
    if big < 10:  # crossing ten: fill the ten first
        need = 10 - big
        return [f"Fill the ten first. {big} needs {need} to make 10.",
                f"Break {small} into {need} and {small - need}.",
                f"{big} + {need} = 10, then 10 + {small - need} = {c}."]
    if small < 10:
        ones = big % 10
        if ones + small >= 10 and ones:  # over the next ten
            need, nxt = 10 - ones, big + 10 - ones
            return [f"{fmt(big)} needs {need} to get to the next ten, {fmt(nxt)}.",
                    f"Break {small} into {need} and {small - need}.",
                    f"{fmt(big)} + {need} = {fmt(nxt)}, then {fmt(nxt)} + {small - need} = {fmt(c)}."]
        return [f"Add the ones: {ones} + {small} = {ones + small}.", f"So {fmt(big)} + {small} = {fmt(c)}."]
    if a % 10 == 0 and b % 10 == 0 and c < 1000:
        return [f"Count tens: {a // 10} tens + {b // 10} tens = {c // 10} tens.", f"{c // 10} tens is {fmt(c)}."]
    if big < 100 and small < 100:  # tens and ones
        t = a // 10 * 10 + b // 10 * 10
        o = a % 10 + b % 10
        st = [f"Split into tens and ones: {a} = {a // 10 * 10} + {a % 10}, {b} = {b // 10 * 10} + {b % 10}.",
              f"Tens: {a // 10 * 10} + {b // 10 * 10} = {t}.", f"Ones: {a % 10} + {b % 10} = {o}."]
        if o >= 10:
            st.append(f"{o} ones is a new ten and {o - 10} ones.")
        st.append(f"Together: {t} + {o} = {c}.")
        return st
    return column_add(a, b)


def column_add(a, b):
    """Place by place from the ones, with the carries."""
    names = ["ones", "tens", "hundreds", "thousands", "ten thousands"]
    st, carry, k = [f"Line up the places and add from the ones."], 0, 0
    x, y = a, b
    while x or y or carry:
        da, db = x % 10, y % 10
        s = da + db + carry
        txt = f"{names[k].capitalize()}: {da} + {db}" + (f" + {carry} carried" if carry else "") + f" = {s}"
        if s >= 10 and (x // 10 or y // 10):
            txt += f": write {s % 10}, carry 1 to the {names[k + 1]}"
        st.append(txt + ".")
        carry = 1 if s >= 10 else 0
        x, y, k = x // 10, y // 10, k + 1
        if k > 6:
            break
    st.append(f"So {fmt(a)} + {fmt(b)} = {fmt(a + b)}.")
    return st


def sub_steps(a, b, packet=0):
    c = a - b
    if isinstance(a, D) or isinstance(b, D):
        return dec_add_sub(a, b, MINUS)
    if a <= 10:
        return [f"Start with {a} and take away {b}.", f"{a} {MINUS} {b} = {c}."]
    if b in (10, 100) and a > b:
        place = "tens" if b == 10 else "hundreds"
        return [f"{b} less: one less {place[:-1]}, so the {place} digit goes down by 1.", f"{fmt(a)} {MINUS} {b} = {fmt(c)}."]
    if a < 20 and b < 10 and c < 10:  # back through ten
        return [f"Jump from {a} down to 10: that's a jump of {a - 10}.",
                f"Then from 10 down to {b}: a jump of {10 - b}.",
                f"The jumps together: {a - 10} + {10 - b} = {c}. So {a} {MINUS} {b} = {c}."]
    if 0 < c < 10 and b >= 10 and a < 100 and b // 10 != a // 10:  # close together: jump up from b
        nxt = (b // 10 + 1) * 10
        return [f"The numbers are close, so jump up from {b} to {a}.",
                f"{b} to {nxt} is {nxt - b}; {nxt} to {a} is {a - nxt}.",
                f"{nxt - b} + {a - nxt} = {c}. So {a} {MINUS} {b} = {c}."]
    if b % 10 == 0 and b < 100 and a < 1000:
        return [f"Take away {b // 10} tens: {a} has {a // 10} tens, so {a // 10 - b // 10} tens are left.",
                f"The ones stay the same: {fmt(c)}."]
    if a < 100:
        at, ao, bt, bo = a // 10 * 10, a % 10, b // 10 * 10, b % 10
        if ao >= bo:
            return [f"Take away the tens: {at} {MINUS} {bt} = {at - bt}.",
                    f"Take away the ones: {ao} {MINUS} {bo} = {ao - bo}.", f"Together: {at - bt} + {ao - bo} = {c}."]
        return [f"Not enough ones ({ao} {MINUS} {bo}), so break a ten: {a} = {at - 10} + {ao + 10}.",
                f"Ones: {ao + 10} {MINUS} {bo} = {ao + 10 - bo}.", f"Tens: {at - 10} {MINUS} {bt} = {at - 10 - bt}.",
                f"Together: {at - 10 - bt} + {ao + 10 - bo} = {c}."]
    return column_sub(a, b)


def column_sub(a, b):
    names = ["ones", "tens", "hundreds", "thousands", "ten thousands"]
    da = [int(d) for d in str(a)][::-1]
    db = [int(d) for d in str(b)][::-1] + [0] * 8
    st = ["Line up the places and take away from the ones."]
    for k in range(len(da)):
        if da[k] < db[k]:
            j = k + 1
            while da[j] == 0:
                j += 1
            st.append(f"{names[k].capitalize()}: {da[k]} {MINUS} {db[k]} needs more, so break a {names[j][:-1]}"
                      + (" (across the zeros)" if j > k + 1 else "") + ".")
            da[j] -= 1
            for m in range(j - 1, k, -1):
                da[m] += 9
            da[k] += 10
        st.append(f"{names[k].capitalize()}: {da[k]} {MINUS} {db[k]} = {da[k] - db[k]}.")
    st.append(f"So {fmt(a)} {MINUS} {fmt(b)} = {fmt(a - b)}.")
    return st


def dec_add_sub(a, b, op):
    a, b = D(str(a)), D(str(b))
    pa = max(-a.as_tuple().exponent, -b.as_tuple().exponent, 0)
    q = D(1).scaleb(-pa)
    r = a + b if op == "+" else a - b
    st = ["Line up the decimal points."]
    if pa:
        st.append(f"Fill the empty places with zeros: {a.quantize(q)} {op} {b.quantize(q)}.")
    st.append(f"{'Add' if op == '+' else 'Take away'} place by place, from the smallest: {fmt(r)}.")
    return st


def mul_steps(a, b, packet=0):
    c = a * b
    if isinstance(a, D) or isinstance(b, D):
        return dec_mul(D(str(a)), D(str(b)))
    for x, y in ((a, b), (b, a)):  # times a power of ten
        if y in (10, 100, 1000) and x >= 10:
            z = len(str(y)) - 1
            return [f"Times {fmt(y)}: every digit moves {z} place{'s' if z > 1 else ''} to the left.",
                    f"{fmt(x)} {TIMES} {fmt(y)} = {fmt(c)}."]
    if a <= 12 and b <= 12:
        if packet in (33, 21) or min(a, b) <= 2:
            return [f"{a} {TIMES} {b} is {a} groups of {b}.",
                    " + ".join([str(b)] * a) + f" = {c}." if a <= 6 else f"Count by {b}s {a} times: {c}."]
        if max(a, b) >= 6:
            big, small = max(a, b), min(a, b)
            if big == 9:
                return [f"{small} {TIMES} 9 is {small} {TIMES} 10 take away one group of {small}.",
                        f"{small} {TIMES} 10 = {small * 10}, and {small * 10} {MINUS} {small} = {c}."]
            return [f"Break {big} into 5 and {big - 5}.",
                    f"{small} {TIMES} 5 = {small * 5} and {small} {TIMES} {big - 5} = {small * (big - 5)}.",
                    f"{small * 5} + {small * (big - 5)} = {c}."]
        return [f"{a} {TIMES} {b} is {a} groups of {b}: {c}."]
    for x, y in ((a, b), (b, a)):  # one-digit times tens or hundreds: count the tens
        if x <= 9 and y % 10 == 0 and y < 1000 and len(str(y).rstrip("0")) == 1:
            z = len(str(y)) - len(str(y).rstrip("0"))
            unit = {1: "tens", 2: "hundreds"}[z]
            return [f"{fmt(y)} is {y // 10 ** z} {unit}.",
                    f"{x} {TIMES} {y // 10 ** z} {unit} = {x * y // 10 ** z} {unit}.", f"{x * y // 10 ** z} {unit} is {fmt(c)}."]
    if a % 10 == 0 and b % 10 == 0:
        za, zb = len(str(a)) - len(str(a).rstrip("0")), len(str(b)) - len(str(b).rstrip("0"))
        ta, tb = a // 10 ** za, b // 10 ** zb
        return [f"Multiply the front digits: {ta} {TIMES} {tb} = {ta * tb}.",
                f"{fmt(a)} {TIMES} {fmt(b)} is {ta * tb} {TIMES} {fmt(10 ** (za + zb))} = {fmt(c)}."]
    big, small = (a, b) if a >= b else (b, a)
    if small < 10:  # split the big one by place
        parts = [p for p, _ in places(big)]
        return [f"Split {fmt(big)} by place: " + " + ".join(fmt(p) for p in parts) + ".",
                "Multiply each part by " + f"{small}: " + ", ".join(f"{fmt(p)} {TIMES} {small} = {fmt(p * small)}" for p in parts) + ".",
                "Add the parts: " + " + ".join(fmt(p * small) for p in parts) + f" = {fmt(c)}."]
    parts = [p for p, _ in places(small)]
    return [f"Split {fmt(small)} by place: " + " + ".join(fmt(p) for p in parts) + ".",
            "; ".join(f"{fmt(big)} {TIMES} {fmt(p)} = {fmt(big * p)}" for p in parts) + ".",
            "Add the rows: " + " + ".join(fmt(big * p) for p in parts) + f" = {fmt(c)}."]


def dec_mul(a, b):
    c = a * b
    pa, pb = max(-a.as_tuple().exponent, 0), max(-b.as_tuple().exponent, 0)
    name = {0: "ones", 1: "tenths", 2: "hundredths", 3: "thousandths", 4: "ten-thousandths"}
    wa, wb = int(a.scaleb(pa)), int(b.scaleb(pb))
    if pa + pb == 0:
        return mul_steps(int(a), int(b))
    if pa == 0 or pb == 0:
        w, f, p = (int(a), wb, pb) if pa == 0 else (int(b), wa, pa)
        return [f"Count {name[p]}: {fmt((a if pa else b))} is {fmt(f)} {name[p]}.",
                f"{fmt(w)} {TIMES} {fmt(f)} {name[p]} = {fmt(w * f)} {name[p]}.", f"{fmt(w * f)} {name[p]} is {fmt(c)}."]
    return [f"Multiply as whole numbers: {fmt(wa)} {TIMES} {fmt(wb)} = {fmt(wa * wb)}.",
            f"{name[pa].capitalize()} {TIMES} {name[pb]} make {name[pa + pb]}, so the answer is {fmt(wa * wb)} {name[pa + pb]}.",
            f"{fmt(wa * wb)} {name[pa + pb]} = {fmt(c)}."]


def div_steps(n, d, packet=0):
    if isinstance(n, D) or isinstance(d, D):
        return dec_div(D(str(n)), D(str(d)))
    q, r = divmod(n, d)
    if d in (10, 100, 1000) and (n >= 100 or n % d):
        z = len(str(d)) - 1
        return [f"Divide by {fmt(d)}: every digit moves {z} place{'s' if z > 1 else ''} to the right.",
                f"{fmt(n)} {DIV} {fmt(d)} = {fmt(D(n) / d)}."]
    if q <= 12 and d <= 12 and r == 0:
        return [f"Think multiplication: {d} {TIMES} what = {n}?", f"{d} {TIMES} {q} = {n}, so {n} {DIV} {d} = {q}."]
    if q <= 12 and d <= 12:
        return [f"Find the biggest group of {d} that fits in {n}: {d} {TIMES} {q} = {d * q}.",
                f"{n} {MINUS} {d * q} = {r} left over.", f"So {n} {DIV} {d} = {q} R {r}."]
    chunks, left, st = [], n, [f"Take out easy groups of {d}."]
    while left >= d:
        k = 10 ** (len(str(left // d)) - 1)
        m = left // (d * k) * k
        chunks.append(m)
        st.append(f"{d} {TIMES} {fmt(m)} = {fmt(d * m)}; {fmt(left)} {MINUS} {fmt(d * m)} = {fmt(left - d * m)}.")
        left -= d * m
    st.append("Add the groups: " + " + ".join(fmt(m) for m in chunks) + f" = {fmt(q)}"
              + (f", with {r} left over: {fmt(q)} R {r}." if r else "."))
    return st


def dec_div(n, d):
    if d == d.to_integral():
        p = max(-n.as_tuple().exponent, 0)
        name = {1: "tenths", 2: "hundredths", 3: "thousandths"}.get(p)
        if name:
            k = int(n.scaleb(p))
            return [f"{fmt(n)} is {fmt(k)} {name}.", f"{fmt(k)} {name} {DIV} {fmt(d)} = {fmt(D(k) / d)} {name}.",
                    f"That's {fmt(n / d)}."]
        return [f"{fmt(n)} {DIV} {fmt(d)} = {fmt(n / d)}."]
    p = max(-d.as_tuple().exponent, 0)
    m = D(10) ** p
    return [f"Make the divisor a whole number: multiply both numbers by {fmt(m)}.",
            f"{fmt(n)} {DIV} {fmt(d)} is the same as {fmt(n * m)} {DIV} {fmt(d * m)}.",
            f"{fmt(n * m)} {DIV} {fmt(d * m)} = {fmt(n / d)}."]


def arith(a, op, b, packet=0):
    a, b = num(a), num(b)
    return {"+": add_steps, MINUS: sub_steps, TIMES: mul_steps, DIV: div_steps}[op](a, b, packet)


def missing_add(a, c):
    """a + ? = c by jumping up: to the next ten, by tens, then the ones."""
    if c - a < 10 or a % 10 == 0:
        return [f"Jump up from {fmt(a)} to {fmt(c)}.", f"{fmt(c)} {MINUS} {fmt(a)} = {fmt(c - a)}."]
    nxt = (a // 10 + 1) * 10
    jumps, st = [nxt - a], [f"Jump up from {fmt(a)} to {fmt(c)}.", f"{fmt(a)} to the next ten, {fmt(nxt)}: {nxt - a}."]
    last = c // 10 * 10
    if last > nxt:
        jumps.append(last - nxt)
        st.append(f"{fmt(nxt)} to {fmt(last)}: {fmt(last - nxt)}.")
    if c > last and last >= nxt:
        jumps.append(c - last)
        st.append(f"{fmt(last)} to {fmt(c)}: {c - last}.")
    st.append("The jumps together: " + " + ".join(fmt(j) for j in jumps) + f" = {fmt(c - a)}.")
    return st


# ---------------------------------------------------------------------------------------------------- fractions


def frac_op_steps(x, op, y):
    """x, y are fractions as written ('2/6'): the steps keep the numbers the student sees (no reducing)."""
    a, b = (int(t) for t in x.split("/"))
    c, d = (int(t) for t in y.split("/"))
    if op in "+" + MINUS:
        sign = 1 if op == "+" else -1
        if b == d:
            return [f"The bottoms are the same, so {'add' if op == '+' else 'take away'} the tops and keep the bottom.",
                    f"{a} {op} {c} = {a + sign * c}, so {x} {op} {y} = {a + sign * c}/{b}."]
        n = b * d // math.gcd(b, d)
        ea, ec = a * n // b, c * n // d
        return [f"Make the bottoms the same: {n}.", f"{x} = {ea}/{n} and {y} = {ec}/{n}.",
                f"{ea}/{n} {op} {ec}/{n} = {ea + sign * ec}/{n}."]
    if op == TIMES:
        return ["Multiply the tops, then the bottoms.", f"Tops: {a} {TIMES} {c} = {a * c}. Bottoms: {b} {TIMES} {d} = {b * d}.",
                f"So {x} {TIMES} {y} = {a * c}/{b * d}."]
    if b == d:
        return [f"Same bottoms: how many {c}s fit in {a}?", f"{a} {DIV} {c} = {a}/{c}" + (f" = {frac_str(F(a, c))}." if F(a, c).denominator != c else ".")]
    n = b * d // math.gcd(b, d)
    ea, ec = a * n // b, c * n // d
    return [f"How many {y} fit in {x}? Make the pieces the same size: {n}ths.", f"{x} = {ea}/{n} and {y} = {ec}/{n}.",
            f"How many {ec}s fit in {ea}? {ea} {DIV} {ec} = {ea}/{ec}" + (f" = {frac_str(F(ea, ec))}." if F(ea, ec).denominator != ec else ".")]


# ---------------------------------------------------------------------------------------------------- the skills

WORDS_EXPLAIN = {}


def fill(text):
    """The prompt with the answers written in: '8 + [5] = 13' -> '8 + 5 = 13'."""
    return re.sub(r"\[([^\]]*)\]", r"\1", text)


def boxes(text):
    return re.findall(r"\[([^\]]*)\]", text)


ABC = rf"({NUM}) ([+{MINUS}{TIMES}{DIV}]) ({NUM}) = ({NUM})"


def explain_eq(packet, sid, text):
    """Steps for one equation-style problem; None when no rule fits."""
    f = fill(text).replace("  ", " ").strip()
    ans = boxes(text)
    m = re.fullmatch(ABC, f)
    if m:
        a, op, b, c = m.groups()
        first = text.strip().startswith("[")
        if op == "+" and "[" in text.split("+")[0] and "[" in text.split("+")[1]:  # [15] + [15] = 30
            return [f"Two equal numbers that make {c}: half of {c}.", f"Half of {c} is {a}, so {a} + {a} = {c}."]
        if op == "+" and re.search(rf"\+ \[", text) and not first:
            x, z = num(a), num(c)
            if z == 10 and x < 10:
                return [f"{a}'s Ten Buddy is {b}: {a} and {b} make 10."]
            if x == 10 and z < 20:
                return [f"{c} is a ten and {z - 10} ones.", f"So 10 + {b} = {c}."]
            if x == num(b) and packet == 6:
                return [f"{c} is a double: double {a} is {c}.", f"So {a} + {a} = {c}."]
            return missing_add(x, z)
        if op == "+" and first:
            return [f"Which number and {b} make {c}?", f"{c} {MINUS} {b} = {a}."] if num(c) != 10 else \
                [f"{a} and {b} are Ten Buddies: together they make 10."]
        if op == DIV and "." in c and "." not in a + b:  # a whole number shared into a decimal
            p = len(c.split(".")[1])
            name = {1: "tenths", 2: "hundredths", 3: "thousandths"}[p]
            n, d = num(a), num(b)
            if d in (10, 100, 1000):
                return div_steps(n, d, packet)
            k = n * 10 ** p
            return [f"{a} is {fmt(k)} {name}.", f"{fmt(k)} {name} {DIV} {b} = {fmt(k // d)} {name}.", f"{fmt(k // d)} {name} = {c}."]
        if op == TIMES and re.search(rf"{TIMES} \[", text):
            return [f"Think: {a} {TIMES} what = {c}?", f"{c} {DIV} {a} = {b}."]
        return arith(a, op, b, packet)
    m = re.fullmatch(rf"({NUM}) ([+{MINUS}{TIMES}{DIV}]) ({NUM}) = ({NUM}) R ({NUM})", f)
    if m:
        return div_steps(num(m.group(1)), num(m.group(3)), packet)
    return None


def explain(packet, sid, kind, item):
    """The worked steps for one problem, from the rules below. Always a list (a plain answer if nothing fits)."""
    try:
        st = _explain(packet, sid, kind, item)
    except Exception:  # a rule that can't read this problem: fall back to the answer
        st = None
    return st


def _explain(packet, sid, kind, item):
    if kind == "word":
        story, sentence, answer, unit = item
        steps = [f"Write the number sentence: {sentence}."]
        parts = sentence.split(", ")
        for k, sent in enumerate(parts):
            m = re.fullmatch(ABC, sent)
            if not m or "$" in sentence or "½" in sentence:
                continue
            a, op, b, c = m.groups()
            if op == "+" and str(answer).replace(",", "") == b.replace(",", "") and len(parts) == 1:
                more = missing_add(num(a), num(c))
            else:
                more = arith(a, op, b, packet)
            if more:
                if len(parts) > 1:
                    steps.append(f"Step {k + 1}: {sent}.")
                    steps += more[-2:] if len(more) > 2 else more
                else:
                    steps += more
        steps.append(f"The answer is {answer}{' ' + unit if unit else ''}.")
        return steps
    if kind in ("yes_text", "yes_text1"):
        return explain_yes(packet, sid, item)
    if kind in ("pow", "pow6"):
        lhs, val = item
        m = re.match(rf"({NUM}) × 10\^(\d+)", lhs)
        if m:
            return [f"10^{m.group(2)} is 1 with {m.group(2)} zeros: {fmt(10 ** int(m.group(2)))}.",
                    f"Times {fmt(10 ** int(m.group(2)))}: every digit moves {m.group(2)} place{'s' if m.group(2) != '1' else ''} to the left.",
                    f"{m.group(1)} {TIMES} {fmt(10 ** int(m.group(2)))} = {val}."]
        m = re.match(r"(\d+)\^(\d+)", lhs)
        if m:
            b, e = int(m.group(1)), int(m.group(2))
            run, st = b, [f"{b}^{e} means {e} {b}s multiplied together."]
            for _ in range(e - 1):
                st.append(f"{fmt(run)} {TIMES} {b} = {fmt(run * b)}")
                run *= b
            return st
    text = item[0] if isinstance(item, tuple) else item
    rule = RULES.get((packet, sid))
    if rule:
        st = rule(text)
        if st:
            return st
    for gen in GENERAL:
        st = gen(packet, sid, text)
        if st:
            return st
    return None


def explain_yes(packet, sid, item):
    text, yes = item
    m = re.fullmatch(r"Is (\d+) a factor of (\d+)\?", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        q, r = divmod(b, a)
        return [f"Divide: {b} {DIV} {a} = {q}" + (f" R {r}." if r else "."),
                f"{'No remainder, so yes' if not r else 'There is a remainder, so no'}: {a} is {'' if not r else 'not '}a factor of {b}."]
    m = re.fullmatch(r"Is (\d+) a multiple of (\d+)\?", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        q, r = divmod(a, b)
        return [f"Divide: {a} {DIV} {b} = {q}" + (f" R {r}." if r else "."),
                f"{'No remainder, so yes' if not r else 'There is a remainder, so no'}: {a} is {'' if not r else 'not '}a multiple of {b}."]
    m = re.fullmatch(rf"x = ({NUM}) in (.+)", text)
    if m:
        x, eq = num(m.group(1)), m.group(2)
        m2 = re.fullmatch(r"x \+ (\d+) = (\d+)", eq)
        if m2:
            s = x + int(m2.group(1))
            return [f"Put {x} in for x: {x} + {m2.group(1)} = {s}.",
                    f"{s} {'is' if s == int(m2.group(2)) else 'is not'} {m2.group(2)}, so {'yes' if yes else 'no'}."]
        m2 = re.fullmatch(r"(\d+)x = (\d+)", eq)
        if m2:
            s = x * int(m2.group(1))
            return [f"{m2.group(1)}x means {m2.group(1)} {TIMES} x: {m2.group(1)} {TIMES} {x} = {s}.",
                    f"{s} {'is' if s == int(m2.group(2)) else 'is not'} {m2.group(2)}, so {'yes' if yes else 'no'}."]
    if packet == 105:
        return ([f"Different people would give different answers, so it's a statistics question."] if yes else
                [f"There is just one answer, so it's not a statistics question."])
    why = FACT_WHY.get(text)
    if why:
        return [why, f"So the answer is {'yes' if yes else 'no'}."]
    return None


FACT_WHY = {
    "A rectangle has 4 right angles.": "Every corner of a rectangle is a square corner: 90 degrees.",
    "A rhombus always has a right angle.": "A rhombus has 4 equal sides, but its corners can lean: they don't have to be square.",
    "A line segment has two endpoints.": "A segment starts and stops: one endpoint at each end.",
    "Perpendicular lines never meet.": "Perpendicular lines cross and make square corners. Parallel lines are the ones that never meet.",
    "An obtuse angle is more than 90 degrees.": "Obtuse angles are wider than a square corner: more than 90 degrees.",
    "A ray goes on forever both ways.": "A ray has one endpoint and goes on forever one way. A line goes on both ways.",
    "A square has 4 lines of symmetry.": "A square folds onto itself across both middles and both diagonals: 4 lines.",
    "An acute angle is more than 90 degrees.": "Acute angles are smaller than a square corner: less than 90 degrees.",
}


# General rules, tried in order for any equation-style problem.

def g_arith(packet, sid, text):
    return explain_eq(packet, sid, text)


def g_compare(packet, sid, text):
    m = re.fullmatch(rf"({NUM}) \[([<>=])\] ({NUM})", text.strip())
    if not m:
        return None
    a, s, b = m.groups()
    x, y = num(a), num(b)
    if x < 0 or y < 0:
        return [f"Think of a thermometer: the warmer temperature is the bigger number.",
                f"{a} is {'warmer' if x > y else 'colder'} than {b}, so {a} {s} {b}."]
    if isinstance(x, D) or isinstance(y, D):
        return ["Line up the decimal points and compare from the left: ones, then tenths, then hundredths.",
                f"{a} {s} {b}."]
    return [f"Compare from the biggest place: the first digit that is different decides.", f"{a} {s} {b}."]


def g_frac(packet, sid, text):
    f = fill(text)
    m = re.fullmatch(rf"(\d+)/10 \+ (\d+)/100 = (\d+)/100", f)
    if m:
        a, b, c = m.groups()
        return [f"Change tenths to hundredths: {a}/10 = {int(a) * 10}/100.", f"{int(a) * 10}/100 + {b}/100 = {c}/100."]
    m = re.fullmatch(rf"(\d+/\d+) ([+{MINUS}{TIMES}{DIV}]) (\d+/\d+) = (\d+)/(\d+)", f)
    if m:
        return frac_op_steps(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(rf"(\d+/\d+) ([+{MINUS}{TIMES}{DIV}]) (\d+/\d+) = (\d+)", f)
    if m:
        return frac_op_steps(m.group(1), m.group(2), m.group(3))
    m = re.fullmatch(rf"(\d+) {DIV} (\d+)/(\d+) = (\d+)", f)
    if m:
        n, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        st = [f"How many {a}/{b} fit in {n}? Each whole has {b} pieces of 1/{b}: {n} {TIMES} {b} = {n * b}."]
        if a > 1:
            st.append(f"Groups of {a} pieces: {n * b} {DIV} {a} = {m.group(4)}.")
        return st
    m = re.fullmatch(rf"(\d+)/(\d+) {DIV} (\d+) = (\d+)/(\d+)", f)
    if m:
        return [f"Share 1/{m.group(2)} among {m.group(3)}: cut each piece into {m.group(3)}.",
                f"Each share is 1/{int(m.group(2)) * int(m.group(3))}."]
    m = re.fullmatch(rf"(\d+) {TIMES} (\d+)/(\d+) = (\d+)/(\d+)", f)
    if m:
        k, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return [f"{k} groups of {a}/{b} is {k} {TIMES} {a} = {k * a} pieces of 1/{b}.", f"That's {k * a}/{b}."]
    m = re.fullmatch(rf"(\d+)/(\d+) (?:of|{TIMES}) (\d+) = (\d+)", f)
    if m:
        a, b, n = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return [f"Find 1/{b} of {n}: {n} {DIV} {b} = {n // b}.",
                f"{a} of those: {a} {TIMES} {n // b} = {a * n // b}." if a > 1 else f"So 1/{b} of {n} is {n // b}."]
    m = re.fullmatch(r"(\d+)/(\d+) = (\d+)/(\d+)", f)
    if m:
        a, b, c, d = map(int, m.groups())
        if d > b:
            return [f"The bottom went from {b} to {d}: times {d // b}.", f"Do the same to the top: {a} {TIMES} {d // b} = {c}."]
        return [f"The bottom went from {b} to {d}: divided by {b // d}.", f"Do the same to the top: {a} {DIV} {b // d} = {c}."]
    m = re.fullmatch(r"(\d+)/(\d+) = (\d+)", f)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return [f"{b} pieces of 1/{b} make one whole.", f"{a} {DIV} {b} = {a // b} wholes."]
    m = re.fullmatch(r"(\d+) = (\d+)/(\d+)", f)
    if m:
        w, a, b = map(int, m.groups())
        return [f"Each whole is {b}/{b}.", f"{w} wholes: {w} {TIMES} {b} = {a}, so {w} = {a}/{b}."]
    m = re.fullmatch(r"(\d+)/(\d+) = (\d+) (\d+)/(\d+)", f)
    if m:
        a, b, w, r, _ = map(int, m.groups())
        return [f"How many wholes in {a}/{b}? Each whole is {b}/{b}.", f"{a} {DIV} {b} = {w} R {r}.",
                f"So {a}/{b} = {w} wholes and {r}/{b}: {w} {r}/{b}."]
    m = re.fullmatch(r"(\d+) (\d+)/(\d+) = (\d+)/(\d+)", f)
    if m:
        w, a, b, n, _ = map(int, m.groups())
        return [f"Each whole is {b}/{b}: {w} wholes is {w} {TIMES} {b} = {w * b} pieces.",
                f"Add the {a} more: {w * b} + {a} = {n}, so {n}/{b}."]
    m = re.fullmatch(r"(\d+)/(\d+) = (\d+) wholes and (\d+)/(\d+)", f)
    if m:
        a, b, w, r, _ = map(int, m.groups())
        return [f"Each whole is {b}/{b}. {a} {DIV} {b} = {w} R {r}.", f"So {w} wholes and {r}/{b}."]
    m = re.fullmatch(rf"(\d+)/(\d+) \[([<>=])\] (\d+)/(\d+)", text.strip())
    if m:
        a, b, s, c, d = m.groups()
        a, b, c, d = int(a), int(b), int(c), int(d)
        if b == d:
            return ["Same bottoms: the pieces are the same size, so compare the tops.", f"{a}/{b} {s} {c}/{d}."]
        if a == c:
            return ["Same tops: the bigger the bottom, the smaller each piece.", f"{a}/{b} {s} {c}/{d}."]
        n = math.lcm(b, d)
        return [f"Make the bottoms the same: {a}/{b} = {a * n // b}/{n} and {c}/{d} = {c * n // d}/{n}.",
                f"Compare the tops: {a * n // b} and {c * n // d}, so {a}/{b} {s} {c}/{d}."]
    return None


def g_mixed(packet, sid, text):
    f = fill(text)
    if "/" not in f:
        return None
    m3 = re.fullmatch(rf"(\d+(?: \d+/\d+)?|\d+/\d+) {TIMES} (\d+(?: \d+/\d+)?|\d+/\d+) {TIMES} (\d+(?: \d+/\d+)?|\d+/\d+) = (.+)", f)
    if m3:
        a, b, c = (parse_frac(m3.group(i)) for i in (1, 2, 3))
        if "[" in text.split("=")[0]:  # the missing edge
            base = a * b
            return [f"The base is {m3.group(1)} {TIMES} {m3.group(2)} = {frac_str(base, True)}.",
                    f"Height = volume {DIV} base: {m3.group(4)} {DIV} {frac_str(base, True)} = {m3.group(3)}."]
        ab = a * b
        return [f"Multiply two edges first: {m3.group(1)} {TIMES} {m3.group(2)} = {frac_str(ab, True)}.",
                f"Then {TIMES} {m3.group(3)}: {frac_str(ab * c, True)}."]
    m = re.fullmatch(rf"(\d+(?: \d+/\d+)?|\d+/\d+) ([+{MINUS}{TIMES}]) (\d+(?: \d+/\d+)?|\d+/\d+) = (.+)", f)
    if not m:
        return None
    a, op, b = parse_frac(m.group(1)), m.group(2), parse_frac(m.group(3))
    if op == TIMES:
        r = a * b
        return [f"Write each as a fraction: {frac_str(a)} {TIMES} {frac_str(b)}.",
                f"Multiply tops and bottoms: {frac_str(r)}.", f"As a mixed number: {frac_str(r, True)}."]
    r = a + b if op == "+" else a - b
    bots = [int(x) for x in re.findall(r"/(\d+)", m.group(1) + " " + m.group(3))]
    n = math.lcm(*bots) if bots else 1
    st = []
    if len(set(bots)) > 1:
        st.append(f"Make the bottoms the same: {n}.")
    st.append(f"{'Add' if op == '+' else 'Take away'} the wholes, then the pieces (in {n}ths)." if n > 1 else
              f"{'Add' if op == '+' else 'Take away'} the wholes, then the pieces.")
    q, rem = divmod(r.numerator * (n // r.denominator), n)
    st.append(f"{m.group(1)} {op} {m.group(3)} = " + (f"{q} {rem}/{n}" if q and rem else f"{rem}/{n}" if rem else f"{q}") + "."
              + (f" That's 0 wholes and {rem}/{n}." if not q and rem else ""))
    return st


def g_place(packet, sid, text):
    f = fill(text)
    m = re.fullmatch(r"(?:(\d+) hundreds )?(\d+) tens (\d+) ones = (\d+)", f)
    if m:
        h, t, o, n = m.groups()
        parts = ([f"{h} hundreds = {int(h) * 100}"] if h else []) + [f"{t} tens = {int(t) * 10}", f"{o} ones = {o}"]
        return [", ".join(parts) + ".", f"Together: {n}."]
    m = re.fullmatch(rf"({NUM}(?: \+ {NUM})+) = ({NUM})", f)
    if m and f.count("+") >= 2:
        terms = f.split(" = ")[0].split(" + ")
        if len(set(terms)) == 1:
            return [f"{len(terms)} equal groups of {terms[0]}.", f"Count by {terms[0]}s: {m.group(2)}."]
        return ["Each part is one place: put them together.", " + ".join(terms) + f" = {f.split(' = ')[1]}."]
    m = re.fullmatch(rf"in ({NUM}) the (\d) is worth ({NUM})", f)
    if m:
        return [f"Find the place of the {m.group(2)} in {m.group(1)}.", f"There it is worth {m.group(3)}."]
    return None


def g_count(packet, sid, text):
    f = fill(text)
    m = re.fullmatch(r"Count (back |on )?by (\d+)s?: (.+)", f)
    if m:
        k = m.group(2)
        return [f"Each step {'takes away' if m.group(1) == 'back ' else 'adds'} {k}.", "Keep going: " + ", ".join(m.group(3).split()) + "."]
    m = re.fullmatch(r"Start at (\d+), add (\d+): (.+)", f)
    if m:
        return [f"Add {m.group(2)} each time.", ", ".join(m.group(3).split()) + "."]
    m = re.fullmatch(rf"((?:{NUM} +)+)rule: add ({NUM})", f)
    if m:
        t = m.group(1).split()
        return [f"Find the jump between neighbours: {t[1]} {MINUS} {t[0]} = {m.group(2)}.", f"Every step adds {m.group(2)}."]
    return None


def g_round(packet, sid, text):
    f = fill(text)
    m = (re.fullmatch(rf"({NUM}) rounds to ({NUM})", f) or
         re.fullmatch(rf"Round ({NUM}) to the nearest (?:10|100|1,000): ({NUM})", f) or
         re.fullmatch(rf"({NUM}) to the nearest (?:ten|hundred|thousand|tenth|hundredth|whole number) = ({NUM})", f))
    if not m:
        return None
    n, r = num(m.group(1)), num(m.group(2))
    place = (re.search(r"nearest (\S+)", f) or [None, None])[1]
    step = {"10": 10, "100": 100, "1,000": 1000, "ten": 10, "hundred": 100, "thousand": 1000, "tenth": D("0.1"),
            "hundredth": D("0.01"), "whole": 1, "100:": 100, "10:": 10}.get(place)
    if step is None:  # "rounds to": the place is the one the answer ends on
        if isinstance(r, D):
            step = D(1).scaleb(r.as_tuple().exponent)
        else:
            step = 1000 if r % 1000 == 0 and n >= 1000 else 100 if r % 100 == 0 and n >= 100 and r % 10 == 0 and str(n)[-2:] != "00" and abs(n - r) >= 5 else 10
    lo = (D(str(n)) // D(str(step))) * D(str(step))
    hi = lo + D(str(step))
    mid = lo + D(str(step)) / 2
    return [f"The {('number' if step == 1 else fmt(step))}s on each side: {fmt(lo)} below, {fmt(hi)} above.",
            f"Halfway is {fmt(mid)}. {fmt(n)} is {'at or above' if D(str(n)) >= mid else 'below'} halfway.",
            f"So {fmt(n)} rounds to {fmt(r)}."]


def g_units(packet, sid, text):
    f = fill(text)
    conv = {("weeks", "days"): 7, ("days", "hours"): 24, ("days", "hr"): 24, ("hr", "min"): 60, ("min", "sec"): 60, ("ft", "in"): 12,
            ("yd", "ft"): 3, ("yd", "in"): 36, ("lb", "oz"): 16, ("kg", "g"): 1000, ("L", "mL"): 1000,
            ("m", "cm"): 100, ("km", "m"): 1000, ("cm", "mm"): 10, ("gal", "qt"): 4, ("qt", "pt"): 2,
            ("pt", "c"): 2, ("mi", "ft"): 5280, ("m", "mm"): 1000}
    m = re.fullmatch(rf"({NUM}) (\S+) = ({NUM}) (\S+)", f)
    if m:
        a, ua, b, ub = m.groups()
        if (ua, ub) in conv:
            k = conv[(ua, ub)]
            return [f"1 {ua.rstrip('s') if ua.endswith('s') else ua} = {fmt(k)} {ub}. Big to small: multiply.",
                    f"{a} {TIMES} {fmt(k)} = {b} {ub}."]
        if (ub, ua) in conv:
            k = conv[(ub, ua)]
            return [f"{fmt(k)} {ua} = 1 {ub}. Small to big: divide.", f"{a} {DIV} {fmt(k)} = {b} {ub}."]
    m = re.fullmatch(rf"(\d+) (\S+) (\d+) (\S+) = (\d+) (\S+)", f)
    if m:
        a, ua, b, ub, c, uc = m.groups()
        k = conv.get((ua, ub))
        if k:
            return [f"1 {ua} = {k} {ub}, so {a} {ua} = {int(a) * k} {ub}.", f"Add the {b} {ub}: {int(a) * k} + {b} = {c} {ub}."]
    m = re.fullmatch(rf"(\d+) (\S+) = (\d+) (\S+) (\d+) (\S+)", f)
    if m:
        a, ua, q, uq, r, _ = m.groups()
        k = conv.get((uq, ua))
        if k:
            return [f"1 {uq} = {k} {ua}. How many {k}s fit in {a}?", f"{a} {DIV} {k} = {q} R {r}: {q} {uq} {r} {ua}."]
    return None


def g_measure(packet, sid, text):
    f = fill(text)
    m = re.fullmatch(rf"({NUM}) (\S+) by ({NUM}) \S+: area = ({NUM}) sq \S+", f)
    if m:
        return ["Area of a rectangle: length times width.", f"{m.group(1)} {TIMES} {m.group(3)} = {m.group(4)} square {m.group(2)}."]
    m = re.fullmatch(rf"({NUM}) (\S+) by ({NUM}) \S+: perimeter = ({NUM}) \S+", f)
    if m and "[" not in text.split(":")[0]:
        a, u, b, p = m.groups()
        return ["Perimeter: add all four sides.", f"{a} + {b} + {a} + {b} = {p} {u}."]
    m = re.fullmatch(rf"({NUM}) (\S+) by \[?({NUM})\]? \S+: perimeter = ({NUM}) \S+", f)
    m = m or re.fullmatch(rf"({NUM}) (\S+) by ({NUM}) \S+: perimeter = ({NUM}) \S+", f)
    m2 = re.fullmatch(rf"({NUM}) (\S+) (?:{TIMES}|by) \[({NUM})\] \S+(?: = |: perimeter = )({NUM}) (sq )?\S+", text.strip())
    if m2:
        a, u, b, t, sq = m2.groups()
        if sq or "sq" in text:
            return ["Area = length times width, so the missing side is area divided by the side you know.",
                    f"{t} {DIV} {a} = {b} {u}."]
        return ["The two known sides add to " + f"{a} + {a} = {2 * num(a)}.",
                f"The other two sides are {t} {MINUS} {2 * num(a)} = {2 * num(b)}, so each is {b} {u}."]
    m = re.fullmatch(rf"area: ({NUM}) {TIMES} ({NUM}) = ({NUM}) sq (\S+)", f)
    if m:
        return ["Area = length times width.", f"{m.group(1)} {TIMES} {m.group(2)} = {m.group(3)} square {m.group(4)}."]
    m = re.fullmatch(rf"perimeter: 2 {TIMES} ({NUM}) \+ 2 {TIMES} ({NUM}) = ({NUM}) (\S+)", f)
    if m:
        a, b, p, u = m.groups()
        return ["Perimeter = 2 lengths + 2 widths.", f"2 {TIMES} {a} = {2 * num(a)}, 2 {TIMES} {b} = {2 * num(b)}.",
                f"{2 * num(a)} + {2 * num(b)} = {p} {u}."]
    m = re.fullmatch(rf"P = ({NUM}) (\S+), length ({NUM}) \S+: width = ({NUM}) \S+", f)
    if m:
        p, u, l, w = m.groups()
        return [f"Take away both lengths: {p} {MINUS} 2 {TIMES} {l} = {num(p) - 2 * num(l)}.",
                f"That's both widths, so one width is {num(p) - 2 * num(l)} {DIV} 2 = {w} {u}."]
    m = re.fullmatch(rf"({NUM}) (\S+) {TIMES} ({NUM}) \S+ {TIMES} ({NUM}) \S+ = ({NUM}) cubic \S+", f)
    if m:
        a, u, b, c, v = m.groups()
        return ["Volume = length times width times height.", f"{a} {TIMES} {b} = {num(a) * num(b)}, then {TIMES} {c} = {v} cubic {u}."]
    m = re.fullmatch(rf"({NUM}) {TIMES} ({NUM}) {TIMES} \[({NUM})\] = ({NUM})", text.strip())
    if m:
        a, b, h, v = m.groups()
        return [f"The base is {a} {TIMES} {b} = {num(a) * num(b)}.", f"Height = volume {DIV} base: {v} {DIV} {num(a) * num(b)} = {h}."]
    m = re.fullmatch(rf"triangle, base ({NUM}) (\S+), height ({NUM}) \S+: +area = ({NUM}) sq \S+", f)
    if m:
        b, u, h, a = m.groups()
        return [f"A triangle is half of the {b} by {h} rectangle around it.",
                f"{b} {TIMES} {h} = {num(b) * num(h)}, and half of that is {a} square {u}."]
    m = re.fullmatch(rf"parallelogram, base ({NUM}) (\S+), height ({NUM}) \S+: +area = ({NUM}) sq \S+", f)
    if m:
        b, u, h, a = m.groups()
        return ["Move the triangle from one end to the other: it's a rectangle.", f"Base {TIMES} height: {b} {TIMES} {h} = {a} square {u}."]
    m = re.fullmatch(rf"trapezoid, sides ({NUM}) and ({NUM}) (\S+), height ({NUM}) \S+: +area = ({NUM}) sq \S+", f)
    if m:
        a, b, u, h, ar = m.groups()
        return [f"Two copies of the trapezoid make a parallelogram: base {a} + {b} = {num(a) + num(b)}.",
                f"{num(a) + num(b)} {TIMES} {h} = {(num(a) + num(b)) * num(h)}, and half of that is {ar} square {u}."]
    m = re.fullmatch(rf"triangle, area ({NUM}) sq (\S+), base ({NUM}) \S+: +height = ({NUM}) \S+", f)
    if m:
        a, u, b, h = m.groups()
        return [f"Area = base {TIMES} height {DIV} 2, so the whole rectangle is {a} {TIMES} 2 = {2 * num(a)}.",
                f"Height = {2 * num(a)} {DIV} {b} = {h} {u}."]
    m = re.fullmatch(rf"box ({NUM}) {TIMES} ({NUM}) {TIMES} ({NUM}) (\S+): +surface area = ({NUM}) sq \S+", f)
    if m:
        L, Wd, H, u, s = m.groups()
        L, Wd, H = num(L), num(Wd), num(H)
        return ["Six faces in three matching pairs.",
                f"Top and bottom: 2 {TIMES} {L * Wd} = {2 * L * Wd}; front and back: 2 {TIMES} {L * H} = {2 * L * H}; sides: 2 {TIMES} {Wd * H} = {2 * Wd * H}.",
                f"{2 * L * Wd} + {2 * L * H} + {2 * Wd * H} = {s} square {u}."]
    m = re.fullmatch(rf"cube, edge ({NUM}) (\S+): +surface area = ({NUM}) sq \S+", f)
    if m:
        e, u, s = m.groups()
        return [f"One face: {e} {TIMES} {e} = {num(e) ** 2}.", f"Six faces: 6 {TIMES} {num(e) ** 2} = {s} square {u}."]
    m = re.fullmatch(rf"({NUM})(?: \S+)? \+ \[({NUM})\] = ({NUM}) degrees", text.strip())
    if m:
        return [f"The two angles together make {m.group(3)} degrees.", f"{m.group(3)} {MINUS} {m.group(1)} = {m.group(2)} degrees."]
    m = re.fullmatch(rf"({NUM}) (\S+) ([+{MINUS}]) ({NUM}) \S+ = ({NUM}) \S+", f)
    if m:
        a, u, op, b, c = m.groups()
        st = arith(a, op, b, packet)
        return st + [f"Keep the unit: {c} {u}."] if st else None
    return None


def g_stats(packet, sid, text):
    f = fill(text)
    m = re.fullmatch(rf"(mean|median|mode|range) of ((?:{NUM}, )+{NUM})(?:, ({NUM}))? = ({NUM})", f)
    if m:
        kind, lst, extra, ans = m.groups()
        vals = [num(v) for v in lst.split(", ")] + ([num(extra)] if extra else [])
        srt = sorted(vals)
        if kind == "mean":
            if "[" in text and text.index("[") < text.index("="):  # missing value
                target = num(ans)
                known = vals[:-1]
                return [f"For a mean of {ans}, all {len(vals)} numbers must add to {len(vals)} {TIMES} {ans} = {len(vals) * target}.",
                        f"The others add to {sum(known)}, so the missing one is {len(vals) * target} {MINUS} {sum(known)} = {vals[-1]}."]
            return [f"Add them: " + " + ".join(fmt(v) for v in vals) + f" = {fmt(sum(vals))}.",
                    f"Share it out: {fmt(sum(vals))} {DIV} {len(vals)} = {ans}."]
        if kind == "median":
            st = ["Put them in order: " + ", ".join(fmt(v) for v in srt) + "."]
            if len(srt) % 2:
                return st + [f"The middle one is {ans}."]
            a, b = srt[len(srt) // 2 - 1], srt[len(srt) // 2]
            return st + [f"Two in the middle: {fmt(a)} and {fmt(b)}. Halfway between them is {ans}."]
        if kind == "mode":
            return [f"{ans} comes up most often."]
        return [f"Biggest {MINUS} smallest: {fmt(max(vals))} {MINUS} {fmt(min(vals))} = {ans}."]
    m = re.fullmatch(rf"((?:{NUM}, )+{NUM}): +mean = ({NUM}) +and +median = ({NUM})", f)
    if m:
        vals = [num(v) for v in m.group(1).split(", ")]
        return [f"Mean: " + " + ".join(fmt(v) for v in vals) + f" = {sum(vals)}, and {sum(vals)} {DIV} {len(vals)} = {m.group(2)}.",
                "Median: in order " + ", ".join(fmt(v) for v in sorted(vals)) + f", the middle one is {m.group(3)}.",
                "The far-off number pulls the mean up, but not the median."]
    return None


def g_ratio(packet, sid, text):
    f = fill(text)
    m = re.fullmatch(rf"({NUM}) : ({NUM}) = ({NUM}) : ({NUM})", f)
    if m:
        a, b, c, d = map(num, m.groups())
        if c >= a and c % a == 0 and (b == 0 or d % b == 0) and c // a == (d // b if b else c // a):
            return [f"{fmt(a)} went to {fmt(c)}: times {c // a}.", f"Do the same to the other side: {fmt(b)} {TIMES} {c // a} = {fmt(d)}."]
        if a % c == 0 and b % d == 0:
            k = a // c
            return [f"Divide both by the same number, {k}" + (" (the GCF)." if math.gcd(a, b) == k else "."),
                    f"{fmt(a)} {DIV} {k} = {fmt(c)}, {fmt(b)} {DIV} {k} = {fmt(d)}."]
    m = re.fullmatch(rf"({NUM}) (\S+(?: \S+)?) in ({NUM}) (\S+) = ({NUM}) .* per (\S+)", f)
    if m:
        t, what, n, _, r, per = m.groups()
        return [f"Find the amount for 1 {per}: divide by {n}.", f"{t} {DIV} {n} = {r} {what} per {per}."]
    m = re.fullmatch(rf"({NUM}) (.+) for \$({NUM}) = \$({NUM}) each", f)
    if m:
        n, _, t, r = m.groups()
        return [f"Price for 1: divide the cost by {n}.", f"${t} {DIV} {n} = ${r}."]
    m = re.fullmatch(rf"({NUM}) (\S+(?: \S+)?) per (\S+): ({NUM}) \S+ = ({NUM}) .*", f)
    if m:
        r, what, per, n, t = m.groups()
        return [f"{r} {what} for each {per}, {n} times.", f"{r} {TIMES} {n} = {t} {what}."]
    m = re.fullmatch(rf"({NUM})% of ({NUM}) = ({NUM})", f)
    if m:
        p, n, part = m.groups()
        if text.find("[") < text.find("="):  # find the whole
            return [f"{p}% means {p} out of 100. {p}% is {part}.", f"So 1% is {part} {DIV} {p}, and 100% is {n}."]
        return [f"{p}% means {p} out of 100: find 1% first.", f"1% of {n} is {n} {DIV} 100 = {fmt(D(str(num(n))) / 100)}.",
                f"{p} {TIMES} {fmt(D(str(num(n))) / 100)} = {part}."]
    m = re.fullmatch(rf"({NUM}) out of ({NUM}) = ({NUM}) %", f)
    if m:
        k, n, p = m.groups()
        return [f"Make it out of 100: {n} {TIMES} {100 // num(n)} = 100.", f"{k} {TIMES} {100 // num(n)} = {p}, so {p}%."]
    return None


def g_misc(packet, sid, text):
    f = fill(text)
    m = re.fullmatch(rf"(?:GCF|gcf) of ({NUM}) and ({NUM}) = ({NUM})", f)
    if m:
        a, b, g = map(num, m.groups())
        fa = [d for d in range(1, a + 1) if a % d == 0]
        fb = [d for d in range(1, b + 1) if b % d == 0]
        return [f"Factors of {a}: " + ", ".join(map(str, fa)) + ".", f"Factors of {b}: " + ", ".join(map(str, fb)) + ".",
                f"The greatest one in both lists is {g}."]
    m = re.fullmatch(rf"(?:LCM|lcm) of ({NUM}) and ({NUM}) = ({NUM})", f)
    if m:
        a, b, l = map(num, m.groups())
        return [f"Multiples of {a}: " + ", ".join(str(a * k) for k in range(1, l // a + 1)) + ".",
                f"Multiples of {b}: " + ", ".join(str(b * k) for k in range(1, l // b + 1)) + ".",
                f"The first one in both lists is {l}."]
    m = re.fullmatch(rf"({NUM}) \+ ({NUM}) = ({NUM}) {TIMES} \( ({NUM}) \+ ({NUM}) \)", f)
    if m:
        a, b, g, x, y = m.groups()
        return [f"The GCF of {a} and {b} is {g}.", f"{a} = {g} {TIMES} {x} and {b} = {g} {TIMES} {y}.",
                f"So {a} + {b} = {g} {TIMES} ( {x} + {y} )."]
    m = re.fullmatch(rf"opposite of ({NUM}) = ({NUM})", f)
    if m:
        return ["The opposite is the same distance from 0 on the other side.", f"The opposite of {m.group(1)} is {m.group(2)}."]
    m = re.fullmatch(rf"\| ?({NUM}) ?\| = ({NUM})", f)
    if m:
        return ["Absolute value is the distance from 0. Distance is never negative.", f"|{m.group(1)}| = {m.group(2)}."]
    m = re.fullmatch(rf"when (\w) = ({NUM}): +(.+) = ({NUM})", f)
    if m:
        v, val, expr, ans = m.groups()
        ex = re.sub(rf"(\d+){v}", rf"\1 {TIMES} {val}", expr).replace(v, val)
        return [f"Put {val} in for {v}: {ex}.", f"Multiply first, then add: {ans}."]
    m = re.fullmatch(rf"(\d+)(\w) \+ (\d+)\2 = (\d+) \2", f)
    if m:
        a, v, b, c = m.groups()
        return [f"Like terms: {a} {v}s and {b} more {v}s.", f"{a} + {b} = {c}, so {c}{v}."]
    m = re.fullmatch(rf"(\d+) \( (\w) \+ (\d+) \) = \1\2 \+ (\d+)", f)
    if m:
        k, v, n, p = m.groups()
        return [f"{k} groups of ({v} + {n}): {k} {v}s and {k} {TIMES} {n}.", f"{k} {TIMES} {n} = {p}."]
    m = re.fullmatch(rf"(.+?): +x = ({NUM})", f)
    if m:
        eq, x = m.groups()
        m2 = re.fullmatch(rf"x \+ ({NUM}) = ({NUM})", eq)
        if m2:
            return [f"x and {m2.group(1)} make {m2.group(2)}: x is the missing part.", f"{m2.group(2)} {MINUS} {m2.group(1)} = {x}."]
        m2 = re.fullmatch(rf"({NUM})x = ({NUM})", eq)
        if m2:
            return [f"{m2.group(1)} equal parts make {m2.group(2)}: x is one part.", f"{m2.group(2)} {DIV} {m2.group(1)} = {x}."]
    m = re.fullmatch(rf"\((.+)\) ([{TIMES}{DIV}+{MINUS}]) ({NUM}) = ({NUM})", f)
    if m:
        inner, op, b, ans = m.groups()
        v = W.ev(inner) if hasattr(W, "ev") else None
        return [f"Parentheses first: {inner} = {fmt(v) if v is not None else '…'}.", f"Then {fmt(v) if v is not None else ''} {op} {b} = {ans}."]
    m = re.fullmatch(rf"({NUM}) ([+{MINUS}]) ({NUM}) ([{TIMES}{DIV}]) ({NUM}) = ({NUM})", f)
    if m:
        a, op1, b, op2, c, ans = m.groups()
        v = num(b) * num(c) if op2 == TIMES else num(b) // num(c)
        return [f"Times and divide come before plus and minus: {b} {op2} {c} = {v}.", f"Then {a} {op1} {v} = {ans}."]
    m = re.fullmatch(r"Multiply (\d+) by (\d+), then (take away|add|divide by) (\d+): (\d+)", f)
    if m:
        a, b, how, c, r = m.groups()
        sym = {"take away": MINUS, "add": "+", "divide by": DIV}[how]
        return [f"First multiply: {a} {TIMES} {b} = {int(a) * int(b)}.", f"Then {how} {c}: {int(a) * int(b)} {sym} {c} = {r}."]
    m = re.fullmatch(r"Add (\d+) and (\d+), then multiply by (\d+): (\d+)", f)
    if m:
        a, b, c, r = m.groups()
        return [f"First add: {a} + {b} = {int(a) + int(b)}.", f"Then multiply by {c}: {int(a) + int(b)} {TIMES} {c} = {r}."]
    m = re.fullmatch(rf"half of ({NUM}|\S+) = (\S+)", f)
    if m:
        a, b = m.groups()
        if "[" in text.split("=")[0]:
            return [f"Half of what is {b}? Double {b}.", f"{b} + {b} = {a}."]
        return [f"Half of {a}: split it into two equal parts.", f"Each part is {b}."]
    m = re.fullmatch(rf"(\d+) {DIV} (\d+) is between (\d+) and (\d+)", f)
    if m:
        a, b, lo, hi = m.groups()
        return [f"{b} {TIMES} {lo} = {int(b) * int(lo)} and {b} {TIMES} {hi} = {int(b) * int(hi)}.", f"{a} is between them, so the answer is between {lo} and {hi}."]
    m = re.fullmatch(rf"({NUM}) {TIMES} ({NUM}) = ({NUM}) tenths = ({NUM})", f)
    if m:
        a, b, t, ans = m.groups()
        return [f"{b} is {int(D(b) * 10)} tenths.", f"{a} {TIMES} {int(D(b) * 10)} tenths = {t} tenths.", f"{t} tenths = {ans}."]
    m = re.fullmatch(rf"(\d+) {TIMES} (\d+) = (\d+) so (\d+) {TIMES} (\d+) = (\d+)", f)
    if m:
        a, b, p, c, d, q = m.groups()
        if int(d) == int(b) * 10:
            return [f"{d} is {b} tens.", f"{a} {TIMES} {b} tens = {p} tens = {q}."]
        return [f"{c} is double {a}, so the answer is double {p}.", f"{p} + {p} = {q}."]
    m = re.fullmatch(rf"(\d+) {TIMES} (\d+) = (\d+) {TIMES} (\d+) \+ (\d+) {TIMES} (\d+) = (\d+)", f)
    if m:
        a, b, _, c, _, d, ans = m.groups()
        return [f"Break {b} into {c} and {d}.", f"{a} {TIMES} {c} = {int(a) * int(c)} and {a} {TIMES} {d} = {int(a) * int(d)}.",
                f"{int(a) * int(c)} + {int(a) * int(d)} = {ans}."]
    m = re.fullmatch(rf"(\d+) (?:groups|rows) of (\d+) = (\d+)", f)
    if m:
        a, b, c = m.groups()
        return [f"{a} groups of {b}: " + " + ".join([b] * int(a)) + f" = {c}."]
    m = re.fullmatch(rf"((?:{NUM} \+ )+{NUM}) = ({NUM})", f)
    if m:
        terms = m.group(1).split(" + ")
        if len(set(terms)) == 1:
            return [f"{len(terms)} equal groups of {terms[0]}.", f"Count by {terms[0]}s: {m.group(2)}."]
    m = re.fullmatch(rf"((?:{NUM}  ?)+) +in order: +((?:{NUM} ?)+)", f)
    if m:
        return ["Think of a thermometer: the coldest is the most below zero.", "From coldest to warmest: " + ", ".join(m.group(2).split()) + "."]
    m = re.fullmatch(rf"\(({NUM}), ({NUM})\) to \(({NUM}), ({NUM})\): ({NUM}) apart", f)
    if m:
        x1, y1, x2, y2, d = map(num, m.groups())
        if y1 == y2:
            return [f"Same up number ({y1}): count across from {x1} to {x2}.", f"{max(x1, x2)} {MINUS} {min(x1, x2)} = {d}."]
        return [f"Same over number ({x1}): count up from {y1} to {y2}.", f"{max(y1, y2)} {MINUS} {min(y1, y2)} = {d}."]
    m = re.fullmatch(rf"each picture = (\d+): (\d+) pictures = (\d+)", f)
    if m:
        a, b, c = m.groups()
        return [f"Each picture stands for {a}.", f"{b} pictures: {b} {TIMES} {a} = {c}." if "[" not in text.split(":")[1].split("=")[0]
                else f"How many {a}s make {c}? {c} {DIV} {a} = {b}."]
    m = re.fullmatch(rf"(\d+):(\d+) to (\d+):(\d+) = (\d+) minutes", f)
    if m:
        h1, m1, h2, m2, d = map(int, m.groups())
        if h1 != h2 and m1 and m2 == 0 and (h2 - h1) % 12 == 1:
            return [f"Jump to the next o'clock: {h1}:{m1:02d} to {h2}:00 is {60 - m1} minutes."]
        if h1 != h2 and m1:
            return [f"Jump to the next o'clock: {h1}:{m1:02d} to {h1 % 12 + 1}:00 is {60 - m1} minutes.",
                    f"Then {h1 % 12 + 1}:00 to {h2}:{m2:02d} is {m2 + 60 * ((h2 - h1 - 1) % 12)} minutes.",
                    f"{60 - m1} + {m2 + 60 * ((h2 - h1 - 1) % 12)} = {d} minutes."]
        return [f"From {h1}:{m1:02d} to {h2}:{m2:02d}: count the minutes.", f"That's {d} minutes."]
    m = re.fullmatch(rf"(\d+) minutes after (\d+):(\d+) = (\d+):(\d+)", f)
    if m:
        d, h, mi, h2, m2 = map(int, m.groups())
        if mi + d >= 60:
            return [f"Jump to the next o'clock: {h}:{mi:02d} to {h % 12 + 1}:00 is {60 - mi} minutes.",
                    f"{d} {MINUS} {60 - mi} = {d - 60 + mi} minutes left: {h2}:{m2:02d}."]
        return [f"Add the minutes: {mi} + {d} = {mi + d}.", f"So it's {h2}:{m2:02d}."]
    m = re.fullmatch(rf"(\d+)(?:¢) \+ (\d+)¢ = (\d+)¢", f)
    if m:
        st = arith(m.group(1), "+", m.group(2), packet)
        return (st or []) + [f"So {m.group(3)}¢."] if "[" in text.split("=")[1] else missing_add(int(m.group(1)), int(m.group(3)))
    m = re.fullmatch(rf"(\d+)¢ \+ (\d+)¢ = 100¢", f)
    if m:
        return missing_add(int(m.group(1)), 100)
    m = re.fullmatch(rf"({NUM}) = ({NUM}) thousandths", f)
    if m:
        return [f"1 tenth = 100 thousandths and 1 hundredth = 10 thousandths.", f"{m.group(1)} = {m.group(2)} thousandths."]
    m = re.fullmatch(rf"({NUM}) = ({NUM}) hundredths", f)
    if m:
        return [f"1 tenth = 10 hundredths.", f"{m.group(1)} = {m.group(2)} hundredths."]
    m = re.fullmatch(rf"([a-z][a-z \-]+) = ({NUM})", f)
    if m and packet == 74:
        return ["Write the whole number, then the decimal point, then each place: tenths, hundredths, thousandths.",
                f"{m.group(1)} = {m.group(2)}."]
    m = re.fullmatch(rf"(\d+)/100 = ({NUM})", f) or re.fullmatch(rf"({NUM}) = (\d+)/100", f)
    if m:
        return ["Hundredths are the second place after the point.", f"{f}."]
    m = re.fullmatch(rf"(\d+)/10 \+ (\d+)/100 = (\d+)/100", f)
    if m:
        a, b, c = m.groups()
        return [f"Change tenths to hundredths: {a}/10 = {int(a) * 10}/100.", f"{int(a) * 10}/100 + {b}/100 = {c}/100."]
    m = re.fullmatch(r"(\d+) pieces of 1/(\d+) make 1 whole", f)
    if m:
        return [f"1/{m.group(2)} means the whole is cut into {m.group(2)} equal pieces.", f"So {m.group(1)} pieces make 1 whole."]
    m = re.fullmatch(r"1/(\d+) is 1 of (\d+) equal parts", f)
    if m:
        return [f"The bottom number tells how many equal parts make the whole.", f"1/{m.group(1)} is 1 of {m.group(2)} equal parts."]
    m = re.fullmatch(r"(\d+) pieces of 1/(\d+) = (\d+)/\2", f)
    if m:
        return [f"Each piece is 1/{m.group(2)}. Count the pieces: {m.group(1)}.", f"So {m.group(1)} pieces is {m.group(3)}/{m.group(2)}."]
    m = re.fullmatch(r"(\d+)/(\d+) = 1 whole and (\d+)/\2", f)
    if m:
        a, b, r = m.groups()
        return [f"One whole is {b}/{b}.", f"{a} {MINUS} {b} = {r}, so 1 whole and {r}/{b}."]
    m = re.fullmatch(rf"(\d+)/(10|100) = ({NUM})", f) or re.fullmatch(rf"({NUM}) = (\d+)/(10|100)", f)
    if m:
        return [("Tenths are the first place after the point." if "10" == (m.group(2) if "/" in f.split(" = ")[0] else m.group(3))
                 else "Hundredths are the second place after the point."), f"{f}."]
    m = re.fullmatch(r"(\d+)/(\d+) shaded, (\d+)/\2 not shaded", f)
    if m:
        a, b, c = m.groups()
        return [f"The whole is {b}/{b}.", f"{b} {MINUS} {a} = {c}, so {c}/{b} is not shaded."]
    m = re.fullmatch(r"(\d+)/(\d+) = (\d+) pieces of 1/\2", f)
    if m:
        return [f"{m.group(1)}/{m.group(2)} means {m.group(1)} pieces of 1/{m.group(2)}."]
    m = re.fullmatch(r"one (\w+) = 1/(\d+)", f) or re.fullmatch(r"(\w+) (\w+) = (\d+)/(\d+)", f)
    if m:
        return ["The bottom number tells how many equal parts make the whole.", f"{f}."]
    m = re.fullmatch(r"((?:\d+/\d+ ?)+)", f)
    if m and packet == 40:
        parts = f.split()
        return [f"Count by 1/{parts[0].split('/')[1]}s: each one has one more piece.", ", ".join(parts) + "."]
    return None


def g_fallback(packet, sid, text):
    return None


GENERAL = [g_arith, g_compare, g_frac, g_mixed, g_place, g_count, g_round, g_units, g_measure, g_stats, g_ratio,
           g_misc]

# Skill-specific rules (packet number, skill id) -> fn(text)
RULES = {}


def rule(packet, sid):
    def deco(fn):
        RULES[(packet, sid)] = fn
        return fn
    return deco


@rule(26, "make_a_whole")
@rule(26, "bigger_or_smaller")
def _shares(text):
    m = re.fullmatch(r"(\d+) (\w+) \[([<>=])\] (\d+) (\w+)", text.strip())
    if not m:
        return None
    return ["Picture the shapes the same size. More pieces in the whole means smaller pieces.",
            f"{m.group(1)} {m.group(2)} {m.group(3)} {m.group(4)} {m.group(5)}."]


@rule(27, "write_the_time")
def _time(text):
    f = fill(text)
    m = re.fullmatch(r"long hand on (\d+) = (\d+) minutes", f)
    if m:
        return ["Each number on the clock is 5 minutes for the long hand.", f"{m.group(1)} {TIMES} 5 = {m.group(2)} minutes."]
    m = re.fullmatch(r"(quarter past|half past|quarter to) (\d+) = (\d+:\d+)", f)
    if m:
        return [{"quarter past": "Quarter past is 15 minutes after the hour.",
                 "half past": "Half past is 30 minutes after the hour.",
                 "quarter to": "Quarter to is 15 minutes before the hour: 45 minutes after the hour before."}[m.group(1)],
                f"So it's {m.group(3)}."]
    return None


@rule(51, "which_is_longer")
def _longer(text):
    f = fill(text)
    m = re.fullmatch(r"(\S+) in or (\S+) in: longer is (\S+) in", f)
    return [f"Compare the whole inches first, then the parts.", f"{m.group(3)} inches is longer."] if m else None


@rule(51, "quarter_inches")
def _quarters(text):
    f = fill(text)
    m = re.fullmatch(r"(\S+) inches = (\d+) quarter inches", f)
    return ["Each inch is 4 quarter inches.", f"So {m.group(1)} inches is {m.group(2)} quarter inches."] if m else None


@rule(54, "about_how_much")
def _about(text):
    f = fill(text)
    m = re.fullmatch(rf"({NUM}) ([+{MINUS}]) ({NUM}) is about ({NUM})", f)
    if not m:
        return None
    a, op, b, r = m.groups()
    ra, rb = round(num(a), -3), round(num(b), -3)
    return [f"Round each to the nearest thousand: {fmt(ra)} and {fmt(rb)}.", f"{fmt(ra)} {op} {fmt(rb)} = {r}."]


@rule(86, "compare_the_rules")
def _rules(text):
    f = fill(text)
    m = re.fullmatch(r"A: add (\d+), B: add (\d+)\. Each B term is (\d+) times the A term", f)
    return [f"Each step, B adds {m.group(2)} and A adds {m.group(1)}.", f"{m.group(2)} {DIV} {m.group(1)} = {m.group(3)}."] if m else None


@rule(88, "fair_shares")
def _fair(text):
    f = fill(text)
    m = re.fullmatch(r"(.+?) (\S+) shared by (\d+) = (\d+)/8 \S+ each", f)
    if not m:
        return None
    tot = parse_frac(m.group(1))
    return [f"Change it to eighths: {m.group(1)} = {int(tot * 8)}/8.", f"{int(tot * 8)} {DIV} {m.group(3)} = {m.group(4)}, so {m.group(4)}/8 each."]


@rule(88, "add_the_data")
def _data(text):
    f = fill(text)
    parts = f.split(" = ")[0].split(" + ")
    tops = [int(p.split("/")[0]) for p in parts]
    return ["Same bottoms: add the tops.", " + ".join(map(str, tops)) + f" = {sum(tops)}, so {sum(tops)}/8."]


@rule(83, "more_than_one_each")
def _share_mixed(text):
    f = fill(text)
    m = re.fullmatch(r"(\d+) ÷ (\d+) = (\d+)/\2 = (\d+) (\d+)/\2", f)
    if not m:
        return None
    a, b, _, w, r = m.groups()
    return [f"Sharing {a} among {b} gives each {a}/{b}.", f"{a} {DIV} {b} = {w} R {r}, so {w} wholes and {r}/{b}."]


@rule(83, "write_it_as_a_fraction")
def _as_frac(text):
    f = fill(text)
    m = re.fullmatch(r"(\d+) ÷ (\d+) = (\d+)/(\d+)", f)
    return [f"Sharing {m.group(1)} wholes among {m.group(2)}: each gets {m.group(1)} pieces of 1/{m.group(2)}.",
            f"{m.group(1)} {DIV} {m.group(2)} = {m.group(1)}/{m.group(2)}."] if m else None


@rule(62, "make_the_bottoms_the_same")
def _same_bottoms(text):
    f = fill(text)
    m = re.fullmatch(r"(\d+)/(\d+) = (\d+)/(\d+) and (\d+)/(\d+) = (\d+)/\4 so \1/\2 ([<>=]) \5/\6", f)
    if not m:
        return None
    a, b, c, n, d, e, g, s = m.groups()
    return [f"Change both to {n}ths: {a}/{b} = {c}/{n} and {d}/{e} = {g}/{n}.", f"Compare the tops: {c} and {g}, so {a}/{b} {s} {d}/{e}."]


@rule(63, "split_it_up")
def _split(text):
    f = fill(text)
    m = re.fullmatch(r"(\d+)/(\d+) = (\d+)/\2 \+ (\d+)/\2", f)
    return [f"The parts must add up to {m.group(1)}/{m.group(2)}.", f"{m.group(1)} {MINUS} {m.group(3)} = {m.group(4)}."] if m else None


@rule(80, "same_bottoms")
def _unlike(text):
    f = fill(text)
    m = re.fullmatch(rf"(\d+)/(\d+) ([+{MINUS}]) (\d+)/(\d+) = (\d+)/(\d+) \3 (\d+)/\7 = (\d+)/\7", f)
    if not m:
        return None
    a, b, op, c, d, e, n, g, r = m.groups()
    return [f"Make the bottoms the same: {n}.", f"{a}/{b} = {e}/{n} and {c}/{d} = {g}/{n}.",
            f"{e}/{n} {op} {g}/{n} = {r}/{n}."]


@rule(65, "as_a_mixed_number")
def _times_mixed(text):
    f = fill(text)
    m = re.fullmatch(r"(\d+) × (\d+)/(\d+) = (\d+)/\3 = (\d+) (\d+)/\3", f)
    if not m:
        return None
    k, a, b, t, w, r = m.groups()
    return [f"{k} groups of {a}/{b}: {k} {TIMES} {a} = {t}, so {t}/{b}.", f"{t} {DIV} {b} = {w} R {r}: {w} {r}/{b}."]


@rule(81, "smaller_or_bigger")
def _scale(text):
    m = re.fullmatch(r"(.+) × (\d+) \[([<>=])\] \2", text.strip())
    if not m:
        return None
    f = parse_frac(m.group(1))
    return [f"Multiplying by {'more' if f > 1 else 'less'} than 1 makes the number {'bigger' if f > 1 else 'smaller'}.",
            f"{m.group(1)} is {'more' if f > 1 else 'less'} than 1, so {m.group(1)} {TIMES} {m.group(2)} {m.group(3)} {m.group(2)}."]


@rule(70, "how_far_apart")
def _apart(text):
    return g_mixed(70, "", text)


# ---------------------------------------------------------------------------------------------------- export


def tokens(text):
    """Text with [answer] boxes -> drawing tokens and the answers, in order."""
    out, ans = [], []

    def piece(t):
        if t.startswith("[") and t.endswith("]") and t.count("[") == 1:
            ans.append(t[1:-1])
            return {"b": len(ans) - 1}
        return {"t": t}

    for raw in text.split():
        m = re.fullmatch(r"(\[[^\]]*\]|\d+)/(\[[^\]]*\]|\d+)([,.;:]?)", raw)
        if m and not re.fullmatch(r"\d+/\d+/\d+", raw):
            out.append({"f": [piece(m.group(1)), piece(m.group(2))]})
            if m.group(3):
                out.append({"t": m.group(3)})
            continue
        m = re.fullmatch(r"(\d+)\^(\d+)", raw)
        if m:
            out.append({"p": [m.group(1), m.group(2)]})
            continue
        bits = re.split(r"(\[[^\]]*\])", raw)
        for b in bits:
            if b:
                out.append(piece(b) if b.startswith("[") else {"t": b})
        out[-1]["end"] = True  # a space after this token
    for t in out:
        if "f" in t or "p" in t:
            t["end"] = True
    return out, ans


def problem(packet, skill, item):
    """One problem as the website gets it."""
    kind = skill.kind
    p = {}
    if kind == "word":
        story, sentence, answer, unit = item
        p["s"] = story
        toks, ans = tokens(f"[{answer}]" + (f" {unit}" if unit else ""))
    elif kind in ("yes_text", "yes_text1"):
        p["s"] = item[0]
        toks, ans = [{"yes": 0}], ["yes" if item[1] else "no"]
    elif kind in ("pow", "pow6"):
        lhs, val = item
        toks, ans = tokens(f"{lhs} = [{val}]")
    else:
        text = item[0] if isinstance(item, tuple) else item
        toks, ans = tokens(re.sub(r"\{(\d+)\}", r"\1", text))
    p["q"], p["a"] = toks, ans
    p["x"] = explain(packet, skill.id, kind, item) or [f"The answer is {', '.join(ans)}."]
    p["fb"] = 1 if not explain(packet, skill.id, kind, item) else 0
    nums = [num(n) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", json.dumps([item]))]
    p["size"] = float(sum(abs(n) for n in nums[:6])) + 3 * len(ans)
    return p


def skill_problems(folder, skill, n=POOL):
    packet = S.number(folder)
    seen, out = set(), []
    items = skill.make(random.Random(f"online:{folder}:{skill.id}"), n * 4)
    for it in items:
        k = json.dumps(it, default=str, ensure_ascii=False)
        if k in seen:
            continue
        seen.add(k)
        out.append(problem(packet, skill, it))
        if len(out) == n:
            break
    # difficulty tiers by size, inside the skill
    order = sorted(range(len(out)), key=lambda i: out[i]["size"])
    for rank, i in enumerate(order):
        out[i]["d"] = 1 + rank * 3 // max(1, len(out))
        del out[i]["size"]
    return out


GRADE_OF = {}


def grade(packet):
    for name, lo, hi in (("K", 0, 2), ("1", 3, 9), ("2", 10, 32), ("3", 33, 52), ("4", 53, 72), ("5", 73, 90), ("6", 91, 999)):
        if lo <= packet <= hi:
            return name


def export(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    order = [p[0] for p in W.PACKETS]
    teach = {n: i for i, n in enumerate(W.TEACHING_ORDER)}
    order.sort(key=lambda f: teach.get(S.number(f), 999))
    units = []
    for folder in order:
        skills = [t for t in S.TYPES.get(folder, []) if t.kind in TEXT_KINDS]
        if not skills:
            continue
        slug = folder.split("-", 1)[1]
        packet = S.number(folder)
        data = {"slug": slug, "skills": {}}
        meta = []
        for t in skills:
            probs = skill_problems(folder, t)
            if len(probs) < 5:
                continue
            for p in probs:
                p.pop("fb", None)
            data["skills"][t.id] = probs
            # the worked example: a middle problem with the fullest explanation, so it shows the whole method
            mid = [p for p in probs if p["d"] == 2] or probs
            meta.append({"id": t.id, "label": t.label, "help": t.help, "count": len(probs),
                         "example": max(mid, key=lambda p: (len(p["x"]), -probs.index(p)))})
        if not meta:
            continue
        (out / f"{slug}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        units.append({"slug": slug, "folder": folder, "number": packet, "title": S.NAME[folder], "grade": grade(packet),
                      "skills": meta})
    (out / "index.json").write_text(json.dumps({"version": 1, "units": units}, ensure_ascii=False, indent=1))
    return units


def report():
    tot = fb = 0
    for folder, types in S.TYPES.items():
        for t in types:
            if t.kind not in TEXT_KINDS:
                continue
            probs = []
            items = t.make(random.Random(1), 40)
            n_fb = 0
            for it in items:
                st = explain(S.number(folder), t.id, t.kind, it)
                tot += 1
                if not st:
                    fb += 1
                    n_fb += 1
            if n_fb:
                ex = items[0]
                print(f"{S.number(folder):>3} {t.id:<30} {t.kind:<8} fallback {n_fb}/40  e.g. {repr(ex)[:90]}")
    print(f"\n{tot - fb} of {tot} problems have worked steps ({fb} fall back to the answer).")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "export":
        units = export(sys.argv[2])
        print(f"{len(units)} units, {sum(len(u['skills']) for u in units)} skills")
    else:
        report()
