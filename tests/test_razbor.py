"""
Тест разбора спецификации (защита от регрессий).

Зачем: когда дорабатываешь конвертер под новые спецификации (исполнения,
позиции, новые профили), этот тест проверяет, что разбор уже известной
спецификации "Каркас" НЕ сломался.

Запуск (из папки C:\\raskroy, при активированной venv):
    pytest

Если после твоей правки тест "покраснел" — значит правка сломала разбор,
который раньше работал. Смотри, что именно разошлось с эталоном.
"""
import os
import sys
import pandas as pd
import pytest

# подключаем конвертер из родительской папки
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from sp_to_cutlist import main as convert_sp

ETALON = os.path.join(HERE, "data", "karkas_etalon.xls")


@pytest.fixture(scope="module")
def sheets(tmp_path_factory):
    """Конвертирует эталон один раз и отдаёт листы как DataFrame."""
    out = tmp_path_factory.mktemp("out") / "karkas_вход.xlsx"
    convert_sp(ETALON, str(out))
    return {
        "Детали": pd.read_excel(out, sheet_name="Детали", dtype=str).fillna(""),
        "Материалы": pd.read_excel(out, sheet_name="Материалы", dtype=str).fillna(""),
        "Проверка": pd.read_excel(out, sheet_name="Проверка", dtype=str).fillna(""),
        "Отсечено": pd.read_excel(out, sheet_name="Отсечено", dtype=str).fillna(""),
    }


def test_число_деталей(sheets):
    # 25 строк линейного проката
    assert len(sheets["Детали"]) == 25


def test_число_материалов(sheets):
    # 5 уникальных материалов (типоразмер + марка)
    assert len(sheets["Материалы"]) == 5


def test_отсечены_листы(sheets):
    # 20 строк не для линейного раскроя (листы, пластины, крепёж, минвата)
    assert len(sheets["Отсечено"]) == 20


def test_длина_извлечена_у_всех(sheets):
    # ни у одной детали проката длина не должна быть пустой
    дет = sheets["Детали"]
    пустые = дет[дет["Длина, мм"] == ""]
    assert len(пустые) == 0, f"Длина не извлечена у строк: {пустые['Обозначение'].tolist()}"


def test_конкретная_длина_трубы(sheets):
    # поз. ...065-2750 -> труба 50х50х4, длина 2750, количество 8
    дет = sheets["Детали"]
    строка = дет[дет["Обозначение"].str.contains("065-2750", na=False)]
    assert len(строка) == 1
    assert строка.iloc[0]["Длина, мм"] == "2750"
    assert строка.iloc[0]["Количество"] == "8"


def test_труба_09Г2С_отдельный_материал(sheets):
    # труба 100х60х5 из 09Г2С НЕ должна слиться с трубами из Ст3
    мат = sheets["Материалы"]
    assert any("09Г2С" in c for c in мат["Код материала"])


def test_конфликт_швеллера_пойман(sheets):
    # поз. 18: наимен. "Швеллер 8П" против материала "10П" -> на лист Проверка
    пров = sheets["Проверка"]
    assert any("746211.010-510" in o for o in пров["Обозначение"])
