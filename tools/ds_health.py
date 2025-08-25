from pathlib import Path
import statistics as st
root = Path("datasets/mt2")
sizes=[]
counts={0:0,1:0,2:0}
for lbl in (root/"labels"/"train").glob("*.txt"):
for ln in lbl.read_text().splitlines():
c,cx,cy,w,h = ln.split()
counts[int(c)] += 1
sizes.append(float(w)*float(h))
print("bbox per class:", counts)
if sizes: print("median bbox area:", st.median(sizes))