"""Genera 05_receding_horizon_p3s2.ipynb (solo se usa al crear el notebook)."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

OUT = Path(__file__).resolve().parent / "05_receding_horizon_p3s2.ipynb"

CELLS: list[tuple[str, str]] = [
    (
        "markdown",
        """# 05 — Maestro receding-horizon para `p=3,s=2`

El MLP de cinta (`mlp_v1_p3s2.pt`) se entrenó con **mayor volumen del buffer**.
El heurístico, en cambio, mira el lookahead. Aquí:

1. Re-etiqueta **solo** `p=3,s=2` con `receding_horizon_ep` (packea el resto con `volume_desc` y proyecta al buffer).
2. Reentrena **solo** ese MLP sobre la muestra **working** (24 / 8 / 8), mismo `mlp_v1` y encoder v1.
3. Compara en val/test cortos contra placeholder, el `mlp_v1_p3s2` actual y el heurístico.
4. Revalida empaquetando en scale val (sin re-etiquetar: receding en pedidos medianos es ~1 min/pedido).
5. Promociona el `.pt` de producción **solo** si gana en val y todo es `is_valid`.

No se toca `mlp_v1_p1s1.pt`. Las transiciones de volumen (`transitions_p3s2.pkl`) no se pisan: las nuevas van a `*_rh.pkl`.
""",
    ),
    (
        "code",
        r"""from pathlib import Path
import sys

try:
    get_ipython().run_line_magic("matplotlib", "inline")
except Exception:
    import matplotlib
    matplotlib.use("Agg")

HERE = Path.cwd().resolve()
if HERE.name == "notebooks":
    ML_ROOT = HERE.parent
else:
    ML_ROOT = HERE if (HERE / "src_ml").is_dir() else Path("/home/edmundo/packing-services/online_policy_ml")

