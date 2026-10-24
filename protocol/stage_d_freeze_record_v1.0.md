# Stage D freeze record v1.0

**Date:** 23 October 2026

**Decision:** Freeze C002 unchanged for prospective validation

**Authority:** Study-author approval

**Registration mechanism:** Public Git tag `protocol-v1.0`

## Frozen candidate

The final development candidate is C002:

```text
H_i = D_i * O_i * M_i
S_i = (abs(tau_hat_i) - delta) / SE_hat_i
G_i(C002) = H_i * U_i(0.80)
```

`D_i`, `O_i` and `M_i` are essential and non-compensatory. The graded
uncertainty stage retains the highest-ranked 80% within each held-out outer
fold and cannot rescue a failed essential check.

## Development provenance

- Stage C completion commit:
  `6f9ab161e0d16676836a1f05b8f4442e5157b4d6`
- Stage C completion tag:
  `stage-c-c002-development-complete-v0.1`
- Commit used by the final C002 robustness execution:
  `e797aabc4f4c469a3a4923ad08fc505b66fdbc86`
- Candidate history:
  `protocol/development_candidate_log_v0.2.md`
- Selection rationale:
  `protocol/c002_final_selection_rationale_v0.1.md`
- Frozen protocol:
  `protocol/protocol_v1.0.md`
- Frozen validation configuration:
  `config/validation.yaml`

## Recorded configuration hashes

| Configuration | SHA-256 |
|---|---|
| Analysis | `21a769c4e64eed35a630985e173da242f8ce779aeaf68923db19dcd4c1cf9063` |
| C002 effective analysis | `7bf829b2f636b6d5af2c5b09c5caca06a1cf987a8d38022afee7119424995a62` |
| Simulation | `e30e4b6d36c31eeacbc32ee47e13555679d25b9e42b7bc7dcd6caa6584632f73` |

The `protocol-v1.0` Git tag identifies the exact commit containing the frozen
documents and supplies the immutable hashes of those files themselves.

## Frozen elements

The following may not change in response to Stage E or Stage F results:

- C002's three essential checks and their thresholds;
- the 80% within-fold uncertainty retention rule;
- materiality margins and outcome definitions;
- causal learners and cross-fitting structure;
- evidence-based default and deferral meaning;
- primary metric, comparator, scenario weighting and confidence-interval rule;
- coverage floor, fairness audit and secondary comparator definitions; and
- the ten primary validation scenario cells.

Stage E may change only the Monte Carlo replicate count and computational
batching according to the frozen variance rule. That change must be committed
and tagged before Stage F begins.

## Known risks carried forward

The no-defect development result was seed-sensitive; utility was lower than
ungated individualisation; evidence-standardised fairness contrasts often
failed their balance diagnostic; and the model-multiplicity check had limited
construct-recovery performance. These findings are not tuned away. They are
preserved as limitations and tested or reported in the prospective analyses.

## Authorisation

Creation of the public `protocol-v1.0` tag authorises Stage E only. Stage F is
authorised only after Stage E has produced a variance-only replicate-count
decision and that decision has been committed and separately tagged.
