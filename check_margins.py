"""Finds anything drawn past the page's side margins (a number or word running off the page).

    python check_margins.py <build folder>      e.g. python check_margins.py .   (after a build)

Renders every page of every colour PDF and lists the pages with ink in the outer 38 pt on the left or right
(the margins are 48 pt; 10 pt of slack). Black-and-white pages have the same layout.
"""
import pathlib
import sys

import numpy as np
import pypdfium2 as P

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
hits = []
for f in sorted(root.glob("*/color/*.pdf")):
    d = P.PdfDocument(str(f))
    for i in range(len(d)):
        a = np.asarray(d[i].render(scale=1).to_pil().convert("L"))
        right, left = a[30:-30, 574:], a[30:-30, :38]
        if (right < 200).sum() > 3 or (left < 200).sum() > 3:
            hits.append(f"{f.relative_to(root)} page {i + 1}")
    d.close()
print("\n".join(hits) or "Nothing past the margins.")
