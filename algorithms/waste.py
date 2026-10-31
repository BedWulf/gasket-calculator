"""
waste.py — Дополнительные функции для расчёта и анализа отходов.
"""

from models.layout import Layout
from models.sheet import Sheet
from models.gasket import Gasket


class WasteCalculator:
    """Калькулятор отходов."""

    @staticmethod
    def calculate_efficiency(layout: Layout) -> float:
        """
        Коэффициент использования материала (0-100%).
        
        Returns:
            Процент полезного использования листа.
        """
        if layout.sheet.area == 0:
            return 0.0
        return 100.0 - layout.waste_percent

    @staticmethod
    def compare_sheets(gasket: Gasket, sheets: list[Sheet], gap: float = 0.0) -> list[dict]:
        """
        Сравнить эффективность разных листов для одной прокладки.
        
        Args:
            gasket — прокладка
            sheets — список листов для сравнения
            gap — расстояние между прокладками
        
        Returns:
            Список словарей с результатами для каждого листа.
        """
        from algorithms.packing import PackingAlgorithm

        results = []
        for sheet in sheets:
            layout = PackingAlgorithm.pack(sheet, gasket, gap)
            results.append({
                "sheet": sheet,
                "gaskets_per_sheet": layout.total_gaskets,
                "waste_percent": layout.waste_percent,
                "efficiency": WasteCalculator.calculate_efficiency(layout),
            })

        # Сортировка по эффективности (от лучшей к худшей)
        results.sort(key=lambda x: x["efficiency"], reverse=True)
        return results

    @staticmethod
    def calculate_total_waste(layout: Layout, quantity: int) -> float:
        """
        Общий объём отходов на весь заказ.
        
        Args:
            layout — раскладка для одного листа
            quantity — общее количество прокладок
        
        Returns:
            Общая площадь отходов в мм².
        """
        if quantity <= 0 or layout.total_gaskets == 0:
            return 0.0

        layout.calculate_sheets_needed(quantity)
        sheets_needed = layout.sheets_needed
        total_gaskets_produced = sheets_needed * layout.total_gaskets
        excess_gaskets = total_gaskets_produced - quantity

        # Отходы = (отходы на лист × кол-во листов) + площадь лишних прокладок
        total_waste = (layout.waste_area * sheets_needed) + (excess_gaskets * layout.placed_gaskets[0].gasket.area if layout.placed_gaskets else 0)
        
        return total_waste