# WeMath worksheets

Six packets, in teaching order. Each starts with a picture-first learning page, followed by practice.

| Folder | Topic | Pages |
|---|---|---|
| `0-adding-and-taking-away/` | Before everything: add and take away within 9 with pictures of real things (gummy bears, apples, ducks…); cross out what goes away | 15 |
| `1-ten-buddies/` | Pairs that make 10 | 3 |
| `2-ten-and-some-more/` | 10 + a number (teen numbers) | 4 |
| `3-up-to-and-over-ten/` | Crossing 10 with buddies (break-apart) | 6 + blank template |
| `4-over-the-next-ten/` | Crossing 20, 30, 40… with buddies, then without hints | 5 + blank template |
| `5-back-through-ten/` | Subtracting across ten with the jump diagram (15 − 8: jump 5, jump 2) | 7 |
| `6-doubles-and-near-doubles/` | Doubles to 10 + 10, then near doubles (6 + 7 = double 6 + 1) | 6 |
| `7-tens-and-ones/` | Two-digit numbers as tens and ones: ten-sticks, quick tens, 40 + 6, which is more | 6 |
| `8-ten-more-ten-less/` | 34 + 10 and 34 − 10: add an orange ten or cross one out; only the tens digit changes | 6 |
| `9-adding-two-digit-numbers/` | 34 + 25 by place value: add the tens, add the ones, put them together; making a new ten (38 + 25) | 6 |
| `10-subtracting-two-digit-numbers/` | 58 − 23 by place value: take away the tens, take away the ones, put them together. Only problems with enough ones; borrowing comes later | 6 |
| `11-missing-numbers/` | Missing addends by jumping up: 8 + ☐ = 13 (8 → 10 → 13), 42 + ☐ = 75 (42 → 50 → 70 → 75). Addition only | 6 |
| `12-subtracting-with-borrowing/` | 52 − 27: not enough ones, so break a ten (52 = 40 + 12), then tens, ones, total | 6 |
| `13-adding-in-columns/` | Two-digit addition stacked in columns; carry the new ten as a small 1 | 6 |
| `14-subtracting-in-columns/` | Two-digit subtraction stacked; cross out the tens digit and write 10 more ones | 6 |
| `15-hundreds-tens-and-ones/` | Three-digit place value: flats, sticks and dots; quick drawings; 300 + 40 + 5 | 6 |
| `16-skip-counting/` | Count by 5s, 10s and 100s from any number | 6 |
| `17-comparing-numbers/` | <, > and = with two- and three-digit numbers; biggest place first | 6 |
| `18-10-and-100-more-or-less/` | 10 or 100 more or less; the number cross | 6 |
| `19-adding-three-digit-numbers/` | Hundreds, tens and ones rows, then stacked columns | 7 |
| `20-subtracting-three-digit-numbers/` | Break a ten or a hundred (one break per problem), rows then columns | 7 |
| `21-equal-groups-and-arrays/` | Equal groups, arrays up to 5 × 5, repeated addition (no × sign) | 7 |
| `22-even-and-odd/` | Pairs, doubles, double + 1, count by 2s, the ones digit | 5 |
| `23-hundred-buddies/` | Pairs that make 100 (64 + 36): fill the hundred grid, jump up to the next ten then 100, tens make 9 and ones make 10; buddies of 50 and 1000 | 6 |
| `24-counting-forward-and-backward/` | Count by 2s, 3s, 4s, 5s, 10s and 25s from any number, forward and backward, across 100 | 7 |
| `25-halves/` | Half means 2 parts the same: share fairly, half undoes double, half the tens and ones, odd numbers (half of 7 = 3½), half of what? | 7 |

Each folder has `color/` and `black-and-white/` (printer friendly: no fills, hollow dots) versions of:

- `<topic>-packet.pdf`: the student packet
- `<topic>-answer-key.pdf`: the same pages filled in, with a short teacher note on the learning page

## Rebuilding

## Check-Ins and assessments

**Check-Ins.** Every packet folder also has a one-page `<slug>-check-in.pdf` (and `-check-in-key.pdf`) in both inks. It has one or two problems of each kind from that packet, with no help. The key shows the mastery line: 80% of the problems correct.

**Grade-level assessments** are in `assessments/`, in color and black-and-white:

| Grade | Packets | Pre | Post |
|---|---|---|---|
| Kindergarten | 0–2: adding and taking away within 9, ten buddies, teen numbers | 44 problems | 46 problems |
| Grade 1 | 3–9: over ten, back through ten, doubles, tens and ones, ten more/less, two-digit adding | 60 problems | 60 problems |
| Grade 2 | 10–25: two-digit subtracting, borrowing, columns, three-digit numbers, skip counting, comparing, arrays, even/odd | 68 problems | 68 problems |

Each answer key ends with a **scoring sheet**: every part, the packet it checks, and a score line. Use the **pre-assessment** for placement: start a student at the first packet where they miss more than 1 problem in its parts. Use the **post-assessment** to see growth: a part with more than 1 miss means that packet needs review.

Check-in and assessment problems are chosen automatically. Problems that no practice packet used come first, and none is repeated across all the check-ins and assessments. The only exception is the ten buddies, where there are only 11 facts.

## Rebuilding

```bash
python build_worksheets.py
```

Needs the packages in `requirements.txt` (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`) and the macOS system fonts (Avenir Next, Arial Rounded). The fonts can't be committed, so the PDFs are built on a Mac; elsewhere you can edit the generator but not rebuild. The build stops with an error if any question appears twice across all the packets.
