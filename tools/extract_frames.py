from __future__ import annotations
import argparse
import cv2
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rec-dir", default="data/recordings", help="folder z nagraniami")
    parser.add_argument("--out-dir", default="datasets/mt2/images/train", help="folder zapisu klatek")
    parser.add_argument("--step", type=int, default=15, help="co ile klatek zapisać (przy 15 FPS → 1 kl/s)")
    args = parser.parse_args()

    if args.step <= 0:
        parser.error("--step must be positive")

    rec_dir = Path(args.rec_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not rec_dir.exists():
        parser.error(f"Nie znaleziono katalogu {rec_dir}")
    videos = sorted(rec_dir.glob("*.mp4"))
    if not videos:
        print(f"Ostrzeżenie: katalog {rec_dir} nie zawiera plików .mp4")
        return

    print(f"Znaleziono {len(videos)} nagrań…")
    for vid in videos:
        print(f"Przetwarzam: {vid}")
        cap = cv2.VideoCapture(str(vid))
        if not cap.isOpened():
            print(f"Nie można otworzyć pliku {vid}, pomijam")
            continue
        i = 0
        saved = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if i % args.step == 0:
                out = out_dir / f"{vid.stem}_{i:06d}.jpg"
                cv2.imwrite(str(out), frame)
                saved += 1
            i += 1
        cap.release()
        print(f" zapisano {saved} klatek")
    print("Gotowe.")

if __name__ == "__main__":
    main()
