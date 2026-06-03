"""
Диалог разделения составной детали (длиннее хлыста).

Всплывает, когда деталь не помещается в хлыст. Оператор задаёт разбиение одним
из двух способов:
  - «Поровну»: ввести число частей, система делит длину на равные;
  - «Вручную»: ввести длину каждой части.

Сумма частей должна быть >= исходной длины, превышение — не более напуска на
сварку (MAX_OVERHANG_MM). Снизу — живой предпросмотр частей и проверка.
Результат: список длин частей (self.result_lengths) или None при отмене.
"""
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.part_splitting import MAX_OVERHANG_MM, split_lengths_equal, validate_split


class SplitPartDialog(QDialog):
    def __init__(self, part_name: str, material_code: str,
                 total_length_mm: int, stock_length_mm: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Разделение составной детали")
        self.resize(560, 360)
        self._total = int(total_length_mm)
        self.result_lengths: Optional[List[int]] = None

        info = QLabel(
            f"Деталь «{part_name}» ({material_code}) длиной {self._total} мм "
            f"больше хлыста ({stock_length_mm} мм).\n"
            f"Её нужно разделить на части (разбивку определяет конструктор под заказ). "
            f"В раскрое части пойдут как ч.1, ч.2 …\n"
            f"Сумма частей должна быть не меньше {self._total} мм и не больше "
            f"{self._total + MAX_OVERHANG_MM} мм (напуск на сварку)."
        )
        info.setWordWrap(True)

        # выбор режима
        self.mode_equal = QRadioButton("Поровну (указать число частей)")
        self.mode_manual = QRadioButton("Вручную (указать длины частей)")
        self.mode_equal.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.mode_equal)
        grp.addButton(self.mode_manual)
        self.mode_equal.toggled.connect(self._on_mode_changed)

        # режим «поровну»
        self.n_parts = QSpinBox()
        self.n_parts.setRange(2, 20)
        self.n_parts.setValue(2)
        self.n_parts.valueChanged.connect(self._update_preview)
        equal_row = QHBoxLayout()
        equal_row.addWidget(QLabel("Число частей:"))
        equal_row.addWidget(self.n_parts)
        equal_row.addStretch(1)
        self.equal_widget = QWidget()
        self.equal_widget.setLayout(equal_row)

        # режим «вручную»
        self.manual_edit = QLineEdit()
        self.manual_edit.setPlaceholderText("Например: 6750 6750  (длины через пробел или +)")
        self.manual_edit.textChanged.connect(self._update_preview)
        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("Длины частей:"))
        manual_row.addWidget(self.manual_edit, 1)
        self.manual_widget = QWidget()
        self.manual_widget.setLayout(manual_row)
        self.manual_widget.setEnabled(False)

        # предпросмотр и статус
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.status = QLabel()
        self.status.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(info)
        layout.addWidget(self.mode_equal)
        layout.addWidget(self.equal_widget)
        layout.addWidget(self.mode_manual)
        layout.addWidget(self.manual_widget)
        layout.addWidget(self.preview)
        layout.addWidget(self.status)
        layout.addStretch(1)
        layout.addWidget(self.buttons)
        self.setLayout(layout)

        self._update_preview()

    def _on_mode_changed(self) -> None:
        equal = self.mode_equal.isChecked()
        self.equal_widget.setEnabled(equal)
        self.manual_widget.setEnabled(not equal)
        self._update_preview()

    def _current_lengths(self) -> List[int]:
        if self.mode_equal.isChecked():
            try:
                return split_lengths_equal(self._total, self.n_parts.value())
            except ValueError:
                return []
        # ручной ввод: числа через пробел, запятую или +
        raw = self.manual_edit.text().replace("+", " ").replace(",", " ")
        lengths = []
        for tok in raw.split():
            try:
                lengths.append(int(tok))
            except ValueError:
                return []
        return lengths

    def _update_preview(self) -> None:
        lengths = self._current_lengths()
        if not lengths:
            self.preview.setText("Части: —")
            self.status.setText("")
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        parts_text = "   ".join(f"ч.{i+1} = {L} мм" for i, L in enumerate(lengths))
        self.preview.setText(f"Части: {parts_text}\nСумма: {sum(lengths)} мм")

        errors = validate_split(self._total, lengths)
        ok_btn = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if errors:
            self.status.setText("✗ " + errors[0])
            ok_btn.setEnabled(False)
        else:
            overhang = sum(lengths) - self._total
            extra = f" (напуск {overhang} мм)" if overhang else ""
            self.status.setText(f"✓ Разбиение корректно{extra}")
            ok_btn.setEnabled(True)

    def _on_accept(self) -> None:
        lengths = self._current_lengths()
        if validate_split(self._total, lengths):
            return
        self.result_lengths = lengths
        self.accept()
