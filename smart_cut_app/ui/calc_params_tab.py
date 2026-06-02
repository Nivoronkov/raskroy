from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.models import CalculationSettings
from data.demo_data import get_demo_settings


class CalcParamsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.cut_width_spin = QSpinBox()
        self.cut_width_spin.setRange(0, 100)
        self.cut_width_spin.setValue(3)
        self.cut_width_spin.setSuffix(" мм")

        self.trim_allowance_spin = QSpinBox()
        self.trim_allowance_spin.setRange(0, 100)
        self.trim_allowance_spin.setValue(0)
        self.trim_allowance_spin.setSuffix(" мм")

        self.min_useful_leftover_spin = QSpinBox()
        self.min_useful_leftover_spin.setRange(0, 100000)
        self.min_useful_leftover_spin.setValue(500)
        self.min_useful_leftover_spin.setSuffix(" мм")

        self.optimization_mode_combo = QComboBox()
        self.optimization_mode_combo.addItem("Минимальный отход", "min_waste")
        self.optimization_mode_combo.addItem("Минимум хлыстов", "min_bars")
        self.optimization_mode_combo.addItem("Сбалансированный", "balanced")
        self.optimization_mode_combo.addItem("Максимально использовать остатки", "max_leftovers")

        self.use_leftovers_checkbox = QCheckBox("Учитывать остатки из базы")
        self.use_leftovers_checkbox.setChecked(False)

        self.load_demo_button = QPushButton("Загрузить демо-параметры")
        self.calculate_button = QPushButton("Рассчитать")
        self.compare_modes_button = QPushButton("Сравнить режимы")

        self.load_demo_button.clicked.connect(self.load_demo_settings)

        title_label = QLabel("Параметры расчета")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        params_group = QGroupBox("Настройки")
        form_layout = QFormLayout()
        form_layout.addRow("Ширина реза:", self.cut_width_spin)
        form_layout.addRow("Припуск:", self.trim_allowance_spin)
        form_layout.addRow("Минимальный полезный остаток:", self.min_useful_leftover_spin)
        form_layout.addRow("Режим оптимизации:", self.optimization_mode_combo)
        form_layout.addRow("", self.use_leftovers_checkbox)
        params_group.setLayout(form_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(title_label)
        main_layout.addWidget(params_group)
        main_layout.addWidget(self.load_demo_button)
        main_layout.addWidget(self.calculate_button)
        main_layout.addWidget(self.compare_modes_button)
        main_layout.addStretch()

        self.setLayout(main_layout)

    def load_demo_settings(self) -> None:
        settings = get_demo_settings()

        self.cut_width_spin.setValue(settings.cut_width_mm)
        self.trim_allowance_spin.setValue(settings.trim_allowance_mm)
        self.min_useful_leftover_spin.setValue(settings.min_useful_leftover_mm)
        self.use_leftovers_checkbox.setChecked(settings.use_leftovers)

        index = self.optimization_mode_combo.findData(settings.optimization_mode)
        if index >= 0:
            self.optimization_mode_combo.setCurrentIndex(index)

    def get_settings(self) -> CalculationSettings:
        return CalculationSettings(
            cut_width_mm=self.cut_width_spin.value(),
            trim_allowance_mm=self.trim_allowance_spin.value(),
            min_useful_leftover_mm=self.min_useful_leftover_spin.value(),
            optimization_mode=self.optimization_mode_combo.currentData(),
             use_leftovers=self.use_leftovers_checkbox.isChecked(),
        )
    
    def set_settings(self, settings: CalculationSettings) -> None:
        self.cut_width_spin.setValue(settings.cut_width_mm)
        self.trim_allowance_spin.setValue(settings.trim_allowance_mm)
        self.min_useful_leftover_spin.setValue(settings.min_useful_leftover_mm)
        self.use_leftovers_checkbox.setChecked(settings.use_leftovers)

        index = self.optimization_mode_combo.findData(settings.optimization_mode)
        if index >= 0:
            self.optimization_mode_combo.setCurrentIndex(index)