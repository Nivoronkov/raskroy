from typing import Dict, List, Tuple

from core.grouping import PreparedGroup, group_parts_by_material
from core.models import (
    CalculationResult,
    CalculationSettings,
    CuttingPattern,
    Leftover,
    LeftoverMovementRow,
    Material,
    Part,
    ProductionRow,
    SummaryRow,
)
from core.optimizer import optimize_group
from core.validators import validate_all
from data.leftovers_repository import load_leftovers


def _build_summary_row(
    group: PreparedGroup,
    patterns: List[CuttingPattern],
    settings: CalculationSettings,
) -> SummaryRow:
    total_parts_count = sum(len(pattern.parts) for pattern in patterns)
    total_parts_length_mm = sum(
        part.base_length_mm
        for pattern in patterns
        for part in pattern.parts
    )
    total_cut_loss_mm = sum(pattern.cuts_count for pattern in patterns) * settings.cut_width_mm
    total_waste_mm = sum(
        pattern.leftover_length_mm
        for pattern in patterns
        if pattern.leftover_type == "Отход"
    )
    total_useful_leftover_mm = sum(
        pattern.leftover_length_mm
        for pattern in patterns
        if pattern.leftover_type == "Полезный остаток"
    )

    total_stock_length_mm = sum(pattern.stock_length_mm for pattern in patterns)

    utilization_percent = 0.0
    if total_stock_length_mm > 0:
        utilization_percent = round(
            (total_parts_length_mm / total_stock_length_mm) * 100,
            2,
        )

    return SummaryRow(
        material_code=group.material.code,
        material_name=group.material.name,
        stock_length_mm=group.material.stock_length_mm,
        total_parts_count=total_parts_count,
        used_bars_count=len(patterns),
        total_parts_length_mm=total_parts_length_mm,
        total_cut_loss_mm=total_cut_loss_mm,
        total_waste_mm=total_waste_mm,
        total_useful_leftover_mm=total_useful_leftover_mm,
        utilization_percent=utilization_percent,
    )


def _build_production_rows(patterns: List[CuttingPattern]) -> List[ProductionRow]:
    grouped: Dict[Tuple[str, int, str], List[CuttingPattern]] = {}

    for pattern in patterns:
        key = (
            pattern.source_type,
            pattern.material_code,
            pattern.stock_length_mm,
            pattern.pattern_key,
        )
        grouped.setdefault(key, []).append(pattern)

    production_rows: List[ProductionRow] = []

    for _, group_patterns in grouped.items():
        first = group_patterns[0]

        production_rows.append(
            ProductionRow(
                source_type=first.source_type,
                material_code=first.material_code,
                material_name=first.material_name,
                stock_length_mm=first.stock_length_mm,
                pattern_text=first.pattern_as_text(),
                count=len(group_patterns),
                cuts_count=first.cuts_count,
                used_length_mm=first.used_length_mm,
                leftover_length_mm=first.leftover_length_mm,
                leftover_type=first.leftover_type,
            )
        )

    production_rows.sort(
        key=lambda row: (row.source_type, row.material_code, row.stock_length_mm, row.pattern_text)
    )

    return production_rows


def _build_leftovers(patterns: List[CuttingPattern]) -> List[Leftover]:
    leftovers: List[Leftover] = []

    for index, pattern in enumerate(patterns, start=1):
        if pattern.leftover_type != "Полезный остаток":
            continue

        leftovers.append(
            Leftover(
                id=f"LEFT-NEW-{index:04d}",
                material_code=pattern.material_code,
                material_name=pattern.material_name,
                length_mm=pattern.leftover_length_mm,
                stock_length_mm=pattern.stock_length_mm,
                source_pattern_id=pattern.id,
                note="Сформировано автоматически после расчета",
            )
        )

    return leftovers


def _get_matching_leftovers(material_code: str) -> List[Leftover]:
    all_leftovers = load_leftovers()
    matching = [
        item for item in all_leftovers
        if item.material_code == material_code
    ]
    matching.sort(key=lambda item: item.length_mm)
    return matching


def _collect_consumed_leftover_ids(patterns: List[CuttingPattern]) -> List[str]:
    consumed_ids = []

    for pattern in patterns:
        if pattern.source_type == "leftover" and pattern.source_leftover_id:
            consumed_ids.append(pattern.source_leftover_id)

    return consumed_ids


def _build_leftover_movements(
    consumed_leftover_ids: List[str],
    new_leftovers: List[Leftover],
) -> List[LeftoverMovementRow]:
    all_existing = load_leftovers()
    existing_by_id = {item.id: item for item in all_existing}

    movements: List[LeftoverMovementRow] = []

    for leftover_id in consumed_leftover_ids:
        item = existing_by_id.get(leftover_id)
        if item is None:
            movements.append(
                LeftoverMovementRow(
                    operation_type="Списан",
                    leftover_id=leftover_id,
                    material_code="",
                    material_name="",
                    length_mm=0,
                    note="Остаток использован в расчете",
                )
            )
        else:
            movements.append(
                LeftoverMovementRow(
                    operation_type="Списан",
                    leftover_id=item.id,
                    material_code=item.material_code,
                    material_name=item.material_name,
                    length_mm=item.length_mm,
                    note="Остаток использован в расчете",
                )
            )

    for item in new_leftovers:
        movements.append(
            LeftoverMovementRow(
                operation_type="Добавлен",
                leftover_id=item.id,
                material_code=item.material_code,
                material_name=item.material_name,
                length_mm=item.length_mm,
                note="Новый остаток после расчета",
            )
        )

    return movements


def calculate_cutting(
    materials: List[Material],
    parts: List[Part],
    settings: CalculationSettings,
) -> CalculationResult:
    result = CalculationResult()

    errors, warnings = validate_all(materials, parts, settings)
    result.errors.extend(errors)
    result.warnings.extend(warnings)

    if result.errors:
        return result

    prepared_groups = group_parts_by_material(parts, materials, settings)

    all_patterns: List[CuttingPattern] = []
    summary_rows: List[SummaryRow] = []

    for group in prepared_groups:
        matching_leftovers = []
        if settings.use_leftovers:
            matching_leftovers = _get_matching_leftovers(group.material.code)

        group_patterns = optimize_group(
            group,
            settings,
            available_leftovers=matching_leftovers,
        )
        all_patterns.extend(group_patterns)

        summary_row = _build_summary_row(group, group_patterns, settings)
        summary_rows.append(summary_row)

    result.patterns = all_patterns
    result.summary_rows = summary_rows
    result.production_rows = _build_production_rows(all_patterns)
    result.leftovers = _build_leftovers(all_patterns)
    result.consumed_leftover_ids = _collect_consumed_leftover_ids(all_patterns)
    result.leftover_movements = _build_leftover_movements(
        result.consumed_leftover_ids,
        result.leftovers,
    )

    return result