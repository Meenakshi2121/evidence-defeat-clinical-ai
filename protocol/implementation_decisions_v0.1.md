# Implementation decisions v0.1

**Status:** Draft for review before protocol lock  
**Date:** 13 October 2026  
**Configuration:** `config/analysis.yaml`

## 1. Why these three treatment-effect learners

The multiplicity check must compare estimators that make meaningfully different
modelling assumptions. Three cosmetic variants of one algorithm would create
an illusion of corroboration.

The prespecified set is therefore:

1. **CausalForestDML** as the primary individualised policy and source of
   pointwise uncertainty. It supplies an honest forest, orthogonal nuisance
   adjustment and effect intervals.
2. **A penalised treatment-interaction model** as a deliberately simpler,
   approximately parametric alternative. For binary outcomes, effects are
   converted from model predictions to probability differences so that all
   learners are compared on the same scale.
3. **DRLearner with a boosted outcome regression and random-forest final
   stage** as an orthogonal pseudo-outcome learner with a different fitting
   architecture.

The candidate action comes from CausalForestDML. The other models cannot
override a well-supported action by averaging. Instead, a materially opposing
estimate defeats automatic individualisation. This implements the
non-compensatory design while retaining a clear primary learner.

EconML 0.17.0 is pinned because it is a released version with a Python 3.11
wheel. Forest size, honesty, leaf sizes and cross-fitting are fixed in the YAML
file. They may be changed before protocol lock only for documented software
failure or failed recovery tests, not because another setting produces more
favourable effectiveness results.

## 2. Within-model uncertainty versus between-model multiplicity

The uncertainty and multiplicity checks answer different questions:

- the uncertainty check asks whether the primary estimator's interval clears
  the clinical indifference region; and
- the multiplicity check asks whether structurally different, prespecified
  estimators materially oppose the proposed action.

The multiplicity rule ignores tiny sign differences inside the materiality
margin. At least two estimators must materially support the primary action,
and none may materially support the opposite action.

## 3. Uncertainty-only matched-coverage comparator

The uncertainty-only method uses the same primary learner and the same
materiality margin as the complete gate. Its continuous ranking score is the
estimated absolute effect beyond the margin divided by the standard error
recovered from the primary learner's interval. Within each held-out fold it
accepts exactly as many participants as the complete gate. It therefore cannot
win or lose merely by personalising more or fewer participants.

No held-out outcome is used to set the matched-coverage threshold.

Score ties are ordered by the ascending hexadecimal SHA-256 digest of the
canonical JSON array `[trial_id, row_id, master_seed]`. Identifiers are
converted to strings and JSON is encoded as UTF-8 without optional
whitespace. This rule was fixed before any diagnostic or confirmatory method
comparison was run.

## 4. Near-optimal-policy disagreement comparator

Sawarni et al. propose a two-stage abstaining policy learner that identifies
near-optimal policies and abstains where they disagree. Their formal algorithm
optimises an abstention-bonus objective over a prespecified policy class. Our
setting instead requires the same observed coverage and the same default
action for every comparator.

We will therefore use a clearly labelled **coverage-matched adaptation**, not
claim an exact replication:

1. create 20 outer-training bootstrap policies from each of the three
   prespecified learners;
2. estimate each candidate's value using inner cross-fitted augmented
   inverse-probability weighting;
3. retain candidates within one standard error of the best training value;
4. if fewer than five remain, include the next-best candidates until five are
   available and flag the fallback;
5. calculate held-out vote disagreement as `1 - largest action vote share`;
6. accept the participants with least disagreement until the complete gate's
   held-out coverage is matched exactly; and
7. send deferred participants to the same population-level default as every
   other deferral method.

This comparator tests whether a single generic policy-multiplicity signal is
sufficient. It does not receive information about record adequacy or reference
support except insofar as those affect the fitted candidate policies.

## 5. Why no weighted fairness score is primary

A composite score could allow good performance on one group metric to obscure
a serious deficit in another. The confirmatory audit will therefore show
coverage, check failures, unsafe acceptance, accepted error, utility and regret
separately for each reportable group. Raw and evidence-standardised gaps will
also remain separate.

This decision does not reject weighted fairness measures in general. It keeps
the present paper's main claim falsifiable and prevents a choice of weights
from deciding whether the gate is declared fair.

## 6. Deterministic outer-fold assignment

Outer folds use scikit-learn's `StratifiedKFold`, stratifying on randomised
treatment only, with shuffling and the prespecified fold seed. Before
splitting, rows are ordered by the ascending string representation of their
unique row identifier and assignments are then mapped back to the supplied
order. This makes fold membership invariant to incidental file row order.
Outcomes and protected-group labels do not enter the split.

Each learner's random state is the unsigned 32-bit reduction of the first
eight bytes of the SHA-256 digest of compact canonical JSON containing
`[master_seed, run_id, fold_id, learner_id]`. The run and learner identifiers
are strings, and the fold identifier is an integer. This gives separate but
reproducible streams to the three estimators.

For continuous outcomes, the mean and sample standard deviation (`ddof=1`)
are calculated using the outer training fold only. Training outcomes are
centred and scaled before learner fitting, so held-out conditional effects and
the materiality margin are on the same training-standard-deviation scale.

## 7. What remains open

Before protocol lock, the project still requires:

1. supervisor and statistical review of the exact data-generating equations
   and coefficients in `config/simulation_scenarios.yaml`;
2. runtime tests to determine whether 1,000 Monte Carlo replicates, 200
   semi-synthetic replications and 500 full-pipeline bootstraps are feasible;
3. unit tests confirming treatment-effect sign, probability-difference scale,
   interval extraction, fold isolation and exact coverage matching; and
4. final supervisor and statistical sign-off.

Runtime tests may change computational counts through a dated precision-based
amendment. They may not be used to tune thresholds or choose methods by their
observed ranking.
