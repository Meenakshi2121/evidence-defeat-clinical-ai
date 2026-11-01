# Controlled development bank v0.1

**Status:** Committed before the first Stage C scientific run

**Date:** 15 October 2026

**Machine-readable files:** `config/development_bank.yaml` and
`config/development_candidates.yaml`

## Purpose and evidential status

This bank is used to construct and select the evidence-defeat framework. Its
results are exploratory, unblinded and ineligible for confirmatory claims. It
uses a separate `dev_v0_1__` scenario prefix and replicate identifiers of
200000 or greater. The reserved validation grid, RCT Bench patient-level data
and real trial outcomes remain prohibited throughout Stage C.

## Baseline non-compensatory gate

For participant `i`, the candidate gate is

```text
G_i = D_i * O_i * M_i * U_i,
```

where every term is binary: record adequacy (`D`), reference support (`O`),
model multiplicity (`M`) and decision certainty (`U`). Thus `G_i = 1` only when
all four checks pass. This formalises the Nyāya-inspired evidence-defeat rule:
one unresolved defeating condition cannot be cancelled by strength elsewhere.

The primary development contrast is

```text
Delta_UA = UA_complete - UA_uncertainty_matched,
```

where `UA` is materially unsafe acceptance divided by the whole simulated
population. Negative values favour the complete gate. This contrast is
descriptive in Stage C; it does not validate the framework.

## Tiers

| Tier | Eligibility | Purpose |
| --- | --- | --- |
| Screening | Every pre-run candidate | Ten replicates of clean control, each single defect and combined defects at `n=500` |
| Fairness stress | Retained candidates | Group-concentrated record, support and combined defects at two group prevalences and `n=2,000` |
| Finalist robustness | Finalists only | Baseline-shape, effect-strength, outcome-type and group-shift variations at `n=2,000` |
| Revision screening | Prospectively declared child candidate | Fresh clean, absent-heterogeneity, single-defect and combined-defect runs at `n=1,000` |
| Revision fairness stress | Retained revised candidate | Fresh group-concentrated scenarios at `n=2,000` |
| Revision finalist robustness | Revised finalist only | Fresh distributional and outcome variations at `n=2,000` |

Promotion is manual and append-only. A later tier cannot be opened by changing
the command line alone; the candidate status must first be changed with a
written post-run decision in the candidate log.

## Fairness audit

For metric `m`, the raw group gap is

```text
Delta_m_raw = mean(m | A=1) - mean(m | A=0),
```

where `A` denotes the audited group. A separate evidence-standardised gap uses
cross-fitted inverse-probability weights derived only from the four evidence
scores. It asks whether a gap remains after mapping both groups to the pooled
distribution of observed evidence conditions. Propensities are clipped to
`[0.05, 0.95]`; weights are truncated at the first and ninety-ninth
percentiles; balance and group sample sizes are reported.

Raw gaps represent experienced access and harm. Standardised gaps are a
diagnostic conditional on evidence conditions. Neither is a fairness
guarantee, and they are never merged into a weighted fairness formula.

## Candidate decisions

Every report retains safety, utility, access, regret, check recovery, raw and
standardised group gaps, scenario stability and seed stability. Candidate
selection inspects the complete profile, prefers Pareto-nondominated options
and uses simplicity only to break practical ties. There is no automatic pass,
weighted composite or threshold search over a result already observed.

Any revision becomes a new child candidate with its exact change, expected
benefit, possible failure mode and falsification metrics committed before it is
run. Rejected candidates and adverse results remain in the history.

## Results-informed candidate C001

After C000 screening was unblinded, its decision-certainty condition was found
to dominate acceptance and reduce complete-gate coverage to 0.38%--5.50%
across the six screening scenarios. C001 is therefore a transparently
results-informed child candidate. It changes only which computed checks are
essential:

```text
G_i(C001) = D_i * O_i * M_i.
```

Decision certainty (`U`) remains computed and reported, and uncertainty-only
deferral remains the primary external comparator at exactly matched coverage.
The thresholds, learners, scenarios, estimands, population default and fairness
audit are unchanged. C001 is development, not independent validation; its
pre-run specification and the complete C000 adverse result are retained in
`protocol/development_candidate_log_v0.2.md`.

## Results-informed candidate C002

C001's finalist-robustness result differed by evidence state: its safety
contrast favoured the three-check gate when generated evidence defects were
present but favoured uncertainty-only deferral in the no-defect scenario.
C002 therefore uses a hierarchy rather than treating evidence defects and
uncertainty as substitutes:

```text
H_i = D_i * O_i * M_i
S_i = (abs(tau_hat_i) - delta) / SE_hat_i
G_i(C002) = H_i * U_i(0.80)
```

`U_i(0.80)` retains the highest-ranked 80% of `S_i` separately within each
held-out fold. It is applied after the three evidence checks and cannot
override their failure. The final comparator again uses uncertainty alone at
exactly matched C002 coverage.

C002 may use only the new revision-screening tier until an append-only decision
authorises progression. Its five replicate identifiers, 230000--230004, do not
overlap C000 or C001. The later namespaces 240000--240004 and
250000--250004 are specified but closed. The 0.80 fraction and all promotion
criteria were recorded before C002 execution; no search over that fraction is
permitted on the fresh C002 results.
