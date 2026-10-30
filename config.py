"""
config.py — Настройки приложения и цветовые палитры.
"""

from enum import Enum


class Theme(Enum):
    """Перечисление доступных тем."""
    # Светлые (мягкие)
    WARM_LINEN = "Тёплый лён"
    OLIVE_GROVE = "Оливковая роща"
    COCOA_MILK = "Какао с молоком"
    
    # Темные (индустриальные)
    INDUSTRIAL_STEEL = "Индустриальная сталь"
    DEEP_OCEAN = "Глубокий океан"
    CYBER_WORKSHOP = "Кибер-цех"
    
    # Литейный цех (вместо красных)
    MOLTEN_FORM = "Раскалённая форма"
    CAST_IRON = "Чугунный цех"
    FOUNDRY_MOLD = "Литейная форма"
    
    # Корпоративные
    ONIIP_CORPORATE = "ОНИИП Корпоративный"
    ENGINEERING_BLUE = "Инженерный синий"


PALETTES = {
    # --- СВЕТЛЫЕ ТЕМЫ ---
    Theme.WARM_LINEN: {
        "app_background": "#F5F0E8",
        "panel_background": "#EDE4D0",
        "sheet_background": "#FAF6EE",
        "accent": "#C4A882",
        "accent_hover": "#B89870",
        "gasket_fill": "#9A8B72",       # приглушённый серо-коричневый
        "gasket_stroke": "#7A6B52",
        "waste_hatch": "#D4B896",
        "text_primary": "#5C4A3A",
        "text_secondary": "#8B7562",
        "border": "#D4C4A8",
        "input_background": "#FFFFFF",
    },
    Theme.OLIVE_GROVE: {
        "app_background": "#F7F3EC",
        "panel_background": "#EDE4D3",
        "sheet_background": "#FAF6EE",
        "accent": "#8FA87A",
        "accent_hover": "#7A9465",
        "gasket_fill": "#8A9A78",       # приглушённый оливковый
        "gasket_stroke": "#6B7A58",
        "waste_hatch": "#A8B89A",
        "text_primary": "#4A5440",
        "text_secondary": "#6B7560",
        "border": "#C4B898",
        "input_background": "#FFFFFF",
    },
    Theme.COCOA_MILK: {
        "app_background": "#FAF6EE",
        "panel_background": "#D4B896",
        "sheet_background": "#F0E6D2",
        "accent": "#B5C4A0",
        "accent_hover": "#9FB08A",
        "gasket_fill": "#9A8B72",       # приглушённый какао
        "gasket_stroke": "#7A6B52",
        "waste_hatch": "#C9B896",
        "text_primary": "#5C4A3A",
        "text_secondary": "#8B7562",
        "border": "#B8A888",
        "input_background": "#FFFFFF",
    },
    
    # --- ТЁМНЫЕ ТЕМЫ ---
    Theme.INDUSTRIAL_STEEL: {
        "app_background": "#1E1E24",
        "panel_background": "#25252B",
        "sheet_background": "#111115",
        "accent": "#3A86FF",
        "accent_hover": "#4CC9F0",
        "gasket_fill": "#4A5568",       # приглушённый стальной
        "gasket_stroke": "#718096",
        "waste_hatch": "#2B2D42",
        "text_primary": "#E0E0E0",
        "text_secondary": "#A0A0A0",
        "border": "#3A3A42",
        "input_background": "#2A2A30",
    },
    Theme.DEEP_OCEAN: {
        "app_background": "#0B132B",
        "panel_background": "#1C2541",
        "sheet_background": "#0A0F1E",
        "accent": "#4361EE",
        "accent_hover": "#4CC9F0",
        "gasket_fill": "#3D5A80",       # приглушённый морской
        "gasket_stroke": "#5A7BA8",
        "waste_hatch": "#1F2D3D",
        "text_primary": "#CBD5E1",
        "text_secondary": "#8899AA",
        "border": "#2A3A5C",
        "input_background": "#151E32",
    },
    Theme.CYBER_WORKSHOP: {
        "app_background": "#0D1117",
        "panel_background": "#161B22",
        "sheet_background": "#0A0D12",
        "accent": "#00B4D8",
        "accent_hover": "#0EA5E9",
        "gasket_fill": "#4A6670",       # приглушённый кибер-синий
        "gasket_stroke": "#6B8A96",
        "waste_hatch": "#212529",
        "text_primary": "#E6EDF3",
        "text_secondary": "#8B949E",
        "border": "#30363D",
        "input_background": "#1C2128",
    },
    
    # --- ЛИТЕЙНЫЙ ЦЕХ (новые, вместо красных) ---
    Theme.MOLTEN_FORM: {
        "app_background": "#2C2C2C",       # тёмно-серый графит
        "panel_background": "#3A3A3A",     # антрацит
        "sheet_background": "#1F1F1F",     # почти чёрный
        "accent": "#D97706",               # оранжевый (раскалённый металл)
        "accent_hover": "#F59E0B",
        "gasket_fill": "#5C4033",          # тёмно-коричневый (форма)
        "gasket_stroke": "#D97706",        # оранжевая кайма
        "waste_hatch": "#4B5563",          # серый
        "text_primary": "#E5E7EB",
        "text_secondary": "#9CA3AF",
        "border": "#4B4B4B",
        "input_background": "#333333",
    },
    Theme.CAST_IRON: {
        "app_background": "#1F2923",       # тёмный серо-зелёный
        "panel_background": "#2D3A32",     # темнее
        "sheet_background": "#151E18",     # почти чёрный с зелёным
        "accent": "#B45309",               # бронзовый
        "accent_hover": "#D97706",
        "gasket_fill": "#4B5563",          # тёмно-серый (чугун)
        "gasket_stroke": "#B45309",        # бронзовая кайма
        "waste_hatch": "#374151",
        "text_primary": "#D1D5DB",
        "text_secondary": "#9CA3AF",
        "border": "#3A4A3F",
        "input_background": "#263329",
    },
    Theme.FOUNDRY_MOLD: {
        "app_background": "#3D3429",       # тёмно-песочный
        "panel_background": "#4A3F33",     # темнее
        "sheet_background": "#2A2218",     # почти чёрный
        "accent": "#C2410C",               # терракотовый
        "accent_hover": "#EA580C",
        "gasket_fill": "#5C3A21",          # тёмно-коричневый (песок формы)
        "gasket_stroke": "#C2410C",        # терракотовая кайма
        "waste_hatch": "#6B5D4F",
        "text_primary": "#E8DFD0",
        "text_secondary": "#B8A88A",
        "border": "#5C4A3A",
        "input_background": "#4A3F33",
    },
    
    # --- КОРПОРАТИВНЫЕ ---
    Theme.ONIIP_CORPORATE: {
        "app_background": "#1A2332",
        "panel_background": "#243447",
        "sheet_background": "#0F1621",
        "accent": "#C9A961",
        "accent_hover": "#D4B876",
        "gasket_fill": "#4A5568",          # приглушённый серый
        "gasket_stroke": "#C9A961",        # золотая кайма
        "waste_hatch": "#1E2A3A",
        "text_primary": "#E8E8E8",
        "text_secondary": "#A0AEC0",
        "border": "#3A4A5C",
        "input_background": "#1E293B",
    },
    Theme.ENGINEERING_BLUE: {
        "app_background": "#1E293B",
        "panel_background": "#334155",
        "sheet_background": "#0F172A",
        "accent": "#3B82F6",
        "accent_hover": "#60A5FA",
        "gasket_fill": "#475569",          # приглушённый синий-серый
        "gasket_stroke": "#3B82F6",        # синяя кайма
        "waste_hatch": "#1E293B",
        "text_primary": "#F1F5F9",
        "text_secondary": "#94A3B8",
        "border": "#475569",
        "input_background": "#273548",
    },
}


DEFAULT_SHEETS = [
    {"name": "1200×2400", "width": 1200, "height": 2400},
    {"name": "1500×3000", "width": 1500, "height": 3000},
    {"name": "1500×2000", "width": 1500, "height": 2000},
    {"name": "1200×2400 (2)", "width": 1200, "height": 2400},
    {"name": "1500×3400", "width": 1500, "height": 3400},
]


GASKET_GAP = 0
APP_TITLE = "Расчёт вместимости прокладок"
APP_WIDTH = 1280
APP_HEIGHT = 800