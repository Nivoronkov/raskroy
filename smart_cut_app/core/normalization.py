"""
Единый модуль нормализации обозначений материала.

ЕДИНЫЙ ФОРМАТ для всего проекта (заполнение справочника, выгрузка из
спецификации, сверка со складом) — чтобы один и тот же материал всегда давал
ОДИН код, без дублей из-за регистра или написания марки.

Канон кода материала:  ПРЕФИКС-РАЗМЕР-МАРКА
  префикс — кириллица (ТР-П, ТР-К, ШВ, УГ, ПЛ, КР, ...)
  размер  — нижний регистр кириллицы, разделитель 'х'   (100х100х5)
  марка   — каноническая (Ст3, С255, 09Г2С, Сталь10)

Все три источника кода (конвертер sp_to_cutlist, диалог справочника,
сверка) должны звать функции отсюда и только отсюда.
"""
import json
import os
import re
from typing import Optional

# ---- префиксы профилей (единый источник истины) ----
PROFILE_TYPE_MAP = {
    "Труба профильная": "ТР-П",
    "Труба круглая": "ТР-К",
    "Швеллер": "ШВ",
    "Уголок": "УГ",
    "Полоса": "ПЛ",
    "Круг": "КР",
    "Лист": "ЛИСТ",
    "Балка тавровая": "БЛ-Т",
    "Балка двутавровая": "БЛ-ТД",
}

# ---- редактируемый список исключений по маркам ----
# Грузится из grade_aliases.json рядом с этим модулем (если есть).
# Ключ — как пишут (в ВЕРХНЕМ регистре, без пробелов), значение — канон.
_DEFAULT_GRADE_ALIASES = {
    "СТАЛЬ3": "Ст3",
}

_ALIASES_FILE = os.path.join(os.path.dirname(__file__), "grade_aliases.json")


def _load_grade_aliases() -> dict:
    aliases = dict(_DEFAULT_GRADE_ALIASES)
    if os.path.exists(_ALIASES_FILE):
        try:
            with open(_ALIASES_FILE, encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                aliases[re.sub(r"\s+", "", str(k)).upper()] = str(v).strip()
        except (OSError, json.JSONDecodeError):
            pass
    return aliases


def normalize_size(size: str) -> str:
    """
    Размер -> единый вид: разделитель 'х', без пробелов.
    Сечения типа 100Х100Х5 / 100x100x5 / '100 х 100 х 5' -> '100х100х5' (нижний).
    Номер профиля с буквой серии (швеллер 18П, 8У, балка 20Б1) -> буква серии
    остаётся ЗАГЛАВНОЙ кириллицей: '18П', '8П' (это не размер, а серия).
    """
    if not size:
        return ""
    s = str(size).strip()
    s = re.sub(r"\s+", "", s)                 # убрать пробелы
    # разделитель сечения -> кириллическая 'х' (любой регистр, латиница, звёздочка)
    s = re.sub(r"[xXхХ*]", "х", s)
    s = re.sub(r"х+", "х", s)
    # номер профиля вида ЧИСЛО+БУКВА(Ы) (швеллер/балка): 18п/18u/18У -> 18П
    m = re.fullmatch(r"(\d+)([a-zA-Zа-яА-Я]+\d*)", s)
    if m:
        letters = (
            m.group(2).upper()
            .replace("U", "П").replace("Y", "У")  # латинские U/Y -> кириллица
        )
        return f"{m.group(1)}{letters}"
    return s.lower()


def normalize_grade(raw: str) -> str:
    """
    Марка стали -> каноническая форма проката.

    Правила (по требованиям производства):
      - Ст3пс / Ст3сп / Ст3кп / Ст3пс3-св / Ст3Гпс ... -> Ст3
      - С255 / С255-4 / С255К / С345-3 ...             -> С255 / С345 (класс прочности)
      - 09Г2С / 09Г2С-12                               -> 09Г2С
      - Сталь10 / 'Сталь 10' / сталь20                 -> Сталь10 / Сталь20
    Сначала проверяется редактируемый список исключений (grade_aliases.json).
    """
    if not raw:
        return ""
    g_compact = re.sub(r"\s+", "", str(raw).strip())
    key = g_compact.upper()

    aliases = _load_grade_aliases()
    if key in aliases:
        return aliases[key]

    m = re.match(r"^СТ(\d+)", key)            # Ст3 и все её раскисления/доработки
    if m:
        return f"Ст{m.group(1)}"

    m = re.match(r"^С(\d{3})", key)           # класс прочности С### + любой суффикс
    if m:
        return f"С{m.group(1)}"

    m = re.match(r"^(\d{2}Г\d?[А-Я]+)", key)  # низколегированные 09Г2С и т.п.
    if m:
        return m.group(1)

    m = re.match(r"^СТАЛЬ(\d+)", key)         # Сталь10, Сталь20
    if m:
        return f"Сталь{m.group(1)}"

    return g_compact                          # редкая марка — оставляем как ввели


def material_code(profile_type_or_prefix: str, size: str, grade: str) -> str:
    """
    Собирает канонический код материала ПРЕФИКС-РАЗМЕР-МАРКА.
    Первым аргументом принимает либо тип профиля ('Труба профильная'),
    либо уже готовый префикс ('ТР-П').
    Возвращает '' если не хватает данных.
    """
    p = (profile_type_or_prefix or "").strip()
    prefix = PROFILE_TYPE_MAP.get(p, p)  # если передали тип — переводим; если префикс — оставляем
    size_n = normalize_size(size)
    grade_n = normalize_grade(grade)
    if not prefix or not size_n or not grade_n:
        return ""
    return f"{prefix}-{size_n}-{grade_n}"


def material_name(profile_type: str, size: str, grade: str) -> str:
    """Человекочитаемое наименование с нормализованными размером и маркой."""
    p = (profile_type or "").strip()
    size_n = normalize_size(size)
    grade_n = normalize_grade(grade)
    if not p or not size_n or not grade_n:
        return ""
    return f"{p} {size_n} {grade_n}"


def canonical_code_key(code: str) -> str:
    """
    Приводит ГОТОВЫЙ код материала к каноническому виду для устойчивого
    сопоставления (без учёта регистра размера и написания марки).

    Нужно, чтобы старые записи каталога ('ТР-П-60Х40Х2-С255', заглавный размер)
    сопоставлялись с деталями нового формата ('ТР-П-60х40х2-С255'). Разбирает
    код на префикс-размер-марку и пересобирает по тем же правилам.
    Если разобрать не удалось — возвращает исходный код без пробелов.
    """
    if not code:
        return ""
    raw = str(code).strip()
    parts = raw.split("-")
    if len(parts) < 3:
        return raw
    # марка — последний сегмент, размер — предпоследний, префикс — всё до него
    grade = parts[-1]
    size = parts[-2]
    prefix = "-".join(parts[:-2])
    size_n = normalize_size(size)
    grade_n = normalize_grade(grade)
    return f"{prefix}-{size_n}-{grade_n}"
