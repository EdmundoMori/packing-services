# Claims and evidence (manuscript draft)

| Claim | Evidence / source | Status |
| --- | --- | --- |
| Protocol / samples frozen | digests; `model_spec.py` = `ca2f6dc3…` | Verified |
| Training abort `2176460` | `forensics/training_abort_*` | Solo validación de hashes; sin Adam/pesos |
| Valid training `468ff51` | `learning_models/` | 9× epoch 40; init nueva; sin selección por development |
| Models published | commit `2b4f5e9` | Verified on remote |
| Failed 240-key launch | `learning_development_eval/` (summary intact) | Harness: `resolve()` → system Python; 0 captures |
| Independent interpretation | `independent_interpretation.json` | `evaluacion_incompleta_por_fallo_del_arnes` |
| Zeros / original gate | preserved, not packing results | Do not close config for lack of improvement |
| Evaluator fix | `worker_env.py`, `run_development_eval.py`, review 21 | Absolute venv path + preflight + integrity gate |
| Full development / test | — | Not claimed; not opened |
| Superiority / PCT / physical stability | — | Not claimed |
