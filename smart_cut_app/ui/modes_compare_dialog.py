from typing import List, Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)


class ModesCompareDialog(QDialog):
    HEADERS = [
        "Код режима",
        "Режим",
        "Всего карт",
        "Новых хлыстов",
        "Использовано остатков",
        "Отход, мм",
        "Полезный остаток, мм",
        "Использование, %",
        "Ошибки",
    ]

    COL_MODE_CODE = 0
    COL_MODE_NAME = 1
    COL_PATTERNS = 2
    COL_NEW_BARS = 3
    COL_USED_LEFTOVERS = 4
    COL_WASTE = 5
    COL_USEFUL_LEFTOVER = 6
    COL_UTILIZATION = 7
    COL_ERRORS = 8

    def __init__(self, rows: List[dict], parent=None) -> None:
        super().__init__(parent)

        self.selected_mode_code: Optional[str] = None
        self.rows_data = rows

        self.setWindowTitle("Сравнение режимов расчета")
        self.resize(1200, 520)

        title_label = QLabel("Сравнение режимов расчета")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(0, True)

        self.apply_button = QPushButton("Применить выбранный режим")
        self.close_button = QPushButton("Закрыть")

        self.apply_button.clicked.connect(self.apply_selected_mode)
        self.close_button.clicked.connect(self.reject)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.apply_button)
        buttons_layout.addWidget(self.close_button)

        layout = QVBoxLayout()
        layout.addWidget(title_label)
        layout.addWidget(self.table)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

        self._fill_table(rows)
        self._highlight_best_values()

    def _fill_table(self, rows: List[dict]) -> None:
        for row_index, row in enumerate(rows):
            self.table.insertRow(row_index)

            values = [
                row["mode_code"],
                row["mode_name"],
                str(row["patterns_count"]),
                str(row["new_bars_count"]),
                str(row["used_leftovers_count"]),
                str(row["total_waste_mm"]),
                str(row["total_useful_leftover_mm"]),
                str(row["utilization_percent"]),
                row["errors_text"],
            ]

            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _highlight_best_values(self) -> None:
        valid_rows = [row for row in self.rows_data if not row["errors_text"]]
        if not valid_rows:
            return

        min_new_bars = min(row["new_bars_count"] for row in valid_rows)
        max_used_leftovers = max(row["used_leftovers_count"] for row in valid_rows)
        min_waste = min(row["total_waste_mm"] for row in valid_rows)
        max_utilization = max(row["utilization_percent"] for row in valid_rows)

        green = QColor(220, 255, 220)
        blue = QColor(220, 235, 255)
        yellow = QColor(255, 250, 210)
        pink = QColor(255, 230, 240)

        for row_index, row in enumerate(self.rows_data):
            if row["errors_text"]:
                continue

            if row["new_bars_count"] == min_new_bars:
                self._paint_cell(row_index, self.COL_NEW_BARS, green)

            if row["used_leftovers_count"] == max_used_leftovers:
                self._paint_cell(row_index, self.COL_USED_LEFTOVERS, blue)

            if row["total_waste_mm"] == min_waste:
                self._paint_cell(row_index, self.COL_WASTE, yellow)

            if row["utilization_percent"] == max_utilization:
                self._paint_cell(row_index, self.COL_UTILIZATION, pink)

    def _paint_cell(self, row: int, column: int, color: QColor) -> None:
        item = self.table.item(row, column)
        if item is not None:
            item.setBackground(color)

    def apply_selected_mode(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Нет выбора", "Выберите режим в таблице.")
            return

        row = selected_rows[0].row()
        mode_item = self.table.item(row, self.COL_MODE_CODE)
        if mode_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось определить выбранный режим.")
            return

        self.selected_mode_code = mode_item.text().strip()
        self.accept()