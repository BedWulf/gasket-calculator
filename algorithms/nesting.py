"""Раскрой заказного листа фиксированной ширины.

Все размеры в мм. Зазор = расстояние МЕЖДУ фактическими контурами;
отступ от кромки листа задаётся отдельно. Shapely проверяет реальные контуры
и отверстия, а не только описывающие прямоугольники.

Это детерминированный эвристический раскрой (несколько порядков добавления),
НЕ гарантия глобально минимальной длины. Каждая размещённая деталь проходит
независимую геометрическую проверку; при невозможности размещения — ошибка.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from math import ceil, isfinite, pi, sqrt
import random
from time import monotonic
from typing import Literal

from shapely.affinity import rotate, translate
from shapely.geometry import Point, Polygon, box
from shapely.geometry.base import BaseGeometry

ShapeKind = Literal["rectangle", "circle", "ring", "rounded_rectangle", "polygon"]


@dataclass
class Part:
    name: str
    kind: ShapeKind
    quantity: int = 1
    width: float = 0.0
    height: float = 0.0
    diameter: float = 0.0
    inner_diameter: float = 0.0
    corner_radius: float = 0.0
    points: list[tuple[float, float]] = field(default_factory=list)
    holes: list[list[tuple[float, float]]] = field(default_factory=list)
    rotate_allowed: bool = True
    # Для сложных контуров: допустимый шаг поворота в тщательном поиске.
    # По умолчанию 45° для обратной совместимости с заданиями v1-v3.
    rotation_step: int = 45
    # Локальная ось X детали должна совпадать с направлением материала.
    grain_aligned: bool = False

    def geometry(self) -> BaseGeometry:
        """Получить контур с локальным левым верхним углом (0,0).

        Polygon может иметь отверстия. Для свободного пространства вокруг
        отверстий действует ровно тот же зазор, что и между двумя деталями.
        """
        if self.kind == "rectangle":
            g = box(0, 0, self.width, self.height)
        elif self.kind == "rounded_rectangle":
            r = self.corner_radius
            if r < 0 or 2 * r > min(self.width, self.height):
                raise ValueError(f"{self.name}: радиус скругления больше допустимого")
            g = box(r, r, self.width-r, self.height-r).buffer(r, quad_segs=12) if r else box(0, 0, self.width, self.height)
        elif self.kind == "circle":
            g = Point(self.diameter/2, self.diameter/2).buffer(self.diameter/2, quad_segs=32)
        elif self.kind == "ring":
            if self.inner_diameter <= 0 or self.inner_diameter >= self.diameter:
                raise ValueError(f"{self.name}: внутренний диаметр должен быть меньше внешнего")
            c = Point(self.diameter/2, self.diameter/2)
            g = c.buffer(self.diameter/2, quad_segs=32).difference(c.buffer(self.inner_diameter/2, quad_segs=32))
        elif self.kind == "polygon":
            g = Polygon(self.points, self.holes)
        else:
            raise ValueError(f"Неизвестная форма {self.kind}")
        if g.is_empty or not g.is_valid or g.area <= 1e-8:
            raise ValueError(f"{self.name}: неверный контур (самопересечение или некорректные размеры)")
        a, b, c, d = g.bounds
        if not all(isfinite(v) for v in (a, b, c, d)) or c-a <= 0 or d-b <= 0:
            raise ValueError(f"{self.name}: размеры должны быть положительными и конечными")
        return translate(g, -a, -b)

    def check(self) -> None:
        if not self.name.strip():
            raise ValueError("Не указано название детали")
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool) or not 1 <= self.quantity <= 300:
            raise ValueError(f"{self.name}: количество должно быть от 1 до 300")
        for value in (self.width, self.height, self.diameter, self.inner_diameter, self.corner_radius):
            if not isfinite(value) or value < 0:
                raise ValueError(f"{self.name}: размеры должны быть конечными неотрицательными")
        if self.kind in ("rectangle", "rounded_rectangle") and (self.width <= 0 or self.height <= 0):
            raise ValueError(f"{self.name}: укажите ширину и высоту")
        if self.kind in ("circle", "ring") and self.diameter <= 0:
            raise ValueError(f"{self.name}: укажите диаметр")
        if self.kind == "polygon" and len(self.points) < 3:
            raise ValueError(f"{self.name}: требуется минимум три вершины")
        if type(self.rotation_step) is not int or self.rotation_step not in (15, 30, 45, 90):
            raise ValueError(f"{self.name}: шаг поворота контура — 15°, 30°, 45° или 90°")
        self.geometry()

    def actual_area(self) -> float:
        if self.kind == "circle":
            return pi * (self.diameter / 2)**2
        if self.kind == "ring":
            return pi * (self.diameter**2 - self.inner_diameter**2) / 4
        return self.geometry().area


@dataclass
class Placement:
    part_index: int
    x: float
    y: float
    angle: int


@dataclass
class NestResult:
    sheet_width: float
    sheet_length: float
    placements: list[Placement]
    gap: float
    margin: float
    length_step: float
    parts: list[Part]
    # Поля заказа необязательны: старые проекты (schema_version=1) открываются
    # с пустыми значениями. Масса рассчитывается только при наличии обоих.
    material_name: str = ""
    thickness_mm: float = 0.0
    density_g_cm3: float = 0.0
    # Дополнительный технологический рез: консервативно увеличивает зазор
    # между деталями и требует по половине ширины реза у каждой кромки.
    kerf_mm: float = 0.0
    grain_direction: str = "none"  # none, width или length

    @property
    def effective_gap(self) -> float:
        return self.gap + self.kerf_mm

    @property
    def effective_margin(self) -> float:
        return self.margin + self.kerf_mm / 2

    @property
    def material_area(self) -> float:
        return sum(self.parts[p.part_index].actual_area() for p in self.placements)

    @property
    def sheet_area(self) -> float:
        return self.sheet_width * self.sheet_length

    @property
    def waste_area(self) -> float:
        return max(0.0, self.sheet_area - self.material_area)

    @property
    def utilization(self) -> float:
        return (100 * self.material_area / self.sheet_area) if self.sheet_area > 0 else 0

    @property
    def area_lower_bound(self) -> float:
        """Оптимистичная нижняя граница ДЛИНЫ листа, включая отступы.

        Площади контуров (вырезы исключены) должны поместиться внутри
        прямоугольника полезной ширины. Междетальные зазоры здесь намеренно
        не учитываются: это математически допустимая, но слабая граница.
        """
        usable_width = self.sheet_width - 2 * self.effective_margin
        return 2 * self.effective_margin + self.material_area / usable_width

    @property
    def order_length_lower_bound(self) -> float:
        """Гарантированная нижняя граница длины с кратностью заказа.

        Помимо площади учитываем минимальную габаритную высоту каждой
        детали с разрешёнными ориентациями, которые помещаются по ширине.
        Это НЕ найденная раскладка и не доказательство её достижимости.
        """
        min_per_part = []
        for part in self.parts:
            valid_heights = [g.bounds[3] for a in allowed_angles(part, thorough=True, grain_direction=self.grain_direction)
                             for g in [oriented_geometry(part, a)]
                             if g.bounds[2] <= self.sheet_width - 2*self.effective_margin + 1e-8]
            if not valid_heights:
                raise ValueError(f"Деталь «{part.name}» не проходит по ширине листа")
            min_per_part.append(min(valid_heights))
        return _round_up(max(self.area_lower_bound,
                             max(min_per_part) + 2*self.effective_margin), self.length_step)

    @property
    def purchased_mass_kg(self) -> float | None:
        """Масса заказного листа в кг, если заданы толщина и плотность.

        мм² * мм / 1000 (мм³/см³) * г/см³ / 1000 (г/кг).
        """
        if self.thickness_mm <= 0 or self.density_g_cm3 <= 0:
            return None
        return self.sheet_area * self.thickness_mm * self.density_g_cm3 / 1_000_000

    @property
    def parts_mass_kg(self) -> float | None:
        if self.purchased_mass_kg is None:
            return None
        return self.material_area * self.thickness_mm * self.density_g_cm3 / 1_000_000

    def to_dict(self) -> dict:
        return {
            "schema_version": (3 if self.kerf_mm or self.grain_direction != "none"
                               or any(p.grain_aligned for p in self.parts) else 2),
            "material_name": self.material_name,
            "thickness_mm": self.thickness_mm,
            "density_g_cm3": self.density_g_cm3,
            "kerf_mm": self.kerf_mm,
            "grain_direction": self.grain_direction,
            "sheet_width": self.sheet_width,
            "sheet_length": self.sheet_length,
            "gap": self.gap, "margin": self.margin, "length_step": self.length_step,
            "parts": [asdict(p) for p in self.parts],
            "placements": [asdict(p) for p in self.placements],
        }


def oriented_geometry(part: Part, angle: int) -> BaseGeometry:
    g = part.geometry()
    if angle % 360:
        g = rotate(g, angle, origin=(0, 0))
        a, b, _, _ = g.bounds
        g = translate(g, -a, -b)
    return g


def allowed_angles(part: Part, *, thorough: bool = False,
                   grain_direction: str = "none") -> tuple[int, ...]:
    """Разрешённые повороты с учётом ориентации материала.

    Для детали с grain_aligned=True локальная ось X должна быть параллельна
    оси прокатки листа. Вращение на 180° сохраняет это направление.
    """
    if not part.rotate_allowed:
        options = (0,)
    elif part.kind == "polygon":
        options = tuple(range(0, 360, part.rotation_step if thorough else 90))
    elif part.kind in ("circle", "ring"):
        options = (0,)
    else:
        options = (0, 90)
    if not part.grain_aligned:
        return options
    if grain_direction not in ("width", "length"):
        return ()
    # Явная ориентация нужна даже для круглых заготовок с волокнами.
    if part.rotate_allowed:
        if part.kind in ("circle", "ring"):
            options = (0, 90, 180, 270)
        elif part.kind != "polygon":
            options = (0, 90, 180, 270)
    locked = (0, 180) if grain_direction == "width" else (90, 270)
    return tuple(angle for angle in options if angle in locked)


def validate_result(result: NestResult) -> bool:
    """Полная проверка с учётом отверстий, отступа и междетального зазора."""
    if not all(isfinite(v) for v in (result.sheet_width, result.sheet_length,
                        result.gap, result.margin, result.length_step,
                        result.thickness_mm, result.density_g_cm3,
                        result.kerf_mm)):
        return False
    if (result.sheet_width <= 0 or result.sheet_length <= 0 or
            result.length_step <= 0 or result.gap < 0 or result.margin < 0 or
            result.thickness_mm < 0 or result.density_g_cm3 < 0 or
            result.kerf_mm < 0 or result.grain_direction not in ("none", "width", "length") or
            result.sheet_width <= 2*result.effective_margin or
            result.sheet_length <= 2*result.effective_margin):
        return False
    if abs(result.sheet_length / result.length_step - round(result.sheet_length / result.length_step)) > 1e-5:
        return False
    if not result.parts or sum(p.quantity for p in result.parts) > 300:
        return False
    try:
        for part in result.parts:
            part.check()
    except (ValueError, TypeError):
        return False
    if result.grain_direction == "none" and any(p.grain_aligned for p in result.parts):
        return False
    shapes: list[BaseGeometry] = []
    counts = [0] * len(result.parts)
    epsilon = 1e-6
    for p in result.placements:
        if type(p.part_index) is not int or p.part_index < 0 or p.part_index >= len(result.parts):
            return False
        if not (isfinite(p.x) and isfinite(p.y)):
            return False
        part = result.parts[p.part_index]
        # В старых JSON (v1-v3) для типовых форм разрешались также 180/270°.
        # Сохраняем совместимость загрузки, хотя для поиска эти повороты
        # бесполезны из-за симметрии или эквивалентны перестановке 90°.
        if part.kind != "polygon" and part.rotate_allowed:
            allowed = ((0, 90, 180, 270) if not part.grain_aligned else
                       allowed_angles(part, thorough=True, grain_direction=result.grain_direction))
        else:
            allowed = allowed_angles(part, thorough=True, grain_direction=result.grain_direction)
        if p.angle not in allowed:
            return False
        try:
            g = translate(oriented_geometry(result.parts[p.part_index], p.angle), p.x, p.y)
        except ValueError:
            return False
        x0,y0,x1,y1 = g.bounds
        if (x0 < result.effective_margin-epsilon or y0 < result.effective_margin-epsilon or
                x1 > result.sheet_width-result.effective_margin+epsilon or
                y1 > result.sheet_length-result.effective_margin+epsilon):
            return False
        for old in shapes:
            if result.effective_gap == 0:
                if g.intersection(old).area > epsilon:
                    return False
            elif g.distance(old) < result.effective_gap-epsilon:
                return False
        counts[p.part_index] += 1
        shapes.append(g)
    return all(actual == part.quantity for actual, part in zip(counts, result.parts))


def _round_up(x: float, step: float) -> float:
    return round(ceil((x-1e-9)/step)*step, 7)


def _attempt(parts: list[Part], order: list[int], width: float,
             gap: float, margin: float, step: float,
             vertex_anchors: bool = False, deadline: float | None = None,
             fine_angles: bool = False, kerf_mm: float = 0.0,
             grain_direction: str = "none") -> NestResult:
    effective_gap = gap + kerf_mm
    effective_margin = margin + kerf_mm / 2
    existing: list[tuple[BaseGeometry, tuple[float, float, float, float]]] = []
    placed: list[Placement] = []
    top = effective_margin
    allowed_right = width - effective_margin
    for idx in order:
        if deadline is not None and monotonic() >= deadline:
            raise TimeoutError('Лимит времени подробного поиска')
        part = parts[idx]
        # Внимание: для сложных деталей ориентация ограничивается их
        # rotation_step, иначе направление прокатки может быть нарушено.
        rotations = allowed_angles(part, thorough=fine_angles, grain_direction=grain_direction)
        options = [(angle, oriented_geometry(part, angle)) for angle in rotations]
        if not options:
            raise ValueError(f"Деталь «{part.name}»: допустимый поворот противоречит направлению материала")
        best = None
        for angle, shape in options:
            w = shape.bounds[2]
            h = shape.bounds[3]
            if w > width-2*effective_margin+1e-8:
                continue
            # Возможные опорные координаты задают существующие детали и кромки.
            # По двум осям проверяются комбинации: это позволяет заполнять
            # пустоты, включая отверстия в уже размещённых контурах.
            x_anchor = {round(effective_margin, 5), round(allowed_right-w, 5)}
            y_anchor = {round(effective_margin, 5), round(top+effective_gap, 5)}
            for _, (a,b,c,d) in existing:
                for x in (a, c+effective_gap, a-w-effective_gap, c-w, c-w-effective_gap):
                    if effective_margin-1e-8 <= x <= allowed_right-w+1e-8:
                        x_anchor.add(round(x, 5))
                for y in (b, d+effective_gap, b-h-effective_gap, d-h, d-h+effective_gap):
                    if y >= effective_margin-1e-8:
                        y_anchor.add(round(y, 5))
            # Укладка кругов со смещением рядов (треугольная решётка).
            # Раньше опорные точки были только у границ описывающих
            # прямоугольников: круги располагались рядами с большими пустотами.
            # Кандидаты ниже НЕ принимаются без геометрической проверки.
            if part.kind in ("circle", "ring"):
                radius = part.diameter / 2
                for old_placement, (_, obox) in zip(placed, existing):
                    old_part = parts[old_placement.part_index]
                    if old_part.kind not in ("circle", "ring"):
                        continue
                    old_radius = old_part.diameter / 2
                    separation = radius + old_radius + effective_gap
                    dx = separation / 2
                    dy = sqrt(max(0, separation**2 - dx**2))
                    ox = (obox[0] + obox[2]) / 2
                    oy = (obox[1] + obox[3]) / 2
                    for sign in (-1, 1):
                        x = ox + sign * dx - radius
                        if effective_margin-1e-8 <= x <= allowed_right-w+1e-8:
                            x_anchor.add(round(x, 5))
                    y = oy + dy - radius
                    if y >= effective_margin-1e-8:
                        # +0.0001 мм устраняет погрешности аппроксимации окружности.
                        y_anchor.add(round(y + 0.0001, 5))

            # Если контур содержит отверстия, добавляем их координаты, чтобы
            # маленькие детали могли попасть внутрь вырезов.
            for old, _ in existing:
                geom_list = [old] if old.geom_type == "Polygon" else list(getattr(old,"geoms",[]))
                for poly in geom_list:
                    for ring in poly.interiors:
                        a,b,c,d = ring.bounds
                        for x in (a+effective_gap, c-w-effective_gap):
                            if effective_margin <= x <= allowed_right-w:
                                x_anchor.add(round(x, 5))
                        for y in (b+effective_gap, d-h-effective_gap):
                            if y >= effective_margin:
                                y_anchor.add(round(y, 5))
                        # В не прямоугольном отверстии угловые кандидаты
                        # иногда не подходят. Центрирование в реальном
                        # отверстии даёт ещё одну пригодную позицию.
                        hole = Polygon(ring)
                        if hole.is_valid and hole.area > shape.area:
                            center = hole.centroid
                            part_center = shape.centroid
                            xcenter = center.x - part_center.x
                            ycenter = center.y - part_center.y
                            if effective_margin <= xcenter <= allowed_right-w:
                                x_anchor.add(round(xcenter, 5))
                            if ycenter >= effective_margin:
                                y_anchor.add(round(ycenter, 5))
            # Дополнительные опорные точки: вершины сложных контуров (в т.ч.
            # вырезов). Это помогает стыковать L-образные и нестандартные формы,
            # а не только их габаритные прямоугольники. Проверка дистанции
            # остаётся обязательной; опорные точки лишь предлагают позиции.
            if vertex_anchors and (part.kind == "polygon" or any(p.kind == "polygon" for p in parts)):
                def sample_vertices(poly, limit=20):
                    rings = [poly.exterior, *poly.interiors] if poly.geom_type == "Polygon" else []
                    for ring in rings:
                        coords = list(ring.coords)[:-1]
                        if not coords:
                            continue
                        stride = max(1, len(coords) // limit)
                        for point in coords[::stride][:limit]:
                            yield point

                source_vertices = list(sample_vertices(shape, 14))
                for old, _ in existing[-14:]:
                    target_vertices = list(sample_vertices(old, 14))
                    for vx, vy in target_vertices:
                        for px, py in source_vertices:
                            for x in (vx - px, vx - px + effective_gap, vx - px - effective_gap):
                                if effective_margin - 1e-8 <= x <= allowed_right-w+1e-8:
                                    x_anchor.add(round(x, 5))
                            for y in (vy - py, vy - py + effective_gap, vy - py - effective_gap):
                                if y >= effective_margin - 1e-8:
                                    y_anchor.add(round(y, 5))
            # Предпочитаем положения с небольшой высотой и близко к левому краю.
            # Предел устраняет взрыв сложности на крупных заказах.
            xs = sorted(x_anchor)
            ys = sorted(y_anchor)
            if len(xs) > 90: xs = xs[:50] + xs[-40:]
            if len(ys) > 90: ys = ys[:75] + ys[-15:]
            for y in ys:
                if deadline is not None and monotonic() >= deadline:
                    raise TimeoutError('Лимит времени подробного поиска')
                if best is not None and max(top, y+h) > best[0][0] + 1e-7:
                    break
                for x in xs:
                    if x+w > allowed_right+1e-6:
                        continue
                    geom = translate(shape, x, y)
                    bbox = geom.bounds
                    collision = False
                    for other, obox in existing:
                        # Быстрая проверка описывающих рамок до Shapely.distance().
                        if (bbox[2]+effective_gap <= obox[0]+1e-7 or obox[2]+effective_gap <= bbox[0]+1e-7 or
                            bbox[3]+effective_gap <= obox[1]+1e-7 or obox[3]+effective_gap <= bbox[1]+1e-7):
                            continue
                        if (geom.intersection(other).area > 1e-7 if effective_gap == 0
                            else geom.distance(other) < effective_gap-1e-7):
                            collision = True
                            break
                    if not collision:
                        score = (max(top, y+h), y+h, y, x, angle)
                        if best is None or score < best[0]:
                            best = (score, idx, x, y, angle, geom)
        if best is None:
            raise ValueError(f"Деталь «{part.name}» не помещается при ширине {width:g} мм")
        _, idx, x, y, angle, geom = best
        placed.append(Placement(idx, x, y, angle))
        existing.append((geom, geom.bounds))
        top = max(top, geom.bounds[3])
    length = _round_up(top + effective_margin, step)
    result = NestResult(width, length, placed, gap, margin, step, parts,
                        kerf_mm=kerf_mm, grain_direction=grain_direction)
    if not validate_result(result):
        raise RuntimeError("Ошибка внутренней проверки раскроя")
    return result


def calculate_variants(parts: list[Part], sheet_width: float,
                    gap: float = 0.0, margin: float = 0.0,
                    length_step: float = 1.0,
                    quality: str = "standard",
                    max_variants: int = 6, kerf_mm: float = 0.0,
                    grain_direction: str = "none") -> list[NestResult]:
    """Подобрать и вернуть несколько РАЗНЫХ корректных раскладок листа.

    Отсортированы по длине заказного листа; расход материала для одной
    ширины и набора деталей однозначно определяется этой длиной.
    Равные по длине варианты могут отличаться положением и поворотом деталей.
    Каждый вариант независимо проходит проверку геометрии.

    Подобрать длину листа при фиксированной ширине.

    Пытаемся несколько порядков укладки и выбираем самый короткий корректный.
    `length_step` позволяет заказать длину с нужной кратностью (например, 10 мм).
    quality='standard' — быстрый многовариантный расчёт;
    quality='thorough' — дополнительный поиск опорных вершин и порядков,
    повороты сложных контуров с шагом 15/30/45/90° для небольших партий.
    Результат не хуже standard, поскольку
    его варианты включены в рассмотрение. Это всё ещё эвристика.
    """
    if type(max_variants) is not int or not 1 <= max_variants <= 20:
        raise ValueError("Количество вариантов должно быть от 1 до 20")
    if quality not in ("standard", "thorough"):
        raise ValueError("Неизвестный режим качества раскроя")
    if not all(isfinite(v) for v in (sheet_width, gap, margin, length_step, kerf_mm)):
        raise ValueError("Введите конечные числовые значения")
    if sheet_width <= 0 or gap < 0 or margin < 0 or length_step <= 0 or kerf_mm < 0:
        raise ValueError("Ширина и шаг должны быть положительными; зазор и отступ неотрицательные")
    if grain_direction not in ("none", "width", "length"):
        raise ValueError("Неизвестное направление материала")
    if sheet_width <= 2*(margin + kerf_mm/2):
        raise ValueError("Отступ и ширина реза оставляют слишком мало ширины листа")
    if not parts:
        raise ValueError("Добавьте минимум одну деталь")
    for p in parts:
        p.check()
        if not allowed_angles(p, thorough=True, grain_direction=grain_direction):
            raise ValueError(f"Деталь «{p.name}»: укажите направление материала или разрешите подходящий поворот")
    if sum(p.quantity for p in parts) > 300:
        raise ValueError("В одном задании допускается не больше 300 деталей")
    geoms = [p.geometry() for p in parts]
    quantities = [i for i,p in enumerate(parts) for _ in range(p.quantity)]
    strategies = [
        lambda i: (-geoms[i].area, -geoms[i].bounds[2], i),
        lambda i: (-max(geoms[i].bounds[2], geoms[i].bounds[3]), -geoms[i].area, i),
        lambda i: (-geoms[i].bounds[3], -geoms[i].area, i),
        lambda i: (-geoms[i].bounds[2], -geoms[i].area, i),
        lambda i: (-(geoms[i].bounds[2]+geoms[i].bounds[3]), -geoms[i].area, i),
    ]
    results = []
    for sorter in strategies:
        order = sorted(quantities, key=sorter)
        try:
            results.append(_attempt(parts, order, sheet_width, gap, margin, length_step,
                                    kerf_mm=kerf_mm, grain_direction=grain_direction))
        except ValueError:
            continue
    # Контурные якоря существенно дороже. На больших заказах не включаем
    # автоматически: интерфейс должен оставаться отзывчивым.
    if quality == "thorough" and len(quantities) <= 55:
        deadline = monotonic() + 4.0  # Лимит только дополнительных вариантов.
        has_polygons = any(p.kind == "polygon" for p in parts)
        orders = [sorted(quantities, key=strategies[0]),
                  sorted(quantities, key=strategies[1])]
        rng = random.Random(7331)  # Повторяемый результат для одинакового задания.
        for _ in range(4):
            order = sorted(quantities, key=strategies[0])
            # Локальные изменения порядка: малые детали заполняют вырезы.
            for _ in range(max(3,len(order)//3)):
                a,b = rng.sample(range(len(order)),2) if len(order)>1 else (0,0)
                order[a],order[b]=order[b],order[a]
            orders.append(order)
        for order in orders:
            try:
                results.append(_attempt(parts, order, sheet_width, gap, margin, length_step,
                                        vertex_anchors=has_polygons, deadline=deadline,
                                        fine_angles=has_polygons, kerf_mm=kerf_mm,
                                        grain_direction=grain_direction))
            except TimeoutError:
                break
            except ValueError:
                continue
    if not results:
        raise ValueError("Не удаётся разместить детали на листе заданной ширины (включая возможный поворот)")
    # Убираем повторяющиеся варианты независимо от порядка экземпляров
    # одинакового типоразмера. Длина и все координаты учитываются в ключе.
    # Стабильная сортировка сохраняет приоритет первого найденного решения.
    unique: list[NestResult] = []
    seen = set()
    for result in sorted(results, key=lambda r: (r.sheet_length, r.waste_area)):
        key = (round(result.sheet_length, 6), tuple(sorted(
            (p.part_index, round(p.x, 4), round(p.y, 4), p.angle % 360)
            for p in result.placements)))
        if key not in seen:
            if not validate_result(result):
                raise RuntimeError("Некорректная альтернативная раскладка")
            seen.add(key)
            unique.append(result)
            if len(unique) == max_variants:
                break
    return unique


def calculate_sheet(parts: list[Part], sheet_width: float,
                    gap: float = 0.0, margin: float = 0.0,
                    length_step: float = 1.0,
                    quality: str = "standard", kerf_mm: float = 0.0,
                    grain_direction: str = "none") -> NestResult:
    """Обратная совместимость: лучший из доступных вариантов раскроя.

    Для просмотра и ручного выбора нескольких схем используйте
    :func:`calculate_variants`.
    """
    return calculate_variants(parts, sheet_width, gap, margin, length_step,
                              quality=quality, max_variants=1, kerf_mm=kerf_mm,
                              grain_direction=grain_direction)[0]
