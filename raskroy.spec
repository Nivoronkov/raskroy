# -*- mode: python ; coding: utf-8 -*-
"""
Рецепт сборки калькулятора раскроя в .exe (PyInstaller, формат onedir — папка).

Сборка:
    pyinstaller raskroy.spec

Результат: dist\РаскройЗИТ\  — папка с РаскройЗИТ.exe и всеми файлами.
Эту папку целиком отдаём в отдел.

Что учтено:
  - точка входа: smart_cut_app/main.py
  - конвертер sp_to_cutlist.py кладётся рядом с .exe (он подтягивается
    динамически при загрузке спецификации)
  - иконка app.ico (положи рядом со spec; если нет — убери параметр icon=)
  - скрытые импорты pandas/openpyxl/xlrd (PyInstaller не всегда видит их сам)
  - справочники и app_config.json НЕ вшиваются — они создаются/редактируются
    рядом с .exe во время работы
"""
import os

block_cipher = None

# Папки проекта
ROOT = os.path.abspath(".")
APP = os.path.join(ROOT, "smart_cut_app")

# Файлы-данные, которые кладём рядом с .exe.
# Конвертер лежит в корне проекта и нужен для загрузки спецификаций.
datas = [
    (os.path.join(ROOT, "sp_to_cutlist.py"), "."),
]

# Скрытые импорты — модули, которые подтягиваются не напрямую.
hiddenimports = [
    "pandas",
    "openpyxl",
    "openpyxl.cell._writer",
    "xlrd",
]

a = Analysis(
    [os.path.join(APP, "main.py")],
    pathex=[APP, ROOT],          # чтобы находились core/data/ui и sp_to_cutlist
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="РаскройЗИТ",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                       # окно без чёрной консоли
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="app.ico" if os.path.exists(os.path.join(ROOT, "app.ico")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="РаскройЗИТ",                   # имя папки в dist\
)
