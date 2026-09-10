"""Utilidades de datasets de entrada (BED-BPP y futuros)."""

from .bed_bpp import (
    BED_BPP_COMPATIBLE_PROBLEM_TYPES,
    TARGET_SIZES_MM,
    convert_order_to_benchmark_input,
    convert_order_to_pack_input,
    list_order_ids,
    looks_like_bed_bpp_orders,
    normalize_benchmark_payload,
    normalize_execute_payload,
    smallest_order_id,
)

__all__ = [
    "BED_BPP_COMPATIBLE_PROBLEM_TYPES",
    "TARGET_SIZES_MM",
    "convert_order_to_benchmark_input",
    "convert_order_to_pack_input",
    "list_order_ids",
    "looks_like_bed_bpp_orders",
    "normalize_benchmark_payload",
    "normalize_execute_payload",
    "smallest_order_id",
]
