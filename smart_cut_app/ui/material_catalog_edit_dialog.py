from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
)

from core.models import MaterialCatalogItem
from data.materials_catalog_repository import (
    PROFILE_TYPE_MAP,
    generate_material_code,
    generate_material_name,
    normalize_size,
)


class MaterialCatalogEditDialog(QDialog):
    def __init__(self, item: Optional[MaterialCatalogItem] = None, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Материал справочника")
        self.resize(520, 360)

        self.item_id = item.id if item is not None else ""

        self.profile_type_combo = QComboBox()
        for profile_type in PROFILE_TYPE_MAP.keys():
            self.profile_type_combo.addItem(profile_type)

        self.size_edit = QLineEdit()
        self.steel_grade_edit = QLineEdit()

        self.stock_length_spin = QSpinBox()
        self.stock_length_spin.setRange(0, 100000)
        self.stock_length_spin.setSuffix(" мм")

        self.available_stock_bars_spin = QSpinBox()
        self.available_stock_bars_spin.setRange(0, 100000)
        self.available_stock_bars_spin.setValue(0)

        self.mass_per_meter_spin = QDoubleSpinBox()
        self.mass_per_meter_spin.setRange(0, 100000)
        self.mass_per_meter_spin.setDecimals(3)
        self.mass_per_meter_spin.setSuffix(" кг")

        self.price_per_meter_spin = QDoubleSpinBox()
        self.price_per_meter_spin.setRange(0, 100000000)
        self.price_per_meter_spin.setDecimals(2)

        self.note_edit = QLineEdit()
        self.external_code_edit = QLineEdit()

        self.code_value_label = QLabel("")
        self.name_value_label = QLabel("")

        self.profile_type_combo.currentTextChanged.connect(self.update_generated_fields)
        self.size_edit.textChanged.connect(self.update_generated_fields)
        self.steel_grade_edit.textChanged.connect(self.update_generated_fields)

        if item is not None:
            index = self.profile_type_combo.findText(item.profile_type)
            if index >= 0:
                self.profile_type_combo.setCurrentIndex(index)

            self.size_edit.setText(item.size)
            self.steel_grade_edit.setText(item.steel_grade)
            self.stock_length_spin.setValue(item.stock_length_mm)
            self.available_stock_bars_spin.setValue(item.available_stock_bars)
            self.mass_per_meter_spin.setValue(item.mass_per_meter)
            self.price_per_meter_spin.setValue(item.price_per_meter)
            self.note_edit.setText(item.note)
            self.external_code_edit.setText(item.external_code)

        self.update_generated_fields()

        form_layout = QFormLayout()
        form_layout.addRow("Тип профиля:", self.profile_type_combo)
        form_layout.addRow("Размер:", self.size_edit)
        form_layout.addRow("Марка стали:", self.steel_grade_edit)
        form_layout.addRow("Длина хлыста:", self.stock_length_spin)
        form_layout.addRow("Хлыстов на складе:", self.available_stock_bars_spin)
        form_layout.addRow("Масса 1 м:", self.mass_per_meter_spin)
        form_layout.addRow("Цена за 1 м:", self.price_per_meter_spin)
        form_layout.addRow("Код 1С / внешний ID:", self.external_code_edit)
        form_layout.addRow("Примечание:", self.note_edit)

        generated_layout = QVBoxLayout()
        generated_layout.addLayout(self._make_readonly_row("Код материала:", self.code_value_label))
        generated_layout.addLayout(self._make_readonly_row("Наименование:", self.name_value_label))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        main_layout = QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addLayout(generated_layout)
        main_layout.addWidget(buttons)

        self.setLayout(main_layout)

    def _make_readonly_row(self, title: str, value_label: QLabel) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel(title))
        layout.addWidget(value_label, 1)
        return layout

    def update_generated_fields(self) -> None:
        profile_type = self.profile_type_combo.currentText().strip()
        size = normalize_size(self.size_edit.text())
        steel_grade = self.steel_grade_edit.text().strip().upper()

        material_code = generate_material_code(profile_type, size, steel_grade)
        material_name = generate_material_name(profile_type, size, steel_grade)

        self.code_value_label.setText(material_code)
        self.name_value_label.setText(material_name)

    def get_item(self) -> MaterialCatalogItem:
        profile_type = self.profile_type_combo.currentText().strip()
        size = normalize_size(self.size_edit.text())
        steel_grade = self.steel_grade_edit.text().strip().upper()
        material_code = generate_material_code(profile_type, size, steel_grade)
        material_name = generate_material_name(profile_type, size, steel_grade)

        return MaterialCatalogItem(
            id=self.item_id,
            material_code=material_code,
            name=material_name,
            profile_type=profile_type,
            profile_code=PROFILE_TYPE_MAP.get(profile_type, ""),
            size=size,
            steel_grade=steel_grade,
            stock_length_mm=self.stock_length_spin.value(),
            mass_per_meter=self.mass_per_meter_spin.value(),
            price_per_meter=self.price_per_meter_spin.value(),
            note=self.note_edit.text().strip(),
            is_active=True,
            external_code=self.external_code_edit.text().strip(),
            available_stock_bars=self.available_stock_bars_spin.value(),
        )