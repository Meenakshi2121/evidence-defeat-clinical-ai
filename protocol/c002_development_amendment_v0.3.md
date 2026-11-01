# C002 development amendment v0.3

**Status:** Prespecified Stage C amendment; C002 not yet run

**Date:** 21 October 2026

**Applies to:** Candidate C002 and the fresh revision tiers only

## Reason for amendment

C001 completed its authorised screening, fairness-stress and finalist-
robustness tiers. Its robustness evidence was mixed. The matched-coverage
unsafe-acceptance contrast favoured C001 in 20 defect-present runs but favoured
uncertainty-only deferral in five no-defect runs; the interval across all 25
runs included zero. C001 was therefore rejected as the final architecture.

This amendment is openly results-informed. Nothing in C000 or C001 is treated
as independent evidence for C002.

## C002 decision rule

For individual `i`, define the non-compensatory evidence qualification rule

```text
H_i = D_i * O_i * M_i,
```

where `D`, `O` and `M` denote record adequacy, reference support and agreement
on the action across prespecified causal estimators. Define the continuous
uncertainty ranking

```text
S_i = (abs(tau_hat_i) - delta) / SE_hat_i.
```

Within each held-out outer fold, `U_i(0.80)` equals one for the highest-ranked
80% of `S_i`, using the locked deterministic hash rule for exact ties. The C002
acceptance rule is

```text
G_i(C002) = H_i * U_i(0.80).
```

Thus uncertainty filters only recommendations whose evidential basis has not
already been defeated. It cannot compensate for a failed evidence check.

The 0.80 retention fraction is a pragmatic Stage C access target, selected
after C001 and fixed before any C002 run. It is not presented as a universal
clinical constant and will not be tuned against C002 results.

## Comparators and outcomes

The primary comparator remains uncertainty-only deferral at exactly matched
final coverage within every held-out fold. Population default, ungated
individualisation, matched random deferral, single checks and leave-one-check-
out ablations remain secondary comparators. Material unsafe acceptance keeps
the whole-population denominator. Utility, regret, access, check recovery and
fairness outcomes remain separate; no weighted composite selects the method.

## Fresh development bank

C002 is initially authorised only for `revision_screening`:

- seven scenarios: clean control, absent heterogeneity, record inadequacy,
  reference-support failure, model multiplicity, decision uncertainty and
  combined defects;
- five replicates per scenario;
- sample size 1,000;
- replicate identifiers 230000--230004; and
- scenario identifiers beginning `dev_v0_1__revision_`.

Fresh fairness-stress and finalist-robustness tiers are specified under
replicate namespaces 240000--240004 and 250000--250004. They remain closed
until a prior tier is reviewed, the decision is appended to the candidate log,
the candidate status and authorised tiers are updated, and a new clean commit
is tagged.

## Screening interpretation rules

C002 will not receive an automatic or weighted score. The complete profile
will be reviewed. The rationale is challenged if any of the following occurs:

1. the pooled defect-present unsafe-acceptance contrast against matched
   uncertainty-only deferral is non-negative;
2. the C002 minus uncertainty-only unsafe-acceptance difference exceeds 0.005
   in the no-defect scenario;
3. mean coverage is below 0.25 in any primary screening scenario;
4. deployed utility is materially worse than the population default;
5. apparent aggregate benefit conceals harmful or unstable group results; or
6. results are materially unstable across scenarios or seeds.

The 0.005 no-defect limit is a development decision boundary, not a clinical
non-inferiority margin and not a confirmatory hypothesis test.

## Evidence boundary

The reserved validation simulation bank, RCT Bench patient-level data and real
trial outcomes remain unopened. C002 development results will be labelled
exploratory and ineligible for confirmatory claims. Any eventual final candidate
must be frozen, reviewed by the supervisors and a statistician, registered and
tagged before independent validation is accessed once.
