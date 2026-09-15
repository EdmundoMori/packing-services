"""Guardia contra maestros tautológicos en el etiquetado P2O.

Contexto. El maestro ``privileged_volume_ep`` elige el mínimo de
``(-item.volume, candidate.rank_key, buffer_index)``, y esas tres componentes
están en el vector de features como ``item_vol_n``, ``rank_0..rank_3`` y
``buffer_index_n``. La etiqueta resultó ser una función determinista y en forma
cerrada de 6 de los 35 features, verificada al 100 % sobre 10 724 transiciones.

Estas pruebas fijan el hallazgo para que no se pueda reintroducir en silencio:

* documentan que el maestro de volumen es tautológico;
* comprueban que el de horizonte deslizante no lo es;
* comprueban que la compuerta ``assert_informative`` rechaza al primero.

Las pruebas sobre datos reales se omiten si los ``.pkl`` de transiciones no están
en el árbol, porque están excluidos del control de versiones.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from packing_services.online.features import FEATURE_DIM, FEATURE_NAMES

REPO = Path(__file__).resolve().parents[1]
ML_ROOT = REPO / "online_policy_ml"
SRC_ML = ML_ROOT / "src_ml"
if str(SRC_ML) not in sys.path:
    sys.path.insert(0, str(SRC_ML))

from methodology import (  # noqa: E402
    CLOSED_FORM_FEATURES,
    TAUTOLOGY_THRESHOLD,
    TautologicalTeacherError,
    assert_informative,
    audit_transitions,
    bootstrap_ci,
    closed_form_index,
    closed_form_rate,
    compare_paired,
    paired_deltas,
    sign_test,
    single_feature_rates,
)

IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}


def _blank(k: int, rng: np.random.Generator) -> np.ndarray:
    return rng.random((k, FEATURE_DIM))


def _transition_from_rule(k: int, rng: np.random.Generator) -> dict:
    """Transición cuya etiqueta la fija la regla cerrada del maestro de volumen."""

    features = _blank(k, rng)
    label = closed_form_index(features)
    return {"features": features.tolist(), "label": int(label), "n_options": k}


def _transition_random_label(k: int, rng: np.random.Generator) -> dict:
    features = _blank(k, rng)
    return {
        "features": features.tolist(),
        "label": int(rng.integers(0, k)),
        "n_options": k,
    }


# --------------------------------------------------------------------------- #
# La regla cerrada
# --------------------------------------------------------------------------- #

def test_closed_form_features_are_the_six_of_the_teacher_key():
    assert CLOSED_FORM_FEATURES == (
        "item_vol_n",
        "rank_0",
        "rank_1",
        "rank_2",
        "rank_3",
        "buffer_index_n",
    )
    for name in CLOSED_FORM_FEATURES:
        assert name in IDX, f"{name} debe existir en el encoder"


def test_closed_form_index_prefers_the_largest_volume():
    """La primera componente de la clave domina: mayor volumen gana siempre."""

    features = np.zeros((3, FEATURE_DIM))
    features[0, IDX["item_vol_n"]] = 0.10
    features[1, IDX["item_vol_n"]] = 0.90
    features[2, IDX["item_vol_n"]] = 0.50
    # La fila ganadora tiene rank_0 peor, y aun así debe ganar por volumen.
    features[1, IDX["rank_0"]] = 99.0
    assert closed_form_index(features) == 1


def test_closed_form_index_breaks_volume_ties_with_rank_key():
    features = np.zeros((3, FEATURE_DIM))
    features[:, IDX["item_vol_n"]] = 0.4
    features[0, IDX["rank_0"]] = -5.0
    features[1, IDX["rank_0"]] = -9.0
    features[2, IDX["rank_0"]] = -1.0
    assert closed_form_index(features) == 1


def test_closed_form_index_falls_through_to_buffer_index():
    features = np.zeros((2, FEATURE_DIM))
    features[:, IDX["item_vol_n"]] = 0.4
    features[0, IDX["buffer_index_n"]] = 0.2
    features[1, IDX["buffer_index_n"]] = 0.0
    assert closed_form_index(features) == 1


# --------------------------------------------------------------------------- #
# Los detectores
# --------------------------------------------------------------------------- #

def test_volume_teacher_labels_are_fully_recoverable_from_features():
    """El defecto encontrado, fijado como prueba."""

    rng = np.random.default_rng(7)
    transitions = [_transition_from_rule(int(rng.integers(2, 20)), rng) for _ in range(200)]
    report = closed_form_rate(transitions)
    assert report["rate"] == pytest.approx(1.0)
    assert report["evaluated"] == 200


def test_random_labels_are_not_recoverable():
    rng = np.random.default_rng(11)
    transitions = [_transition_random_label(int(rng.integers(5, 20)), rng) for _ in range(300)]
    report = closed_form_rate(transitions)
    assert report["rate"] < 0.35, "una etiqueta aleatoria no debe ser reconstruible"


def test_trivial_single_option_steps_are_excluded_because_any_rule_hits_them():
    """Con una sola opción legal la etiqueta es 0 por necesidad."""

    rng = np.random.default_rng(3)
    transitions = [_transition_random_label(1, rng) for _ in range(50)]
    transitions += [_transition_random_label(10, rng) for _ in range(50)]

    included = closed_form_rate(transitions, exclude_trivial=False)
    excluded = closed_form_rate(transitions, exclude_trivial=True)

    assert included["evaluated"] == 100
    assert excluded["evaluated"] == 50
    assert excluded["trivial_steps"] == 50
    # Incluir los triviales infla la tasa: es justo lo que queremos evitar.
    assert included["rate"] > excluded["rate"]


def test_single_feature_detector_finds_a_one_feature_shortcut():
    """Un maestro que eligiera por support_ratio sería detectado igualmente."""

    rng = np.random.default_rng(5)
    transitions = []
    for _ in range(200):
        k = int(rng.integers(3, 12))
        features = _blank(k, rng)
        label = int(np.argmax(features[:, IDX["support_ratio"]]))
        transitions.append({"features": features.tolist(), "label": label, "n_options": k})

    rows = single_feature_rates(transitions)
    assert rows[0]["feature"] == "support_ratio"
    assert rows[0]["rate"] == pytest.approx(1.0)
    assert rows[0]["direction"] == "argmax"


# --------------------------------------------------------------------------- #
# La compuerta
# --------------------------------------------------------------------------- #

def test_gate_rejects_the_tautological_teacher():
    rng = np.random.default_rng(13)
    payload = {
        "teacher": "privileged_volume_ep",
        "feature_version": 1,
        "transitions": [
            _transition_from_rule(int(rng.integers(3, 15)), rng) for _ in range(120)
        ],
    }
    report = audit_transitions(payload, label="sintetico")
    assert report["is_tautological"] is True
    assert report["closed_form_rate"] >= TAUTOLOGY_THRESHOLD

    with pytest.raises(TautologicalTeacherError) as excinfo:
        assert_informative(payload, label="sintetico")
    assert "tautológico" in str(excinfo.value)


def test_gate_accepts_an_informative_teacher():
    rng = np.random.default_rng(17)
    payload = {
        "teacher": "receding_horizon_ep",
        "feature_version": 1,
        "transitions": [
            _transition_random_label(int(rng.integers(5, 20)), rng) for _ in range(200)
        ],
    }
    report = assert_informative(payload, label="sintetico")
    assert report["is_tautological"] is False


# --------------------------------------------------------------------------- #
# Estadística emparejada
# --------------------------------------------------------------------------- #

def test_paired_deltas_align_by_order_and_ignore_unmatched():
    a = [{"order_id": "1", "volume_utilization": 0.70},
         {"order_id": "2", "volume_utilization": 0.60},
         {"order_id": "9", "volume_utilization": 0.99}]
    b = [{"order_id": "1", "volume_utilization": 0.65},
         {"order_id": "2", "volume_utilization": 0.62}]
    deltas, shared = paired_deltas(a, b)
    assert shared == ["1", "2"]
    assert deltas == pytest.approx([0.05, -0.02])


def test_sign_test_is_exact_for_a_clean_sweep():
    result = sign_test([0.01, 0.02, 0.03, 0.04, 0.05])
    assert result["wins"] == 5
    assert result["losses"] == 0
    assert result["p_value"] == pytest.approx(2 / 32)


def test_sign_test_discards_ties():
    result = sign_test([0.0, 0.0, 0.01])
    assert result["ties"] == 2
    assert result["wins"] == 1


def test_bootstrap_ci_brackets_the_mean():
    ci = bootstrap_ci([0.10, 0.12, 0.11, 0.13, 0.09], n_boot=2000)
    assert ci["lo"] <= ci["mean"] <= ci["hi"]
    assert ci["n"] == 5


def test_tiny_difference_on_few_orders_is_not_significant():
    """El escenario exacto de las promociones del proyecto: no debe pasar."""

    a = [{"order_id": str(i), "volume_utilization": 0.6753 + 0.02 * ((-1) ** i)} for i in range(8)]
    b = [{"order_id": str(i), "volume_utilization": 0.6726 + 0.02 * ((-1) ** i)} for i in range(8)]
    # Diferencia constante y minúscula pero sin ruido: aquí sí sería detectable.
    result = compare_paired(a, b, label_a="fase3", label_b="fase4")
    assert result["n_paired"] == 8

    noisy_a = [{"order_id": str(i), "volume_utilization": u}
               for i, u in enumerate([0.71, 0.55, 0.68, 0.80, 0.61, 0.66, 0.72, 0.59])]
    noisy_b = [{"order_id": str(i), "volume_utilization": u}
               for i, u in enumerate([0.60, 0.70, 0.74, 0.62, 0.69, 0.58, 0.66, 0.75])]
    noisy = compare_paired(noisy_a, noisy_b, label_a="A", label_b="B")
    assert noisy["significant"] is False, "con 8 pedidos y varianza real no hay evidencia"


def test_identical_arms_are_never_significant():
    rows = [{"order_id": str(i), "volume_utilization": 0.6 + i / 100} for i in range(20)]
    result = compare_paired(rows, list(rows), label_a="X", label_b="X")
    assert result["mean_delta"] == pytest.approx(0.0)
    assert result["significant"] is False


# --------------------------------------------------------------------------- #
# Datos reales (se omiten si no están los .pkl)
# --------------------------------------------------------------------------- #

def _load(path: Path):
    import pickle

    with path.open("rb") as handle:
        return pickle.load(handle)


@pytest.mark.parametrize(
    "relative",
    ["data/train/transitions_p1s1.pkl", "data/train/transitions_p3s2.pkl"],
)
def test_current_train_transitions_are_informative(relative: str):
    path = ML_ROOT / relative
    if not path.is_file():
        pytest.skip(f"no está {relative} (excluido de git)")
    payload = _load(path)
    assert payload["teacher"] == "receding_horizon_ep"
    report = assert_informative(payload, label=relative)
    assert report["is_tautological"] is False
    assert report["closed_form_rate"] < 0.9


def test_legacy_volume_teacher_dump_is_tautological_if_present():
    path = ML_ROOT / "data/train/transitions_p1s1_volume.pkl"
    if not path.is_file():
        pytest.skip("no hay dump diagnóstico del maestro de volumen")
    payload = _load(path)
    assert payload["teacher"] == "privileged_volume_ep"
    report = audit_transitions(payload, label=str(path))
    assert report["closed_form_rate"] == pytest.approx(1.0, abs=1e-9)
    assert report["is_tautological"] is True
