# Claims and evidence (manuscript draft)

| Claim | Evidence / source | Status |
| --- | --- | --- |
| Mandi et al., ICML 2022, PMLR 162:14935–14947; §4.3 Eq. (13) | PMLR HTML/PDF; ar5iv 2112.03609 | Verified (exact folio of Eq. 13 within the range not recovered by PDF text extraction) |
| Pairwise-difference is Mandi Eq. 13; our preference loss is softplus-weighted pairs | Mandi; `tools/losses.py` | Verified |
| Unified S is the single support map for label/train/deploy | `tools/candidate_support.py`, `support_api.py` | Verified in specification + synthetic tests |
| Actor features exclude suffix and Q_hat | counterfactual `actor_features.py` | Verified |
| Pref−class / pref−greedy / class−greedy means | Recalculated from 84 `result.json` | Verified |
| Exploratory bootstrap interval for pref−class | `results/02_existing_pilot_analysis.json` | Verified; non-confirmatory |
| Prior labels reusable under new S | Metadata audit: 122/144 states with `n_legal` > alternatives; full legal lists absent | No respaldado / no comprobada |
| Prior pilot uses the new support contract | Deployment scored full legal lists | No respaldado |
| PPO rule selection chose Greedy on development; 120/120 plans match | `rl_rule_selection` closure | Verified historically |
| New campaign improves packing / publishability | — | Pendiente |
| Final abstract and conclusions | — | Pendiente |
| Protocol freeze and sample sizes | `reviews/05_experiment_design_decisions.md` | Pendiente |
