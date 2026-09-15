"""Rutas del mini-proyecto. Todo vive bajo online_policy_ml/."""

from __future__ import annotations

from pathlib import Path

ML_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ML_ROOT.parent

DATA_DIR = ML_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SPLITS_DIR = DATA_DIR / "splits"
TRAIN_DIR = DATA_DIR / "train"
VAL_DIR = DATA_DIR / "val"
TEST_DIR = DATA_DIR / "test"
HOLDOUT_DIR = DATA_DIR / "holdout_producto"
SCALE_DIR = DATA_DIR / "scale"

ARTIFACTS_DIR = ML_ROOT / "artifacts"
REPORTS_DIR = ARTIFACTS_DIR / "reports"
MODELS_DIR = ARTIFACTS_DIR / "models"

NOTEBOOKS_DIR = ML_ROOT / "notebooks"
DOCS_DIR = ML_ROOT / "docs"

SOURCE_BED_BPP = Path(
    "/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json"
)
DEMO_BED_BPP = REPO_ROOT / "examples" / "5_bed-bpp.json"
PLACEHOLDER_LINEAR = REPO_ROOT / "examples" / "online_policy_linear_v1.json"

BED_JSON_NAME = "bed_bpp_orders.json"
ORDER_IDS_NAME = "order_ids.json"


def transitions_path(split: str, lookahead_p: int, select_s: int) -> Path:
    return split_dir(split) / f"transitions_p{lookahead_p}s{select_s}.pkl"


def scale_split_dir(name: str) -> Path:
    if name not in ("train", "val", "test"):
        raise KeyError(f"split desconocido: {name}")
    return SCALE_DIR / name


def scale_transitions_path(split: str, lookahead_p: int, select_s: int) -> Path:
    return scale_split_dir(split) / f"transitions_p{lookahead_p}s{select_s}.pkl"


def rh_transitions_path(split: str, lookahead_p: int, select_s: int) -> Path:
    return split_dir(split) / f"transitions_p{lookahead_p}s{select_s}_rh.pkl"


def scale_rh_transitions_path(split: str, lookahead_p: int, select_s: int) -> Path:
    return scale_split_dir(split) / f"transitions_p{lookahead_p}s{select_s}_rh.pkl"


def model_path_linear() -> Path:
    return MODELS_DIR / "linear_v1.json"


def model_path_mlp(lookahead_p: int, select_s: int) -> Path:
    return MODELS_DIR / f"mlp_v1_p{lookahead_p}s{select_s}.pt"


def model_path_mlp_ppo(lookahead_p: int = 1, select_s: int = 1) -> Path:
    return MODELS_DIR / f"mlp_v1_p{lookahead_p}s{select_s}_ppo.pt"


def model_dir_fase(fase: str) -> Path:
    path = MODELS_DIR / fase
    path.mkdir(parents=True, exist_ok=True)
    return path


def split_dir(name: str) -> Path:
    mapping = {"train": TRAIN_DIR, "val": VAL_DIR, "test": TEST_DIR}
    if name not in mapping:
        raise KeyError(f"split desconocido: {name}")
    return mapping[name]


def ensure_dirs() -> None:
    for path in (
        RAW_DIR,
        SPLITS_DIR,
        TRAIN_DIR,
        VAL_DIR,
        TEST_DIR,
        HOLDOUT_DIR,
        SCALE_DIR / "train",
        SCALE_DIR / "val",
        SCALE_DIR / "test",
        REPORTS_DIR,
        MODELS_DIR,
        NOTEBOOKS_DIR,
        DOCS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
