from __future__ import annotations

from PySide6 import QtCore, QtWidgets
from config.models import BuffConfig


class AdvancedPanel(QtWidgets.QWidget):
    """Tab with advanced agent options."""

    config_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        # --- auto loot group ---
        loot_box = QtWidgets.QGroupBox("Automatyczne zbieranie i ekwipunek")
        loot_layout = QtWidgets.QVBoxLayout(loot_box)
        self.auto_loot_chk = QtWidgets.QCheckBox("Auto loot")
        self.inventory_manager_chk = QtWidgets.QCheckBox("Zarządzanie ekwipunkiem")
        loot_layout.addWidget(self.auto_loot_chk)
        loot_layout.addWidget(self.inventory_manager_chk)
        layout.addWidget(loot_box)

        # --- buffs and potions ---
        buff_box = QtWidgets.QGroupBox("Buffy i mikstury")
        buff_layout = QtWidgets.QFormLayout(buff_box)
        self.hp_key_edit = QtWidgets.QLineEdit()
        self.hp_thr_spin = QtWidgets.QSpinBox()
        self.hp_thr_spin.setRange(0, 100)
        self.mp_key_edit = QtWidgets.QLineEdit()
        self.mp_thr_spin = QtWidgets.QSpinBox()
        self.mp_thr_spin.setRange(0, 100)
        buff_layout.addRow("Klawisz HP", self.hp_key_edit)
        buff_layout.addRow("Próg HP", self.hp_thr_spin)
        buff_layout.addRow("Klawisz MP", self.mp_key_edit)
        buff_layout.addRow("Próg MP", self.mp_thr_spin)
        self.buff_table = QtWidgets.QTableWidget(0, 2)
        self.buff_table.setHorizontalHeaderLabels(["Klawisz", "Interwał [s]"])
        buff_layout.addRow(self.buff_table)
        buff_add_row = QtWidgets.QHBoxLayout()
        self.buff_key_input = QtWidgets.QLineEdit()
        self.buff_interval_input = QtWidgets.QSpinBox()
        self.buff_interval_input.setRange(1, 3600)
        self.buff_add_btn = QtWidgets.QPushButton("Dodaj buff")
        self.buff_remove_btn = QtWidgets.QPushButton("Usuń buff")
        buff_add_row.addWidget(self.buff_key_input)
        buff_add_row.addWidget(self.buff_interval_input)
        buff_add_row.addWidget(self.buff_add_btn)
        buff_add_row.addWidget(self.buff_remove_btn)
        buff_layout.addRow(buff_add_row)
        layout.addWidget(buff_box)

        # --- humanizer ---
        hum_box = QtWidgets.QGroupBox("Anty-stuck & humanizacja")
        hum_layout = QtWidgets.QFormLayout(hum_box)
        self.stuck_window_spin = QtWidgets.QDoubleSpinBox()
        self.stuck_window_spin.setRange(0.1, 5.0)
        self.stuck_window_spin.setSingleStep(0.1)
        self.pause_jitter_spin = QtWidgets.QDoubleSpinBox()
        self.pause_jitter_spin.setRange(0.0, 1.0)
        self.pause_jitter_spin.setSingleStep(0.01)
        self.cursor_jitter_spin = QtWidgets.QDoubleSpinBox()
        self.cursor_jitter_spin.setRange(0.0, 20.0)
        self.cursor_jitter_spin.setSingleStep(0.1)
        hum_layout.addRow("Okno stuck", self.stuck_window_spin)
        hum_layout.addRow("Pause jitter", self.pause_jitter_spin)
        hum_layout.addRow("Cursor jitter", self.cursor_jitter_spin)
        layout.addWidget(hum_box)

        # --- minimap navigation ---
        nav_box = QtWidgets.QGroupBox("Nawigacja po minimapie")
        nav_layout = QtWidgets.QHBoxLayout(nav_box)
        self.pathfinding_chk = QtWidgets.QCheckBox("Pathfinding")
        self.path_start_btn = QtWidgets.QPushButton("Start")
        self.path_stop_btn = QtWidgets.QPushButton("Stop")
        nav_layout.addWidget(self.pathfinding_chk)
        nav_layout.addWidget(self.path_start_btn)
        nav_layout.addWidget(self.path_stop_btn)
        layout.addWidget(nav_box)

        # --- multi client ---
        mc_box = QtWidgets.QGroupBox("Multi-client")
        mc_layout = QtWidgets.QFormLayout(mc_box)
        self.clients_spin = QtWidgets.QSpinBox()
        self.clients_spin.setRange(1, 8)
        self.rotation_edit = QtWidgets.QLineEdit()
        mc_layout.addRow("Klienci", self.clients_spin)
        mc_layout.addRow("Rotacja", self.rotation_edit)
        layout.addWidget(mc_box)

        layout.addStretch()

        # connect signals
        for w in [
            self.auto_loot_chk,
            self.inventory_manager_chk,
            self.hp_key_edit,
            self.hp_thr_spin,
            self.mp_key_edit,
            self.mp_thr_spin,
            self.stuck_window_spin,
            self.pause_jitter_spin,
            self.cursor_jitter_spin,
            self.pathfinding_chk,
            self.clients_spin,
            self.rotation_edit,
        ]:
            if hasattr(w, "toggled"):
                w.toggled.connect(self.config_changed)
            elif hasattr(w, "editingFinished"):
                w.editingFinished.connect(self.config_changed)
            else:
                w.valueChanged.connect(self.config_changed)  # type: ignore[arg-type]

        self.buff_add_btn.clicked.connect(self.add_buff)
        self.buff_remove_btn.clicked.connect(self.remove_buff)

    # ---- buff management ----
    def add_buff(self) -> None:
        key = self.buff_key_input.text().strip()
        if not key:
            QtWidgets.QMessageBox.warning(
                self,
                "Błąd",
                "Klawisz buffa nie może być pusty",
            )
            return
        interval = self.buff_interval_input.value()
        row = self.buff_table.rowCount()
        self.buff_table.insertRow(row)
        self.buff_table.setItem(row, 0, QtWidgets.QTableWidgetItem(key))
        self.buff_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(interval)))
        self.buff_key_input.clear()
        self.buff_interval_input.setValue(1)
        self.config_changed.emit()

    def remove_buff(self) -> None:
        rows = {idx.row() for idx in self.buff_table.selectedIndexes()}
        for row in sorted(rows, reverse=True):
            self.buff_table.removeRow(row)
        if rows:
            self.config_changed.emit()

    # ---- config binding ----
    def load_from_config(self, cfg) -> None:
        self.auto_loot_chk.setChecked(getattr(cfg, "auto_loot", False))
        self.inventory_manager_chk.setChecked(getattr(cfg, "inventory_manager", False))
        pot = getattr(cfg, "potions", None)
        if pot:
            self.hp_key_edit.setText(getattr(pot, "hp_key", ""))
            self.hp_thr_spin.setValue(int(getattr(pot, "hp_threshold", 0)))
            self.mp_key_edit.setText(getattr(pot, "mp_key", ""))
            self.mp_thr_spin.setValue(int(getattr(pot, "mp_threshold", 0)))
        self.buff_table.setRowCount(0)
        for b in getattr(cfg, "buffs", []) or []:
            row = self.buff_table.rowCount()
            self.buff_table.insertRow(row)
            self.buff_table.setItem(row, 0, QtWidgets.QTableWidgetItem(b.key))
            self.buff_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(b.interval_sec)))
        self.stuck_window_spin.setValue(getattr(getattr(cfg, "stuck", None), "window", 0.8))
        self.pause_jitter_spin.setValue(getattr(getattr(cfg, "humanizer", None), "pause_jitter", 0.05))
        self.cursor_jitter_spin.setValue(getattr(getattr(cfg, "humanizer", None), "cursor_jitter", 2.0))
        self.pathfinding_chk.setChecked(getattr(cfg, "pathfinding", False))
        mc = getattr(cfg, "multi_client", None)
        if mc:
            self.clients_spin.setValue(getattr(mc, "count", 1))
            self.rotation_edit.setText(
                ",".join(str(i) for i in getattr(mc, "rotation", []))
            )

    def update_config(self, cfg) -> None:
        cfg.auto_loot = self.auto_loot_chk.isChecked()
        cfg.inventory_manager = self.inventory_manager_chk.isChecked()
        if not hasattr(cfg, "potions"):
            from config.models import PotionsConfig

            cfg.potions = PotionsConfig()
        cfg.potions.hp_key = self.hp_key_edit.text().strip()
        cfg.potions.hp_threshold = int(self.hp_thr_spin.value())
        cfg.potions.mp_key = self.mp_key_edit.text().strip()
        cfg.potions.mp_threshold = int(self.mp_thr_spin.value())
        buffs = []
        for row in range(self.buff_table.rowCount()):
            key_item = self.buff_table.item(row, 0)
            interval_item = self.buff_table.item(row, 1)
            if key_item is None or not key_item.text().strip():
                raise ValueError("Klawisz buffa nie może być pusty")
            buffs.append(
                BuffConfig(key=key_item.text().strip(), interval_sec=float(interval_item.text()))
            )
        cfg.buffs = buffs
        cfg.stuck.window = float(self.stuck_window_spin.value())
        cfg.humanizer.pause_jitter = float(self.pause_jitter_spin.value())
        cfg.humanizer.cursor_jitter = float(self.cursor_jitter_spin.value())
        cfg.pathfinding = self.pathfinding_chk.isChecked()
        if not hasattr(cfg, "multi_client"):
            from config.models import MultiClientConfig

            cfg.multi_client = MultiClientConfig()
        cfg.multi_client.count = int(self.clients_spin.value())
        rot_text = self.rotation_edit.text().strip()
        cfg.multi_client.rotation = [int(x) for x in rot_text.split(",") if x.strip().isdigit()]
        self.config_changed.emit()
