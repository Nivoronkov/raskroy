"""
Конвертер спецификации Компас (.xls выгрузка) -> Excel для калькулятора раскроя.

Блок 2 (извлечение) + Блок 3 (классификация и нормализация) из общей схемы.
Выход: книга с листами "Детали" и "Материалы" в формате smart_cut_app,
плюс лист "Проверка" с пометками для человека и лист "Отсечено" (листы/2D).
"""
import re
import sys
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# ----- карта профилей (как в калькуляторе) -----
PROFILE_MAP = {
    "Труба профильная": "ТР-П",
    "Труба круглая": "ТР-К",
    "Швеллер": "ШВ",
    "Уголок": "УГ",
    "Полоса": "ПЛ",
    "Круг": "КР",
}
STOCK_LENGTH_DEFAULT = {  # типовая длина хлыста, мм
    "ТР-П": 6000, "ТР-К": 6000, "ШВ": 11700, "УГ": 11700, "ПЛ": 6000, "КР": 6000,
}

# ----- 2D-профили, которые НЕ идут в линейный раскрой -----
SHEET_KEYWORDS = ("Лист", "Пластина", "Косынка", "Ребро", "Полоса")


def classify_profile(naim: str):
    """Определяет тип профиля и размер из наименования детали."""
    n = naim.strip()
    # Труба XXxYYxZZ (профильная/прямоугольная) или XXxYY (квадрат)
    m = re.search(r"Труба\s+([\dхx*]+)", n, re.I)
    if m:
        size = normalize_size(m.group(1))
        # квадрат 50х50х4 / прямоуг 60х40х2 -> профильная
        return "Труба профильная", size
    m = re.search(r"Швеллер\s*№?\s*([\dПпUu]+)", n, re.I)
    if m:
        return "Швеллер", m.group(1).upper().replace("U", "П")
    m = re.search(r"Уголок\s+([\dхx*]+)", n, re.I)
    if m:
        return "Уголок", normalize_size(m.group(1))
    return None, None


def normalize_size(s: str) -> str:
    return s.strip().upper().replace("X", "х").replace("*", "х").replace(" ", "")


def extract_length(obozn: str):
    """Длина детали из суффикса обозначения: ...065-2750 -> 2750."""
    m = re.search(r"-(\d+)(?:_д)?$", str(obozn).strip())
    return int(m.group(1)) if m else None


def extract_grade(obozn_mat: str, primech: str):
    """
    Марка стали. Приоритет: явная марка в обозначении материала ($$...;МАРКА...$$),
    затем колонка примечания (С255/С345), затем 'Сталь 10' и т.п.
    """
    t = str(obozn_mat)
    # внутри $$...$$ марка обычно после ';'
    m = re.search(r";\s*([0-9]{0,2}[А-ЯA-Z][\w\-]+)\s+ГОСТ", t)
    if m:
        return m.group(1).strip()
    # 'Сталь 10 ГОСТ...' без $$
    m = re.search(r"Сталь\s+(\d+\w*)", t)
    if m:
        return f"Сталь{m.group(1)}"
    return ""


