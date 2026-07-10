"""Tests del servicio de preparación para espacio de datos."""

from __future__ import annotations

from packing_services.services.dataspace_service import DataspaceService


def test_catalog_lists_operational_services():
    catalog = DataspaceService().catalog()
    names = [s.service_name for s in catalog.services]
    assert "3D Bin Packing Offline Service" in names
    assert "Container Loading Service" in names
    assert "Cartonization Service" in names
    assert "Packing Validation Service" in names
    assert "Packing Benchmark / Comparison Service" in names
    assert catalog.dataspace_ready is True


def test_descriptors_have_publication_fields():
    catalog = DataspaceService().catalog()
    for svc in catalog.services:
        assert svc.execution_endpoint
        assert svc.validation_endpoint
        assert svc.metadata_endpoint
        assert svc.metrics
        assert svc.traceability
        assert svc.input_schema and svc.output_schema


def test_packing_service_lists_implemented_algorithms():
    catalog = DataspaceService().catalog()
    bpp = next(s for s in catalog.services if s.problem_type == "3D_BPP")
    assert "heuristic_3d_bpp_v1" in bpp.algorithms
    assert "extreme_points_3d" in bpp.algorithms
