from typing import List, Optional, Tuple

from core.grouping import PreparedGroup
from core.models import CalculationSettings, CuttingPattern, ExpandedPart, Leftover


DEBUG_OPTIMIZER = False


def _log(message: str) -> None:
    if DEBUG_OPTIMIZER:
        print(message)


def _calculate_additional_length(
    pattern: CuttingPattern,
    part: ExpandedPart,
    settings: CalculationSettings,
) -> int:
    """
    Каждая деталь учитывается вместе с одним резом.
    """
    return settings.cut_width_mm + part.effective_length_mm


def _can_fit_part(
    pattern: CuttingPattern,
    part: ExpandedPart,
    settings: CalculationSettings,
) -> bool:
    additional_length = _calculate_additional_length(pattern, part, settings)
    return pattern.used_length_mm + additional_length <= pattern.stock_length_mm


def _add_part_to_pattern(
    pattern: CuttingPattern,
    part: ExpandedPart,
    settings: CalculationSettings,
) -> None:
    additional_length = _calculate_additional_length(pattern, part, settings)

    pattern.cuts_count += 1
    pattern.parts.append(part)
    pattern.used_length_mm += additional_length
    pattern.leftover_length_mm = pattern.stock_length_mm - pattern.used_length_mm


def _build_pattern_key(pattern: CuttingPattern) -> str:
    lengths = [str(part.base_length_mm) for part in pattern.parts]
    return "|".join(lengths)


def _finalize_pattern(
    pattern: CuttingPattern,
    settings: CalculationSettings,
) -> None:
    if pattern.leftover_length_mm >= settings.min_useful_leftover_mm:
        pattern.leftover_type = "Полезный остаток"
    else:
        pattern.leftover_type = "Отход"

    pattern.pattern_key = _build_pattern_key(pattern)


def _create_empty_pattern(
    group: PreparedGroup,
    pattern_index: int,
) -> CuttingPattern:
    return CuttingPattern(
        id=f"PATTERN-{group.material.code}-{pattern_index}",
        material_code=group.material.code,
        material_name=group.material.name,
        stock_length_mm=group.material.stock_length_mm,
        parts=[],
        cuts_count=0,
        used_length_mm=0,
        leftover_length_mm=group.material.stock_length_mm,
        leftover_type="Отход",
        pattern_key="",
        source_type="new",
        source_leftover_id="",
    )


def _create_pattern_from_leftover(
    leftover: Leftover,
    pattern_index: int,
) -> CuttingPattern:
    return CuttingPattern(
        id=f"PATTERN-LEFT-{pattern_index}",
        material_code=leftover.material_code,
        material_name=leftover.material_name,
        stock_length_mm=leftover.length_mm,
        parts=[],
        cuts_count=0,
        used_length_mm=0,
        leftover_length_mm=leftover.length_mm,
        leftover_type="Отход",
        pattern_key="",
        source_type="leftover",
        source_leftover_id=leftover.id,
    )


def _remaining_length_after_add(
    pattern: CuttingPattern,
    part: ExpandedPart,
    settings: CalculationSettings,
) -> int:
    additional_length = _calculate_additional_length(pattern, part, settings)
    return pattern.stock_length_mm - (pattern.used_length_mm + additional_length)


def _score_pattern(
    pattern: CuttingPattern,
    part: ExpandedPart,
    settings: CalculationSettings,
) -> Tuple:
    """
    Чем меньше score, тем предпочтительнее паттерн.
    """
    remaining_length = _remaining_length_after_add(pattern, part, settings)
    is_leftover = 0 if pattern.source_type == "leftover" else 1

    mode = settings.optimization_mode

    if mode == "max_leftovers":
        return (is_leftover, remaining_length)

    if mode == "balanced":
        return (is_leftover, remaining_length)

    return (remaining_length, is_leftover)


