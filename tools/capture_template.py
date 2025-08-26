from pathlib import Path
import cv2, numpy as np
from recorder.window_capture import WindowCapture


out = Path("assets/templates"); out.mkdir(parents=True, exist_ok=True)
wc = WindowCapture("Metin2")  # fragment tytułu
if not wc.locate(timeout=5):
    raise RuntimeError("Nie znaleziono okna")
frame = np.array(wc.grab())[:,:,:3]
# ustaw ROI ręcznie na start
x,y,w,h = 1000, 80, 90, 30
name = "wczytaj"
cv2.imwrite(str(out/f"{name}.png"), frame[y:y+h, x:x+w])
print("zapisano:", out/f"{name}.png")