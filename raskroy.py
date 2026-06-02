"""
РАСКРОЙ ИЗ СПЕЦИФИКАЦИИ — скрипт "всё в одном" для отладки.

Что делает:
  1. Читает выгрузку спецификации Компас (.xls)
  2. Конвертирует в формат калькулятора (через sp_to_cutlist)
  3. Сверяется со справочником склада (materials_catalog.json)
  4. Сообщает, каких материалов на складе НЕТ (предлагает добавить)
  5. Считает раскрой и сохраняет готовую карту в Excel

Запуск:
    python raskroy.py "имя_спецификации.xls"

Результат: два файла рядом со спецификацией:
    <имя>_вход.xlsx       — что система поняла (Детали/Материалы/Проверка/Отсечено)
    <имя>_раскрой.xlsx    — готовая карта раскроя
"""
import sys
import os
import json

# --- пути к калькулятору (папка smart_cut_app должна лежать рядом) ---
HERE = os.path.dirname(os.path.abspath(__file__))
CALC_DIR = os.path.join(HERE, "smart_cut_app")
sys.path.insert(0, CALC_DIR)
sys.path.insert(0, HERE)

from sp_to_cutlist import main as convert_sp
from data.excel_importer import import_materials_from_excel, import_parts_from_excel
from core.cutting_engine import calculate_cutting
from core.models import CalculationSettings
from data.excel_exporter import export_result_to_excel

CATALOG_FILE = os.path.join(CALC_DIR, "materials_catalog.json")


def load_catalog_codes():
    """Возвращает множество кодов материалов, которые есть в справочнике склада."""
    if not os.path.exists(CATALOG_FILE):
        return {}
    with open(CATALOG_FILE, encoding="utf-8") as f:
        items = json.load(f)
    return {it["material_code"]: it for it in items}


def main():
    if len(sys.argv) < 2:
        print("Использование: python raskroy.py \"спецификация.xls\"")
        sys.exit(1)

    src = sys.argv[1]
    if not os.path.exists(src):
        print(f"ОШИБКА: файл не найден: {src}")
        sys.exit(1)

    base = os.path.splitext(src)[0]
    f_in = base + "_вход.xlsx"
    f_out = base + "_раскрой.xlsx"

    print("=" * 70)
    print("ШАГ 1. Чтение спецификации и конвертация")
    print("=" * 70)
    convert_sp(src, f_in)

    print()
    print("=" * 70)
    print("ШАГ 2. Сверка материалов со справочником склада")
    print("=" * 70)
    catalog = load_catalog_codes()
    materials = import_materials_from_excel(f_in)
    parts = import_parts_from_excel(f_in)

    missing = []
    for m in materials:
        if m.code in catalog:
            cat = catalog[m.code]
            m.stock_length_mm = cat.get("stock_length_mm", 6000) or 6000
            m.available_count = cat.get("available_stock_bars", 0)
            print(f"  [ЕСТЬ]  {m.code}  (склад: {m.available_count} хл. по {m.stock_length_mm} мм)")
        else:
            missing.append(m)
            # для отладки даём хлысты, чтобы расчёт прошёл
            if m.stock_length_mm == 0:
                m.stock_length_mm = 6000
            m.available_count = 999
            print(f"  [НЕТ В СПРАВОЧНИКЕ]  {m.code}  ->  нужно добавить на склад")

    if missing:
        print()
        print(f"  ВНИМАНИЕ: {len(missing)} материал(ов) отсутствует в справочнике склада.")
        print("  Их нужно добавить вручную (указать длины хлыстов в наличии).")
        print("  Список см. выше с пометкой [НЕТ В СПРАВОЧНИКЕ].")
        print("  Сейчас для расчёта они взяты как хлыст 6000 мм (заглушка).")

    print()
    print("=" * 70)
    print("ШАГ 3. Расчёт раскроя")
    print("=" * 70)
    settings = CalculationSettings(
        cut_width_mm=2,            # ширина реза, мм
        trim_allowance_mm=0,       # припуск на торцовку
        min_useful_leftover_mm=300, # что считать полезным остатком
        optimization_mode="min_waste",
        use_leftovers=False,
    )
    res = calculate_cutting(materials, parts, settings)

    if not res.success:
        print("  ОШИБКИ расчёта:")
        for e in res.errors:
            print("   -", e)
        sys.exit(1)

    for row in res.summary_rows:
        print(f"  {row.material_code:24} хлыстов={row.used_bars_count:2}  "
              f"деталей={row.total_parts_count:3}  исп.={row.utilization_percent:5.1f}%  "
              f"отход={row.total_waste_mm} мм")

    export_result_to_excel(res, f_out)
    print()
    print("=" * 70)
    print("ГОТОВО")
    print("=" * 70)
    print(f"  Проверка обработки : {f_in}")
    print(f"  Карта раскроя      : {f_out}")


if __name__ == "__main__":
    main()
