from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from core.models import CalculationResult
from data.excel_exporter import ExcelExportError, export_result_to_excel
from data.leftovers_service import apply_leftovers_result
from data.leftovers_repository import LeftoversRepositoryError
from ui.cut_visualization_widget import CutPatternWidget


class ResultsTab(QWidget):
    SUMMARY_HEADERS = [
        "Код материала",
        "Материал",
        "Длина хлыста, мм",
        "Кол-во деталей",
        "Кол-во хлыстов",
        "Длина деталей, мм",
        "Потери на рез, мм",
        "Отход, мм",
        "Полезный остаток, мм",
        "Использование, %",
    ]

    PATTERN_HEADERS = [
        "Источник",
        "Код материала",
        "Материал",
        "Длина хлыста, мм",
        "Состав раскроя",
        "Резов",
        "Занято, мм",
        "Остаток, мм",
        "Тип остатка",
    ]

    PRODUCTION_HEADERS = [
        "Источник",
        "Код материала",
        "Материал",
        "Длина хлыста, мм",
        "Кол-во одинаковых хлыстов",
        "Схема раскроя",
        "Резов",
        "Занято, мм",
        "Остаток, мм",
        "Тип остатка",
    ]

    MOVEMENT_HEADERS = [
        "Операция",
        "ID остатка",
        "Код материала",
        "Материал",
        "Длина, мм",
        "Примечание",
    ]

    def __init__(self) -> None:
        super().__init__()

        self.current_result: Optional[CalculationResult] = None
        self.leftovers_applied = False

        self.messages_edit = QPlainTextEdit()
        self.messages_edit.setReadOnly(True)

        self.summary_table = QTableWidget(0, len(self.SUMMARY_HEADERS))
        self.summary_table.setHorizontalHeaderLabels(self.SUMMARY_HEADERS)

        self.patterns_table = QTableWidget(0, len(self.PATTERN_HEADERS))
        self.patterns_table.setHorizontalHeaderLabels(self.PATTERN_HEADERS)

        self.production_table = QTableWidget(0, len(self.PRODUCTION_HEADERS))
        self.production_table.setHorizontalHeaderLabels(self.PRODUCTION_HEADERS)

        self.movement_table = QTableWidget(0, len(self.MOVEMENT_HEADERS))
        self.movement_table.setHorizontalHeaderLabels(self.MOVEMENT_HEADERS)

        self.cutoff_table = QTableWidget(0, 4)
        self.cutoff_table.setHorizontalHeaderLabels(
            ["Материал", "Наименование", "Отрезки (длина — количество)", "Всего деталей"]
        )
        self.cutoff_table.horizontalHeader().setStretchLastSection(False)

        for table in [
            self.summary_table,
            self.patterns_table,
            self.production_table,
            self.movement_table,
        ]:
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        self.visual_scroll = QScrollArea()
        self.visual_scroll.setWidgetResizable(True)
        self.visual_container = QWidget()
        self.visual_layout = QVBoxLayout()
        self.visual_layout.setContentsMargins(8, 8, 8, 8)
        self.visual_layout.setSpacing(10)
        self.visual_container.setLayout(self.visual_layout)
        self.visual_scroll.setWidget(self.visual_container)

        self.export_excel_button = QPushButton("Экспорт в Excel")
        self.export_excel_button.clicked.connect(self.export_to_excel)

        self.save_leftovers_button = QPushButton("Применить изменения по остаткам")
        self.save_leftovers_button.clicked.connect(self.save_leftovers)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(self.export_excel_button)
        top_buttons.addWidget(self.save_leftovers_button)
        top_buttons.addStretch()

        tabs = QTabWidget()
        tabs.addTab(self._wrap_widget(self.messages_edit), "Сообщения")
        tabs.addTab(self._wrap_widget(self.summary_table), "Сводка")
        tabs.addTab(self._wrap_widget(self.patterns_table), "Карты раскроя")
        tabs.addTab(self._wrap_widget(self.production_table), "Производство")
        tabs.addTab(self._wrap_widget(self.cutoff_table), "Отрезки")
        tabs.addTab(self._wrap_widget(self.movement_table), "Движение остатков")
        tabs.addTab(self.visual_scroll, "Схема раскроя")

        layout = QVBoxLayout()
        layout.addLayout(top_buttons)
        layout.addWidget(tabs)
        self.setLayout(layout)

    def _wrap_widget(self, widget: QWidget) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        wrapper.setLayout(layout)
        return wrapper

    def clear_results(self) -> None:
        self.current_result = None
        self.leftovers_applied = False
        self.messages_edit.clear()
        self.summary_table.setRowCount(0)
        self.patterns_table.setRowCount(0)
        self.production_table.setRowCount(0)
        self.cutoff_table.setRowCount(0)
        self.movement_table.setRowCount(0)
        self._clear_visualization()
        self.save_leftovers_button.setEnabled(True)

    def show_result(self, result: CalculationResult) -> None:
        self.clear_results()
        self.current_result = result
        self.leftovers_applied = False
        self.save_leftovers_button.setEnabled(True)

        self._fill_messages(result)
        self._fill_summary(result)
        self._fill_patterns(result)
        self._fill_production(result)
        self._fill_cutoff_summary(result)
        self._fill_movements(result)
        self._fill_visualization(result)

    def _fill_messages(self, result: CalculationResult) -> None:
        lines = []

        if result.success:
            lines.append("РАСЧЕТ ВЫПОЛНЕН УСПЕШНО")
        else:
            lines.append("РАСЧЕТ ЗАВЕРШЕН С ОШИБКАМИ")

        if result.errors:
            lines.append("")
            lines.append("Ошибки:")
            for item in result.errors:
                lines.append(f" - {item}")

        if result.warnings:
            lines.append("")
            lines.append("Предупреждения:")
            for item in result.warnings:
                lines.append(f" - {item}")

        self.messages_edit.setPlainText("\n".join(lines))

    def _fill_summary(self, result: CalculationResult) -> None:
        for row_index, row in enumerate(result.summary_rows):
            self.summary_table.insertRow(row_index)
            values = [
                row.material_code,
                row.material_name,
                str(row.stock_length_mm),
                str(row.total_parts_count),
                str(row.used_bars_count),
                str(row.total_parts_length_mm),
                str(row.total_cut_loss_mm),
                str(row.total_waste_mm),
                str(row.total_useful_leftover_mm),
                str(row.utilization_percent),
            ]
            for col, value in enumerate(values):
                self.summary_table.setItem(row_index, col, QTableWidgetItem(value))

    def _fill_patterns(self, result: CalculationResult) -> None:
        for row_index, pattern in enumerate(result.patterns):
            self.patterns_table.insertRow(row_index)
            source_text = "Остаток" if pattern.source_type == "leftover" else "Новый хлыст"
            values = [
                source_text,
                pattern.material_code,
                pattern.material_name,
                str(pattern.stock_length_mm),
                pattern.pattern_as_text(),
                str(pattern.cuts_count),
                str(pattern.used_length_mm),
                str(pattern.leftover_length_mm),
                pattern.leftover_type,
            ]
            for col, value in enumerate(values):
                self.patterns_table.setItem(row_index, col, QTableWidgetItem(value))

    def _fill_cutoff_summary(self, result: CalculationResult) -> None:
        for row_index, row in enumerate(result.cutoff_summary_rows):
            self.cutoff_table.insertRow(row_index)
            values = [
                row.material_code,
                row.material_name,
                row.as_text(),
                str(row.total_count),
            ]
            for col, value in enumerate(values):
                self.cutoff_table.setItem(row_index, col, QTableWidgetItem(value))
        self.cutoff_table.resizeColumnsToContents()

    def _fill_production(self, result: CalculationResult) -> None:
        for row_index, row in enumerate(result.production_rows):
            self.production_table.insertRow(row_index)
            source_text = "Остаток" if row.source_type == "leftover" else "Новый хлыст"
            values = [
                source_text,
                row.material_code,
                row.material_name,
                str(row.stock_length_mm),
                str(row.count),
                row.pattern_text,
                str(row.cuts_count),
                str(row.used_length_mm),
                str(row.leftover_length_mm),
                row.leftover_type,
            ]
            for col, value in enumerate(values):
                self.production_table.setItem(row_index, col, QTableWidgetItem(value))

    def _fill_movements(self, result: CalculationResult) -> None:
        for row_index, row in enumerate(result.leftover_movements):
            self.movement_table.insertRow(row_index)
            values = [
                row.operation_type,
                row.leftover_id,
                row.material_code,
                row.material_name,
                str(row.length_mm),
                row.note,
            ]
            for col, value in enumerate(values):
                self.movement_table.setItem(row_index, col, QTableWidgetItem(value))

    def _clear_visualization(self) -> None:
        while self.visual_layout.count():
            item = self.visual_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _fill_visualization(self, result: CalculationResult) -> None:
        self._clear_visualization()

        if not result.patterns:
            self.visual_layout.addWidget(QLabel("Нет данных для визуализации раскроя."))
            self.visual_layout.addStretch()
            return

        for index, pattern in enumerate(result.patterns, start=1):
            source_text = f"{'Остаток' if pattern.source_type == 'leftover' else 'Новый хлыст'} #{index}"
            material_text = f"{pattern.material_code} | {pattern.material_name}"

            parts_data = []
            for part in pattern.parts:
                parts_data.append({
                    "length_mm": part.base_length_mm,
                    "assembly": getattr(part, "assembly", ""),
                    "note": getattr(part, "note", ""),
            })

            title = QLabel(
                f"{source_text} — {pattern.pattern_as_text()} — остаток {pattern.leftover_length_mm} мм"
            )
            title.setStyleSheet("font-weight: bold;")

            widget = CutPatternWidget(
                stock_length_mm=pattern.stock_length_mm,
                parts_data=parts_data,
                leftover_length_mm=pattern.leftover_length_mm,
                source_text=source_text,
                material_text=material_text,
            )

            self.visual_layout.addWidget(title)
            self.visual_layout.addWidget(widget)

        self.visual_layout.addStretch()

    def export_to_excel(self) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "Нет данных", "Сначала выполните расчет.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить Excel-файл",
            str(Path.cwd() / "результат_раскроя.xlsx"),
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return

        try:
            export_result_to_excel(self.current_result, file_path)
            QMessageBox.information(self, "Готово", f"Файл сохранен:\n{file_path}")
        except PermissionError:
            QMessageBox.warning(
                self,
                "Файл используется",
                "Не удалось сохранить файл.\n\n"
                "Возможно, Excel-файл уже открыт. Закройте его и повторите попытку.",
            )
        except ExcelExportError as exc:
            QMessageBox.warning(self, "Ошибка экспорта", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Непредвиденная ошибка:\n{exc}")

    def save_leftovers(self) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "Нет данных", "Сначала выполните расчет.")
            return

        if self.leftovers_applied:
            QMessageBox.information(
                self,
                "Изменения уже применены",
                "Изменения по остаткам для этого расчета уже были применены.\n"
                "Чтобы применить новые изменения, сначала выполните новый расчет.",
            )
            return

        try:
            stats = apply_leftovers_result(
                consumed_leftover_ids=self.current_result.consumed_leftover_ids,
                new_leftovers=self.current_result.leftovers,
            )
            QMessageBox.information(
                self,
                "Остатки обновлены",
                "База остатков успешно обновлена.\n\n"
                f"Списано использованных остатков: {stats['deleted']}\n"
                f"Добавлено новых остатков: {stats['added']}\n"
                f"Всего остатков в базе: {stats['total']}",
            )

            self.leftovers_applied = True
            self.save_leftovers_button.setEnabled(False)

        except LeftoversRepositoryError as exc:
            QMessageBox.warning(self, "Ошибка обновления остатков", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Непредвиденная ошибка при обновлении остатков:\n{exc}",
            )