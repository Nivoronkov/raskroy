"""
Конвертер спецификации Компас (.xls) -> Excel для калькулятора раскроя.
Версия 3:
  - автоопределение исполнений (несколько колонок "Количество") и их разворот
    в плоский список (номер исполнения -> в примечание детали);
  - протягивание базового обозначения, суффикс доработки _д/_дN;
  - марка С255/чистая/Сталь N; конфликт размера наимен. vs сортамент;
  - "умный" светофор: статус строки по заполненности + валидности кода,
    доработка отдельным флагом (не мешает зелёному).
"""
import re
import sys
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import FormulaRule

PROFILE_MAP = {
    "Труба профильная": "ТР-П", "Труба круглая": "ТР-К", "Швеллер": "ШВ",
    "Уголок": "УГ", "Полоса": "ПЛ", "Круг": "КР",
}
STOCK_LENGTH_DEFAULT = {"ТР-П": 6000, "ТР-К": 6000, "ШВ": 11700, "УГ": 11700, "ПЛ": 6000, "КР": 6000}
SHEET_KEYWORDS = ("Лист", "Пластина", "Косынка", "Ребро", "Сетка", "Скоба",
                  "Бобышка", "Гайка", "Болт", "Шайба", "Винт")


def normalize_size(s):
    return s.strip().upper().replace("X", "х").replace("*", "х").replace(" ", "")


def classify_profile(naim):
    n = naim.strip()
    m = re.search(r"Труба\s+([\dхx*]+)", n, re.I)
    if m:
        return "Труба профильная", normalize_size(m.group(1))
    m = re.search(r"Швеллер\s*№?\s*([\dПпUuУу]+)", n, re.I)
    if m:
        return "Швеллер", m.group(1).upper().replace("U", "П").replace("У", "П")
    m = re.search(r"Уголок\s+([\dхx*]+)", n, re.I)
    if m:
        return "Уголок", normalize_size(m.group(1))
    return None, None


def parse_designation(obozn, base):
    o = str(obozn).strip()
    full = re.sub(r"-[^-]*$", "", base) + o if (o.startswith("-") and base) else o
    m = re.search(r"-(\d+)(_д\d*)?$", full)
    length = int(m.group(1)) if m else None
    dorab = m.group(2) if (m and m.group(2)) else ""
    return full, length, dorab


def extract_grade(obozn_mat):
    t = str(obozn_mat).strip()
    m = re.search(r";\s*([0-9]{0,2}[А-ЯA-Z][\w\-]+)\s+ГОСТ", t)
    if m:
        return m.group(1).strip()
    m = re.search(r"^(С\d{3})\s+ГОСТ", t)
    if m:
        return m.group(1)
    m = re.search(r"Сталь\s+(\d+\w*)", t)
    if m:
        return f"Сталь{m.group(1)}"
    return ""


def grade_from_note(primech):
    """Запасной источник марки: класс прочности в примечании, напр. 'С255-4' -> 'С255'."""
    m = re.search(r"(С\d{3})", str(primech))
    return m.group(1) if m else ""


def material_size(obozn_mat):
    m = re.search(r"d?(\d+х\d+х\d+|\d+х\d+|\d+[ПУпу])", str(obozn_mat))
    return normalize_size(m.group(1)) if m else ""


def detect_layout(df):
    """Определяет колонки количества, обозначения материала/примечания, исполнения."""
    hdr = [str(df.iloc[0, c]).strip() for c in range(df.shape[1])]
    kol_cols = [c for c, h in enumerate(hdr) if h == "Количество"]
    # колонка сортамента ("Обозначение материала"), если есть
    mat_col = None
    for c, h in enumerate(hdr):
        if "материал" in h.lower():
            mat_col = c
    # колонка примечания (запасной источник марки: С255-4)
    prim_col = None
    for c, h in enumerate(hdr):
        if h.lower().startswith("примеч"):
            prim_col = c
    ispoln = {}
    if len(kol_cols) > 1:
        for i in range(1, 6):
            if i < len(df) and "исполн" in str(df.iloc[i, 4]).lower():
                for c in kol_cols:
                    v = str(df.iloc[i, c]).strip()
                    if v and v.lower() != "nan":
                        ispoln[c] = v
                break
    if not ispoln:
        ispoln = {kol_cols[0]: ""}
    return ispoln, mat_col, prim_col


