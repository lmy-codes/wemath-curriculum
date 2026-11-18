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

import io
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
PICTURE_POOL = 60  # picture skills: fewer (each is drawn)
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
        return [f"Same bottoms: how many {c}s fit in {a}?", f"{a} {DIV} {c} = " + (f"{a // c}." if a % c == 0 else f"{a}/{c}" + (f" = {frac_str(F(a, c))}." if F(a, c).denominator != c else "."))]
    n = b * d // math.gcd(b, d)
    ea, ec = a * n // b, c * n // d
    return [f"How many {y} fit in {x}? Make the pieces the same size: {n}ths.", f"{x} = {ea}/{n} and {y} = {ec}/{n}.",
            f"How many {ec}s fit in {ea}? {ea} {DIV} {ec} = " + (f"{ea // ec}." if ea % ec == 0 else f"{ea}/{ec}" + (f" = {frac_str(F(ea, ec))}." if F(ea, ec).denominator != ec else "."))]


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
    if m and "[=]" not in text:
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


# ---------------------------------------------------------------------------------------------------- picture cards
# Every other card is drawn exactly as on the packets (an image), with the answer boxes and the "circle it" choices
# found while drawing it: the website puts typing boxes over the printed boxes, and the student taps what the key
# circles. Cards answered only by drawing (shade it, draw the hands, plot the points …) are left out.

import tempfile as _tmp

NO_SCREEN = {"shade", "tally_draw", "frac_shade", "pv_fill", "dstack", "grid_plot", "draw_hands"}
# Cards whose answer key rings a choice (a word, a number, a shape): the rings become things to tap.
TAP_KINDS = set(W.ANSWER_OF) | {"round_card", "name_share", "round_dec", "gcf_lists", "all_names", "tri_sides", "net_ok",
                                "which_more", "biggest", "biggest_dec", "is_quad", "name_quad", "quad_fact", "prime"}
TAP_KINDS -= {"mixed1", "mixed2", "mixed3", "yes_text", "yes_text1", "draw_hands", "shade", "frac_shade", "match_frac",
              "shade_more", "show_amount", "tally_draw", "area2", "partial2", "div_area", "partial_q", "add_strip", "to_mixed",
              "groups_frac", "read_grid", "read_tenths", "conv_table", "rect_formula", "make_x8", "read_x8", "shift",
              "factor_array", "cut_strip", "find_whole", "unit_name", "wholes", "more_whole", "count_pieces", "frac_name"}


def card_size(kind):
    k = W.KINDS[kind]
    return (W.CW - k.gap * (k.cols - 1)) / k.cols, k.h


def draw_card(kind, item, key):
    """One card alone on a page its size: (pdf bytes, page w, page h, [(rect, answer)], [ring rects])."""
    w, h = card_size(kind)
    pw, ph = w + 16, h + 8  # the whole card (gutter included) with a margin; trimmed to the drawing later
    fields, rings = [], []
    with _tmp.TemporaryDirectory() as tmp:
        bk = W.Book(Path(tmp) / "c.pdf", key, subtitle="", asked={})
        bk.rec, bk.repeat_ok = [], True
        c = bk.c
        c.setPageSize((pw, ph))
        cur = {}
        ob, ov, oe = bk.box, bk.value, c.ellipse

        def box(x, y, bw, bh, value=None, size=16, reveal=None):
            cur["r"] = (x, y, bw, bh)
            try:
                return ob(x, y, bw, bh, value, size, reveal)
            finally:
                cur.pop("r", None)

        def value(cx, cy, value, size=16, reveal=None):
            if reveal is None and value not in (None, ""):
                r = cur.get("r") or (cx - max(14, size * 1.2), cy - size * 0.8, max(28, size * 2.4), size * 1.6)
                fields.append((r, str(value)))
            return ov(cx, cy, value, size, reveal)

        def ellipse(x1, y1, x2, y2, stroke=1, fill=0):
            if key and getattr(c, "_strokeColorObj", None) == W.T.answer:
                rings.append((min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)))
            return oe(x1, y1, x2, y2, stroke=stroke, fill=fill)

        bk.box, bk.value, c.ellipse = box, value, ellipse
        W.KINDS[kind].draw(bk, 8, 4, w, item)
        c.showPage()
        c.save()
        data = (Path(tmp) / "c.pdf").read_bytes()
    return data, pw, ph, fields, (rings if kind in TAP_KINDS else [])


