"""
layout.py — Модель результата раскладки.
"""

from dataclasses import dataclass, field
from typing import List, Tuple
from .sheet import Sheet
from .gasket import Gasket


@dataclass
class PlacedGasket:
    gasket: Gasket
    x: float
    y: float
    rotation: int = 0


@dataclass
class RemainderRect:
    """Прямоугольник остатка материала."""
    x: float
    y: float
    width: float
    height: float
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    def __str__(self):
        return f"{int(self.width)}×{int(self.height)} мм"


@dataclass
class Layout:
    sheet: Sheet
    placed_gaskets: List[PlacedGasket] = field(default_factory=list)
    total_gaskets: int = 0
    waste_area: float = 0.0
    waste_percent: float = 0.0
    sheets_needed: int = 1
    remainder_rects: List[RemainderRect] = field(default_factory=list)  # Остатки
    is_rotated: bool = False  # Повёрнут ли вариант упаковки

    @property
    def used_area(self) -> float:
        return sum(g.gasket.area for g in self.placed_gaskets)

    def calculate_waste(self):
        self.waste_area = self.sheet.area - self.used_area
        if self.sheet.area > 0:
            self.waste_percent = (self.waste_area / self.sheet.area) * 100
        else:
            self.waste_percent = 0.0

    def calculate_sheets_needed(self, total_quantity: int):
        if self.total_gaskets > 0:
            import math
            self.sheets_needed = math.ceil(total_quantity / self.total_gaskets)
        else:
            self.sheets_needed = 0

    def analyze_remainders(self):
        """
        Анализ остатков материала после упаковки.
        Находит свободные прямоугольные зоны по краям листа.
        """
        self.remainder_rects = []
        
        if not self.placed_gaskets:
            # Если ничего не размещено — весь лист является остатком
            self.remainder_rects.append(RemainderRect(
                x=0, y=0, width=self.sheet.width, height=self.sheet.height
            ))
            return
        
        # Находим bounding box всех размещённых деталей
        min_x = min(p.x for p in self.placed_gaskets)
        min_y = min(p.y for p in self.placed_gaskets)
        
        max_x = 0
        max_y = 0
        for p in self.placed_gaskets:
            if p.gasket.shape.name == "RECTANGLE":
                end_x = p.x + p.gasket.length
                end_y = p.y + p.gasket.width
            else:
                end_x = p.x + p.gasket.diameter / 2
                end_y = p.y + p.gasket.diameter / 2
            max_x = max(max_x, end_x)
            max_y = max(max_y, end_y)
        
        # Остаток справа (если есть)
        if max_x < self.sheet.width:
            right_waste_width = self.sheet.width - max_x
            if right_waste_width > 1:  # Игнорируем очень узкие полосы
                self.remainder_rects.append(RemainderRect(
                    x=max_x, y=0,
                    width=right_waste_width,
                    height=self.sheet.height
                ))
        
        # Остаток снизу (если есть)
        if max_y < self.sheet.height:
            bottom_waste_height = self.sheet.height - max_y
            if bottom_waste_height > 1:
                # Ширина остатка снизу = ширина блока деталей (не всего листа)
                self.remainder_rects.append(RemainderRect(
                    x=0, y=max_y,
                    width=max_x,
                    height=bottom_waste_height
                ))
        
        # Сортируем по площади (большие сначала)
        self.remainder_rects.sort(key=lambda r: r.area, reverse=True)