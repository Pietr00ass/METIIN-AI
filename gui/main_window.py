"""Main application window for the Metin2 vision agent GUI."""

from __future__ import annotations

import json
import logging
import os
import time
import asyncio

import cv2
import numpy as np
import pyautogui
from pynput import keyboard as pynput_keyboard
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QSettings

import agent.teleport_config as tc
from agent.channel import ChannelSwitcher
from agent.cycle import CycleFarm
from agent.strategy import load_strategy
from agent.teleport import Teleporter, TeleportResult
from agent.wasd import KeyHold
from gui.preview import PreviewWorker
from gui.teleport_config_dialog import TeleportConfigDialog
from recorder.window_capture import WindowCapture

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("teleport.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# Configure Qt DPI behaviour for Windows to avoid crashes when changing DPI awareness.
# Allow users to override DPI options via environment variables; default to enabling
# automatic scaling so the UI can be scaled later.
os.environ.setdefault("QT_QPA_PLATFORM", "windows:dpiawareness=1")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

pyautogui.FAILSAFE = False  # disable the corner failsafe to avoid unintended exceptions


class QtLogHandler(QtCore.QObject, logging.Handler):
    """Forward logging records to Qt via a signal."""

    log = QtCore.Signal(str)

    def __init__(self) -> None:
        QtCore.QObject.__init__(self)
        logging.Handler.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.log.emit(msg)


class RecordThread(QtCore.QThread):
    status = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, region: tuple[int, int, int, int]):
        super().__init__()
        self.region = region

    def run(self) -> None:  # pragma: no cover - GUI thread
        from recorder.capture import record_session

        try:
            self.status.emit(
                QtCore.QCoreApplication.translate("MainWindow", "Nagrywanie 5 min…")
            )
            record_session(
                "data/recordings", region=self.region, fps=15, duration_sec=300
            )
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow",
                    "Nagrywanie zakończone. Użyj narzędzia 'extract_frames'.",
                )
            )
        except Exception as exc:  # pragma: no cover - UI feedback
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Błąd nagrywania: {exc}"
                ).format(exc=exc)
            )
        finally:
            self.finished.emit()


class AgentThread(QtCore.QThread):
    status = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:  # pragma: no cover - GUI thread
        win = WindowCapture(self.cfg["window"]["title_substr"])
        try:
            if not win.locate(timeout=5):
                self.status.emit(
                    QtCore.QCoreApplication.translate(
                        "MainWindow", "Nie znaleziono okna."
                    )
                )
                return
            agent = load_strategy(self.cfg, win)
            period = self.cfg.get("scan", {}).get("period", 1 / 15)
            while not self._stop:
                agent.step()
                time.sleep(period)
        except Exception as exc:  # pragma: no cover - UI feedback
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Błąd agenta: {exc}"
                ).format(exc=exc)
            )
        finally:
            win.close()
            self.finished.emit()


class TeleportHuntThread(QtCore.QThread):
    status = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, cfg: dict, point: str, side: str, minutes: int):
        super().__init__()
        self.cfg = cfg
        self.point = point
        self.side = side
        self.minutes = minutes
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:  # pragma: no cover - GUI thread
        win = WindowCapture(self.cfg["window"]["title_substr"])
        try:
            if not win.locate(timeout=5):
                self.status.emit(
                    QtCore.QCoreApplication.translate(
                        "MainWindow", "Nie znaleziono okna."
                    )
                )
                return
            try:
                test_img = pyautogui.screenshot()
                logger.info(
                    "Zrzut ekranu zakończony powodzeniem (%dx%d)",
                    test_img.width,
                    test_img.height,
                )
            except Exception as e:  # pragma: no cover - UI feedback
                logger.error("Błąd przy robieniu zrzutu ekranu: %s", e)
                self.status.emit(
                    QtCore.QCoreApplication.translate(
                        "MainWindow", "Błąd przechwytywania ekranu: {e}"
                    ).format(e=e)
                )
                return
            tp = Teleporter(win, self.cfg["paths"]["templates_dir"], use_ocr=True)
            res = tp.teleport(self.point, self.side)
            if res is not TeleportResult.OK:
                msg_map = {
                    TeleportResult.TEMPLATE_NOT_FOUND: QtCore.QCoreApplication.translate(
                        "MainWindow", "Nie znaleziono szablonu w panelu teleportu."
                    ),
                    TeleportResult.OCR_MISS: QtCore.QCoreApplication.translate(
                        "MainWindow", "Nie rozpoznano wskazanego slotu (OCR)."
                    ),
                    TeleportResult.WINDOW_NOT_FOREGROUND: QtCore.QCoreApplication.translate(
                        "MainWindow", "Okno gry nie jest aktywne."
                    ),
                }
                self.status.emit(
                    msg_map.get(
                        res,
                        QtCore.QCoreApplication.translate(
                            "MainWindow", "Teleportacja nie powiodła się."
                        ),
                    )
                )
            hd = load_strategy(self.cfg, win)
            t_end = time.time() + self.minutes * 60
            period = self.cfg.get("scan", {}).get("period", 1 / 15)
            while time.time() < t_end and not self._stop:
                hd.step()
                time.sleep(period)
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Zakończono 'Teleportuj i poluj'."
                )
            )
        except RuntimeError as exc:  # pragma: no cover - UI feedback
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow",
                    "Błąd przechwytywania ekranu: {exc}. Czy okno gry jest poza ekranem lub zminimalizowane?",
                ).format(exc=exc)
            )
        except Exception as exc:  # pragma: no cover - UI feedback
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Błąd teleport+poluj: {exc}"
                ).format(exc=exc)
            )
        finally:
            win.close()
            self.finished.emit()


