from __future__ import annotations

import time
import numpy as np

from recorder.window_capture import WindowCapture
from agent.teleport import Teleporter
from agent.channel import ChannelSwitcher
from agent.hunt_destroy import HuntDestroy
from agent.detector import ObjectDetector
from agent.wasd import KeyHold


class CycleFarm:
    """
    Cykl 8×8: sloty 1..8 × CH(ch_from..ch_to).
    Na każdym slocie: teleport -> poluj (z autoskanem 'E').
    Brak celu -> krótki skan E; nadal brak -> kolejny slot.
    Ma cooldown slotów (minuty) by nie wracać od razu.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.win = WindowCapture(cfg["window"]["title_substr"])
        assert self.win.locate()

        self.dry = cfg.get("dry_run", False)
        self.tp = Teleporter(self.win, use_ocr=True, dry=self.dry)
        self.ch = ChannelSwitcher(self.win, dry=self.dry)
        self.agent = HuntDestroy(cfg, self.win)
        self.det = ObjectDetector(cfg["detector"]["model_path"], cfg["detector"]["classes"])
        self.keys = KeyHold(dry=self.dry, active_fn=getattr(self.win, "is_foreground", None))
        self._stop = False

        # progi i priorytety
        self.conf_thr = float(cfg.get("detector", {}).get("conf_thr", 0.5))
        self.priority = list(cfg.get("priority", []))

        # parametry skanowania
        scan = cfg.get("scan", {})
        self.spin_key = scan.get("key", "e")
        self.sweep_ms = int(scan.get("sweep_ms", 250))
        self.sweeps = int(scan.get("sweeps", 8))
        self.idle_before_scan = float(scan.get("idle_sec", 1.5))
        self.pause_between_sweeps = float(scan.get("pause", 0.12))

        # cooldown slotów
        self.cooldown = {}
        self.cooldown_min = int(cfg.get("cooldowns", {}).get("slot_min", 10))

    def stop(self):
        self._stop = True
        try:
            self.keys.stop()
        except Exception:
            pass

    # ---- detekcje ----
    def _any_target_seen(self) -> bool:
        fr = self.win.grab()
        frame = np.array(fr)[:, :, :3].copy()
        dets = self.det.infer(frame)
        return bool(dets)

    # ---- główna pętla cyklu ----
    def run(self, page_label, ch_from, ch_to, slots, per_spot_sec, clear_sec):
        """Główna pętla cyklu farmienia.

        Parameters
        ----------
        page_label: str
            Etykieta strony teleportu.
        ch_from, ch_to: int
            Zakres kanałów do cyklicznego odwiedzenia.
        slots: Iterable[int]
            Kolekcja numerów slotów do odwiedzenia.
        per_spot_sec: float
            Maksymalny czas polowania na jednym spocie.
        clear_sec: float
            Czas bez celu po którym uznajemy spot za czysty.
        """

        # Przejście przez kanały oraz sloty
        for ch in range(ch_from, ch_to + 1):
            if self._stop:
                break

            # zmiana kanału
            try:
                self.ch.switch(ch)
            except Exception:
                pass

            for slot in slots:
                if self._stop:
                    break

                # sprawdzenie cooldownu dla (ch, slot)
                now = time.time()
                key = (ch, slot)
                last = self.cooldown.get(key, 0)
                if now - last < self.cooldown_min * 60:
                    continue

                # teleportacja do slotu
                try:
                    # większość logiki teleportu (otwarcie panelu itp.)
                    # znajduje się w klasie Teleporter
                    if hasattr(self.tp, "teleport_slot"):
                        self.tp.teleport_slot(slot, page_label)
                    else:
                        self.tp.teleport(slot, page_label)
                except Exception:
                    # jeśli teleportacja się nie udała, pomijamy slot
                    self.cooldown[key] = now
                    continue

                # ewentualne skanowanie po teleportacji
                if not self._any_target_seen():
                    time.sleep(self.idle_before_scan)
                    for _ in range(self.sweeps):
                        if self._stop:
                            break
                        self.keys.press(self.spin_key)
                        time.sleep(self.sweep_ms / 1000.0)
                        self.keys.release(self.spin_key)
                        time.sleep(self.pause_between_sweeps)

                # jeżeli nadal brak celu, od razu kolejny slot
                if not self._any_target_seen() or self._stop:
                    self.cooldown[key] = time.time()
                    continue

                # główna pętla polowania na spocie
                t_end = time.time() + float(per_spot_sec)
                last_seen = time.time()
                while time.time() < t_end and not self._stop:
                    self.agent.step()
                    if self._any_target_seen():
                        last_seen = time.time()
                    elif time.time() - last_seen > float(clear_sec):
                        # spróbuj przeskanować otoczenie
                        time.sleep(self.idle_before_scan)
                        for _ in range(self.sweeps):
                            if self._stop:
                                break
                            self.keys.press(self.spin_key)
                            time.sleep(self.sweep_ms / 1000.0)
                            self.keys.release(self.spin_key)
                            time.sleep(self.pause_between_sweeps)
                        if not self._any_target_seen():
                            break
                        last_seen = time.time()

                # zapisz cooldown na odwiedzony slot
                self.cooldown[key] = time.time()

        # zakończ po przejściu całego cyklu
        return
