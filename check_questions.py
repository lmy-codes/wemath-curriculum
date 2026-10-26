"""
List every question already used by earlier packets, or check new ones before writing a packet.

    python check_questions.py                     # how many questions all packets use
    python check_questions.py "47 + 5 = []" ...   # USED, CHECKIN or free for each (write blanks as [])
    python check_questions.py --skip 30-two-step-word-problems "story: 38 + 26 = 64" ...
                                                  # leave out the packet you're writing

USED means a practice packet asks it (the build would stop). CHECKIN means a check-in or assessment
picked it: a practice packet can use it, but then that check-in quietly changes, so pick a free one.

Builds into a temp folder, so nothing in this folder changes.
"""
import pathlib
import sys
import tempfile

import build_worksheets as bw

args = sys.argv[1:]
skip = None
if args[:1] == ["--skip"]:
    skip, args = args[1], args[2:]
bw.ROOT = pathlib.Path(tempfile.mkdtemp())
bw.T = bw.theme(True)
packets = [p for p in bw.PACKETS if p[0] != skip]
asked = {}
for packet in packets:
    bw.build_packet(packet, "color", True, asked)
picker = bw.Picker(asked)
for packet in packets:
    if packet[0] in bw.CHECKINS:
        bw.build_check_in(packet, "color", True, picker)
for grade in bw.GRADES:
    for when in ("pre", "post"):
        bw.build_assessment(grade, when, "color", True, picker)
print(len(asked), "questions in", len(packets), "packets")
for q in args:
    k = bw.qkey(q)
    if k in asked:
        print(f"USED     {q}   ({asked[k]})")
    else:
        print(("CHECKIN  " if k in picker.used else "free     ") + q)