class CycleThread(QtCore.QThread):
    status = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, cfg: dict, page: str | None):
        super().__init__()
        self.cfg = cfg
        self.page = page
        self._stop = False
        self.cycle_agent: CycleFarm | None = None

    def stop(self) -> None:
        self._stop = True
        if self.cycle_agent:
            try:
                self.cycle_agent.stop()
            except Exception:
                pass

    def run(self) -> None:  # pragma: no cover - GUI thread
        cfg = self.cfg
        cycle_cfg = cfg.get("cycle", {})
        try:
            cf = CycleFarm(cfg)
            self.cycle_agent = cf
            asyncio.run(
                cf.run(
                    page_label=self.page,
                    ch_from=cycle_cfg.get("ch_from", 1),
                    ch_to=cycle_cfg.get("ch_to", 8),
                    slots=cycle_cfg.get("slots", list(range(1, 9))),
                    per_spot_sec=cycle_cfg.get("per_spot_sec", 90),
                    clear_sec=cycle_cfg.get("clear_sec", 6),
                    sequence=cycle_cfg.get("sequence"),
                )
            )
            self.status.emit(
                QtCore.QCoreApplication.translate("MainWindow", "Cykl 8×8 zakończony.")
            )
        except Exception as exc:  # pragma: no cover - UI feedback
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Błąd cyklu: {exc}"
                ).format(exc=exc)
            )
        finally:
            self.cycle_agent = None
            self.finished.emit()


class ChannelThread(QtCore.QThread):
    status = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, cfg: dict, channel: int):
        super().__init__()
        self.cfg = cfg
        self.channel = channel

    def run(self) -> None:  # pragma: no cover - GUI thread
        try:
            cfg = self.cfg
            win = WindowCapture(cfg["window"]["title_substr"])
            try:
                if not win.locate(timeout=5):
                    self.status.emit(
                        QtCore.QCoreApplication.translate(
                            "MainWindow", "Nie znaleziono okna."
                        )
                    )
                    return
                keys = KeyHold(
                    dry=cfg.get("dry_run", False),
                    active_fn=getattr(win, "is_foreground", None),
                )
                cs = ChannelSwitcher(
                    win,
                    cfg["paths"]["templates_dir"],
                    dry=cfg.get("dry_run", False),
                    keys=keys,
                    hotkeys=cfg.get("channel", {}).get("hotkeys"),
                )
                try:
                    ok = cs.switch(self.channel)
                finally:
                    keys.stop()
                msg = (
                    QtCore.QCoreApplication.translate(
                        "MainWindow", "Zmieniono kanał na CH{ch}"
                    ).format(ch=self.channel)
                    if ok
                    else QtCore.QCoreApplication.translate(
                        "MainWindow", "Nie znaleziono przycisku CH – sprawdź szablony."
                    )
                )
                self.status.emit(msg)
            finally:
                win.close()
        except Exception as exc:  # pragma: no cover - UI feedback
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Błąd zmiany kanału: {exc}"
                ).format(exc=exc)
            )
        finally:
            self.finished.emit()


class TrainThread(QtCore.QThread):
    status = QtCore.Signal(str)
    finished = QtCore.Signal()

    def run(self) -> None:  # pragma: no cover - GUI thread
        try:
            self.status.emit(
                QtCore.QCoreApplication.translate("MainWindow", "Trening YOLO – start…")
            )
            from ultralytics import YOLO

            model = YOLO("yolov8n.pt")
            model.train(
                data="datasets/mt2/data.yaml",
                imgsz=640,
                epochs=50,
                batch=16,
                device="cpu",
            )
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow",
                    "Trening zakończony. Wybierz runs/detect/train/weights/best.pt",
                )
            )
        except Exception as exc:  # pragma: no cover - UI feedback
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Błąd treningu: {exc}"
                ).format(exc=exc)
            )
        finally:
            self.finished.emit()


