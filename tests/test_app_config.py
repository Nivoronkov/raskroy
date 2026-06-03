"""Тесты настраиваемого пути к справочнику и атомарной записи."""
import os, sys, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "smart_cut_app"))

import pytest
import core.app_config as cfg
from core.models import MaterialCatalogItem
from data.materials_catalog_repository import save_materials_catalog, load_materials_catalog


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    # перенаправляем конфиг и умолчания во временную папку, чтобы не трогать реальные
    monkeypatch.setattr(cfg, "_CONFIG_FILE", str(tmp_path / "app_config.json"))
    monkeypatch.setattr(cfg, "_DEFAULT_CATALOG", str(tmp_path / "materials_catalog.json"))
    monkeypatch.setattr(cfg, "_DEFAULT_LEFTOVERS", str(tmp_path / "leftovers_db.json"))
    yield tmp_path


def test_путь_по_умолчанию(temp_config):
    assert cfg.get_catalog_path() == cfg.get_default_catalog_path()


def test_задать_и_сбросить_путь(temp_config):
    net = str(temp_config / "net" / "materials_catalog.json")
    cfg.set_catalog_path(net)
    assert cfg.get_catalog_path() == net
    cfg.set_catalog_path(None)
    assert cfg.get_catalog_path() == cfg.get_default_catalog_path()


def test_конфиг_не_падает_на_битом(temp_config):
    with open(cfg._CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("{битый")
    # повреждённый конфиг -> работаем на умолчаниях, без исключения
    assert cfg.get_catalog_path() == cfg.get_default_catalog_path()


def test_сохранение_по_настроенному_пути(temp_config):
    net = str(temp_config / "sklad" / "materials_catalog.json")
    cfg.set_catalog_path(net)
    item = MaterialCatalogItem(
        id="MATCAT-0001", material_code="ТР-П-50х50х4-Ст3", name="Труба 50х50х4 Ст3",
        profile_type="Труба профильная", profile_code="ТР-П", size="50х50х4",
        steel_grade="Ст3", stock_length_mm=6000, available_stock_bars=5, is_active=True)
    save_materials_catalog([item])
    assert os.path.exists(net)
    loaded = load_materials_catalog()
    assert len(loaded) == 1 and loaded[0].material_code == "ТР-П-50х50х4-Ст3"


def test_атомарная_запись_без_временных(temp_config):
    net_dir = temp_config / "sklad2"
    net = str(net_dir / "materials_catalog.json")
    cfg.set_catalog_path(net)
    save_materials_catalog([])
    # после записи не остаётся .tmp файлов
    tmps = [f for f in os.listdir(net_dir) if f.endswith(".tmp")]
    assert tmps == []
