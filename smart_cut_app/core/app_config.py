r"""
Конфигурация приложения (app_config.json).

Хранит настройки, не относящиеся к конкретному расчёту, — прежде всего ПУТЬ К
СПРАВОЧНИКУ материалов и остатков. Это позволяет вести общий справочник в
сетевой папке (\\сервер\папка\... или Z:\...), к которому обращаются несколько
рабочих мест.

Файл конфига лежит рядом с программой (app_config.json). Если его нет —
используются пути по умолчанию (справочники рядом с программой), и при первом
сохранении конфиг создаётся.

Пример app_config.json:
{
  "catalog_path": "\\\\server\\sklad\\materials_catalog.json",
  "leftovers_path": "\\\\server\\sklad\\leftovers_db.json"
}
"""
import json
import os
import sys
from typing import Optional


def _app_dir() -> str:
    """
    Папка приложения — где лежат справочники и конфиг.
    - В обычном запуске (python): папка пакета smart_cut_app (на уровень выше core/).
    - В собранном .exe (PyInstaller): папка, где лежит сам .exe.
    Так данные всегда оказываются рядом с программой и доступны для правки.
    """
    if getattr(sys, "frozen", False):
        # запущено как собранный .exe — данные рядом с исполняемым файлом
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Папка программы (где конфиг и справочники по умолчанию)
APP_DIR = _app_dir()

_CONFIG_FILE = os.path.join(APP_DIR, "app_config.json")

# Значения по умолчанию — справочники рядом с программой
_DEFAULT_CATALOG = os.path.join(APP_DIR, "materials_catalog.json")
_DEFAULT_LEFTOVERS = os.path.join(APP_DIR, "leftovers_db.json")


def _load_config() -> dict:
    if not os.path.exists(_CONFIG_FILE):
        return {}
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        # Повреждённый конфиг не должен ронять программу — работаем на умолчаниях.
        return {}


def _save_config(config: dict) -> None:
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_catalog_path() -> str:
    """Путь к справочнику материалов (из конфига или по умолчанию)."""
    return _load_config().get("catalog_path") or _DEFAULT_CATALOG


def get_leftovers_path() -> str:
    """Путь к базе остатков (из конфига или по умолчанию)."""
    return _load_config().get("leftovers_path") or _DEFAULT_LEFTOVERS


def set_catalog_path(path: Optional[str]) -> None:
    """
    Задаёт путь к справочнику материалов. Пустое значение / None — сброс на
    путь по умолчанию (рядом с программой).
    """
    config = _load_config()
    if path:
        config["catalog_path"] = path
    else:
        config.pop("catalog_path", None)
    _save_config(config)


def set_leftovers_path(path: Optional[str]) -> None:
    """Задаёт путь к базе остатков. Пустое / None — сброс на путь по умолчанию."""
    config = _load_config()
    if path:
        config["leftovers_path"] = path
    else:
        config.pop("leftovers_path", None)
    _save_config(config)


def get_default_catalog_path() -> str:
    return _DEFAULT_CATALOG


def get_default_leftovers_path() -> str:
    return _DEFAULT_LEFTOVERS


def get_icon_path() -> Optional[str]:
    """
    Путь к иконке приложения (app.ico рядом с программой / .exe).
    Возвращает None, если иконки нет — тогда используется стандартная.
    """
    for name in ("app.ico", "app_ico.ico"):
        candidate = os.path.join(APP_DIR, name)
        if os.path.exists(candidate):
            return candidate
    return None
