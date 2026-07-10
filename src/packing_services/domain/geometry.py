"""Primitivas geométricas para packing 3D con cajas alineadas a los ejes (AABB).

Todo el proyecto asume cajas rectangulares alineadas a los ejes X (length),
Y (width) y Z (height). El origen del contenedor es la esquina (0, 0, 0) y las
coordenadas crecen hacia +x, +y, +z. La posición de un ítem colocado es la
esquina de menor coordenada (min-corner).

Estas funciones son deterministas y sin estado: reciben datos simples y
devuelven resultados, lo que las hace fáciles de testear de forma aislada.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations

# Tolerancia para comparaciones en punto flotante. Evita falsos positivos de
# solapamiento cuando dos caras se tocan exactamente por redondeo.
EPS = 1e-6


@dataclass(frozen=True)
class Dimensions:
    """Dimensiones de una caja: length (x), width (y), height (z)."""

    length: float
    width: float
    height: float

    @property
    def volume(self) -> float:
        return self.length * self.width * self.height

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.length, self.width, self.height)


@dataclass(frozen=True)
class Position:
    """Esquina de menor coordenada de una caja colocada."""

    x: float
    y: float
    z: float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class AABB:
    """Caja alineada a los ejes definida por posición + dimensiones."""

    position: Position
    dimensions: Dimensions

    @property
    def min_corner(self) -> tuple[float, float, float]:
        return self.position.as_tuple()

    @property
    def max_corner(self) -> tuple[float, float, float]:
        return (
            self.position.x + self.dimensions.length,
            self.position.y + self.dimensions.width,
            self.position.z + self.dimensions.height,
        )


def _canonical_orientation(dims: Dimensions) -> tuple[float, float, float]:
    """Firma ordenada de dimensiones, invariante a la rotación aplicada."""

    return tuple(sorted(dims.as_tuple()))  # type: ignore[return-value]


def unique_orientations(dims: Dimensions, allow_rotation: bool) -> list[Dimensions]:
    """Devuelve las orientaciones únicas de una caja.

    Con ``allow_rotation`` se generan hasta 6 permutaciones de (l, w, h),
    eliminando duplicados (p. ej. si dos lados son iguales). Sin rotación se
    devuelve únicamente la orientación original.
    """

    if not allow_rotation:
        return [dims]

    seen: set[tuple[float, float, float]] = set()
    result: list[Dimensions] = []
    for perm in permutations(dims.as_tuple()):
        if perm not in seen:
            seen.add(perm)
            result.append(Dimensions(perm[0], perm[1], perm[2]))
    return result


def is_same_box(dims_a: Dimensions, dims_b: Dimensions) -> bool:
    """True si dos conjuntos de dimensiones representan la misma caja base.

    Compara la firma ordenada, por lo que una orientación rotada del mismo ítem
    se considera equivalente a su forma original.
    """

    a = _canonical_orientation(dims_a)
    b = _canonical_orientation(dims_b)
    return all(abs(x - y) <= EPS for x, y in zip(a, b))


def fits_within(box: AABB, container: Dimensions) -> bool:
    """True si la caja está completamente contenida en el contenedor."""

    px, py, pz = box.min_corner
    mx, my, mz = box.max_corner
    return (
        px >= -EPS
        and py >= -EPS
        and pz >= -EPS
        and mx <= container.length + EPS
        and my <= container.width + EPS
        and mz <= container.height + EPS
    )


def overlaps(a: AABB, b: AABB) -> bool:
    """True si dos cajas se solapan con volumen positivo.

    El contacto exacto entre caras (comparten un plano) NO se considera
    solapamiento gracias a la tolerancia EPS.
    """

    a_min = a.min_corner
    a_max = a.max_corner
    b_min = b.min_corner
    b_max = b.max_corner
    for i in range(3):
        # Separación en algún eje => no hay solapamiento.
        if a_max[i] <= b_min[i] + EPS or b_max[i] <= a_min[i] + EPS:
            return False
    return True


def overlap_volume(a: AABB, b: AABB) -> float:
    """Volumen de intersección entre dos cajas (0 si no se solapan)."""

    a_min, a_max = a.min_corner, a.max_corner
    b_min, b_max = b.min_corner, b.max_corner
    dims = []
    for i in range(3):
        lo = max(a_min[i], b_min[i])
        hi = min(a_max[i], b_max[i])
        overlap = hi - lo
        if overlap <= EPS:
            return 0.0
        dims.append(overlap)
    return dims[0] * dims[1] * dims[2]


def is_interior_point(point: tuple[float, float, float], box: AABB) -> bool:
    """True si el punto está estrictamente dentro del volumen de la caja.

    Se usa para limpiar puntos extremos que quedaron cubiertos por una caja
    recién colocada (un punto sobre una cara NO se considera interior).
    """

    px, py, pz = point
    b_min = box.min_corner
    b_max = box.max_corner
    return (
        b_min[0] + EPS < px < b_max[0] - EPS
        and b_min[1] + EPS < py < b_max[1] - EPS
        and b_min[2] + EPS < pz < b_max[2] - EPS
    )


def face_contact_area(a: AABB, b: AABB) -> float:
    """Área de contacto cara-con-cara entre dos cajas adyacentes.

    Dos cajas que comparten un plano perpendicular a un eje (p. ej. la cara
    derecha de una coincide con la izquierda de la otra) aportan como contacto
    el área solapada en los otros dos ejes. Si no se tocan, devuelve 0.
    """

    a_min, a_max = a.min_corner, a.max_corner
    b_min, b_max = b.min_corner, b.max_corner

    total = 0.0
    for axis in range(3):
        others = [i for i in range(3) if i != axis]
        touching = (
            abs(a_max[axis] - b_min[axis]) <= EPS
            or abs(a_min[axis] - b_max[axis]) <= EPS
        )
        if not touching:
            continue
        overlap = 1.0
        for o in others:
            lo = max(a_min[o], b_min[o])
            hi = min(a_max[o], b_max[o])
            gap = hi - lo
            if gap <= EPS:
                overlap = 0.0
                break
            overlap *= gap
        total += overlap
    return total


def supported_area_ratio(item: AABB, supports: list[AABB]) -> float:
    """Fracción de la cara inferior de ``item`` apoyada sobre otras cajas o suelo.

    Se usa como base para validaciones de estabilidad. Si el ítem está en z=0
    se considera totalmente apoyado en el suelo. En caso contrario, se calcula
    el área de contacto con las caras superiores de las cajas que están justo
    debajo (mismo plano z, con tolerancia EPS).
    """

    base_area = item.dimensions.length * item.dimensions.width
    if base_area <= EPS:
        return 0.0

    item_z = item.min_corner[2]
    if item_z <= EPS:
        return 1.0

    ix0, iy0, _ = item.min_corner
    ix1, iy1, _ = item.max_corner

    covered = 0.0
    for support in supports:
        support_top = support.max_corner[2]
        if abs(support_top - item_z) > EPS:
            continue  # No está justo debajo.
        sx0, sy0, _ = support.min_corner
        sx1, sy1, _ = support.max_corner
        overlap_x = max(0.0, min(ix1, sx1) - max(ix0, sx0))
        overlap_y = max(0.0, min(iy1, sy1) - max(iy0, sy0))
        covered += overlap_x * overlap_y

    return min(1.0, covered / base_area)
