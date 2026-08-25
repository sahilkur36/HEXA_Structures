from __future__ import annotations

import pytest

from core.surface_geometry import (
    SurfacePolygonGeometryError,
    surface_polygon_area,
    triangulate_surface_polygon,
    validate_surface_polygon,
)


def test_validate_surface_polygon_accepts_concave_boundary() -> None:
    points = [
        (0.0, 0.0, 2.0),
        (3.0, 0.0, 2.0),
        (3.0, 3.0, 2.0),
        (1.0, 1.0, 2.0),
        (0.0, 3.0, 2.0),
    ]

    geometry = validate_surface_polygon(points)

    assert geometry.area == pytest.approx(6.0)
    assert surface_polygon_area(points) == pytest.approx(6.0)
    assert len(triangulate_surface_polygon(points)) == 3


def test_validate_surface_polygon_rejects_crossing_edges() -> None:
    with pytest.raises(SurfacePolygonGeometryError) as exc_info:
        validate_surface_polygon(
            [
                (0.0, 0.0, 0.0),
                (2.0, 2.0, 0.0),
                (0.0, 2.0, 0.0),
                (2.0, 0.0, 0.0),
            ]
        )

    assert exc_info.value.code == "polygon_crossing_edges"


def test_validate_surface_polygon_rejects_non_coplanar_boundary() -> None:
    with pytest.raises(SurfacePolygonGeometryError) as exc_info:
        validate_surface_polygon(
            [
                (0.0, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                (2.0, 2.0, 0.0),
                (0.0, 2.0, 0.1),
            ]
        )

    assert exc_info.value.code == "polygon_not_coplanar"