def main(src_xls: str, out_xlsx: str):
    df = pd.read_excel(src_xls, sheet_name=0, header=None, dtype=str)
    df.columns = ["Формат", "Зона", "Позиция", "Обозначение", "Наименование",
                  "Количество", "Примечание", "Масса", "БЦО", "Обозн_СТ",
                  "Вид", "IDФГ", "IDPart", "ОКП", "IDмат", "ОбознМат"][:df.shape[1]]

    rows = df[df["Позиция"].notna() & df["Позиция"].astype(str).str.match(r"^\d+$", na=False)]

    parts = []        # для листа "Детали"
    materials = {}     # code -> dict (для листа "Материалы")
    checks = []        # для листа "Проверка"
    cut_off = []       # отсечённые листы/2D

    for _, r in rows.iterrows():
        naim = str(r["Наименование"]).strip()
        obozn = str(r["Обозначение"]).strip()
        qty = int(float(str(r["Количество"]).replace(",", "."))) if str(r["Количество"]).strip() else 0
        pos = str(r["Позиция"]).strip()

        # --- отсечь 2D (листы/пластины) ---
        if any(k in naim for k in SHEET_KEYWORDS) and "Труба" not in naim:
            cut_off.append([pos, obozn, naim, qty, "листовой/2D — линейный раскрой неприменим"])
            continue

        profile_type, size = classify_profile(naim)
        length = extract_length(obozn)
        grade = extract_grade(r["ОбознМат"], r["Примечание"])

        # --- проверки для человека ---
        warn = []
        if profile_type is None:
            cut_off.append([pos, obozn, naim, qty, "не распознан профиль — проверить вручную"])
            continue
        if length is None:
            warn.append("длина не извлечена из обозначения")
        if not grade:
            warn.append("марка стали не определена — заполнить вручную")

        # ловушка: наименование швеллера расходится с обозначением материала
        if profile_type == "Швеллер":
            m_mat = re.search(r"d?(\d+П)", str(r["ОбознМат"]))
            if m_mat and size and m_mat.group(1) != size:
                warn.append(f"конфликт: наимен.='{size}', материал='{m_mat.group(1)}'")
                size = m_mat.group(1)  # доверяем обозначению материала

        prefix = PROFILE_MAP.get(profile_type, "")
        code = f"{prefix}-{size}-{grade.upper()}" if (prefix and size and grade) else ""

        if warn:
            checks.append([pos, obozn, naim, size, grade, length, qty, "; ".join(warn)])

        parts.append({
            "Обозначение": obozn, "Наименование детали": naim,
            "Код материала": code, "Длина, мм": length or "", "Количество": qty,
            "Узел": "", "Примечание": "; ".join(warn),
        })

        if code and code not in materials:
            materials[code] = {
                "Код материала": code,
                "Наименование": f"{profile_type} {size} {grade}",
                "Тип профиля": profile_type, "Размер": size, "Марка": grade,
                "Длина хлыста, мм": STOCK_LENGTH_DEFAULT.get(prefix, 6000),
                "Кол-во хлыстов": 0, "Примечание": "",
            }

    write_workbook(out_xlsx, parts, list(materials.values()), checks, cut_off)
    print(f"Деталей (линейный прокат): {len(parts)}")
    print(f"Уникальных материалов: {len(materials)}")
    print(f"Строк с пометками для проверки: {len(checks)}")
    print(f"Отсечено (листы/2D/непонятное): {len(cut_off)}")


def write_workbook(path, parts, materials, checks, cut_off):
    wb = Workbook()
    H = Font(bold=True, color="FFFFFF", name="Arial")
    HF = PatternFill("solid", fgColor="1F4E78")
    WARN = PatternFill("solid", fgColor="FFF2CC")
    thin = Side(style="thin", color="BBBBBB")
    BORD = Border(thin, thin, thin, thin)

    def style_header(ws, ncol):
        for c in range(1, ncol + 1):
            cell = ws.cell(row=1, column=c)
            cell.font = H; cell.fill = HF; cell.border = BORD
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # --- Детали ---
    ws = wb.active; ws.title = "Детали"
    cols = ["Обозначение", "Наименование детали", "Код материала", "Длина, мм", "Количество", "Узел", "Примечание"]
    ws.append(cols); style_header(ws, len(cols))
    for p in parts:
        ws.append([p[c] for c in cols])
        if p["Примечание"]:
            for c in range(1, len(cols) + 1):
                ws.cell(row=ws.max_row, column=c).fill = WARN
    widths = [24, 26, 26, 11, 12, 10, 38]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    # --- Материалы ---
    ws2 = wb.create_sheet("Материалы")
    cols2 = ["Код материала", "Наименование", "Тип профиля", "Размер", "Марка", "Длина хлыста, мм", "Кол-во хлыстов", "Примечание"]
    ws2.append(cols2); style_header(ws2, len(cols2))
    for m in materials:
        ws2.append([m.get(c, "") for c in cols2])
    for i, w in enumerate([26, 30, 18, 12, 12, 16, 14, 20], 1):
        ws2.column_dimensions[chr(64 + i)].width = w

    # --- Проверка ---
    ws3 = wb.create_sheet("Проверка")
    cols3 = ["Позиция", "Обозначение", "Наименование", "Размер", "Марка", "Длина, мм", "Кол-во", "Что проверить"]
    ws3.append(cols3); style_header(ws3, len(cols3))
    for row in checks:
        ws3.append(row)
        for c in range(1, len(cols3) + 1):
            ws3.cell(row=ws3.max_row, column=c).fill = WARN
    for i, w in enumerate([10, 24, 22, 12, 12, 11, 9, 44], 1):
        ws3.column_dimensions[chr(64 + i)].width = w

    # --- Отсечено ---
    ws4 = wb.create_sheet("Отсечено")
    cols4 = ["Позиция", "Обозначение", "Наименование", "Кол-во", "Причина"]
    ws4.append(cols4); style_header(ws4, len(cols4))
    for row in cut_off:
        ws4.append(row)
    for i, w in enumerate([10, 26, 26, 9, 44], 1):
        ws4.column_dimensions[chr(64 + i)].width = w

    wb.save(path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
