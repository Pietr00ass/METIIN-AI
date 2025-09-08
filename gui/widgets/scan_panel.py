from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class ScanPanel(QtWidgets.QGroupBox):
    """Widget with scan/rotation parameters."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        form = QtWidgets.QFormLayout(self)

        self.sweeps = QtWidgets.QSpinBox()
        self.sweeps.setRange(1, 20)
        self.sweeps.setValue(8)
        self.sweeps_label = QtWidgets.QLabel()
        form.addRow(self.sweeps_label, self.sweeps)

        self.sweep_ms = QtWidgets.QSpinBox()
        self.sweep_ms.setRange(50, 1000)
        self.sweep_ms.setValue(250)
        self.sweep_ms_label = QtWidgets.QLabel()
        form.addRow(self.sweep_ms_label, self.sweep_ms)

        self.idle_sec = QtWidgets.QDoubleSpinBox()
        self.idle_sec.setRange(0.5, 5.0)
        self.idle_sec.setSingleStep(0.1)
        self.idle_sec.setValue(1.5)
        self.idle_sec_label = QtWidgets.QLabel()
        form.addRow(self.idle_sec_label, self.idle_sec)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Parametry skanu (obrót E)")
        )
        if getattr(self, "sweeps_label", None) is not None:
            self.sweeps_label.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Skan sweeps:")
            )
        if getattr(self, "sweep_ms_label", None) is not None:
            self.sweep_ms_label.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Sweep ms:")
            )
        if getattr(self, "idle_sec_label", None) is not None:
            self.idle_sec_label.setText(
                QtCore.QCoreApplication.translate("MainWindow", "Idle sec:")
            )

    def get_config(self, enabled: bool) -> dict:
        return {
            "scan": {
                "enabled": enabled,
                "key": "e",
                "sweeps": int(self.sweeps.value()),
                "sweep_ms": int(self.sweep_ms.value()),
                "idle_sec": float(self.idle_sec.value()),
                "period": 0.066,
                "pause": 0.12,
            }
        }
