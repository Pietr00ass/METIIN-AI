from __future__ import annotations

import asyncio
import logging
import time

import numpy as np

from agent import AgentConfig, get_config
from agent.channel import ChannelSwitcher
from agent.detector import ObjectDetector
from agent.strategy import load_strategy
from agent.scanner import AreaScanner
from agent.teleport import Teleporter
from agent.wasd import KeyHold
from recorder.window_capture import WindowCapture

logger = logging.getLogger(__name__)


class CycleFarm:
    """8×8 cycle: slots 1..8 × CH(ch_from..ch_to).

    On each slot: teleport → hunt (with auto scan 'E').
    No target → short 'E' scan; still none → next slot.
    Slots have cooldown (minutes) to avoid immediate return.

    PL:
    Cykl 8×8: sloty 1..8 × CH(ch_from..ch_to).
    Na każdym slocie: teleport -> poluj (z autoskanem 'E').
    Brak celu -> krótki skan E; nadal brak -> kolejny slot.
    Ma cooldown slotów (minuty) by nie wracać od razu.
    """

    def __init__(self, cfg: AgentConfig | dict | None = None):
        if cfg is None:
            cfg = get_config()
        elif isinstance(cfg, dict):
            cfg = AgentConfig(**cfg)
        self.cfg = cfg
        self.win = WindowCapture(cfg.window.title_substr)
        if not self.win.locate(timeout=5):
            raise RuntimeError("Nie znaleziono okna – sprawdź title_substr")

        self.dry = cfg.dry_run
        tdir = cfg.paths.templates_dir
        self.tp = Teleporter(self.win, tdir, use_ocr=True, dry=self.dry, cfg=cfg)
        self.keys = KeyHold(
            dry=self.dry, active_fn=getattr(self.win, "is_foreground", None)
        )
        self.ch = ChannelSwitcher(
            self.win,
            tdir,
            dry=self.dry,
            keys=self.keys,
            hotkeys=cfg.channel.hotkeys,
        )
        self.agent = load_strategy(cfg, self.win)
        self.det = ObjectDetector(
            cfg.paths.model, cfg.detector.classes, cv2_threads=cfg.detector.cv2_threads
        )
        self._stop = False

        ch_cfg = cfg.channel
        self.ch_settle = float(ch_cfg.settle_sec)
        self.ch_check = float(ch_cfg.timeout_per_ch)

        # progi i priorytety
        self.conf_thr = float(cfg.detector.conf_thr)
        self.priority = list(cfg.priority)

        # parametry skanowania
        scan = cfg.scan
        self.spin_key = scan.key
        self.sweep_ms = int(scan.sweep_ms)
        self.sweeps = int(scan.sweeps)
        self.idle_before_scan = float(scan.idle_sec)
        self.pause_between_sweeps = float(scan.pause)
        self.scan_enabled = scan.enabled
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
        self.cooldown_min = int(cfg.cooldowns.slot_min)

    def stop(self):
        """Stop agent components gracefully.

        Delegates cleanup to the loaded strategy when it exposes a ``stop``
        method. Only expected errors from the underlying helpers are
        swallowed. Any such errors are logged for debugging instead of
        silenced.
        """
        self._stop = True

        stop_fn = getattr(self.agent, "stop", None)
        if callable(stop_fn):
            try:
                stop_fn()
            except Exception as exc:  # pragma: no cover - best effort cleanup
                logger.exception(
                    "Błąd podczas zatrzymywania strategii: %s", exc
                )

        try:
            self.keys.stop()
        except (RuntimeError, OSError) as exc:
            logger.exception("Błąd podczas zatrzymywania klawiszy: %s", exc)

        try:
            self.win.close()
        except (RuntimeError, OSError) as exc:
            logger.exception("Błąd podczas zamykania okna: %s", exc)

    # ---- detekcje ----
    def _any_target_seen(self) -> bool:
        fr = self.win.grab()
        frame = np.array(fr)[:, :, :3].copy()
        dets = self.det.infer(frame)
        return bool(dets)

    # ---- logika pojedynczego slotu ----
    async def _process_slot(self, ch, slot, page_label, per_spot_sec, clear_sec):
        """Handle teleportation and hunting on a single slot.

        PL: Obsłuż teleportację i polowanie na pojedynczym slocie.
        """

        now = time.time()
        key = (ch, slot)
        last = self.cooldown.get(key, 0)
        if now - last < self.cooldown_min * 60:
            logger.debug("Pomijam slot %s na kanale %s - cooldown", slot, ch)
            return

        logger.info("Teleportuję na slot %s (ch%s)", slot, ch)
        try:
            if hasattr(self.tp, "teleport_slot"):
                await asyncio.to_thread(self.tp.teleport_slot, slot, page_label)
            else:
                await asyncio.to_thread(self.tp.teleport, slot, page_label)
        except Exception:
            logger.warning(
                "Teleportacja na slot %s kanału %s nie powiodła się", slot, ch
            )
            self.cooldown[key] = now
            return

        if self.scanner and not self._any_target_seen():
            logger.debug("Brak celu po teleportacji – skanuję otoczenie")
            await self.scanner.scan_async()

        if not self._any_target_seen() or self._stop:
            logger.info("Brak celu na slocie %s kanału %s", slot, ch)
            self.cooldown[key] = time.time()
            return

        logger.debug("Rozpoczynam polowanie na slocie %s kanału %s", slot, ch)
        t_end = time.time() + float(per_spot_sec)
        last_seen = time.time()
        while time.time() < t_end and not self._stop:
            await asyncio.to_thread(self.agent.step)
            if self._any_target_seen():
                last_seen = time.time()
            elif time.time() - last_seen > float(clear_sec):
                if self.scanner:
                    await self.scanner.scan_async()
                if not self._any_target_seen():
                    await self.ch.cycle_until_target_seen_async(
                        check_fn=self._any_target_seen,
                        settle=self.ch_settle,
                        timeout_per_ch=self.ch_check,
                        max_rounds=1,
                    )
                if not self._any_target_seen():
                    logger.debug("Pole czyste – przechodzę dalej")
                    break
                last_seen = time.time()
            await asyncio.sleep(0)

        self.cooldown[key] = time.time()

    # ---- główna pętla cyklu ----
    async def run(
        self,
        page_label,
        ch_from,
        ch_to,
        slots,
        per_spot_sec,
        clear_sec,
        sequence=None,
    ):
        """Main farming cycle loop.

        ``sequence`` specifies the full order of channel/slot visits. Each
        element should be a two‑element iterable ``(ch, slot)`` or a dict with
        keys ``ch`` and ``slot``. When ``sequence`` is provided the parameters
        ``ch_from``, ``ch_to`` and ``slots`` are ignored.

        Parameters
        ----------
        page_label: str
            Teleport page label.
        ch_from, ch_to: int
            Range of channels to visit cyclically.
        slots: Iterable[int]
            Collection of slot numbers to visit.
        per_spot_sec: float
            Maximum time to hunt on a single spot.
        clear_sec: float
            Time without a target after which the spot is considered clear.
        sequence: Iterable
            Optional full sequence of ``(channel, slot)`` pairs.

        PL:
        Główna pętla cyklu farmienia.
        "sequence" pozwala określić pełną kolejność odwiedzania kanałów i
        slotów.  Każdy element listy powinien być dwuelementowym iterowalnym
        (ch, slot) lub słownikiem z kluczami ``ch`` i ``slot``.  Gdy sekwencja
        jest podana, parametry ``ch_from``, ``ch_to`` oraz ``slots`` są
        ignorowane.
        """

        if sequence:
            steps = []
            for item in sequence:
                if isinstance(item, dict):
                    steps.append((item["ch"], item["slot"]))
                else:
                    ch, slot = item
                    steps.append((ch, slot))
        else:
            steps = [
                (ch, slot) for ch in range(ch_from, ch_to + 1) for slot in slots
            ]

        current_ch = None
        for ch, slot in steps:
            if self._stop:
                break
            if ch != current_ch:
                logger.info("Przechodzę na kanał %s", ch)
                try:
                    await asyncio.to_thread(self.ch.switch, ch, post_wait=self.ch_settle)
                except Exception:
                    logger.warning("Nie udało się zmienić kanału na %s", ch)
                current_ch = ch
            if self._stop:
                break
            await self._process_slot(ch, slot, page_label, per_spot_sec, clear_sec)

        self.win.close()
        return
