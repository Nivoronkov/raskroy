from typing import List, Optional

from PySide6.QtWidgets import (
    QAbstractItemView,
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

from core.models import MaterialCatalogItem
from data.materials_catalog_repository import (
    MaterialsCatalogError,
    add_catalog_item,
    delete_catalog_items_by_ids,
    find_duplicate_catalog_item,
    get_next_catalog_item_id,
    load_materials_catalog,
    update_catalog_item,
)
from ui.material_catalog_edit_dialog import MaterialCatalogEditDialog


class MaterialsCatalogTab(QWidget):
    HEADERS = [
        "ID",
        "Код материала",
        "Наименование",
        "Тип профиля",
        "Размер",
        "Марка стали",
        "Длина хлыста, мм",
        "Хлыстов на складе",
        "Масса 1 м, кг",
        "Цена за 1 м",
        "Код 1С / внешний ID",
        "Примечание",
    ]

    def __init__(self) -> None:
        super().__init__()

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)

        self.refresh_button = QPushButton("Обновить")
        self.add_button = QPushButton("Добавить")
        self.edit_button = QPushButton("Редактировать")
        self.delete_button = QPushButton("Удалить")

        self.refresh_button.clicked.connect(self.refresh_data)
        self.add_button.clicked.connect(self.add_item)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)

        # Клавиша Delete на таблице — то же, что кнопка «Удалить»
        from PySide6.QtGui import QShortcut, QKeySequence
        from PySide6.QtCore import Qt as _Qt
        _del = QShortcut(QKeySequence(_Qt.Key.Key_Delete), self.table)
        _del.setContext(_Qt.ShortcutContext.WidgetShortcut)
        _del.activated.connect(self.delete_selected)

        title_label = QLabel("Справочник материалов")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(title_label)
        layout.addLayout(button_layout)
        layout.addWidget(self.table)

        self.setLayout(layout)

        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            items = load_materials_catalog()
            self._fill_table(items)
        except MaterialsCatalogError as exc:
            QMessageBox.warning(self, "Ошибка загрузки", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Непредвиденная ошибка:\n{exc}")

    def add_item(self) -> None:
        dialog = MaterialCatalogEditDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        item = dialog.get_item()
        item.id = get_next_catalog_item_id()

        error_text = self._validate_item(item)
        if error_text:
            QMessageBox.warning(self, "Некорректные данные", error_text)
            return

        duplicate = find_duplicate_catalog_item(
            profile_type=item.profile_type,
            size=item.size,
            steel_grade=item.steel_grade,
            stock_length_mm=item.stock_length_mm,
        )
        if duplicate is not None:
            QMessageBox.warning(
                self,
                "Дубликат",
                f"Такая позиция уже существует в справочнике:\n{duplicate.material_code}",
            )
            return

        try:
            add_catalog_item(item)
            self.refresh_data()
            QMessageBox.information(self, "Добавлено", "Материал добавлен в справочник.")
        except MaterialsCatalogError as exc:
            QMessageBox.warning(self, "Ошибка добавления", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Непредвиденная ошибка:\n{exc}")

    def edit_selected(self) -> None:
        item = self._get_single_selected_item()
        if item is None:
            return

        dialog = MaterialCatalogEditDialog(item=item, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        updated_item = dialog.get_item()
        updated_item.id = item.id

        error_text = self._validate_item(updated_item)
        if error_text:
            QMessageBox.warning(self, "Некорректные данные", error_text)
            return

        duplicate = find_duplicate_catalog_item(
            profile_type=updated_item.profile_type,
            size=updated_item.size,
            steel_grade=updated_item.steel_grade,
            stock_length_mm=updated_item.stock_length_mm,
            exclude_id=updated_item.id,
        )
        if duplicate is not None:
            QMessageBox.warning(
                self,
                "Дубликат",
                f"Такая позиция уже существует в справочнике:\n{duplicate.material_code}",
            )
            return

        try:
            update_catalog_item(updated_item)
            self.refresh_data()
            QMessageBox.information(self, "Сохранено", "Материал обновлен.")
        except MaterialsCatalogError as exc:
            QMessageBox.warning(self, "Ошибка редактирования", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Непредвиденная ошибка:\n{exc}")

    def delete_selected(self) -> None:
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)

        if not selected_rows:
            QMessageBox.information(self, "Нет выбора", "Выберите материалы для удаления.")
            return

        item_ids: List[str] = []
        for row_index in selected_rows:
            item = self.table.item(row_index, 0)
            if item:
                item_ids.append(item.text().strip())

        if not item_ids:
            QMessageBox.information(self, "Нет выбора", "Не удалось определить ID выбранных материалов.")
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Удалить выбранные материалы: {len(item_ids)} шт.?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted_count = delete_catalog_items_by_ids(item_ids)
            self.refresh_data()
            QMessageBox.information(self, "Удаление завершено", f"Удалено материалов: {deleted_count}")
        except MaterialsCatalogError as exc:
            QMessageBox.warning(self, "Ошибка удаления", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Непредвиденная ошибка:\n{exc}")

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
                str(item.mass_per_meter),
                str(item.price_per_meter),
                item.external_code,
                item.note,
            ]

            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _get_single_selected_item(self) -> Optional[MaterialCatalogItem]:
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})

        if not selected_rows:
            QMessageBox.information(self, "Нет выбора", "Выберите один материал для редактирования.")
            return None

        if len(selected_rows) > 1:
            QMessageBox.information(self, "Слишком много строк", "Для редактирования выберите только один материал.")
            return None

        row = selected_rows[0]

        return MaterialCatalogItem(
            id=self._get_cell_text(row, 0),
            material_code=self._get_cell_text(row, 1),
            name=self._get_cell_text(row, 2),
            profile_type=self._get_cell_text(row, 3),
            profile_code="",
            size=self._get_cell_text(row, 4),
            steel_grade=self._get_cell_text(row, 5),
            stock_length_mm=self._to_int(self._get_cell_text(row, 6)),
            available_stock_bars=self._to_int(self._get_cell_text(row, 7)),
            mass_per_meter=self._to_float(self._get_cell_text(row, 8)),
            price_per_meter=self._to_float(self._get_cell_text(row, 9)),
            external_code=self._get_cell_text(row, 10),
            note=self._get_cell_text(row, 11),
            is_active=True,
        )

    def _validate_item(self, item: MaterialCatalogItem) -> str:
        if not item.profile_type:
            return "Не выбран тип профиля."
        if not item.size:
            return "Не заполнен размер."
        if not item.steel_grade:
            return "Не заполнена марка стали."
        if item.stock_length_mm <= 0:
            return "Длина хлыста должна быть больше 0."
        if not item.material_code:
            return "Не удалось сформировать код материала."
        if not item.name:
            return "Не удалось сформировать наименование."
        return ""

    def _get_cell_text(self, row: int, column: int) -> str:
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

    @staticmethod
    def _to_float(value: str) -> float:
        if not value:
            return 0.0
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return 0.0