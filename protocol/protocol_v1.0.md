# Protocol v1.0: Nyaya-inspired evidence defeat for safe clinical-AI deferral

**Status:** Frozen before blinded variance estimation and confirmatory validation

**Freeze date:** 23 October 2026

**Final candidate:** C002

**Registration:** Public Git tag `protocol-v1.0`

## 1. Study objective

This study evaluates whether a non-compensatory evidence-defeat framework can
reduce unsafe acceptance of individualised clinical recommendations compared
with uncertainty-only deferral at exactly matched coverage. The framework does
not decide whether care should be delayed. When evidence is inadequate, it
returns the case to an evidence-based default policy or to human review.

The central question is not whether a model can always personalise treatment.
It is whether the system can identify when the evidence supporting a
personalised recommendation is insufficient to justify acting on it.

## 2. Frozen C002 framework

C002 applies three essential checks to every held-out recommendation:

1. record adequacy (`D_i`): required patient information is present and
   plausible;
2. reference-population support (`O_i`): the patient lies in a covariate region
   supported by the reference data; and
3. estimator-action agreement (`M_i`): the prespecified causal estimators agree
   on the recommended action.

The non-compensatory evidence gate is

```text
H_i = D_i * O_i * M_i.
```

The product is logical conjunction, not a weighted score. If any essential
check fails, the recommendation is defeated and cannot be rescued by strength
on another check.

Recommendations surviving the essential gate are ranked within each held-out
outer fold by

```text
S_i = (abs(tau_hat_i) - delta) / SE_hat_i,
```

where `tau_hat_i` is the estimated treatment effect on the common risk-
difference scale, `delta` is the prespecified materiality margin and
`SE_hat_i` is the corresponding standard error. The highest-ranked 80% among
eligible recommendations are retained. If `U_i(0.80)` denotes that indicator,
the final rule is

```text
G_i(C002) = H_i * U_i(0.80).
```

The uncertainty stage is subordinate to the essential evidence checks. It can
defer an otherwise eligible recommendation but cannot reinstate a defeated
one.

## 3. Nyaya rationale

The framework is inspired by Nyaya's treatment of defeating flaws in
reasoning (*hetvabhasa*). Missing or implausible case information is analogous
to a reason not established in the subject; unsupported extension into a
sparse covariate region is analogous to a relation whose applicability has
not been established; and opposing recommendations from prespecified
estimators are analogous to counterbalanced inference (*satpratipaksa*).

These are conceptual mappings, not a claim that classical Nyaya supplied a
modern statistical algorithm. Nyaya contributes the non-compensatory design
principle: an essential defect defeats the recommendation rather than being
averaged away.

## 4. Development history and separation from validation

C000, C001 and C002 were examined in transparent Stage C development. C000
lost excessive coverage, and C001 was inferior to uncertainty-only deferral
in the development no-defect setting. C002 added a graded uncertainty stage
without allowing uncertainty to compensate for a failed essential check.

Stage C selected C002 because it had the strongest observed safety-access
profile among the evaluated candidates. Those estimates are developmental
and will not be presented as independent confirmation. The C002 rule,
thresholds, learner set, outcome definitions, default policy, estimands,
comparators and fairness audit are frozen before Stage E and Stage F.

## 5. Validation design

### 5.1 Stage E: blinded variance pilot

The pilot uses 25 new replicates in each of the ten primary scenario cells.
Only the paired primary-contrast standard deviation and computational resource
use may be disclosed. Mean effects, method rankings and group differences may
not be examined.

For each scenario, the required Monte Carlo replicate count is

```text
R_s = ceiling((SD_s / 0.0025)^2).
```

The final common count is the largest `R_s`, subject to a minimum of 1,000 and
a maximum of 5,000 replicates per scenario. Only this count and computational
batching may change after the pilot.

### 5.2 Stage F: one-time confirmatory validation

The primary grid crosses five generated evidence defects—record inadequacy,
weak reference support, model multiplicity, decision uncertainty and combined
defects—with sample sizes 500 and 2,000. All scenarios use a binary outcome,
a nonlinear baseline, moderate treatment-effect heterogeneity, group
prevalence 0.20, equal defect allocation and treatment probability 0.50.

The frozen pipeline will be run once over the selected replicate range.
Results will be reported regardless of direction. No scenario, seed or
replicate may be removed because it is unfavourable.

## 6. Outcomes and decision rule

The primary metric is material unsafe acceptance with the full simulated
population as denominator. A recommendation is materially unsafe when the
accepted action conflicts with the known optimal action and the true absolute
treatment effect meets the prespecified materiality threshold.

The primary contrast is

```text
mean unsafe acceptance under C002
minus
mean unsafe acceptance under uncertainty-only deferral at exact matched coverage.
```

Each of the ten scenario cells receives equal weight. Negative values favour
C002. The confirmatory safety claim is supported only if the upper limit of
the two-sided 95% confidence interval is below zero. Mean C002 coverage must
also remain at or above 25% for the result to be considered practically
informative.

Policy utility, oracle regret, regret relative to the default, check-failure
rates and the no-defect negative control are secondary outcomes. They cannot
replace a failed primary result.

## 7. Comparators and ablations

The principal comparator is uncertainty-only deferral tuned within each
held-out fold to exactly match C002 coverage. Secondary comparators are
ungated individualisation, matched random deferral and the evidence-based
population default.

Mechanism analyses remove each essential check in turn. Holm adjustment is
applied across the three check-specific comparisons. These analyses assess
whether each check contributes to safety; they do not redefine the primary
claim.

## 8. Fairness audit

Fairness is evaluated as a safety-and-access audit, not as a single optimised
score. The study reports group-specific coverage, unsafe acceptance and
utility, together with raw between-group differences. Evidence-standardised
contrasts are reported only where their balance diagnostics pass. No weighted
fairness composite is used, and aggregate safety improvement will not be
described as proof of fairness.

## 9. Public-data evaluation

After the controlled validation is complete, the frozen method will be
applied without tuning in a separate public randomised-trial case study. That
analysis evaluates feasibility and transportability under real data. It does
not convert known-truth simulation performance into proof of clinical
effectiveness, and deferral continues to mean default care or human review,
not withholding indicated treatment.

## 10. Reproducibility and reporting

All configurations, seeds, code commits, fold allocations and run manifests
will be retained. Stage E and Stage F use replicate namespaces not used during
development. Confirmatory results, null findings, adverse subgroup patterns
and protocol deviations will be reported. Any later change to C002 creates a
new framework version requiring new validation data.
