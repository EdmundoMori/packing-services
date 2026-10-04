"""Congela el protocolo y la lista de desarrollo. No entrena ni empaqueta."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from model import adam_effective_parameters  # noqa: E402
from observation import FEATURE_NAMES, OBS_DIM  # noqa: E402
from rules import RULE_NAMES  # noqa: E402
from run_training import HASHED_FILES, study_hashes  # noqa: E402
from sample_audit import (  # noqa: E402
    DATASET,
    EXPECTED_DATASET_SHA256,
    SELECTION_PREFIX,
    exposure_audit,
    select_development,
)


def main() -> int:
    if (STUDY / "training").exists():
        raise SystemExit("bloqueo: training ya existe")
    train = json.loads((STUDY / "train_manifest.json").read_text(encoding="utf-8"))
    pool = json.loads((STUDY.parents[2] / train["pool"]).read_text(encoding="utf-8"))
    orders = json.loads(DATASET.read_text(encoding="utf-8"))
    audit = exposure_audit(orders, pool)
    development = select_development(orders, pool, audit, train)
    development["dataset_sha256"] = EXPECTED_DATASET_SHA256
    (STUDY / "development_manifest.json").write_text(
        json.dumps(development, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    hashes = study_hashes(STUDY)
    protocol = {
        "status": "congelado_antes_del_primer_update",
        "confirmatory_preregistration": False,
        "convergence_claimed": False,
        "publishable_claimed": False,
        "physical_stability_verified": None,
        "dataset_path": str(DATASET),
        "dataset_sha256": EXPECTED_DATASET_SHA256,
        "selection_prefix": SELECTION_PREFIX,
        "train_manifest": "train_manifest.json",
        "n_train": train["n_train"],
        "development_manifest": "development_manifest.json",
        "n_development": development["n_development"],
        "development_episodes_executed": False,
        "final_test_selected": False,
        "final_test_consulted": False,
        "historical_checkpoint_loaded": False,
        "rules": list(RULE_NAMES),
        "observation_dim": OBS_DIM,
        "observation_features": FEATURE_NAMES,
        "actor": "Linear(36,64), ReLU, Linear(64,3); último peso a cero; sesgo inicial [1, 0, 0]",
        "critic": "Linear(36,64), ReLU, Linear(64,1); última capa a cero; red distinta del actor",
        "initial_logits": [1.0, 0.0, 0.0],
        "gamma": 1.0,
        "gae_lambda": 1.0,
        "ppo_clip": 0.2,
        "adam": adam_effective_parameters(),
        "entropy_coef": 0.01,
        "value_coef": 0.5,
        "value_loss": "error cuadrático medio, sin clipping del valor",
        "value_clipping": False,
        "epochs_per_rollout": 4,
        "rollout_decisions": 512,
        "minibatch": 128,
        "grad_clip_max_norm": 0.5,
        "grad_clip_norm_type": 2.0,
        "advantage_normalization": "se centra el vector del rollout y se divide por la desviación poblacional; si esa desviación es cero, el resultado es el vector centrado, todo ceros",
        "advantage_scope": "una vez por rollout de 512, antes de los minibatches, con los valores recogidos",
        "on_policy": "cada actualización usa solo su rollout; el buffer se descarta; log_prob antigua queda separada del grafo",
        "update_definition": "una actualización procesa las cuatro épocas de un rollout completo de 512",
        "optimizer_steps_per_update": 16,
        "device": "cpu",
        "max_workers": 2,
        "torch_threads_per_worker": 1,
        "checkpoint_policy": "checkpoint final del último update válido; las recompensas de train no eligen checkpoint ni semilla",
        "generators": "tres generadores independientes, cada uno con manual_seed de la semilla de campaña: calendario, acciones y permutación de cada época",
        "budget": {
            "seeds": [101, 102, 103],
            "decisions_per_seed": 6144,
            "rollouts_per_seed": 12,
            "seed_wall_seconds": 4800,
            "global_wall_seconds": 14400,
            "decision_definition": "cada llamada real a step, también cuando las tres reglas proponen la misma colocación",
            "distinct_proposals": "decisiones con colocación en las que all_three es falso",
            "previous_episode_cap_removed": True,
            "unused_budget_reassigned": False,
            "reason": "tiempo observado en el preflight, antes de este entrenamiento y sin usar U_geom para elegir el corte",
            "slowest_preflight_seconds_per_decision": 0.6411254537755092,
            "slowest_source": "pedido 00106344, regla fija, 62.830 s de bucle y 98 decisiones",
            "extrapolation_note": "6144 decisiones a 0.641 s caben en 4800 s con margen; 60000 no. Cuatro pedidos no caracterizan el resto de train. No es evidencia de convergencia.",
        },
        "development_gate": {
            "applied": False,
            "kind": "puerta de ingeniería, no significación estadística",
            "reference_rule": "la regla fija de mayor media de U_geom en desarrollo; si la diferencia absoluta es <= 1e-12, gana el menor índice de acción",
            "uniform_random_seeds": [101, 102, 103],
            "aggregation": "igual peso por pedido y después por semilla",
            "conditions": [
                "media de RL menos la mejor regla fija >= 0.005 de U_geom",
                "diferencia RL menos referencia > 0 en al menos dos de tres semillas",
                "agregado RL menos referencia >= 0 en cada target",
                "media de RL menos la selección aleatoria uniforme > 0",
                "campaña íntegra y evaluación completa",
            ],
            "online_bph": "comparación externa posterior; no es PCT aprendido y no entra en esta puerta",
        },
        "code_hashes": hashes,
        "hashed_files": list(HASHED_FILES),
    }
    (STUDY / "protocol_frozen.json").write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    protocol_sha = hashlib.sha256((STUDY / "protocol_frozen.json").read_bytes()).hexdigest()
    (STUDY / "protocol_frozen.md").write_text(_protocol_md(protocol, protocol_sha), encoding="utf-8")
    (STUDY / "training_operational_annex.md").write_text(_annex(protocol, protocol_sha), encoding="utf-8")
    return 0


def _protocol_md(protocol: dict, protocol_sha: str) -> str:
    return f"""# Protocolo congelado de selección de reglas

