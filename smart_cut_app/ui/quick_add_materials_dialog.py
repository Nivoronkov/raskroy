"""
Быстрое добавление недостающих материалов из спецификации на склад.

Открывается после загрузки спецификации, если каких-то материалов нет в
справочнике. Профиль, размер и марка уже подставлены из спецификации (менять
не нужно), оператор только указывает длину хлыста и количество хлыстов на
складе и жмёт «Добавить все». Коды собираются единым модулем нормализации,
поэтому совпадают с кодами деталей — материал сразу опознаётся при расчёте.
"""
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.models import MaterialCatalogItem
from core.normalization import material_code as build_code, material_name as build_name
from data.materials_catalog_repository import (
    add_catalog_item,
    find_duplicate_catalog_item,
    get_next_catalog_item_id,
)


class QuickAddMaterialsDialog(QDialog):
    """cards — список dict: material_code, profile_type, size, grade, stock_length_mm."""

    COL_NAME = 0
    COL_LENGTH = 1
    COL_BARS = 2

    def __init__(self, cards: List[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Добавить материалы на склад")
        self.resize(680, 420)
        self._cards = cards
        self.added_count = 0

        intro = QLabel(
            "Этих материалов из спецификации нет в справочнике склада.\n"
            "Профиль, размер и марка уже распознаны — укажите длину хлыста и "
            "количество на складе, затем нажмите «Добавить все на склад»."
        )
        intro.setWordWrap(True)

        self.table = QTableWidget(len(cards), 3)
        self.table.setHorizontalHeaderLabels(
            ["Материал (из спецификации)", "Длина хлыста, мм", "Хлыстов на складе"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            self.COL_NAME, QHeaderView.ResizeMode.Stretch
        )

        self._length_spins = []
        self._bars_spins = []

        for row, card in enumerate(cards):
            name = build_name(card["profile_type"], card["size"], card["grade"]) or card["material_code"]
            name_item = QTableWidgetItem(f"{name}\n{card['material_code']}")
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self.COL_NAME, name_item)

            length_spin = QSpinBox()
            length_spin.setRange(0, 100000)
            length_spin.setSingleStep(500)
            length_spin.setSuffix(" мм")
            length_spin.setValue(int(card.get("stock_length_mm") or 6000))
            self.table.setCellWidget(row, self.COL_LENGTH, length_spin)
            self._length_spins.append(length_spin)

            bars_spin = QSpinBox()
            bars_spin.setRange(0, 100000)
            bars_spin.setValue(0)
            self.table.setCellWidget(row, self.COL_BARS, bars_spin)
            self._bars_spins.append(bars_spin)

        self.table.resizeRowsToContents()

        add_all_btn = QPushButton("Добавить все на склад")
        add_all_btn.clicked.connect(self._add_all)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_all_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(buttons)

        layout = QVBoxLayout()
        layout.addWidget(intro)
        layout.addWidget(self.table, 1)
        layout.addLayout(btn_row)
        self.setLayout(layout)

    def _add_all(self) -> None:
        added, skipped_dup, skipped_len = 0, [], []

        for row, card in enumerate(self._cards):
            length = self._length_spins[row].value()
            bars = self._bars_spins[row].value()
            profile = card["profile_type"]
            size = card["size"]
            grade = card["grade"]

            if length <= 0:
                skipped_len.append(card["material_code"])
                continue

            # защита от дубликатов: тот же материал мог быть заведён иначе
            dup = find_duplicate_catalog_item(profile, size, grade, length)
            if dup is not None:
                skipped_dup.append(f"{card['material_code']} (уже есть: {dup.material_code})")
                continue

            code = build_code(profile, size, grade)
            name = build_name(profile, size, grade)
            item = MaterialCatalogItem(
                id=get_next_catalog_item_id(),
                material_code=code,
                name=name,
                profile_type=profile,
                profile_code=code.split("-")[0] if code else "",
                size=size,
                steel_grade=grade,
                stock_length_mm=length,
                available_stock_bars=bars,
                is_active=True,
            )
            add_catalog_item(item)
            added += 1

        self.added_count += added

        msg = [f"Добавлено материалов: {added}."]
        if skipped_dup:
            msg.append("\nПропущены как дубликаты:\n  " + "\n  ".join(skipped_dup))
        if skipped_len:
            msg.append("\nНе добавлены (не указана длина хлыста):\n  " + "\n  ".join(skipped_len))

        QMessageBox.information(self, "Добавление на склад", "\n".join(msg))

        if not skipped_len:
            self.accept()