def trim_box(data, pw, ph, margin=6):
    """The part of the page with drawing on it, in points: (x, y from the top, w, h)."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageChops
    doc = pdfium.PdfDocument(data)
    img = doc[0].render(scale=1).to_pil().convert("RGB")
    doc.close()
    box = ImageChops.difference(img, Image.new("RGB", img.size, "white")).getbbox() or (0, 0, img.width, img.height)
    sx, sy = pw / img.width, ph / img.height
    x0, y0 = max(0, box[0] * sx - margin), max(0, box[1] * sy - margin)
    x1, y1 = min(pw, box[2] * sx + margin), min(ph, box[3] * sy + margin)
    return x0, y0, x1 - x0, y1 - y0


def card_png(kind, item, scale=2.5):
    import pypdfium2 as pdfium
    W.T = W.theme(True)
    data, pw, ph, _, _ = draw_card(kind, item, False)
    x, y, w, h = trim_box(data, pw, ph)
    doc = pdfium.PdfDocument(data)
    img = doc[0].render(scale=scale).to_pil().convert("RGB")
    doc.close()
    img = img.crop((round(x * scale), round(y * scale), round((x + w) * scale), round((y + h) * scale)))
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def pct(r, crop, ph):
    """A rect in page points (y from the bottom) as % of the trimmed picture."""
    x, y, w, h = r
    cx, cy, cw, chh = crop
    return [round(100 * (x - cx) / cw, 2), round(100 * (ph - y - h - cy) / chh, 2), round(100 * w / cw, 2), round(100 * h / chh, 2)]


# ---------------------------------------------------------------------- the question of each picture card

# Founder: a picture card on screen must say what it asks. ASK[kind](item) is one or two sentences built from
# the problem's own numbers, shown above the picture (the packet card's section subtitle alone wasn't enough).


def _m(op):
    return MINUS if op in ("-", MINUS) else "+"


def _f(a, b):
    return f"{a}/{b}"


_NTH = {2: "halves", 3: "thirds", 4: "fourths", 5: "fifths", 6: "sixths", 7: "sevenths", 8: "eighths", 9: "ninths",
        10: "tenths", 12: "twelfths", 100: "hundredths"}


def _nth(b):
    return _NTH.get(b, f"{b}ths")


def _plural(word):
    if word in ("fish", "sheep"):
        return word
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    return word + ("es" if word.endswith(("s", "x", "ch", "sh")) else "s")


def _one(word):
    """boxes -> box, hours -> hour."""
    if word.endswith("es") and word[:-2].endswith(("x", "s", "ch", "sh")):
        return word[:-2]
    return word[:-1] if word.endswith("s") else word


def _sh(kind):
    return {"strip": "strip", "circle": "circle", "rect": "rectangle", "tall": "rectangle", "square": "square",
            "hsquare": "square", "grid": "square", "diag": "square"}.get(kind, "shape")


ASK = {
    "pic_add": lambda it: f"{it[1]} and {it[2]} more. How many in all?",
    "sp_wide_add": lambda it: f"{it[1]} and {it[2]} more. How many in all?",
    "pic_take": lambda it: f"There are {it[1]}. Take away {it[2]}. How many are left?",
    "sp_wide_take": lambda it: f"There are {it[1]}. Take away {it[2]}. How many are left?",
    "wide_story": lambda it: "Write the number sentence for the picture: the first number, + or − in the circle, "
                             "the second number, and the answer.",
    "draw_solve": lambda it: f"Draw circles to find {it[0]} {_m(it[1])} {it[2]}.",
    "frame_buddy": lambda it: "How many dots are in the ten-frame? How many more make 10?",
    "kframe": lambda it: f"The frame has {it} dots. How many more dots fill it to 10?",
    "more10": lambda it: f"How many more does {it[1]} need to make 10?",
    "buddy_yesno": lambda it: f"Do {it[0]} make 10? Tap yes or no.",
    "teen": lambda it: f"A full ten and {it[1]} more. How many is that?",
    "kteen": lambda it: f"A full ten and {it} more. How many is that?",
    "three": lambda it: f"Add {it[0]} + {it[1]} + {it[2]}. Find the two numbers that make 10 first, then add the last one.",
    "ba": lambda it: f"Find {it[0]} + {it[1]}. Break {it[1]} apart: the buddy that makes 10 with {it[0]}, and what is left over.",
    "ladder": lambda it: f"Find {it[0]} + {it[1]}. First the buddy that takes {it[0]} to 10, then the rest.",
    "hint": lambda it: f"Find {it[0]} + {it[1]}. Write the next ten after {it[0]} too.",
    "jump_dots": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Jump down from {it[0]} to 10, then jump the rest. Fill in the jumps and the answer.",
    "jump": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Jump down from {it[0]} to 10, then jump the rest. Fill in the jumps and the answer.",
    "jump_less": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Fill in the two jumps (to 10, then the rest) and the answer.",
    "jump_big": lambda it: f"Find {it[0]} {MINUS} {it[1]} by jumping up from {it[1]}: to the next ten, then to {it[0]}. "
                           "Fill in the jumps and add them.",
    "double_dots": lambda it: f"Each row has {it} dot{'s' if it != 1 else ''}. What is double {it}?",
    "near_dots": lambda it: f"Find double {it[0]}, then {it[0]} + {it[1]} (one more).",
    "count_to": lambda it: "How many tens and how many ones are in the picture? What number is it?",
    "draw_qt": lambda it: f"How many tens and ones do you draw for {it}?",
    "count_tens": lambda it: "How many tens are in the picture? What number is it?",
    "which_more": lambda it: f"Which is more, {it[0]} or {it[1]}? Tap it.",
    "ten_pic": lambda it: "What is 10 less than the number in the picture?" if it[1] in ("-", MINUS)
    else "What is 10 more than the number in the picture?",
    "side": lambda it: f"What is 10 less than {it}? What is 10 more than {it}?",
    "chain10": lambda it: f"Start at {it[1]} and keep going {'up' if it[0] == '+' else 'down'} by 10. Fill in the missing numbers.",
    "add_tens_pic": lambda it: f"Find {it[0]} + {it[1]}. Add the tens in the picture.",
    "add_split": lambda it: f"Find {it[0]} + {it[1]}. Add the tens, add the ones, then put them together.",
    "sub_tens_pic": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Take away the tens.",
    "sub_split": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Take away the tens, take away the ones, then put them together.",
    "enough": lambda it: f"In {it[0]} {MINUS} {it[1]}, are there enough ones to take away without breaking a ten? Don't solve it.",
    "jump_up": lambda it: f"What goes with {it[0]} to make {it[1]}? Jump up from {it[0]} to the next ten, then to {it[1]}. "
                          "Fill in the stops and jumps, then add the jumps.",
    "find_stops": lambda it: f"What goes with {it[0]} to make {it[1]}? Fill in the stops (next ten, then the tens) and the jumps, "
                             "then add the jumps.",
    "break_ten": lambda it: f"Break one ten of {it} into ones. How many ones are there now?",
    "borrow_rows": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Break a ten, then take away the tens and the ones.",
    "col_add_boxes": lambda it: f"Add {it[0]} + {it[1]} in columns. Write the new ten in the carry box.",
    "line_up": lambda it: f"Write {it[0]} + {it[1]} in columns (tens under tens, ones under ones), then add.",
    "col_add": lambda it: f"Add {it[0]} + {it[1]}.",
    "sub_mat": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Open a ten on the mat, then subtract.",
    "col_sub_boxes": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Break a ten: write the new tens and ones digits, then subtract.",
    "col_sub": lambda it: f"Subtract {it[0]} {MINUS} {it[1]}.",
    "count_hto": lambda it: "How many hundreds, tens and ones are in the picture? What number is it?",
    "draw_hto": lambda it: f"How many hundreds, tens and ones do you draw for {it}?",
    "worth": lambda it: f"What is the {it[1]} in {it[0]} worth?",
    "bars5": lambda it: "Count the dots by fives. Write the total under each bar.",
    "chain": lambda it: f"Count by {it[1]}s from {it[0]}. Fill in the missing numbers.",
    "seq": lambda it: f"Count by {it[1]}s from {it[0]}. Fill in the missing numbers.",
    "count_by": lambda it: "What number are we counting by?",
    "cmp_pic": lambda it: f"Compare {it[0]} and {it[1]}. Write <, > or =.",
    "cmp_draw": lambda it: f"Compare {it[0]} and {it[1]}. Write <, > or =.",
    "order": lambda it: "Put the numbers in order from smallest to biggest.",
    "hund_pic": lambda it: "What is 100 less than the number in the picture?" if it[1] in ("-", MINUS)
    else "What is 100 more than the number in the picture?",
    "cross": lambda it: f"Fill in the number cross for {it}: 10 more to the right, 10 less to the left, 100 more above, 100 less below.",
    "chain_hund": lambda it: f"Start at {it[0]} and count by {abs(it[1])}s {'up' if it[1] > 0 else 'down'}. Fill in the missing numbers.",
    "add3_rows": lambda it: f"Find {it[0]} + {it[1]}. Add the hundreds, the tens and the ones, then put them together.",
    "col_add3_boxes": lambda it: f"Add {it[0]} + {it[1]} in columns. Write a new ten or hundred in its carry box.",
    "col_add3": lambda it: f"Add {it[0]} + {it[1]}.",
    "take3": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Cross out what is taken. What is left?",
    "sub3_rows": lambda it: f"Find {it[0]} {MINUS} {it[1]}. Take away the hundreds, the tens and the ones, then put them together.",
    "col_sub3": lambda it: f"Subtract {it[0]} {MINUS} {it[1]}.",
    "groups": lambda it: "How many groups? How many in each group? How many in all?",
    "eq_groups": lambda it: "Are the groups equal? Tap yes or no.",
    "array": lambda it: "How many rows? How many in each row? Add the rows to find how many in all.",
    "pairs_eo": lambda it: "Pair up the dots. Is the number even or odd?",
    "eo_ones": lambda it: f"Look at the ones digit of {it}. Is it even or odd?",
    "eo_word": lambda it: f"Is {it} even or odd? Write even or odd.",
    "hgrid": lambda it: f"{it} dots are filled. How many more fill the grid to 100?",
    "chain_any": lambda it: f"Count by {abs(it[1])}s {'up' if it[1] > 0 else 'down'} from {it[0]}. Fill in the missing numbers.",
    "direction": lambda it: "Is it counting forward or back? By how many?",
    "seq_any": lambda it: f"Count by {abs(it[1])}s {'up' if it[1] > 0 else 'down'} from {it[0]}. Fill in the missing numbers.",
    "share": lambda it: f"Share {it[1]} {_plural(it[0])} fairly on 2 plates. How many go on each plate?",
    "half_split": lambda it: f"Find half of {it}. Take half of the tens and half of the ones, then put them together.",
    "eq_share": lambda it: "Are the parts equal shares? Tap yes or no.",
    "name_share": lambda it: "How many equal parts is it cut into? Write the number and tap the name of one part.",
    "read_clock": lambda it: "What time does the clock show?",
    "read_minute": lambda it: "What time does the clock show? Read it to the minute.",
    "ampm": lambda it: "Is it a.m. or p.m.? Tap it.",
    "coins": lambda it: "How much money is it? Count the coins.",
    "symbol": lambda it: "Does it cost cents (¢) or dollars ($)? Tap the right one.",
    "tens_ones": lambda it: f"How many tens and ones make {it}? Then break one ten into ones: how many tens and ones now?",
    "bar": lambda it: "Find the number that goes in the box of the bar model.",
    "two_step": lambda it: f"{it[0]} Fill in step 1 and step 2.",
    "read_tape": lambda it: f"How long is the {it[0]}? Read the tape measure in {'centimeters' if it[2] == 'cm' else 'inches'}.",
    "unit_choice": lambda it: f"{it[0]} what? Tap the unit that makes sense.",
    "tally_read": lambda it: "How many tally marks are there?",
    "mini_bar": lambda it: f"Read the bar graph. {it[3][0]}",
    "times_groups": lambda it: "How many groups, and how many in each? Write the times fact and how many in all.",
    "times_array": lambda it: "How many rows, and how many in each row? Write the times fact and how many in all.",
    "break_array": lambda it: f"Find {it[0]} {TIMES} {it[1]} by breaking the array into two easier parts. Fill in the parts and add them.",
    "share_div": lambda it: f"Share {it[1]} {_plural(it[0])} on {it[2]} plates. How many on each plate? Write the division fact.",
    "think_times": lambda it: f"Find {it[0]} {DIV} {it[1]}. Think: {it[1]} {TIMES} what = {it[0]}?",
    "round_card": lambda it: f"Round {it[0]} to the nearest {it[1]}. Write the {it[1]} below and the {it[1]} above, then tap the closer one.",
    "tens_groups": lambda it: f"{it[0]} groups of {it[1]} tens. Fill in the times fact in tens, then the number.",
    "area_rows": lambda it: "How many rows of squares? How many in each row? What is the area?",
    "area_split": lambda it: "Find the area: break the rectangle into two parts at the dashed line, find each part, then add.",
    "unit_name": lambda it: f"The {_sh(it[0])} is cut into equal parts. What fraction is one part?",
    "find_whole": lambda it: f"The piece is 1/{it} of the whole. How many pieces like it make the whole?",
    "bigger_unit_plain": lambda it: f"Which piece is bigger, 1/{it[0]} or 1/{it[1]} of the same whole? Tap it.",
    "frac_name": lambda it: "What fraction is shaded? Write the top and the bottom.",
    "wholes": lambda it: "How many pieces are shaded, and how many wholes is that?",
    "more_whole": lambda it: "What fraction is shaded? It is more than one whole.",
    "vs_one": lambda it: f"Is {it[0]}/{it[1]} less than 1, equal to 1, or more than 1? Tap it.",
    "same_amount": lambda it: f"Do {it[0]}/{it[1]} and {it[2]}/{it[3]} show the same amount? Tap yes or no.",
    "match_frac": lambda it: f"How many {_nth(it[1])} are the same as {it[0][0]}/{it[0][1]}? Shade to match.",
    "compare_frac": lambda it: f"Compare {_f(*it[0])} and {_f(*it[1])}. Write <, > or =.",
    "biggest": lambda it: "Which fraction is the biggest? Tap it.",
    "group_frac": lambda it: f"What is {it[2]}/{it[1]} of {it[0]}?",
    "perim_add": lambda it: "Add all four sides. What is the perimeter?",
    "area_perim": lambda it: "Find the area (squares inside) and the perimeter (all around).",
    "jump_time": lambda it: f"How long is it from {it[0][0]}:{it[0][1]:02d} to {it[1][0]}:{it[1][1]:02d}? "
                            "Jump to the next o'clock, then to the end. Fill in the stops and the minutes.",
    "table_row": lambda it: f"Fill in the {it[0]}s row of the times table.",
    "table_piece": lambda it: "Fill in the missing numbers in this piece of the times table.",
    "eo_product": lambda it: f"Is {it[0]} {TIMES} {it[1]} even or odd? Tap it.",
    "balance": lambda it: f"The balance is level. How heavy is the {it[0]}? Add the weights.",
    "beaker": lambda it: "How much water is in the beaker? Read the marks (liters).",
    "sgraph": lambda it: "Read the graph and answer each question. Check the key: each picture or square stands for more than 1.",
    "quarter": lambda it: f"How long is the {it[0]}? Read the ruler to the nearest quarter inch.",
    "is_quad": lambda it: "Is the shape a quadrilateral (4 straight sides)? Tap yes or no.",
    "right_count": lambda it: "How many right angles does the shape have?",
    "name_quad": lambda it: "What is the best name for the shape? Tap it.",
    "quad_fact": lambda it: f"{it[0]} True or not? Tap yes or no.",
    "quick_th": lambda it: "How many thousands, hundreds, tens and ones are in the quick drawing? What number is it?",
    "big_stack": lambda it: f"{'Add' if it[2] == '+' else 'Subtract'} {it[0]:,} {_m(it[2])} {it[1]:,} in columns.",
    "area_mult": lambda it: f"Find {it[0]} {TIMES} {it[1]} with the area model: multiply each part, then add the parts.",
    "partial": lambda it: f"Find {it[0]} {TIMES} {it[1]}: multiply the tens and the ones, then add the parts.",
    "groups_rem": lambda it: f"Make groups of {it[1]} from {it[0]}. How many groups, and how many are left over?",
    "rem_think": lambda it: f"Find {it[0]} {DIV} {it[1]} with a times fact: the biggest {it[1]} {TIMES} ? that fits, then the remainder.",
    "area2": lambda it: f"Find {it[0]} {TIMES} {it[1]} with the area model: fill in each piece, then add the pieces.",
    "div_area": lambda it: f"Find {it[0]} {DIV} {it[1]} with the area model: divide each part, then add the answers.",
    "pairs": lambda it: f"Fill in the factor pairs of {it.split(' =')[0]}.",
    "prime": lambda it: f"Is {it} prime or composite? Tap it.",
    "cut_strip": lambda it: f"Cut each 1/{it[1]} piece into {it[2]} equal pieces. What fraction equals {it[0]}/{it[1]}?",
    "equal_q": lambda it: f"Is {_f(*it[0])} equal to {_f(*it[1])}? Tap yes or no.",
    "vs_half": lambda it: f"Is {it[0]}/{it[1]} more than, less than, or equal to 1/2? Tap it.",
    "add_strip": lambda it: f"Find {it[0]}/{it[2]} {_m(it[3])} {it[1]}/{it[2]} with the strip.",
    "to_mixed": lambda it: f"Write {it[1]}/{it[0]} as a mixed number: how many wholes and what fraction is left?",
    "groups_frac": lambda it: f"Find {it[0]} {TIMES} {it[1]}/{it[2]}: how many {_nth(it[2])} in all?",
    "read_grid": lambda it: "How many hundredths are shaded? Write it as a fraction and as a decimal.",
    "compare_grids": lambda it: f"Compare {it[0] / 100:g} and {it[1] / 100:g}. Write <, > or =.",
    "biggest_dec": lambda it: "Which decimal is the biggest? Tap it.",
    "conv_table": lambda it: f"Change {it[0]} to {it[1]}. Fill in the table.",
    "rect_formula": lambda it: f"A rectangle is {it[0]} {it[2]} by {it[1]} {it[2]}. Find its area and its perimeter.",
    "read_x8": lambda it: "Read the X chart and answer each question.",
    "angle_kind": lambda it: "Is the angle acute, right or obtuse? Tap it.",
    "read_protractor": lambda it: "How many degrees is the angle? Read the protractor.",
    "line_name": lambda it: "Is it a segment, a ray or a line? Tap it.",
    "two_lines": lambda it: "Are the lines parallel, perpendicular or neither? Tap it.",
    "triangle_kind": lambda it: "Is it a right, acute or obtuse triangle? Tap it.",
    "shift": lambda it: f"Find {it[0]} {TIMES if it[1] == 'x' else DIV} {10 ** it[2]:,}. Move the digits in the place-value chart.",
    "order_dec": lambda it: "Put the decimals in order from smallest to biggest.",
    "round_dec": lambda it: f"Round {it[0]} to the nearest {['whole number', 'tenth', 'hundredth'][it[1]]}. "
                            "Write the one below and the one above, then tap the closer one.",
    "mrows": lambda it: f"Find {it[0]} {TIMES} {it[1]}: multiply by the ones, then by the tens, then add the rows.",
    "partial_q": lambda it: f"Find {it[0]:,} {DIV} {it[1]}: divide each part, then add the answers.",
    "frac_grid": lambda it: f"Find {it[0]}/{it[1]} {TIMES} {it[2]}/{it[3]}. Shade the overlap and write the fraction.",
    "cube_count": lambda it: "How many unit cubes make the box? What is its volume?",
    "share_frac": lambda it: f"Share {it[0]} strips fairly among {it[1]} people. How much does each one get?",
    "unit_cut": lambda it: f"Share a 1/{it[0]} piece among {it[1]}. What fraction of the whole does each one get?",
    "two_rules": lambda it: f"Rule A: start at 0 and add {it[0]}. Rule B: start at 0 and add {it[1]}. "
                            f"Each B term is how many times the A term next to it?",
    "read_share": lambda it: "Read the X chart and answer each question.",
    "grid_read": lambda it: "Write each point's pair: over, then up.",
    "all_names": lambda it: "Tap every name that fits the shape.",
    "tri_sides": lambda it: "Is the triangle equilateral, isosceles or scalene? Tap it.",
    "ratio_pic": lambda it: "Write the ratio of circles to squares.",
    "ratio_tab": lambda it: f"{it[2]} {it[0]} for every {it[3]} {it[1]}. Fill in the {it[1]} row of the table.",
    "rate_tab": lambda it: f"{it[3]} {it[1]} for {it[2]} {it[0]}. How many {it[1]} for 1 {_one(it[0])}? "
                           f"Then fill in the {it[1]} for {' and '.join(map(str, it[4]))} {it[0]}.",
    "grid_pct": lambda it: "What percent of the grid is shaded?",
    "fit_strip": lambda it: f"How many {it[2]}/{it[3]} pieces fit in {it[0]}/{it[1]}?",
    "long_div": lambda it: f"Find {it[0]:,} {DIV} {it[1]} with long division.",
    "gcf_lists": lambda it: f"Tap the factors that {it[0]} and {it[1]} share. Which is the greatest?",
    "thermo_read": lambda it: "What temperature does the thermometer show?",
    "x_bar": lambda it: f"x + {it[0]} = {it[0] + it[1]}. Find the missing part.",
    "para": lambda it: "Find the area of the parallelogram: base × height.",
    "tri": lambda it: "Find the area of the triangle: half of base × height.",
    "trap": lambda it: "Find the area of the trapezoid: add the two bases, times the height, then half.",
    "house": lambda it: "Find the area: the rectangle plus the triangle on top.",
    "half_cubes": lambda it: "How many half-unit cubes fill the box? How many whole cubes is that?",
    "net_ok": lambda it: "Does the net fold into a cube? Tap yes or no.",
    "cube_net": lambda it: "Find the area of one face, then the surface area of the cube (all 6 faces).",
    "net": lambda it: "Find the area of each pair of faces, then the surface area of the box.",
    "pyramid": lambda it: "Find the area of the square base and of the four triangles, then the surface area.",
    "level": lambda it: "Even out the towers: how many blocks in all, and how many in each tower? That is the mean.",
    "median": lambda it: "Write the numbers in order. What is the median (the middle number)?",
    "xstats": lambda it: "Read the X chart: find the median, the mode, the mean and the range.",
    "freq": lambda it: "Count how many numbers fall in each group.",
    "hist": lambda it: "Read the histogram and answer each question.",
    "make_x": lambda it: "Read the X chart and answer each question.",
}


def ask(kind, item):
    f = ASK.get(kind)
    try:
        return f(item) if f else None
    except Exception:
        return None


def picture_problem(packet, skill, item):
    W.T = W.theme(True)
    _, pw, ph, fields, rings = draw_card(skill.kind, item, True)
    if not fields and not rings:
        return None
    crop = trim_box(draw_card(skill.kind, item, False)[0], pw, ph)
    ans = [a for _, a in fields]
    steps = explain_picture(packet, skill.kind, item, ans) or []
    if not steps:
        steps = ["Fill in: " + ", ".join(ans) + "."] if ans else []
    if rings and not ans:
        right = W.ANSWER_OF.get(skill.kind, lambda it: None)(item)
        if right and not any(right.lower() in s.lower() for s in steps):
            steps.append(f"The answer is {right}.")
    p = {"img": [round(crop[2], 1), round(crop[3], 1)], "f": [pct(r, crop, ph) for r, _ in fields], "a": ans, "x": steps,
         "rings": [pct(r, crop, ph) for r in rings], "n": len(rings)}
    q = ask(skill.kind, item)
    if q:
        p["s"] = q
    return p


def _ints(it):
    return [x for x in (it if isinstance(it, (tuple, list)) else [it]) if isinstance(x, int)]


def explain_picture(packet, kind, it, ans):
    try:
        f = PIC.get(kind)
        st = f(it, ans, packet) if f else None
    except Exception:
        st = None
    return st


def _sub(a, b, p):
    return sub_steps(a, b, p)


def _place_count(n):
    parts = places(n)
    return [", ".join(f"{fmt(v)} is {v // 10 ** (len(str(v)) - 1)} {name}" for v, name in parts) + ".", f"Together: {fmt(n)}."]


PIC = {
    "pic_add": lambda it, a, p: add_steps(it[1], it[2], p), "sp_wide_add": lambda it, a, p: add_steps(it[1], it[2], p),
    "pic_take": lambda it, a, p: [f"Start with {it[1]}. Cross out {it[2]}.", f"Count the ones left: {it[1] - it[2]}."],
    "sp_wide_take": lambda it, a, p: [f"Start with {it[1]}. Cross out {it[2]}.", f"Count the ones left: {it[1] - it[2]}."],
    "wide_story": lambda it, a, p: [f"The number sentence: {it[1]} {it[2].replace('-', MINUS)} {it[3]} = {a[-1]}."]
    + (add_steps(it[1], it[3], p) if it[2] == "+" else [f"Take away {it[3]} from {it[1]}: {it[1] - it[3]} left."]),
    "draw_solve": lambda it, a, p: [f"Draw {it[0]} circles" + (f", then {it[2]} more." if it[1] == "+" else f", then cross out {it[2]}."),
                                    f"Count them: {a[-1]}."],
    "frame_buddy": lambda it, a, p: [f"The frame has {it} dots, so {10 - it} boxes are empty.", f"{it} and {10 - it} are Ten Buddies."],
    "kframe": lambda it, a, p: [f"Count the empty boxes: {10 - it}.", f"{it} and {10 - it} are Ten Buddies."],
    "more10": lambda it, a, p: [f"{it[1]} needs {it[2]} more to make 10: {it[1]} and {it[2]} are Ten Buddies."],
    "teen": lambda it, a, p: [f"A full ten and {it[1]} more.", f"10 + {it[1]} = {10 + it[1]}."],
    "kteen": lambda it, a, p: [f"A full ten and {it} more.", f"10 + {it} = {10 + it}."],
    "three": lambda it, a, p: _three(it),
    "ba": lambda it, a, p: add_steps(it[0], it[1], p), "ladder": lambda it, a, p: add_steps(it[0], it[1], p),
    "hint": lambda it, a, p: add_steps(it[0], it[1], p),
    "jump_dots": lambda it, a, p: _sub(it[0], it[1], 5), "jump": lambda it, a, p: _sub(it[0], it[1], 5),
    "jump_less": lambda it, a, p: _sub(it[0], it[1], 5), "jump_big": lambda it, a, p: _sub(it[0], it[1], 5),
    "double_dots": lambda it, a, p: [f"Two rows of {it}: a double.", f"{it} + {it} = {2 * it}."],
    "near_dots": lambda it, a, p: add_steps(it[0], it[1], 6),
    "count_to": lambda it, a, p: [f"Count the sticks: {it // 10} tens. Count the loose dots: {it % 10} ones.", f"{it // 10} tens and {it % 10} ones is {it}."],
    "draw_qt": lambda it, a, p: [f"{it} is {it // 10} tens and {it % 10} ones.", f"Draw {it // 10} lines and {it % 10} dots."],
    "count_tens": lambda it, a, p: [f"Count the sticks: {it // 10} tens.", f"{it // 10} tens is {it}."],
    "which_more": lambda it, a, p: [f"Compare the tens first: {it[0] // 10} tens and {it[1] // 10} tens.", f"{max(it)} is more."],
    "ten_pic": lambda it, a, p: [f"{'One more ten' if it[1] == '+' else 'One ten crossed out'}: the tens digit goes {'up' if it[1] == '+' else 'down'} by 1.", f"So {a[0]}."],
    "side": lambda it, a, p: [f"10 less: {it} has one ten fewer, {it - 10}.", f"10 more: one ten more, {it + 10}."],
    "chain10": lambda it, a, p: [f"Each step {'takes away' if it[0] == MINUS else 'adds'} a ten: only the tens digit changes.", ", ".join(a) + "."],
    "add_tens_pic": lambda it, a, p: add_steps(it[0], it[1], p), "add_split": lambda it, a, p: add_steps(it[0], it[1], 9),
    "sub_tens_pic": lambda it, a, p: _sub(it[0], it[1], 10), "sub_split": lambda it, a, p: _sub(it[0], it[1], 10),
    "enough": lambda it, a, p: [f"Look at the ones: {it[0] % 10} and {it[1] % 10}.",
                                f"{it[0] % 10} {'is' if it[0] % 10 >= it[1] % 10 else 'is not'} enough to take away {it[1] % 10}, so {'yes' if it[0] % 10 >= it[1] % 10 else 'no'}."],
    "jump_up": lambda it, a, p: missing_add(it[0], it[1]), "find_stops": lambda it, a, p: missing_add(it[0], it[1]),
    "break_ten": lambda it, a, p: [f"{it} is {it // 10} tens and {it % 10} ones.", f"Break one ten into 10 ones: {it // 10 - 1} tens and {it % 10 + 10} ones."],
    "borrow_rows": lambda it, a, p: _sub(it[0], it[1], 12),
    "col_add_boxes": lambda it, a, p: column_add(it[0], it[1]), "line_up": lambda it, a, p: column_add(it[0], it[1]),
    "col_add": lambda it, a, p: column_add(it[0], it[1]),
    "sub_mat": lambda it, a, p: column_sub(it[0], it[1]), "col_sub_boxes": lambda it, a, p: column_sub(it[0], it[1]),
    "col_sub": lambda it, a, p: column_sub(it[0], it[1]),
    "count_hto": lambda it, a, p: _place_count(it), "draw_hto": lambda it, a, p: _place_count(it),
    "worth": lambda it, a, p: [f"Find the place of the {it[1]} in {it[0]}.", f"There it is worth {a[0]}."],
    "bars5": lambda it, a, p: ["Each bar has 5 dots: count by 5s.", ", ".join(str(5 * i) for i in range(1, it + 1)) + "."],
    "chain": lambda it, a, p: [f"Each step adds {it[1]}.", ", ".join(a) + "."],
    "chain_any": lambda it, a, p: [f"Each step {'adds' if it[1] > 0 else 'takes away'} {abs(it[1])}.", ", ".join(a) + "."],
    "chain_hund": lambda it, a, p: [f"Each step {'adds' if it[1] > 0 else 'takes away'} {abs(it[1])}.", ", ".join(a) + "."],
    "seq": lambda it, a, p: [f"Each step adds {it[1]}.", "The missing numbers: " + ", ".join(a) + "."],
    "seq_any": lambda it, a, p: [f"Each step {'adds' if it[1] > 0 else 'takes away'} {abs(it[1])}.", "The missing numbers: " + ", ".join(a) + "."],
    "count_by": lambda it, a, p: [f"Find the jump between neighbours: {it[1]} {MINUS} {it[0]} = {it[1] - it[0]}.", f"We're counting by {a[0]}s."],
    "direction": lambda it, a, p: [f"From {it[0]} to {it[1]} is {'up' if it[1] > it[0] else 'down'} {abs(it[1] - it[0])}.", f"Counting {a[0]} by {a[1]}."],
    "cmp_pic": lambda it, a, p: _cmp(it[0], it[1], a), "cmp_draw": lambda it, a, p: _cmp(it[0], it[1], a),
    "order": lambda it, a, p: ["Compare the hundreds, then the tens, then the ones.", "From smallest: " + ", ".join(a) + "."],
    "hund_pic": lambda it, a, p: [f"{'One more hundred' if it[1] == '+' else 'One hundred less'}: only the hundreds digit changes.", f"So {a[0]}."],
    "cross": lambda it, a, p: [f"10 more and 10 less change the tens digit; 100 more and 100 less change the hundreds digit.", f"Around {it}: " + ", ".join(a) + "."],
    "add3_rows": lambda it, a, p: column_add(it[0], it[1]), "col_add3_boxes": lambda it, a, p: column_add(it[0], it[1]),
    "col_add3": lambda it, a, p: column_add(it[0], it[1]),
    "take3": lambda it, a, p: column_sub(it[0], it[1]), "sub3_rows": lambda it, a, p: column_sub(it[0], it[1]),
    "col_sub3": lambda it, a, p: column_sub(it[0], it[1]),
    "groups": lambda it, a, p: [f"{it[0]} groups of {it[1]}: " + " + ".join([str(it[1])] * it[0]) + f" = {it[0] * it[1]}."],
    "eq_groups": lambda it, a, p: [f"The groups have {', '.join(map(str, it))}.", "Equal groups all have the same number: " + ("yes." if len(set(it)) == 1 else "no.")],
    "array": lambda it, a, p: [f"{it[0]} rows of {it[1]}: " + " + ".join([str(it[1])] * it[0]) + f" = {it[0] * it[1]}."],
    "pairs_eo": lambda it, a, p: [f"Make pairs: {it // 2} pairs" + (", and 1 is left over." if it % 2 else ", none left over."), f"{it} is {'odd' if it % 2 else 'even'}."],
    "eo_ones": lambda it, a, p: [f"Look at the ones digit: {it % 10}.", f"{it % 10} is {'odd' if it % 2 else 'even'}, so {it} is {'odd' if it % 2 else 'even'}."],
    "eo_word": lambda it, a, p: [f"Look at the ones digit: {it % 10}.", f"So {it} is {'odd' if it % 2 else 'even'}."],
    "hgrid": lambda it, a, p: [f"{it} dots are filled. The tens make 9: {it // 10} and {9 - it // 10}. The ones make 10: {it % 10} and {10 - it % 10}." if it % 10 else f"{it} + {100 - it} = 100.", f"So {it} + {100 - it} = 100."],
    "share": lambda it, a, p: [f"Share {it[1]} on two plates, one at a time.", f"Each plate gets {it[1] // 2}: half of {it[1]} is {it[1] // 2}."],
    "half_split": lambda it, a, p: [f"Split {it} into tens and ones: {it // 10 * 10} and {it % 10}.", f"Half of each, then put them together: half of {it} is {fmt(D(it) / 2)}."],
    "tens_ones": lambda it, a, p: [f"{it} = {it // 10} tens + {it % 10} ones.", f"Break one ten: {it // 10 - 1} tens + {it % 10 + 10} ones."],
    "read_clock": lambda it, a, p: [f"The short hand is past {it[0]}: the hour is {it[0]}.", f"The long hand counts by 5s to {it[1]} minutes: {a[0]}."],
    "read_minute": lambda it, a, p: [f"The short hand: {it[0]}. The long hand: {it[1]} minutes (count by 5s, then 1s).", f"So {a[0]}."],
    "coins": lambda it, a, p: ["Start with the biggest coins and count on: quarters 25, dimes 10, nickels 5, pennies 1.", f"Altogether {a[0]}."],
    "read_tape": lambda it, a, p: [f"The object starts at 0. Read the number at its end.", f"It is {a[0]} {it[2]} long."],
    "tally_read": lambda it, a, p: ["Each bundle of tally marks is 5. Count by 5s, then the ones.", f"{a[0]}."],
    "times_groups": lambda it, a, p: mul_steps(it[0], it[1], 33), "times_array": lambda it, a, p: mul_steps(it[0], it[1], 33),
    "break_array": lambda it, a, p: mul_steps(it[0], it[1], 34),
    "share_div": lambda it, a, p: [f"Share {it[1]} on {it[2]} plates, one at a time.", f"Each plate gets {it[1] // it[2]}: {it[1]} {DIV} {it[2]} = {it[1] // it[2]}."],
    "think_times": lambda it, a, p: div_steps(it[0], it[1], 35),
    "round_card": lambda it, a, p: _round_card(it, a),
    "tens_groups": lambda it, a, p: mul_steps(it[0], it[1] * 10, 37),
    "area_rows": lambda it, a, p: [f"{it[0]} rows of {it[1]} squares.", f"{it[0]} {TIMES} {it[1]} = {it[0] * it[1]} squares."],
    "area_split": lambda it, a, p: [f"Split the {it[0]} by {it[1] + it[2]} rectangle into {it[0]} by {it[1]} and {it[0]} by {it[2]}.",
                                    f"{it[0]} {TIMES} {it[1]} = {it[0] * it[1]} and {it[0]} {TIMES} {it[2]} = {it[0] * it[2]}.", f"Together: {it[0] * (it[1] + it[2])}."],
    "unit_name": lambda it, a, p: [f"The whole is cut into {it[1]} equal parts.", f"One part is 1/{it[1]}."],
    "frac_name": lambda it, a, p: [f"{it[1]} equal parts make the whole; {it[2]} are shaded.", f"That's {it[2]}/{it[1]}."],
    "find_whole": lambda it, a, p: [f"1/{it} is one of {it} equal pieces.", f"So {it} pieces make the whole."],
    "wholes": lambda it, a, p: [f"Each whole has {a[-1]} pieces." if False else f"Count the pieces: {a[0]}.", f"That's {a[0]}/{a[1]}."],
    "more_whole": lambda it, a, p: [f"Count all the shaded pieces: {a[0]}.", f"Each piece is 1/{a[1]}, so {a[0]}/{a[1]}."],
    "match_frac": lambda it, a, p: [f"{it[0][0]}/{it[0][1]}: the bottom goes from {it[0][1]} to {it[1]}, times {it[1] // it[0][1]}.", f"Do the same to the top: {it[0][0]} {TIMES} {it[1] // it[0][1]} = {a[0]}."],
    "compare_frac": lambda it, a, p: [f"Look at the shaded parts of the two strips.", f"{it[0][0]}/{it[0][1]} {a[0]} {it[1][0]}/{it[1][1]}."],
    "group_frac": lambda it, a, p: [f"Make {it[1]} equal groups of {it[0]}: each has {it[0] // it[1]}.", f"{it[2]} of the groups: {it[2]} {TIMES} {it[0] // it[1]} = {it[2] * it[0] // it[1]}." if it[2] > 1 else f"One group is {it[0] // it[1]}."],
    "perim_add": lambda it, a, p: ["Add all four sides.", f"{it[0]} + {it[1]} + {it[0]} + {it[1]} = {2 * (it[0] + it[1])} {it[2]}."],
    "area_perim": lambda it, a, p: [f"Area: {it[0]} {TIMES} {it[1]} = {it[0] * it[1]} squares.", f"Perimeter: {it[0]} + {it[1]} + {it[0]} + {it[1]} = {2 * (it[0] + it[1])}."],
    "table_row": lambda it, a, p: [f"Each box is {it[0]} times the number on top.", ", ".join(f"{it[0]} {TIMES} {k} = {it[0] * k}" for k in it[1]) + "."],
    "balance": lambda it, a, p: ["The balance is level, so the object weighs the same as the weights.", " + ".join(map(str, it[1])) + f" = {a[0]} {it[2]}."],
    "beaker": lambda it, a, p: ["Read the mark at the top of the liquid.", f"{it[0]} liters."],
    "quarter": lambda it, a, p: ["Each inch has 4 quarter marks.", f"The end is at {a[0]} inches."],
    "quick_th": lambda it, a, p: _place_count(it),
    "big_stack": lambda it, a, p: column_add(it[0], it[1]) if it[2] == "+" else column_sub(it[0], it[1]),
    "area_mult": lambda it, a, p: mul_steps(it[0], it[1], 56), "partial": lambda it, a, p: mul_steps(it[0], it[1], 56),
    "groups_rem": lambda it, a, p: div_steps(it[0], it[1], 57), "rem_think": lambda it, a, p: div_steps(it[0], it[1], 57),
    "area2": lambda it, a, p: mul_steps(it[0], it[1], 58), "mrows": lambda it, a, p: mul_steps(it[0], it[1], 77),
    "div_area": lambda it, a, p: div_steps(it[0], it[1], 59), "partial_q": lambda it, a, p: div_steps(it[0], it[1], 78),
    "long_div": lambda it, a, p: div_steps(it[0], it[1], 95),
    "pairs": lambda it, a, p: ["Find every pair of numbers that multiply to make it, starting with 1.", f"{it.replace('[', '').replace(']', '')}."],
    "cut_strip": lambda it, a, p: [f"Cut each 1/{it[1]} piece into {it[2]}: {it[1]} {TIMES} {it[2]} = {it[1] * it[2]} pieces in all.", f"{it[0]}/{it[1]} = {it[0] * it[2]}/{it[1] * it[2]}."],
    "add_strip": lambda it, a, p: [f"Same bottoms: {'add' if it[3] == '+' else 'take away'} the tops.", f"{it[0]} {it[3].replace('-', MINUS)} {it[1]} = {a[0]}, so {a[0]}/{it[2]}."],
    "to_mixed": lambda it, a, p: [f"{it[1]} pieces of 1/{it[0]}: every {it[0]} pieces make a whole.", f"{it[1]} {DIV} {it[0]} = {it[1] // it[0]} R {it[1] % it[0]}: {a[-3] if len(a) >= 3 else ''}".strip()],
    "groups_frac": lambda it, a, p: [f"{it[0]} groups of {it[1]}/{it[2]}: {it[0]} {TIMES} {it[1]} = {it[0] * it[1]} pieces.", f"That's {it[0] * it[1]}/{it[2]}."],
    "read_grid": lambda it, a, p: [f"{it} of the 100 squares are shaded: {it}/100.", f"As a decimal: {fmt(D(it) / 100)}."],
    "compare_grids": lambda it, a, p: [f"Compare the shaded squares: {it[0]} and {it[1]} hundredths.", f"So {fmt(D(it[0]) / 100)} {a[0]} {fmt(D(it[1]) / 100)}."],
    "biggest_dec": lambda it, a, p: ["Line up the decimal points and compare tenths first.", f"The biggest is {W.dstr(max(it))}."],
    "biggest": lambda it, a, p: ["Same bottoms: the biggest top is the biggest fraction.", f"The biggest is {max(it, key=lambda t: F(*t))[0]}/{max(it, key=lambda t: F(*t))[1]}."],
    "conv_table": lambda it, a, p: [f"1 {it[0]} = {W.CONV[(it[0], it[1])] if hasattr(W, 'CONV') and (it[0], it[1]) in W.CONV else '…'} {it[1]}: multiply each row.", ", ".join(a) + "."],
    "rect_formula": lambda it, a, p: [f"Area = length {TIMES} width: {it[0]} {TIMES} {it[1]} = {it[0] * it[1]}.", f"Perimeter = 2 lengths + 2 widths: {2 * (it[0] + it[1])}."],
    "shift": lambda it, a, p: [f"{'Times' if it[1] == 'm' else 'Divide by'} {10 ** it[2]:,}: every digit moves {it[2]} place{'s' if it[2] > 1 else ''} to the {'left' if it[1] == 'm' else 'right'}.", f"So {a[0]}."],
    "order_dec": lambda it, a, p: ["Line up the decimal points and compare place by place from the left.", "From smallest: " + ", ".join(a) + "."],
    "round_dec": lambda it, a, p: [f"The numbers on each side: {a[0]} below and {a[1]} above.", f"Which is {it[0]} closer to? It rounds to {a[2]}."],
    "frac_grid": lambda it, a, p: frac_op_steps(f"{it[0]}/{it[1]}", TIMES, f"{it[2]}/{it[3]}"),
    "cube_count": lambda it, a, p: [f"One layer: {it[0]} {TIMES} {it[1]} = {it[0] * it[1]} cubes.", f"{it[2]} layers: {it[0] * it[1]} {TIMES} {it[2]} = {it[0] * it[1] * it[2]}."],
    "share_frac": lambda it, a, p: [f"{it[0]} wholes shared by {it[1]}: each gets one piece from each whole.", f"{it[0]} pieces of 1/{it[1]}: {it[0]}/{it[1]}."],
    "unit_cut": lambda it, a, p: [f"Share 1/{it[0]} among {it[1]}: cut each piece into {it[1]}.", f"Each share is 1/{it[0] * it[1]}."],
    "two_rules": lambda it, a, p: [f"Each step, B adds {it[1]} and A adds {it[0]}.", f"{it[1]} {DIV} {it[0]} = {it[1] // it[0]}."],
    "grid_read": lambda it, a, p: ["Over first (along the bottom), then up.", ", ".join(f"{n}: ({x}, {y})" for x, y, n in it) + "."],
    "ratio_pic": lambda it, a, p: [f"Count the circles: {it[0]}. Count the squares: {it[1]}.", f"Circles to squares = {it[0]} : {it[1]}."],
    "ratio_tab": lambda it, a, p: [f"The first column is {it[2]} {it[0]} : {it[3]} {it[1]}. Each column multiplies both by the same number."]
    + [f"{it[2] * k} is {it[2]} {TIMES} {k}, so {it[3]} {TIMES} {k} = {it[3] * k}." for k in it[4][1:]],
    "rate_tab": lambda it, a, p: [f"Find 1 first: {it[3]} {it[1]} {DIV} {it[2]} = {it[3] // it[2]} {it[1]} for 1 {_one(it[0])}."]
    + [f"{k} {it[0] if k != 1 else _one(it[0])}: {k} {TIMES} {it[3] // it[2]} = {it[3] // it[2] * k} {it[1]}." for k in it[4]],
    "grid_pct": lambda it, a, p: [f"{it} of the 100 squares are shaded.", f"Out of 100 is percent: {it}%."],
    "fit_strip": lambda it, a, p: frac_op_steps(f"{it[0]}/{it[1]}", DIV, f"{it[2]}/{it[3]}"),
    "gcf_lists": lambda it, a, p: g_misc(97, "", f"GCF of {it[0]} and {it[1]} = [{math.gcd(it[0], it[1])}]"),
    "thermo_read": lambda it, a, p: ["Read the top of the liquid. Below 0 is negative.", f"{a[0]} degrees."],
    "x_bar": lambda it, a, p: [f"The whole is {it[0] + it[1]}; one part is {it[0]}.", f"x = {it[0] + it[1]} {MINUS} {it[0]} = {it[1]}."],
    "para": lambda it, a, p: g_measure(101, "", f"parallelogram, base {it[0]} {it[2]}, height {it[1]} {it[2]}:  area = [{it[0] * it[1]}] sq {it[2]}"),
    "tri": lambda it, a, p: g_measure(101, "", f"triangle, base {it[0]} {it[3]}, height {it[1]} {it[3]}:  area = [{it[0] * it[1] // 2}] sq {it[3]}"),
    "trap": lambda it, a, p: g_measure(101, "", f"trapezoid, sides {it[0]} and {it[1]} {it[3]}, height {it[2]} {it[3]}:  area = [{(it[0] + it[1]) * it[2] // 2}] sq {it[3]}"),
    "house": lambda it, a, p: [f"Rectangle: {it[0]} {TIMES} {it[1]} = {it[0] * it[1]}.", f"Triangle: {it[0]} {TIMES} {it[2]} {DIV} 2 = {it[0] * it[2] // 2}.", f"Together: {it[0] * it[1] + it[0] * it[2] // 2}."],
    "half_cubes": lambda it, a, p: [f"Small cubes: {it[0]} {TIMES} {it[1]} {TIMES} {it[2]} = {it[0] * it[1] * it[2]}.", f"8 small cubes make 1: {it[0] * it[1] * it[2]} {DIV} 8 = {it[0] * it[1] * it[2] // 8}."],
    "cube_net": lambda it, a, p: g_measure(103, "", f"cube, edge {it[0]} {it[1]}:  surface area = [{6 * it[0] ** 2}] sq {it[1]}"),
    "net": lambda it, a, p: g_measure(103, "", f"box {it[0]} × {it[1]} × {it[2]} {it[3]}:  surface area = [{2 * (it[0] * it[1] + it[0] * it[2] + it[1] * it[2])}] sq {it[3]}"),
    "pyramid": lambda it, a, p: [f"The square: {it[0]} {TIMES} {it[0]} = {it[0] ** 2}.", f"Each triangle: {it[0]} {TIMES} {it[1]} {DIV} 2 = {it[0] * it[1] // 2}; four of them: {2 * it[0] * it[1]}.",
                                 f"Together: {it[0] ** 2 + 2 * it[0] * it[1]}."],
    "level": lambda it, a, p: [f"All the cubes: " + " + ".join(map(str, it)) + f" = {sum(it)}.", f"Share them out: {sum(it)} {DIV} {len(it)} = {sum(it) // len(it)} in each tower."],
    "median": lambda it, a, p: ["Put them in order: " + ", ".join(map(str, sorted(it))) + ".", f"The middle one is {sorted(it)[len(it) // 2]}."],
    "level_eq": None,
}
PIC = {k: v for k, v in PIC.items() if v}
def _qa(qs):
    return [f"{q} {a if isinstance(a, str) else fmt(a)}." for q, a in qs]


def _bar(it, a):
    if it[0] == "pw":
        _, x, y, unk = it
        return ([f"The two parts are {x} and {y}. Put them together: {x} + {y} = {x + y}."] if unk == "whole" else
                [f"The whole is {x + y}; one part is {x}.", f"The other part: {x + y} {MINUS} {x} = {y}."])
    if it[0] == "cmp":
        big, small, unk = it[1], it[2], it[3]
        return {"diff": [f"The difference is the dashed part: {big} {MINUS} {small} = {big - small}."],
                "big": [f"The bigger bar is the smaller one and the difference: {small} + {big - small} = {big}."],
                "small": [f"The smaller bar is the bigger one take away the difference: {big} {MINUS} {big - small} = {small}."]}[unk]
    if it[0] == "eq":
        n, each, unk = it[1], it[2], it[3]
        return ([f"{n} equal pieces of {each}: {n} {TIMES} {each} = {n * each}."] if unk == "whole" else
                [f"{n * each} shared into {n} equal pieces: {n * each} {DIV} {n} = {each}."])
    return None


PIC.update({
    "bar": lambda it, a, p: _bar(it, a),
    "two_step": lambda it, a, p: [f"Step 1: {it[1][0]}.", f"Step 2: {it[2][0]}.", f"The answer is {a[-1]}."],
    "name_share": lambda it, a, p: [f"The shape is cut into {it[1]} equal parts.", f"{it[2]} of them are shaded: {it[2]} {W.share_word(it[1], it[2]).split(' ', 1)[1] if hasattr(W, 'share_word') else ''}".strip() + "."],
    "mini_bar": lambda it, a, p: ["Read the top of the bar against the numbers on the side.", f"{a[0]}."],
    "jump_time": lambda it, a, p: [f"Jump from {it[0][0]}:{it[0][1]:02d} to the next o'clock, {it[0][0] % 12 + 1}:00: {60 - it[0][1]} minutes.",
                                   f"Then to {it[1][0]}:{it[1][1]:02d}: {it[1][1] + 60 * ((it[1][0] - it[0][0] - 1) % 12)} minutes.",
                                   f"Altogether: {(it[1][0] * 60 + it[1][1]) - (it[0][0] * 60 + it[0][1])} minutes."],
    "table_piece": lambda it, a, p: ["Each box is its row number times its column number.", "So the boxes are " + ", ".join(a) + "."],
    "sgraph": lambda it, a, p: [f"Each picture or square stands for {it[5]}."] + _qa(it[6]),
    "right_count": lambda it, a, p: ["A right angle is a square corner. Check each corner of the shape.", f"This one has {a[0]}."],
    "read_x8": lambda it, a, p: ["Each X is one thing measured."] + _qa(W.x8_questions(it[1], it[2])),
    "read_share": lambda it, a, p: ["Each X is one thing measured."] + _qa(W.share_questions(it[1], it[2])),
    "xstats": lambda it, a, p: ["List the data from the X chart in order: " + ", ".join(map(str, sorted(it[1]))) + "."] + _qa(W.stat_qs(it[1])),
    "hist": lambda it, a, p: ["Each bar shows how many numbers are in its group."] + _qa(W.hist_qs(it[1], it[2])),
    "freq": lambda it, a, p: ["Go through the list and count the numbers in each group.", ", ".join(f"{lo}–{hi}: {sum(lo <= v <= hi for v in it[0])}" for lo, hi in W._bins(it[0], it[1])) + "."],
    "make_x": lambda it, a, p: ["One X above each number for every time it appears.", f"The most X's are over {max(set(it[1]), key=it[1].count)}: that's the mode.",
                                f"Range: {max(it[1])} {MINUS} {min(it[1])} = {max(it[1]) - min(it[1])}."],
    "read_protractor": lambda it, a, p: ["Start at 0 on the side the angle opens from, and read where the other ray crosses.", f"{it} degrees."],
    # tap cards
    "buddy_yesno": lambda it, a, p: [f"Add them: {it[0].replace(' and ', ' + ')} = {sum(map(int, it[0].split(' and ')))}.", "They make 10, so yes." if it[1] else "They don't make 10, so no."],
    "eq_share": lambda it, a, p: ["Equal shares are all the same size.", "These parts are equal: yes." if it[2] else "These parts aren't the same size: no."],
    "ampm": lambda it, a, p: ["a.m. is from midnight to noon (morning); p.m. is from noon to midnight.", f"{it[0]}: {it[1]}."],
    "symbol": lambda it, a, p: ["Small amounts are cents (¢); big ones are dollars ($).", f"{it[0]}{it[1]}." if it[1] == "¢" else f"{it[0]} {it[1]}."],
    "unit_choice": lambda it, a, p: ["Picture the real thing: which unit gives a sensible number?", f"{it[0]} {it[2]}."],
    "is_quad": lambda it, a, p: ["A quadrilateral has exactly 4 straight sides.", f"A {it[0]} has {W.SHAPES[it[0]] if hasattr(W, 'SHAPES') and isinstance(W.SHAPES.get(it[0]), int) else ''}".strip() + (" so yes." if it[0] in ("square", "rectangle", "rhombus", "parallelogram", "trapezoid", "kite", "quad") else ": not 4 sides, so no.")],
    "name_quad": lambda it, a, p: ["Look at the sides and the corners: equal sides? Square corners? Parallel sides?", f"It's a {it[0]}."],
    "quad_fact": lambda it, a, p: [W.FITS and ("Yes: it is always true." if it[1] else "No: it isn't always true."), ""][0:1],
    "prime": lambda it, a, p: ([f"{it} has only two factors, 1 and {it}: prime."] if W.is_prime(it) else
                               [f"{it} has more factors: {', '.join(map(str, W.factors(it)))}. Composite."]),
    "equal_q": lambda it, a, p: [f"Make the bottoms the same: {it[0][0]}/{it[0][1]} and {it[1][0]}/{it[1][1]}.",
                                 "They are equal: yes." if F(*it[0]) == F(*it[1]) else "They are not equal: no."],
    "vs_half": lambda it, a, p: [f"Half of {it[1]} is {fmt(D(it[1]) / 2)}.",
                                 f"{it[0]} is {'less than' if 2 * it[0] < it[1] else 'equal to' if 2 * it[0] == it[1] else 'more than'} that, so {it[0]}/{it[1]} is {'less than' if 2 * it[0] < it[1] else 'equal to' if 2 * it[0] == it[1] else 'more than'} 1/2."],
    "vs_one": lambda it, a, p: [f"{it[1]}/{it[1]} is one whole.", f"{it[0]}/{it[1]} is {'less than' if it[0] < it[1] else 'equal to' if it[0] == it[1] else 'more than'} 1."],
    "same_amount": lambda it, a, p: [f"Compare {it[0]}/{it[1]} and {it[2]}/{it[3]} on the same whole.",
                                     "They cover the same amount: yes." if F(it[0], it[1]) == F(it[2], it[3]) else "They don't cover the same amount: no."],
    "bigger_unit_plain": lambda it, a, p: ["The more pieces a whole is cut into, the smaller each piece.", f"1/{min(it[0], it[1])} is bigger than 1/{max(it[0], it[1])}."],
    "bigger_unit": lambda it, a, p: ["The more pieces a whole is cut into, the smaller each piece.", f"1/{min(it[0], it[1])} is bigger than 1/{max(it[0], it[1])}."],
    "angle_kind": lambda it, a, p: ["Less than a square corner (90°) is acute; exactly 90° is right; more is obtuse.",
                                    f"{it[0]}° is {'acute' if it[0] < 90 else 'right' if it[0] == 90 else 'obtuse'}."],
    "line_name": lambda it, a, p: ["A segment has two endpoints, a ray has one, a line has arrows both ways.", f"This is a {it[0]}."],
    "two_lines": lambda it, a, p: ["Parallel lines never meet; perpendicular lines meet in a square corner.", f"These are {it[0]}."],
    "triangle_kind": lambda it, a, p: [f"The angles are {it[0]}°, {it[1]}° and {180 - it[0] - it[1]}° (they add to 180°).",
                                       f"The biggest is {max(it[0], it[1], 180 - it[0] - it[1])}°: " + ("a right triangle." if 90 in (it[0], it[1], 180 - it[0] - it[1]) else "an obtuse triangle." if max(it[0], it[1], 180 - it[0] - it[1]) > 90 else "an acute triangle.")],
    "all_names": lambda it, a, p: [f"A {it[0]} is all of these: " + ", ".join(W.FITS[it[0]]) + "."],
    "tri_sides": lambda it, a, p: [f"The angles are {it[0]}°, {it[1]}° and {180 - it[0] - it[1]}°; equal angles face equal sides.", f"So it's {W.tri_sides(it[0], it[1])}."],
    "net_ok": lambda it, a, p: ["Fold it up in your head: one square is the bottom, the others fold up around it.",
                                "Every square lands on its own face: yes, it makes a cube." if it[1] else "Two squares land on the same face (or a face is missing): no."],
    "eo_product": lambda it, a, p: [f"{it[0]} {TIMES} {it[1]} = {it[0] * it[1]}." , f"{it[0] * it[1]} is {'even' if it[0] * it[1] % 2 == 0 else 'odd'}" + (": an even number times anything is even." if it[0] % 2 == 0 or it[1] % 2 == 0 else ": odd times odd is odd.")],
    "symmetry": lambda it, a, p: ["A line of symmetry folds the shape onto itself.", f"A {it} has {W.SYM[it]}."],
})
PIC["quad_fact"] = lambda it, a, p: [it[0], "That's always true: yes." if it[1] else "That isn't always true: no."]



def _three(it):
    a, b, c = it
    pairs = [(x, y) for x, y in ((a, b), (a, c), (b, c)) if x + y == 10]
    if pairs:
        x, y = pairs[0]
        other = a + b + c - 10
        return [f"Find the Ten Buddies first: {x} and {y} make 10.", f"10 + {other} = {10 + other}."]
    return add_steps(a + b, c)


def _cmp(x, y, a):
    return ["Compare the biggest place first: hundreds, then tens, then ones.", f"{x} {a[0]} {y}."]


def _round_card(it, a):
    n, place = it[0], it[1]
    lo = n // place * place
    return [f"The {fmt(place)}s on each side: {fmt(lo)} below, {fmt(lo + place)} above.",
            f"{fmt(n)} is closer to {a[-1]}" + (" (in the middle rounds up)." if n - lo == place // 2 else ".")]


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


def skill_items(folder, skill, n):
    """The skill's problems in a fixed order (problem i here is problem i everywhere: export and card images)."""
    seen, out = set(), []
    for it in skill.make(random.Random(f"online:{folder}:{skill.id}"), n * 4):
        k = json.dumps(it, default=str, ensure_ascii=False)
        if k not in seen:
            seen.add(k)
            out.append(it)
        if len(out) == n:
            break
    return out


