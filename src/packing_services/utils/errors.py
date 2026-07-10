"""Jerarquía de errores del dominio.

Se separan los errores de negocio (entrada inválida, algoritmo inexistente,
dependencia externa ausente) para que la API pueda mapearlos a códigos HTTP
claros sin filtrar trazas internas.
"""

from __future__ import annotations


class PackingError(Exception):
    """Error base del proyecto."""


class InvalidInputError(PackingError):
    """La entrada es sintáctica o semánticamente inválida (HTTP 422)."""


class AlgorithmNotFoundError(PackingError):
    """No existe un algoritmo con el nombre solicitado (HTTP 404)."""


class AlgorithmNotExecutableError(PackingError):
    """El algoritmo existe pero no es ejecutable (stub/future) (HTTP 400)."""


class AdapterUnavailableError(PackingError):
    """Un adaptador externo no tiene su dependencia/motor disponible (HTTP 503).

    Debe incluir instrucciones claras de instalación o configuración.
    """


class ExecutionError(PackingError):
    """Fallo inesperado durante la ejecución de un algoritmo (HTTP 500)."""
