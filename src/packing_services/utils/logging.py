"""Configuración de logging estándar y simple.

Se usa el módulo ``logging`` de la librería estándar para no añadir
dependencias. Cada módulo obtiene su logger con ``get_logger(__name__)``.
"""

from __future__ import annotations

import logging
import os

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Configura el logging raíz una sola vez.

    El nivel puede fijarse por argumento o vía la variable de entorno
    ``PACKING_LOG_LEVEL`` (por defecto INFO).
    """

    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = (level or os.getenv("PACKING_LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger configurado para el módulo indicado."""

    configure_logging()
    return logging.getLogger(name)
