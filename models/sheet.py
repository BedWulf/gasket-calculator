"""
sheet.py — Модель листа материала.
Хранит размеры листа и умеет считать свою площадь.
"""

from dataclasses import dataclass
import math


@dataclass
class Sheet:
    """
    Лист материала.
    
    Атрибуты:
        name — название типоразмера (например, "1200×2400")
        width — ширина в мм
        height — высота в мм
    """
    name: str
    width: float
    height: float

    @property
    def area(self) -> float:
        """Площадь листа в мм²."""
        return self.width * self.height

    @property
    def is_valid(self) -> bool:
        """Проверка корректности размеров."""
        return (math.isfinite(self.width) and math.isfinite(self.height)
                and self.width > 0 and self.height > 0)

    def __str__(self) -> str:
        return f"{self.name} ({self.width}×{self.height} мм)"