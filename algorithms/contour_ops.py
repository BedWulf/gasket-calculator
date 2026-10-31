"""Чистые функции для редактора 2D-контуров; размеры в миллиметрах."""
from __future__ import annotations

from math import acos, atan2, ceil, cos, hypot, pi, sin, tan

from shapely.geometry import Polygon


def fillet_corner(points: list[tuple[float,float]], index: int,
                  radius: float, tolerance: float = 0.1) -> list[tuple[float,float]]:
    """Заменить выпуклую вершину дугой радиуса R.

    Дуга превращается в отрезки с хордовой погрешностью <= tolerance.
    Соседние стороны должны быть достаточны для данного радиуса.
    Поддерживается выпуклый угол внешнего контура или отверстия.
    """
    if not 0 <= index < len(points) or len(points)<3:
        raise ValueError('Не выбрана вершина для скругления')
    if not (radius > 0 and 0 < tolerance <= 2):
        raise ValueError('Радиус должен быть положительным; допуск — от 0 до 2 мм')
    polygon=Polygon(points)
    if not polygon.is_valid or polygon.area<=0:
        raise ValueError('Перед скруглением исправьте контур')
    prev=points[index-1];p=points[index];nxt=points[(index+1)%len(points)]
    u=(prev[0]-p[0],prev[1]-p[1]);v=(nxt[0]-p[0],nxt[1]-p[1])
    lu=hypot(*u);lv=hypot(*v)
    if lu<1e-8 or lv<1e-8:raise ValueError('Смежная сторона имеет нулевую длину')
    u=(u[0]/lu,u[1]/lu);v=(v[0]/lv,v[1]/lv)
    theta=acos(max(-1,min(1,u[0]*v[0]+u[1]*v[1])))
    if theta<=0.001 or theta>=pi-0.001:raise ValueError('Нельзя скруглить нулевой или прямой угол (180°)')
    incoming=(p[0]-prev[0],p[1]-prev[1]);outgoing=(nxt[0]-p[0],nxt[1]-p[1])
    cross=incoming[0]*outgoing[1]-incoming[1]*outgoing[0]
    if cross*(1 if polygon.exterior.is_ccw else -1)<=1e-8:
        raise ValueError('Для этого инструмента поддерживаются только выпуклые углы')
    tangent=radius/tan(theta/2)
    if tangent>=min(lu,lv)-1e-7:
        raise ValueError(f'Радиус слишком велик: расстояние до точки касания {tangent:.2f} мм')
    a=(p[0]+u[0]*tangent,p[1]+u[1]*tangent)
    b=(p[0]+v[0]*tangent,p[1]+v[1]*tangent)
    bis=(u[0]+v[0],u[1]+v[1]);bl=hypot(*bis)
    distance=radius/sin(theta/2)
    center=(p[0]+distance*bis[0]/bl,p[1]+distance*bis[1]/bl)
    start=atan2(a[1]-center[1],a[0]-center[0])
    stop=atan2(b[1]-center[1],b[0]-center[0])
    direction=1 if polygon.exterior.is_ccw else -1
    if direction==1:
        while stop<start:stop+=2*pi
    else:
        while stop>start:stop-=2*pi
    sweep=stop-start
    # Строим дугу на внутренней стороне угла, а не большой обход.
    if abs(sweep)>pi+1e-5:
        raise ValueError('Не удалось построить скругление; проверьте ориентацию контура')
    max_angle=2*acos(max(-1,min(1,1-min(tolerance/radius,1.))))
    segments=max(3,min(256,ceil(abs(sweep)/max(max_angle,0.01))))
    arc=[(round(center[0]+radius*cos(start+sweep*i/segments),5),
          round(center[1]+radius*sin(start+sweep*i/segments),5))
         for i in range(segments+1)]
    new=points[:index]+arc+points[index+1:]
    if not Polygon(new).is_valid:
        raise ValueError('Скругление вызвало пересечение соседних элементов')
    return new


def set_edge_length(points: list[tuple[float, float]], edge_start: int,
                    new_length: float) -> list[tuple[float, float]]:
    """Resize one edge in mm, keeping its first vertex and direction fixed.

    Only the second endpoint moves. Geometry validity of the entire gasket,
    including holes, must be checked by the caller before applying the change.
    """
    from math import isfinite

    if len(points) < 3 or not 0 <= edge_start < len(points):
        raise ValueError('Выберите ребро замкнутого контура')
    if not isfinite(new_length) or new_length <= 0:
        raise ValueError('Длина ребра должна быть положительной и конечной')
    a = points[edge_start]
    end_idx = (edge_start + 1) % len(points)
    b = points[end_idx]
    old_length = hypot(b[0] - a[0], b[1] - a[1])
    if old_length <= 1e-9:
        raise ValueError('У выбранного ребра нулевая длина')
    updated = list(points)
    updated[end_idx] = (
        round(a[0] + (b[0] - a[0]) * new_length / old_length, 5),
        round(a[1] + (b[1] - a[1]) * new_length / old_length, 5),
    )
    return updated


def rectangular_hole(center: tuple[float, float], width: float,
                     height: float) -> list[tuple[float, float]]:
    """Four-point closed rectangle, centered at a selected drawing location."""
    from math import isfinite
    if not all(isfinite(v) for v in (*center, width, height)) or min(width, height) <= 0:
        raise ValueError('Центр и размеры отверстия должны быть корректными')
    x, y = center
    w, h = width / 2, height / 2
    return [(x-w, y-h), (x+w, y-h), (x+w, y+h), (x-w, y+h)]


def circular_hole(center: tuple[float, float], diameter: float,
                  segments: int = 96) -> list[tuple[float, float]]:
    """Approximate a circular hole by a regular polygon in millimetres."""
    from math import isfinite
    if (not all(isfinite(v) for v in (*center, diameter)) or diameter <= 0
            or not 24 <= segments <= 512):
        raise ValueError('Некорректный диаметр, центр или точность окружности')
    cx, cy = center
    radius = diameter / 2
    return [(cx + radius*cos(2*pi*i/segments),
             cy + radius*sin(2*pi*i/segments)) for i in range(segments)]
