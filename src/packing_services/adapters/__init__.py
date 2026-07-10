"""Adaptadores a motores open source externos.

Estrategia (según el análisis de repositorios): NO se modifican los repositorios
originales. Cada adaptador traduce la entrada normalizada al formato del motor,
ejecuta el motor y traduce la salida de vuelta al formato normalizado
comparable.

En esta versión solo ``py3dbp_adapter`` puede ser realmente ejecutable (si la
librería está instalada). El resto son stubs documentados que declaran su
metadata y explican cómo se integrarán, sin afirmar que ya funcionan.
"""

from __future__ import annotations

from .base import ExternalAdapter
from .boxpacker_adapter import BoxPackerAdapter
from .container_packing_adapter import ContainerPackingAdapter
from .dwave_adapter import DWaveAdapter
from .packingsolver_adapter import PackingSolverAdapter
from .py3dbp_adapter import Py3dbpAdapter
from .skjolber_adapter import SkjolberAdapter


def build_adapters() -> list[ExternalAdapter]:
    """Devuelve las instancias de todos los adaptadores conocidos."""

    return [
        Py3dbpAdapter(),
        SkjolberAdapter(),
        BoxPackerAdapter(),
        ContainerPackingAdapter(),
        PackingSolverAdapter(),
        DWaveAdapter(),
    ]


__all__ = [
    "ExternalAdapter",
    "Py3dbpAdapter",
    "SkjolberAdapter",
    "BoxPackerAdapter",
    "ContainerPackingAdapter",
    "PackingSolverAdapter",
    "DWaveAdapter",
    "build_adapters",
]
