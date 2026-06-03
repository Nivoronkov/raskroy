"""
Миграция leftovers_db.json к каноническим кодам материала.

Логика:
  - если material_name содержит профиль+размер+марку — пересобираем код через
    единый модуль нормализации (надёжно);
  - если марки в name нет (старые коды CH-22P, TR-40x20x2) — НЕ угадываем,
    помечаем в отчёте как требующие ручного решения по марке.
Скрипт сначала ПОКАЗЫВАЕТ план, перезапись — только с флагом --apply.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.join(os.path.dirname(__file__), "smart_cut_app")))
from core.normalization import normalize_size, normalize_grade, material_code, PROFILE_TYPE_MAP

PROFILES = sorted(PROFILE_TYPE_MAP.keys(), key=len, reverse=True)


def parse_name(name: str):
    """Из 'Труба профильная 100х100х5 С345' -> (профиль, размер, марка) или None по марке."""
    n = (name or "").strip()
    profile = None
    for p in PROFILES:
        if n.startswith(p):
            profile = p
            n = n[len(p):].strip()
            break
    if not profile:
        return None, None, None
    parts = n.split()
    if not parts:
        return profile, None, None
    size = parts[0]
    grade = parts[1] if len(parts) > 1 else None
    return profile, size, grade


def main(apply: bool):
    path = os.path.join(os.path.join(os.path.dirname(__file__), "smart_cut_app"), "leftovers_db.json")
    data = json.load(open(path, encoding="utf-8"))

    changed, manual = [], []
    for it in data:
        old_code = it.get("material_code", "")
        profile, size, grade = parse_name(it.get("material_name", ""))
        if profile and size and grade:
            new_code = material_code(profile, size, grade)
            new_name = f"{profile} {normalize_size(size)} {normalize_grade(grade)}"
            if new_code and new_code != old_code:
                changed.append((old_code, new_code, it["id"]))
                it["material_code"] = new_code
                it["material_name"] = new_name
        else:
            manual.append((old_code, it.get("material_name", ""), it["id"]))

    print("=== ПЛАН МИГРАЦИИ ОСТАТКОВ ===")
    print(f"Всего остатков: {len(data)}")
    print(f"\nБудут перекодированы ({len(changed)}):")
    seen = set()
    for old, new, _id in changed:
        if (old, new) not in seen:
            seen.add((old, new))
            print(f"  {old:24} -> {new}")
    print(f"\nТРЕБУЮТ РУЧНОГО РЕШЕНИЯ — нет марки в наименовании ({len(manual)}):")
    seenm = set()
    for old, name, _id in manual:
        if old not in seenm:
            seenm.add(old)
            cnt = sum(1 for x in manual if x[0] == old)
            print(f"  {old:24} '{name}'  ({cnt} шт.) — добавьте марку стали")

    if apply:
        # бэкап
        bak = path + ".bak"
        if not os.path.exists(bak):
            json.dump(json.load(open(path, encoding="utf-8")), open(bak, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n✓ Применено. Бэкап: {os.path.basename(bak)}")
    else:
        print("\n(показан только план; для записи запустите с --apply)")


if __name__ == "__main__":
    main("--apply" in sys.argv)