REPO_ROOT = ML_ROOT.parent
for p in (ML_ROOT / "src_ml", REPO_ROOT / "src"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from bootstrap import setup
setup()

import json
import shutil
import pandas as pd
import matplotlib.pyplot as plt
try:
    from IPython.display import display
except ImportError:
    def display(x):
        print(x)

print("ML_ROOT =", ML_ROOT)
""",
    ),
    (
        "code",
        r"""from config import HIDDEN_SIZE, MLP_EPOCHS, SEED, TEACHER_RECEDING, mlp_lr
from paths import (
    BED_JSON_NAME,
    HOLDOUT_DIR,
    ORDER_IDS_NAME,
    PLACEHOLDER_LINEAR,
    REPORTS_DIR,
    SPLITS_DIR,
    TRAIN_DIR,
    VAL_DIR,
    TEST_DIR,
    model_dir_fase,
    model_path_mlp,
    rh_transitions_path,
    scale_split_dir,
)
from splits import load_orders
from collect import (
    collect_dataset,
    disagreement_vs_volume,
    load_transitions,
    save_transitions,
)
from train_mlp import fit_mlp
from export_ckpt import export_mlp_pt
from evaluate import evaluate_orders, run_engine, write_report
from packing_services.online.features import FEATURE_DIM
from packing_services.online.learned.policy import LearnedPlacementPolicy
from packing_services.datasets.bed_bpp import smallest_order_id

assert (SPLITS_DIR / "working_split.json").is_file(), "Falta fase 1"
assert model_path_mlp(3, 2).is_file(), "Falta mlp_v1_p3s2.pt de producción"
assert PLACEHOLDER_LINEAR.is_file()
assert FEATURE_DIM == 35

LOOKAHEAD_P, SELECT_S = 3, 2
print("maestro", TEACHER_RECEDING, "régimen p=", LOOKAHEAD_P, "s=", SELECT_S)
print("producción p3s2 actual", model_path_mlp(LOOKAHEAD_P, SELECT_S))
""",
    ),
    (
        "markdown",
        """## Colecta P2O receding-horizon (pedidos cortos)

Misma muestra working de las fases 1–3 (24 / 8 / 8). Si el pickle `*_rh.pkl` ya existe, se reutiliza.
""",
    ),
    (
        "code",
        r"""def collect_or_load(orders, order_ids, path, *, tag):
    if path.is_file():
        payload = load_transitions(path)
        print(f"  {tag}: reusa {path.name} ({payload['n_transitions']} tr, {payload.get('seconds', 0):.1f}s)")
        return payload
    print(f"  {tag}: colecta {len(order_ids)} pedidos → {path.name}")
    payload = collect_dataset(
        orders,
        order_ids,
        lookahead_p=LOOKAHEAD_P,
        select_s=SELECT_S,
        teacher=TEACHER_RECEDING,
    )
    save_transitions(payload, path)
    print(f"  {tag}: {payload['n_transitions']} tr, label_rate={payload['label_rate']:.2f}, {payload['seconds']:.1f}s")
    return payload


working_dirs = {"train": TRAIN_DIR, "val": VAL_DIR, "test": TEST_DIR}
working_orders = {name: load_orders(d / BED_JSON_NAME) for name, d in working_dirs.items()}
working_ids = {
    name: json.loads((d / ORDER_IDS_NAME).read_text(encoding="utf-8"))
    for name, d in working_dirs.items()
}

print("=== working p=3 s=2 receding ===")
working_payloads = {}
working_rows = []
for split_name in ("train", "val", "test"):
    path = rh_transitions_path(split_name, LOOKAHEAD_P, SELECT_S)
    payload = collect_or_load(
        working_orders[split_name], working_ids[split_name], path, tag=f"working/{split_name}"
    )
    working_payloads[split_name] = payload
    n_opt = [t["n_options"] for t in payload["transitions"]]
    disc = disagreement_vs_volume(payload["transitions"])
    working_rows.append(
        {
            "set": "working",
            "split": split_name,
            "n_orders": len(working_ids[split_name]),
            "n_transitions": payload["n_transitions"],
            "label_rate": payload["label_rate"],
            "n_options_mean": round(sum(n_opt) / max(len(n_opt), 1), 2),
            "disagree_vs_volume": disc["rate"],
            "seconds": round(float(payload.get("seconds") or 0.0), 2),
        }
    )

df_working = pd.DataFrame(working_rows)
display(df_working)
assert df_working["label_rate"].min() == 1.0
""",
    ),
    (
        "markdown",
        """## Scale val: solo empaquetar

No se re-etiqueta scale. En un pedido de ~40 ítems el maestro receding tarda ~10–60 s (packea el resto en cada paso). La comparación en pedidos medianos usa los JSON de la fase 4 y corre las políticas, no el maestro.
""",
    ),
    (
        "code",
        r"""scale_ok = all((scale_split_dir(n) / BED_JSON_NAME).is_file() for n in ("train", "val"))
print("scale JSON fase 4:", "sí" if scale_ok else "no")

scale_payloads = {}
scale_rows = []
scale_ids = {}
scale_orders = {}
if scale_ok:
    scale_orders = {n: load_orders(scale_split_dir(n) / BED_JSON_NAME) for n in ("train", "val")}
    scale_ids = {
        n: json.loads((scale_split_dir(n) / ORDER_IDS_NAME).read_text(encoding="utf-8"))
        for n in ("train", "val")
    }
    print("scale val pedidos:", len(scale_ids["val"]), "(eval packing, sin colecta RH)")
""",
    ),
    (
        "markdown",
        """## Entrenar MLP `p=3,s=2` (working RH y, si hay, scale RH)

Misma arquitectura que producción: `Linear(35,64)→ReLU→Linear(64,1)`. Se guardan en `artifacts/models/fase5/`.
""",
    ),
    (
        "code",
        r"""fase5_dir = model_dir_fase("fase5")
prod_p3 = model_path_mlp(LOOKAHEAD_P, SELECT_S)
prod_p1 = model_path_mlp(1, 1)
p1_mtime_before = prod_p1.stat().st_mtime
print("no se toca p1s1:", prod_p1)

candidates = {}
histories = {}

print("\n--- MLP working RH ---")
fit_w = fit_mlp(
    working_payloads["train"]["transitions"],
    working_payloads["val"]["transitions"],
    hidden_size=HIDDEN_SIZE,
    epochs=MLP_EPOCHS,
    lr=mlp_lr(LOOKAHEAD_P, SELECT_S),
    seed=SEED,
)
path_w = fase5_dir / "mlp_v1_p3s2_rh_working.pt"
export_mlp_pt(fit_w["state_dict"], path_w, hidden_size=HIDDEN_SIZE)
candidates["rh_working"] = path_w
histories["rh_working"] = fit_w["history"]
display(pd.DataFrame(fit_w["history"]).tail(3))

if "train" in scale_payloads:
    print("\n--- MLP scale RH ---")
    fit_s = fit_mlp(
        scale_payloads["train"]["transitions"],
        scale_payloads["val"]["transitions"],
        hidden_size=HIDDEN_SIZE,
        epochs=MLP_EPOCHS,
        lr=mlp_lr(LOOKAHEAD_P, SELECT_S),
        seed=SEED,
    )
    path_s = fase5_dir / "mlp_v1_p3s2_rh_scale.pt"
    export_mlp_pt(fit_s["state_dict"], path_s, hidden_size=HIDDEN_SIZE)
    candidates["rh_scale"] = path_s
    histories["rh_scale"] = fit_s["history"]
    display(pd.DataFrame(fit_s["history"]).tail(3))

fig, ax = plt.subplots(figsize=(6, 3.5))
for name, hist in histories.items():
    dfh = pd.DataFrame(hist)
    ax.plot(dfh["epoch"], dfh["val_acc"], marker="o", label=name)
ax.set_xlabel("epoch")
ax.set_ylabel("val acc (P2O)")
ax.set_title("MLP p=3 s=2 receding-horizon")
ax.legend()
ax.grid(True, alpha=0.3)
plt.show()

for name, path in candidates.items():
    policy = LearnedPlacementPolicy.from_path(path)
    print("carga ok", name, type(policy).__name__, path.name)
""",
    ),
    (
        "markdown",
        """## Validación packing (no accuracy P2O)

Pedidos cortos: heurístico + placeholder + MLP actual + candidatos RH.  
Scale val: sin heurístico (lookahead caro). `mlp_v1_p1s1` no entra en esta tabla.
""",
    ),
    (
        "code",
        r"""def summarize(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["model"] = df.apply(
        lambda r: (
            "heuristic"
            if r["engine"] == "heuristic"
            else Path(str(r["model_path"])).name
            + ("#prod" if str(r["model_path"]) == str(prod_p3) else "")
        ),
        axis=1,
    )
    g = (
        df.groupby("model", sort=False)
        .agg(
            n=("order_id", "count"),
            util=("volume_utilization", "mean"),
            packed=("items_packed", "mean"),
            valid=("is_valid", "mean"),
            sec=("seconds", "mean"),
        )
        .reset_index()
    )
    return g.round({"util": 4, "packed": 2, "valid": 3, "sec": 4})


def util_of(summary, model_name):
    hit = summary.loc[summary["model"] == model_name, "util"]
    return float(hit.iloc[0]) if len(hit) else None


def valid_of(summary, model_name):
    hit = summary.loc[summary["model"] == model_name, "valid"]
    return float(hit.iloc[0]) if len(hit) else None


def eval_suite(orders, order_ids, *, with_heuristic, max_orders=None):
    rows = []
    if with_heuristic:
        rows += evaluate_orders(
            orders, order_ids, engine="heuristic",
            lookahead_p=LOOKAHEAD_P, select_s=SELECT_S, max_orders=max_orders,
        )
    rows += evaluate_orders(
        orders, order_ids, engine="learned",
        lookahead_p=LOOKAHEAD_P, select_s=SELECT_S,
        model_path=str(PLACEHOLDER_LINEAR), max_orders=max_orders,
    )
    rows += evaluate_orders(
        orders, order_ids, engine="learned",
        lookahead_p=LOOKAHEAD_P, select_s=SELECT_S,
        model_path=str(prod_p3), max_orders=max_orders,
    )
    for path in candidates.values():
        rows += evaluate_orders(
            orders, order_ids, engine="learned",
            lookahead_p=LOOKAHEAD_P, select_s=SELECT_S,
            model_path=str(path), max_orders=max_orders,
        )
    return rows


print("working val p=3 s=2")
rows_wval = eval_suite(working_orders["val"], working_ids["val"], with_heuristic=True)
sum_wval = summarize(rows_wval)
display(sum_wval)

print("working test p=3 s=2")
rows_wtest = eval_suite(working_orders["test"], working_ids["test"], with_heuristic=True)
sum_wtest = summarize(rows_wtest)
display(sum_wtest)

rows_sval = []
sum_sval = pd.DataFrame()
if scale_ok:
    print("scale val p=3 s=2 (sin heurístico)")
    rows_sval = eval_suite(scale_orders["val"], scale_ids["val"], with_heuristic=False)
    sum_sval = summarize(rows_sval)
    display(sum_sval)
""",
    ),
    (
        "markdown",
        """## Smoke holdout de producto (`00100408`, nunca train)

Régimen de esta fase: `lookahead_p=3`, `select_s=2`.
""",
    ),
    (
        "code",
        r"""holdout = load_orders(HOLDOUT_DIR / "5_bed-bpp.json")
oid = smallest_order_id(holdout)
smoke_rows = []
for path in [prod_p3, *candidates.values()]:
    LearnedPlacementPolicy.from_path(path)
    row = run_engine(
        holdout, oid, engine="learned",
        lookahead_p=LOOKAHEAD_P, select_s=SELECT_S, model_path=str(path),
    )
    row["checkpoint"] = path.name
    smoke_rows.append(row)
    print(
        oid, path.name, "packed", row["items_packed"], "/", row["n_items"],
        "valid", row["is_valid"], "util", round(row["volume_utilization"], 4),
    )
assert all(r["is_valid"] for r in smoke_rows)
assert all(r["items_packed"] + r["items_unpacked"] == r["n_items"] for r in smoke_rows)
""",
    ),
    (
        "markdown",
        """## Promoción

Criterio: el mejor candidato RH debe **superar o igualar** la utilización del `mlp_v1_p3s2.pt` actual en working val, con `is_valid=1`, y no empeorar scale val si existe. `mlp_v1_p1s1.pt` no se mueve.
""",
    ),
    (
        "code",
        r"""u_prod_w = util_of(sum_wval, prod_p3.name + "#prod")
v_prod_w = valid_of(sum_wval, prod_p3.name + "#prod")
u_heu_w = util_of(sum_wval, "heuristic")

ranked = []
for name, path in candidates.items():
    u_w = util_of(sum_wval, path.name)
    v_w = valid_of(sum_wval, path.name)
    u_s = util_of(sum_sval, path.name) if not sum_sval.empty else None
    v_s = valid_of(sum_sval, path.name) if not sum_sval.empty else None
    ranked.append({"name": name, "path": path, "util_working": u_w, "valid_working": v_w, "util_scale": u_s, "valid_scale": v_s})

ranked.sort(key=lambda r: (r["util_working"] or -1, r["util_scale"] or -1), reverse=True)
best = ranked[0]
print("working val prod / heurístico / mejor RH:", u_prod_w, u_heu_w, best["util_working"], best["name"])

ok_valid = (best["valid_working"] == 1.0) and (best["valid_scale"] in (None, 1.0))
ok_working = best["util_working"] is not None and u_prod_w is not None and best["util_working"] >= u_prod_w
ok_scale = True
if best["util_scale"] is not None:
    u_prod_s = util_of(sum_sval, prod_p3.name + "#prod")
    ok_scale = u_prod_s is None or best["util_scale"] >= u_prod_s

promoted = bool(ok_valid and ok_working and ok_scale)
print("ok_valid", ok_valid, "ok_working", ok_working, "ok_scale", ok_scale, "→ promociona", promoted)

if promoted:
    backup = fase5_dir / "mlp_v1_p3s2_before.pt"
    if prod_p3.is_file() and not backup.is_file():
        shutil.copy2(prod_p3, backup)
        print("backup producción p3s2 →", backup)
    shutil.copy2(best["path"], prod_p3)
    print("producción p3s2 ahora es", best["name"], "→", prod_p3)
else:
    print("se mantiene", prod_p3)

p1_before = prod_p1.stat().st_mtime
assert p1_before == p1_mtime_before, "mlp_v1_p1s1.pt no debía cambiar"
print("p1s1 intacto", prod_p1)

report = {
    "fase": 5,
    "seed": SEED,
    "hidden_size": HIDDEN_SIZE,
    "teacher": TEACHER_RECEDING,
    "regime": {"lookahead_p": LOOKAHEAD_P, "select_s": SELECT_S},
    "promoted": promoted,
    "best_candidate": best["name"],
    "val_util_working_prod": u_prod_w,
    "val_util_working_heuristic": u_heu_w,
    "val_util_working_best_rh": best["util_working"],
    "val_util_scale_best_rh": best["util_scale"],
    "candidates": [
        {k: (str(v) if hasattr(v, "name") else v) for k, v in row.items()}
        for row in ranked
    ],
    "transitions_working": working_rows,
    "transitions_scale": scale_rows,
    "val_working": sum_wval.to_dict(orient="records"),
    "test_working": sum_wtest.to_dict(orient="records"),
    "val_scale": sum_sval.to_dict(orient="records") if not sum_sval.empty else [],
    "smoke_holdout": smoke_rows,
    "production_p3s2": str(prod_p3),
    "production_p1s1": str(prod_p1),
    "note": "mlp_v1_p1s1.pt no se modifica en esta fase",
}
write_report(REPORTS_DIR / "05_receding.json", report)
print("reporte", REPORTS_DIR / "05_receding.json")
print()
print("Línea para producto (p=3 s=2):")
print(f'parameters.model_path = "online_policy_ml/artifacts/models/{prod_p3.name}"')
print("packing_mode=online, lookahead_p=3, select_s=2")
print("p=1 s=1 sigue siendo mlp_v1_p1s1.pt")
""",
    ),
]


def main() -> None:
    nb = new_notebook(
        cells=[
            new_markdown_cell(src) if kind == "markdown" else new_code_cell(src)
            for kind, src in CELLS
        ],
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            }
        },
    )
    nbformat.write(nb, OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
