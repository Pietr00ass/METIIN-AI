"""Teleport configuration dialog."""

from __future__ import annotations

import keyboard
from PySide6 import QtCore, QtGui, QtWidgets

import agent.teleport_config as tc


class TeleportConfigDialog(QtWidgets.QDialog):
    """Dialog for editing teleport positions and channel buttons."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(QtCore.QCoreApplication.translate("TeleportConfigDialog", "Konfiguracja teleportu"))
        self._cfg = tc.load_teleport_config()
        self._current_edit: tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit] | None = None
        self._edit_map: dict[
            QtWidgets.QLineEdit, tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit]
        ] = {}

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.pos_edits: list[tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit]] = []

        for idx in range(8):
            x_edit = QtWidgets.QLineEdit()
            x_edit.setMaximumWidth(60)
            y_edit = QtWidgets.QLineEdit()
            y_edit.setMaximumWidth(60)
            for edit in (x_edit, y_edit):
                edit.installEventFilter(self)
                self._edit_map[edit] = (x_edit, y_edit)
            btn = QtWidgets.QPushButton(
                QtCore.QCoreApplication.translate("TeleportConfigDialog", "Przechwyć")
            )
            btn.clicked.connect(lambda _, xe=x_edit, ye=y_edit: self._capture(xe, ye))
            row = QtWidgets.QHBoxLayout()
            row.addWidget(
                QtWidgets.QLabel(
                    QtCore.QCoreApplication.translate("TeleportConfigDialog", "X:")
                )
            )
            row.addWidget(x_edit)
            row.addWidget(
                QtWidgets.QLabel(
                    QtCore.QCoreApplication.translate("TeleportConfigDialog", "Y:")
                )
            )
            row.addWidget(y_edit)
            row.addWidget(btn)
            w = QtWidgets.QWidget()
            w.setLayout(row)
            form.addRow(
                QtCore.QCoreApplication.translate("TeleportConfigDialog", "Slot {num}:").format(
                    num=idx + 1
                ),
                w,
            )
            self.pos_edits.append((x_edit, y_edit))

        btn_group = QtWidgets.QGroupBox(QtCore.QCoreApplication.translate("TeleportConfigDialog", "Przyciski kanałów"))
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
            btn = QtWidgets.QPushButton(QtCore.QCoreApplication.translate("TeleportConfigDialog", "Przechwyć"))
            btn.clicked.connect(lambda _, xe=x_edit, ye=y_edit: self._capture(xe, ye))
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(QtCore.QCoreApplication.translate("TeleportConfigDialog", "X:")))
            row.addWidget(x_edit)
            row.addWidget(QtWidgets.QLabel(QtCore.QCoreApplication.translate("TeleportConfigDialog", "Y:")))
            row.addWidget(y_edit)
            row.addWidget(btn)
            w = QtWidgets.QWidget()
            w.setLayout(row)
            btn_form.addRow(QtCore.QCoreApplication.translate("TeleportConfigDialog", "CH{num}:").format(num=ch), w)
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
        pos_cfg = self._cfg.get("positions", [])
        for idx, (x_edit, y_edit) in enumerate(self.pos_edits):
            if idx < len(pos_cfg):
                x, y = pos_cfg[idx]
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
        pos_out: list[list[int]] = []
        for x_edit, y_edit in self.pos_edits:
            x = int(x_edit.text() or 0)
            y = int(y_edit.text() or 0)
            pos_out.append([x, y])
        btn_out: dict[int, list[int]] = {}
        for ch, (x_edit, y_edit) in self.btn_edits.items():
            x = int(x_edit.text() or 0)
            y = int(y_edit.text() or 0)
            btn_out[ch] = [x, y]
        data["positions"] = pos_out
        data["channel_buttons"] = btn_out
        tc.save_teleport_config(data)
        tc._cfg_cache = None
        tc._cfg_mtime = None
        tc.get_config()
        super().accept()


__all__ = ["TeleportConfigDialog"]

