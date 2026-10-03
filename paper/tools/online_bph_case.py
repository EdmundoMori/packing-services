"""Un episodio de OnlineBPH sobre una secuencia finita.

La selección es la de heuristic.OnlineBPH: EMS ordenados por (z, y, x)
y la primera orientación factible. El generador sigue siendo el EMS de ese
repositorio. Esta adaptación solo fija la secuencia, evita el reset final
que borraría la geometría y no inventa ítems intermedios.
"""

from __future__ import annotations

from typing import Any


class FiniteSequenceCreator:
    """Entrega la secuencia de llegada y, al acabarla, un centinela mayor que el contenedor."""

    def __init__(self, boxes: list[tuple[float, float, float]], sentinel: tuple[float, float, float]) -> None:
        self.sequence = [tuple(box) for box in boxes]
        self.sentinel = tuple(sentinel)
        self.box_list: list[tuple[float, float, float]] = []
        self.cursor = 0

    def reset(self) -> None:
        self.box_list.clear()
        self.cursor = 0

    def preview(self, length: int) -> list[tuple[float, float, float]]:
        import copy

        while len(self.box_list) < length:
            self.generate_box_size()
        return copy.deepcopy(self.box_list[:length])

    def drop_box(self) -> None:
        self.box_list.pop(0)

    def generate_box_size(self, **kwargs: Any) -> None:
        del kwargs
        if self.cursor < len(self.sequence):
            self.box_list.append(self.sequence[self.cursor])
        else:
            self.box_list.append(self.sentinel)
        self.cursor += 1


def run_online_bph_episode(
    *,
    repo: str,
    container_lwh: tuple[float, float, float],
    items_lwh: list[tuple[float, float, float]],
) -> dict[str, Any]:
    import sys
    import time
    from pathlib import Path

    root = Path(repo).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    started = time.perf_counter()
    from heuristic import OnlineBPH
    from pct_envs.PctContinuous0 import PackingContinuous

    length, width, height = container_lwh
    sentinel = (length + 1.0, width + 1.0, height + 1.0)
    holder = max(80, len(items_lwh) + 5)
    env = PackingContinuous(
        setting=2,
        container_size=(length, width, height),
        item_set=list(items_lwh) or [(1.0, 1.0, 1.0)],
        internal_node_holder=holder,
        leaf_node_holder=50,
        next_holder=1,
        shuffle=False,
        sample_from_distribution=False,
        load_test_data=False,
    )
    env.box_creator = FiniteSequenceCreator(items_lwh, sentinel)
    env.test = False
    env.sample_from_distribution = False
    real_reset = env.reset
    calls = {"n": 0}

    def guarded_reset():
        calls["n"] += 1
        if calls["n"] == 1:
            return real_reset()
        return None

    env.reset = guarded_reset
    imports_done = time.perf_counter()
    loop_started = time.perf_counter()
    OnlineBPH(env, times=1)
    loop_seconds = time.perf_counter() - loop_started
    placed = []
    for box in env.space.boxes:
        placed.append(
            {
                "oriented_lwh_mm": [float(box.x), float(box.y), float(box.z)],
                "flb_mm": [float(box.lx), float(box.ly), float(box.lz)],
            }
        )
    return {
        "placed": placed,
        "n_input": len(items_lwh),
        "sentinel_lwh_mm": list(sentinel),
        "reset_calls": calls["n"],
        "orientation": int(env.orientation),
        "setting": int(env.setting),
        "holder": holder,
        "generator": "ems_online_bph",
        "packing_loop_seconds": loop_seconds,
        "import_seconds": imports_done - started,
        "physical_stability_verified": None,
    }
