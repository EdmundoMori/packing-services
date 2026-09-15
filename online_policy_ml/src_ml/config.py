"""Constantes del mini-proyecto."""

SEED = 42
SPLIT_FRACTIONS = {"train": 0.70, "val": 0.15, "test": 0.15}
WORKING_COUNTS = {"train": 24, "val": 8, "test": 8}
# Fase 4: muestra aleatoria del split completo (no los más cortos).
SCALE_COUNTS = {"train": 80, "val": 20, "test": 20}

# Un checkpoint por régimen en fases posteriores. Aquí se generan las transiciones.
REGIMES = ((1, 1), (3, 2))
# privileged_volume_ep es tautológico respecto al encoder v1 (fuga de objetivo).
# Solo receding_horizon_ep aporta información que los features no contienen.
TEACHER_NAME = "receding_horizon_ep"
TEACHER_RECEDING = "receding_horizon_ep"
TEACHER_VOLUME = "privileged_volume_ep"
TRAINABLE_TEACHERS = frozenset({TEACHER_RECEDING})
# working_subset: "random" evita el sesgo de quedarse solo con los pedidos más cortos.
WORKING_STRATEGY = "random"
COLLINEARITY_CORR_THRESHOLD = 0.95
CONSTANT_FEATURE_STD = 1e-8
OVERFIT_ACC_GAP_MAX = 0.15
SELECTION = "best_fit"
PROBLEM_TYPE = "3D_BPP"
HIDDEN_SIZE = 64
HEURISTIC_P3S2_MAX_ORDERS = 3
MLP_EPOCHS = 10
MLP_LR = 1e-3
MLP_LR_P3S2 = 3e-4
MLP_WEIGHT_DECAY = 1e-4


PPO_OUTER_EPOCHS = 6
PPO_INNER_EPOCHS = 4
PPO_ROLLOUTS = 2
PPO_LR = 1e-4
PPO_CLIP = 0.2
PPO_ENTROPY_COEF = 0.01
PPO_VALUE_COEF = 0.5
PPO_GAMMA = 0.99
# Penalización de descarte: fracción de volumen del ítem rechazado (misma escala que el reward denso).
PPO_UNPACK_PENALTY = 1.0
PPO_MAX_GRAD = 0.5
# Receta O4M-SP / alvaro-frank: el volumen solo no distingue colocaciones en s=1.
PPO_SUPPORT_COEF = 0.15
PPO_HEIGHT_COEF = 0.15
# KL hacia el actor BC (conserva la política de imitación si el PPO divaga).
PPO_KL_COEF = 0.02
# Régimen STEP (ítem del buffer). p=1 s=1 no tiene decisión de selección.
PPO_STEP_LOOKAHEAD_P = 3
PPO_STEP_SELECT_S = 2


def mlp_lr(lookahead_p: int, select_s: int) -> float:
    if (lookahead_p, select_s) == (3, 2):
        return MLP_LR_P3S2
    return MLP_LR
