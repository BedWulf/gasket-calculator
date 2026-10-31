"""
gasket.py — Модель прокладки.
Хранит форму и размеры, умеет считать свою площадь.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional


class GasketShape(Enum):
    """Форма прокладки."""
    RECTANGLE = "Прямоугольная"
    CIRCLE = "Круглая"


@dataclass
class Gasket:
    """
    Прокладка.
    
    Атрибуты:
        shape — форма (прямоугольная или круглая)
        length — длина (только для прямоугольной)
        width — ширина (только для прямоугольной)
        diameter — диаметр (только для круглой)
    """
    shape: GasketShape
    length: Optional[float] = None
    width: Optional[float] = None
    diameter: Optional[float] = None

    @property
    def area(self) -> float:
        """Площадь прокладки в мм²."""
        if self.shape == GasketShape.RECTANGLE:
            if self.length is None or self.width is None:
                return 0.0
            return self.length * self.width
        elif self.shape == GasketShape.CIRCLE:
            if self.diameter is None:
                return 0.0
            import math
            return math.pi * (self.diameter / 2) ** 2
        return 0.0

    @property
    def is_valid(self) -> bool:
        """Проверка, что размеры заданы корректно."""
        if self.shape == GasketShape.RECTANGLE:
            return (self.length is not None and self.width is not None
                    and math.isfinite(self.length) and math.isfinite(self.width)
                    and self.length > 0 and self.width > 0)
        elif self.shape == GasketShape.CIRCLE:
            return self.diameter is not None and math.isfinite(self.diameter) and self.diameter > 0
        return False

    def __str__(self) -> str:
        if self.shape == GasketShape.RECTANGLE:
            return f"Прямоугольная {self.length}×{self.width} мм"
        else:
            return f"Круглая Ø{self.diameter} мм"