import statistics as st
from pathlib import Path

from utils.logging_config import logger

root = Path("datasets/mt2")
sizes: list[float] = []
counts = {0: 0, 1: 0, 2: 0}

for lbl in (root / "labels" / "train").glob("*.txt"):
    for ln in lbl.read_text().splitlines():
        c, cx, cy, w, h = ln.split()
        counts[int(c)] += 1
        sizes.append(float(w) * float(h))

logger.info("bbox per class: {}", counts)
if sizes:
    logger.info("median bbox area: {}", st.median(sizes))