class MainWindow(QtWidgets.QMainWindow):
    """Main GUI window with controls for vision agent automation."""

    def __init__(self) -> None:
        super().__init__()
        self.scale = 1.0
        self.base_font_pt = QtWidgets.QApplication.font().pointSizeF()
        self.setWindowTitle("Metin2 Vision Agent – Panel")

        # central layout
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # left pane with controls inside a scroll area so all sections remain accessible
        left_widget = QtWidgets.QWidget()
        left = QtWidgets.QVBoxLayout(left_widget)
        left_scroll = QtWidgets.QScrollArea()
        left_scroll.setWidget(left_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(360)
        splitter.addWidget(left_scroll)

        # language selector
        self.translator = QtCore.QTranslator(self)
        lang_row = QtWidgets.QHBoxLayout()
        self.lang_label = QtWidgets.QLabel()
        self.lang_combo = QtWidgets.QComboBox()
        self.lang_combo.addItem(
            QtCore.QCoreApplication.translate("MainWindow", "Polski"), "pl"
        )
        self.lang_combo.addItem(
            QtCore.QCoreApplication.translate("MainWindow", "English"), "en"
        )
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        lang_row.addWidget(self.lang_label)
        lang_row.addWidget(self.lang_combo)
        left.addLayout(lang_row)

        # settings group
        self.settings_box = QtWidgets.QGroupBox()
        settings_form = QtWidgets.QFormLayout(self.settings_box)
        self.title_edit = QtWidgets.QLineEdit()
        self.title_edit.setPlaceholderText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Fragment tytułu okna (np. Metin2)"
            )
        )
        settings_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Tytuł okna:"),
            self.title_edit,
        )
        self.model_path = QtWidgets.QLineEdit("runs/detect/train/weights/best.pt")
        settings_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Ścieżka modelu YOLO:"),
            self.model_path,
        )
        self.classes_edit = QtWidgets.QLineEdit("metin,boss,potwory")
        settings_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Klasy obiektów:"),
            self.classes_edit,
        )
        tmpl_widget = QtWidgets.QWidget()
        tmpl_layout = QtWidgets.QHBoxLayout(tmpl_widget)
        tmpl_layout.setContentsMargins(0, 0, 0, 0)
        self.templates_dir_edit = QtWidgets.QLineEdit("assets/templates")
        self.btn_templates_dir = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Wybierz…")
        )
        tmpl_layout.addWidget(self.templates_dir_edit)
        tmpl_layout.addWidget(self.btn_templates_dir)
        self.templates_widget = tmpl_widget
        settings_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Katalog szablonów:"),
            self.templates_widget,
        )
        self.btn_templates_dir.clicked.connect(self.browse_templates_dir)
        left.addWidget(self.settings_box)

        # agent parameters group
        self.agent_box = QtWidgets.QGroupBox()
        agent_layout = QtWidgets.QVBoxLayout(self.agent_box)
        self.prio_label = QtWidgets.QLabel(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Priorytety (przeciągnij aby zmienić):"
            )
        )
        agent_layout.addWidget(self.prio_label)
        self.prio_list = QtWidgets.QListWidget()
        self.prio_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        for name in ["boss", "metin", "potwory"]:
            self.prio_list.addItem(QtWidgets.QListWidgetItem(name))
        agent_layout.addWidget(self.prio_list)
        policy_form = QtWidgets.QFormLayout()
        self.deadzone = QtWidgets.QDoubleSpinBox()
        self.deadzone.setRange(0.0, 0.5)
        self.deadzone.setSingleStep(0.01)
        self.deadzone.setValue(0.05)

        self.desired_w = QtWidgets.QDoubleSpinBox()
        self.desired_w.setRange(0.02, 1.0)
        self.desired_w.setSingleStep(0.01)
        self.desired_w.setValue(0.12)

        self.desired_w_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.desired_w_slider.setRange(2, 100)
        self.desired_w_slider.setValue(int(self.desired_w.value() * 100))
        self.desired_w_slider.valueChanged.connect(
            lambda val: self.desired_w.setValue(val / 100)
        )
        self.desired_w.valueChanged.connect(
            lambda val: self.desired_w_slider.setValue(int(val * 100))
        )
        self.desired_w_widget = QtWidgets.QWidget()
        self.desired_w_layout = QtWidgets.QHBoxLayout()
        self.desired_w_layout.setContentsMargins(0, 0, 0, 0)
        self.desired_w_layout.addWidget(self.desired_w_slider)
        self.desired_w_layout.addWidget(self.desired_w)
        self.desired_w_widget.setLayout(self.desired_w_layout)

        policy_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Deadzone X:"),
            self.deadzone,
        )
        policy_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Desired box W:"),
            self.desired_w_widget,
        )
        agent_layout.addLayout(policy_form)
        self.overlay_chk = QtWidgets.QCheckBox(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Overlay YOLO na podglądzie"
            )
        )
        self.overlay_chk.setChecked(True)
        agent_layout.addWidget(self.overlay_chk)
        self.dry_run_chk = QtWidgets.QCheckBox(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Dry run (bez klików/klawiszy)"
            )
        )
        self.dry_run_chk.setChecked(False)
        agent_layout.addWidget(self.dry_run_chk)
        self.movement_chk = QtWidgets.QCheckBox(
            QtCore.QCoreApplication.translate("MainWindow", "Movement włączony")
        )
        self.movement_chk.setChecked(True)
        agent_layout.addWidget(self.movement_chk)
        self.rotate_chk = QtWidgets.QCheckBox(
            QtCore.QCoreApplication.translate("MainWindow", "Obrót (E) włączony")
        )
        self.rotate_chk.setChecked(True)
        agent_layout.addWidget(self.rotate_chk)
        left.addWidget(self.agent_box)

        # scan parameters
        self.scan_box = QtWidgets.QGroupBox()
        scan_form = QtWidgets.QFormLayout(self.scan_box)
        self.sweeps = QtWidgets.QSpinBox()
        self.sweeps.setRange(1, 20)
        self.sweeps.setValue(8)
        self.sweep_ms = QtWidgets.QSpinBox()
        self.sweep_ms.setRange(50, 1000)
        self.sweep_ms.setValue(250)
        self.idle_sec = QtWidgets.QDoubleSpinBox()
        self.idle_sec.setRange(0.5, 5.0)
        self.idle_sec.setSingleStep(0.1)
        self.idle_sec.setValue(1.5)
        scan_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Skan sweeps:"), self.sweeps
        )
        scan_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Sweep ms:"), self.sweep_ms
        )
        scan_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Idle sec:"), self.idle_sec
        )
        left.addWidget(self.scan_box)

        # teleportation controls
        self.tp_box = QtWidgets.QGroupBox()
        tp_form = QtWidgets.QFormLayout(self.tp_box)
        self.tp_point = QtWidgets.QLineEdit()
        self.tp_point.setPlaceholderText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Nazwa punktu (OCR lub template)"
            )
        )
        self.tp_side = QtWidgets.QLineEdit()
        self.tp_side.setPlaceholderText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Strona/mapa (np. Strona I)"
            )
        )
        self.tp_minutes = QtWidgets.QSpinBox()
        self.tp_minutes.setRange(1, 180)
        self.tp_minutes.setValue(10)
        tp_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Punkt:"), self.tp_point
        )
        tp_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Strona:"), self.tp_side
        )
        tp_form.addRow(
            QtCore.QCoreApplication.translate("MainWindow", "Czas (min):"),
            self.tp_minutes,
        )
        left.addWidget(self.tp_box)

        # channels and cooldown
        self.ch_box = QtWidgets.QGroupBox()
        ch_layout = QtWidgets.QVBoxLayout(self.ch_box)
        self.ch_shortcuts_label = QtWidgets.QLabel(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Skróty kanałów (klawisze numpada):"
            )
        )
        ch_layout.addWidget(self.ch_shortcuts_label)
        self.ch_key_edits = {}
        ch_form = QtWidgets.QFormLayout()
        for i in range(1, 9):
            edit = QtWidgets.QLineEdit(f"numpad{i}")
            edit.setMaximumWidth(40)
            self.ch_key_edits[i] = edit
            ch_form.addRow(
                QtCore.QCoreApplication.translate("MainWindow", "CH{num}:").format(
                    num=i
                ),
                edit,
            )
        ch_layout.addLayout(ch_form)
        self.channel_label = QtWidgets.QLabel(
            QtCore.QCoreApplication.translate("MainWindow", "Kanał (minimapa):")
        )
        ch_layout.addWidget(self.channel_label)
        self.channel_combo = QtWidgets.QComboBox()
        self.channel_combo.addItems([f"CH{i}" for i in range(1, 9)])
        ch_layout.addWidget(self.channel_combo)
        self.cooldown_label = QtWidgets.QLabel(
            QtCore.QCoreApplication.translate("MainWindow", "Cooldown slotów (minuty):")
        )
        ch_layout.addWidget(self.cooldown_label)
        self.cooldown_spin = QtWidgets.QSpinBox()
        self.cooldown_spin.setRange(1, 60)
        self.cooldown_spin.setValue(10)
        ch_layout.addWidget(self.cooldown_spin)
        left.addWidget(self.ch_box)

        # UI scale selector
        self.scale_box = QtWidgets.QGroupBox()
        scale_layout = QtWidgets.QHBoxLayout(self.scale_box)
        self.scale_spin = QtWidgets.QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 3.0)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setDecimals(2)
        self.scale_spin.setValue(1.0)
        scale_layout.addWidget(self.scale_spin)
        left.addWidget(self.scale_box)

        # action buttons
        self.actions_box = QtWidgets.QGroupBox()
        actions_layout = QtWidgets.QVBoxLayout(self.actions_box)
        self.btn_preview = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Start podglądu")
        )
        self.btn_preview.setCheckable(True)
        self.btn_record = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Nagrywaj dane (5 min)")
        )
        self.btn_record.setCheckable(True)
        self.btn_agent = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Start agenta (YOLO + WASD)"
            )
        )
        self.btn_agent.setCheckable(True)
        self.btn_tp_hunt = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Teleportuj i poluj")
        )
        self.btn_tp_hunt.setCheckable(True)
        self.btn_cycle = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Cykl 8×8 (sloty×kanały)")
        )
        self.btn_cycle.setCheckable(True)
        self.btn_ch = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Zmień kanał")
        )
        self.btn_ch.setCheckable(True)
        self.btn_stop = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "STOP (F12)")
        )
        self.btn_train = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Trenuj YOLO")
        )
        self.btn_train.setCheckable(True)
        for b in [
            self.btn_preview,
            self.btn_record,
            self.btn_agent,
            self.btn_tp_hunt,
            self.btn_cycle,
            self.btn_ch,
            self.btn_stop,
            self.btn_train,
        ]:
            actions_layout.addWidget(b)

        # optional custom cycle sequence table
        self.seq_table = QtWidgets.QTableWidget(0, 2)
        self.seq_table.setHorizontalHeaderLabels(
            [
                QtCore.QCoreApplication.translate("MainWindow", "CH"),
                QtCore.QCoreApplication.translate("MainWindow", "Slot"),
            ]
        )
        self.seq_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.seq_add_btn = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Dodaj krok")
        )
        self.seq_remove_btn = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Usuń krok")
        )
        seq_btns = QtWidgets.QHBoxLayout()
        seq_btns.addWidget(self.seq_add_btn)
        seq_btns.addWidget(self.seq_remove_btn)
        self.seq_box = QtWidgets.QGroupBox()
        seq_layout = QtWidgets.QVBoxLayout(self.seq_box)
        self.seq_help = QtWidgets.QLabel(
            QtCore.QCoreApplication.translate(
                "MainWindow",
                "Opcjonalna lista kanałów i slotów; puste = domyślny cykl 8×8.",
            )
        )
        self.seq_help.setWordWrap(True)
        self.seq_help.setToolTip(
            QtCore.QCoreApplication.translate(
                "MainWindow",
                "Każdy wiersz określa kanał (1-8) i slot (1-8) odwiedzany kolejno.",
            )
        )
        self.seq_box.setToolTip(
            QtCore.QCoreApplication.translate(
                "MainWindow",
                "Ustal kolejność kanałów i slotów. Pozostaw puste dla domyślnego 8×8.",
            )
        )
        seq_layout.addWidget(self.seq_help)
        seq_layout.addWidget(self.seq_table)
        seq_layout.addLayout(seq_btns)
        actions_layout.insertWidget(actions_layout.indexOf(self.btn_ch), self.seq_box)
        self.seq_add_btn.clicked.connect(self.add_seq_row)
        self.seq_remove_btn.clicked.connect(self.remove_seq_row)

        self.btn_tp_cfg = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Konfiguracja teleportu")
        )
        actions_layout.addWidget(self.btn_tp_cfg)
        self.btn_tp_cfg.clicked.connect(self.open_teleport_config)
        self.btn_save_cfg = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Zapisz konfigurację")
        )
        self.btn_load_cfg = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Wczytaj konfigurację")
        )
        actions_layout.addWidget(self.btn_save_cfg)
        actions_layout.addWidget(self.btn_load_cfg)
        left.addWidget(self.actions_box)

        # logs
        self.log_box = QtWidgets.QGroupBox()
        log_layout = QtWidgets.QVBoxLayout(self.log_box)
        log_lvl_layout = QtWidgets.QHBoxLayout()
        self.log_level_label = QtWidgets.QLabel(
            QtCore.QCoreApplication.translate("MainWindow", "Poziom:")
        )
        log_lvl_layout.addWidget(self.log_level_label)
        self.log_level_combo = QtWidgets.QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO"])
        log_lvl_layout.addWidget(self.log_level_combo)
        log_layout.addLayout(log_lvl_layout)
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3)
        self.log_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        log_layout.addWidget(self.log_view)
        left.addWidget(self.log_box)

        left.addStretch(1)
        self.status_label = QtWidgets.QLabel(
            QtCore.QCoreApplication.translate("MainWindow", "Gotowy.")
        )
        self.status_label.setWordWrap(True)
        left.addWidget(self.status_label)

        # video preview on the right
        self.video = QtWidgets.QLabel()
        self.video.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.video.setMinimumSize(320, 180)
        self.video.setStyleSheet("background:#222; border:1px solid #444")
        self.video.setAlignment(QtCore.Qt.AlignCenter)
        self.video.setFocusPolicy(QtCore.Qt.NoFocus)
        splitter.addWidget(self.video)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        # thread references
        self.preview_thread: PreviewWorker | None = None
        self.agent_thread: QtCore.QThread | None = None
        self.record_thread: QtCore.QThread | None = None
        self.channel_thread: QtCore.QThread | None = None
        self.train_thread: QtCore.QThread | None = None
        self._hotkey_listener = None

        # connections
        self.btn_preview.toggled.connect(self.toggle_preview)
        self.btn_record.toggled.connect(self.record_data)
        self.btn_agent.toggled.connect(self.start_agent)
        self.btn_tp_hunt.toggled.connect(self.start_tp_and_hunt)
        self.btn_cycle.toggled.connect(self.start_cycle)
        self.btn_ch.toggled.connect(self.change_channel)
        self.btn_stop.clicked.connect(self.stop_all)
        self.btn_train.toggled.connect(self.train_yolo_api)
        self.btn_save_cfg.clicked.connect(self.save_config)
        self.btn_load_cfg.clicked.connect(self.load_config)
        self.scale_spin.valueChanged.connect(self.apply_scale)
        # hotkey F12
        self.start_hotkey_listener()

        # logging setup
        self.log_handler = QtLogHandler()
        self.log_handler.log.connect(self.log_view.appendPlainText)
        self.logger = logging.getLogger()
        self.logger.addHandler(self.log_handler)
        self.log_level_combo.currentTextChanged.connect(
            lambda lvl: self.logger.setLevel(getattr(logging, lvl))
        )

        # restore persistent settings
        self.settings = QSettings("METIIN-AI", "MainWindow")
        geometry = self.settings.value("window/geometry", b"", type=QtCore.QByteArray)
        if geometry:
            self.restoreGeometry(geometry)
        self.title_edit.setText(self.settings.value("window/title", ""))
        self.model_path.setText(
            self.settings.value("paths/model", self.model_path.text())
        )
        self.templates_dir_edit.setText(
            self.settings.value("paths/templates_dir", self.templates_dir_edit.text())
        )
        scale = float(self.settings.value("ui/scale", self.scale))
        self.scale_spin.setValue(scale)
        self.apply_scale(scale)

        self.retranslate_ui()

    # ---------- helpers ----------
    def change_language(self, idx: int) -> None:
        lang = self.lang_combo.itemData(idx)
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        app.removeTranslator(self.translator)
        if lang and lang != "pl":
            path = os.path.join(os.path.dirname(__file__), "i18n", f"{lang}.qm")
            if self.translator.load(path):
                app.installTranslator(self.translator)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Metin2 Vision Agent – Panel"
            )
        )
        self.lang_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Język:")
        )
        self.lang_combo.setItemText(
            0, QtCore.QCoreApplication.translate("MainWindow", "Polski")
        )
        self.lang_combo.setItemText(
            1, QtCore.QCoreApplication.translate("MainWindow", "English")
        )

        # settings
        self.settings_box.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Ustawienia")
        )
        settings_form = self.settings_box.layout()
        if isinstance(settings_form, QtWidgets.QFormLayout):
            settings_form.labelForField(self.title_edit).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Tytuł okna:")
            )
            settings_form.labelForField(self.model_path).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Ścieżka modelu YOLO:")
            )
            settings_form.labelForField(self.classes_edit).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Klasy obiektów:")
            )
            settings_form.labelForField(self.templates_widget).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Katalog szablonów:")
            )
        self.title_edit.setPlaceholderText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Fragment tytułu okna (np. Metin2)"
            )
        )

        # agent box
        self.agent_box.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Parametry agenta")
        )
        policy_form = self.agent_box.findChild(QtWidgets.QFormLayout)
        if policy_form:
            label = policy_form.labelForField(self.deadzone)
            if label:
                label.setText(
                    QtCore.QCoreApplication.translate("MainWindow", "Deadzone X:")
                )
            label = policy_form.labelForField(self.desired_w_widget)
            if label:
                label.setText(
                    QtCore.QCoreApplication.translate("MainWindow", "Desired box W:")
                )
        self.prio_label.setText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Priorytety (przeciągnij aby zmienić):"
            )
        )
        self.overlay_chk.setText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Overlay YOLO na podglądzie"
            )
        )
        self.dry_run_chk.setText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Dry run (bez klików/klawiszy)"
            )
        )
        self.movement_chk.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Movement włączony")
        )
        self.rotate_chk.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Obrót (E) włączony")
        )

        # scan box
        self.scan_box.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Parametry skanu (obrót E)")
        )
        scan_form = self.scan_box.findChild(QtWidgets.QFormLayout)
        if scan_form:
            scan_form.labelForField(self.sweeps).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Skan sweeps:")
            )
            scan_form.labelForField(self.sweep_ms).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Sweep ms:")
            )
            scan_form.labelForField(self.idle_sec).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Idle sec:")
            )

        # teleport box
        self.tp_box.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Teleportacja")
        )
        tp_form = self.tp_box.findChild(QtWidgets.QFormLayout)
        if tp_form:
            tp_form.labelForField(self.tp_point).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Punkt:")
            )
            tp_form.labelForField(self.tp_side).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Strona:")
            )
            tp_form.labelForField(self.tp_minutes).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Czas (min):")
            )
        self.tp_point.setPlaceholderText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Nazwa punktu (OCR lub template)"
            )
        )
        self.tp_side.setPlaceholderText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Strona/mapa (np. Strona I)"
            )
        )

        # channels box
        self.ch_box.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Kanały i cooldown")
        )
        self.ch_shortcuts_label.setText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Skróty kanałów (klawisze numpada):"
            )
        )
        for i in range(1, 9):
            label = self.ch_box.findChild(QtWidgets.QFormLayout).labelForField(
                self.ch_key_edits[i]
            )
            label.setText(
                QtCore.QCoreApplication.translate("MainWindow", "CH{num}:").format(
                    num=i
                )
            )
        self.channel_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Kanał (minimapa):")
        )
        self.cooldown_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Cooldown slotów (minuty):")
        )

        # scale box
        self.scale_box.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Skala UI")
        )

        # actions box
        self.actions_box.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Akcje")
        )
        self.btn_preview.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Start podglądu")
        )
        self.btn_record.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Nagrywaj dane (5 min)")
        )
        self.btn_agent.setText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Start agenta (YOLO + WASD)"
            )
        )
        self.btn_tp_hunt.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Teleportuj i poluj")
        )
        self.btn_cycle.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Cykl 8×8 (sloty×kanały)")
        )
        self.btn_ch.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Zmień kanał")
        )
        self.btn_stop.setText(
            QtCore.QCoreApplication.translate("MainWindow", "STOP (F12)")
        )
        self.btn_train.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Trenuj YOLO")
        )
        self.seq_box.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Sekwencja cyklu")
        )
        self.seq_help.setText(
            QtCore.QCoreApplication.translate(
                "MainWindow",
                "Opcjonalna lista kanałów i slotów; puste = domyślny cykl 8×8.",
            )
        )
        self.seq_help.setToolTip(
            QtCore.QCoreApplication.translate(
                "MainWindow",
                "Każdy wiersz określa kanał (1-8) i slot (1-8) odwiedzany kolejno.",
            )
        )
        self.seq_box.setToolTip(
            QtCore.QCoreApplication.translate(
                "MainWindow",
                "Ustal kolejność kanałów i slotów. Pozostaw puste dla domyślnego 8×8.",
            )
        )
        self.seq_add_btn.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Dodaj krok")
        )
        self.seq_remove_btn.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Usuń krok")
        )
        self.seq_table.setHorizontalHeaderLabels(
            [
                QtCore.QCoreApplication.translate("MainWindow", "CH"),
                QtCore.QCoreApplication.translate("MainWindow", "Slot"),
            ]
        )
        self.btn_tp_cfg.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Konfiguracja teleportu")
        )
        self.btn_save_cfg.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Zapisz konfigurację")
        )
        self.btn_load_cfg.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Wczytaj konfigurację")
        )

        # logs and status
        self.log_box.setTitle(QtCore.QCoreApplication.translate("MainWindow", "Logi"))
        self.log_level_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Poziom:")
        )
        self.status_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Gotowy.")
        )

    def current_priority(self) -> list[str]:
        return [self.prio_list.item(i).text() for i in range(self.prio_list.count())]

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        logging.info(text)

    def apply_scale(self, scale: float) -> None:
        """Apply global font scaling and adjust widgets accordingly."""
        self.scale = scale
        font = QtGui.QFont()
        font.setPointSizeF(self.base_font_pt * scale)
        QtWidgets.QApplication.setFont(font)
        # Ensure log view shows exactly three lines at the current scale
        metrics = QtGui.QFontMetrics(font)
        self.log_view.setFixedHeight(int(metrics.lineSpacing() * 4))

    def add_seq_row(self) -> None:
        """Append an empty step to the cycle sequence table."""
        self.seq_table.insertRow(self.seq_table.rowCount())

    def remove_seq_row(self) -> None:
        """Remove the currently selected step from the sequence table."""
        row = self.seq_table.currentRow()
        if row >= 0:
            self.seq_table.removeRow(row)

    def browse_templates_dir(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            QtCore.QCoreApplication.translate(
                "MainWindow", "Wybierz katalog z szablonami"
            ),
            self.templates_dir_edit.text(),
        )
        if path:
            self.templates_dir_edit.setText(path)

    def open_teleport_config(self) -> None:
        dlg = TeleportConfigDialog(self)
        dlg.exec()

    def show_frame(self, frame: np.ndarray) -> None:
        """Display a frame in the video QLabel."""
        if not frame.flags["C_CONTIGUOUS"]:
            frame = np.ascontiguousarray(frame)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        bytes_per_line = rgb.strides[0]
        qimg = QtGui.QImage(
            rgb.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888
        )
        pix = QtGui.QPixmap.fromImage(qimg).scaled(
            self.video.width(), self.video.height(), QtCore.Qt.KeepAspectRatio
        )
        self.video.setPixmap(pix)

    # ---------- preview ----------
    def toggle_preview(self, checked: bool) -> None:
        if not checked:
            if self.preview_thread and self.preview_thread.isRunning():
                self.preview_thread.stop()
                self.preview_thread.wait()
                self.preview_thread = None
            self.btn_preview.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Start podglądu")
            )
            self.set_status(
                QtCore.QCoreApplication.translate("MainWindow", "Podgląd zatrzymany.")
            )
            return
        title = self.title_edit.text().strip()
        if not title:
            self.set_status(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Podaj fragment tytułu okna."
                )
            )
            self.btn_preview.setChecked(False)
            return
        # start preview
        self.preview_thread = PreviewWorker(title)
        self.preview_thread.frame_ready.connect(self.show_frame)
        self.preview_thread.status.connect(self.set_status)
        self.preview_thread.error.connect(self.set_status)
        classes = [c.strip() for c in self.classes_edit.text().split(",") if c.strip()]
        self.preview_thread.configure_overlay(
            self.model_path.text().strip(), classes, self.overlay_chk.isChecked()
        )
        self.preview_thread.start()
        self.btn_preview.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Stop podglądu")
        )

    # ---------- recording ----------
    def record_data(self, checked: bool) -> None:
        if not checked:
            self.btn_record.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Nagrywaj dane (5 min)")
            )
            return
        title = self.title_edit.text().strip()
        if not title:
            self.set_status(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Podaj fragment tytułu okna."
                )
            )
            self.btn_record.setChecked(False)
            return
        with WindowCapture(title) as wc:
            if not wc.locate(timeout=5):
                self.set_status(
                    QtCore.QCoreApplication.translate(
                        "MainWindow", "Nie znaleziono okna."
                    )
                )
                self.btn_record.setChecked(False)
                return
            wc.update_region()
            l, t, w, h = wc.region

        self.record_thread = RecordThread((l, t, w, h))
        self.record_thread.status.connect(self.set_status)
        self.record_thread.finished.connect(lambda: self.btn_record.setChecked(False))
        self.record_thread.finished.connect(
            lambda: self.btn_record.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Nagrywaj dane (5 min)")
            )
        )
        self.record_thread.start()
        self.btn_record.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Nagrywam dane (5 min)")
        )

    # ---------- configuration ----------
    def build_cfg(self) -> dict:
        title = self.title_edit.text().strip()
        classes = [c.strip() for c in self.classes_edit.text().split(",") if c.strip()]
        prio = self.current_priority()
        hotkeys = {
            i: self.ch_key_edits[i].text().strip() or f"numpad{i}"
            for i in range(1, 9)
        }
        cfg = {
            "window": {"title_substr": title},
            "paths": {
                "templates_dir": self.templates_dir_edit.text().strip(),
                "model": self.model_path.text().strip(),
            },
            "controls": {
                "keys": {
                    "forward": "w",
                    "left": "a",
                    "back": "s",
                    "right": "d",
                    "rotate": "e",
                },
                "movement": self.movement_chk.isChecked(),
                "key_repeat_ms": 60,
                "mouse_pause": 0.02,
            },
            "detector": {
                "classes": classes,
                "conf_thr": 0.5,
                "iou_thr": 0.45,
            },
            "policy": {
                "deadzone_x": float(self.deadzone.value()),
                "desired_box_w": float(self.desired_w_slider.value() / 100),
            },
            "stuck": {
                "flow_window": 0.8,
                "min_flow_mag": 0.7,
                "rotate_ms_on_stuck": 250,
            },
            "priority": prio,
            "dry_run": self.dry_run_chk.isChecked(),
            "scan": {
                "enabled": self.rotate_chk.isChecked(),
                "key": "e",
                "sweeps": int(self.sweeps.value()),
                "sweep_ms": int(self.sweep_ms.value()),
                "idle_sec": float(self.idle_sec.value()),
                "period": 0.066,
                "pause": 0.12,
            },
            "cooldowns": {"slot_min": int(self.cooldown_spin.value())},
            "channel": {
                "settle_sec": 5.0,
                "timeout_per_ch": 2.5,
                "hotkeys": hotkeys,
            },
            "ui": {"scale": float(self.scale_spin.value())},
        }

        sequence: list[dict[str, int]] = []
        for row in range(self.seq_table.rowCount()):
            ch_item = self.seq_table.item(row, 0)
            slot_item = self.seq_table.item(row, 1)
            if not ch_item or not slot_item:
                continue
            try:
                ch = int(ch_item.text())
                slot = int(slot_item.text())
            except ValueError:
                continue
            if 1 <= ch <= 8 and 1 <= slot <= 8:
                sequence.append({"ch": ch, "slot": slot})

        if sequence:
            cfg["cycle"] = {"sequence": sequence}
        return cfg

    def save_config(self) -> None:
        cfg = self.build_cfg()
        cfg["teleport"] = {
            "point": self.tp_point.text().strip(),
            "side": self.tp_side.text().strip(),
            "minutes": int(self.tp_minutes.value()),
        }
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Zapisz konfigurację", "config.json", "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
                self.set_status("Zapisano konfigurację.")
            except Exception as exc:
                self.set_status(f"Błąd zapisu: {exc}")

    def load_config(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Wczytaj konfigurację", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as exc:
            self.set_status(f"Błąd wczytywania: {exc}")
            return
        self.title_edit.setText(cfg.get("window", {}).get("title_substr", ""))
        det = cfg.get("detector", {})
        paths = cfg.get("paths", {})
        self.model_path.setText(paths.get("model", ""))
        self.classes_edit.setText(",".join(det.get("classes", [])))
        self.deadzone.setValue(float(cfg.get("policy", {}).get("deadzone_x", 0.05)))
        self.desired_w.setValue(float(cfg.get("policy", {}).get("desired_box_w", 0.12)))
        self.desired_w_slider.setValue(int(self.desired_w.value() * 100))
        self.dry_run_chk.setChecked(bool(cfg.get("dry_run", False)))
        self.movement_chk.setChecked(
            bool(cfg.get("controls", {}).get("movement", True))
        )
        scan = cfg.get("scan", {})
        self.rotate_chk.setChecked(bool(scan.get("enabled", True)))
        self.sweeps.setValue(int(scan.get("sweeps", 8)))
        self.sweep_ms.setValue(int(scan.get("sweep_ms", 250)))
        self.idle_sec.setValue(float(scan.get("idle_sec", 1.5)))
        self.cooldown_spin.setValue(int(cfg.get("cooldowns", {}).get("slot_min", 10)))
        self.templates_dir_edit.setText(paths.get("templates_dir", "assets/templates"))
        ui = cfg.get("ui", {})
        scale = float(ui.get("scale", 1.0))
        self.scale_spin.setValue(scale)
        self.apply_scale(scale)
        self.prio_list.clear()
        for name in cfg.get("priority", []):
            self.prio_list.addItem(QtWidgets.QListWidgetItem(name))
        tp = cfg.get("teleport", {})
        self.tp_point.setText(tp.get("point", ""))
        self.tp_side.setText(tp.get("side", ""))
        self.tp_minutes.setValue(int(tp.get("minutes", 10)))
        ch_hot = cfg.get("channel", {}).get("hotkeys", {})
        for i in range(1, 9):
            key = ch_hot.get(str(i)) or ch_hot.get(i) or f"numpad{i}"
            self.ch_key_edits[i].setText(key)

        seq = cfg.get("cycle", {}).get("sequence", [])
        self.seq_table.setRowCount(0)
        for step in seq:
            row = self.seq_table.rowCount()
            self.seq_table.insertRow(row)
            ch = step.get("ch")
            slot = step.get("slot")
            self.seq_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(ch)))
            self.seq_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(slot)))
        self.set_status("Wczytano konfigurację.")

    # ---------- agent actions ----------
    def start_agent(self, checked: bool) -> None:
        if not checked:
            if self.agent_thread:
                self.agent_thread.stop()
                self.agent_thread.wait()
                self.agent_thread = None
            self.btn_agent.setText("Start agenta (YOLO + WASD)")
            self.set_status("Agent zatrzymany.")
            return
        cfg = self.build_cfg()
        self.agent_thread = AgentThread(cfg)
        self.agent_thread.status.connect(self.set_status)
        self.agent_thread.finished.connect(lambda: self.btn_agent.setChecked(False))
        self.agent_thread.finished.connect(
            lambda: self.btn_agent.setText("Start agenta (YOLO + WASD)")
        )
        self.agent_thread.start()
        self.btn_agent.setText("Stop agenta")
        self.set_status("Agent YOLO+WASD uruchomiony.")

    def start_tp_and_hunt(self, checked: bool) -> None:
        if not checked:
            if self.agent_thread:
                self.agent_thread.stop()
                self.agent_thread.wait()
                self.agent_thread = None
            self.btn_tp_hunt.setText("Teleportuj i poluj")
            self.set_status("Przerwano 'Teleportuj i poluj'.")
            return
        point = self.tp_point.text().strip()
        side = self.tp_side.text().strip()
        minutes = int(self.tp_minutes.value())
        if not point or not side:
            self.set_status("Uzupełnij punkt i stronę teleportacji.")
            self.btn_tp_hunt.setChecked(False)
            return
        cfg = self.build_cfg()

        self.agent_thread = TeleportHuntThread(cfg, point, side, minutes)
        self.agent_thread.status.connect(self.set_status)
        self.agent_thread.finished.connect(lambda: self.btn_tp_hunt.setChecked(False))
        self.agent_thread.finished.connect(
            lambda: self.btn_tp_hunt.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Teleportuj i poluj")
            )
        )
        self.agent_thread.start()
        self.btn_tp_hunt.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Stop 'Teleportuj i poluj'")
        )
        self.set_status(
            QtCore.QCoreApplication.translate("MainWindow", "Teleportuję i poluję…")
        )

    def start_cycle(self, checked: bool) -> None:
        if not checked:
            if self.agent_thread:
                self.agent_thread.stop()
                self.agent_thread.wait()
                self.agent_thread = None
            self.btn_cycle.setText(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Cykl 8×8 (sloty×kanały)"
                )
            )
            self.set_status(
                QtCore.QCoreApplication.translate("MainWindow", "Cykl zatrzymany.")
            )
            return
        page = self.tp_side.text().strip() or None
        cfg = self.build_cfg()
        self.agent_thread = CycleThread(cfg, page)
        self.agent_thread.status.connect(self.set_status)
        self.agent_thread.finished.connect(lambda: self.btn_cycle.setChecked(False))
        self.agent_thread.finished.connect(
            lambda: self.btn_cycle.setText(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Cykl 8×8 (sloty×kanały)"
                )
            )
        )
        self.agent_thread.start()
        self.btn_cycle.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Stop cyklu 8×8")
        )
        self.set_status(
            QtCore.QCoreApplication.translate("MainWindow", "Start cyklu 8×8…")
        )

    def change_channel(self, checked: bool) -> None:
        if not checked:
            self.btn_ch.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Zmień kanał")
            )
            return
        cfg = self.build_cfg()
        ch = int(self.channel_combo.currentText().replace("CH", ""))
        self.channel_thread = ChannelThread(cfg, ch)
        self.channel_thread.status.connect(self.set_status)
        self.channel_thread.finished.connect(lambda: self.btn_ch.setChecked(False))
        self.channel_thread.finished.connect(
            lambda: self.btn_ch.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Zmień kanał")
            )
        )
        self.channel_thread.start()
        self.btn_ch.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Zmiana kanału…")
        )
        self.set_status(
            QtCore.QCoreApplication.translate("MainWindow", "Zmiana kanału…")
        )

    def stop_all(self) -> None:
        try:
            KeyHold().release_all()
        except Exception:
            pass
        if self.agent_thread and self.agent_thread.isRunning():
            try:
                self.agent_thread.stop()
            except Exception:
                pass
            self.agent_thread.wait()
            self.agent_thread = None
        if self.record_thread and self.record_thread.isRunning():
            self.record_thread.wait()
            self.record_thread = None
        if self.channel_thread and self.channel_thread.isRunning():
            self.channel_thread.wait()
            self.channel_thread = None
        if self.train_thread and self.train_thread.isRunning():
            self.train_thread.wait()
            self.train_thread = None
        if self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.stop()
            self.preview_thread.wait()
            self.preview_thread = None
        for b in [
            self.btn_preview,
            self.btn_record,
            self.btn_agent,
            self.btn_tp_hunt,
            self.btn_cycle,
            self.btn_ch,
            self.btn_train,
        ]:
            b.setChecked(False)
        self.set_status(
            QtCore.QCoreApplication.translate(
                "MainWindow", "STOP – wszystkie klawisze zwolnione."
            )
        )

    def train_yolo_api(self, checked: bool) -> None:
        """Train YOLO using ultralytics API (runs asynchronously)."""
        if not checked:
            self.btn_train.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Trenuj YOLO")
            )
            return
        self.train_thread = TrainThread()
        self.train_thread.status.connect(self.set_status)
        self.train_thread.finished.connect(lambda: self.btn_train.setChecked(False))
        self.train_thread.finished.connect(
            lambda: self.btn_train.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Trenuj YOLO")
            )
        )
        self.train_thread.start()
        self.btn_train.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Trwa trening…")
        )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pragma: no cover
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/title", self.title_edit.text())
        self.settings.setValue("paths/model", self.model_path.text())
        self.settings.setValue("paths/templates_dir", self.templates_dir_edit.text())
        self.settings.setValue("ui/scale", self.scale_spin.value())
        self.settings.sync()
        super().closeEvent(event)

    # ---------- hotkey ----------
    def start_hotkey_listener(self) -> None:
        def on_press(key):
            try:
                if key == pynput_keyboard.Key.f12:
                    self.stop_all()
            except Exception:
                pass

        self._hotkey_listener = pynput_keyboard.Listener(on_press=on_press)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()
