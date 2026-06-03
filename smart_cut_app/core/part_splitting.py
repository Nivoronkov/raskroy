"""
Разделение составной детали (длиннее хлыста) на части.

Деталь, которая длиннее доступного хлыста (например, сварной швеллер 24П
длиной 13500 мм), не может быть раскроена целиком. По решению конструктора под
конкретный заказ она режется на части (обычно 2, иногда больше). Здесь — логика
формирования частей; на сколько и как делить, задаёт оператор в диалоге.

Правила (согласованы с производством):
  - минимум 2 части;
  - сумма длин частей >= исходной длины (деталь должна быть цельной);
  - превышение допустимо не более MAX_OVERHANG_MM (напуск на сварку);
  - каждая часть участвует в раскрое как отдельная деталь с пометкой 'ч.N'.

Разбиение применяется на всё количество исходной детали. Архитектура (поля
split_parent_id / part_index у Part) оставляет задел на то, чтобы в будущем
разные экземпляры одной детали можно было делить по-разному.
"""
from typing import List

from core.models import Part

MAX_OVERHANG_MM = 10  # допустимый суммарный напуск на сварку


def split_lengths_equal(total_length_mm: int, n_parts: int) -> List[int]:
    """Делит длину на n равных частей; остаток округления — в последнюю часть."""
    if n_parts < 2:
        raise ValueError("Число частей должно быть не меньше 2.")
    base = total_length_mm // n_parts
    lengths = [base] * n_parts
    lengths[-1] += total_length_mm - base * n_parts
    return lengths


def validate_split(total_length_mm: int, part_lengths: List[int]) -> List[str]:
    """Проверяет корректность разбиения. Пустой список = всё в порядке."""
    errors: List[str] = []
    if len(part_lengths) < 2:
        errors.append("Деталь нужно разделить минимум на 2 части.")
    if any(L <= 0 for L in part_lengths):
        errors.append("Длина каждой части должна быть больше 0.")
        return errors
    s = sum(part_lengths)
    if s < total_length_mm:
        errors.append(
            f"Сумма частей ({s} мм) меньше исходной длины ({total_length_mm} мм) — "
            f"деталь не будет цельной."
        )
    elif s > total_length_mm + MAX_OVERHANG_MM:
        errors.append(
            f"Сумма частей ({s} мм) превышает исходную ({total_length_mm} мм) "
            f"более чем на {MAX_OVERHANG_MM} мм. Уменьшите длины частей."
        )
    return errors


def build_split_parts(source: Part, part_lengths: List[int]) -> List[Part]:
    """
    Создаёт детали-части из исходной составной детали.
    Каждая часть наследует материал/количество/исполнение исходной и получает
    пометку 'ч.N'. Возвращает список Part (по одной на каждую часть).
    """
    errors = validate_split(source.length_mm, part_lengths)
    if errors:
        raise ValueError("; ".join(errors))

    n = len(part_lengths)
    result: List[Part] = []
    for i, length in enumerate(part_lengths, start=1):
        # к краткому примечанию добавляем 'ч.N' (для схемы раскроя)
        base_note = (source.note or "").strip()
        short = f"ч.{i}"
        note = f"{base_note} {short}".strip() if base_note else short
        result.append(
            Part(
                id=f"{source.id}-ч{i}",
                designation=source.designation,
                name=source.name,
                material_code=source.material_code,
                length_mm=length,
                quantity=source.quantity,
                assembly=source.assembly,
                note=note,
                part_index=i,
                split_parent_id=source.id,
                split_total_parts=n,
            )
        )
    return result


def apply_splits(parts: List[Part], splits: dict) -> List[Part]:
    """
    Применяет разбиения к списку деталей.
    splits: {part_id: [длины частей]} — какие детали как делить.
    Детали без записи в splits остаются как есть; делимые заменяются частями.
    """
    result: List[Part] = []
    for p in parts:
        if p.id in splits:
            result.extend(build_split_parts(p, splits[p.id]))
        else:
            result.append(p)
    return result
