from data.materials_catalog_repository import (
    generate_material_code,
    generate_material_name,
    normalize_size,
)

print("Проверка генерации кода:")
print(generate_material_code("Труба профильная", "40х40х2", "09Г2С"))
print(generate_material_code("Швеллер", "22П", "Ст3"))
print(generate_material_code("Уголок", "50х50х5", "Ст3"))
print(generate_material_code("Труба круглая", "57х3", "Ст3"))

print("\nПроверка генерации наименования:")
print(generate_material_name("Труба профильная", "40х40х2", "09Г2С"))

print("\nПроверка нормализации размера:")
print(normalize_size("40x40x2"))
print(normalize_size("40*40*2"))
print(normalize_size("40 х 40 х 2"))
