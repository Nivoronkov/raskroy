"""Тесты единой нормализации обозначений материала (размер, марка, код)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "smart_cut_app"))

from core.normalization import normalize_size, normalize_grade, material_code


# ---------- размер ----------
def test_размер_регистр_и_латиница():
    assert normalize_size("100Х100Х5") == "100х100х5"
    assert normalize_size("100x100x5") == "100х100х5"
    assert normalize_size("100X100X5") == "100х100х5"


def test_размер_пробелы_и_звёздочка():
    assert normalize_size(" 100 х 100 х 5 ") == "100х100х5"
    assert normalize_size("100*100*5") == "100х100х5"


def test_размер_серия_швеллера_заглавная():
    # номер профиля с буквой серии остаётся заглавным
    assert normalize_size("18п") == "18П"
    assert normalize_size("18У") == "18У"
    assert normalize_size("18u") == "18П"
    assert normalize_size("8П") == "8П"


# ---------- марка ----------
def test_марка_ст3_все_раскисления():
    for g in ("Ст3", "ст3", "СТ3", "Ст3пс", "Ст3сп", "Ст3кп", "Ст3пс3-св", "Ст3Гпс"):
        assert normalize_grade(g) == "Ст3", g


def test_марка_класс_прочности():
    assert normalize_grade("С255") == "С255"
    assert normalize_grade("С255-4") == "С255"
    assert normalize_grade("С255К") == "С255"
    assert normalize_grade("С345-3") == "С345"


def test_марка_низколегированная():
    assert normalize_grade("09Г2С") == "09Г2С"
    assert normalize_grade("09Г2С-12") == "09Г2С"


def test_марка_сталь_n():
    assert normalize_grade("Сталь10") == "Сталь10"
    assert normalize_grade("Сталь 10") == "Сталь10"
    assert normalize_grade("сталь20") == "Сталь20"


# ---------- код целиком ----------
def test_код_одинаков_для_разных_написаний():
    a = material_code("Труба профильная", "100Х100Х5", "С345")
    b = material_code("Труба профильная", "100x100x5", "с345")
    c = material_code("Труба профильная", " 100 х 100 х 5 ", "С345-4")
    assert a == b == c == "ТР-П-100х100х5-С345"


def test_код_принимает_и_префикс_и_тип():
    assert material_code("ТР-П", "50х50х4", "Ст3") == "ТР-П-50х50х4-Ст3"
    assert material_code("Труба профильная", "50х50х4", "Ст3") == "ТР-П-50х50х4-Ст3"


def test_код_пустой_при_нехватке_данных():
    assert material_code("Труба профильная", "", "Ст3") == ""
    assert material_code("Труба профильная", "50х50х4", "") == ""
