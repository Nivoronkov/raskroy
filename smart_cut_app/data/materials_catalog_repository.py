import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models import MaterialCatalogItem
from core.normalization import (
    PROFILE_TYPE_MAP,
    material_code as _build_material_code,
    material_name as _build_material_name,
    normalize_grade,
    normalize_size,
)


class MaterialsCatalogError(Exception):
    pass


DEFAULT_CATALOG_FILE = "materials_catalog.json"


def generate_material_code(profile_type: str, size: str, steel_grade: str) -> str:
    """Канонический код материала. Делегирует единому модулю нормализации."""
    return _build_material_code(profile_type, size, steel_grade)


def generate_material_name(profile_type: str, size: str, steel_grade: str) -> str:
    """Наименование материала с нормализованными размером и маркой."""
    return _build_material_name(profile_type, size, steel_grade)


def _item_to_dict(item: MaterialCatalogItem) -> Dict[str, Any]:
    return {
        "id": item.id,
        "material_code": item.material_code,
        "name": item.name,
        "profile_type": item.profile_type,
        "profile_code": item.profile_code,
        "size": item.size,
        "steel_grade": item.steel_grade,
        "stock_length_mm": item.stock_length_mm,
        "mass_per_meter": item.mass_per_meter,
        "price_per_meter": item.price_per_meter,
        "note": item.note,
        "is_active": item.is_active,
        "external_code": item.external_code,
        "available_stock_bars": item.available_stock_bars,
    }


def _item_from_dict(data: Dict[str, Any]) -> MaterialCatalogItem:
    return MaterialCatalogItem(
        id=data.get("id", ""),
        material_code=data.get("material_code", ""),
        name=data.get("name", ""),
        profile_type=data.get("profile_type", ""),
        profile_code=data.get("profile_code", ""),
        size=data.get("size", ""),
        steel_grade=data.get("steel_grade", ""),
        stock_length_mm=int(data.get("stock_length_mm", 0)),
        mass_per_meter=float(data.get("mass_per_meter", 0.0)),
        price_per_meter=float(data.get("price_per_meter", 0.0)),
        note=data.get("note", ""),
        is_active=bool(data.get("is_active", True)),
        external_code=data.get("external_code", ""),
        available_stock_bars=int(data.get("available_stock_bars", 0)),
    )


def load_materials_catalog(
    file_path: str = DEFAULT_CATALOG_FILE,
) -> List[MaterialCatalogItem]:
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except OSError as exc:
        raise MaterialsCatalogError(f"Не удалось открыть справочник материалов:\n{exc}") from exc
    except json.JSONDecodeError as exc:
        raise MaterialsCatalogError(
            f"Файл справочника материалов поврежден или имеет неверный формат:\n{exc}"
        ) from exc

    return [_item_from_dict(item) for item in raw_data]


def save_materials_catalog(
    items: List[MaterialCatalogItem],
    file_path: str = DEFAULT_CATALOG_FILE,
) -> None:
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(
                [_item_to_dict(item) for item in items],
                file,
                ensure_ascii=False,
                indent=2,
            )
    except OSError as exc:
        raise MaterialsCatalogError(f"Не удалось сохранить справочник материалов:\n{exc}") from exc


def get_next_catalog_item_id(
    file_path: str = DEFAULT_CATALOG_FILE,
) -> str:
    items = load_materials_catalog(file_path)
    numbers = []

    for item in items:
        if item.id.startswith("MATCAT-"):
            tail = item.id.replace("MATCAT-", "")
            if tail.isdigit():
                numbers.append(int(tail))

    next_number = max(numbers, default=0) + 1
    return f"MATCAT-{next_number:04d}"


def find_duplicate_catalog_item(
    profile_type: str,
    size: str,
    steel_grade: str,
    stock_length_mm: int,
    file_path: str = DEFAULT_CATALOG_FILE,
    exclude_id: str = "",
) -> Optional[MaterialCatalogItem]:
    """
    Ищет в справочнике материал, совпадающий по типу + НОРМАЛИЗОВАННОМУ размеру
    + КАНОНИЧЕСКОЙ марке + длине хлыста. За счёт нормализации '100Х100Х5' и
    '100х100х5', а также 'Ст3пс3-св' и 'Ст3' опознаются как один материал.
    """
    normalized_size = normalize_size(size)
    normalized_grade = normalize_grade(steel_grade)

    for item in load_materials_catalog(file_path):
        if exclude_id and item.id == exclude_id:
            continue

        if (
            item.profile_type == profile_type
            and normalize_size(item.size) == normalized_size
            and normalize_grade(item.steel_grade) == normalized_grade
            and item.stock_length_mm == stock_length_mm
        ):
            return item

    return None


def find_catalog_item_by_code(
    material_code: str,
    file_path: str = DEFAULT_CATALOG_FILE,
) -> Optional[MaterialCatalogItem]:
    """Поиск материала по точному коду (коды уже канонические)."""
    code = (material_code or "").strip()
    if not code:
        return None
    for item in load_materials_catalog(file_path):
        if item.material_code == code:
            return item
    return None


def add_catalog_item(
    item: MaterialCatalogItem,
    file_path: str = DEFAULT_CATALOG_FILE,
) -> None:
    items = load_materials_catalog(file_path)
    items.append(item)
    save_materials_catalog(items, file_path)


def update_catalog_item(
    updated_item: MaterialCatalogItem,
    file_path: str = DEFAULT_CATALOG_FILE,
) -> None:
    items = load_materials_catalog(file_path)

    found = False
    for index, item in enumerate(items):
        if item.id == updated_item.id:
            items[index] = updated_item
            found = True
            break

    if not found:
        raise MaterialsCatalogError(
            f"Материал справочника с ID '{updated_item.id}' не найден."
        )

    save_materials_catalog(items, file_path)


def delete_catalog_items_by_ids(
    item_ids: List[str],
    file_path: str = DEFAULT_CATALOG_FILE,
) -> int:
    if not item_ids:
        return 0

    items = load_materials_catalog(file_path)
    filtered = [item for item in items if item.id not in item_ids]
    deleted_count = len(items) - len(filtered)

    save_materials_catalog(filtered, file_path)
    return deleted_count