Estado: congelado antes del primer update del piloto. No es una preregistración confirmatoria. No afirma convergencia ni publicabilidad. `physical_stability_verified` permanece null.

SHA256 de este JSON hermano: `{protocol_sha}`.

## Presupuesto

Semillas 101, 102 y 103. Cada una tiene 6144 decisiones, doce rollouts de 512 y 4800 segundos. El entrenamiento global tiene 14400 segundos. Una decisión es cada llamada real a `step`, también si las tres reglas proponen la misma colocación. El límite anterior de 1000 episodios no es el criterio. El presupuesto no usado no se reasigna.

El corte sustituye al techo de 60000 decisiones por el tiempo del preflight, medido antes de este entrenamiento. El bucle más lento hizo 98 decisiones en 62.830 segundos, 0.641 segundos por decisión. A esa tasa, 60000 decisiones superan las cuatro horas de un worker y 6144 quedan dentro de los 4800 segundos con margen. U_geom no intervino en el corte. Cuatro pedidos no caracterizan el resto de train.

Si una semilla no completa las 6144 decisiones y las doce actualizaciones, la campaña queda incompleta. Esas semillas no se comparan como ajustes de igual presupuesto.

## Qué se conserva

Las tres reglas, la observación de {protocol["observation_dim"]} entradas, los 128 pedidos de train, el contrato compacto y las escalas fijas. El actor empieza con logits [1, 0, 0]. No se cargan checkpoints históricos.

## Desarrollo

Hay 40 pedidos, veinte por target, elegidos por el mismo hash y separados de train, de los pedidos ya observados y de los clones. Sus episodios no se ejecutan y no se calculan estadísticas. El test final no se selecciona ni se consulta.

## Puerta

La puerta queda escrita y no se aplica. Es una puerta de ingeniería. La regla de referencia será la de mayor media en desarrollo, con desempate al menor índice si la diferencia absoluta no supera 1e-12. La aleatoria uniforme usa las semillas 101, 102 y 103. OnlineBPH queda como comparación externa posterior y no se llama PCT aprendido.
"""


def _annex(protocol: dict, protocol_sha: str) -> str:
    adam = json.dumps(protocol["adam"], indent=2, ensure_ascii=False)
    return f"""# Anexo operativo del piloto PPO

Este anexo queda escrito antes del primer update. El JSON congelado es `protocol_frozen.json`, SHA256 `{protocol_sha}`.

## Redes

El actor es Linear(36, 64), ReLU, Linear(64, 3). El último peso empieza en cero y el sesgo en [1, 0, 0]. El crítico es otra red Linear(36, 64), ReLU, Linear(64, 1), con la última capa a cero. La entrada es la observación ya definida, sin ítems futuros, sin identificadores y sin el número de ítems restantes.

## Optimización

gamma = 1 y lambda = 1. El clip de PPO es 0.2. La entropía entra con coeficiente 0.01 y el valor con 0.5. Hay cuatro épocas por rollout y minibatches de 128 transiciones. El recorte de gradiente usa la norma 2 con máximo 0.5.

La pérdida de valor es el error cuadrático medio. No hay clipping del valor. El coeficiente 0.5 multiplica esa pérdida fuera del error cuadrático.

Las ventajas se normalizan una vez sobre las 512 transiciones del rollout, con los valores de la recogida, antes de partir minibatches. Se resta la media y se divide por la desviación poblacional. Si esa desviación es cero, el lote normalizado es el vector centrado y queda en cero.

Adam usa estos parámetros efectivos:

```json
{adam}
```

## Datos y corte

Cada actualización consume un rollout nuevo de 512 decisiones. No se reutilizan rollouts antiguos. La log_prob antigua se conserva separada del grafo. Una actualización son las cuatro épocas; cada una hace cuatro pasos de Adam, dieciséis por actualización y 192 si la semilla termina.

El reloj se consulta antes de cada decisión y antes de cada actualización. Un rollout que no llega a 512 no se actualiza. El estado recuperable es el último checkpoint de un update terminado, más el checkpoint inicial. Una semilla que agota el reloj guarda ese estado y no se reintenta.

El calendario ordena los identificadores y aplica una permutación reproducible. No ordena por longitud. Si el rollout corta un episodio, el retorno usa el valor del estado siguiente y el mismo entorno continúa. Un final real no usa bootstrap. No hay recompensas nuevas.

CPU, dos workers como máximo y un hilo de Torch por worker. Tres generadores independientes comparten el número de semilla: uno para el calendario, otro para las acciones y otro para las permutaciones de las épocas.

La auditoría exhaustiva no entra en el rollout. Al cierre de cada semilla se audita la última captura de un episodio terminado, si existe. Las comprobaciones legales del motor siguen activas en cada decisión.
"""


if __name__ == "__main__":
    raise SystemExit(main())