def main(src_xls, out_xlsx):
    df = pd.read_excel(src_xls, sheet_name=0, header=None, dtype=str)
    ispoln, mat_col, prim_col = detect_layout(df)
    has_isp = any(v for v in ispoln.values())

    rows = df[df[2].notna() & df[2].astype(str).str.match(r"^\d+$", na=False)]

    parts, materials, checks, cut_off = [], {}, [], []
    base_desig = ""

    for _, r in rows.iterrows():
        naim = str(r[4]).strip()
        obozn_raw = str(r[3]).strip()
        pos = str(r[2]).strip()
        obozn_mat = r[mat_col] if mat_col is not None else ""
        primech = r[prim_col] if prim_col is not None else ""

        if obozn_raw and not obozn_raw.startswith("-") and obozn_raw.lower() != "nan":
            base_desig = obozn_raw

        if any(k in naim for k in SHEET_KEYWORDS) and "Труба" not in naim:
            cut_off.append([pos, obozn_raw, naim, "не линейный прокат (лист/крепёж/прочее)"])
            continue
        profile_type, size = classify_profile(naim)
        if profile_type is None:
            cut_off.append([pos, obozn_raw, naim, "не распознан профиль — проверить вручную"])
            continue

        full_desig, length, dorab = parse_designation(obozn_raw, base_desig)
        grade = extract_grade(obozn_mat) or grade_from_note(primech)

        warn = []
        if length is None:
            warn.append("длина не извлечена")
        if not grade:
            warn.append("марка не определена")
        msize = material_size(obozn_mat)
        conflict = ""
        if profile_type == "Швеллер" and msize and size and msize != size:
            conflict = f"размер: наимен.='{size}' / сортамент='{msize}'"
            size = msize
        elif profile_type == "Труба профильная" and msize and size and msize != size:
            conflict = f"размер: наимен.='{size}' / сортамент='{msize}' (возможна опечатка)"
        if conflict:
            warn.append(conflict)

        prefix = PROFILE_MAP.get(profile_type, "")
        code = f"{prefix}-{size}-{grade.upper()}" if (prefix and size and grade) else ""

        # разворот по исполнениям: одна строка на каждое исполнение с кол-вом
        for col, isp in ispoln.items():
            qv = str(r[col]).strip()
            if qv in ("", "nan", "None"):
                continue
            try:
                qty = int(float(qv.replace(",", ".")))
            except ValueError:
                continue
            note_parts = []
            if isp:
                note_parts.append(f"исп.{isp}")
            if dorab:
                note_parts.append(f"доработка{dorab}")
            note = " ".join(note_parts)

            if warn:
                checks.append([pos, full_desig, naim, isp or "-", size, grade,
                               length if length else "", qty, "; ".join(warn)])
            parts.append({
                "Обозначение": full_desig, "Наименование детали": naim, "Код материала": code,
                "Длина, мм": length if length else "", "Количество": qty,
                "Исполнение": isp, "Доработка": dorab, "Примечание": note,
                "_conflict": bool(conflict),
            })
            if code and code not in materials:
                materials[code] = {
                    "Код материала": code, "Наименование": f"{profile_type} {size} {grade}",
                    "Тип профиля": profile_type, "Размер": size, "Марка": grade,
                    "Длина хлыста, мм": STOCK_LENGTH_DEFAULT.get(prefix, 6000),
                    "Кол-во хлыстов": 0, "Примечание": "",
                }

    write_workbook(out_xlsx, parts, list(materials.values()), checks, cut_off, has_isp)
    print(f"Исполнений в файле: {len([v for v in ispoln.values() if v]) or 1}"
          f"{' (' + ', '.join(v for v in ispoln.values() if v) + ')' if has_isp else ' (без исполнений)'}")
    print(f"Деталей-строк (после разворота): {len(parts)}")
    print(f"Уникальных материалов: {len(materials)}")
    print(f"Строк с пометками: {len(checks)}")
    print(f"Отсечено: {len(cut_off)}")


