# Claims and evidence (manuscript draft)

| Claim | Evidence / source | Status |
| --- | --- | --- |
| Mandi et al.\ ICML 2022; §4.3 Eq.\ (13) | PMLR HTML/PDF | Verified (adaptation, not exact reproduction) |
| Crainic et al.\ extreme points JOC 2008 | DOI 10.1287/ijoc.1070.0250 | Verified as candidate-generation context |
| Zhao et al.\ PCT ICLR 2022 | OpenReview `bfuGjlCwAq` | Related only; not an experimental baseline |
| Kagerer et al.\ BED-BPP IJRR 2023 | DOI 10.1177/02783649231193048 | Instance source; not official robotic eval |
| Unified $S$ for label/train/deploy | `candidate_support.py`, preflight | Verified |
| Differentiable losses match frozen formulae | `torch_losses.py` vs `losses.py` | Verified |
| Protocol and samples frozen | digests in protocol/sample manifests | Verified; unchanged by recovery layer |
| Attempt 01 interrupted | `learning_labels/`, reviews 13–14 | Cause and exit code unknown; non-atomic writes and empty files demonstrated |
| Progress as integrity SoT | review 14 | Rejected |
| Registered time 214.80… s | sum of progress order walls | Registered time, not proven total wall bound |
| Recovery layer (atomic IO + plan + execute) | `labeling_io.py`, `labeling_campaign_safe.py`, `run_learning_labels_recover.py` | Implemented; `--execute-recovery` wires attempt 02 |
| Attempt 02 recovery results | `learning_labels_recovery/` | Pending until authorised run after this publication |
| Pref−class / vs Greedy exploratory pilot | Recalculated 84 episodes | Exploratory only |
| Actor evaluation / final abstract | — | Pending |
| Physical stability | `null` | Not verified |
