"""Небольшие функции списка заказа, не зависящие от Qt.

Одни и те же типоразмеры можно добавить несколько раз через быстрый ввод:
они объединяются в одну строку с суммарным количеством. Разные имена
сохраняются отдельно (важно для номенклатуры производства).
"""

from dataclasses import asdict
from algorithms.nesting import Part

STANDARD_KINDS = ("rectangle", "circle", "ring", "rounded_rectangle")
MAX_PIECES = 300


def standard_part(*, kind: str, quantity: int = 1, name: str = "",
                  width: float = 0, height: float = 0,
                  diameter: float = 0, inner_diameter: float = 0,
                  corner_radius: float = 0, rotate_allowed: bool = True,
                  grain_aligned: bool = False) -> Part:
    """Создать типовую деталь; имя заполняется по размеру, если оно пустое."""
    if kind not in STANDARD_KINDS:
        raise ValueError("В быстром вводе доступны только типовые формы")
    if not name.strip():
        if kind in ("rectangle", "rounded_rectangle"):
            name = f"Прямоугольник {width:g}×{height:g}"
            if kind == "rounded_rectangle":
                name += f" R{corner_radius:g}"
        elif kind == "circle":
            name = f"Круг Ø{diameter:g}"
        else:
            name = f"Кольцо Ø{diameter:g}/Ø{inner_diameter:g}"
    p = Part(name=name.strip(), kind=kind, quantity=quantity,
             width=width if kind in ("rectangle", "rounded_rectangle") else 0,
             height=height if kind in ("rectangle", "rounded_rectangle") else 0,
             diameter=diameter if kind in ("circle", "ring") else 0,
             inner_diameter=inner_diameter if kind == "ring" else 0,
             corner_radius=corner_radius if kind == "rounded_rectangle" else 0,
             rotate_allowed=rotate_allowed, grain_aligned=grain_aligned)
    p.check()
    return p


def add_to_order(parts: list[Part], part: Part, *, merge: bool = True) -> list[Part]:
    """Вернуть новый список. При ошибке исходные объекты НЕ меняются."""
    part.check()
    if sum(p.quantity for p in parts) + part.quantity > MAX_PIECES:
        raise ValueError(f"Максимальное количество деталей в одном задании — {MAX_PIECES}")
    result = [Part(**asdict(p)) for p in parts]
    if merge:
        candidate = asdict(part)
        candidate.pop('quantity')
        for i, previous in enumerate(result):
            data = asdict(previous)
            old_qty = data.pop('quantity')
            if data == candidate and old_qty + part.quantity <= MAX_PIECES:
                result[i].quantity = old_qty + part.quantity
                return result
    result.append(Part(**asdict(part)))
    return result
