from __future__ import annotations

import logging
import time

import numpy as np

from agent import get_config
from agent.channel import ChannelSwitcher
from agent.detector import ObjectDetector
from agent.hunt_destroy import HuntDestroy
from agent.scanner import AreaScanner
from agent.teleport import Teleporter
from agent.wasd import KeyHold
from recorder.window_capture import WindowCapture

logger = logging.getLogger(__name__)


class CycleFarm:
    """
    Cykl 8×8: sloty 1..8 × CH(ch_from..ch_to).
    Na każdym slocie: teleport -> poluj (z autoskanem 'E').
    Brak celu -> krótki skan E; nadal brak -> kolejny slot.
    Ma cooldown slotów (minuty) by nie wracać od razu.
    """

    def __init__(self, cfg: dict | None = None):
        cfg = cfg or get_config()
        self.cfg = cfg
        self.win = WindowCapture(cfg["window"]["title_substr"])
        if not self.win.locate(timeout=5):
            raise RuntimeError("Nie znaleziono okna – sprawdź title_substr")

        self.dry = cfg.get("dry_run", False)
        tdir = cfg["paths"]["templates_dir"]
        self.tp = Teleporter(self.win, tdir, use_ocr=True, dry=self.dry, cfg=cfg)
        self.keys = KeyHold(
            dry=self.dry, active_fn=getattr(self.win, "is_foreground", None)
        )
        self.ch = ChannelSwitcher(
            self.win,
            tdir,
            dry=self.dry,
            keys=self.keys,
            hotkeys=cfg.get("channel", {}).get("hotkeys"),
        )
        self.agent = HuntDestroy(cfg, self.win)
        self.det = ObjectDetector(cfg["paths"]["model"], cfg["detector"]["classes"])
        self._stop = False

        ch_cfg = cfg.get("channel", {})
        self.ch_settle = float(ch_cfg.get("settle_sec", 5.0))
        self.ch_check = float(ch_cfg.get("timeout_per_ch", 5.0))

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
        self.scan_enabled = scan.get("enabled", True)
        if self.scan_enabled:
            # AreaScanner emulates a human turning in place by repeatedly holding the
            # camera‑rotate key.  This reveals monsters that might spawn behind the
            # player after teleportation.
            self.scanner = AreaScanner(
                self.keys,
                self.spin_key,
                self.sweep_ms,
                self.sweeps,
                self.idle_before_scan,
                self.pause_between_sweeps,
            )
        else:
            self.scanner = None

        # cooldown slotów
        self.cooldown = {}
        self.cooldown_min = int(cfg.get("cooldowns", {}).get("slot_min", 10))

    def stop(self):
        self._stop = True
        try:
            self.keys.stop()
        except Exception:
            pass
        try:
            self.win.close()
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
            logger.info("Przechodzę na kanał %s", ch)
            try:
                self.ch.switch(ch, post_wait=self.ch_settle)
            except Exception:
                logger.warning("Nie udało się zmienić kanału na %s", ch)

            for slot in slots:
                if self._stop:
                    break

                # sprawdzenie cooldownu dla (ch, slot)
                now = time.time()
                key = (ch, slot)
                last = self.cooldown.get(key, 0)
                if now - last < self.cooldown_min * 60:
                    logger.debug("Pomijam slot %s na kanale %s - cooldown", slot, ch)
                    continue

                # teleportacja do slotu
                logger.info("Teleportuję na slot %s (ch%s)", slot, ch)
                try:
                    # większość logiki teleportu (otwarcie panelu itp.)
                    # znajduje się w klasie Teleporter
                    if hasattr(self.tp, "teleport_slot"):
                        self.tp.teleport_slot(slot, page_label)
                    else:
                        self.tp.teleport(slot, page_label)
                except Exception:
                    logger.warning(
                        "Teleportacja na slot %s kanału %s nie powiodła się", slot, ch
                    )
                    # jeśli teleportacja się nie udała, pomijamy slot
                    self.cooldown[key] = now
                    continue

                # ewentualne skanowanie po teleportacji
                if self.scanner and not self._any_target_seen():
                    logger.debug("Brak celu po teleportacji – skanuję otoczenie")
                    self.scanner.scan()

                # jeżeli nadal brak celu, od razu kolejny slot
                if not self._any_target_seen() or self._stop:
                    logger.info("Brak celu na slocie %s kanału %s", slot, ch)
                    self.cooldown[key] = time.time()
                    continue

                # główna pętla polowania na spocie
                logger.debug("Rozpoczynam polowanie na slocie %s kanału %s", slot, ch)
                t_end = time.time() + float(per_spot_sec)
                last_seen = time.time()
                while time.time() < t_end and not self._stop:
                    self.agent.step()
                    if self._any_target_seen():
                        last_seen = time.time()
                    elif time.time() - last_seen > float(clear_sec):
                        # spróbuj przeskanować otoczenie
                        if self.scanner:
                            self.scanner.scan()
                        if not self._any_target_seen():
                            self.ch.cycle_until_target_seen(
                                check_fn=self._any_target_seen,
                                settle=self.ch_settle,
                                timeout_per_ch=self.ch_check,
                                max_rounds=1,
                            )
                        if not self._any_target_seen():
                            logger.debug("Pole czyste – przechodzę dalej")
                            break
                        last_seen = time.time()

                # zapisz cooldown na odwiedzony slot
                self.cooldown[key] = time.time()

        # zakończ po przejściu całego cyklu
        self.win.close()
        return