def _find_best_pattern(
    candidate_patterns: List[CuttingPattern],
    part: ExpandedPart,
    settings: CalculationSettings,
) -> Optional[CuttingPattern]:
    best_pattern: Optional[CuttingPattern] = None
    best_score: Optional[Tuple] = None

    for pattern in candidate_patterns:
        additional_length = _calculate_additional_length(pattern, part, settings)
        will_fit = pattern.used_length_mm + additional_length <= pattern.stock_length_mm

        _log(
            f"    Проверка источника: "
            f"{'Остаток' if pattern.source_type == 'leftover' else 'Новый хлыст'} | "
            f"длина={pattern.stock_length_mm} | "
            f"уже занято={pattern.used_length_mm} | "
            f"нужно добавить={additional_length} | "
            f"помещается={'Да' if will_fit else 'Нет'}"
        )

        if not will_fit:
            continue

        score = _score_pattern(pattern, part, settings)
        _log(f"      score={score}")

        if best_pattern is None or score < best_score:
            best_pattern = pattern
            best_score = score
            _log("      -> пока лучший вариант")

    return best_pattern


def _find_best_pattern_min_bars(
    patterns: List[CuttingPattern],
    part: ExpandedPart,
    settings: CalculationSettings,
) -> Optional[CuttingPattern]:
    """
    Специальная логика для режима min_bars:
    1. Сначала стараемся заполнить уже открытые НОВЫЕ хлысты
    2. Потом пробуем остатки
    3. И только потом открываем новый хлыст
    """
    opened_new_patterns = [p for p in patterns if p.source_type == "new" and p.parts]
    leftover_patterns = [p for p in patterns if p.source_type == "leftover"]

    _log("  Режим min_bars: сначала ищем среди уже открытых новых хлыстов.")
    best_pattern = _find_best_pattern(opened_new_patterns, part, settings)
    if best_pattern is not None:
        _log(
            f"  Найден уже открытый новый хлыст | длина заготовки={best_pattern.stock_length_mm}"
        )
        return best_pattern

    _log("  В уже открытые новые хлысты не помещается, пробуем остатки.")
    best_pattern = _find_best_pattern(leftover_patterns, part, settings)
    if best_pattern is not None:
        _log(
            f"  Найден подходящий остаток | длина заготовки={best_pattern.stock_length_mm}"
        )
        return best_pattern

    _log("  Ни открытые новые хлысты, ни остатки не подошли.")
    return None


def _pack_parts_into_patterns(
    parts_to_place: List[ExpandedPart],
    candidate_patterns: List[CuttingPattern],
    settings: CalculationSettings,
    create_new_pattern_fn=None,
) -> Tuple[List[ExpandedPart], List[CuttingPattern]]:
    """
    Укладывает детали в существующие candidate_patterns.
    Если create_new_pattern_fn задана, при невозможности укладки открывает новую заготовку.
    Возвращает:
    - список неуложенных деталей
    - итоговый список паттернов
    """
    remaining_parts: List[ExpandedPart] = []

    for part in parts_to_place:
        best_pattern = _find_best_pattern(candidate_patterns, part, settings)

        if best_pattern is None:
            if create_new_pattern_fn is None:
                remaining_parts.append(part)
            else:
                new_pattern = create_new_pattern_fn()
                _add_part_to_pattern(new_pattern, part, settings)
                candidate_patterns.append(new_pattern)

                _log(
                    f"  Деталь добавлена в новый хлыст | "
                    f"использовано={new_pattern.used_length_mm} | "
                    f"остаток={new_pattern.leftover_length_mm}"
                )
        else:
            _add_part_to_pattern(best_pattern, part, settings)
            _log(
                f"  Деталь добавлена в "
                f"{'остаток' if best_pattern.source_type == 'leftover' else 'новый хлыст'} | "
                f"использовано={best_pattern.used_length_mm} | "
                f"остаток={best_pattern.leftover_length_mm}"
            )

    return remaining_parts, candidate_patterns


