import json
from pathlib import Path
from typing import Any, Dict, List

from core.models import CalculationSettings, Material, Part


class ProjectRepositoryError(Exception):
    pass


def _material_to_dict(material: Material) -> Dict[str, Any]:
    return {
        "id": material.id,
        "code": material.code,
        "name": material.name,
        "profile_type": material.profile_type,
        "size": material.size,
        "grade": material.grade,
        "stock_length_mm": material.stock_length_mm,
        "mass_per_meter": material.mass_per_meter,
        "price_per_meter": material.price_per_meter,
        "available_count": material.available_count,
        "note": material.note,
    }


def _part_to_dict(part: Part) -> Dict[str, Any]:
    return {
        "id": part.id,
        "designation": part.designation,
        "name": part.name,
        "material_code": part.material_code,
        "length_mm": part.length_mm,
        "quantity": part.quantity,
        "assembly": part.assembly,
        "note": part.note,
    }


def _settings_to_dict(settings: CalculationSettings) -> Dict[str, Any]:
    return {
        "cut_width_mm": settings.cut_width_mm,
        "trim_allowance_mm": settings.trim_allowance_mm,
        "min_useful_leftover_mm": settings.min_useful_leftover_mm,
        "optimization_mode": settings.optimization_mode,
        "use_leftovers": settings.use_leftovers,
    }


def _material_from_dict(data: Dict[str, Any]) -> Material:
    return Material(
        id=data.get("id", ""),
        code=data.get("code", ""),
        name=data.get("name", ""),
        profile_type=data.get("profile_type", ""),
        size=data.get("size", ""),
        grade=data.get("grade", ""),
        stock_length_mm=int(data.get("stock_length_mm", 0)),
        mass_per_meter=float(data.get("mass_per_meter", 0.0)),
        price_per_meter=float(data.get("price_per_meter", 0.0)),
        available_count=int(data.get("available_count", 0)),
        note=data.get("note", ""),
    )


def _part_from_dict(data: Dict[str, Any]) -> Part:
    return Part(
        id=data.get("id", ""),
        designation=data.get("designation", ""),
        name=data.get("name", ""),
        material_code=data.get("material_code", ""),
        length_mm=int(data.get("length_mm", 0)),
        quantity=int(data.get("quantity", 0)),
        assembly=data.get("assembly", ""),
        note=data.get("note", ""),
    )


def _settings_from_dict(data: Dict[str, Any]) -> CalculationSettings:
    return CalculationSettings(
        cut_width_mm=int(data.get("cut_width_mm", 0)),
        trim_allowance_mm=int(data.get("trim_allowance_mm", 0)),
        min_useful_leftover_mm=int(data.get("min_useful_leftover_mm", 0)),
        optimization_mode=data.get("optimization_mode", "min_waste"),
        use_leftovers=bool(data.get("use_leftovers", False)),
    )


def save_project(
    file_path: str,
    materials: List[Material],
    parts: List[Part],
    settings: CalculationSettings,
) -> None:
    project_data = {
        "materials": [_material_to_dict(item) for item in materials],
        "parts": [_part_to_dict(item) for item in parts],
        "settings": _settings_to_dict(settings),
    }

    try:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(project_data, file, ensure_ascii=False, indent=2)
    except OSError as exc:
        raise ProjectRepositoryError(f"Не удалось сохранить проект:\n{exc}") from exc


def load_project(file_path: str) -> Dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        raise ProjectRepositoryError(f"Файл проекта не найден:\n{file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except OSError as exc:
        raise ProjectRepositoryError(f"Не удалось открыть проект:\n{exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProjectRepositoryError(f"Файл проекта поврежден или имеет неверный формат:\n{exc}") from exc

    materials = [_material_from_dict(item) for item in raw_data.get("materials", [])]
    parts = [_part_from_dict(item) for item in raw_data.get("parts", [])]
    settings = _settings_from_dict(raw_data.get("settings", {}))

    return {
        "materials": materials,
        "parts": parts,
        "settings": settings,
    }
