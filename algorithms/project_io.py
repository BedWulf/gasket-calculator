"""Безопасное чтение сохранённого раскроя JSON, независимо от интерфейса Qt.

Поддерживаются проекты v1 (без реквизитов материала) и v2 (с толщиной,
плотностью и наименованием). Все восстановленные координаты проверяются
геометрически, чтобы нельзя было открыть ошибочный проект как корректный.
"""
from __future__ import annotations

from algorithms.nesting import NestResult, Part, Placement, validate_result


def result_from_dict(payload: dict) -> NestResult:
    if not isinstance(payload, dict):
        raise ValueError("Файл проекта должен содержать объект JSON")
    if payload.get("schema_version") not in (1, 2):
        raise ValueError("Неизвестная версия файла проекта")
    try:
        raw_parts = payload["parts"]
        raw_placements = payload["placements"]
        if not isinstance(raw_parts, list) or not isinstance(raw_placements, list):
            raise ValueError("Некорректные списки деталей и расположений")
        if not 1 <= len(raw_parts) <= 300 or len(raw_placements) > 300:
            raise ValueError("Слишком много деталей в проекте")
        parts = [Part(**entry) for entry in raw_parts]
        placements = [Placement(**entry) for entry in raw_placements]
        result = NestResult(
            sheet_width=float(payload["sheet_width"]),
            sheet_length=float(payload["sheet_length"]),
            placements=placements,
            gap=float(payload["gap"]),
            margin=float(payload["margin"]),
            length_step=float(payload["length_step"]),
            parts=parts,
            material_name=str(payload.get("material_name", "")) if payload["schema_version"] == 2 else "",
            thickness_mm=float(payload.get("thickness_mm", 0)) if payload["schema_version"] == 2 else 0.0,
            density_g_cm3=float(payload.get("density_g_cm3", 0)) if payload["schema_version"] == 2 else 0.0,
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Не удалось прочитать параметры проекта: {exc}") from exc
    if not validate_result(result):
        raise ValueError("В проекте неверные размеры, количество, зазоры или пересечения")
    return result
