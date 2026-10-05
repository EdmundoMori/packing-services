# Claims and evidence (manuscript draft)

| Claim | Evidence / source | Status |
| --- | --- | --- |
| Mandi et al.\ ICML 2022; §4.3 Eq.\ (13) | PMLR HTML/PDF | Verified (adaptation, not exact reproduction) |
| Crainic et al.\ extreme points JOC 2008 | DOI 10.1287/ijoc.1070.0250 | Verified as candidate-generation context |
| Zhao et al.\ PCT ICLR 2022 | OpenReview `bfuGjlCwAq` | Verified as related online packing RL; not an experimental baseline here |
| Kagerer et al.\ BED-BPP IJRR 2023 | DOI 10.1177/02783649231193048 | Verified as instance source; not official robotic eval here |
| Unified $S$ for label/train/deploy | `candidate_support.py`, `pipeline.py`, synthetic + preflight | Verified |
| Differentiable losses match frozen formulae | `torch_losses.py` vs `losses.py`; autograd tests | Verified (extreme-logit float reference may underflow; stable log-sum-exp used) |
| Protocol and samples frozen | `protocol_frozen.json`, `sample_manifest.json` | Verified |
| Labelling executor implemented | `run_learning_labels.py`, review 09 | Verified; full campaign not run |
| Pref−class / vs Greedy exploratory pilot | Recalculated 84 episodes | Verified; exploratory only |
| Prior labels reusable under new $S$ | Metadata audit | Not supported |
| New campaign improves packing / publishability | — | Pending |
| Final abstract and conclusions | — | Pending |
| PCT / OnlineBPH / MLP conflation | Manuscript wording | Explicitly separated |
| Physical stability | `physical_stability_verified=null` | Not verified |
