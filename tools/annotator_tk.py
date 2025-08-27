# tools/annotator_tk.py
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

# Ścieżki datasetu
ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "datasets" / "mt2" / "images" / "train"
LBL_DIR = ROOT / "datasets" / "mt2" / "labels" / "train"
LBL_DIR.mkdir(parents=True, exist_ok=True)

# Kolejność klas MUSI zgadzać się z data.yaml
CLASSES = ["metin", "boss", "potwory"]

HELP = """Sterowanie:
- Lewy przycisk: przeciągnij, aby narysować prostokąt
- 1/2/3: wybierz klasę (metin/boss/potwory)
- Delete: usuń zaznaczoną ramkę (z listy po prawej)
- S: zapisz etykiety
- A / D: poprzedni / następny obraz
- Ctrl + +/- : zoom (opcjonalnie)
- H: ten help
"""


def yolo_line(cls_id, cx, cy, w, h):
    return f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n"


class Annotator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mini Annotator (YOLO, Tkinter)")
        self.geometry("1200x750")

        # Stan
        self.images = sorted([p for p in IMG_DIR.glob("*.jpg")])
        if not self.images:
            messagebox.showerror("Brak obrazów", f"Nie ma JPG w {IMG_DIR}")
            sys.exit(1)
        self.idx = 0
        self.curr_img_path: Path | None = None
        self.curr_image: Image.Image | None = None
        self.tk_img: ImageTk.PhotoImage | None = None
        self.boxes = []  # list[(cls, cx,cy,w,h)]
        self.sel_box = None  # indeks wybranej ramki
        self.start_pt = None
        self.zoom = 1.0

        # UI
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main = ttk.Frame(self)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # Canvas (obraz + rysowanie)
        self.canvas = tk.Canvas(main, bg="#222")
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        # Panel boczny
        side = ttk.Frame(main)
        side.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        ttk.Label(side, text="Klasa (1/2/3):").pack(anchor="w")
        self.cls_var = tk.StringVar(value=CLASSES[0])
        self.cls_combo = ttk.Combobox(
            side, textvariable=self.cls_var, values=CLASSES, state="readonly"
        )
        self.cls_combo.pack(fill="x", pady=(0, 6))
        self.listbox = tk.Listbox(side, height=20, exportselection=False)
        self.listbox.pack(fill="both", expand=True)
        btns = ttk.Frame(side)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="Usuń (Del)", command=self.delete_selected).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(btns, text="Zapisz (S)", command=self.save_labels).pack(side="left")

        # Status
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status).grid(
            row=1, column=0, sticky="we", padx=6, pady=(0, 6)
        )

        # Zdarzenia
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.listbox.bind("<<ListboxSelect>>", self.on_select_box)
        self.bind("<Key>", self.on_key)

        self.after(50, self.load_image)
        self.set_status()

    # --- Helpers ---
    def set_status(self, extra=""):
        base = f"[{self.idx+1}/{len(self.images)}] {self.curr_img_path.name if self.curr_img_path else ''}  |  Klasa: {self.cls_var.get()}  |  Zoom: {self.zoom:.2f}"
        self.status.set(base + ("  |  " + extra if extra else ""))

    def img_to_canvas_coords(self, x, y):
        """mapuj współrzędne obrazu -> canvas (z uwzgl. zoomu i centrowania)"""
        if not self.curr_image:
            return x, y
        W, H = self.curr_image.size
        cw = int(W * self.zoom)
        ch = int(H * self.zoom)
        x0 = (self.canvas.winfo_width() - cw) // 2
        y0 = (self.canvas.winfo_height() - ch) // 2
        return x0 + int(x * self.zoom), y0 + int(y * self.zoom)

    def canvas_to_img_coords(self, X, Y):
        """mapuj współrzędne canvas -> obraz (nieprzekroczone do [0,W/H])"""
        if not self.curr_image:
            return 0, 0
        W, H = self.curr_image.size
        cw = int(W * self.zoom)
        ch = int(H * self.zoom)
        x0 = (self.canvas.winfo_width() - cw) // 2
        y0 = (self.canvas.winfo_height() - ch) // 2
        x = (X - x0) / self.zoom
        y = (Y - y0) / self.zoom
        return max(0, min(W - 1, x)), max(0, min(H - 1, y))

    # --- Rysowanie / interakcja ---
    def on_press(self, e):
        self.start_pt = (e.x, e.y)

    def on_drag(self, e):
        if not self.start_pt:
            return
        self.redraw(temp_rect=(self.start_pt, (e.x, e.y)))

    def on_release(self, e):
        if not self.start_pt:
            return
        (x1, y1) = self.canvas_to_img_coords(*self.start_pt)
        (x2, y2) = self.canvas_to_img_coords(e.x, e.y)
        self.start_pt = None
        if abs(x2 - x1) < 3 or abs(y2 - y1) < 3:
            self.redraw()
            return
        # YOLO: cx,cy,w,h znormalizowane [0..1]
        W, H = self.curr_image.size
        lx1, lx2 = sorted([x1, x2])
        ly1, ly2 = sorted([y1, y2])
        w = (lx2 - lx1) / W
        h = (ly2 - ly1) / H
        cx = (lx1 + lx2) / 2 / W
        cy = (ly1 + ly2) / 2 / H
        cls_id = CLASSES.index(self.cls_var.get())
        self.boxes.append([cls_id, cx, cy, w, h])
        self.refresh_list()
        self.redraw()

    def on_select_box(self, _):
        self.sel_box = (
            self.listbox.curselection()[0] if self.listbox.curselection() else None
        )
        self.redraw()

    def on_key(self, e):
        if e.char == "1":
            self.cls_var.set(CLASSES[0])
            self.set_status()
        elif e.char == "2":
            self.cls_var.set(CLASSES[1])
            self.set_status()
        elif e.char == "3":
            self.cls_var.set(CLASSES[2])
            self.set_status()
        elif e.char.lower() == "s":
            self.save_labels()
        elif e.char.lower() == "a":
            self.prev_img()
        elif e.char.lower() == "d":
            self.next_img()
        elif e.char.lower() == "h":
            messagebox.showinfo("Help", HELP)
        elif e.keysym == "Delete":
            self.delete_selected()
        elif (e.state & 4) and e.keysym in ("plus", "KP_Add"):  # Ctrl + +
            self.zoom = min(4.0, self.zoom * 1.1)
            self.redraw()
            self.set_status()
        elif (e.state & 4) and e.keysym in ("minus", "KP_Subtract"):
            self.zoom = max(0.25, self.zoom / 1.1)
            self.redraw()
            self.set_status()

    # --- Obraz / etykiety ---
    def load_image(self):
        self.canvas.delete("all")
        self.curr_img_path = self.images[self.idx]
        self.curr_image = Image.open(self.curr_img_path).convert("RGB")
        self.zoom = 1.0
        self.boxes = []
        # wczytaj istniejące .txt
        y = LBL_DIR / (self.curr_img_path.stem + ".txt")
        if y.exists():
            with open(y, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        cls, cx, cy, w, h = parts
                        self.boxes.append(
                            [int(cls), float(cx), float(cy), float(w), float(h)]
                        )
        self.refresh_list()
        self.redraw()
        self.set_status()

    def save_labels(self):
        y = LBL_DIR / (self.curr_img_path.stem + ".txt")
        with open(y, "w", encoding="utf-8") as f:
            for cls, cx, cy, w, h in self.boxes:
                f.write(yolo_line(cls, cx, cy, w, h))
        self.set_status("Zapisano.")

    def prev_img(self):
        self.save_labels()
        if self.idx > 0:
            self.idx -= 1
            self.load_image()

    def next_img(self):
        self.save_labels()
        if self.idx < len(self.images) - 1:
            self.idx += 1
            self.load_image()

    # --- Rysowanie na canvasie ---
    def redraw(self, temp_rect=None):
        self.canvas.delete("all")
        if not self.curr_image:
            return
        W, H = self.curr_image.size
        # dopasuj do rozmiaru canvasu
        cw = int(W * self.zoom)
        ch = int(H * self.zoom)
        img_resized = self.curr_image.resize((cw, ch), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(img_resized)
        x0 = (self.canvas.winfo_width() - cw) // 2
        y0 = (self.canvas.winfo_height() - ch) // 2
        self.canvas.create_image(x0, y0, anchor="nw", image=self.tk_img)

        # narysuj istniejące ramki
        for i, (cls, cx, cy, w, h) in enumerate(self.boxes):
            x = (cx - w / 2) * W
            y = (cy - h / 2) * H
            X1, Y1 = self.img_to_canvas_coords(x, y)
            X2, Y2 = self.img_to_canvas_coords(x + w * W, y + h * H)
            color = "#ffcc00" if i == self.sel_box else "#00e0ff"
            self.canvas.create_rectangle(X1, Y1, X2, Y2, outline=color, width=2)
            self.canvas.create_text(
                X1 + 4, Y1 + 10, text=CLASSES[cls], fill=color, anchor="w"
            )

        # rysuj aktualnie przeciągany prostokąt (podgląd)
        if temp_rect:
            (sx, sy), (ex, ey) = temp_rect
            self.canvas.create_rectangle(
                sx, sy, ex, ey, outline="#ffffff", dash=(4, 2), width=2
            )

    def delete_selected(self):
        if self.sel_box is not None and 0 <= self.sel_box < len(self.boxes):
            self.boxes.pop(self.sel_box)
            self.sel_box = None
            self.refresh_list()
            self.redraw()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for cls, cx, cy, w, h in self.boxes:
            self.listbox.insert(
                tk.END, f"{CLASSES[cls]}  cx={cx:.3f} cy={cy:.3f} w={w:.3f} h={h:.3f}"
            )


if __name__ == "__main__":
    app = Annotator()
    app.mainloop()
