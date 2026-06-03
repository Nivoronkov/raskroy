"""Тесты разделения составной детали."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "smart_cut_app"))

import pytest
from core.models import Part, Material, CalculationSettings
from core.part_splitting import (
    split_lengths_equal, validate_split, build_split_parts, apply_splits, MAX_OVERHANG_MM
)
from core.cutting_engine import calculate_cutting


def test_деление_поровну():
    assert split_lengths_equal(13500, 2) == [6750, 6750]
    assert split_lengths_equal(13500, 3) == [4500, 4500, 4500]
    # остаток округления — в последнюю часть, сумма сохраняется
    parts = split_lengths_equal(13501, 2)
    assert sum(parts) == 13501


def test_деление_минимум_две_части():
    with pytest.raises(ValueError):
        split_lengths_equal(13500, 1)


def test_валидация_сумма_меньше():
    errs = validate_split(13500, [6000, 6000])
    assert errs and "меньше" in errs[0]


def test_валидация_напуск_допустим():
    # +10 мм (ровно граница напуска) — принимается
    assert validate_split(13500, [6750, 6760]) == []


def test_валидация_напуск_превышен():
    # +20 мм — отклоняется
    errs = validate_split(13500, [6760, 6760])
    assert errs and "превышает" in errs[0]


def test_части_получают_пометку():
    src = Part(id="P1", designation="д", name="Швеллер 24П",
               material_code="ШВ-24П-С355", length_mm=13500, quantity=3, note="4")
    parts = build_split_parts(src, [6750, 6750])
    assert len(parts) == 2
    assert parts[0].part_index == 1 and "ч.1" in parts[0].note
    assert parts[1].part_index == 2 and "ч.2" in parts[1].note
    # количество и материал наследуются
    assert all(p.quantity == 3 and p.material_code == "ШВ-24П-С355" for p in parts)


def test_apply_splits_заменяет_только_делимые():
    a = Part(id="A", designation="", name="дл", material_code="M", length_mm=13500, quantity=1)
    b = Part(id="B", designation="", name="кор", material_code="M", length_mm=2000, quantity=1)
    out = apply_splits([a, b], {"A": [6750, 6750]})
    ids = [p.id for p in out]
    assert "A-ч1" in ids and "A-ч2" in ids and "B" in ids
    assert "A" not in ids


def test_разделённые_части_раскраиваются():
    src = Part(id="P1", designation="д", name="Швеллер 24П",
               material_code="ШВ-24П-С355", length_mm=13500, quantity=2, note="")
    mat = [Material(id="M", code="ШВ-24П-С355", name="Швеллер 24П",
                    profile_type="Швеллер", size="24П", grade="С355",
                    stock_length_mm=12000, available_count=999)]
    parts = apply_splits([src], {"P1": [6750, 6750]})
    r = calculate_cutting(mat, parts, CalculationSettings(optimization_mode="min_waste"))
    assert not r.errors
    assert r.summary_rows[0].total_parts_count == 4  # 2шт x 2 части
