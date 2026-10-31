"""Векторный контурный чертёж в реальных миллиметрах (не G-code)."""
from __future__ import annotations

from xml.sax.saxutils import escape
from shapely.affinity import translate

from algorithms.nesting import NestResult, oriented_geometry, validate_result

COLORS = ["#459ad5", "#e9a23b", "#58b49d", "#ab86d5", "#e78c83", "#77a4cd", "#91b665"]


def build_svg(result: NestResult) -> str:
    """Контуры деталей с отверстиями. `fill-rule=evenodd` защищает отверстия."""
    if not validate_result(result):
        raise ValueError("Нельзя экспортировать раскрой с пересечениями или неверными границами")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{result.sheet_width:g}mm" height="{result.sheet_length:g}mm" viewBox="0 0 {result.sheet_width:g} {result.sheet_length:g}">',
        f'<rect x="0" y="0" width="{result.sheet_width:g}" height="{result.sheet_length:g}" fill="white" stroke="black" stroke-width="0.6"/>',
    ]
    for p in result.placements:
        shape = translate(oriented_geometry(result.parts[p.part_index], p.angle),p.x,p.y)
        polygons = [shape] if shape.geom_type == "Polygon" else list(shape.geoms)
        segments = []
        for polygon in polygons:
            for ring in [polygon.exterior, *polygon.interiors]:
                coords = list(ring.coords)
                segments.append('M ' + ' L '.join(f'{x:.4f},{y:.4f}' for x,y in coords) + ' Z')
        color = COLORS[p.part_index % len(COLORS)]
        lines.append(f'<path d="{" ".join(segments)}" fill="{color}" fill-opacity="0.40" stroke="#1a202c" stroke-width="0.5" fill-rule="evenodd">')
        lines.append(f'<title>{escape(result.parts[p.part_index].name)}</title></path>')
    lines.append('</svg>')
    return '\n'.join(lines)
