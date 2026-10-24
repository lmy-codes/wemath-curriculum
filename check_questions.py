"""
List every question already used by earlier packets, or check new ones before writing a packet.

    python check_questions.py                     # how many questions all packets use
    python check_questions.py "47 + 5 = []" ...   # USED or free for each (write blanks as [])

Builds the packets into a temp folder, so nothing in this folder changes.
"""
import pathlib
import sys
import tempfile

import build_worksheets as bw

bw.ROOT = pathlib.Path(tempfile.mkdtemp())
bw.T = bw.theme(True)
asked = {}
for packet in bw.PACKETS:
    bw.build_packet(packet, "color", True, asked)
print(len(asked), "questions in", len(bw.PACKETS), "packets")
for q in sys.argv[1:]:
    print(("USED  " if q in asked else "free  ") + q + (f"   ({asked[q]})" if q in asked else ""))
