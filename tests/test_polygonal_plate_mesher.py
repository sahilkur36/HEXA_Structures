from __future__ import annotations

from copy import deepcopy
import math

import pytest

pytest.importorskip("cytriangle")

from core.adapters.meshing import ConstrainedTriangularPlateMesher
from core.model_data import ProjectModel
from core.plate_mesh_settings import polygonal_plate_mesh_recommendation
from core.self_weight import surface_area_m2
from core.surface_geometry import validate_surface_polygon


def _concave_project(*, divisions: int = 6) -> ProjectModel:
    project = ProjectModel(name="Concave polygon mesh")
    project.add_material("Beton C30", "concrete", "C30/37")
    section = project.add_section(
        "Dalle 20 cm",
        "surface",
        material_tag=1,
        properties={"thickness": 0.20, "element_formulation": "ShellMITC4"},
    )
    for point in (
        (0.0, 0.0, 0.0),
        (4.0, 0.0, 0.0),
        (4.0, 3.0, 0.0),
        (2.0, 1.5, 0.0),
        (0.0, 3.0, 0.0),
    ):
        project.add_node(*point)
    project.add_plate_region(
        (1, 2, 3, 4, 5),
        section_tag=section.tag,
        mesh_nx=divisions,
        mesh_ny=divisions,
    )
    return project


def _triangle_area(project: ProjectModel, nodes: tuple[int, ...]) -> float:
    points = [
        (project.nodes[tag].x, project.nodes[tag].y, project.nodes[tag].z)
        for tag in nodes
    ]
    first = tuple(points[1][axis] - points[0][axis] for axis in range(3))
    second = tuple(points[2][axis] - points[0][axis] for axis in range(3))
    cross = (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )
    return 0.5 * math.sqrt(sum(value * value for value in cross))


def _minimum_triangle_angle(project: ProjectModel, nodes: tuple[int, ...]) -> float:
    points = [
        (project.nodes[tag].x, project.nodes[tag].y, project.nodes[tag].z)
        for tag in nodes
    ]
    lengths = [
        math.dist(points[index], points[(index + 1) % 3])
        for index in range(3)
    ]
    angles = []
    for opposite, adjacent_1, adjacent_2 in (
        (lengths[1], lengths[0], lengths[2]),
        (lengths[2], lengths[0], lengths[1]),
        (lengths[0], lengths[1], lengths[2]),
    ):
        cosine = (
            adjacent_1**2 + adjacent_2**2 - opposite**2
        ) / (2.0 * adjacent_1 * adjacent_2)
        angles.append(math.degrees(math.acos(max(-1.0, min(1.0, cosine)))))
    return min(angles)


def test_constrained_mesher_preserves_concave_area_and_boundary() -> None:
    source = _concave_project()
    target = deepcopy(source)
    source_counts = (len(source.nodes), len(source.surface_elements))

    mesh = ConstrainedTriangularPlateMesher().generate_plate_region_mesh(
        source,
        target,
        source.plate_regions[1],
    )

    assert (len(source.nodes), len(source.surface_elements)) == source_counts
    assert mesh.mesh_kind == "constrained_triangular"
    assert mesh.mesh_nx == 0
    assert mesh.mesh_ny == 0
    assert mesh.surface_tags
    assert all(len(nodes) == 3 for nodes in mesh.cell_node_tags)
    assert all(
        target.surface_elements[tag].formulation == "ASDShellT3"
        for tag in mesh.surface_tags
    )
    assert sum(
        surface_area_m2(target, target.surface_elements[tag])
        for tag in mesh.surface_tags
    ) == pytest.approx(9.0)
    assert mesh.boundary_node_tags["12"][0] == 1
    assert mesh.boundary_node_tags["12"][-1] == 2
    assert mesh.boundary_node_tags["51"][0] == 5
    assert mesh.boundary_node_tags["51"][-1] == 1


def test_constrained_mesher_respects_area_and_quality_targets() -> None:
    source = _concave_project(divisions=5)
    target = deepcopy(source)
    plate = source.plate_regions[1]
    recommendation = polygonal_plate_mesh_recommendation(source, plate)

    mesh = ConstrainedTriangularPlateMesher().generate_plate_region_mesh(
        source,
        target,
        plate,
    )

    areas = [_triangle_area(target, nodes) for nodes in mesh.cell_node_tags]
    angles = [_minimum_triangle_angle(target, nodes) for nodes in mesh.cell_node_tags]
    assert max(areas) <= recommendation.max_triangle_area * 1.001
    assert min(angles) >= recommendation.min_angle_deg - 0.1


