from typing import List, Optional

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from core.models import Leftover
from data.leftovers_repository import (
    LeftoversRepositoryError,
    add_leftover,
    delete_leftovers_by_ids,
    load_leftovers,
    update_leftover,
)
from ui.leftover_edit_dialog import LeftoverEditDialog


class LeftoversTab(QWidget):
    HEADERS = [
        "ID остатка",
        "Код материала",
        "Материал",
        "Длина остатка, мм",
        "Исходная длина хлыста, мм",
        "Источник",
        "Примечание",
    ]

    def __init__(self) -> None:
        super().__init__()

        self.all_leftovers: List[Leftover] = []

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
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по ID, коду материала, наименованию, примечанию")

        self.min_length_spin = QSpinBox()
        self.min_length_spin.setRange(0, 100000)
        self.min_length_spin.setSuffix(" мм")
        self.min_length_spin.setValue(0)

        self.refresh_button = QPushButton("Обновить")
        self.add_button = QPushButton("Добавить остаток")
        self.edit_button = QPushButton("Редактировать")
        self.delete_button = QPushButton("Удалить выбранные")
        self.reset_filter_button = QPushButton("Сбросить фильтры")

        self.refresh_button.clicked.connect(self.refresh_data)
        self.add_button.clicked.connect(self.add_leftover)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        self.reset_filter_button.clicked.connect(self.reset_filters)

        self.search_edit.textChanged.connect(self.apply_filters)
        self.min_length_spin.valueChanged.connect(self.apply_filters)

        title_label = QLabel("Полезные остатки")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Поиск:"))
        filter_layout.addWidget(self.search_edit)
        filter_layout.addWidget(QLabel("Мин. длина:"))
        filter_layout.addWidget(self.min_length_spin)
        filter_layout.addWidget(self.reset_filter_button)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(title_label)
        layout.addLayout(filter_layout)
        layout.addLayout(button_layout)
        layout.addWidget(self.table)

        self.setLayout(layout)

        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            self.all_leftovers = load_leftovers()
            self.apply_filters()
        except LeftoversRepositoryError as exc:
            QMessageBox.warning(self, "Ошибка загрузки остатков", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Непредвиденная ошибка при загрузке остатков:\n{exc}",
            )

    def apply_filters(self) -> None:
        search_text = self.search_edit.text().strip().lower()
        min_length = self.min_length_spin.value()

        filtered: List[Leftover] = []

        for item in self.all_leftovers:
            if item.length_mm < min_length:
                continue

            search_blob = " ".join([
                item.id,
                item.material_code,
                item.material_name,
                item.source_pattern_id,
                item.note,
            ]).lower()

            if search_text and search_text not in search_blob:
                continue

            filtered.append(item)

        self._fill_table(filtered)

    def reset_filters(self) -> None:
        self.search_edit.clear()
        self.min_length_spin.setValue(0)
        self.apply_filters()

    def add_leftover(self) -> None:
        dialog = LeftoverEditDialog(parent=self)
        dialog.id_edit.setText(self._generate_next_leftover_id())

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        leftover = dialog.get_leftover()
        quantity = dialog.get_quantity()

        validation_error = self._validate_leftover(leftover)
        if validation_error:
            QMessageBox.warning(self, "Некорректные данные", validation_error)
            return

        try:
            created_count = 0

            for _ in range(quantity):
                new_leftover = Leftover(
                    id=self._generate_next_leftover_id(),
                    material_code=leftover.material_code,
                    material_name=leftover.material_name,
                    length_mm=leftover.length_mm,
                    stock_length_mm=leftover.stock_length_mm,
                    source_pattern_id=leftover.source_pattern_id,
                    note=leftover.note,
                )
                add_leftover(new_leftover)
                created_count += 1

            self.refresh_data()
            QMessageBox.information(
                self,
                "Добавлено",
                f"В базу добавлено остатков: {created_count}",
            )

        except LeftoversRepositoryError as exc:
            QMessageBox.warning(self, "Ошибка добавления", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Непредвиденная ошибка при добавлении остатка:\n{exc}",
            )

    def edit_selected(self) -> None:
        leftover = self._get_single_selected_leftover()
        if leftover is None:
            return

        dialog = LeftoverEditDialog(leftover=leftover, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        updated_leftover = dialog.get_leftover()

        validation_error = self._validate_leftover(updated_leftover)
        if validation_error:
            QMessageBox.warning(self, "Некорректные данные", validation_error)
            return

        try:
            update_leftover(updated_leftover)
            self.refresh_data()
            QMessageBox.information(self, "Сохранено", "Остаток обновлен.")
        except LeftoversRepositoryError as exc:
            QMessageBox.warning(self, "Ошибка редактирования", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Непредвиденная ошибка при редактировании остатка:\n{exc}",
            )

    def delete_selected(self) -> None:
        selected_rows = sorted(
            {index.row() for index in self.table.selectedIndexes()},
            reverse=True,
        )

        if not selected_rows:
            QMessageBox.information(self, "Нет выбора", "Выберите остатки для удаления.")
            return

        leftover_ids: List[str] = []
        for row_index in selected_rows:
            item = self.table.item(row_index, 0)
            if item:
                leftover_ids.append(item.text().strip())

        if not leftover_ids:
            QMessageBox.information(self, "Нет выбора", "Не удалось определить ID выбранных остатков.")
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Удалить выбранные остатки: {len(leftover_ids)} шт.?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted_count = delete_leftovers_by_ids(leftover_ids)
            self.refresh_data()
            QMessageBox.information(
                self,
                "Удаление завершено",
                f"Удалено остатков: {deleted_count}",
            )
        except LeftoversRepositoryError as exc:
            QMessageBox.warning(self, "Ошибка удаления", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Непредвиденная ошибка при удалении остатков:\n{exc}",
            )

    def _fill_table(self, leftovers: List[Leftover]) -> None:
        self.table.setRowCount(0)

        for row_index, item in enumerate(leftovers):
            self.table.insertRow(row_index)

            values = [
                item.id,
                item.material_code,
                item.material_name,
                str(item.length_mm),
                str(item.stock_length_mm),
                item.source_pattern_id,
                item.note,
            ]

            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _get_single_selected_leftover(self) -> Optional[Leftover]:
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})

        if not selected_rows:
            QMessageBox.information(self, "Нет выбора", "Выберите один остаток для редактирования.")
            return None

        if len(selected_rows) > 1:
            QMessageBox.information(self, "Слишком много строк", "Для редактирования выберите только один остаток.")
            return None

        row = selected_rows[0]

        return Leftover(
            id=self._get_cell_text(row, 0),
            material_code=self._get_cell_text(row, 1),
            material_name=self._get_cell_text(row, 2),
            length_mm=self._to_int(self._get_cell_text(row, 3)),
            stock_length_mm=self._to_int(self._get_cell_text(row, 4)),
            source_pattern_id=self._get_cell_text(row, 5),
            note=self._get_cell_text(row, 6),
        )

    def _validate_leftover(self, leftover: Leftover) -> str:
        if not leftover.material_code:
            return "Не выбран материал."
        if not leftover.material_name:
            return "Не заполнено наименование материала."
        if leftover.length_mm <= 0:
            return "Длина остатка должна быть больше 0."
        return ""

    def _get_cell_text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def _generate_next_leftover_id(self) -> str:
        leftovers = load_leftovers()
        numbers = []

        for item in leftovers:
            if item.id.startswith("LEFT-"):
                tail = item.id.replace("LEFT-", "")
                if tail.isdigit():
                    numbers.append(int(tail))

        next_number = max(numbers, default=0) + 1
        return f"LEFT-{next_number:04d}"

    @staticmethod
    def _to_int(value: str) -> int:
        if not value:
            return 0
        try:
            return int(float(value.replace(",", ".")))
        except ValueError:
            return 0