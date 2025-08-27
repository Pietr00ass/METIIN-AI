import json, cv2, numpy as np
from pathlib import Path
from agent.wasd import resolve_key

def align(video_path, events_path, out_dir, image_size=224, region=None):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    keys = []
    with open(events_path, 'r') as f:
        for line in f:
            e = json.loads(line)
            if e['kind'] == 'key':
                p = e['payload']
                k = resolve_key(p)
                if not k:
                    continue
                k = k.lower()
                if any(ch in k for ch in ['w', 'a', 's', 'd']):
                    keys.append((e['ts'], 'down' if p.get('down', False) else 'up', k))
    held = { 'w':False,'a':False,'s':False,'d':False }
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    idx=0; ok=True
    while ok:
        ok, frame = cap.read(); idx+=1
        if not ok: break
        ts = idx / max(fps,1.0)
        for (t,typ,k) in list(keys):
            if abs(t - ts) <= 0.05:
                if 'w' in k: held['w'] = (typ=='down')
                if 'a' in k: held['a'] = (typ=='down')
                if 's' in k: held['s'] = (typ=='down')
                if 'd' in k: held['d'] = (typ=='down')
        img = cv2.resize(frame, (image_size,image_size))
        y = np.array([held['w'],held['a'],held['s'],held['d']], dtype=np.float32)
        np.savez_compressed(Path(out_dir)/f"kbd_{idx:07d}.npz", img=img[:,:,::-1], y=y)
    cap.release()
