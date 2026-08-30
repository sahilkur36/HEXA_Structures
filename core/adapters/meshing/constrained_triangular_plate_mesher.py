"""Adapter for constrained triangular meshes of polygonal plate regions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.polygonal_plate_mesher import generate_polygonal_plate_mesh

if TYPE_CHECKING:
    from core.model_data import PlateRegionData, ProjectModel
    from core.plate_mesher import GeneratedPlateMesh


class ConstrainedTriangularPlateMesher:
    """Expose polygonal constrained triangulation through the mesh port."""

    def generate_plate_region_mesh(
        self,
        source_project: "ProjectModel",
        target_project: "ProjectModel",
        plate: "PlateRegionData",
    ) -> "GeneratedPlateMesh":
        """Generate a constrained triangular analysis mesh."""
        return generate_polygonal_plate_mesh(source_project, target_project, plate)
