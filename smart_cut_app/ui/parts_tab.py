from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from core.models import Part
from data.demo_data import get_demo_parts
from ui.part_material_select_dialog import PartMaterialSelectDialog


class PartsTab(QWidget):
    HEADERS = [
        "Обозначение",
        "Наименование детали",
        "Код материала",
        "Материал",
        "Длина, мм",
        "Количество",
        "Узел",
        "Примечание",
    ]

    COL_DESIGNATION = 0
    COL_NAME = 1
    COL_MATERIAL_CODE = 2
    COL_MATERIAL_NAME = 3
    COL_LENGTH = 4
    COL_QUANTITY = 5
    COL_ASSEMBLY = 6
    COL_NOTE = 7

    def __init__(self) -> None:
        super().__init__()

        self.material_history: Dict[str, str] = {}

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_MATERIAL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_NOTE, QHeaderView.ResizeMode.Stretch)

        self.add_button = QPushButton("Добавить строку")
        self.choose_material_button = QPushButton("Выбрать материал")
        self.assign_material_button = QPushButton("Назначить из списка")
        self.remove_button = QPushButton("Удалить выбранные")
        self.load_demo_button = QPushButton("Загрузить демо-детали")

        self.quick_material_combo = QComboBox()
        self.quick_material_combo.setMinimumWidth(320)

        self.add_button.clicked.connect(self.add_empty_row)
        self.choose_material_button.clicked.connect(self.choose_material_for_selected_rows)
        self.assign_material_button.clicked.connect(self.assign_material_from_quick_list)
        self.remove_button.clicked.connect(self.remove_selected_rows)
        self.load_demo_button.clicked.connect(self.load_demo_data)

        from PySide6.QtGui import QShortcut, QKeySequence
        from PySide6.QtCore import Qt as _Qt
        _del = QShortcut(QKeySequence(_Qt.Key.Key_Delete), self.table)
        _del.setContext(_Qt.ShortcutContext.WidgetShortcut)
        _del.activated.connect(self.remove_selected_rows)

        title_label = QLabel("Детали")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("Быстрый выбор материала:"))
        quick_layout.addWidget(self.quick_material_combo, 1)
        quick_layout.addWidget(self.assign_material_button)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.choose_material_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.load_demo_button)
        button_layout.addStretch()

        main_layout = QVBoxLayout()
        main_layout.addWidget(title_label)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(quick_layout)
        main_layout.addWidget(self.table)

        self.setLayout(main_layout)

        self.refresh_material_history()

    def add_empty_row(self) -> None:
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)

        self._set_combo_to_row(row_index, self.COL_DESIGNATION, "")
        self._set_combo_to_row(row_index, self.COL_NAME, "")

    def _set_combo_to_row(self, row_index: int, column_index: int, current_value: str) -> None:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        values = self._collect_existing_values(column_index)

        combo.addItem("")
        for value in values:
            if value:
                combo.addItem(value)

        if current_value and combo.findText(current_value) < 0:
            combo.addItem(current_value)

        combo.setCurrentText(current_value)

        combo.lineEdit().editingFinished.connect(self.refresh_combos)
        combo.currentTextChanged.connect(self.refresh_combos)

        self.table.setCellWidget(row_index, column_index, combo)

    def _collect_existing_values(self, column_index: int) -> List[str]:
        values = []

        for row_index in range(self.table.rowCount()):
            value = self._get_cell_or_widget_text(row_index, column_index).strip()
            if value and value not in values:
                values.append(value)

        return values

    def refresh_combos(self) -> None:
        designation_values = self._collect_existing_values(self.COL_DESIGNATION)
        name_values = self._collect_existing_values(self.COL_NAME)

        for row_index in range(self.table.rowCount()):
            self._refresh_combo_in_cell(row_index, self.COL_DESIGNATION, designation_values)
            self._refresh_combo_in_cell(row_index, self.COL_NAME, name_values)

    def _refresh_combo_in_cell(self, row_index: int, column_index: int, values: List[str]) -> None:
        combo = self.table.cellWidget(row_index, column_index)
        if not isinstance(combo, QComboBox):
            return

        current_text = combo.currentText().strip()

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("")
        for value in values:
            if value:
                combo.addItem(value)

        if current_text and combo.findText(current_text) < 0:
            combo.addItem(current_text)

        combo.setCurrentText(current_text)
        combo.blockSignals(False)

    def choose_material_for_selected_rows(self) -> None:
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            QMessageBox.information(
                self,
                "Нет выбора",
                "Сначала выберите одну или несколько строк деталей, которым нужно назначить материал.",
            )
            return

        dialog = PartMaterialSelectDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.selected_item is None:
            return

        for row_index in selected_rows:
            self._set_material_to_row(
                row_index=row_index,
                material_code=dialog.selected_item.material_code,
                material_name=dialog.selected_item.name,
            )

        self.refresh_material_history()

    def assign_material_from_quick_list(self) -> None:
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            QMessageBox.information(
                self,
                "Нет выбора",
                "Сначала выберите одну или несколько строк деталей.",
            )
            return

        material_code = self.quick_material_combo.currentData()
        if not material_code:
            QMessageBox.information(
                self,
                "Материал не выбран",
                "Выберите материал в списке быстрого выбора.",
            )
            return

        material_name = self.material_history.get(material_code, "")
        if not material_name:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не удалось определить наименование выбранного материала.",
            )
            return

        for row_index in selected_rows:
            self._set_material_to_row(
                row_index=row_index,
                material_code=material_code,
                material_name=material_name,
            )

        self.refresh_material_history()

    def _set_material_to_row(self, row_index: int, material_code: str, material_name: str) -> None:
        code_item = QTableWidgetItem(material_code)
        name_item = QTableWidgetItem(material_name)

        self.table.setItem(row_index, self.COL_MATERIAL_CODE, code_item)
        self.table.setItem(row_index, self.COL_MATERIAL_NAME, name_item)

        if material_code and material_name:
            self.material_history[material_code] = material_name

    def refresh_material_history(self) -> None:
        current_code = self.quick_material_combo.currentData()

        history: Dict[str, str] = {}

        for row_index in range(self.table.rowCount()):
            material_code = self._get_cell_or_widget_text(row_index, self.COL_MATERIAL_CODE).strip()
            material_name = self._get_cell_or_widget_text(row_index, self.COL_MATERIAL_NAME).strip()

            if material_code and material_name:
                history[material_code] = material_name

        self.material_history = history

        self.quick_material_combo.blockSignals(True)
        self.quick_material_combo.clear()
        self.quick_material_combo.addItem("— Выберите материал —", "")

        for code, name in sorted(self.material_history.items()):
            self.quick_material_combo.addItem(f"{code} | {name}", code)

        if current_code:
            index = self.quick_material_combo.findData(current_code)
            if index >= 0:
                self.quick_material_combo.setCurrentIndex(index)

        self.quick_material_combo.blockSignals(False)

    def _get_selected_rows(self) -> List[int]:
        return sorted({index.row() for index in self.table.selectedIndexes()})

    def remove_selected_rows(self) -> None:
        selected_rows = sorted(
            {index.row() for index in self.table.selectedIndexes()},
            reverse=True,
        )
        for row_index in selected_rows:
            self.table.removeRow(row_index)

        self.refresh_combos()
        self.refresh_material_history()

    def clear_table(self) -> None:
        self.table.setRowCount(0)
        self.refresh_material_history()

    def load_demo_data(self) -> None:
        self.clear_table()
        for part in get_demo_parts():
            self.add_part(part)

    def set_parts(self, parts: List[Part]) -> None:
        self.clear_table()
        for part in parts:
            self.add_part(part)

    def add_part(self, part: Part) -> None:
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)

        self._set_combo_to_row(row_index, self.COL_DESIGNATION, part.designation)
        self._set_combo_to_row(row_index, self.COL_NAME, part.name)

        values = {
            self.COL_MATERIAL_CODE: part.material_code,
            self.COL_MATERIAL_NAME: "",
            self.COL_LENGTH: str(part.length_mm),
            self.COL_QUANTITY: str(part.quantity),
            self.COL_ASSEMBLY: part.assembly,
            self.COL_NOTE: part.note,
        }

        for column_index, value in values.items():
            item = QTableWidgetItem(value)
            if column_index in (self.COL_LENGTH, self.COL_QUANTITY):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_index, column_index, item)

        self.refresh_combos()
        self.refresh_material_history()

    def get_parts(self) -> List[Part]:
        parts: List[Part] = []

        for row_index in range(self.table.rowCount()):
            designation = self._get_cell_or_widget_text(row_index, self.COL_DESIGNATION)
            name = self._get_cell_or_widget_text(row_index, self.COL_NAME)
            material_code = self._get_cell_or_widget_text(row_index, self.COL_MATERIAL_CODE)
            length_mm = self._to_int(self._get_cell_or_widget_text(row_index, self.COL_LENGTH))
            quantity = self._to_int(self._get_cell_or_widget_text(row_index, self.COL_QUANTITY))
            assembly = self._get_cell_or_widget_text(row_index, self.COL_ASSEMBLY)
            note = self._get_cell_or_widget_text(row_index, self.COL_NOTE)

            if not any([
                designation,
                name,
                material_code,
                self._get_cell_or_widget_text(row_index, self.COL_LENGTH),
                self._get_cell_or_widget_text(row_index, self.COL_QUANTITY),
                assembly,
                note,
            ]):
                continue

            parts.append(
                Part(
                    id=f"PART-{row_index + 1:03d}",
                    designation=designation,
                    name=name,
                    material_code=material_code,
                    length_mm=length_mm,
                    quantity=quantity,
                    assembly=assembly,
                    note=note,
                )
            )

        return parts

    def _get_cell_or_widget_text(self, row: int, column: int) -> str:
        widget = self.table.cellWidget(row, column)
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()

        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    @staticmethod
    def _to_int(value: str) -> int:
        if not value:
            return 0
        try:
            return int(float(value.replace(",", ".")))
        except ValueError:
            return 0