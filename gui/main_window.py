"""Main application window for the Metin2 vision agent GUI."""

from __future__ import annotations

import json
import logging
import os
import threading
import time

import cv2
import numpy as np
import pyautogui
from pynput import keyboard as pynput_keyboard
from PySide6 import QtCore, QtGui, QtWidgets

from agent.channel import ChannelSwitcher
from agent.cycle import CycleFarm
from agent.strategy import load_strategy
from agent.teleport import Teleporter, TeleportResult
from agent.wasd import KeyHold
from recorder.window_capture import WindowCapture
import agent.teleport_config as tc

from gui.preview import PreviewWorker
from gui.teleport_config_dialog import TeleportConfigDialog

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


class MainWindow(QtWidgets.QMainWindow):
    """Main GUI window with controls for vision agent automation."""

    def __init__(self) -> None:
        super().__init__()
        self.scale = 1.0
        self.base_font_pt = QtWidgets.QApplication.font().pointSizeF()
        self.base_window_size = QtCore.QSize(1200, 800)
        self.base_video_size = QtCore.QSize(860, 480)
        self.setWindowTitle("Metin2 Vision Agent – Panel")

        # central layout
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        # left pane with controls inside a scroll area so all sections remain accessible
        left_widget = QtWidgets.QWidget()
        left = QtWidgets.QVBoxLayout(left_widget)
        left_scroll = QtWidgets.QScrollArea()
        left_scroll.setWidget(left_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        layout.addWidget(left_scroll, 1)

        # settings group
        settings_box = QtWidgets.QGroupBox("Ustawienia")
        settings_form = QtWidgets.QFormLayout(settings_box)
        self.title_edit = QtWidgets.QLineEdit()
        self.title_edit.setPlaceholderText("Fragment tytułu okna (np. Metin2)")
        settings_form.addRow("Tytuł okna:", self.title_edit)
        self.model_path = QtWidgets.QLineEdit("runs/detect/train/weights/best.pt")
        settings_form.addRow("Ścieżka modelu YOLO:", self.model_path)
        self.classes_edit = QtWidgets.QLineEdit("metin,boss,potwory")
        settings_form.addRow("Klasy obiektów:", self.classes_edit)
        tmpl_widget = QtWidgets.QWidget()
        tmpl_layout = QtWidgets.QHBoxLayout(tmpl_widget)
        tmpl_layout.setContentsMargins(0, 0, 0, 0)
        self.templates_dir_edit = QtWidgets.QLineEdit("assets/templates")
        self.btn_templates_dir = QtWidgets.QPushButton("Wybierz…")
        tmpl_layout.addWidget(self.templates_dir_edit)
        tmpl_layout.addWidget(self.btn_templates_dir)
        settings_form.addRow("Katalog szablonów:", tmpl_widget)
        self.btn_templates_dir.clicked.connect(self.browse_templates_dir)
        left.addWidget(settings_box)

        # agent parameters group
        agent_box = QtWidgets.QGroupBox("Parametry agenta")
        agent_layout = QtWidgets.QVBoxLayout(agent_box)
        agent_layout.addWidget(
            QtWidgets.QLabel("Priorytety (przeciągnij aby zmienić):")
        )
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
        desired_w_layout = QtWidgets.QHBoxLayout()
        desired_w_layout.addWidget(self.desired_w_slider)
        desired_w_layout.addWidget(self.desired_w)

        policy_form.addRow("Deadzone X:", self.deadzone)
        policy_form.addRow("Desired box W:", desired_w_layout)
        agent_layout.addLayout(policy_form)
        self.overlay_chk = QtWidgets.QCheckBox("Overlay YOLO na podglądzie")
        self.overlay_chk.setChecked(True)
        agent_layout.addWidget(self.overlay_chk)
        self.dry_run_chk = QtWidgets.QCheckBox("Dry run (bez klików/klawiszy)")
        self.dry_run_chk.setChecked(False)
        agent_layout.addWidget(self.dry_run_chk)
        self.movement_chk = QtWidgets.QCheckBox("Movement włączony")
        self.movement_chk.setChecked(True)
        agent_layout.addWidget(self.movement_chk)
        self.rotate_chk = QtWidgets.QCheckBox("Obrót (E) włączony")
        self.rotate_chk.setChecked(True)
        agent_layout.addWidget(self.rotate_chk)
        left.addWidget(agent_box)

        # scan parameters
        scan_box = QtWidgets.QGroupBox("Parametry skanu (obrót E)")
        scan_form = QtWidgets.QFormLayout(scan_box)
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
        scan_form.addRow("Skan sweeps:", self.sweeps)
        scan_form.addRow("Sweep ms:", self.sweep_ms)
        scan_form.addRow("Idle sec:", self.idle_sec)
        left.addWidget(scan_box)

        # teleportation controls
        tp_box = QtWidgets.QGroupBox("Teleportacja")
        tp_form = QtWidgets.QFormLayout(tp_box)
        self.tp_point = QtWidgets.QLineEdit()
        self.tp_point.setPlaceholderText("Nazwa punktu (OCR lub template)")
        self.tp_side = QtWidgets.QLineEdit()
        self.tp_side.setPlaceholderText("Strona/mapa (np. Strona I)")
        self.tp_minutes = QtWidgets.QSpinBox()
        self.tp_minutes.setRange(1, 180)
        self.tp_minutes.setValue(10)
        tp_form.addRow("Punkt:", self.tp_point)
        tp_form.addRow("Strona:", self.tp_side)
        tp_form.addRow("Czas (min):", self.tp_minutes)
        left.addWidget(tp_box)

        # channels and cooldown
        ch_box = QtWidgets.QGroupBox("Kanały i cooldown")
        ch_layout = QtWidgets.QVBoxLayout(ch_box)
        ch_layout.addWidget(QtWidgets.QLabel("Skróty kanałów (Ctrl + klawisz):"))
        self.ch_key_edits = {}
        ch_form = QtWidgets.QFormLayout()
        for i in range(1, 9):
            edit = QtWidgets.QLineEdit(str(i))
            edit.setMaximumWidth(40)
            self.ch_key_edits[i] = edit
            ch_form.addRow(f"CH{i}:", edit)
        ch_layout.addLayout(ch_form)
        ch_layout.addWidget(QtWidgets.QLabel("Kanał (minimapa):"))
        self.channel_combo = QtWidgets.QComboBox()
        self.channel_combo.addItems([f"CH{i}" for i in range(1, 9)])
        ch_layout.addWidget(self.channel_combo)
        ch_layout.addWidget(QtWidgets.QLabel("Cooldown slotów (minuty):"))
        self.cooldown_spin = QtWidgets.QSpinBox()
        self.cooldown_spin.setRange(1, 60)
        self.cooldown_spin.setValue(10)
        ch_layout.addWidget(self.cooldown_spin)
        left.addWidget(ch_box)

        # UI scale selector
        scale_box = QtWidgets.QGroupBox("Skala UI")
        scale_layout = QtWidgets.QHBoxLayout(scale_box)
        self.scale_spin = QtWidgets.QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 3.0)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setDecimals(2)
        self.scale_spin.setValue(1.0)
        scale_layout.addWidget(self.scale_spin)
        left.addWidget(scale_box)

        # action buttons
        actions_box = QtWidgets.QGroupBox("Akcje")
        actions_layout = QtWidgets.QVBoxLayout(actions_box)
        self.btn_preview = QtWidgets.QPushButton("Start podglądu")
        self.btn_preview.setCheckable(True)
        self.btn_record = QtWidgets.QPushButton("Nagrywaj dane (5 min)")
        self.btn_record.setCheckable(True)
        self.btn_agent = QtWidgets.QPushButton("Start agenta (YOLO + WASD)")
        self.btn_agent.setCheckable(True)
        self.btn_tp_hunt = QtWidgets.QPushButton("Teleportuj i poluj")
        self.btn_tp_hunt.setCheckable(True)
        self.btn_cycle = QtWidgets.QPushButton("Cykl 8×8 (sloty×kanały)")
        self.btn_cycle.setCheckable(True)
        self.btn_ch = QtWidgets.QPushButton("Zmień kanał")
        self.btn_ch.setCheckable(True)
        self.btn_stop = QtWidgets.QPushButton("STOP (F12)")
        self.btn_train = QtWidgets.QPushButton("Trenuj YOLO")
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
        self.seq_table.setHorizontalHeaderLabels(["CH", "Slot"])
        self.seq_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.seq_add_btn = QtWidgets.QPushButton("Dodaj krok")
        self.seq_remove_btn = QtWidgets.QPushButton("Usuń krok")
        seq_btns = QtWidgets.QHBoxLayout()
        seq_btns.addWidget(self.seq_add_btn)
        seq_btns.addWidget(self.seq_remove_btn)
        self.seq_box = QtWidgets.QGroupBox("Sekwencja cyklu")
        seq_layout = QtWidgets.QVBoxLayout(self.seq_box)
        seq_help = QtWidgets.QLabel(
            "Opcjonalna lista kanałów i slotów; puste = domyślny cykl 8×8."
        )
        seq_help.setWordWrap(True)
        seq_help.setToolTip(
            "Każdy wiersz określa kanał (1-8) i slot (1-8) odwiedzany kolejno."
        )
        self.seq_box.setToolTip(
            "Ustal kolejność kanałów i slotów. Pozostaw puste dla domyślnego 8×8."
        )
        seq_layout.addWidget(seq_help)
        seq_layout.addWidget(self.seq_table)
        seq_layout.addLayout(seq_btns)
        actions_layout.insertWidget(actions_layout.indexOf(self.btn_ch), self.seq_box)
        self.seq_add_btn.clicked.connect(self.add_seq_row)
        self.seq_remove_btn.clicked.connect(self.remove_seq_row)

        self.btn_tp_cfg = QtWidgets.QPushButton("Konfiguracja teleportu")
        actions_layout.addWidget(self.btn_tp_cfg)
        self.btn_tp_cfg.clicked.connect(self.open_teleport_config)
        self.btn_save_cfg = QtWidgets.QPushButton("Zapisz konfigurację")
        self.btn_load_cfg = QtWidgets.QPushButton("Wczytaj konfigurację")
        actions_layout.addWidget(self.btn_save_cfg)
        actions_layout.addWidget(self.btn_load_cfg)
        left.addWidget(actions_box)

        # logs
        log_box = QtWidgets.QGroupBox("Logi")
        log_layout = QtWidgets.QVBoxLayout(log_box)
        log_lvl_layout = QtWidgets.QHBoxLayout()
        log_lvl_layout.addWidget(QtWidgets.QLabel("Poziom:"))
        self.log_level_combo = QtWidgets.QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO"])
        log_lvl_layout.addWidget(self.log_level_combo)
        log_layout.addLayout(log_lvl_layout)
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3)
        self.log_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        log_layout.addWidget(self.log_view)
        left.addWidget(log_box)

        left.addStretch(1)
        self.status_label = QtWidgets.QLabel("Gotowy.")
        self.status_label.setWordWrap(True)
        left.addWidget(self.status_label)

        # right pane with video
        right = QtWidgets.QVBoxLayout()
        layout.addLayout(right, 2)
        self.video = QtWidgets.QLabel()
        self.video.setMinimumSize(self.base_video_size)
        self.video.setStyleSheet("background:#222; border:1px solid #444")
        self.video.setAlignment(QtCore.Qt.AlignCenter)
        self.video.setFocusPolicy(QtCore.Qt.NoFocus)
        right.addWidget(self.video)

        # thread references
        self.preview_thread: PreviewWorker | None = None
        self.agent_thread: threading.Thread | None = None
        self.cycle_agent: CycleFarm | None = None
        self._panic = False
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
        self.apply_scale(self.scale)

    # ---------- helpers ----------
    def current_priority(self) -> list[str]:
        return [self.prio_list.item(i).text() for i in range(self.prio_list.count())]

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        logging.info(text)

    def apply_scale(self, scale: float) -> None:
        """Apply scaling to window size, video widget and global font."""
        # Determine maximum geometry available on the primary screen
        screen = QtWidgets.QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QtCore.QRect()

        base_w = self.base_window_size.width()
        base_h = self.base_window_size.height()

        # Desired size based purely on the requested scale
        desired_w = int(base_w * scale)
        desired_h = int(base_h * scale)

        # Clamp to available screen geometry
        clamped_w = min(desired_w, avail.width()) if avail.width() else desired_w
        clamped_h = min(desired_h, avail.height()) if avail.height() else desired_h

        # Effective scale actually applied
        effective_scale = min(clamped_w / base_w, clamped_h / base_h)
        self.scale = effective_scale

        # Resize window using clamped dimensions
        self.resize(clamped_w, clamped_h)
        self.video.setMinimumSize(
            int(self.base_video_size.width() * effective_scale),
            int(self.base_video_size.height() * effective_scale),
        )
        font = QtGui.QFont()
        font.setPointSizeF(self.base_font_pt * effective_scale)
        QtWidgets.QApplication.setFont(font)
        # Ensure log view shows exactly three lines at the current scale
        metrics = QtGui.QFontMetrics(font)
        self.log_view.setFixedHeight(int(metrics.lineSpacing() * 4))

        if effective_scale < scale:
            self.set_status("Skala dopasowana do dostępnej rozdzielczości ekranu.")

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
            self, "Wybierz katalog z szablonami", self.templates_dir_edit.text()
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
            self.btn_preview.setText("Start podglądu")
            self.set_status("Podgląd zatrzymany.")
            return
        title = self.title_edit.text().strip()
        if not title:
            self.set_status("Podaj fragment tytułu okna.")
            self.btn_preview.setChecked(False)
            return
        # start preview
        self.preview_thread = PreviewWorker(title)
        self.preview_thread.frame_ready.connect(self.show_frame)
        self.preview_thread.status.connect(self.set_status)
        classes = [c.strip() for c in self.classes_edit.text().split(",") if c.strip()]
        self.preview_thread.configure_overlay(
            self.model_path.text().strip(), classes, self.overlay_chk.isChecked()
        )
        self.preview_thread.start()
        self.btn_preview.setText("Stop podglądu")

    # ---------- recording ----------
    def record_data(self, checked: bool) -> None:
        if not checked:
            self.btn_record.setText("Nagrywaj dane (5 min)")
            return
        from recorder.capture import record_session

        title = self.title_edit.text().strip()
        if not title:
            self.set_status("Podaj fragment tytułu okna.")
            self.btn_record.setChecked(False)
            return
        with WindowCapture(title) as wc:
            if not wc.locate(timeout=5):
                self.set_status("Nie znaleziono okna.")
                self.btn_record.setChecked(False)
                return
            wc.update_region()
            l, t, w, h = wc.region

        def job():
            try:
                self.set_status("Nagrywanie 5 min…")
                record_session(
                    "data/recordings", region=(l, t, w, h), fps=15, duration_sec=300
                )
                self.set_status(
                    "Nagrywanie zakończone. Użyj narzędzia 'extract_frames'."
                )
            except Exception as exc:
                self.set_status(f"Błąd nagrywania: {exc}")
            finally:
                self.btn_record.setChecked(False)

        threading.Thread(target=job, daemon=True).start()
        self.btn_record.setText("Nagrywam dane (5 min)")

    # ---------- configuration ----------
    def build_cfg(self) -> dict:
        title = self.title_edit.text().strip()
        classes = [c.strip() for c in self.classes_edit.text().split(",") if c.strip()]
        prio = self.current_priority()
        hotkeys = {
            i: self.ch_key_edits[i].text().strip() or str(i) for i in range(1, 9)
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
            key = ch_hot.get(str(i)) or ch_hot.get(i) or str(i)
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
            self._panic = True
            if self.agent_thread:
                self.agent_thread.join(timeout=1)
                self.agent_thread = None
            self.btn_agent.setText("Start agenta (YOLO + WASD)")
            self.set_status("Agent zatrzymany.")
            return
        cfg = self.build_cfg()

        def run():
            cap = WindowCapture(cfg["window"]["title_substr"])
            try:
                agent = load_strategy(cfg, cap)
                if not agent.win.locate(timeout=5):
                    self.set_status("Nie znaleziono okna.")
                    return
                period = cfg.get("scan", {}).get("period", 1 / 15)
                while not self._panic:
                    agent.step()
                    time.sleep(period)
            except Exception as exc:
                self.set_status(f"Błąd agenta: {exc}")
            finally:
                cap.close()
                self.agent_thread = None
                self.btn_agent.setChecked(False)
                self.btn_agent.setText("Start agenta (YOLO + WASD)")

        self._panic = False
        self.agent_thread = threading.Thread(target=run, daemon=True)
        self.agent_thread.start()
        self.btn_agent.setText("Stop agenta")
        self.set_status("Agent YOLO+WASD uruchomiony.")

    def start_tp_and_hunt(self, checked: bool) -> None:
        if not checked:
            self._panic = True
            if self.agent_thread:
                self.agent_thread.join(timeout=1)
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

        def run():
            win = WindowCapture(cfg["window"]["title_substr"])
            try:
                if not win.locate(timeout=5):
                    self.set_status("Nie znaleziono okna.")
                    return
                try:
                    test_img = pyautogui.screenshot()
                    logger.info(
                        "Zrzut ekranu zakończony powodzeniem (%dx%d)",
                        test_img.width,
                        test_img.height,
                    )
                except Exception as e:
                    logger.error("Błąd przy robieniu zrzutu ekranu: %s", e)
                    self.set_status(f"Błąd przechwytywania ekranu: {e}")
                    return
                tp = Teleporter(win, cfg["paths"]["templates_dir"], use_ocr=True)
                res = tp.teleport(point, side)
                if res is not TeleportResult.OK:
                    msg_map = {
                        TeleportResult.TEMPLATE_NOT_FOUND: "Nie znaleziono szablonu w panelu teleportu.",
                        TeleportResult.OCR_MISS: "Nie rozpoznano wskazanego slotu (OCR).",
                        TeleportResult.WINDOW_NOT_FOREGROUND: "Okno gry nie jest aktywne.",
                    }
                    self.set_status(msg_map.get(res, "Teleportacja nie powiodła się."))
                hd = load_strategy(cfg, win)
                t_end = time.time() + minutes * 60
                period = cfg.get("scan", {}).get("period", 1 / 15)
                while time.time() < t_end and not self._panic:
                    hd.step()
                    time.sleep(period)
                self.set_status("Zakończono 'Teleportuj i poluj'.")
            except RuntimeError as exc:
                self.set_status(
                    f"Błąd przechwytywania ekranu: {exc}. "
                    "Czy okno gry jest poza ekranem lub zminimalizowane?"
                )
            except Exception as exc:
                self.set_status(f"Błąd teleport+poluj: {exc}")
            finally:
                win.close()
                self.agent_thread = None
                self.btn_tp_hunt.setChecked(False)
                self.btn_tp_hunt.setText("Teleportuj i poluj")

        self._panic = False
        self.agent_thread = threading.Thread(target=run, daemon=True)
        self.agent_thread.start()
        self.btn_tp_hunt.setText("Stop 'Teleportuj i poluj'")
        self.set_status("Teleportuję i poluję…")

    def start_cycle(self, checked: bool) -> None:
        if not checked:
            self._panic = True
            if self.agent_thread:
                self.agent_thread.join(timeout=1)
                self.agent_thread = None
            if self.cycle_agent:
                try:
                    self.cycle_agent.stop()
                except Exception:
                    pass
                self.cycle_agent = None
            self.btn_cycle.setText("Cykl 8×8 (sloty×kanały)")
            self.set_status("Cykl zatrzymany.")
            return
        page = self.tp_side.text().strip() or None
        cfg = self.build_cfg()
        cycle_cfg = cfg.get("cycle", {})

        def run():
            try:
                cf = CycleFarm(cfg)
                self.cycle_agent = cf
                cf.run(
                    page_label=page,
                    ch_from=cycle_cfg.get("ch_from", 1),
                    ch_to=cycle_cfg.get("ch_to", 8),
                    slots=cycle_cfg.get("slots", list(range(1, 9))),
                    per_spot_sec=cycle_cfg.get("per_spot_sec", 90),
                    clear_sec=cycle_cfg.get("clear_sec", 6),
                    sequence=cycle_cfg.get("sequence"),
                )
                self.set_status("Cykl 8×8 zakończony.")
            except Exception as exc:
                self.set_status(f"Błąd cyklu: {exc}")
            finally:
                self.cycle_agent = None
                self.agent_thread = None
                self.btn_cycle.setChecked(False)
                self.btn_cycle.setText("Cykl 8×8 (sloty×kanały)")

        self._panic = False
        self.agent_thread = threading.Thread(target=run, daemon=True)
        self.agent_thread.start()
        self.btn_cycle.setText("Stop cyklu 8×8")
        self.set_status("Start cyklu 8×8…")

    def change_channel(self, checked: bool) -> None:
        if not checked:
            self.btn_ch.setText("Zmień kanał")
            return

        def job():
            try:
                cfg = self.build_cfg()
                win = WindowCapture(cfg["window"]["title_substr"])
                try:
                    if not win.locate(timeout=5):
                        self.set_status("Nie znaleziono okna.")
                        return
                    ch = int(self.channel_combo.currentText().replace("CH", ""))
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
                        ok = cs.switch(ch)
                    finally:
                        keys.stop()
                    msg = (
                        f"Zmieniono kanał na CH{ch}"
                        if ok
                        else "Nie znaleziono przycisku CH – sprawdź szablony."
                    )
                    self.set_status(msg)
                finally:
                    win.close()
            except Exception as exc:
                self.set_status(f"Błąd zmiany kanału: {exc}")
            finally:
                self.btn_ch.setChecked(False)
                self.btn_ch.setText("Zmień kanał")

        threading.Thread(target=job, daemon=True).start()
        self.btn_ch.setText("Zmiana kanału…")
        self.set_status("Zmiana kanału…")

    def stop_all(self) -> None:
        self._panic = True
        try:
            KeyHold().release_all()
        except Exception:
            pass
        if self.cycle_agent:
            try:
                self.cycle_agent.stop()
            except Exception:
                pass
            self.cycle_agent = None
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
        self.set_status("STOP – wszystkie klawisze zwolnione.")

    def train_yolo_api(self, checked: bool) -> None:
        """Train YOLO using ultralytics API (runs asynchronously)."""
        if not checked:
            self.btn_train.setText("Trenuj YOLO")
            return

        def job():
            try:
                self.set_status("Trening YOLO – start…")
                from ultralytics import YOLO

                model = YOLO("yolov8n.pt")
                model.train(
                    data="datasets/mt2/data.yaml",
                    imgsz=640,
                    epochs=50,
                    batch=16,
                    device="cpu",
                )
                self.set_status(
                    "Trening zakończony. Wybierz runs/detect/train/weights/best.pt"
                )
            except Exception as exc:
                self.set_status(f"Błąd treningu: {exc}")
            finally:
                self.btn_train.setChecked(False)
                self.btn_train.setText("Trenuj YOLO")

        threading.Thread(target=job, daemon=True).start()
        self.btn_train.setText("Trwa trening…")

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