def optimize_group(
    group: PreparedGroup,
    settings: CalculationSettings,
    available_leftovers: Optional[List[Leftover]] = None,
) -> List[CuttingPattern]:
    patterns: List[CuttingPattern] = []

    _log(f"\n=== Группа материала: {group.material.code} / {group.material.name} ===")
    _log(f"Режим оптимизации: {settings.optimization_mode}")
    _log(f"Учитывать остатки: {settings.use_leftovers}")

    leftover_patterns: List[CuttingPattern] = []
    if available_leftovers:
        available_leftovers = sorted(available_leftovers, key=lambda item: item.length_mm)

        _log("Доступные остатки:")
        for leftover in available_leftovers:
            _log(
                f"  - {leftover.id}: материал={leftover.material_code}, длина={leftover.length_mm}"
            )

        for index, leftover in enumerate(available_leftovers, start=1):
            leftover_patterns.append(_create_pattern_from_leftover(leftover, index))
    else:
        _log("Подходящих остатков нет.")

    # Специальный двухэтапный режим
    if settings.optimization_mode == "max_leftovers":
        _log("\n--- Этап 1: максимально укладываем в остатки ---")
        parts_not_placed, used_leftover_patterns = _pack_parts_into_patterns(
            parts_to_place=group.expanded_parts,
            candidate_patterns=leftover_patterns,
            settings=settings,
            create_new_pattern_fn=None,
        )

        used_leftover_patterns = [p for p in used_leftover_patterns if p.parts]

        _log("\n--- Этап 2: оставшиеся детали укладываем в новые хлысты ---")
        new_patterns: List[CuttingPattern] = []

        pattern_counter = 0

        def create_new_pattern():
            nonlocal pattern_counter
            pattern_counter += 1
            _log("  Открывается новый хлыст.")
            return _create_empty_pattern(group, pattern_counter)

        _, new_patterns = _pack_parts_into_patterns(
            parts_to_place=parts_not_placed,
            candidate_patterns=new_patterns,
            settings=settings,
            create_new_pattern_fn=create_new_pattern,
        )

        patterns = used_leftover_patterns + new_patterns

    else:
        patterns = list(leftover_patterns)

        for part in group.expanded_parts:
            _log(
                f"\nОбрабатывается деталь: "
                f"{part.designation or part.name} | "
                f"чистая длина={part.base_length_mm} | "
                f"расчетная длина={part.effective_length_mm + settings.cut_width_mm}"
            )

            best_pattern: Optional[CuttingPattern] = None

            if settings.optimization_mode == "min_bars":
                best_pattern = _find_best_pattern_min_bars(patterns, part, settings)

            else:
                leftover_candidates = [p for p in patterns if p.source_type == "leftover"]
                new_candidates = [p for p in patterns if p.source_type == "new"]

                _log("  Сначала ищем среди остатков.")
                best_pattern = _find_best_pattern(leftover_candidates, part, settings)

                if best_pattern is not None:
                    _log(
                        f"  Найден подходящий остаток | длина заготовки={best_pattern.stock_length_mm}"
                    )
                else:
                    _log("  Подходящий остаток не найден, ищем среди новых хлыстов.")
                    best_pattern = _find_best_pattern(new_candidates, part, settings)

                    if best_pattern is not None:
                        _log(
                            f"  Найден подходящий новый хлыст | длина заготовки={best_pattern.stock_length_mm}"
                        )

            if best_pattern is None:
                _log("  Открывается новый хлыст.")

                new_pattern = _create_empty_pattern(group, len(patterns) + 1)
                _add_part_to_pattern(new_pattern, part, settings)
                patterns.append(new_pattern)

                _log(
                    f"  Деталь добавлена в новый хлыст | "
                    f"использовано={new_pattern.used_length_mm} | "
                    f"остаток={new_pattern.leftover_length_mm}"
                )
            else:
                _add_part_to_pattern(best_pattern, part, settings)

                _log(
                    f"  Деталь добавлена в "
                    f"{'остаток' if best_pattern.source_type == 'leftover' else 'новый хлыст'} | "
                    f"использовано={best_pattern.used_length_mm} | "
                    f"остаток={best_pattern.leftover_length_mm}"
                )

    patterns = [pattern for pattern in patterns if pattern.parts]

    _log("\nИтог по группе:")
    for pattern in patterns:
        _finalize_pattern(pattern, settings)
        _log(
            f"  - "
            f"{'Остаток' if pattern.source_type == 'leftover' else 'Новый хлыст'} | "
            f"длина={pattern.stock_length_mm} | "
            f"состав={pattern.pattern_as_text()} | "
            f"резов={pattern.cuts_count} | "
            f"остаток={pattern.leftover_length_mm} | "
            f"тип={pattern.leftover_type}"
        )

    return patterns