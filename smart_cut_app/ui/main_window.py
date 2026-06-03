from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QTabWidget

from core.cutting_engine import calculate_cutting
from core.models import Material
from data.materials_catalog_repository import load_materials_catalog
from data.project_repository import ProjectRepositoryError, load_project, save_project
from ui.calc_params_tab import CalcParamsTab
from ui.leftovers_tab import LeftoversTab
from ui.materials_catalog_tab import MaterialsCatalogTab
from ui.materials_tab import MaterialsTab
from ui.modes_compare_dialog import ModesCompareDialog
from ui.parts_tab import PartsTab
from ui.results_tab import ResultsTab
from ui.import_specification import import_specification, SpecImportError


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Калькулятор линейного раскроя металлопроката")
        self.resize(1400, 900)

        self.tabs = QTabWidget()

        self.materials_catalog_tab = MaterialsCatalogTab()
        self.materials_tab = MaterialsTab()
        self.parts_tab = PartsTab()
        self.calc_params_tab = CalcParamsTab()
        self.results_tab = ResultsTab()
        self.leftovers_tab = LeftoversTab()

        self.tabs.addTab(self.materials_catalog_tab, "Справочник материалов")
        self.tabs.addTab(self.materials_tab, "Материалы")
        self.tabs.addTab(self.parts_tab, "Детали")
        self.tabs.addTab(self.calc_params_tab, "Параметры расчета")
        self.tabs.addTab(self.results_tab, "Результаты")
        self.tabs.addTab(self.leftovers_tab, "Остатки")

        self.setCentralWidget(self.tabs)

        self.calc_params_tab.calculate_button.clicked.connect(self.run_calculation)
        self.calc_params_tab.compare_modes_button.clicked.connect(self.compare_modes)

        self._create_menu()
        self._create_statusbar()

    def _create_menu(self) -> None:
        menu = self.menuBar().addMenu("Файл")

        import_spec_action = QAction("Загрузить спецификацию (Компас .xls)", self)
        open_action = QAction("Открыть проект", self)
        save_action = QAction("Сохранить проект", self)

        import_spec_action.triggered.connect(self.import_specification)
        open_action.triggered.connect(self.open_project)
        save_action.triggered.connect(self.save_project)

        menu.addAction(import_spec_action)
        menu.addSeparator()
        menu.addAction(open_action)
        menu.addAction(save_action)

    def _create_statusbar(self) -> None:
        self.statusBar().showMessage("Автор: Воронков Н.А.")

    def _build_project_materials_from_parts(self, parts) -> list[Material]:
        catalog_items = load_materials_catalog()
        catalog_by_code = {
            item.material_code: item for item in catalog_items if item.is_active
        }

        materials: list[Material] = []
        used_codes = []

        for part in parts:
            code = (part.material_code or "").strip()
            if not code or code in used_codes:
                continue

            catalog_item = catalog_by_code.get(code)
            if catalog_item is None:
                continue

            used_codes.append(code)

            materials.append(
                Material(
                    id=f"MAT-{len(materials)+1:03d}",
                    code=catalog_item.material_code,
                    name=catalog_item.name,
                    profile_type=catalog_item.profile_type,
                    size=catalog_item.size,
                    grade=catalog_item.steel_grade,
                    stock_length_mm=catalog_item.stock_length_mm,
                    mass_per_meter=catalog_item.mass_per_meter,
                    price_per_meter=catalog_item.price_per_meter,
                    available_count=catalog_item.available_stock_bars,
                    note=catalog_item.note,
                )
            )

        return materials

    def run_calculation(self) -> None:
        try:
            parts = self.parts_tab.get_parts()
            settings = self.calc_params_tab.get_settings()

            materials = self._build_project_materials_from_parts(parts)

            # Составные детали (длиннее хлыста): предложить оператору разделить.
            parts = self._handle_oversized_parts(parts, materials)
            if parts is None:
                return  # оператор отменил

            result = calculate_cutting(materials, parts, settings)

            self.results_tab.show_result(result)
            self.materials_tab.build_from_parts(parts, result)
            self.tabs.setCurrentWidget(self.results_tab)

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Произошла непредвиденная ошибка:\n{exc}",
            )

    def _handle_oversized_parts(self, parts, materials):
        """
        Находит детали длиннее хлыста и предлагает разделить каждую через диалог.
        Возвращает обновлённый список деталей или None, если оператор отменил.
        """
        from core.part_splitting import build_split_parts
        from ui.split_part_dialog import SplitPartDialog

        stock_by_code = {m.code: m.stock_length_mm for m in materials}

        oversized = [
            p for p in parts
            if p.length_mm > stock_by_code.get(p.material_code, p.length_mm)
            and p.part_index == 0  # ещё не разделённая
        ]
        if not oversized:
            return parts

        splits = {}  # part_id -> длины частей
        for p in oversized:
            stock = stock_by_code.get(p.material_code, p.length_mm)
            dlg = SplitPartDialog(p.name, p.material_code, p.length_mm, stock, self)
            if dlg.exec() != dlg.DialogCode.Accepted or not dlg.result_lengths:
                # оператор не разделил эту деталь — спросим, продолжать ли без неё
                resp = QMessageBox.question(
                    self,
                    "Деталь не разделена",
                    f"Деталь «{p.name}» ({p.length_mm} мм) не разделена и не войдёт "
                    f"в раскрой. Продолжить расчёт без неё?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return None
                continue
            splits[p.id] = dlg.result_lengths

        if not splits:
            return parts

        new_parts = []
        for p in parts:
            if p.id in splits:
                new_parts.extend(build_split_parts(p, splits[p.id]))
            else:
                new_parts.append(p)
        return new_parts

    def compare_modes(self) -> None:
        try:
            parts = self.parts_tab.get_parts()
            settings = self.calc_params_tab.get_settings()
            materials = self._build_project_materials_from_parts(parts)

            mode_names = {
                "min_waste": "Минимальный отход",
                "min_bars": "Минимум хлыстов",
                "balanced": "Сбалансированный",
                "max_leftovers": "Максимально использовать остатки",
            }

            compare_rows = []

            for mode_code, mode_name in mode_names.items():
                test_settings = type(settings)(
                    cut_width_mm=settings.cut_width_mm,
                    trim_allowance_mm=settings.trim_allowance_mm,
                    min_useful_leftover_mm=settings.min_useful_leftover_mm,
                    optimization_mode=mode_code,
                    use_leftovers=settings.use_leftovers,
                )

                result = calculate_cutting(materials, parts, test_settings)

                patterns_count = len(result.patterns)
                new_bars_count = len([p for p in result.patterns if p.source_type == "new"])
                used_leftovers_count = len([p for p in result.patterns if p.source_type == "leftover"])
                total_waste_mm = sum(row.total_waste_mm for row in result.summary_rows)
                total_useful_leftover_mm = sum(row.total_useful_leftover_mm for row in result.summary_rows)

                utilization_percent = 0.0
                if result.summary_rows:
                    utilization_percent = round(
                        sum(row.utilization_percent for row in result.summary_rows) / len(result.summary_rows),
                        2,
                    )

                errors_text = "; ".join(result.errors) if result.errors else ""

                compare_rows.append({
                    "mode_code": mode_code,
                    "mode_name": mode_name,
                    "patterns_count": patterns_count,
                    "new_bars_count": new_bars_count,
                    "used_leftovers_count": used_leftovers_count,
                    "total_waste_mm": total_waste_mm,
                    "total_useful_leftover_mm": total_useful_leftover_mm,
                    "utilization_percent": utilization_percent,
                    "errors_text": errors_text,
                })

            dialog = ModesCompareDialog(compare_rows, self)
            if dialog.exec() == dialog.DialogCode.Accepted and dialog.selected_mode_code:
                index = self.calc_params_tab.optimization_mode_combo.findData(dialog.selected_mode_code)
                if index >= 0:
                    self.calc_params_tab.optimization_mode_combo.setCurrentIndex(index)
                    QMessageBox.information(
                        self,
                        "Режим применен",
                        "Выбранный режим установлен в параметрах расчета.",
                    )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось сравнить режимы:\n{exc}",
            )

    def save_project(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить проект",
            "проект_раскроя.json",
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        try:
            parts = self.parts_tab.get_parts()
            settings = self.calc_params_tab.get_settings()
            materials = self._build_project_materials_from_parts(parts)

            save_project(file_path, materials, parts, settings)

            QMessageBox.information(
                self,
                "Проект сохранен",
                f"Проект успешно сохранен:\n{file_path}",
            )

        except ProjectRepositoryError as exc:
            QMessageBox.warning(self, "Ошибка сохранения", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Непредвиденная ошибка при сохранении:\n{exc}",
            )

    def import_specification(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Загрузить спецификацию Компас",
            "",
            "Excel (*.xls *.xlsx)",
        )
        if not file_path:
            return

        try:
            parts, missing, info, missing_cards = import_specification(file_path)

            self.parts_tab.set_parts(parts)
            self.results_tab.clear_results()
            self.materials_tab.build_from_parts(parts, None)
            self.tabs.setCurrentWidget(self.parts_tab)

            if missing:
                # быстрое добавление недостающих материалов на склад в один проход
                if missing_cards:
                    from ui.quick_add_materials_dialog import QuickAddMaterialsDialog
                    dlg = QuickAddMaterialsDialog(missing_cards, self)
                    dlg.exec()
                    if dlg.added_count:
                        # обновим список материалов с учётом пополненного справочника
                        self.materials_tab.build_from_parts(parts, None)
                        QMessageBox.information(
                            self,
                            "Склад пополнен",
                            f"Добавлено материалов на склад: {dlg.added_count}.\n"
                            "Теперь они опознаются при расчёте раскроя.",
                        )
                else:
                    QMessageBox.warning(
                        self, "Спецификация загружена — нужны материалы", info
                    )
            else:
                QMessageBox.information(self, "Спецификация загружена", info)

        except SpecImportError as exc:
            QMessageBox.warning(self, "Не удалось загрузить спецификацию", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Непредвиденная ошибка при загрузке спецификации:\n{exc}",
            )

    def open_project(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект",
            "",
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        try:
            project_data = load_project(file_path)

            self.parts_tab.set_parts(project_data["parts"])
            self.calc_params_tab.set_settings(project_data["settings"])
            self.results_tab.clear_results()
            self.materials_tab.build_from_parts(project_data["parts"], None)

            QMessageBox.information(
                self,
                "Проект открыт",
                f"Проект успешно загружен:\n{file_path}",
            )

        except ProjectRepositoryError as exc:
            QMessageBox.warning(self, "Ошибка открытия", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Непредвиденная ошибка при открытии:\n{exc}",
            )