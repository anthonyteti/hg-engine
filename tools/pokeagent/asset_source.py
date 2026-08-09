"""Source-format-neutral static mesh records used before asset normalization."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MeshCorner:
    vertex: int
    uv: int
    normal: int


@dataclass(frozen=True)
class MeshFace:
    id: str
    material: str
    corners: tuple[MeshCorner, ...]

    @property
    def primitive(self) -> str:
        return "triangle" if len(self.corners) == 3 else "quad"


@dataclass(frozen=True)
class SourceMesh:
    vertices: tuple[tuple[float, float, float], ...]
    uvs: tuple[tuple[float, float], ...]
    normals: tuple[tuple[float, float, float], ...]
    faces: tuple[MeshFace, ...]
    metadata: dict[str, object] = field(default_factory=dict)
