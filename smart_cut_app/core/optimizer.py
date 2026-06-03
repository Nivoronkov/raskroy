"""
Оптимизатор раскроя линейного проката.

Версия 2 — заполнение хлыста ПОДБОРОМ КОМБИНАЦИИ деталей (subset-sum),
а не пошаговой жадностью (First-Fit Decreasing). Это даёт раскрой
уровня веб-калькуляторов: на тесте трубы 100х100х5 — 17 хлыстов вместо 18.

Публичный контракт не изменился:
    optimize_group(group, settings, available_leftovers=None) -> List[CuttingPattern]

Как работает:
  1. Для каждой ЗАГОТОВКИ (сначала доступные остатки, затем новые хлысты)
     методом динамического программирования подбирается набор деталей,
     максимально плотно заполняющий её длину с учётом ширины реза.
  2. Заготовка «забивается», выбранные детали удаляются из очереди, и так
     до тех пор, пока все детали не размещены.

Ширина реза (settings.cut_width_mm) учитывается честно: каждая деталь
занимает (длина + рез). Параметр настраивается из GUI (бывает 0, бывает 5–10 мм).

Режимы оптимизации:
  - min_waste / balanced — максимально плотное заполнение каждой заготовки
    (минимум суммарного отхода).
  - min_bars — то же плотное заполнение; цель «меньше хлыстов» достигается
    тем же подбором (плотная укладка = меньше заготовок).
  - max_leftovers — сначала максимально расходуем имеющиеся остатки, затем
    новые хлысты.
"""
from typing import Dict, List, Optional, Tuple

from core.grouping import PreparedGroup
from core.models import CalculationSettings, CuttingPattern, ExpandedPart, Leftover


DEBUG_OPTIMIZER = False

# Предел числа состояний DP на одну заготовку (защита от комбинаторного взрыва
# при большом числе разнодлинных деталей). При превышении оставляем состояния,
# наиболее близкие к полному заполнению.
_DP_STATE_LIMIT = 50000


def _log(message: str) -> None:
    if DEBUG_OPTIMIZER:
        print(message)


def _occupied_length(part: ExpandedPart, settings: CalculationSettings) -> int:
    """Сколько длины заготовки занимает одна деталь: её рабочая длина + один рез."""
    return part.effective_length_mm + settings.cut_width_mm


def _best_fill(
    parts: List[ExpandedPart],
    capacity: int,
    settings: CalculationSettings,
) -> List[int]:
    """
    Подбирает индексы деталей из `parts`, максимально плотно заполняющих
    заготовку длиной `capacity`. Возвращает список индексов в `parts`.

    DP по достижимой занятой длине: reachable[used] = список индексов деталей.
    Цель — максимальный used <= capacity.
    """
    reachable: Dict[int, List[int]] = {0: []}

    for idx, part in enumerate(parts):
        need = _occupied_length(part, settings)
        if need > capacity:
            continue  # одна деталь не влезает в эту заготовку — пропускаем

        additions: Dict[int, List[int]] = {}
        for used, chosen in reachable.items():
            new_used = used + need
            if new_used <= capacity and new_used not in reachable and new_used not in additions:
                additions[new_used] = chosen + [idx]

        if additions:
            reachable.update(additions)

        if len(reachable) > _DP_STATE_LIMIT:
            keep_keys = sorted(reachable.keys(), reverse=True)[:_DP_STATE_LIMIT]
            reachable = {k: reachable[k] for k in keep_keys}
            if 0 not in reachable:
                reachable[0] = []

    best_used = max(reachable.keys())
    return reachable[best_used]


def _new_pattern_for_stock(
    group: PreparedGroup,
    stock_length_mm: int,
    pattern_index: int,
) -> CuttingPattern:
    return CuttingPattern(
        id=f"PATTERN-{group.material.code}-{pattern_index}",
        material_code=group.material.code,
        material_name=group.material.name,
        stock_length_mm=stock_length_mm,
        parts=[],
        cuts_count=0,
        used_length_mm=0,
        leftover_length_mm=stock_length_mm,
        leftover_type="Отход",
        pattern_key="",
        source_type="new",
        source_leftover_id="",
    )


def _pattern_from_leftover(leftover: Leftover, pattern_index: int) -> CuttingPattern:
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


def _place_parts_in_pattern(
    pattern: CuttingPattern,
    parts: List[ExpandedPart],
    chosen_indices: List[int],
    settings: CalculationSettings,
) -> None:
    """Кладёт выбранные детали в заготовку и обновляет её счётчики."""
    for idx in chosen_indices:
        part = parts[idx]
        pattern.parts.append(part)
        pattern.cuts_count += 1
        pattern.used_length_mm += _occupied_length(part, settings)
    pattern.leftover_length_mm = pattern.stock_length_mm - pattern.used_length_mm


