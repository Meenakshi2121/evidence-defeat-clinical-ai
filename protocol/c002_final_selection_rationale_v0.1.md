# C002 final development-selection rationale v0.1

**Status:** Draft for supervisor and statistical review; candidate not frozen

**Date:** 23 October 2026

**Scope:** Stage C controlled-simulation development only

## Proposed decision

Select C002 unchanged as the provisional final development candidate and
recommend it for Stage D freeze after supervisor and statistical approval.
Do not alter the evidence checks, thresholds, 80% graded-uncertainty retention
fraction, causal learners, population default, estimands or fairness audit in
response to the Stage C results.

This is a development-selection decision. It is not independent validation,
a fairness guarantee, evidence of clinical effectiveness or authorisation for
deployment.

## Candidate rule

C002 first applies three essential, non-compensatory evidence checks:

```text
H_i = D_i * O_i * M_i,
```

where `D_i` is record adequacy, `O_i` is reference-population support and
`M_i` is agreement on the recommended action across prespecified causal
estimators. A failed check cannot be offset by strength elsewhere.

For recommendations that survive those checks, C002 computes

```text
S_i = (abs(tau_hat_i) - delta) / SE_hat_i
```

and retains the highest-ranked 80% within each held-out outer fold. Its final
acceptance rule is

```text
G_i(C002) = H_i * U_i(0.80).
```

The graded uncertainty filter cannot rescue a recommendation defeated by an
essential evidence check. Deferred cases return to the evidence-based default
or a human-review pathway; deferral does not mean withholding or delaying
clinically indicated care.

## Why C002 is preferred

Across 35 revision-screening, 30 revision-fairness-stress and 25 revision-
finalist-robustness runs, the primary matched-coverage safety contrast favoured
C002 at every tier. In the final robustness tier, C002 reduced whole-population
material unsafe acceptance by 0.010160 relative to uncertainty-only deferral
(95% confidence interval -0.014963 to -0.005357). The defect-present estimate
was -0.011825 (-0.016551 to -0.007099), and all five scenario means were in the
same direction.

C002 retained meaningful access: mean robustness coverage was 45.236%, with
all scenario means above the prespecified 25% floor. Its utility was not
distinguishable from matched-coverage uncertainty-only deferral, while it
exceeded matched random deferral and the population default. Removing any of
the three essential evidence checks increased unsafe acceptance; the largest
increase followed removal of model multiplicity.

The architecture also resolves the central weakness of C001. C001 was clearly
inferior to uncertainty-only deferral in its no-defect robustness scenario.
C002's no-defect mean did not show that disadvantage and remained within the
recorded development boundary.

No simpler evaluated candidate achieved the same overall profile. C000
collapsed access through a strict binary certainty condition. C001 preserved
access and helped under generated evidence defects but failed in the no-defect
robustness scenario. C002 adds only a graded, rank-based uncertainty stage to
C001's three-check structure and is therefore the Pareto-preferred development
candidate among those evaluated.

## Adverse findings and unresolved risks

The no-defect robustness result was seed-sensitive. Four of five run-level
contrasts slightly favoured uncertainty-only deferral, while one strongly
favoured C002; the scenario confidence interval included both benefit and
harm. This must be tested in the untouched validation bank rather than tuned
away.

C002 incurred a utility cost relative to ungated individualisation. That cost
is the consequence of deferring more recommendations for safety and must be
reported as a trade-off, not hidden behind the safety result.

The fairness-stress tier showed that additional deferral and a small utility
loss could be concentrated in the group exposed to more evidence defects.
The final robustness tier produced no clear overall raw coverage or unsafe-
acceptance gap, but none of its evidence-standardised analyses met the balance
criterion. The framework therefore does not establish equal access or proven
fairness. Fairness remains a separate safety-and-access audit; no weighted
fairness score is used.

Model multiplicity was safety-relevant in ablation but remained a weak
classifier of its named generated defect. Its construct validity and practical
interpretation require further scrutiny. The binary defect-recovery statistic
for decision uncertainty also has low specificity and should not be confused
with C002's operational within-fold graded ranking rule.

## Conditions before validation

Before any reserved validation simulation or patient-level trial outcome is
opened:

1. supervisors and an independent statistician must review the full candidate
   history, this rationale and the adverse findings;
2. C002 must be frozen by candidate identifier, clean Git commit and complete
   configuration hashes;
3. the protocol must specify the untouched confirmatory scenarios, primary
   contrast, confidence-interval rule, Monte Carlo replicate count and
   fairness reporting without further candidate tuning;
4. the protocol and analysis plan must be registered and tagged
   `protocol-v1.0`; and
5. the independent validation must be run once and reported regardless of
   result.

Only independent validation can support a claim that C002 generalises beyond
the development bank. Subsequent public trial evaluation would then assess
clinical transportability and feasibility, not retrospectively validate the
development simulations.

## Review record

- Study-author recommendation: select C002 unchanged for freeze review.
- Supervisor decision, name and date: pending.
- Statistical reviewer decision, name and date: pending.
- Approved deviations or required changes: pending.
