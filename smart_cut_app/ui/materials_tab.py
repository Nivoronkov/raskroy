from typing import Dict, List

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from core.models import CalculationResult, MaterialCatalogItem, Part
from data.materials_catalog_repository import load_materials_catalog


class MaterialsTab(QWidget):
    HEADERS = [
        "Код материала",
        "Наименование",
        "Тип профиля",
        "Размер",
        "Марка стали",
        "Длина хлыста, мм",
        "Хлыстов на складе",
        "Хлыстов требуется",
        "Разница",
        "Статус",
    ]

    def __init__(self) -> None:
        super().__init__()

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.refresh_button = QPushButton("Обновить сводку")
        self.refresh_button.setEnabled(False)

        title_label = QLabel("Материалы проекта")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        layout = QVBoxLayout()
        layout.addWidget(title_label)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.table)
        self.setLayout(layout)

    def clear_table(self) -> None:
        self.table.setRowCount(0)

    def build_from_parts(
        self,
        parts: List[Part],
        calculation_result: CalculationResult | None = None,
    ) -> None:
        self.clear_table()

        catalog_items = load_materials_catalog()
        catalog_by_code: Dict[str, MaterialCatalogItem] = {
            item.material_code: item for item in catalog_items if item.is_active
        }

        used_material_codes = []
        for part in parts:
            code = (part.material_code or "").strip()
            if code and code not in used_material_codes:
                used_material_codes.append(code)

        required_new_bars_by_code: Dict[str, int] = {}
        if calculation_result is not None:
            for pattern in calculation_result.patterns:
                if pattern.source_type != "new":
                    continue
                code = pattern.material_code
                required_new_bars_by_code[code] = required_new_bars_by_code.get(code, 0) + 1

        for row_index, material_code in enumerate(used_material_codes):
            catalog_item = catalog_by_code.get(material_code)

            if catalog_item is not None:
                name = catalog_item.name
                profile_type = catalog_item.profile_type
                size = catalog_item.size
                steel_grade = catalog_item.steel_grade
                stock_length_mm = catalog_item.stock_length_mm
                available_stock_bars = catalog_item.available_stock_bars
            else:
                name = ""
                profile_type = ""
                size = ""
                steel_grade = ""
                stock_length_mm = 0
                available_stock_bars = 0

            required_new_bars = required_new_bars_by_code.get(material_code, 0)
            difference = available_stock_bars - required_new_bars

            if required_new_bars == 0:
                status = "Не рассчитано"
            elif difference >= 0:
                status = "Хватает"
            elif available_stock_bars == 0:
                status = "Нет на складе"
            else:
                status = "Недостаточно"

            self.table.insertRow(row_index)

            values = [
                material_code,
                name,
                profile_type,
                size,
                steel_grade,
                str(stock_length_mm),
                str(available_stock_bars),
                str(required_new_bars),
                str(difference),
                status,
            ]

            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(value))

    def set_materials(self, materials) -> None:
        """
        Оставляем для совместимости с уже существующим кодом открытия проекта.
        Теперь вкладка материалов формируется автоматически, поэтому здесь просто очищаем таблицу.
        """
        self.clear_table()