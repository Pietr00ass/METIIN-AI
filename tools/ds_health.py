import logging
import statistics as st
from pathlib import Path

logging.basicConfig(level=logging.INFO)

root = Path("datasets/mt2")
sizes: list[float] = []
counts = {0: 0, 1: 0, 2: 0}

for lbl in (root / "labels" / "train").glob("*.txt"):
    for ln in lbl.read_text().splitlines():
        c, cx, cy, w, h = ln.split()
        counts[int(c)] += 1
        sizes.append(float(w) * float(h))

logging.info("bbox per class: %s", counts)
if sizes:
    logging.info("median bbox area: %s", st.median(sizes))