def write_workbook(path, parts, materials, checks, cut_off, has_isp):
    wb = Workbook()
    H = Font(bold=True, color="FFFFFF", name="Arial")
    HF = PatternFill("solid", fgColor="1F4E78")

    def style_header(ws, names, row=1):
        for c, name in enumerate(names, 1):
            cell = ws.cell(row=row, column=c, value=name)
            cell.font = H; cell.fill = HF
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # ===== Лист Детали со светофором =====
    ws = wb.active; ws.title = "Детали"
    cols = ["Обозначение", "Наименование детали", "Код материала", "Длина, мм",
            "Количество", "Исполнение", "Доработка", "Примечание"]
    n = len(cols)
    status_col = n + 1
    sc = chr(64 + status_col)
    data_first = 4
    data_last = 4 + max(len(parts) - 1, 0)

    cnt_formula = f'=COUNTIF(${sc}{data_first}:${sc}{data_last},"⚠ заполнить")'
    ws.cell(row=1, column=1, value="НЕ ЗАПОЛНЕНО:").font = Font(bold=True, name="Arial")
    ws.cell(row=1, column=3, value=cnt_formula).font = Font(bold=True, size=12, name="Arial")
    verdict = ('=IF($C$1=0,"✓ ВСЁ ЗАПОЛНЕНО — можно считать раскрой",'
               '"✗ ЗАПОЛНИТЕ строки со статусом ⚠ (Длина и Код материала)")')
    vc = ws.cell(row=1, column=4, value=verdict)
    vc.font = Font(bold=True, size=12, name="Arial")
    ws.merge_cells(start_row=1, start_column=4, end_row=1, end_column=status_col)

    for c, name in enumerate(cols + ["Статус"], 1):
        cell = ws.cell(row=3, column=c, value=name)
        cell.font = H; cell.fill = HF
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    r = data_first
    for p in parts:
        for c, name in enumerate(cols, 1):
            ws.cell(row=r, column=c, value=p[name])
        # статус: заполнить / доработка / готова  (по заполненности кода и длины)
        st = (f'=IF(OR($C{r}="",$D{r}=""),"⚠ заполнить",'
              f'IF($G{r}<>"","● доработка","✓ готова"))')
        ws.cell(row=r, column=status_col, value=st)
        r += 1
    data_last_real = r - 1

    if parts:
        rng = f"A4:{sc}{data_last_real}"
        red = PatternFill("solid", fgColor="FFC7CE")
        peach = PatternFill("solid", fgColor="FCE4D6")
        green = PatternFill("solid", fgColor="E2EFDA")
        # красный — нужно заполнить (нет кода или длины)
        ws.conditional_formatting.add(rng, FormulaRule(formula=['OR($C4="",$D4="")'], fill=red, stopIfTrue=True))
        # персик — доработка (заполнено, но требует внимания)
        ws.conditional_formatting.add(rng, FormulaRule(formula=['$G4<>""'], fill=peach, stopIfTrue=True))
        # зелёный — всё ок
        ws.conditional_formatting.add(rng, FormulaRule(formula=['AND($C4<>"",$D4<>"")'], fill=green))

    for i, w in enumerate([26, 22, 26, 10, 11, 11, 11, 24, 13], 1):
        ws.column_dimensions[chr(64 + i)].width = w

    # ===== Материалы =====
    ws2 = wb.create_sheet("Материалы")
    cols2 = ["Код материала", "Наименование", "Тип профиля", "Размер", "Марка",
             "Длина хлыста, мм", "Кол-во хлыстов", "Примечание"]
    style_header(ws2, cols2)
    for m in materials:
        ws2.append([m.get(c, "") for c in cols2])
    for i, w in enumerate([26, 30, 18, 12, 12, 16, 14, 20], 1):
        ws2.column_dimensions[chr(64 + i)].width = w

    # ===== Проверка =====
    ws3 = wb.create_sheet("Проверка")
    cols3 = ["Позиция", "Обозначение", "Наименование", "Исп.", "Размер", "Марка",
             "Длина, мм", "Кол-во", "Что проверить"]
    style_header(ws3, cols3)
    peach = PatternFill("solid", fgColor="FCE4D6")
    warn = PatternFill("solid", fgColor="FFF2CC")
    for row in checks:
        ws3.append(row)
    for i, w in enumerate([8, 24, 20, 7, 11, 11, 10, 7, 46], 1):
        ws3.column_dimensions[chr(64 + i)].width = w

    # ===== Отсечено =====
    ws4 = wb.create_sheet("Отсечено")
    cols4 = ["Позиция", "Обозначение", "Наименование", "Причина"]
    style_header(ws4, cols4)
    for row in cut_off:
        ws4.append(row)
    for i, w in enumerate([8, 26, 26, 44], 1):
        ws4.column_dimensions[chr(64 + i)].width = w

    wb.save(path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
