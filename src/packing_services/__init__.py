"""packing-services: arquitectura modular de servicios de Cutting and Packing.

Expone modelos de dominio, esquemas de entrada/salida, un validador geométrico
propio, un registro homogéneo de algoritmos y una API local (FastAPI).

La versión inicial prioriza heurísticas constructivas 3D-BPP y un validador
propio antes de metaheurísticas, métodos exactos o IA (ver docs/roadmap.md).
"""

__version__ = "0.1.0"
SERVICE_VERSION = __version__
