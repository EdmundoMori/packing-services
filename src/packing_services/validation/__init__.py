"""Validador geométrico propio y tipos de violación."""

from .validator import PackingValidator
from .violations import ViolationType

__all__ = ["PackingValidator", "ViolationType"]
