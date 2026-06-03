import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from core.app_config import get_leftovers_path
from core.models import Leftover


class LeftoversRepositoryError(Exception):
    pass


# Путь к базе остатков берётся из конфига (может быть общим в сетевой папке).
# Сентинел: если file_path не передан, путь разрешается из конфига при вызове.
_USE_CONFIG = None


def _resolve(file_path):
    return get_leftovers_path() if file_path is _USE_CONFIG else file_path


def _leftover_to_dict(leftover: Leftover) -> Dict[str, Any]:
    return {
        "id": leftover.id,
        "material_code": leftover.material_code,
        "material_name": leftover.material_name,
        "length_mm": leftover.length_mm,
        "stock_length_mm": leftover.stock_length_mm,
        "source_pattern_id": leftover.source_pattern_id,
        "note": leftover.note,
    }


def _leftover_from_dict(data: Dict[str, Any]) -> Leftover:
    return Leftover(
        id=data.get("id", ""),
        material_code=data.get("material_code", ""),
        material_name=data.get("material_name", ""),
        length_mm=int(data.get("length_mm", 0)),
        stock_length_mm=int(data.get("stock_length_mm", 0)),
        source_pattern_id=data.get("source_pattern_id", ""),
        note=data.get("note", ""),
    )


def load_leftovers(file_path=_USE_CONFIG) -> List[Leftover]:
    path = Path(_resolve(file_path))
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except OSError as exc:
        raise LeftoversRepositoryError(f"Не удалось открыть базу остатков:\n{exc}") from exc
    except json.JSONDecodeError as exc:
        raise LeftoversRepositoryError(
            f"Файл базы остатков поврежден или имеет неверный формат:\n{exc}"
        ) from exc

    return [_leftover_from_dict(item) for item in raw_data]


def save_leftovers(
    leftovers: List[Leftover],
    file_path=_USE_CONFIG,
) -> None:
    """Атомарная запись (временный файл + os.replace) — как у справочника."""
    target = _resolve(file_path)
    target_dir = os.path.dirname(os.path.abspath(target))
    try:
        os.makedirs(target_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=target_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(
                    [_leftover_to_dict(item) for item in leftovers],
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
            os.replace(tmp_path, target)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    except OSError as exc:
        raise LeftoversRepositoryError(f"Не удалось сохранить базу остатков:\n{exc}") from exc


def append_leftovers(
    new_leftovers: List[Leftover],
    file_path=_USE_CONFIG,
) -> None:
    existing = load_leftovers(file_path)
    existing.extend(new_leftovers)
    save_leftovers(existing, file_path)


def delete_leftovers_by_ids(
    leftover_ids: List[str],
    file_path=_USE_CONFIG,
) -> int:
    if not leftover_ids:
        return 0

    existing = load_leftovers(file_path)
    filtered = [item for item in existing if item.id not in leftover_ids]
    deleted_count = len(existing) - len(filtered)

    save_leftovers(filtered, file_path)
    return deleted_count


def apply_leftovers_result(
    consumed_leftover_ids: List[str],
    new_leftovers: List[Leftover],
    file_path=_USE_CONFIG,
) -> Dict[str, int]:
    existing = load_leftovers(file_path)

    remaining = [
        item for item in existing
        if item.id not in consumed_leftover_ids
    ]
    deleted_count = len(existing) - len(remaining)

    remaining.extend(new_leftovers)
    added_count = len(new_leftovers)

    save_leftovers(remaining, file_path)

    return {
        "deleted": deleted_count,
        "added": added_count,
        "total": len(remaining),
    }


def add_leftover(
    leftover: Leftover,
    file_path=_USE_CONFIG,
) -> None:
    existing = load_leftovers(file_path)
    existing.append(leftover)
    save_leftovers(existing, file_path)


def update_leftover(
    updated_leftover: Leftover,
    file_path=_USE_CONFIG,
) -> None:
    existing = load_leftovers(file_path)

    found = False
    for index, item in enumerate(existing):
        if item.id == updated_leftover.id:
            existing[index] = updated_leftover
            found = True
            break

    if not found:
        raise LeftoversRepositoryError(
            f"Остаток с ID '{updated_leftover.id}' не найден."
        )

    save_leftovers(existing, file_path)