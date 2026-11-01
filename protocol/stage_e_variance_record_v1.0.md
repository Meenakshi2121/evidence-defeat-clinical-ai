# Stage E blinded variance-pilot completion record v1.0

**Candidate:** C002
**Protocol:** `protocol-v1.0`
**Completed:** 24 October 2026
**Scientific status:** variance-only planning; not confirmatory evidence

## Decision

The Stage F Monte Carlo count is locked at **1,000 replicates per primary
scenario**. With ten primary scenario cells, Stage F therefore contains 10,000
confirmatory simulation runs. This count applies uniformly; it was not chosen
from effect direction, method rankings or subgroup results.

## Audit identity

- Stage E code commit: `525788bd24428a684ecc1941c7441e5ee60e9a72`
- Stage E code tag: `stage-e-pilot-code-v1.0`
- Stage E configuration combined SHA-256:
  `fc46b71a41e3cf0827c2e044edff35f7cb7bc8be0d25fd29107ad4098a5baa44`
- Variance-only summary SHA-256:
  `f9c28d5dfb1c0be2c4a8ea3769ae395d4263b919f7e5b936a063262b25271a15`
- Scenario groups completed: 10 of 10
- Pilot replicates completed: 250 of 250
- All scenario-group invariants passed: yes
- Scientific-effect results exposed: no

The summary file remains in the ignored validation-results tree. Its digest is
recorded here so the exact file can be authenticated without committing
intermediate output or broadening the permitted disclosure.

## Permitted variance results

| Primary scenario | Paired-contrast SD | Variance-based count | Count after protocol minimum |
|---|---:|---:|---:|
| Combined, n=500 | 0.016024 | 42 | 1,000 |
| Combined, n=2,000 | 0.013732 | 31 | 1,000 |
| Decision uncertainty, n=500 | 0.014822 | 36 | 1,000 |
| Decision uncertainty, n=2,000 | 0.011169 | 20 | 1,000 |
| Model multiplicity, n=500 | 0.013500 | 30 | 1,000 |
| Model multiplicity, n=2,000 | 0.006831 | 8 | 1,000 |
| Record adequacy, n=500 | 0.024676 | 98 | 1,000 |
| Record adequacy, n=2,000 | 0.014157 | 33 | 1,000 |
| Reference support, n=500 | 0.014465 | 34 | 1,000 |
| Reference support, n=2,000 | 0.007745 | 10 | 1,000 |

For each scenario `s`, the predeclared calculation was

```text
R_s = ceiling((SD_s / 0.0025)^2).
```

The common count was then

```text
R = min(5000, max(1000, max_s R_s)) = 1000.
```

The target Monte Carlo standard error was reachable within the protocol cap in
all ten cells.

## Disclosure and change control

The Stage E reports omitted individual paired contrasts, mean effects, method
rankings and group differences. Consequently, Stage E provides no evidence
that C002 succeeds or fails scientifically. It establishes only that the
confirmatory experiment is computationally specified with adequate planned
Monte Carlo precision.

The only post-pilot scientific-config value changed is the permitted Monte
Carlo replicate count placeholder, now fixed at 1,000. Computational batching
may be adjusted without changing the run set. C002, its thresholds, the
scenario grid, outcomes, comparators, estimand, confidence interval, coverage
floor and decision rule remain unchanged.

Stage F is authorised only after this record and the locked configuration are
committed and publicly tagged as `stage-e-variance-complete-v1.0`. Stage F
results must be reported regardless of direction.
