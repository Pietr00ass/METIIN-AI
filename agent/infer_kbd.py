from __future__ import annotations
import time, numpy as np, cv2, torch
from recorder.window_capture import WindowCapture
from .wasd import KeyHold
from .stuck_flow import FlowStuck
from .model_kbd import KbdPolicy

class KbdVisionAgent:
    def __init__(self, cfg):
        self.win = WindowCapture(cfg['window']['title_substr'])
        self.keys = KeyHold()
        self.period = 1/15
        self.flow = FlowStuck(cfg.get('stuck', {}).get('flow_window', 0.8), fps=15, min_mag=cfg.get('stuck', {}).get('min_flow_mag', 0.7))
        self.net = KbdPolicy(); self.net.load_state_dict(torch.load('checkpoints/kbd_policy.pt', map_location='cpu'))
        self.net.eval()

    def run(self):
        assert self.win.locate()
        while True:
            t0=time.time()
            fr = self.win.grab(); frame = np.array(fr)[:,:,:3]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            stuck = self.flow.update(gray)
            img = cv2.resize(frame, (224,224))[:,:,::-1]
            x = torch.tensor(img).permute(2,0,1).unsqueeze(0).float()/255.0
            with torch.no_grad(): y = self.net(x).squeeze(0).numpy()
            self.keys.release_all()
            keys = ['w','a','s','d']
            for i,k in enumerate(keys):
                if y[i] > 0.5: self.keys.press(k)
            if stuck:
                self.keys.release_all(); self.keys.press('a'); time.sleep(0.2); self.keys.release_all()
            dt=time.time()-t0
            if dt<self.period: time.sleep(self.period-dt)
