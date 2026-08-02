from __future__ import annotations

from typing import Any


def point_in_geometry(longitude: float, latitude: float, geometry: dict[str, Any]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        return point_in_polygon(longitude, latitude, coordinates)
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return any(
            point_in_polygon(longitude, latitude, polygon)
            for polygon in coordinates
            if isinstance(polygon, list)
        )
    return False


def point_in_polygon(longitude: float, latitude: float, rings: list[Any]) -> bool:
    if not rings or not _point_in_ring(longitude, latitude, rings[0]):
        return False
    return not any(
        _point_in_ring(longitude, latitude, ring)
        for ring in rings[1:]
        if isinstance(ring, list)
    )


def _point_in_ring(longitude: float, latitude: float, ring: list[Any]) -> bool:
    inside = False
    previous = ring[-1] if ring else None
    for current in ring:
        if not _is_point(previous) or not _is_point(current):
            previous = current
            continue
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        if _on_segment(longitude, latitude, x1, y1, x2, y2):
            return True
        if (y1 > latitude) != (y2 > latitude):
            intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < intersection:
                inside = not inside
        previous = current
    return inside


def _on_segment(
    x: float, y: float, x1: float, y1: float, x2: float, y2: float
) -> bool:
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > 1e-10:
        return False
    return min(x1, x2) - 1e-10 <= x <= max(x1, x2) + 1e-10 and min(
        y1, y2
    ) - 1e-10 <= y <= max(y1, y2) + 1e-10


def _is_point(value: object) -> bool:
    return (
        isinstance(value, list | tuple)
        and len(value) >= 2
        and isinstance(value[0], int | float)
        and isinstance(value[1], int | float)
    )
