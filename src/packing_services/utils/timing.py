"""Utilidades de medición de tiempo de ejecución."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass
class Elapsed:
    """Contenedor mutable para exponer el tiempo transcurrido tras el bloque."""

    seconds: float = 0.0


@contextmanager
def measure_time() -> Iterator[Elapsed]:
    """Context manager que mide el tiempo de pared de un bloque.

    Uso::

        with measure_time() as elapsed:
            do_work()
        print(elapsed.seconds)
    """

    elapsed = Elapsed()
    start = time.perf_counter()
    try:
        yield elapsed
    finally:
        elapsed.seconds = time.perf_counter() - start


class Deadline:
    """Límite de tiempo simple para algoritmos que soportan time_limit.

    Un ``time_limit_seconds`` nulo significa "sin límite".
    """

    def __init__(self, time_limit_seconds: float | None) -> None:
        self._limit = time_limit_seconds
        self._start = time.perf_counter()

    def exceeded(self) -> bool:
        if self._limit is None:
            return False
        return (time.perf_counter() - self._start) >= self._limit

    @property
    def remaining(self) -> float | None:
        if self._limit is None:
            return None
        return max(0.0, self._limit - (time.perf_counter() - self._start))
