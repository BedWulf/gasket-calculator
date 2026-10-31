"""
sheet_repository.py — Сохранение и загрузка типоразмеров листов в JSON.
"""

import json
import os
from models.sheet import Sheet
from config import DEFAULT_SHEETS


class SheetRepository:
    """Управляет списком листов и сохраняет их в файл."""
    
    FILE_PATH = "sheets_data.json"

    def __init__(self):
        self.sheets = []
        if os.path.exists(self.FILE_PATH):
            self.load()
        else:
            # Если файла нет, создаем его со стандартными листами
            self.sheets = [Sheet(**s) for s in DEFAULT_SHEETS]
            self.save()

    def load(self):
        """Загрузка листов из JSON."""
        try:
            with open(self.FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.sheets = [Sheet(**s) for s in data]
        except Exception as e:
            print(f"Ошибка загрузки листов: {e}")
            self.sheets = [Sheet(**s) for s in DEFAULT_SHEETS]

    def save(self):
        """Сохранение листов в JSON."""
        data = [{"name": s.name, "width": s.width, "height": s.height} for s in self.sheets]
        with open(self.FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def add_sheet(self, sheet: Sheet):
        """Добавить новый лист."""
        self.sheets.append(sheet)
        self.save()

    def remove_sheet(self, index: int):
        """Удалить лист по индексу."""
        if 0 <= index < len(self.sheets):
            self.sheets.pop(index)
            self.save()