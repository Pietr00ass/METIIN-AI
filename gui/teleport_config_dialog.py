"""Teleport configuration dialog."""

from __future__ import annotations

import keyboard
from PySide6 import QtCore, QtGui, QtWidgets

import agent.teleport_config as tc


class TeleportConfigDialog(QtWidgets.QDialog):
    """Dialog for editing teleport positions and channel buttons."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Konfiguracja teleportu")
        self._cfg = tc.load_teleport_config()
        self._current_edit: tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit] | None = None
        self._edit_map: dict[
            QtWidgets.QLineEdit, tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit]
        ] = {}

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
                for edit in (x_edit, y_edit):
                    edit.installEventFilter(self)
                    self._edit_map[edit] = (x_edit, y_edit)
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
            for edit in (x_edit, y_edit):
                edit.installEventFilter(self)
                self._edit_map[edit] = (x_edit, y_edit)
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

        self._hotkey = keyboard.add_hotkey(
            "f2", lambda: self._current_edit and self._capture(*self._current_edit)
        )

    def _capture(
        self, x_edit: QtWidgets.QLineEdit, y_edit: QtWidgets.QLineEdit
    ) -> None:
        pos = QtGui.QCursor.pos()
        x_edit.setText(str(pos.x()))
        y_edit.setText(str(pos.y()))

    def _set_current_edit(
        self, pair: tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit]
    ) -> None:
        if self._current_edit:
            for e in self._current_edit:
                e.setStyleSheet("")
        self._current_edit = pair
        for e in pair:
            e.setStyleSheet("background-color: #e0f7fa;")

    def eventFilter(
        self, obj: QtCore.QObject, event: QtCore.QEvent
    ) -> bool:  # type: ignore[override]
        if event.type() == QtCore.QEvent.FocusIn and obj in self._edit_map:
            self._set_current_edit(self._edit_map[obj])
        return super().eventFilter(obj, event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        keyboard.remove_hotkey(self._hotkey)
        super().closeEvent(event)

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
        tc._cfg_cache = None
        tc._cfg_mtime = None
        tc.get_config()
        super().accept()


__all__ = ["TeleportConfigDialog"]

