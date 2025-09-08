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
        form.addRow("", self.sweeps)  # placeholders for labels

        self.sweep_ms = QtWidgets.QSpinBox()
        self.sweep_ms.setRange(50, 1000)
        self.sweep_ms.setValue(250)
        form.addRow("", self.sweep_ms)

        self.idle_sec = QtWidgets.QDoubleSpinBox()
        self.idle_sec.setRange(0.5, 5.0)
        self.idle_sec.setSingleStep(0.1)
        self.idle_sec.setValue(1.5)
        form.addRow("", self.idle_sec)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setTitle(
            QtCore.QCoreApplication.translate("MainWindow", "Parametry skanu (obrót E)")
        )
        form = self.layout()
        if isinstance(form, QtWidgets.QFormLayout):
            form.labelForField(self.sweeps).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Skan sweeps:")
            )
            form.labelForField(self.sweep_ms).setText(
                QtCore.QCoreApplication.translate("MainWindow", "Sweep ms:")
            )
            form.labelForField(self.idle_sec).setText(
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
