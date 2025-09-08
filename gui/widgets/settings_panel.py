from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class SettingsPanel(QtWidgets.QGroupBox):
    """Widget containing basic application settings."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QFormLayout(self)

        self.title_label = QtWidgets.QLabel()
        self.title_edit = QtWidgets.QLineEdit()
        layout.addRow(self.title_label, self.title_edit)

        self.model_label = QtWidgets.QLabel()
        self.model_path = QtWidgets.QLineEdit("runs/detect/train/weights/best.pt")
        layout.addRow(self.model_label, self.model_path)

        self.classes_label = QtWidgets.QLabel()
        self.classes_edit = QtWidgets.QLineEdit("metin,boss,potwory")
        layout.addRow(self.classes_label, self.classes_edit)

        self.templates_label = QtWidgets.QLabel()
        tmpl_widget = QtWidgets.QWidget()
        tmpl_layout = QtWidgets.QHBoxLayout(tmpl_widget)
        tmpl_layout.setContentsMargins(0, 0, 0, 0)
        self.templates_dir_edit = QtWidgets.QLineEdit("assets/templates")
        self.btn_templates_dir = QtWidgets.QPushButton()
        tmpl_layout.addWidget(self.templates_dir_edit)
        tmpl_layout.addWidget(self.btn_templates_dir)
        layout.addRow(self.templates_label, tmpl_widget)

        self.btn_templates_dir.clicked.connect(self.browse_templates_dir)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setTitle(QtCore.QCoreApplication.translate("MainWindow", "Ustawienia"))
        self.title_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Tytuł okna:")
        )
        self.model_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Ścieżka modelu YOLO:")
        )
        self.classes_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Klasy obiektów:")
        )
        self.templates_label.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Katalog szablonów:")
        )
        self.title_edit.setPlaceholderText(
            QtCore.QCoreApplication.translate(
                "MainWindow", "Fragment tytułu okna (np. Metin2)"
            )
        )
        self.btn_templates_dir.setText(
            QtCore.QCoreApplication.translate("MainWindow", "Wybierz…")
        )

    def browse_templates_dir(self) -> None:
        """Open a directory chooser for template path."""
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            QtCore.QCoreApplication.translate(
                "MainWindow", "Wybierz katalog z szablonami"
            ),
            self.templates_dir_edit.text(),
        )
        if path:
            self.templates_dir_edit.setText(path)

    def get_config(self) -> dict:
        classes = [c.strip() for c in self.classes_edit.text().split(",") if c.strip()]
        return {
            "window": {"title_substr": self.title_edit.text().strip()},
            "paths": {
                "templates_dir": self.templates_dir_edit.text().strip(),
                "model": self.model_path.text().strip(),
            },
            "detector": {
                "classes": classes,
                "conf_thr": 0.5,
                "iou_thr": 0.45,
            },
        }
