from __future__ import annotations

"""
Metin2 Vision Agent GUI

This improved GUI implements several features for automating gameplay on a Metin2 private server.  It
provides real‑time preview of a selected window, overlaying object detection results using a YOLO
model.  Users can record data for training, train the model via the Ultralytics API, launch an agent
to control the game via WASD keys, teleport to saved positions, cycle through multiple slots and
channels, and perform an emergency stop.  Additional controls allow toggling a dry‑run mode (no
keyboard/mouse input), adjusting parameters for the object detection and navigation policy, and
configuring the rotation scan used to locate objects when none are visible.

Dependencies: PySide6, numpy, OpenCV, pyautogui, pynput, ultralytics.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root on ``sys.path`` regardless of package depth
# ---------------------------------------------------------------------------
# Walk up the directory tree until both ``agent`` and ``recorder`` packages
# are found.  This allows running the module with ``python -m gui.app`` even if
# the project is nested deeper in the filesystem hierarchy.
ROOT_DIR = Path(__file__).resolve()
for parent in ROOT_DIR.parents:
    if (parent / "agent").exists() and (parent / "recorder").exists():
        ROOT_DIR = parent
        break
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import logging
import os
import threading
import time

import cv2
import numpy as np
import pyautogui
from pynput import keyboard
from PySide6 import QtCore, QtGui, QtWidgets

from agent.channel import ChannelSwitcher
from agent.cycle import CycleFarm
from agent.detector import ObjectDetector
from agent.hunt_destroy import HuntDestroy
from agent.teleport import Teleporter, TeleportResult
from agent.wasd import KeyHold
from recorder.window_capture import WindowCapture
import agent.teleport_config as tc

logging.basicConfig(level=logging.DEBUG)


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


class PreviewWorker(QtCore.QThread):
    """Thread that captures frames from a window and optionally overlays detections."""

    frame_ready = QtCore.Signal(np.ndarray)
    status = QtCore.Signal(str)

    def __init__(self, title_substr: str):
        super().__init__()
        self.title = title_substr
        self._stop = False
        self._det: ObjectDetector | None = None
        self._overlay = False
        self._classes: list[str] | None = None

    def configure_overlay(
        self, model_path: str | None, classes: list[str] | None, enabled: bool
    ):
        """Enable or disable overlay and load the model lazily."""
        self._overlay = enabled
        self._classes = classes
        if enabled and model_path:
            try:
                self._det = ObjectDetector(model_path, classes)
                self.status.emit("Overlay YOLO aktywny.")
            except Exception as exc:
                self.status.emit(f"Błąd YOLO: {exc}")
                self._det = None
        else:
            self._det = None

    def run(self) -> None:
        """Main loop capturing frames from the window and emitting them."""
        try:
            with WindowCapture(self.title) as cap:
                self.status.emit("Szukam okna…")
                if not cap.locate(timeout=5):
                    self.status.emit("Nie znaleziono okna.")
                    return
                self.status.emit("Znaleziono okno. Podgląd działa.")
                while not self._stop:
                    fr = cap.grab()
                    frame = np.array(fr)[
                        :, :, :3
                    ].copy()  # convert BGRA to BGR and ensure contiguous
                    if self._overlay and self._det:
                        try:
                            dets = self._det.infer(frame)
                            for d in dets:
                                x1, y1, x2, y2 = map(int, d["bbox"])
                                color = (0, 0, 255)
                                if d["name"] == "boss":
                                    color = (0, 215, 255)
                                elif d["name"] == "potwory":
                                    color = (255, 128, 0)
                                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                                cv2.putText(
                                    frame,
                                    f"{d['name']} {d['conf']:.2f}",
                                    (x1, max(12, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    color,
                                    1,
                                )
                        except Exception as exc:
                            self.status.emit(f"Overlay YOLO błąd: {exc}")
                    self.frame_ready.emit(frame)
                    self.msleep(33)
        except Exception as exc:
            self.status.emit(f"Błąd podglądu: {exc}")

    def stop(self) -> None:
        self._stop = True


class TeleportConfigDialog(QtWidgets.QDialog):
    """Dialog for editing teleport positions and channel buttons."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Konfiguracja teleportu")
        self._cfg = tc.load_teleport_config()

        layout = QtWidgets.QVBoxLayout(self)
        self.pos_edits: dict[int, list[tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit]]] = {}
        tabs = QtWidgets.QTabWidget()
        layout.addWidget(tabs)

        for ch in range(1, 5):
            tab = QtWidgets.QWidget()
            form = QtWidgets.QFormLayout(tab)
            slots: list[tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit]] = []
            for idx in range(8):
                x_edit = QtWidgets.QLineEdit()
                x_edit.setMaximumWidth(60)
                y_edit = QtWidgets.QLineEdit()
                y_edit.setMaximumWidth(60)
                btn = QtWidgets.QPushButton("Przechwyć")
                btn.clicked.connect(lambda _, xe=x_edit, ye=y_edit: self._capture(xe, ye))
                row = QtWidgets.QHBoxLayout()
                row.addWidget(QtWidgets.QLabel("X:"))
                row.addWidget(x_edit)
                row.addWidget(QtWidgets.QLabel("Y:"))
                row.addWidget(y_edit)
                row.addWidget(btn)
                w = QtWidgets.QWidget()
                w.setLayout(row)
                form.addRow(f"Slot {idx + 1}:", w)
                slots.append((x_edit, y_edit))
            self.pos_edits[ch] = slots
            tabs.addTab(tab, f"CH{ch}")

        btn_group = QtWidgets.QGroupBox("Przyciski kanałów")
        btn_form = QtWidgets.QFormLayout(btn_group)
        self.btn_edits: dict[int, tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit]] = {}
        for ch in range(1, 5):
            x_edit = QtWidgets.QLineEdit()
            x_edit.setMaximumWidth(60)
            y_edit = QtWidgets.QLineEdit()
            y_edit.setMaximumWidth(60)
            btn = QtWidgets.QPushButton("Przechwyć")
            btn.clicked.connect(lambda _, xe=x_edit, ye=y_edit: self._capture(xe, ye))
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel("X:"))
            row.addWidget(x_edit)
            row.addWidget(QtWidgets.QLabel("Y:"))
            row.addWidget(y_edit)
            row.addWidget(btn)
            w = QtWidgets.QWidget()
            w.setLayout(row)
            btn_form.addRow(f"CH{ch}:", w)
            self.btn_edits[ch] = (x_edit, y_edit)
        layout.addWidget(btn_group)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate()

        self._f2_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_F2), self
        )
        self._f2_shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        self._f2_shortcut.activated.connect(self._capture_current)

    def _capture(
        self, x_edit: QtWidgets.QLineEdit, y_edit: QtWidgets.QLineEdit
    ) -> None:
        pos = QtGui.QCursor.pos()
        x_edit.setText(str(pos.x()))
        y_edit.setText(str(pos.y()))

    def _capture_current(self) -> None:
        fw = self.focusWidget()
        for slots in self.pos_edits.values():
            for x_edit, y_edit in slots:
                if fw in (x_edit, y_edit):
                    self._capture(x_edit, y_edit)
                    return
        for x_edit, y_edit in self.btn_edits.values():
            if fw in (x_edit, y_edit):
                self._capture(x_edit, y_edit)
                return

    def _populate(self) -> None:
        pos_cfg = self._cfg.get("positions_by_channel", {})
        for ch, slots in self.pos_edits.items():
            vals = pos_cfg.get(ch, [])
            for idx, (x_edit, y_edit) in enumerate(slots):
                if idx < len(vals):
                    x, y = vals[idx]
                    x_edit.setText(str(x))
                    y_edit.setText(str(y))

        btn_cfg = self._cfg.get("channel_buttons", {})
        for ch, (x_edit, y_edit) in self.btn_edits.items():
            if ch in btn_cfg:
                x, y = btn_cfg[ch]
                x_edit.setText(str(x))
                y_edit.setText(str(y))

    def accept(self) -> None:  # type: ignore[override]
        data = dict(self._cfg)
        pos_out: dict[int, list[list[int]]] = {}
        for ch, slots in self.pos_edits.items():
            pos_out[ch] = []
            for x_edit, y_edit in slots:
                x = int(x_edit.text() or 0)
                y = int(y_edit.text() or 0)
                pos_out[ch].append([x, y])
        btn_out: dict[int, list[int]] = {}
        for ch, (x_edit, y_edit) in self.btn_edits.items():
            x = int(x_edit.text() or 0)
            y = int(y_edit.text() or 0)
            btn_out[ch] = [x, y]
        data["positions_by_channel"] = pos_out
        data["channel_buttons"] = btn_out
        tc.save_teleport_config(data)
        tc.positions_by_channel = pos_out
        tc.channel_buttons = btn_out
        super().accept()


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
        self.desired_w.setRange(0.02, 0.5)
        self.desired_w.setSingleStep(0.01)
        self.desired_w.setValue(0.12)
        policy_form.addRow("Deadzone X:", self.deadzone)
        policy_form.addRow("Desired box W:", self.desired_w)
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
                "desired_box_w": float(self.desired_w.value()),
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
                agent = HuntDestroy(cfg, cap)
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
                tp = Teleporter(win, cfg["paths"]["templates_dir"], use_ocr=True)
                res = tp.teleport(point, side)
                if res is not TeleportResult.OK:
                    msg_map = {
                        TeleportResult.TEMPLATE_NOT_FOUND: "Nie znaleziono szablonu w panelu teleportu.",
                        TeleportResult.OCR_MISS: "Nie rozpoznano wskazanego slotu (OCR).",
                        TeleportResult.WINDOW_NOT_FOREGROUND: "Okno gry nie jest aktywne.",
                    }
                    self.set_status(msg_map.get(res, "Teleportacja nie powiodła się."))
                hd = HuntDestroy(cfg, win)
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
                if key == keyboard.Key.f12:
                    self.stop_all()
            except Exception:
                pass

        self._hotkey_listener = keyboard.Listener(on_press=on_press)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
