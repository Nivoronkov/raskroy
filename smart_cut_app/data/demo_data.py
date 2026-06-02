from typing import List

from core.models import Material, Part, CalculationSettings


def get_demo_materials() -> List[Material]:
    """
    Возвращает тестовый список материалов.
    """
    return [
        Material(
            id="MAT-001",
            code="TR-40x20x2",
            name="Труба профильная 40х20х2",
            profile_type="Труба профильная",
            size="40х20х2",
            grade="Ст3",
            stock_length_mm=6000,
            mass_per_meter=1.86,
            price_per_meter=210.0,
            available_count=100,
            note="",
        ),
        Material(
            id="MAT-002",
            code="CH-22P",
            name="Швеллер 22П",
            profile_type="Швеллер",
            size="22П",
            grade="С255",
            stock_length_mm=12000,
            mass_per_meter=21.0,
            price_per_meter=340.0,
            available_count=50,
            note="",
        ),
    ]


def get_demo_parts() -> List[Part]:
    """
    Возвращает тестовый список деталей.
    """
    return [
        Part(
            id="PART-001",
            designation="Д-001",
            name="Стойка",
            material_code="TR-40x20x2",
            length_mm=1480,
            quantity=6,
            assembly="Рама 1",
            note="",
        ),
        Part(
            id="PART-002",
            designation="Д-002",
            name="Перемычка",
            material_code="TR-40x20x2",
            length_mm=960,
            quantity=8,
            assembly="Рама 1",
            note="",
        ),
        Part(
            id="PART-003",
            designation="Д-003",
            name="Балка",
            material_code="CH-22P",
            length_mm=2200,
            quantity=4,
            assembly="Каркас 1",
            note="",
        ),
        Part(
            id="PART-004",
            designation="Д-004",
            name="Связь",
            material_code="CH-22P",
            length_mm=1800,
            quantity=3,
            assembly="Каркас 1",
            note="",
        ),
    ]


def get_demo_settings() -> CalculationSettings:
    """
    Возвращает тестовые параметры расчета.
    """
    return CalculationSettings(
        cut_width_mm=3,
        trim_allowance_mm=0,
        min_useful_leftover_mm=500,
        optimization_mode="min_waste",
        use_leftovers=False,
    )
