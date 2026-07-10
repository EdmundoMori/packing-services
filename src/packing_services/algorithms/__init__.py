"""Algoritmos de packing, metadata y registro homogéneo.

Importar este paquete registra automáticamente el catálogo completo de
algoritmos (implementados, adaptadores, stubs y futuros) en el
``default_registry``.
"""

from .registry import AlgorithmRegistry, default_registry, get_default_registry

__all__ = ["AlgorithmRegistry", "default_registry", "get_default_registry"]
