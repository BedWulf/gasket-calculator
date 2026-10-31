"""Текстовая спецификация заказного листа для кладовой/закупки.

Не является технологической картой резки: учитывается геометрический зазор,
но не припуск на станке, ширина реза отдельно, крепёж и дефекты материала.
Модуль не зависит от Qt и может использоваться через API в будущей системе.
"""
from __future__ import annotations

from algorithms.nesting import NestResult, validate_result


def build_order_report(result: NestResult) -> str:
    """Возвращает UTF-8 текст с проверенными габаритами и расходом.

    При расчёте массы единицы: мм² * мм * г/см³ / 1_000_000 = кг.
    Масса не выводится, если не указаны и толщина, и плотность.
    """
    if not validate_result(result):
        raise ValueError("Невозможно сформировать заказ: раскладка не прошла проверку")
    lines = [
        "СПЕЦИФИКАЦИЯ ЗАКАЗНОГО ЛИСТА / РАСКРОЙ ПРОКЛАДОК",
        "=" * 52,
        f"Материал: {result.material_name.strip() or 'не указан'}",
        f"Размер заказываемого листа: {result.sheet_width:g} × {result.sheet_length:g} мм",
        f"Зазор между деталями (свободный материал): {result.gap:g} мм",
        f"Ширина реза: {result.kerf_mm:g} мм",
        f"Расчётное расстояние между контурами: {result.effective_gap:g} мм",
        f"Направление материала: {dict(none='не задано', width='вдоль ширины', length='вдоль длины')[result.grain_direction]}",
        f"Отступ от кромки: {result.margin:g} мм",
        f"Кратность заказной длины: {result.length_step:g} мм",
        f"Деталей: {len(result.placements)} шт., типоразмеров: {len(result.parts)}",
        f"Площадь листа: {result.sheet_area / 1e6:.6f} м²",
        f"Площадь деталей (без отверстий): {result.material_area / 1e6:.6f} м²",
        f"Отходы по геометрии: {result.waste_area / 1e6:.6f} м²",
        f"Использование материала: {result.utilization:.2f} %",
        f"Оптимистичная нижняя граница длины: {result.order_length_lower_bound:g} мм",
    ]
    if result.purchased_mass_kg is not None:
        lines += [
            f"Толщина листа: {result.thickness_mm:g} мм",
            f"Плотность: {result.density_g_cm3:g} г/см³",
            f"Масса заказываемого листа: {result.purchased_mass_kg:.3f} кг",
            f"Масса готовых деталей (теоретическая): {result.parts_mass_kg:.3f} кг",
        ]
    else:
        lines.append("Масса: не рассчитана (укажите толщину и плотность материала)")
    lines += ["", "ПЕРЕЧЕНЬ ДЕТАЛЕЙ", "-" * 52]
    for i, part in enumerate(result.parts, start=1):
        if part.kind in ("rectangle", "rounded_rectangle"):
            dims = f"{part.width:g} × {part.height:g} мм"
            if part.kind == "rounded_rectangle":
                dims += f", R{part.corner_radius:g} мм"
        elif part.kind == "circle":
            dims = f"Ø{part.diameter:g} мм"
        elif part.kind == "ring":
            dims = f"Ø{part.diameter:g} / Ø{part.inner_diameter:g} мм"
        else:
            dims = f"контур: {len(part.points)} вершин, отверстий: {len(part.holes)}"
        lines.append(f"{i}. {part.name} — {part.quantity} шт.; {dims}; "
                     f"ось X по материалу: {'да' if part.grain_aligned else 'нет'}")
    lines += [
        "", "ПРЕДУПРЕЖДЕНИЕ",
        "Результат получен эвристическим алгоритмом. Минимальная возможная длина",
        "не гарантируется. Перед заказом проверьте материал, направление",
        "прокатки, фактическую геометрию, технологию резки и необходимые припуски.",
        "Ширина реза применяется как дополнительный консервативный зазор,",
        "это НЕ управляющая программа станка и НЕ расчёт общего реза.",
    ]
    return "\n".join(lines) + "\n"
