"""Esquemas de request de la API (contrato de entrada estandarizado).

El request replica el JSON normalizado descrito en los documentos de contexto.
Incluye utilidades para convertir un ``PackRequest`` en un ``PackingProblem``
interno, expandiendo la cantidad (``quantity``) de cada ítem en unidades
individuales con id único.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..domain.enums import ProblemType
from ..domain.models import (
    AlgorithmConfig,
    Container,
    ConstraintFlags,
    Item,
    PackedItem,
    PackingProblem,
)


class PackRequest(BaseModel):
    """Entrada estandarizada para ejecutar un algoritmo de packing."""

    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType = ProblemType.THREE_D_BPP
    request_id: str | None = None
    containers: list[Container]
    items: list[Item]
    constraints: ConstraintFlags = Field(default_factory=ConstraintFlags)
    objective: str = "maximize_volume_utilization"
    algorithm: AlgorithmConfig

    def expand_items(self) -> list[Item]:
        """Expande ``quantity`` en ítems individuales con id único.

        Si ``quantity == 1`` se conserva el id original. Para cantidades
        mayores se generan ids ``"<id>#<n>"`` (1-indexado) para trazabilidad.
        """

        expanded: list[Item] = []
        for item in self.items:
            if item.quantity == 1:
                expanded.append(item.model_copy(update={"quantity": 1}))
                continue
            for n in range(1, item.quantity + 1):
                expanded.append(
                    item.model_copy(update={"id": f"{item.id}#{n}", "quantity": 1})
                )
        return expanded

    def to_problem(self) -> PackingProblem:
        """Construye la instancia interna normalizada."""

        return PackingProblem(
            problem_type=self.problem_type,
            request_id=self.request_id,
            containers=self.containers,
            items=self.expand_items(),
            constraints=self.constraints,
            objective=self.objective,
            algorithm=self.algorithm,
        )


class ContainerLoadingRequest(BaseModel):
    """Entrada del Container Loading Service.

    Comparte forma con ``PackRequest`` pero el algoritmo es opcional: si no se
    indica, se usa ``weight_aware_container_loading``.
    """

    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType = ProblemType.CONTAINER_LOADING
    request_id: str | None = None
    containers: list[Container]
    items: list[Item]
    constraints: ConstraintFlags = Field(default_factory=ConstraintFlags)
    objective: str = "maximize_volume_utilization"
    algorithm: AlgorithmConfig | None = None

    def to_problem(self) -> PackingProblem:
        algorithm = self.algorithm or AlgorithmConfig(
            name="weight_aware_container_loading"
        )
        expanded: list[Item] = []
        for item in self.items:
            if item.quantity == 1:
                expanded.append(item)
            else:
                for n in range(1, item.quantity + 1):
                    expanded.append(item.model_copy(update={"id": f"{item.id}#{n}"}))
        return PackingProblem(
            problem_type=self.problem_type,
            request_id=self.request_id,
            containers=self.containers,
            items=expanded,
            constraints=self.constraints,
            objective=self.objective,
            algorithm=algorithm,
        )


class PalletizationRequest(BaseModel):
    """Entrada del Palletization Service."""

    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType = ProblemType.PALLETIZATION
    request_id: str | None = None
    containers: list[Container]
    items: list[Item]
    constraints: ConstraintFlags = Field(default_factory=ConstraintFlags)
    objective: str = "maximize_volume_utilization"
    algorithm: AlgorithmConfig | None = None

    def to_problem(self) -> PackingProblem:
        algorithm = self.algorithm or AlgorithmConfig(name="layer_based_palletization")
        expanded: list[Item] = []
        for item in self.items:
            if item.quantity == 1:
                expanded.append(item)
            else:
                for n in range(1, item.quantity + 1):
                    expanded.append(item.model_copy(update={"id": f"{item.id}#{n}"}))
        return PackingProblem(
            problem_type=self.problem_type,
            request_id=self.request_id,
            containers=self.containers,
            items=expanded,
            constraints=self.constraints,
            objective=self.objective,
            algorithm=algorithm,
        )


class StackingAwareRequest(BaseModel):
    """Entrada del Stacking-aware Packing Service."""

    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType = ProblemType.STACKING_AWARE
    request_id: str | None = None
    containers: list[Container]
    items: list[Item]
    constraints: ConstraintFlags = Field(
        default_factory=lambda: ConstraintFlags(
            basic_stability=True,
            load_bearing=True,
        )
    )
    objective: str = "maximize_volume_utilization"
    algorithm: AlgorithmConfig | None = None

    def to_problem(self) -> PackingProblem:
        algorithm = self.algorithm or AlgorithmConfig(
            name="stacking_aware_constructive",
            parameters={"sort_strategy": "weight_desc", "min_support_ratio": 0.6},
        )
        expanded: list[Item] = []
        for item in self.items:
            if item.quantity == 1:
                expanded.append(item)
            else:
                for n in range(1, item.quantity + 1):
                    expanded.append(item.model_copy(update={"id": f"{item.id}#{n}"}))
        return PackingProblem(
            problem_type=self.problem_type,
            request_id=self.request_id,
            containers=self.containers,
            items=expanded,
            constraints=self.constraints,
            objective=self.objective,
            algorithm=algorithm,
        )


class BoxOption(BaseModel):
    """Caja candidata del catálogo de cartonization (con coste opcional)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    max_weight: float | None = Field(default=None, ge=0)
    cost: float | None = Field(default=None, ge=0)

    def to_container(self) -> Container:
        return Container(
            id=self.id,
            length=self.length,
            width=self.width,
            height=self.height,
            max_weight=self.max_weight,
        )


