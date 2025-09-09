"""Main application window for the Metin2 vision agent GUI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

import cv2
import numpy as np
import pyautogui
from pynput import keyboard as pynput_keyboard
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QSettings

from agent.channel import ChannelSwitcher
from agent.cycle import CycleFarm
from agent.strategy import load_strategy
from agent.wasd import KeyHold
from gui.preview import PreviewWorker
from gui.teleport_config_dialog import TeleportConfigDialog
from gui.widgets import AgentPanel, ScanPanel, SettingsPanel
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


class RLTrainThread(QtCore.QThread):
    """Thread executing RL training with ``stable-baselines3``."""

    status = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, timesteps: int = 10000, algo: str = "dqn") -> None:
        super().__init__()
        self.timesteps = timesteps
        self.algo = algo

    def run(self) -> None:  # pragma: no cover - GUI thread
        env = None
        tb_proc = None
        try:
            self.status.emit(
                QtCore.QCoreApplication.translate("MainWindow", "Trening RL – start…")
            )
            import shutil
            import subprocess
            import webbrowser
            from datetime import datetime
            from pathlib import Path

            from stable_baselines3 import A2C, DQN, PPO

            from agent_rl import Metin2Env

            algos = {"dqn": DQN, "ppo": PPO, "a2c": A2C}
            algo_cls = algos.get(self.algo)
            if algo_cls is None:
                self.status.emit(
                    QtCore.QCoreApplication.translate(
                        "MainWindow", "Nieznany algorytm RL"
                    )
                )
                return

            run_dir = Path("runs/rl") / f"{self.algo}_{datetime.now():%Y%m%d_%H%M%S}"
            run_dir.mkdir(parents=True, exist_ok=True)

            if shutil.which("tensorboard"):
                tb_proc = subprocess.Popen(["tensorboard", "--logdir", str(run_dir)])
                try:
                    time.sleep(5)  # wait for TensorBoard to initialize
                    webbrowser.open("http://localhost:6006")
                except Exception:
                    pass

            env = Metin2Env()
            model = algo_cls("CnnPolicy", env, tensorboard_log=str(run_dir))
            model.learn(total_timesteps=self.timesteps)
            model.save(str(run_dir / "metin2_rl_agent"))
            self.status.emit(
                QtCore.QCoreApplication.translate("MainWindow", "Zakończono trening RL")
            )
        except Exception as exc:  # pragma: no cover - UI feedback
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Błąd treningu RL: {exc}"
                ).format(exc=exc)
            )
        finally:
            if tb_proc is not None:
                try:
                    tb_proc.terminate()
                except Exception:
                    pass
            if env is not None:
                try:
                    env.close()
                except Exception:
                    pass
            self.finished.emit()


class RLAgentThread(QtCore.QThread):
    """Thread executing a trained RL policy in the environment."""

    status = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, model_path: str) -> None:
        super().__init__()
        self.model_path = model_path
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:  # pragma: no cover - GUI thread
        env = None
        try:
            from stable_baselines3 import DQN

            from agent_rl import Metin2Env

            self.status.emit(
                QtCore.QCoreApplication.translate("MainWindow", "Start RL agent…")
            )
            env = Metin2Env(dry=False)
            model = DQN.load(self.model_path)
            obs, _ = env.reset()
            while not self._stop:
                action, _state = model.predict(obs)
                obs, _, terminated, truncated, _ = env.step(int(action))
                if terminated or truncated:
                    obs, _ = env.reset()
            self.status.emit(
                QtCore.QCoreApplication.translate("MainWindow", "RL agent zatrzymany.")
            )
        except Exception as exc:  # pragma: no cover - UI feedback
            self.status.emit(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Błąd RL: {exc}"
                ).format(exc=exc)
            )
        finally:
            if env is not None:
                try:
                    env.close()
                except Exception:
                    pass
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
        self.settings_panel = SettingsPanel()
        left.addWidget(self.settings_panel)
        # expose sub-widgets for backward compatibility
        self.title_edit = self.settings_panel.title_edit
        self.model_path = self.settings_panel.model_path
        self.rl_model_path = self.settings_panel.rl_model_path
        self.classes_edit = self.settings_panel.classes_edit
        self.templates_dir_edit = self.settings_panel.templates_dir_edit

        # agent parameters group
        self.agent_panel = AgentPanel()
        left.addWidget(self.agent_panel)
        self.prio_list = self.agent_panel.prio_list
        self.deadzone = self.agent_panel.deadzone
        self.desired_w = self.agent_panel.desired_w
        self.desired_w_slider = self.agent_panel.desired_w_slider
        self.desired_w_widget = self.agent_panel.desired_w_widget
        self.overlay_chk = self.agent_panel.overlay_chk
        self.dry_run_chk = self.agent_panel.dry_run_chk
        self.movement_chk = self.agent_panel.movement_chk
        self.rotate_chk = self.agent_panel.rotate_chk

        # scan parameters
        self.scan_panel = ScanPanel()
        left.addWidget(self.scan_panel)
        self.sweeps = self.scan_panel.sweeps
        self.sweep_ms = self.scan_panel.sweep_ms
        self.idle_sec = self.scan_panel.idle_sec

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
        self.btn_hunt = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Start polowania")
        )
        self.btn_hunt.setCheckable(True)
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
        self.btn_run_rl = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Start RL")
        )
        self.btn_run_rl.setCheckable(True)
        self.btn_train_rl = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Trenuj RL")
        )
        self.btn_train_rl.setCheckable(True)
        self.btn_train = QtWidgets.QPushButton(
            QtCore.QCoreApplication.translate("MainWindow", "Trenuj YOLO")
        )
        self.btn_train.setCheckable(True)
        for b in [
            self.btn_preview,
            self.btn_record,
            self.btn_agent,
            self.btn_hunt,
            self.btn_cycle,
            self.btn_ch,
            self.btn_stop,
            self.btn_run_rl,
            self.btn_train_rl,
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
        self.rl_thread: QtCore.QThread | None = None
        self.rl_agent_thread: QtCore.QThread | None = None
        self._hotkey_listener = None

        # connections
        self.btn_preview.toggled.connect(self.toggle_preview)
        self.btn_record.toggled.connect(self.record_data)
        self.btn_agent.toggled.connect(self.start_agent)
        self.btn_hunt.toggled.connect(self.start_hunt)
        self.btn_cycle.toggled.connect(self.start_cycle)
        self.btn_ch.toggled.connect(self.change_channel)
        self.btn_stop.clicked.connect(self.stop_all)
        self.btn_train_rl.toggled.connect(self.train_rl_agent)
        self.btn_run_rl.toggled.connect(self.run_rl_agent)
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
        self.rl_model_path.setText(
            self.settings.value("paths/rl_model", self.rl_model_path.text())
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

        # settings and agent sections handled by dedicated widgets
        self.settings_panel.retranslate_ui()
        self.agent_panel.retranslate_ui()
        self.scan_panel.retranslate_ui()

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
        self.btn_hunt.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Start polowania")
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
        self.btn_run_rl.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Start RL")
        )
        self.btn_train_rl.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Trenuj RL")
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
        cfg = {}
        cfg.update(self.settings_panel.get_config())
        cfg.update(self.agent_panel.get_config())
        cfg.update(self.scan_panel.get_config(self.rotate_chk.isChecked()))
        hotkeys = {
            i: self.ch_key_edits[i].text().strip() or f"numpad{i}" for i in range(1, 9)
        }
        cfg.update(
            {
                "stuck": {
                    "flow_window": 0.8,
                    "min_flow_mag": 0.7,
                    "rotate_ms_on_stuck": 250,
                },
                "cooldowns": {"slot_min": int(self.cooldown_spin.value())},
                "channel": {
                    "settle_sec": 5.0,
                    "timeout_per_ch": 2.5,
                    "hotkeys": hotkeys,
                },
                "ui": {"scale": float(self.scale_spin.value())},
            }
        )

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
        cfg = self.build_cfg()
        self.agent_thread = CycleThread(cfg, None)
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

    def start_hunt(self, checked: bool) -> None:
        if checked:
            try:
                if not self.btn_preview.isChecked():
                    self.btn_preview.setChecked(True)
                if not self.btn_agent.isChecked():
                    self.btn_agent.setChecked(True)
                if not self.btn_cycle.isChecked():
                    self.btn_cycle.setChecked(True)
                self.btn_hunt.setText(
                    QtCore.QCoreApplication.translate(
                        "MainWindow", "Stop polowania"
                    )
                )
            except Exception:
                self.btn_hunt.setChecked(False)
                self.stop_all()
        else:
            self.stop_all()
            self.btn_hunt.setText(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Start polowania"
                )
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
        if self.rl_thread and self.rl_thread.isRunning():
            self.rl_thread.wait()
            self.rl_thread = None
        if self.rl_agent_thread and self.rl_agent_thread.isRunning():
            try:
                self.rl_agent_thread.stop()
            except Exception:
                pass
            self.rl_agent_thread.wait()
            self.rl_agent_thread = None
        if self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.stop()
            self.preview_thread.wait()
            self.preview_thread = None
        for b in [
            self.btn_preview,
            self.btn_record,
            self.btn_agent,
            self.btn_hunt,
            self.btn_cycle,
            self.btn_ch,
            self.btn_run_rl,
            self.btn_train,
            self.btn_train_rl,
        ]:
            b.setChecked(False)
        self.set_status(
            QtCore.QCoreApplication.translate(
                "MainWindow", "STOP – wszystkie klawisze zwolnione."
            )
        )

    def run_rl_agent(self, checked: bool) -> None:
        if not checked:
            if self.rl_agent_thread:
                try:
                    self.rl_agent_thread.stop()
                except Exception:
                    pass
                self.rl_agent_thread.wait()
                self.rl_agent_thread = None
            self.btn_run_rl.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Start RL")
            )
            self.set_status(
                QtCore.QCoreApplication.translate("MainWindow", "Agent RL zatrzymany.")
            )
            return
        model_path = self.rl_model_path.text().strip()
        if not model_path:
            self.set_status(
                QtCore.QCoreApplication.translate(
                    "MainWindow", "Podaj ścieżkę modelu RL."
                )
            )
            self.btn_run_rl.setChecked(False)
            return
        self.rl_agent_thread = RLAgentThread(model_path)
        self.rl_agent_thread.status.connect(self.set_status)
        self.rl_agent_thread.finished.connect(lambda: self.btn_run_rl.setChecked(False))
        self.rl_agent_thread.finished.connect(
            lambda: self.btn_run_rl.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Start RL")
            )
        )
        self.rl_agent_thread.finished.connect(
            lambda: setattr(self, "rl_agent_thread", None)
        )
        self.rl_agent_thread.start()
        self.btn_run_rl.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Stop RL")
        )
        self.set_status(
            QtCore.QCoreApplication.translate("MainWindow", "Uruchomiono agenta RL.")
        )

    def train_rl_agent(self, checked: bool) -> None:
        """Start training of RL agent asynchronously."""
        if not checked:
            self.btn_train_rl.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Trenuj RL")
            )
            return
        self.rl_thread = RLTrainThread()
        self.rl_thread.status.connect(self.set_status)
        self.rl_thread.finished.connect(lambda: self.btn_train_rl.setChecked(False))
        self.rl_thread.finished.connect(
            lambda: self.btn_train_rl.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Trenuj RL")
            )
        )
        self.rl_thread.start()
        self.btn_train_rl.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Trwa trening RL…")
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
        self.settings.setValue("paths/rl_model", self.rl_model_path.text())
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
