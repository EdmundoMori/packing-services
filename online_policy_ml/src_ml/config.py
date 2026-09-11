"""Constantes del mini-proyecto."""

SEED = 42
SPLIT_FRACTIONS = {"train": 0.70, "val": 0.15, "test": 0.15}
WORKING_COUNTS = {"train": 24, "val": 8, "test": 8}
# Fase 4: muestra aleatoria del split completo (no los más cortos).
SCALE_COUNTS = {"train": 80, "val": 20, "test": 20}

# Un checkpoint por régimen en fases posteriores. Aquí se generan las transiciones.
REGIMES = ((1, 1), (3, 2))
TEACHER_NAME = "privileged_volume_ep"
TEACHER_RECEDING = "receding_horizon_ep"
SELECTION = "best_fit"
PROBLEM_TYPE = "3D_BPP"
HIDDEN_SIZE = 64
HEURISTIC_P3S2_MAX_ORDERS = 3
MLP_EPOCHS = 10
MLP_LR = 1e-3
MLP_LR_P3S2 = 3e-4
MLP_WEIGHT_DECAY = 1e-4


def mlp_lr(lookahead_p: int, select_s: int) -> float:
    if (lookahead_p, select_s) == (3, 2):
        return MLP_LR_P3S2
    return MLP_LR
