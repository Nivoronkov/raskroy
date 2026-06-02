from typing import List, Optional

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from core.models import MaterialCatalogItem
from data.materials_catalog_repository import (
    MaterialsCatalogError,
    load_materials_catalog,
)


class PartMaterialSelectDialog(QDialog):
    HEADERS = [
        "ID",
        "Код материала",
        "Наименование",
        "Тип профиля",
        "Размер",
        "Марка стали",
        "Длина хлыста, мм",
        "Хлыстов на складе",
        "Примечание",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.selected_item: Optional[MaterialCatalogItem] = None
        self.all_items: List[MaterialCatalogItem] = []

        self.setWindowTitle("Выбор материала для детали")
        self.resize(1100, 520)

        title_label = QLabel("Выбор материала для детали")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по коду, наименованию, размеру, марке")
        self.search_edit.textChanged.connect(self.apply_filter)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.accept_selected)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)

        self.refresh_button = QPushButton("Обновить")
        self.select_button = QPushButton("Выбрать")
        self.cancel_button = QPushButton("Отмена")

        self.refresh_button.clicked.connect(self.load_data)
        self.select_button.clicked.connect(self.accept_selected)
        self.cancel_button.clicked.connect(self.reject)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Поиск:"))
        top_layout.addWidget(self.search_edit)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.select_button)
        buttons_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addWidget(title_label)
        layout.addLayout(top_layout)
        layout.addWidget(self.table)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

        self.load_data()

    def load_data(self) -> None:
        try:
            self.all_items = [item for item in load_materials_catalog() if item.is_active]
            self.apply_filter()
        except MaterialsCatalogError as exc:
            QMessageBox.warning(self, "Ошибка загрузки", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Непредвиденная ошибка:\n{exc}")

    def apply_filter(self) -> None:
        search_text = self.search_edit.text().strip().lower()

        filtered = []
        for item in self.all_items:
            blob = " ".join([
                item.material_code,
                item.name,
                item.profile_type,
                item.size,
                item.steel_grade,
                item.note,
            ]).lower()

            if search_text and search_text not in blob:
                continue

            filtered.append(item)

        self._fill_table(filtered)

    def _fill_table(self, items: List[MaterialCatalogItem]) -> None:
        self.table.setRowCount(0)

        for row_index, item in enumerate(items):
            self.table.insertRow(row_index)

            values = [
                item.id,
                item.material_code,
                item.name,
                item.profile_type,
                item.size,
                item.steel_grade,
                str(item.stock_length_mm),
                str(item.available_stock_bars),
                item.note,
            ]

            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(value))

    def accept_selected(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Нет выбора", "Выберите материал из справочника.")
            return

        row = selected_rows[0].row()
        selected_id_item = self.table.item(row, 0)
        if selected_id_item is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось определить выбранный материал.")
            return

        selected_id = selected_id_item.text().strip()

        for item in self.all_items:
            if item.id == selected_id:
                self.selected_item = item
                self.accept()
                return

        QMessageBox.warning(self, "Ошибка", "Выбранный материал не найден в справочнике.")