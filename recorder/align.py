import json, cv2, numpy as np
from pathlib import Path

def align(video_path, events_path, out_dir, image_size=224, region=(0,0,1280,720)):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    clicks = []
    with open(events_path, 'r') as f:
        for line in f:
            e = json.loads(line)
            if e['kind'] == 'click' and 'left' in e['payload']['button']:
                clicks.append(e)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    idx = 0; ok = True
    while ok:
        ok, frame = cap.read(); idx += 1
        if not ok: break
        ts = idx / max(fps, 1.0)
        nearest = None; best = 9e9
        for e in clicks:
            d = abs(e['ts'] - e.get('ts0', 0.0) - ts)
            if d < best and d <= 0.2:
                best = d; nearest = e
        h, w = frame.shape[:2]
        if nearest is not None:
            x = (nearest['payload']['x'] - region[0]) / w
            y = (nearest['payload']['y'] - region[1]) / h
            click = 1
        else:
            x = 0.0; y = 0.0; click = 0
        img = cv2.resize(frame, (image_size, image_size))
        np.savez_compressed(Path(out_dir)/f"sample_{idx:07d}.npz", img=img[:, :, ::-1], x=x, y=y, click=click)
    cap.release()
