# R13 — Final-policy evaluation closure

56 unique episodes on eight evaluation orders: 24 final PPO actor episodes
and 32 internal reference episodes. Four confirmed references were reused;
52 episodes were generated during recovery. All 56 episodes terminate naturally.
Input, sequence, orientations, rewards and AABB geometry are checked by the
artifact verifier. Physical stability is not verified.

The first attempt failed because the evaluator loaded the entire training
checkpoint as a state dict instead of its model field. The original attempt
and frozen v1 protocol remain intact. Recovery changes the loader, preserves
weights and reuses confirmed references. Both supervisor times count against
the same 600-second episode-generation budget.

The closure replays deterministic policy inference on saved observations
against all three final checkpoints. It does not step the environment, train,
or replay Adam. Summary tables use equal weights for orders; the combined
PPO row first averages the three seeds within each order.

This is a resource usability demonstration, not evidence of general packing
superiority. Equal returns do not establish equality of actions or layouts.
Action counts and per-order returns are reported separately. Eight orders,
three seeds and one uniform realization per order limit generalization.
No seed, checkpoint, configuration or method is selected by these results.