def is_picture(kind):
    return kind not in TEXT_KINDS and kind not in NO_SCREEN


def pool_size(kind):
    return POOL if kind in TEXT_KINDS else PICTURE_POOL


def skill_problems(folder, skill):
    packet = S.number(folder)
    out = []
    for i, it in enumerate(skill_items(folder, skill, pool_size(skill.kind))):
        if is_picture(skill.kind):
            p = picture_problem(packet, skill, it)
            if p is None:
                continue
            p["i"] = i
        else:
            p = problem(packet, skill, it)
        p["size"] = float(sum(abs(n) for n in [num(n) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", json.dumps([it], default=str))][:6]))
        out.append(p)
    order = sorted(range(len(out)), key=lambda i: out[i]["size"])
    for rank, i in enumerate(order):
        out[i]["d"] = 1 + rank * 3 // max(1, len(out))
        del out[i]["size"]
    return out


def card_for(folder, skill_id, i):
    """The PNG of problem i of a picture skill (the student's version: empty boxes, nothing circled)."""
    skill = next(t for t in S.TYPES[folder] if t.id == skill_id)
    it = skill_items(folder, skill, pool_size(skill.kind))[int(i)]
    return card_png(skill.kind, it)


GRADE_OF = {}


def grade(packet):
    for name, lo, hi in (("K", 0, 2), ("1", 3, 9), ("2", 10, 32), ("3", 33, 52), ("4", 53, 72), ("5", 73, 90), ("6", 91, 999)):
        if lo <= packet <= hi:
            return name


def instruction(skill, probs):
    """One line for the top of a picture problem."""
    sub = next((sec[1] for sec in _subs(skill)), None)
    if sub:
        keep = [t for t in re.split(r"(?<=[.?!])\s+", sub) if not re.match(r"(Every|All|The rest|More|Some)\b", t)]
        if keep:
            return " ".join(keep)
    p = probs[0]
    if p.get("n") and not p.get("a"):
        return "Tap every right answer." if p["n"] > 1 else "Tap the right answer."
    return "Fill in the boxes." if p.get("img") else ""


def _subs(skill):
    """(name, subtitle) of the packet sections this skill came from."""
    for f, ts in S.TYPES.items():
        if skill in ts:
            for sec in W.CHECKINS.get(f, []):
                if sec.kind == skill.kind and sec.sub:
                    yield sec.name, sec.sub
            ex = W.EXTRA.get(f)
            for block in ([ex] if isinstance(ex, tuple) else ex or []):
                for sec in block[1]:
                    if sec[2] == skill.kind and sec[1]:
                        yield sec[0], sec[1]
            return


def export(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    order = [p[0] for p in W.PACKETS]
    teach = {n: i for i, n in enumerate(W.TEACHING_ORDER)}
    order.sort(key=lambda f: teach.get(S.number(f), 999))
    units = []
    for folder in order:
        skills = [t for t in S.TYPES.get(folder, []) if t.kind in TEXT_KINDS or is_picture(t.kind)]
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
                         "picture": is_picture(t.kind), "inst": instruction(t, probs),
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
    if cmd == "card":
        sys.stdout.buffer.write(card_for(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == "export":
        units = export(sys.argv[2])
        print(f"{len(units)} units, {sum(len(u['skills']) for u in units)} skills")
    else:
        report()
