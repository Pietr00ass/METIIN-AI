from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class AgentPanel(QtWidgets.QGroupBox):
    """Widget with agent configuration options."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        self.prio_label = QtWidgets.QLabel()
        layout.addWidget(self.prio_label)
        self.prio_list = QtWidgets.QListWidget()
        self.prio_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        for name in ["boss", "metin", "potwory"]:
            self.prio_list.addItem(QtWidgets.QListWidgetItem(name))
        layout.addWidget(self.prio_list)

        self.policy_form = QtWidgets.QFormLayout()
        self.deadzone = QtWidgets.QDoubleSpinBox()
        self.deadzone.setRange(0.0, 0.5)
        self.deadzone.setSingleStep(0.01)
        self.deadzone.setValue(0.05)
        self.deadzone_label = QtWidgets.QLabel()
        self.policy_form.addRow(self.deadzone_label, self.deadzone)

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
        self.desired_w_layout = QtWidgets.QHBoxLayout()
        self.desired_w_layout.setContentsMargins(0, 0, 0, 0)
        self.desired_w_layout.addWidget(self.desired_w_slider)
        self.desired_w_layout.addWidget(self.desired_w)
        self.desired_w_widget = QtWidgets.QWidget()
        self.desired_w_widget.setLayout(self.desired_w_layout)
        self.desired_w_label = QtWidgets.QLabel()
        self.policy_form.addRow(self.desired_w_label, self.desired_w_widget)

        self.auto_press_chk = QtWidgets.QCheckBox()
        self.policy_form.addRow(self.auto_press_chk)
        self.auto_press_key_label = QtWidgets.QLabel()
        self.auto_press_key = QtWidgets.QLineEdit()
        self.auto_press_key.setMaxLength(1)
        self.policy_form.addRow(self.auto_press_key_label, self.auto_press_key)
        self.auto_press_interval_label = QtWidgets.QLabel()
        self.auto_press_interval = QtWidgets.QDoubleSpinBox()
        self.auto_press_interval.setRange(0.05, 10.0)
        self.auto_press_interval.setSingleStep(0.05)
        self.auto_press_interval.setValue(1.0)
        self.policy_form.addRow(
            self.auto_press_interval_label, self.auto_press_interval
        )

        layout.addLayout(self.policy_form)

        self.overlay_chk = QtWidgets.QCheckBox()
        self.overlay_chk.setChecked(True)
        layout.addWidget(self.overlay_chk)

        self.dry_run_chk = QtWidgets.QCheckBox()
        self.dry_run_chk.setChecked(False)
        layout.addWidget(self.dry_run_chk)

        self.movement_chk = QtWidgets.QCheckBox()
        self.movement_chk.setChecked(True)
        layout.addWidget(self.movement_chk)

        self.rotate_chk = QtWidgets.QCheckBox()
        self.rotate_chk.setChecked(True)
        layout.addWidget(self.rotate_chk)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Parametry agenta")
        )
        self.prio_label.setText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Priorytety (przeciągnij aby zmienić):"
            )
        )
        self.deadzone_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Deadzone X:")
        )
        self.desired_w_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Desired box W:")
        )
        self.auto_press_chk.setText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Automatyczne klikanie"
            )
        )
        self.auto_press_key_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Klawisz:")
        )
        self.auto_press_interval_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Interwał (s):")
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

    def current_priority(self) -> list[str]:
        return [self.prio_list.item(i).text() for i in range(self.prio_list.count())]

    def get_config(self) -> dict:
        return {
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
            "policy": {
                "deadzone_x": float(self.deadzone.value()),
                "desired_box_w": float(self.desired_w_slider.value() / 100),
            },
            "priority": self.current_priority(),
            "dry_run": self.dry_run_chk.isChecked(),
            "auto_press": {
                "enabled": self.auto_press_chk.isChecked(),
                "key": self.auto_press_key.text().strip(),
                "interval_sec": float(self.auto_press_interval.value()),
            },
        }