def test_adjacent_polygonal_regions_share_identical_boundary_nodes() -> None:
    project = ProjectModel(name="Adjacent polygon meshes")
    project.add_material("Beton C30", "concrete", "C30/37")
    section = project.add_section(
        "Dalle 20 cm",
        "surface",
        material_tag=1,
        properties={"thickness": 0.20, "element_formulation": "ShellMITC4"},
    )
    for point in (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.5, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (2.0, 0.0, 0.0),
        (2.0, 1.0, 0.0),
        (1.5, 1.0, 0.0),
    ):
        project.add_node(*point)
    left = project.add_plate_region(
        (1, 2, 3, 4, 5),
        section_tag=section.tag,
        mesh_nx=4,
        mesh_ny=4,
    )
    right = project.add_plate_region(
        (2, 6, 7, 8, 3),
        section_tag=section.tag,
        mesh_nx=8,
        mesh_ny=8,
    )
    target = deepcopy(project)
    mesher = ConstrainedTriangularPlateMesher()

    left_mesh = mesher.generate_plate_region_mesh(project, target, left)
    right_mesh = mesher.generate_plate_region_mesh(project, target, right)

    left_edge = left_mesh.boundary_node_tags["23"]
    right_edge = right_mesh.boundary_node_tags["51"]
    assert len(left_edge) > 2
    assert left_edge == tuple(reversed(right_edge))


def test_constrained_mesher_is_deterministic() -> None:
    source = _concave_project(divisions=5)
    targets = [deepcopy(source), deepcopy(source)]

    meshes = [
        ConstrainedTriangularPlateMesher().generate_plate_region_mesh(
            source,
            target,
            source.plate_regions[1],
        )
        for target in targets
    ]

    assert meshes[0].cell_node_tags == meshes[1].cell_node_tags
    assert meshes[0].boundary_node_tags == meshes[1].boundary_node_tags
    assert {
        tag: (node.x, node.y, node.z)
        for tag, node in targets[0].nodes.items()
    } == {
        tag: (node.x, node.y, node.z)
        for tag, node in targets[1].nodes.items()
    }


def test_constrained_mesher_preserves_inclined_plane_and_orientation() -> None:
    source = ProjectModel(name="Inclined polygon mesh")
    source.add_material("Beton C30", "concrete", "C30/37")
    section = source.add_section(
        "Voile 20 cm",
        "surface",
        material_tag=1,
        properties={"thickness": 0.20, "element_formulation": "ShellMITC4"},
    )
    points = [
        (0.0, 0.0, 0.0),
        (3.0, 0.0, 1.2),
        (3.0, 2.0, 1.6),
        (1.5, 1.0, 0.8),
        (0.0, 2.0, 0.4),
    ]
    for point in points:
        source.add_node(*point)
    plate = source.add_plate_region(
        (1, 2, 3, 4, 5),
        section_tag=section.tag,
        mesh_nx=5,
        mesh_ny=5,
    )
    geometry = validate_surface_polygon(points)
    target = deepcopy(source)

    mesh = ConstrainedTriangularPlateMesher().generate_plate_region_mesh(
        source,
        target,
        plate,
    )

    assert sum(_triangle_area(target, nodes) for nodes in mesh.cell_node_tags) == pytest.approx(
        geometry.area
    )
    for node_tag in mesh.node_tags.values():
        node = target.nodes[node_tag]
        relative = (
            node.x - geometry.origin[0],
            node.y - geometry.origin[1],
            node.z - geometry.origin[2],
        )
        assert sum(
            relative[index] * geometry.normal[index]
            for index in range(3)
        ) == pytest.approx(0.0, abs=1e-9)

    for cell in mesh.cell_node_tags:
        p0 = target.nodes[cell[0]]
        p1 = target.nodes[cell[1]]
        p2 = target.nodes[cell[2]]
        edge_1 = (p1.x - p0.x, p1.y - p0.y, p1.z - p0.z)
        edge_2 = (p2.x - p0.x, p2.y - p0.y, p2.z - p0.z)
        cell_normal = (
            edge_1[1] * edge_2[2] - edge_1[2] * edge_2[1],
            edge_1[2] * edge_2[0] - edge_1[0] * edge_2[2],
            edge_1[0] * edge_2[1] - edge_1[1] * edge_2[0],
        )
        assert sum(
            cell_normal[index] * geometry.normal[index]
            for index in range(3)
        ) > 0.0
