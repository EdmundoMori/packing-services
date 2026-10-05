"""Escritura JSON atómica y helpers de integridad operativa.

No cambia fórmulas, muestras ni presupuesto. No garantiza durabilidad
absoluta: SIGKILL y fallos de almacenamiento pueden truncar el proceso
antes del reemplazo atómico.
"""

from __future__ import annotations

import json
import os
import signal
import tempfile
from pathlib import Path
from typing import Any, Callable


class AtomicWriteError(RuntimeError):
    """Fallo al persistir o validar un JSON."""


def validate_json_bytes(raw: bytes) -> Any:
    if not raw.strip():
        raise AtomicWriteError("JSON vacío")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AtomicWriteError(f"JSON ilegible: {exc}") from exc


def read_json_strict(path: Path) -> Any:
    if not path.is_file():
        raise AtomicWriteError(f"ausente: {path}")
    return validate_json_bytes(path.read_bytes())


def atomic_write_json(path: Path, payload: Any, *, indent: int | None = 2) -> None:
    """Escribe JSON en un temporal del mismo directorio, valida y reemplaza.

    Orden: mkdir → temp en el mismo dir → write+flush+fsync → validar bytes
    → os.replace → fsync del directorio cuando sea posible.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=indent, ensure_ascii=False)
    if indent is not None:
        text += "\n"
    data = text.encode("utf-8")
    # Validación previa del payload serializado
    validate_json_bytes(data)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        # Releer y validar antes del reemplazo
        validate_json_bytes(tmp_path.read_bytes())
        os.replace(tmp_path, path)
        tmp_path = Path()  # replaced; avoid double unlink
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            # Algunos FS no permiten fsync de directorio; no es fallo fatal.
            pass
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def install_termination_flags(flag: dict[str, bool]) -> list[Any]:
    """Instala manejadores para SIGTERM/SIGINT que marcan flag['stop']=True.

    SIGKILL y SIGSTOP no pueden capturarse. Devuelve handlers previos para restaurar.
    """

    previous: list[tuple[Any, Any]] = []

    def _handler(signum: int, _frame: Any) -> None:
        flag["stop"] = True
        flag["signal"] = int(signum)

    for sig in (signal.SIGTERM, signal.SIGINT):
        previous.append((sig, signal.getsignal(sig)))
        signal.signal(sig, _handler)
    return previous


def restore_signal_handlers(previous: list[tuple[Any, Any]]) -> None:
    for sig, handler in previous:
        signal.signal(sig, handler)
