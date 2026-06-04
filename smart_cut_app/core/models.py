from dataclasses import dataclass, field
from typing import List


@dataclass
class Material:
    """
    Исходный материал (хлыст), из которого выполняется раскрой.
    """
    id: str
    code: str
    name: str
    profile_type: str
    size: str
    grade: str = ""
    stock_length_mm: int = 0
    mass_per_meter: float = 0.0
    price_per_meter: float = 0.0
    available_count: int = 0
    note: str = ""


@dataclass
class Part:
    """
    Деталь из пользовательского списка.
    """
    id: str
    designation: str
    name: str
    material_code: str
    length_mm: int
    quantity: int
    assembly: str = ""
    note: str = ""
    # Разделение составной детали (длиннее хлыста) на части. Если деталь —
    # часть составной, здесь номер части (1,2,...) и обозначение исходной.
    part_index: int = 0          # 0 = не часть; 1,2,... = номер части ('ч.N')
    split_parent_id: str = ""    # id исходной составной детали
    split_total_parts: int = 0   # на сколько частей разделена исходная


@dataclass
class CalculationSettings:
    """
    Параметры расчета раскроя.
    """
    cut_width_mm: int = 0
    trim_allowance_mm: int = 0
    min_useful_leftover_mm: int = 0
    optimization_mode: str = "min_waste"
    use_leftovers: bool = False


@dataclass
class ExpandedPart:
    """
    Одна конкретная деталь после разворачивания количества.
    """
    id: str
    source_part_id: str
    designation: str
    name: str
    material_code: str
    base_length_mm: int
    effective_length_mm: int
    sequence_no: int
    assembly: str = ""
    note: str = ""
    part_index: int = 0          # номер части составной детали ('ч.N'), 0 = не часть
    split_parent_id: str = ""


@dataclass
class CuttingPattern:
    """
    Карта раскроя одного хлыста.
    """
    id: str
    material_code: str
    material_name: str
    stock_length_mm: int
    parts: List[ExpandedPart] = field(default_factory=list)
    cuts_count: int = 0
    used_length_mm: int = 0
    leftover_length_mm: int = 0
    leftover_type: str = "Отход"
    pattern_key: str = ""
    source_type: str = "new"
    source_leftover_id: str = ""

    def part_lengths(self) -> List[int]:
        return [part.base_length_mm for part in self.parts]

    def pattern_as_text(self) -> str:
        return " + ".join(str(part.base_length_mm) for part in self.parts)


@dataclass
class SummaryRow:
    """
    Одна строка сводного отчета по материалу.
    """
    material_code: str
    material_name: str
    stock_length_mm: int
    total_parts_count: int
    used_bars_count: int
    total_parts_length_mm: int
    total_cut_loss_mm: int
    total_waste_mm: int
    total_useful_leftover_mm: int
    utilization_percent: float


@dataclass
class ProductionRow:
    """
    Сгруппированная строка для производственного задания.
    """
    source_type: str
    material_code: str
    material_name: str
    stock_length_mm: int
    pattern_text: str
    count: int
    cuts_count: int
    used_length_mm: int
    leftover_length_mm: int
    leftover_type: str

@dataclass
class Leftover:
    """
    Полезный остаток материала.
    """
    id: str
    material_code: str
    material_name: str
    length_mm: int
    stock_length_mm: int
    source_pattern_id: str
    note: str = ""

@dataclass
class LeftoverMovementRow:
    """
    Строка движения остатков.
    """
    operation_type: str   # "Списан" / "Добавлен"
    leftover_id: str
    material_code: str
    material_name: str
    length_mm: int
    note: str = ""

@dataclass
class MaterialCatalogItem:
    """
    Элемент справочника материалов.
    """
    id: str
    material_code: str
    name: str
    profile_type: str
    profile_code: str
    size: str
    steel_grade: str
    stock_length_mm: int
    mass_per_meter: float = 0.0
    price_per_meter: float = 0.0
    note: str = ""
    is_active: bool = True
    external_code: str = ""
    available_stock_bars: int = 0

@dataclass
class CutoffSummaryRow:
    """
    Сводка отрезков по одному материалу — для лентопильщика.
    Перечень уникальных длин деталей с количеством (напр. '184 — 2 шт., 595 — 20 шт.').
    Позволяет пересчитать нарезанное по факту и понять, где остановился.
    """
    material_code: str
    material_name: str
    items: List[tuple] = field(default_factory=list)  # [(длина_мм, количество), ...]
    total_count: int = 0

    def as_text(self) -> str:
        return "  ".join(f"{length} — {qty} шт." for length, qty in self.items)

@dataclass
class CalculationResult:
    """
    Общий результат расчета.
    """
    summary_rows: List[SummaryRow] = field(default_factory=list)
    patterns: List[CuttingPattern] = field(default_factory=list)
    production_rows: List[ProductionRow] = field(default_factory=list)
    cutoff_summary_rows: List["CutoffSummaryRow"] = field(default_factory=list)
    leftovers: List[Leftover] = field(default_factory=list)
    consumed_leftover_ids: List[str] = field(default_factory=list)
    leftover_movements: List[LeftoverMovementRow] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0