"""Interfaz común de adaptadores externos.

Un adaptador implementa la misma interfaz que un algoritmo local
(``PackingAlgorithm``), pero su ejecución depende de una dependencia o motor
externo. Si el motor no está disponible, ``run`` lanza ``AdapterUnavailableError``
con instrucciones claras, sin romper el resto del proyecto.
"""

from __future__ import annotations

from abc import abstractmethod

from ..algorithms.base import PackingAlgorithm
from ..algorithms.metadata import AlgorithmMetadata
from ..domain.models import PackingProblem, PackingSolution
from ..utils.errors import AdapterUnavailableError


class ExternalAdapter(PackingAlgorithm):
    """Base para adaptadores a motores externos."""

    metadata: AlgorithmMetadata

    #: Mensaje de instalación/uso mostrado cuando el motor no está disponible.
    unavailable_hint: str = "Motor externo no disponible en este entorno."

    def is_available(self) -> bool:
        """True si el motor externo puede ejecutarse en este entorno.

        Por defecto, los adaptadores son stubs no disponibles. ``py3dbp`` lo
        sobrescribe comprobando el import de la librería.
        """

        return False

    @abstractmethod
    def _run_available(self, problem: PackingProblem) -> PackingSolution:
        """Ejecuta el motor asumiendo que está disponible."""

    def run(self, problem: PackingProblem) -> PackingSolution:
        if not self.is_available():
            raise AdapterUnavailableError(
                f"[{self.metadata.name}] {self.unavailable_hint}"
            )
        return self._run_available(problem)
