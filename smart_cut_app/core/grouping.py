from dataclasses import dataclass, field
from typing import Dict, List

from core.models import Material, Part, ExpandedPart, CalculationSettings
from core.normalization import canonical_code_key


@dataclass
class PreparedGroup:
    """
    Подготовленная группа деталей для раскроя по одному материалу.
    """
    material: Material
    expanded_parts: List[ExpandedPart] = field(default_factory=list)


def expand_parts(parts: List[Part], settings: CalculationSettings) -> List[ExpandedPart]:
    """
    Разворачивает список деталей по количеству.
    Например, если quantity=3, то из одной детали будет создано 3 ExpandedPart.
    """
    expanded: List[ExpandedPart] = []

    for part in parts:
        for sequence_no in range(1, part.quantity + 1):
            expanded_part = ExpandedPart(
                id=f"{part.id}-{sequence_no}",
                source_part_id=part.id,
                designation=part.designation,
                name=part.name,
                material_code=part.material_code,
                base_length_mm=part.length_mm,
                effective_length_mm=part.length_mm + settings.trim_allowance_mm,
                sequence_no=sequence_no,
                assembly=part.assembly,
                note=part.note,
                part_index=part.part_index,
                split_parent_id=part.split_parent_id,
            )
            expanded.append(expanded_part)

    return expanded


def group_parts_by_material(
    parts: List[Part],
    materials: List[Material],
    settings: CalculationSettings,
) -> List[PreparedGroup]:
    """
    Группирует детали по коду материала.
    Внутри каждой группы детали сортируются по убыванию effective_length_mm.
    """
    materials_by_code: Dict[str, Material] = {material.code: material for material in materials}
    materials_by_canon: Dict[str, Material] = {
        canonical_code_key(material.code): material for material in materials
    }
    expanded_parts = expand_parts(parts, settings)

    grouped: Dict[str, List[ExpandedPart]] = {}

    for part in expanded_parts:
        grouped.setdefault(part.material_code, []).append(part)

    prepared_groups: List[PreparedGroup] = []

    for material_code, group_parts in grouped.items():
        material = materials_by_code.get(material_code)
        if material is None:
            material = materials_by_canon.get(canonical_code_key(material_code))
        if material is None:
            # На практике сюда не должны попадать невалидные данные,
            # потому что это уже должен отловить validators.py
            continue

        # Детали длиннее хлыста (составные/сварные) физически не укладываются —
        # исключаем из раскроя. Предупреждение о них уже выдал validators.py.
        cuttable_parts = [
            p for p in group_parts if p.effective_length_mm <= material.stock_length_mm
        ]
        if not cuttable_parts:
            continue

        cuttable_parts.sort(key=lambda item: item.effective_length_mm, reverse=True)

        prepared_groups.append(
            PreparedGroup(
                material=material,
                expanded_parts=cuttable_parts,
            )
        )

    prepared_groups.sort(key=lambda group: group.material.code)

    return prepared_groups
