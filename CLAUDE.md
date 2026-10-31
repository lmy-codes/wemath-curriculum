# WeMath worksheet playbook

How to build WeMath math packets fast and the way the founder (the person who runs WeMath) wants them. Read this before touching `build_worksheets.py`.

WeMath is a math tutoring program in a community center, with Mathnasium-style teaching. The audience is **young kids (K–3)**. These packets are the start of a home-grown curriculum.

---

## 1. What exists

| Folder | Topic | Key visual |
|---|---|---|
| `0-adding-and-taking-away/` | Add and take away within 9 with objects (comes before packet 1) | `icon(bk, kind, cx, cy, s)` (17 drawn objects, colour and B/W outline), `objects` (rows of 5, last ones crossed), `together` (two groups with +, `outline=True` rings each group), `circles` (a child's drawn circles for keys), `STORY_BANK` + `story_text`, `flow()` (a part that runs onto new pages by itself) |
| `1-ten-buddies/` | Pairs that make 10 | ten-frames, blue + orange dots |
| `2-ten-and-some-more/` | 10 + n, teen numbers | full ten-frame + extra dots, "1**4**" with the ones digit in orange |
| `3-up-to-and-over-ten/` | Crossing 10 (8 + 5) | **break-apart diagram** (make-ten box with the ten in a band, leftover circle) |
| `4-over-the-next-ten/` | Crossing 20, 30… (28 + 5) | break-apart with band 30/40…, dot "ladder" 8+2, 18+2, 28+2 |
| `5-back-through-ten/` | Subtracting across ten (15 − 8) | **jump diagram**: 15 → 10 → 8, jumps 5 + 2 = 7 |
| `6-doubles-and-near-doubles/` | Doubles to 10 + 10, near doubles (6 + 7) | `dot_pair` rows like a domino, extra dot orange |
| `7-tens-and-ones/` | Two-digit numbers as tens and ones | `ten_stick` (bar of 10 blue dots), loose orange ones, `quick_tens` (line per ten, dot per one), `pv_chart` (tens \| ones) |
| `8-ten-more-ten-less/` | 10 more / 10 less than a two-digit number | `more_less_picture`: an added ten-stick with orange dots, or the last stick crossed out (`cross_out`); 10 less ← n → 10 more strips; +10 chains |
| `9-adding-two-digit-numbers/` | Two-digit + two-digit within 100 | `add_picture` (first number blue sticks + ones, second orange), `split_rows` (tens / ones / total scaffold; `helped=True` prints the parts) |
| `10-subtracting-two-digit-numbers/` | Two-digit − two-digit, no borrowing | `take_away_picture` (blue sticks + ones, the taken tens crossed with an orange X, taken ones slashed), `split_rows(..., op="−")` (total row still adds tens + ones) |
| `11-missing-numbers/` | Missing addends (8 + ☐ = 13, 42 + ☐ = 75) | `jump_stops(start, total)` (start → next ten → last ten → total), `jump_up` (stops in a row, a curved arrow per jump with the jump size in a bubble on the curve; `given=False` makes the tens stops boxes), `jumps_sum` |
| `12-subtracting-with-borrowing/` | Two-digit subtraction that needs a ten broken | `broken_picture` (tens − 1 sticks, the opened ten as an orange ten-frame, then the loose ones; taken parts crossed), `borrow_rows` (break / tens / ones / total). `column_sub` (stacked, crossed digits) is kept for a later column packet |
| `13-adding-in-columns/` | Stacked two-digit addition | `stacked(op="+")` (columns, carry boxes, `room=False` for no carry row), `stack_grid` (empty columns to copy into), `add_mat` (tens/ones mat; the new ten is an orange-outlined stick) |
| `14-subtracting-in-columns/` | Stacked two-digit subtraction | `stacked(op="−")` (crossed digits, new digits above), `sub_mat` (row 1 the number, row 2 a ten opened into 10 orange ones; taken parts crossed) |
| `15-hundreds-tens-and-ones/` | Three-digit place value | `hundred_flat` (10 × 10 grid; orange for an added hundred), `hto_picture`, `quick_hto` (square, line, dot), `hto_chart`, `hto_boxes` |
| `16-skip-counting/` | By 5s, 10s and 100s | `five_bar`, `count_chain` (arcs with a +5 bubble, or commas when `arcs=False`), `step_bubble` |
| `17-comparing-numbers/` | <, >, = | `compare_card` (each picture centred over its number, sign box between), `mini_tens`, `sign_of` |
| `18-10-and-100-more-or-less/` | ±10, ±100 | `number_cross` (100 more up, 100 less down, 10 less left, 10 more right) |
| `19-adding-three-digit-numbers/` | Three-digit addition | `two_drawings` (blue + orange quick drawings), `hto_add_rows` (hundreds/tens/ones/total; total adds three parts so no carrying is needed), `stacked` with 3 places |
| `20-subtracting-three-digit-numbers/` | Three-digit subtraction, one break | `quick_take` (quick drawing with taken parts crossed), `hto_sub_rows` (break row only when needed) |
| `21-equal-groups-and-arrays/` | Repeated addition | `group_ring` (dice pattern), `groups_picture`, `array_picture` (rows or columns alternate blue/orange) |
| `22-even-and-odd/` | Even and odd | `pairs_picture` (pairs in rings; the leftover dot is orange only on the key, so it doesn't give the answer away), `even_odd_choice` |
| `23-hundred-buddies/` | Complements to 100, 50, 1000 (Mathnasium wholes and parts) | `hundred_grid` (10 × 10 dots filled row by row; buddy orange), `c_hgrid`, `c_nines` (tens make 9, ones make 10), reuses `c_jump_up` |
| `24-counting-forward-and-backward/` | Count by any number, either way (Mathnasium counting) | `count_chain` with "−2" bubbles, `c_chain` (sign-aware), `c_seq`, `c_direction` (Count [forward/back] by [n]), `countby_key` |
| `25-halves/` | Half of, both directions (Mathnasium: half first, before other fractions) | `c_share` (objects over two plates; key fills the plates), `c_half_double` (dot pairs), `c_half_tens` (sticks cut by a dashed line), `c_half_split`, `c_half_odd` (last object cut), `half_str` (3½, ½) |
| `26-halves-thirds-and-fourths/` | Equal shares of shapes (2.G.3) and rows and columns of squares (2.G.2) | `share_shape(kind, n, shaded, equal, answer, lines)` with kinds circle / rect / tall / square / hsquare / grid / diag and `equal=False` cuts that look almost fair; `shade` (light fill, or diagonal hatching in black-and-white), `share_word(3, 2)` = "2 thirds", `circle_choice` (key rings a word), `yes_no_choice`, `square_grid` |
| `27-telling-time/` | Clocks to 5 minutes, a.m./p.m. (2.MD.7) | `clock(cx, cy, R, (h, m), ring, shaded, answer)`: short thick blue hour hand, long thin orange minute hand; `ring` = "full" (5…55 outside), "quarters" (15, 30, 45) or None, so help fades; `shaded` = half / quarter / three (links to packet 26); `answer=True` draws the hands only on the key. `time_words`, `sun_icon`, `moon_icon` |
| `28-money/` | Coins and bills (2.MD.8): cents or whole dollars, no decimals | `coin(kind, k)` at real relative size (a dime is smaller than a penny), `coin_row(coins, totals="boxes"/"given")` (running totals under each coin), `bill`, `greedy` (fewest coins). Coins are letters: Q, D, N, P |
| `29-subtracting-across-zeros/` | 403 − 157 (finishes 2.NBT.7) | `tens_break` and `zero_rows`: 403 = 40 tens + 3 ones = 39 tens + 13 ones, then tens / ones / total rows; reuses `stacked` for columns (it already breaks twice) and `quick_hto` |
| `30-two-step-word-problems/` | Bar models (2.OA.1) | `bar_model(parts, whole)` (blue and orange pieces, bracket above), `compare_bars(big, small, unknown, names)` (difference dashed), `draw_model(("pw", a, b, "whole"/"part"))` / `("cmp", big, small, "diff"/"big"/"small", names)`, `c_story_bar`, `c_two_step` (step 1 and step 2 bars or a space to draw them) |
| `31-measuring-length/` | Length with rulers and tape measures (2.MD.1–5) | `tape_measure(n, unit)` (0 at the left, half ticks), `length_object(kind, length)` (pencil / crayon / ribbon / straw), `clip` (paper clips), `INCH = 72` and `CM`: true size when printed at 100%, so kids can measure with a real ruler. **Answer boxes with units: write `[21] cm`, never `[21 cm]`** (a space inside brackets breaks the box) |
| `32-graphs/` | Data (2.MD.9–10) | `tally`, `picture_graph` (one symbol for every row, "Each ★ = 1"), `bar_graph` (square grid, 0–10 scale; `show=False` for "make it", the key fills it), `x_chart` (line plot without a line), `graph_qs` (how many, how many more, together, in all), `c_graph` (one card numbered "15–18)" for 4 questions) |
| `33-multiplication/` | Grade 3 starts: × as equal groups (3.OA.1, 3.OA.5) | `TIMES`, `X(a, b)`, `c_times_groups`, `c_times_array`, `c_times_turn`, `c_times_count`. Owns the ×2, ×5, ×10 facts as plain problems. `×` and `÷` are in `OPS` (drawn in Avenir) |
| `34-multiplication-strategies/` | The other facts by breaking arrays (3.OA.5, 3.OA.7) | `split_array` (blue rows, dashed line, orange rows; `cross_from` crosses the extra row for ×9 = ×10 − one group), `STRATEGY`, `break_lines`. Owns all 36 facts of 3, 4, 6, 7, 8, 9 |
| `35-division/` | Sharing and grouping (3.OA.2, 3.OA.6) | `DIV`, `D(p, d)`, `plate_row` (key fills the plates), `c_share_div`, `c_make_groups` (key rings the groups), `c_think_times` (missing factor is this packet's core skill), `c_fact_family` |
| `36-fractions/` | Fractions as numbers (3.NF.1–3), denominators 2, 3, 4, 6, 8 | `frac_expr(text)` draws stacked fractions: "3/4 [<] 7/8", "1/2 = [2]/4" (either part can be a box); `strip` (fraction strip), the fraction wall on the learning page. No number lines |
| `37-rounding/` | Round to 10 and 100 (3.NBT.1), **the founder's method**: find the ten (or hundred) below and above, ask which one the number is closest to | `between(n, place)`: [ten below] ← n → [ten above], the key rings the closer one. **No distance bubbles and no ten-frame** (founder: kids only need the ten below and above, and can usually see which is closer; the bubbles were confusing). `round_to`, `c_between` (levels: closer = tens given, boxes = all blank). Exactly in the middle rounds up |
| `38-multiplying-by-tens/` | One digit × a multiple of 10 (3.NBT.3): 4 × 30 = 12 tens = 120, never "add a zero" | `tens_groups(g, t)` (rings of ten-sticks, alternating blue/orange), `tens_fact` ("6 × 4 = ☐ so 6 × 40 = ☐"), `TENS_FACTS` |
| `39-area/` | Area (3.MD.5–7) | `area_rect(rows, cols, cell, grid, unit, split, numbers, fill)` (unit squares; `split` = dashed line with blue and orange parts), `area_L` (two rectangles), `area_eq` / `square_area_eq` / `missing_side_eq` ("4 cm × ☐ cm = 24 sq cm"; the missing side is this packet's skill) |
| `40-perimeter/` | Perimeter (3.MD.8) | `edge_numbers` (numbers each unit edge around the outside), `rect_sides` (a label on every side), `polygon_sides` (any number of sides, labels pushed out), `c_perim_missing` (P − both long sides, then half), `c_area_perim` |
| `41-elapsed-time/` | Time to the minute and intervals (3.MD.1) | `jump_times` (packet 11's jump picture with times: start → next o'clock → end, minutes in the bubbles; **not a number line**), `time_stops`, `tadd`, `tdiff`, `c_read_minute` (big clock), `c_how_long` (two clocks), `c_jump_time` (modes given / find / end) |
| `42-four-operations/` | Two-step problems with all four operations (3.OA.8) | `equal_bar(n, each, unknown)` (bar of equal pieces; also `("eq", n, each, "whole"/"each")` in `draw_model`, so `c_story_bar`, `c_two_step` and the "bar" check-in kind take it), `about_eq` (round to check), `two_step_x`, `stories_two` |
| `43-patterns-in-the-times-table/` | Times-table patterns (3.OA.9) | `times_table(n, cell, hl_rows, hl_cols, hl_cells, blanks)`, `c_table_row`, `c_table_piece`, `c_eo_product` (even/odd of a product; `EO_POOL` leaves out the practice ones so the check-in alternates), `double_fact` |
| `44-mass-and-liquid-volume/` | Grams, kilograms, liters (3.MD.2) | `balance(cx, by, obj, weights, unit, obj_label)` (level pan balance, weights stacked on the right pan), `beaker(x, y, h, maxv, level)` (a marked measuring beaker: a measuring tool, not a number line), `MASS_UNITS` for the shared "unit_choice" card |
| `45-scaled-graphs/` | Scaled graphs (3.MD.3) | `scaled_picture_graph(..., per)` ("Each ★ = 5"), `scaled_bar_graph(..., step)`, `c_sgraph`, `c_make_sgraph`, `pictures_eq` |
| `46-measuring-to-the-quarter-inch/` | Quarter inches and X charts (3.MD.4) | `ruler_q(x, y, n)` (true size, half and quarter marks), `qstr(quarters)` ("2¾"), `c_quarter`, `c_measure_q`, `c_make_xchart`, `c_read_xchart` |
| `47-shapes-and-quadrilaterals/` | Quadrilaterals (3.G.1) | `SHAPES`, `draw_shape(kind, cx, cy, s, rot)` (right-angle squares and equal-side ticks are worked out from the corners), `right_angles`, `quad_name`, `c_is_quad`, `c_name_quad`, `c_quad_fact`, `c_draw_quad` (dot grid) |
| `48-thousands/` | Grade 4 starts: place value to 9,999 (4.NBT.1–2) | `nf(n)` (commas for 1,000 and up; use it for every big number, also in boxes), `thousand_cube`, `mini_cube`, `quick_th`, `expanded_eq` / `expand_eq` (blanks on the left, still a + b = c), `worth_eq`, `compare_big` |
| `49-rounding-big-numbers/` | Rounding to 1,000 (4.NBT.3), the founder's method | reuses `between` / `c_between` (with `nf`); `round_eq(n, p)` names the place ("to the nearest thousand") so 1,000 and 100 questions don't collide; `about_k` |
| `50-adding-and-subtracting-big-numbers/` | Four-digit columns (4.NBT.4) | reuses `stacked` (any number of places), `c_big_stack`, `big_eq` |
| `51-multiplying-by-one-digit/` | Two- and three-digit × one digit (4.NBT.5) | `area_model(x, y, w, h, n, f, labels, products)` (pieces sized by place value), `place_parts`, `partial_lines`, `c_area_mult` (modes given / split), `c_partial` |
| `52-division-with-remainders/` | Remainders (4.OA.3) | `rem_eq` ("17 ÷ 5 = [3] R [2]"; curriculum.json writes "3 R 2"), `c_share_rem` (plates and a left-over box), `c_groups_rem`, `c_rem_think`, `stories_rem` |

Each folder has `color/` and `black-and-white/` subfolders, each holding `<slug>-packet.pdf` and `<slug>-answer-key.pdf`. **The Check-In is the last page of both** (founder's request): `build_check_in(..., into=bk)` draws it into the still-open packet Book, so the main loop builds every packet with `save=False`, runs the `Picker`, then adds each Check-In and saves. The standalone `-check-in.pdf` files are the same pages. Packets 3 and 4 also include `break-apart-template.pdf`.

**Rebuild everything:** `python build_worksheets.py`, run from this folder.
- Needs `reportlab` (plus `pypdfium2` and `pypdf` for checking). If they're missing, create a venv outside the PDF folders: `python3 -m venv .venv && .venv/bin/pip install reportlab pypdfium2 pypdf`.
- Uses the macOS fonts Avenir Next (`.ttc` subfont indices 7, 5, 2, 0) and Arial Rounded Bold.
- **Off a Mac (cloud sessions):** set `WEMATH_PREVIEW_FONTS` to a folder with `Inter-Regular/Medium/SemiBold/Bold.ttf` and `LiberationSans-Bold.ttf` (Inter's `.otf` converted with fontTools), and `WEMATH_OUT` to a scratch folder. The stand-ins match Avenir's widths closely enough to check layouts. **Never commit PDFs built this way**; the founder rebuilds on the Mac.
- The folder moved once (from `Website/curriculum` to `WeMath/curriculum`). Always `ls` before assuming paths.

---

## 2. Founder's preferences (non-negotiable)

### Packet structure
- **One subject per packet, one folder per packet.** Number the folders in teaching order: `N-slug/`.
- **Page 1 is a learning page:** very visual, few words, for young kids. Big title (AvB 30), short tagline (Rnd 15), big dots and big colored numbers. Usually 3 numbered step panels, then "Write it like this" with the diagram filled in, then a "Your turn!" panel.
- **Practice pages remove help gradually ("training wheels").** The pattern: full diagram + dots → diagram with labels → less help (only blanks for the parts) → **"On your own"** plain problems → word problems. The founder asks for more help at the start and an unstructured, no-help section near the end.
- **Always write problems as a + b = c** (blank in any of the three spots), never "c = a + b" or "☐ = 6 + 7". The founder says it's too early to switch the order. This applies to every packet so far. To ask for a fact already used plainly in an earlier packet, use two blanks instead (☐ + ☐ = 13, "two numbers 1 apart") or a different wording ("double ☐ = 10").
- **No-help practice is organized by kind of question**, not one mixed pile. Example from packet 6: *Find the missing double* → *Find the near double* (total unknown) → *Find the missing near double* → *Big numbers*. Put the blank in the answer spot (6 + 8 = ☐). A blank in the first two spots (☐ + 7 = 14) is a missing addend, which belongs to the planned Missing Numbers packet; only use it when it *is* the packet's core skill (buddies, doubles, 10 + ☐ = 16 place value). The founder wants plenty of it: about 40–50 no-help problems per packet.
- **Word problems scattered in**, with different stories (take-away, "how many more", missing part). The challenge problem goes last.
- **Respect dependencies.** Never use a skill before the packet that teaches it. Number lines were removed for this reason; don't use them. "Find the buddies, then add" moved to packet 2 because it needs 10 + n.
- **Answer keys:** the same pages with answers in red (color) or black (black-and-white). Add a short "For teachers" note at the bottom of the learning page: the goal and the exact words to say.

### Problems
- **No question twice, ever, across all packets.** `Book.ask()` enforces this, so register every question (see §4). Commutative pairs (2 + 9 vs 9 + 2) were allowed; the founder said leave that.
- **Mix the order.** Don't drill 9s, then 8s, then 7s, and don't always put the buddies in the same positions in 6 + 4 + 3 problems. Shuffle so no two problems in a row start with the same number.
- **Avoid boring answer runs** (five answers of 13 in a row looked bad).
- **No "turnarounds" in diagrams** (smaller number first, so the arrows cross). Always write bigger + smaller in break-apart diagrams. Commutative versions are fine in plain compact problems.
- **Wanted:** plenty of bigger-number problems (two-digit across tens) and plenty of practice overall.
- **Worked examples must differ from practice problems.** Example: 28 + 5 is the example in packet 4, so practice uses 28 + 6.

### Visual style
- **Simple, not "AI-looking":** no heavy header bands, no pill or bubble badges for "SET B" or "PART 2", no gradients or shadows.
  - Header: a thin top line with the WeMath "buddies" logo (`draw_logo`, from `assets/wemath-logo.svg`: blue and orange pieces that fit together; black and grey in black-and-white), "WeMath", the subject in gray, and Name/Date on the right ("Answer Key" in red on keys).
  - Sections are plain text: **Part 2** Fill in the buddy. *gray subtitle*.
- **Problem numbers are a gray "12)"**: in the top-left corner on tall cards, vertically centered on short cards. Content starts at `x + GUT` (46pt), well clear of the number.
  - Tried and rejected: blue number bubbles (too AI-looking), and a left "number column" with a divider line (looked weird on tall cards).
- **Cards:** light outlined rounded boxes, no fill.
- **Two inks for every PDF:**
  - Color: blue = the starting number, orange = the buddy, leftover or jump, red = answers.
  - Black-and-white: no fills, black dots for the start, hollow dots for the buddy.
- **Break-apart diagram** (`Book.break_apart`): problem on top with the split number in the accent color, two arrows down, make-ten box (band = the next ten, dashed split, buddy box), + circle (leftover) = answer box, with captions *start / buddy / left over / answer*.
- **Jump diagram** (`jump_diagram`, packet 5): based on the founder's own sketch.
  - **Chosen style: `JUMP_STYLE = "inline"`** ("bubble on the curve"). One smooth curve runs from the first number down to the 10 and back up to the second, with each jump bubble sitting on the curve and the line hidden behind the bubble's white fill. It was compressed vertically twice ("too tall"), so keep it flat.
  - Vertical version (`jump_column_inline`): plain column subtraction, with the curve going **out to the right** to a 10 beside the column and back in to the bottom number. Keep it horizontally compact.
  - The older `"below"` style (circles under the arrow bends) is still in the code but not used.
- **Dot pairs** (`dot_pair`, packet 6): two rows of dots lined up like a domino, with a small gap after every 5. The extra "one more" dot is orange (hollow in black-and-white).

---

## 3. Fast process for a new packet

1. **Research the next topic briefly** (Common Core progressions, Mathnasium method page). Propose a short sequence and get a yes before building. Already researched next steps: doubles/near doubles → tens and ones (sticks + dots "quick tens") → 10 more/10 less → 2-digit + 2-digit. Use part-whole bar models in word problems.
2. **Write a problem plan before coding:**
   - Enumerate the full fact pool (e.g., all 35 single-digit subtractions that cross ten).
   - Allocate each fact once across learn page, parts and word problems.
   - Check that the order is shuffled and the answers vary.
   - Confirm the example is not used in practice.
3. **Write `learn_<topic>(bk)` and `practice_<topic>(bk)`.** Reuse the components in §4, then add the packet to `PACKETS`.
4. **Plan page heights first.**
   - First practice page content starts at y ≈ H − 130 (with a goal line); continuation pages start at H − 104.
   - Part header ≈ 14pt; gap after a grid ≈ 30pt.
   - The footer guard warns if a card goes below y = 44.
   - Typical heights: compact rows 42, word cards 110 + 8 gap, break-apart cards 130.
5. **Build, then render every new page to PNG and look at it** (pypdfium2, scale 1.4) in both inks. Check the answer key too.
6. **Fix, rebuild, re-check.** Update `README.md` (packet table and page counts).
7. **Send** the color packet and key with `SendUserFile`, and say the black-and-white versions are in the folder.

---

## 4. Components (in `build_worksheets.py`)

- **Page:**
  - `bk.new_page(heading, goal, first=, name_line=, footer=, big=)`. `big=True` is the learning-page title. Pass `footer=` on the first page of a packet only.
  - `bk.part(y, n, text, sub)`, `bk.note(y, text)`.
- **Layout:**
  - `practice_cards(bk, y, items, first_num, cols, rows, h, gap, draw)`: generic grid. `draw(x, cy, w, item)` must call `bk.ask(...)`.
  - `compact(bk, y, ["a + b = [ans]", ...], first_num, cols=3)`: one-line problems; it registers questions itself.
  - `words(bk, y, [(story, sentence, answer, unit)], first_num)` → `word_card`: registers `story: …`.
  - `ba_grid(bk, y, [(bigger, smaller)], first_num)`: break-apart cards. `(None, None)` gives a blank card.
- **Equations:**
  - `bk.eq(x, y, "8 + [2] = 10", size)`: `[n]` is an answer box, revealed only on the key; `{n}` is a number in the accent color.
  - `bk.fit_eq(x, y, max_w, text, size)` shrinks the equation to fit. **Use it anywhere width is tight.**
- **Visuals:**
  - `bk.ten_frame(x, y, cell, fills)` and `bk.frames(...)` for two frames. fills are `'a'`, `'b'` or `None`; `dots(n, kind)`.
  - `bk.break_apart`, `bk.buddies_first`, `jump_diagram` / `jump_inline` / `jump_column_inline` / `jump_vertical`, `buddy_strip`, `step_panel`.
  - `curve_arrow(bk, p0, p1, p2, p3)` (Bézier with head), `bk.arrow`, `jump_circle`, `bezier_point`.
- **Learning page:** `color_eq(bk, x, y, [(text, kind[, "tight"])], size, anchor)` with kind `'a'`, `'b'`, `'op'` or `None`. Also `panel`, `your_turn(bk, y, h)`, `label`, `teacher_note(bk, text)` (key only).
- **Answers:** `bk.box(x, y, w, h, value, size, reveal=)` and `bk.value(...)` show on the key, or always when `reveal` is a color (worked examples).
- **Themes:** `theme(color)` sets the global `T`. Never hardcode colors; use `T.ink`, `T.text2`, `T.muted`, `T.line`, `T.box`, `T.dot_a`, `T.dot_b` (None means hollow), `T.accent`, `T.answer`, `T.band`, `T.panel`, `T.strip`.

---

## 5. Mistakes made before (check these every time)

| Mistake | Fix |
|---|---|
| **Arial Rounded (`Rnd`) has no minus "−" or "·"**, so it rendered as a blank box | Draw signs with Avenir (`AvD`). Use `bk.eq` / `color_eq` (ops already use AvD); never `drawString("15 − 8", font="Rnd")`. |
| Avenir has no "☐" | Use "?" or a drawn box. |
| **Fill color bleeds**: after drawing hollow dots the fill is white, so the next "=" vanished in B/W and turned orange in color | Always `setFillColor` right before drawing text. |
| Footer set before `new_page` closed the previous page, so the wrong set name showed in the footer | Pass `footer=` into `new_page`. |
| Cards running into the footer | Plan heights; watch for the `WARNING ... overlaps the footer` output. |
| Answer boxes poking out of cards or panels (Set C Part 5, packet 2 "Your turn") | Use `fit_eq` and keep everything inside the card width. |
| Problem numbers touching the math ("10) 10 + …") | Content starts at `x + GUT`. |
| Captions sitting on card borders | Add card height. |
| Circles in the answer key overlapping "+" signs | Widen the gaps. |
| Story text running into the work box | Cap the paragraph width. |
| Duplicate questions slipped in (9 + 3 twice, 7 + 6 twice) | Register everything with `bk.ask`; run one registry across all packets (it's shared in `__main__`). |
| `rep()` patch scripts failing on escaped "−" vs a literal "−" in the source | `grep \| cat -v` first and match exactly. |
| Problem numbers skipping after a "(continued)" part (12 → 15) | When a part is split across pages, recount `first_num` for every later part. |
| Rows of answer boxes touching (tens / ones / total scaffold) | A box is 1.6 × the type size tall; space rows at least 2 × size apart. |
| Wording that names a color ("the orange tens") | The black-and-white version has no orange. Describe the thing instead ("the second number's tens"). |
| Yes/no cards with the answers in a pattern (yes, no, yes, no, so in 2 columns every "yes" was on the left) | **Shuffle the order of the questions** so the right answers don't follow the grid; check where the key's circles land. **Keep "yes" first and "no" second on every card**: swapping the labels was tried and the founder said it looked weird. Fixed in packet 1 (Are they Ten Buddies?) and packet 10 (Enough ones?). |
| Stacked layers inside a structured card (problem, then jump bubbles, then the sum row) crammed together: the bubbles were ~3pt under the problem's answer box | **Leave about 15pt of clear space between each layer** of a structured card, and grow the card (packet 11 jump cards went from 130 to 152pt tall) instead of squeezing. Look at the gap between the top of the diagram and the bottom of the problem's answer box. |
| A picture that gives the answer away (the leftover dot in orange on an even/odd question; answer boxes sized to fit "even" or "odd") | Highlight only on the key, and keep choice boxes one size. |
| `bk.ask()` keys treat anything in `[ ]` as a blank, so a Python list in the key (`f"{sizes}"`) made every card the same question | Never put a list or brackets in a question key; join with `-` instead. |
| Repeats with earlier packets only show up at build time, one at a time | Before writing a new packet's lists, run `python check_questions.py "47 + 5 = []" ...` to see which are already used. |
| Answer boxes holding a + or − sign printed a blank box (Arial Rounded has no minus) | `Book.value` now uses Avenir for signs. A sign blank next to number boxes looks like a 3-digit number, so draw the sign blank as a circle. |
| Equation placed at a fixed spot (`x + w - 200`) on full-width picture cards ran into the widest picture (4 birds + 5 birds, packet 0 #62) | Right-align equations from the card edge with `eq_width`, and check the card with the widest picture, not a typical one. |
| Check-In "Mastery" tag on the title line ran into long titles | The score/mastery tag sits on the goal line (H − 103). |
| A word problem over ~95 characters wraps to 3 lines and runs into "Number sentence" | Keep stories to 2 lines, especially the long "Challenge:" ones. |
| `rm` on an empty glob aborts a `&&` chain | `mkdir -p` / `rm -f`, or don't chain. |
| Assuming paths | The folder moved without notice; check first. |
| Repeating the pattern shown just above (a "Your turn" that repeats a row of the pattern) | Pick a fresh fact. |
| Worked example equal to a practice problem | Pick a fresh fact. |
| **A new packet's practice question changed an old check-in** (packet 26 used "4 rows of 4", a fresh problem packet 21's check-in had picked, so that check-in picked a different one) | Run `python check_questions.py --skip <new folder> ...` on every new question: anything marked CHECKIN is taken. Then rebuild and compare the text of every old PDF with the last build: only the grade assessments you added parts to should change. |
| Teacher notes longer than 3 lines spill out of their box | Keep them to about 300 characters, and look at page 1 of the key. |
| `\u201c` escapes in a file written with the Write tool turn into real curly quotes, so a later patch that searches for the escape finds nothing | Search for the real character, or for a plain part of the line. |
| **Learning page running into the "For teachers" note** (key only, note sits at y ≈ 48–106) | Learning-page content must end above y = 112. Add a check like the one in `learn_doubles`, and look at the **answer key's** page 1, not just the packet's. |
| **A packet's core skill getting dodged with odd wording** because earlier packets had used those facts as filler (packet 6's "find the near double" became ☐ + ☐ = 13, and the founder said adding two numbers 1 apart is the whole point) | **Each packet owns its core facts.** Move filler problems in earlier packets to other facts so the new packet can ask its main question plainly (5 + 6 to 8 + 9 were moved out of packet 3). Never weaken the main skill to get past the duplicate check. |
| Facts already used as plain questions in an earlier packet (5 + 5 … 9 + 9 in packet 3) | Use a different wording: "double 6 = ?", "? + ? = 12", "double 7 = ?, so 7 + 8 = ?". Let `bk.ask` catch the rest. It caught "10 + 9" from packet 2. |

---

## 6. Open decisions / state

- **Packet 5 jump style:** decided. "Inline" (bubble on the curve) is the default, and the test files were deleted.
- **Packet 6 (Doubles and Near Doubles):** built; waiting for the founder's review.
- **Packet 7 (Tens and Ones):** built; waiting for the founder's review. Parts: count tens and ones from pictures → draw quick tens → count whole tens → tens plus ones (40 + 6) → which is more (circle it; no < > signs yet) → no help (☐ tens ☐ ones = 76, then 6 tens 2 ones = ☐) → words. Ten-sticks are wide: put more than 6 in a row only on 2-column cards.
- **Packet 8 (Ten More, Ten Less):** built; waiting for the founder's review. Pictures (10 more, 10 less) → 10 less ← n → 10 more strips → +10 / −10 chains → no help (ten more, ten less, both ways, mixed) → words. The founder removed the missing-number part and the unknown-start word problem; see the Missing Numbers packet below.
- **Packet 9 (Adding Two-Digit Numbers):** built; waiting for the founder's review. Add tens with pictures → pictures + helped split → split with all boxes → split that makes a new ten → no help (add tens, no new ten, make a new ten, mixed) → words. The founder removed "find the missing tens" (42 + ☐ = 72): missing-addend problems are their own unit, so don't put them in addition packets. No column (stacked) addition yet; ask the founder before adding it.
- **Packet 11 (Missing Numbers):** built; waiting for the founder's review. **Missing addends only, no subtraction forms** (founder: no 15 − ☐ = 8, no ☐ − 7 = 8). **Core idea (founder): it's all about jumping up, and always the same route: jump to the next ten, then by tens, then the ones.** 42 + ☐ = 75 is 42 → 50 → 70 → 75 = 8 + 20 + 5 = 33 (never 42 → 72 → 75). Within 20: 8 → 10 → 13. Parts: jump to 10 (stops given) → jump to the next ten (two-digit, stops given) → find the stops (tens are boxes) → no help (up to 20, total is a ten, two-digit, mixed) → word problems (unknown change, "how many more"). Doubles and near doubles are left out of the within-20 facts because packet 6 owns them (its "find the missing near double" already asks 8 + ☐ = 17). **Outside this packet and each packet's own core skill, keep the blank in the answer spot.**
- **Packet 10 (Subtracting Two-Digit Numbers):** built; waiting for the founder's review. Founder chose real take-away subtraction (not jumping up) because **borrowing will be added later** and builds on the tens/ones split. Every problem has enough ones; Part 4 "Enough ones?" only asks kids to spot the borrowing cases (52 − 27 → no). Take away tens (pictures) → tens and ones (pictures + helped rows) → all-box rows → enough ones? → no help (take away tens, take away ones, tens and ones, mixed) → take-away word problems. "How many more?" stories wait for Missing Numbers (jumping up).
- **Packet 12 (Subtracting with Borrowing):** built; the founder picked the **rows** option over stacked columns ("the one with the sticks is a much better first start"). Column subtraction (and column addition with carrying) can be a later packet; `column_sub` already exists. **Part 1 gives the tens and asks only for the ones** ("63 = 5 tens ☐ ones"), so kids see that the opened ten joins the ones. Parts: break a ten (pictures) → break, then subtract (break row given) → all boxes → no help (break a ten, from a tens number, take away ones, mixed) → take-away words. When showing the founder two designs, build both with `OPTIONS` (each gets its own registry copy) and send both keys.
- **Packet 0 (Adding and Taking Away):** built; waiting for the founder's review. Plan, research and the story bank are in `PLAN-0-adding-and-taking-away.md`. The founder wants it much bigger than the others (141 problems) for early retention, with real-object pictures and the cross-out method. Picture problems may reuse a fact with a different object (keys like `pic: apple 5 - 2`); plain facts never repeat and skip the doubles/near doubles packet 6 owns. Sums stay ≤ 9 (10 belongs to Ten Buddies). Within 5 first, then up to 9. Up-to-9 pictures need full-width cards (rows of 5); half-width cards made the groups wrap badly.
- **Check-Ins and grade assessments (founder's request):**
  - **Check-In:** one page per packet (`<slug>-check-in.pdf`) with each kind of problem from the packet.
  - **Assessments:** a pre and a post assessment per grade in `assessments/`. Kindergarten covers packets 0–2, grade 1 covers 3–9, grade 2 covers 10–32, grade 3 covers 33–47, and grade 4 covers 48–52.
  - **How it's built:**
    - Defined in `CHECKINS` and `GRADES` at the end of `build_worksheets.py`. A `Section` is (name, subtitle, card kind, pool, count, packet).
    - Card kinds are in `KINDS`. Each points to a shared `c_*` drawer: the practice packets' card code, lifted out.
    - `Picker` takes problems from each pool: first ones no practice packet used, then practice ones, and never twice across check-ins and assessments (except tiny fact sets like ten buddies, which never repeat within one page).
    - `BALANCE` alternates yes/no, even/odd and </> answers so they don't form a pattern, and `spread()` keeps two equations in a row from starting with the same number.
    - Word problems come from templates in `stories()`.
  - **Rules to keep:**
    - A check-in must fit on one page (the build warns if it doesn't).
    - Every answer key shows "Mastery: N of M (80%)".
    - Assessment keys end with a scoring sheet.
  - **When adding a packet:** add a `CHECKINS` entry and add it to the right grade in `GRADES`.
  - **`curriculum.json`** is written by every build (`write_manifest`): packets in `TEACHING_ORDER` (add new packets there, or the build stops), and each test's questions with their part, packet and answer. Answers come from the key's answer boxes (`Book.value` records them while `bk.rec` is a list), from `solve()` for plain arithmetic prompts, or from `ANSWER_OF` for cards that circle a choice: **add a new choice card to `ANSWER_OF`**. The website's tutor marking and "Recommended next" read this file, so changing a test changes the website after `npm run sync:curriculum`.
- **Packets 13–22:** built in one go from `PLAN-13-22.md` (research, sources and the plan for each); all waiting for the founder's review. Left for later: money, time, measurement, two-step bar-model word problems, subtracting across zeros (403 − 157), fractions.
- **Packets 23–25 (Hundred Buddies, Counting Forward and Backward, Halves):** built from Mathnasium research (counting from any number by any number both ways; wholes and parts: halves first, then complements). Waiting for the founder's review. In teaching order they can come earlier: Hundred Buddies after 11, Counting after 16, Halves after 22. Each has a Check-In, and they're in the grade 2 assessments.
- **Packets 26–30 (Halves, Thirds and Fourths · Telling Time · Money · Subtracting Across Zeros · Two-Step Word Problems):** built from `PLAN-26-30.md` (research, sources, the order and why). Waiting for the founder's review. The order changed from the old plan: shapes before time (half past and quarter past are halves and fourths of a circle), and across zeros before two-step problems. Each ends with a short **"Remember?"** part: 6 fresh problems from earlier packets (spaced review; research in the plan). Each has a Check-In and parts in the grade 2 assessments, which now cover packets 10–30 (92 problems; the scoring sheet tightens its rows to stay on one page).
- **Rulers (founder):** a tape measure or ruler can be used for measuring length. Number lines are still out everywhere else.
- **Packets 31–32 (Measuring Length, Graphs):** finish grade 2 (all 2.MD standards except 2.MD.6, number-line sums). Line plots are "X charts". Waiting for the founder's review.
- **Packets 33–36 (Multiplication, Multiplication Strategies, Division, Fractions):** the start of grade 3, from the research in `PLAN-26-30.md`. Multiplication is "groups of", then arrays; the hard facts come from ×2, ×5 and ×10 by breaking arrays apart; division is sharing and grouping, then a missing factor; fractions use strips and the fraction wall. New `assessments/grade-3-*` (42 problems) cover them. Waiting for the founder's review.
- **Packet 37 (Rounding):** built with the founder's method (ten below, ten above, which is closer?), no number line. Waiting for the founder's review.
- **Packets 38–42 (Multiplying by Tens, Area, Perimeter, Elapsed Time, All Four Operations):** built from `PLAN-38-42.md` (research, sources, order). Waiting for the founder's review. Elapsed time uses jumps between times (packet 11), not a number line. Each has a Check-In and parts in the grade 3 assessments (now 59 problems).
- **Packets 43–52 (Patterns in the Times Table, Mass and Liquid Volume, Scaled Graphs, Quarter Inch, Quadrilaterals, Thousands, Rounding Big Numbers, Adding and Subtracting Big Numbers, Multiplying by One Digit, Division with Remainders):** built from `PLAN-43-52.md`. 43–47 finish grade 3; 48–52 start grade 4 with new `assessments/grade-4-*` (34 problems; grade 3 is now 69). Waiting for the founder's review. The founder asked for 10 packets per round.
- **Checking repeats for a batch:** `python check_questions.py --skip` only leaves out one folder, so a batch of new packets marks each other as USED. For a batch, check every new packet's questions against the older packets and each other at once (build the older packets into one registry, then collect each new packet's `ask` keys); and after the full build, compare old PDFs: a new review question that an older check-in had picked changes that check-in (and now the packet, since the check-in is its last page).
- **Next up (not built):** grade 4 continued: multiplying two two-digit numbers (4.NBT.5), dividing bigger numbers (4.NBT.6), factors and multiples (4.OA.4), equivalent fractions (4.NF.1), comparing fractions (4.NF.2), adding fractions with like denominators (4.NF.3), tenths and hundredths (4.NF.5–7), angles (4.MD.5–7), line plots with fractions (4.MD.4), area and perimeter formulas (4.MD.3). Also mental-math warm-up cards per level.
- The online Claude doc "Up to and Over Ten: Research & Practice Problems" is out of date compared with the PDFs. Don't rely on it.
- The founder likes a short summary after each change: what changed, what was checked, and which files.
