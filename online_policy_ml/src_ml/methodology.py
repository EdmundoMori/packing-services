"""Compuertas metodológicas del pipeline P2O.

Este módulo no entrena. Solo impide que un error de diseño (fuga de objetivo,
solape de splits, uso del holdout para tunear, features constantes o
colineales sin diagnóstico, sobreajuste sin validación) llegue a
``fit_*`` o a una promoción.

Las comprobaciones son deterministas y no dependen de ejecutar el bucle online.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from math import comb

from packing_services.online.features import FEATURE_NAMES

from config import (
    COLLINEARITY_CORR_THRESHOLD,
    CONSTANT_FEATURE_STD,
    OVERFIT_ACC_GAP_MAX,
    TRAINABLE_TEACHERS,
)
from paths import HOLDOUT_DIR, ORDER_IDS_NAME, SPLITS_DIR

# Pares estructuralmente redundantes en encoder v1 (best_fit):
# rank_1..3 son z, y, x en mm; pos_*_n son las mismas coordenadas normalizadas.
STRUCTURAL_COLLINEAR_PAIRS: tuple[tuple[str, str], ...] = (
    ("pos_z_n", "rank_1"),
    ("pos_y_n", "rank_2"),
    ("pos_x_n", "rank_3"),
)


class MethodologyError(AssertionError):
    """El pipeline no cumple un requisito metodológico."""


class TautologicalTeacherError(AssertionError):
    """El maestro no aporta información más allá de los features."""


# Features que componen la clave cerrada de privileged_volume_ep.
_IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}
I_VOL = _IDX["item_vol_n"]
I_BUF = _IDX["buffer_index_n"]
I_RANKS = tuple(_IDX[f"rank_{k}"] for k in range(4))
CLOSED_FORM_FEATURES: tuple[str, ...] = (
    "item_vol_n",
    "rank_0",
    "rank_1",
    "rank_2",
    "rank_3",
    "buffer_index_n",
)
TAUTOLOGY_THRESHOLD = 0.98


def _as_matrix(transition: dict[str, Any]) -> np.ndarray:
    return np.asarray(transition["features"], dtype=np.float64)


def closed_form_index(features: np.ndarray) -> int:
    """argmin de (−item_vol_n, rank_0..3, buffer_index_n) usando solo features."""

    best = 0
    best_key: tuple | None = None
    for row in range(features.shape[0]):
        key = (
            -features[row, I_VOL],
            features[row, I_RANKS[0]],
            features[row, I_RANKS[1]],
            features[row, I_RANKS[2]],
            features[row, I_RANKS[3]],
            features[row, I_BUF],
        )
        if best_key is None or key < best_key:
            best_key = key
            best = row
    return best


def closed_form_rate(
    transitions: Sequence[dict[str, Any]],
    *,
    exclude_trivial: bool = True,
) -> dict[str, Any]:
    hits = total = trivial = 0
    for tr in transitions:
        features = _as_matrix(tr)
        if features.shape[0] <= 1:
            trivial += 1
            if exclude_trivial:
                continue
        hits += int(closed_form_index(features) == int(tr["label"]))
        total += 1
    return {
        "rate": float(hits) / total if total else 0.0,
        "hits": int(hits),
        "evaluated": int(total),
        "trivial_steps": int(trivial),
        "excluded_trivial": bool(exclude_trivial),
    }


def single_feature_rates(
    transitions: Sequence[dict[str, Any]],
    *,
    exclude_trivial: bool = True,
) -> list[dict[str, Any]]:
    n_feat = len(FEATURE_NAMES)
    lo = np.zeros(n_feat, dtype=np.int64)
    hi = np.zeros(n_feat, dtype=np.int64)
    total = 0
    for tr in transitions:
        features = _as_matrix(tr)
        if exclude_trivial and features.shape[0] <= 1:
            continue
        label = int(tr["label"])
        lo += (np.argmin(features, axis=0) == label).astype(np.int64)
        hi += (np.argmax(features, axis=0) == label).astype(np.int64)
        total += 1
    rows: list[dict[str, Any]] = []
    for i, name in enumerate(FEATURE_NAMES):
        r_lo = float(lo[i]) / total if total else 0.0
        r_hi = float(hi[i]) / total if total else 0.0
        rows.append(
            {
                "feature": name,
                "rate": float(max(r_lo, r_hi)),
                "direction": "argmin" if r_lo >= r_hi else "argmax",
                "rate_argmin": r_lo,
                "rate_argmax": r_hi,
                "evaluated": int(total),
            }
        )
    rows.sort(key=lambda row: -row["rate"])
    return rows


def audit_transitions(
    payload: dict[str, Any],
    *,
    label: str = "",
    exclude_trivial: bool = True,
) -> dict[str, Any]:
    transitions = payload["transitions"]
    closed = closed_form_rate(transitions, exclude_trivial=exclude_trivial)
    per_feature = single_feature_rates(transitions, exclude_trivial=exclude_trivial)
    worst = per_feature[0] if per_feature else {"feature": None, "rate": 0.0}
    ks = [len(tr["features"]) for tr in transitions]
    return {
        "label": label,
        "teacher": payload.get("teacher"),
        "feature_version": payload.get("feature_version"),
        "n_transitions": len(transitions),
        "k_mean": float(np.mean(ks)) if ks else 0.0,
        "k_min": int(np.min(ks)) if ks else 0,
        "k_max": int(np.max(ks)) if ks else 0,
        "closed_form_rate": float(closed["rate"]),
        "closed_form_evaluated": int(closed["evaluated"]),
        "trivial_steps": int(closed["trivial_steps"]),
        "worst_single_feature": worst["feature"],
        "worst_single_rate": float(worst["rate"]),
        "is_tautological": bool(
            closed["rate"] >= TAUTOLOGY_THRESHOLD
            or worst["rate"] >= TAUTOLOGY_THRESHOLD
        ),
        "top_features": per_feature[:5],
    }


def assert_informative(
    payload: dict[str, Any],
    *,
    threshold: float = TAUTOLOGY_THRESHOLD,
    label: str = "",
) -> dict[str, Any]:
    report = audit_transitions(payload, label=label)
    if report["is_tautological"]:
        raise TautologicalTeacherError(
            f"maestro tautológico en {label or 'transiciones'}: "
            f"la regla cerrada recupera {report['closed_form_rate']:.2%} de las etiquetas "
            f"y el feature '{report['worst_single_feature']}' por sí solo "
            f"{report['worst_single_rate']:.2%} (umbral {threshold:.0%})."
        )
    return report


def lift_over_closed_form(model_accuracy: float, closed_form_accuracy: float) -> float:
    return float(model_accuracy) - float(closed_form_accuracy)


def paired_deltas(
    rows_a: Sequence[dict[str, Any]],
    rows_b: Sequence[dict[str, Any]],
    *,
    key: str = "volume_utilization",
    by: str = "order_id",
) -> tuple[np.ndarray, list[str]]:
    map_a = {row[by]: row for row in rows_a}
    map_b = {row[by]: row for row in rows_b}
    shared = sorted(set(map_a) & set(map_b))
    deltas = np.array(
        [float(map_a[k][key]) - float(map_b[k][key]) for k in shared],
        dtype=np.float64,
    )
    return deltas, shared


def bootstrap_ci(
    values: Sequence[float] | np.ndarray,
    *,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, float]:
    data = np.asarray(values, dtype=np.float64)
    n = data.size
    if n == 0:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0, "n": 0}
    if n == 1:
        v = float(data[0])
        return {"mean": v, "lo": v, "hi": v, "n": 1}
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n, size=(n_boot, n))
    means = data[draws].mean(axis=1)
    return {
        "mean": float(data.mean()),
        "lo": float(np.percentile(means, 100 * alpha / 2)),
        "hi": float(np.percentile(means, 100 * (1 - alpha / 2))),
        "n": int(n),
    }


def sign_test(deltas: Sequence[float] | np.ndarray, *, tol: float = 1e-12) -> dict[str, Any]:
    data = np.asarray(deltas, dtype=np.float64)
    wins = int(np.sum(data > tol))
    losses = int(np.sum(data < -tol))
    ties = int(data.size - wins - losses)
    n = wins + losses
    if n == 0:
        return {"wins": wins, "losses": losses, "ties": ties, "p_value": 1.0}
    k = min(wins, losses)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2**n)
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "p_value": float(min(1.0, 2 * tail)),
    }


def compare_paired(
    rows_a: Sequence[dict[str, Any]],
    rows_b: Sequence[dict[str, Any]],
    *,
    label_a: str = "A",
    label_b: str = "B",
    key: str = "volume_utilization",
    by: str = "order_id",
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, Any]:
    deltas, shared = paired_deltas(rows_a, rows_b, key=key, by=by)
    ci = bootstrap_ci(deltas, n_boot=n_boot, alpha=alpha, seed=seed)
    signs = sign_test(deltas)
    significant = bool(deltas.size and (ci["lo"] > 0.0 or ci["hi"] < 0.0))
    return {
        "label_a": label_a,
        "label_b": label_b,
        "metric": key,
        "n_paired": len(shared),
        "mean_a": float(np.mean([float(r[key]) for r in rows_a])) if rows_a else 0.0,
        "mean_b": float(np.mean([float(r[key]) for r in rows_b])) if rows_b else 0.0,
        "mean_delta": ci["mean"],
        "ci_lo": ci["lo"],
        "ci_hi": ci["hi"],
        "alpha": alpha,
        "significant": significant,
        "wins": signs["wins"],
        "losses": signs["losses"],
        "ties": signs["ties"],
        "p_value": signs["p_value"],
        "order_ids": shared,
    }


def verdict(comparison: dict[str, Any]) -> str:
    d = comparison
    direction = "mejor" if d["mean_delta"] > 0 else "peor"
    if not d["significant"]:
        return (
            f"{d['label_a']} vs {d['label_b']}: diferencia {d['mean_delta']:+.4f} "
            f"(IC95 {d['ci_lo']:+.4f} a {d['ci_hi']:+.4f}, n={d['n_paired']}) — "
            "NO significativa."
        )
    return (
        f"{d['label_a']} vs {d['label_b']}: {direction} en {abs(d['mean_delta']):.4f} "
        f"(IC95 {d['ci_lo']:+.4f} a {d['ci_hi']:+.4f}, n={d['n_paired']}, "
        f"p={d['p_value']:.4f}) — significativa."
    )


def load_holdout_ids(path: Path | None = None) -> frozenset[str]:
    target = path or (HOLDOUT_DIR / ORDER_IDS_NAME)
    if target.is_file():
        import json

        payload = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return frozenset(str(x) for x in payload)
        if isinstance(payload, dict) and "order_ids" in payload:
            return frozenset(str(x) for x in payload["order_ids"])
    blocked = SPLITS_DIR / "blocked_demo_ids.json"
    if blocked.is_file():
        import json

        payload = json.loads(blocked.read_text(encoding="utf-8"))
        return frozenset(str(x) for x in payload.get("order_ids", []))
    return frozenset()


def assert_holdout_excluded(
    order_ids: Iterable[str],
    *,
    role: str,
    holdout_ids: Iterable[str] | None = None,
) -> None:
    """El holdout de producto no puede entrar en train, val, test ni en el tuneo."""

    blocked = set(holdout_ids) if holdout_ids is not None else set(load_holdout_ids())
    leak = sorted(set(str(x) for x in order_ids) & blocked)
    if leak:
        raise MethodologyError(
            f"{role}: el holdout de producto aparece en este conjunto: {leak}. "
            "Esos cinco pedidos son evaluación fuera de muestra y no se usan "
            "para entrenar, validar, elegir epoch ni promocionar."
        )


def assert_disjoint_splits(splits: Mapping[str, Sequence[str]]) -> None:
    names = [name for name in ("train", "val", "test") if name in splits]
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            overlap = sorted(set(splits[a]) & set(splits[b]))
            if overlap:
                raise MethodologyError(
                    f"solape {a}/{b}: {len(overlap)} pedidos ({overlap[:5]}). "
                    "Train, val y test deben ser disjuntos por order_id."
                )


def assert_split_integrity(
    splits: Mapping[str, Sequence[str]],
    *,
    blocked: Iterable[str],
    orders: Mapping[str, Any] | None = None,
) -> None:
    blocked_set = set(blocked)
    for name, ids in splits.items():
        leak = sorted(set(ids) & blocked_set)
        if leak:
            raise MethodologyError(f"fuga del holdout en {name}: {leak}")
        if orders is not None:
            missing = [oid for oid in ids if oid not in orders]
            if missing:
                raise MethodologyError(f"{name}: order_id ausente: {missing[:5]}")
        if len(ids) != len(set(ids)):
            raise MethodologyError(f"{name}: hay order_id duplicados")
    assert_disjoint_splits(splits)
    for required in ("train", "val", "test"):
        if required not in splits or not splits[required]:
            raise MethodologyError(
                f"falta el split '{required}'. Sin val no hay early stopping; "
                "sin test no hay evaluación fuera de la muestra de ajuste."
            )


def assert_trainable_teacher(teacher: str, *, allow_diagnostic: bool = False) -> None:
    if allow_diagnostic:
        return
    if teacher not in TRAINABLE_TEACHERS:
        raise MethodologyError(
            f"maestro '{teacher}' no es entrenable. Los maestros permitidos "
            f"son {sorted(TRAINABLE_TEACHERS)}. privileged_volume_ep es "
            "tautológico respecto al encoder v1: la etiqueta se recupera al "
            "100 % con 6 features. Úsalo solo con allow_diagnostic=True."
        )


def assert_trainable_transitions(
    transitions: Sequence[dict[str, Any]],
    *,
    label: str = "train",
    threshold: float = TAUTOLOGY_THRESHOLD,
) -> dict[str, Any]:
    """Rechaza entrenar si la etiqueta es una función cerrada de los features."""

    if not transitions:
        raise MethodologyError(f"{label}: no hay transiciones")
    closed = closed_form_rate(transitions)
    if closed["rate"] >= threshold:
        raise TautologicalTeacherError(
            f"{label}: la regla cerrada recupera {closed['rate']:.2%} de las "
            f"etiquetas ({closed['hits']}/{closed['evaluated']}). Entrenar "
            "aquí no aprende a empaquetar: copia una ordenación lexicográfica."
        )
    return closed


def assert_collectable(
    order_ids: Sequence[str],
    *,
    teacher: str,
    allow_diagnostic: bool = False,
    holdout_ids: Iterable[str] | None = None,
) -> None:
    assert_trainable_teacher(teacher, allow_diagnostic=allow_diagnostic)
    assert_holdout_excluded(order_ids, role="collect", holdout_ids=holdout_ids)


def _stack_options(transitions: Sequence[dict[str, Any]]) -> np.ndarray:
    blocks = [np.asarray(tr["features"], dtype=np.float64) for tr in transitions]
    if not blocks:
        return np.zeros((0, len(FEATURE_NAMES)))
    return np.concatenate(blocks, axis=0)


def diagnose_constant_features(
    transitions: Sequence[dict[str, Any]],
    *,
    std_eps: float = CONSTANT_FEATURE_STD,
) -> list[dict[str, Any]]:
    """Features con varianza ~0: el modelo les asigna peso de ruido."""

    matrix = _stack_options(transitions)
    if matrix.size == 0:
        return []
    stds = matrix.std(axis=0)
    rows: list[dict[str, Any]] = []
    for i, name in enumerate(FEATURE_NAMES):
        if float(stds[i]) <= std_eps:
            rows.append(
                {
                    "feature": name,
                    "std": float(stds[i]),
                    "mean": float(matrix[:, i].mean()),
                    "note": (
                        "constante en este conjunto; no aporta señal y su peso "
                        "queda sin identificar (p. ej. bin_index_n con un contenedor)"
                    ),
                }
            )
    return rows


def diagnose_collinearity(
    transitions: Sequence[dict[str, Any]],
    *,
    threshold: float = COLLINEARITY_CORR_THRESHOLD,
) -> dict[str, Any]:
    """Correlación de Pearson entre pares de features.

    No elimina features (el encoder v1 es contrato de producción). Devuelve los
    pares por encima del umbral y marca los pares estructuralmente redundantes
    del encoder (posición vs rank_key).
    """

    matrix = _stack_options(transitions)
    n_feat = len(FEATURE_NAMES)
    if matrix.shape[0] < 3:
        return {"pairs": [], "structural_confirmed": [], "n_rows": int(matrix.shape[0])}

    stds = matrix.std(axis=0)
    usable = stds > CONSTANT_FEATURE_STD
    corr = np.full((n_feat, n_feat), np.nan)
    idx = np.where(usable)[0]
    if idx.size >= 2:
        sub = np.corrcoef(matrix[:, idx], rowvar=False)
        for a, i in enumerate(idx):
            for b, j in enumerate(idx):
                corr[i, j] = sub[a, b]

    pairs: list[dict[str, Any]] = []
    for i in range(n_feat):
        for j in range(i + 1, n_feat):
            value = corr[i, j]
            if np.isnan(value):
                continue
            if abs(float(value)) >= threshold:
                left, right = FEATURE_NAMES[i], FEATURE_NAMES[j]
                pairs.append(
                    {
                        "a": left,
                        "b": right,
                        "corr": float(value),
                        "structural": (left, right) in STRUCTURAL_COLLINEAR_PAIRS
                        or (right, left) in STRUCTURAL_COLLINEAR_PAIRS,
                    }
                )
    pairs.sort(key=lambda row: -abs(row["corr"]))

    structural_confirmed: list[dict[str, Any]] = []
    name_index = {name: i for i, name in enumerate(FEATURE_NAMES)}
    for a, b in STRUCTURAL_COLLINEAR_PAIRS:
        value = corr[name_index[a], name_index[b]]
        structural_confirmed.append(
            {
                "a": a,
                "b": b,
                "corr": None if np.isnan(value) else float(value),
            }
        )

    return {
        "pairs": pairs,
        "structural_confirmed": structural_confirmed,
        "n_rows": int(matrix.shape[0]),
        "threshold": threshold,
        "n_flagged": len(pairs),
    }


def diagnose_overfit(
    train_acc: float,
    val_acc: float,
    *,
    max_gap: float = OVERFIT_ACC_GAP_MAX,
) -> dict[str, Any]:
    """Hueco train−val de imitación. No promociona; solo avisa o corta."""

    gap = float(train_acc) - float(val_acc)
    return {
        "train_acc": float(train_acc),
        "val_acc": float(val_acc),
        "gap": gap,
        "max_gap": max_gap,
        "overfit": gap > max_gap,
    }


def assert_no_overfit(train_acc: float, val_acc: float, *, label: str = "") -> dict[str, Any]:
    report = diagnose_overfit(train_acc, val_acc)
    if report["overfit"]:
        raise MethodologyError(
            f"{label or 'modelo'}: hueco train−val = {report['gap']:.3f} "
            f"(train {report['train_acc']:.3f}, val {report['val_acc']:.3f}). "
            f"Supera {report['max_gap']:.2f}: el modelo memoriza el train."
        )
    return report


def accuracy_by_order(transitions: Sequence[dict[str, Any]], predict) -> dict[str, Any]:
    """Exactitud macro por pedido.

    Los pasos de un mismo pedido no son i.i.d.; la exactitud por transición
    infla el tamaño muestral efectivo.
    """

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tr in transitions:
        grouped[str(tr.get("order_id") or "_")].append(tr)
    per_order: list[float] = []
    for rows in grouped.values():
        ok = sum(int(predict(tr) == int(tr["label"])) for tr in rows)
        per_order.append(ok / max(len(rows), 1))
    return {
        "n_orders": len(per_order),
        "n_transitions": len(transitions),
        "micro": (
            sum(int(predict(tr) == int(tr["label"])) for tr in transitions)
            / max(len(transitions), 1)
        ),
        "macro_by_order": float(np.mean(per_order)) if per_order else 0.0,
    }


def assert_selection_split(order_ids: Iterable[str], *, role: str = "model_selection") -> None:
    """Val es el único split que puede elegir epoch o hiperparámetros."""

    assert_holdout_excluded(order_ids, role=role)
    if role == "model_selection":
        test_file = SPLITS_DIR / "working_split.json"
        scale_file = SPLITS_DIR / "scale_split.json"
        import json

        test_ids: set[str] = set()
        for path in (test_file, scale_file):
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            test_ids.update(str(x) for x in payload.get("test", []))
        leak = sorted(set(str(x) for x in order_ids) & test_ids)
        if leak:
            raise MethodologyError(
                f"{role}: se están usando {len(leak)} pedidos de test para "
                "elegir el epoch. Test es evaluación fuera de muestra; el "
                "ajuste se hace solo en val."
            )


GATE_DISTILL = "distill"
GATE_PPO = "ppo"


def interpret_teacher_gate(
    teacher_rows: Sequence[dict[str, Any]],
    heuristic_rows: Sequence[dict[str, Any]],
    mlp_rows: Sequence[dict[str, Any]] | None = None,
    *,
    key: str = "volume_utilization",
) -> dict[str, Any]:
    """Compuerta previa al PPO: ¿el maestro RH es un profesor mejor que imitar?

    * Si el maestro gana al heurístico con IC que excluye el cero → más
      destilación (más pedidos RH o DAgger). PPO todavía no.
    * Si empatan o el maestro pierde → no hay profesor mejor: el siguiente
      paso justificado es fine-tuning PPO del MLP actual.
    """

    vs_heuristic = compare_paired(
        teacher_rows,
        heuristic_rows,
        label_a="teacher",
        label_b="heuristic",
        key=key,
    )
    vs_mlp = None
    if mlp_rows:
        vs_mlp = compare_paired(
            teacher_rows,
            mlp_rows,
            label_a="teacher",
            label_b="mlp",
            key=key,
        )

    teacher_wins = bool(vs_heuristic["significant"] and vs_heuristic["mean_delta"] > 0)
    if teacher_wins:
        decision = GATE_DISTILL
        next_step = (
            "Más destilación: el maestro RH gana al heurístico en val. "
            "Ampliar etiquetas RH o DAgger antes de programar PPO."
        )
    else:
        decision = GATE_PPO
        next_step = (
            "Fine-tuning PPO del mlp_v1_p1s1.pt: el maestro no supera al "
            "heurístico; imitar más no tiene techo que perseguir."
        )

    return {
        "decision": decision,
        "next_step": next_step,
        "teacher_wins_heuristic": teacher_wins,
        "teacher_vs_heuristic": vs_heuristic,
        "teacher_vs_mlp": vs_mlp,
        "verdict_heuristic": verdict(vs_heuristic),
        "verdict_mlp": verdict(vs_mlp) if vs_mlp else None,
    }


def assert_can_promote(comparison: Mapping[str, Any]) -> None:
    """Una promoción exige diferencia significativa en val, no un empate ruidoso."""

    if not comparison.get("significant"):
        raise MethodologyError(
            f"no hay evidencia para promocionar {comparison.get('label_a')} "
            f"sobre {comparison.get('label_b')}: "
            f"Δ={comparison.get('mean_delta'):+.4f} "
            f"IC95 [{comparison.get('ci_lo'):+.4f}, {comparison.get('ci_hi'):+.4f}], "
            f"n={comparison.get('n_paired')}. El intervalo contiene el cero."
        )
