from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from core.models import Leftover
from ui.material_catalog_select_dialog import MaterialCatalogSelectDialog


class LeftoverEditDialog(QDialog):
    def __init__(self, leftover: Optional[Leftover] = None, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Остаток")
        self.resize(560, 320)

        self.is_edit_mode = leftover is not None

        self.id_edit = QLineEdit()
        self.id_edit.setReadOnly(True)

        self.material_code_edit = QLineEdit()
        self.material_code_edit.setReadOnly(True)

        self.material_name_edit = QLineEdit()
        self.material_name_edit.setReadOnly(True)

        self.select_material_button = QPushButton("Выбрать материал")
        self.select_material_button.clicked.connect(self.select_material)

        self.length_spin = QSpinBox()
        self.length_spin.setRange(1, 100000)
        self.length_spin.setSuffix(" мм")

        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 100000)
        self.quantity_spin.setValue(1)

        self.stock_length_spin = QSpinBox()
        self.stock_length_spin.setRange(0, 100000)
        self.stock_length_spin.setSuffix(" мм")

        self.source_pattern_edit = QLineEdit()
        self.note_edit = QLineEdit()

        if leftover is not None:
            self.id_edit.setText(leftover.id)
            self.material_code_edit.setText(leftover.material_code)
            self.material_name_edit.setText(leftover.material_name)
            self.length_spin.setValue(leftover.length_mm)
            self.quantity_spin.setValue(1)
            self.quantity_spin.setEnabled(False)
            self.stock_length_spin.setValue(leftover.stock_length_mm)
            self.source_pattern_edit.setText(leftover.source_pattern_id)
            self.note_edit.setText(leftover.note)

            self.select_material_button.setEnabled(False)

        form_layout = QFormLayout()

        material_layout = QHBoxLayout()
        material_layout.addWidget(self.material_code_edit, 2)
        material_layout.addWidget(self.material_name_edit, 4)
        material_layout.addWidget(self.select_material_button, 2)

        form_layout.addRow("ID остатка:", self.id_edit)
        form_layout.addRow("Материал:", material_layout)
        form_layout.addRow("Длина остатка:", self.length_spin)
        form_layout.addRow("Количество:", self.quantity_spin)
        form_layout.addRow("Исходная длина хлыста:", self.stock_length_spin)
        form_layout.addRow("Источник:", self.source_pattern_edit)
        form_layout.addRow("Примечание:", self.note_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def select_material(self) -> None:
        dialog = MaterialCatalogSelectDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.selected_item is None:
            return

        self.material_code_edit.setText(dialog.selected_item.material_code)
        self.material_name_edit.setText(dialog.selected_item.name)

        if self.stock_length_spin.value() == 0:
            self.stock_length_spin.setValue(dialog.selected_item.stock_length_mm)

    def get_leftover(self) -> Leftover:
        return Leftover(
            id=self.id_edit.text().strip(),
            material_code=self.material_code_edit.text().strip(),
            material_name=self.material_name_edit.text().strip(),
            length_mm=self.length_spin.value(),
            stock_length_mm=self.stock_length_spin.value(),
            source_pattern_id=self.source_pattern_edit.text().strip(),
            note=self.note_edit.text().strip(),
        )

    def get_quantity(self) -> int:
        return self.quantity_spin.value()