class CartonizationRequest(BaseModel):
    """Entrada del Cartonization Service: un pedido + catálogo de cajas."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    items: list[Item]
    boxes: list[BoxOption] = Field(min_length=1)
    constraints: ConstraintFlags = Field(default_factory=ConstraintFlags)
    algorithm: AlgorithmConfig | None = None

    def to_problem(self) -> PackingProblem:
        algorithm = self.algorithm or AlgorithmConfig(name="smallest_feasible_box")
        expanded: list[Item] = []
        for item in self.items:
            if item.quantity == 1:
                expanded.append(item)
            else:
                for n in range(1, item.quantity + 1):
                    expanded.append(item.model_copy(update={"id": f"{item.id}#{n}"}))
        return PackingProblem(
            problem_type=ProblemType.CARTONIZATION,
            request_id=self.request_id,
            containers=[b.to_container() for b in self.boxes],
            items=expanded,
            constraints=self.constraints,
            objective="maximize_volume_utilization",
            algorithm=algorithm,
        )


class ValidateRequest(BaseModel):
    """Entrada para validar una solución generada por cualquier motor."""

    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType = ProblemType.THREE_D_BPP
    request_id: str | None = None
    containers: list[Container]
    items: list[Item]
    constraints: ConstraintFlags = Field(default_factory=ConstraintFlags)
    packed_items: list[PackedItem]

    def expanded_items(self) -> list[Item]:
        """Ítems expandidos por cantidad, coherente con ``PackRequest``."""

        expanded: list[Item] = []
        for item in self.items:
            if item.quantity == 1:
                expanded.append(item)
                continue
            for n in range(1, item.quantity + 1):
                expanded.append(item.model_copy(update={"id": f"{item.id}#{n}"}))
        return expanded


class BenchmarkEngineConfig(BaseModel):
    """Configuración de un motor/algoritmo dentro de un benchmark."""

    model_config = ConfigDict(extra="forbid")

    name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None
    time_limit_seconds: float | None = Field(default=None, gt=0)

    def to_algorithm_config(self) -> AlgorithmConfig:
        return AlgorithmConfig(
            name=self.name,
            parameters=self.parameters,
            random_seed=self.random_seed,
            time_limit_seconds=self.time_limit_seconds,
        )


class BenchmarkRequest(BaseModel):
    """Entrada para comparar varios algoritmos sobre una misma instancia.

    Grupos soportados por ``problem_type``:

    - ``3D_BPP``: ``containers`` + ``items`` + ``engines``
    - ``CONTAINER_LOADING``: ``containers`` + ``items`` + ``engines``
    - ``CARTONIZATION``: ``items`` + ``boxes`` + ``engines`` (o ``profile``)
    - ``SINGLE_CONTAINER_LOADING``: un contenedor + ``items`` + ``engines`` (o ``profile``)

    Si se indica ``profile``, se resuelve el conjunto estándar de motores comparables.
    Los ``engines`` explícitos tienen prioridad sobre ``profile``.
    """

    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType = ProblemType.THREE_D_BPP
    request_id: str | None = None
    profile: str | None = None
    containers: list[Container] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)
    boxes: list[BoxOption] = Field(default_factory=list)
    constraints: ConstraintFlags = Field(default_factory=ConstraintFlags)
    objective: str = "maximize_volume_utilization"
    engines: list[BenchmarkEngineConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def resolve_profile_and_validate(self) -> BenchmarkRequest:
        from ..benchmark.profiles import resolve_profile_engines

        if not self.engines:
            if not self.profile:
                raise ValueError(
                    "Benchmark requiere 'engines' (≥2 motores) o 'profile' estándar"
                )
            object.__setattr__(
                self,
                "engines",
                resolve_profile_engines(self.problem_type, self.profile),
            )
        if len(self.engines) < 2:
            raise ValueError("Benchmark requiere al menos 2 motores en 'engines'")

        if self.problem_type == ProblemType.CARTONIZATION:
            if not self.boxes:
                raise ValueError("CARTONIZATION benchmark requiere 'boxes'")
            if not self.items:
                raise ValueError("CARTONIZATION benchmark requiere 'items'")
        else:
            if not self.containers:
                raise ValueError(
                    f"{self.problem_type.value} benchmark requiere 'containers'"
                )
            if not self.items:
                raise ValueError(f"{self.problem_type.value} benchmark requiere 'items'")
        return self

    def _expand_items(self) -> list[Item]:
        expanded: list[Item] = []
        for item in self.items:
            if item.quantity == 1:
                expanded.append(item)
            else:
                for n in range(1, item.quantity + 1):
                    expanded.append(item.model_copy(update={"id": f"{item.id}#{n}"}))
        return expanded

    def to_problem(self, engine: BenchmarkEngineConfig) -> PackingProblem:
        """Construye una instancia interna para un motor concreto (packing/CL)."""

        return PackingProblem(
            problem_type=self.problem_type,
            request_id=self.request_id,
            containers=self.containers,
            items=self._expand_items(),
            constraints=self.constraints,
            objective=self.objective,
            algorithm=engine.to_algorithm_config(),
        )

    def to_cartonization_request(self, engine: BenchmarkEngineConfig) -> CartonizationRequest:
        return CartonizationRequest(
            request_id=self.request_id,
            items=self.items,
            boxes=self.boxes,
            constraints=self.constraints,
            algorithm=engine.to_algorithm_config(),
        )

    def to_container_loading_request(
        self, engine: BenchmarkEngineConfig
    ) -> ContainerLoadingRequest:
        return ContainerLoadingRequest(
            problem_type=ProblemType.CONTAINER_LOADING,
            request_id=self.request_id,
            containers=self.containers,
            items=self.items,
            constraints=self.constraints,
            objective=self.objective,
            algorithm=engine.to_algorithm_config(),
        )


class PackAlgorithmInput(BaseModel):
    """Entrada normalizada para ejecutar un algoritmo de packing vía URL.

    El nombre del algoritmo va en el path (``/algorithms/{name}/execute``).
    Si el algoritmo admite varios ``problem_type``, el campo ``problem_type`` es
    obligatorio (estrategia A3).
    """

    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType | None = None
    request_id: str | None = None
    containers: list[Container]
    items: list[Item]
    constraints: ConstraintFlags = Field(default_factory=ConstraintFlags)
    objective: str = "maximize_volume_utilization"
    parameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None
    time_limit_seconds: float | None = Field(default=None, gt=0)

    def resolve_problem_type(self, allowed: list[ProblemType]) -> ProblemType:
        if self.problem_type is not None:
            if self.problem_type not in allowed:
                allowed_values = ", ".join(p.value for p in allowed)
                raise ValueError(
                    f"problem_type={self.problem_type.value} no es compatible con "
                    f"este algoritmo. Valores permitidos: {allowed_values}"
                )
            return self.problem_type
        if len(allowed) == 1:
            return allowed[0]
        allowed_values = ", ".join(p.value for p in allowed)
        raise ValueError(
            f"El campo 'problem_type' es obligatorio para este algoritmo. "
            f"Valores permitidos: {allowed_values}"
        )

    def to_pack_request(self, algorithm_name: str, allowed: list[ProblemType]) -> PackRequest:
        return PackRequest(
            problem_type=self.resolve_problem_type(allowed),
            request_id=self.request_id,
            containers=self.containers,
            items=self.items,
            constraints=self.constraints,
            objective=self.objective,
            algorithm=AlgorithmConfig(
                name=algorithm_name,
                parameters=self.parameters,
                random_seed=self.random_seed,
                time_limit_seconds=self.time_limit_seconds,
            ),
        )


class CartonizationAlgorithmInput(BaseModel):
    """Entrada normalizada para algoritmos de cartonization vía URL."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    items: list[Item]
    boxes: list[BoxOption] = Field(min_length=1)
    constraints: ConstraintFlags = Field(default_factory=ConstraintFlags)
    parameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None
    time_limit_seconds: float | None = Field(default=None, gt=0)

    def to_cartonization_request(self, algorithm_name: str) -> CartonizationRequest:
        return CartonizationRequest(
            request_id=self.request_id,
            items=self.items,
            boxes=self.boxes,
            constraints=self.constraints,
            algorithm=AlgorithmConfig(
                name=algorithm_name,
                parameters=self.parameters,
                random_seed=self.random_seed,
                time_limit_seconds=self.time_limit_seconds,
            ),
        )
