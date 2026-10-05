# Claims and evidence (manuscript draft)

| Claim | Evidence / source | Status |
| --- | --- | --- |
| Mandi / Crainic / Zhao / Kagerer as scoped | primary URLs in review 11 | Verified within stated limits |
| Protocol and samples frozen | digests unchanged | Verified |
| Differentiable losses | `torch_losses.py` tests | Verified |
| Attempt 01 interrupted | `learning_labels/`, reviews 13–14 | Cause/exit unknown; empty files retained as incident evidence |
| Attempt 02 recovery interrupted | `learning_labels_recovery/`, review 16 | 46 verified; 26 pending at interrupt |
| Attempt 03 generation complete | `learning_labels_attempt03/`, summary `completed` | 46 referenced + 26 new |
| Attempt 03 process exit 1 | `runs/attempt_03/run_state.json` | Preserved; verifier glob then included staging |
| Posterior label verification | `forensics/label_verification_closure.json`, verifier `manifest_keyed_v2` | Distinct from process exit; `verified` |
| Coverage 48/24; 192/96 states; 1115 alts | posterior verification | Verified; test not executed |
| Final train normalisation 743 rows | `normalization_train.json` | Fitted once; provisional unused; 372 development rows not fitted |
| Paired training executor (9 models) | `run_learning_train.py`, tests | Implemented; campaign pending publication then one run |
| Actor episodes / abstract / superiority | — | Pending |
| Physical stability | `null` | Not verified |
