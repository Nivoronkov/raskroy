from typing import List, Tuple, Dict

from core.models import Material, Part, CalculationSettings


def validate_materials(materials: List[Material]) -> Tuple[List[str], List[str]]:
    """
    Проверка списка материалов.
    Возвращает кортеж: (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not materials:
        errors.append("Не задан ни один материал.")
        return errors, warnings

    seen_codes = set()

    for index, material in enumerate(materials, start=1):
        row_prefix = f"Материал #{index}"

        if not material.code.strip():
            errors.append(f"{row_prefix}: не указан код материала.")

        if not material.name.strip():
            errors.append(f"{row_prefix}: не указано наименование материала.")

        if not material.profile_type.strip():
            errors.append(f"{row_prefix}: не указан тип профиля.")

        if not material.size.strip():
            errors.append(f"{row_prefix}: не указан размер профиля.")

        if material.stock_length_mm <= 0:
            errors.append(f"{row_prefix}: длина хлыста должна быть больше 0.")

        if material.mass_per_meter < 0:
            errors.append(f"{row_prefix}: масса 1 м не может быть отрицательной.")

        if material.price_per_meter < 0:
            errors.append(f"{row_prefix}: цена за 1 м не может быть отрицательной.")

        if material.available_count < 0:
            errors.append(f"{row_prefix}: количество хлыстов не может быть отрицательным.")

        if material.code in seen_codes:
            errors.append(f"{row_prefix}: дублирующийся код материала '{material.code}'.")

        seen_codes.add(material.code)

    return errors, warnings


def validate_parts(
    parts: List[Part],
    materials: List[Material],
) -> Tuple[List[str], List[str]]:
    """
    Проверка списка деталей.
    Возвращает кортеж: (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not parts:
        errors.append("Не задана ни одна деталь.")
        return errors, warnings

    materials_by_code: Dict[str, Material] = {m.code: m for m in materials}

    for index, part in enumerate(parts, start=1):
        row_prefix = f"Деталь #{index}"

        if not part.name.strip():
            warnings.append(f"{row_prefix}: не указано наименование детали.")

        if not part.material_code.strip():
            errors.append(f"{row_prefix}: не указан код материала.")

        if part.length_mm <= 0:
            errors.append(f"{row_prefix}: длина детали должна быть больше 0.")

        if part.quantity <= 0:
            errors.append(f"{row_prefix}: количество должно быть больше 0.")

        material = materials_by_code.get(part.material_code)
        if material is None:
            errors.append(
                f"{row_prefix}: материал с кодом '{part.material_code}' не найден."
            )
            continue

        if part.length_mm > material.stock_length_mm:
            errors.append(
                f"{row_prefix}: длина детали ({part.length_mm} мм) "
                f"больше длины хлыста ({material.stock_length_mm} мм) "
                f"для материала '{material.code}'."
            )

        if not part.designation.strip():
            warnings.append(f"{row_prefix}: не указано обозначение детали.")

    return errors, warnings


def validate_settings(settings: CalculationSettings) -> Tuple[List[str], List[str]]:
    """
    Проверка параметров расчета.
    Возвращает кортеж: (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if settings.cut_width_mm < 0:
        errors.append("Ширина реза не может быть отрицательной.")

    if settings.trim_allowance_mm < 0:
        errors.append("Припуск не может быть отрицательным.")

    if settings.min_useful_leftover_mm < 0:
        errors.append("Минимальный полезный остаток не может быть отрицательным.")

    allowed_modes = {"min_waste", "min_bars", "balanced", "max_leftovers"}
    if settings.optimization_mode not in allowed_modes:
        errors.append(
            "Недопустимый режим оптимизации. "
            f"Допустимые значения: {', '.join(sorted(allowed_modes))}."
        )

    return errors, warnings


def validate_all(
    materials: List[Material],
    parts: List[Part],
    settings: CalculationSettings,
) -> Tuple[List[str], List[str]]:
    """
    Общая проверка всех входных данных.
    Возвращает кортеж: (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    material_errors, material_warnings = validate_materials(materials)
    errors.extend(material_errors)
    warnings.extend(material_warnings)

    # Детали проверяем только если материалы хотя бы частично валидны по списку
    part_errors, part_warnings = validate_parts(parts, materials)
    errors.extend(part_errors)
    warnings.extend(part_warnings)

    settings_errors, settings_warnings = validate_settings(settings)
    errors.extend(settings_errors)
    warnings.extend(settings_warnings)

    return errors, warnings