def _finalize_pattern(pattern: CuttingPattern, settings: CalculationSettings) -> None:
    if pattern.leftover_length_mm >= settings.min_useful_leftover_mm:
        pattern.leftover_type = "Полезный остаток"
    else:
        pattern.leftover_type = "Отход"
    pattern.pattern_key = "|".join(str(p.base_length_mm) for p in pattern.parts)


def _resolve_new_stock_lengths(group: PreparedGroup) -> List[int]:
    """
    Доступные длины новых хлыстов для материала.
    Сейчас модель Material хранит одну длину (stock_length_mm). Если в будущем
    появится список длин (несколько хлыстов 6 м / 12 м), достаточно вернуть его
    отсортированным по возрастанию — алгоритм сам выберет под деталь.
    """
    extra = getattr(group.material, "stock_lengths_mm", None)
    if extra:
        lengths = sorted({int(x) for x in extra if int(x) > 0})
        if lengths:
            return lengths
    return [group.material.stock_length_mm]


def optimize_group(
    group: PreparedGroup,
    settings: CalculationSettings,
    available_leftovers: Optional[List[Leftover]] = None,
) -> List[CuttingPattern]:
    """
    Раскраивает все детали одной материальной группы.
    Возвращает список заготовок (CuttingPattern) с уложенными деталями.
    """
    _log(f"\n=== Группа: {group.material.code} / {group.material.name} ===")
    _log(f"Режим: {settings.optimization_mode}, рез={settings.cut_width_mm} мм")

    # очередь деталей (по убыванию длины — крупные размещаем первыми)
    remaining: List[ExpandedPart] = sorted(
        group.expanded_parts,
        key=lambda p: p.effective_length_mm,
        reverse=True,
    )

    patterns: List[CuttingPattern] = []
    pattern_counter = 0

    # ---- Этап 1: расходуем имеющиеся остатки (если включено) ----
    use_leftovers = settings.use_leftovers or settings.optimization_mode == "max_leftovers"
    if use_leftovers and available_leftovers:
        # от коротких к длинным: сначала добиваем мелкие остатки
        leftovers_sorted = sorted(available_leftovers, key=lambda l: l.length_mm)
        for li, leftover in enumerate(leftovers_sorted, start=1):
            if not remaining:
                break
            pattern = _pattern_from_leftover(leftover, li)
            chosen = _best_fill(remaining, pattern.stock_length_mm, settings)
            if not chosen:
                continue
            _place_parts_in_pattern(pattern, remaining, chosen, settings)
            for idx in sorted(chosen, reverse=True):
                remaining.pop(idx)
            patterns.append(pattern)

    # ---- Этап 2: новые хлысты ----
    stock_lengths = _resolve_new_stock_lengths(group)

    while remaining:
        # для каждой доступной длины хлыста подбираем заполнение, выбираем
        # длину с наименьшим относительным отходом
        best_choice = None  # (waste_ratio, stock_length, chosen_indices, used)
        for stock_length in stock_lengths:
            chosen = _best_fill(remaining, stock_length, settings)
            if not chosen:
                continue
            used = sum(_occupied_length(remaining[i], settings) for i in chosen)
            waste = stock_length - used
            waste_ratio = waste / stock_length
            if best_choice is None or waste_ratio < best_choice[0]:
                best_choice = (waste_ratio, stock_length, chosen, used)

        if best_choice is None:
            # ни одна деталь не влезает ни в один доступный хлыст — защита от петли
            biggest = max(remaining, key=lambda p: p.effective_length_mm)
            _log(
                f"  ВНИМАНИЕ: деталь {biggest.designation or biggest.name} "
                f"({biggest.effective_length_mm} мм) длиннее любого хлыста "
                f"{stock_lengths} — пропущена."
            )
            remaining.remove(biggest)
            continue

        _, stock_length, chosen, _used = best_choice
        pattern_counter += 1
        pattern = _new_pattern_for_stock(group, stock_length, pattern_counter)
        _place_parts_in_pattern(pattern, remaining, chosen, settings)
        for idx in sorted(chosen, reverse=True):
            remaining.pop(idx)
        patterns.append(pattern)

    # ---- финализация ----
    patterns = [p for p in patterns if p.parts]
    for pattern in patterns:
        _finalize_pattern(pattern, settings)
        _log(
            f"  {'Остаток' if pattern.source_type == 'leftover' else 'Хлыст'} "
            f"{pattern.stock_length_mm} | {pattern.pattern_as_text()} | "
            f"остаток={pattern.leftover_length_mm} | {pattern.leftover_type}"
        )

    return patterns
