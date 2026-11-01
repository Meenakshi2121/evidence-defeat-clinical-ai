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

## 7. Population default and policy-value nuisance regressions

The population default is estimated separately inside each outer training
fold. Separate outcome regressions are fitted for treatment arms 0 and 1 using
the prespecified histogram-gradient-boosting model. Predictions for the
outer-training rows are generated by three-fold inner cross-fitting. These
predictions enter randomisation-aware augmented inverse-probability-weighted
estimates of the two population treatment values. Treatment 1 becomes the
default only when its estimated advantage strictly exceeds the applicable
materiality margin; otherwise treatment 0 remains the conservative default.

For held-out policy evaluation, the two outcome regressions are refitted on
the complete outer training fold and applied to its held-out rows. Documented
randomisation probability is used when supplied; otherwise the treatment-1
fraction in that outer training fold is used and recorded. Propensities are
subject to the prespecified clipping bounds. Held-out outcomes enter only the
final augmented inverse-probability-weighted score, after the gate, default and
all policy actions have been fixed.

Influence-function standard errors conditional on the fitted policies are
useful software diagnostics, but are not the paper's final inference. Final
confidence intervals will use the prespecified participant-level bootstrap
that repeats the entire data-dependent pipeline.

## 8. Random deferral and known-truth metric signs

Random deferral is repeated 100 times. For repetition `r`, its unsigned 32-bit
seed follows the locked model-seed hash rule with learner identifier
`random_deferral` and repetition identifier in the fold position. Within each
outer fold, all rows receive an equal ranking score and the seeded canonical
identifier hash breaks the tie. This gives a deterministic, row-order-invariant
pseudo-random sample with exactly the complete gate's acceptance count.

Material unsafe acceptance uses the complete simulated population as its
denominator. The accepted-actionable error rate uses accepted, materially
actionable rows as its denominator and is unavailable when that denominator is
zero. Known-truth policy utility is the mean potential-outcome utility under
the deployed action. Oracle regret is `oracle utility - deployed utility`.
Regret relative to the default is `default utility - deployed utility`, so a
positive value means harm relative to the default and a negative value means
improvement. Utility gain versus default is also retained with the opposite
sign to make interpretation explicit.

For continuous outcomes, the row-level materiality threshold on the original
outcome scale is the prespecified standard-deviation margin multiplied by the
sample standard deviation of that row's outer training fold.

## 9. What remains open

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

## 10. Proof-of-concept execution and result concealment

The Stage A runner expands only the scenarios and replicate identifiers in
`config/poc.yaml`. It refuses to run from a dirty worktree and records the full
Git commit plus SHA-256 hashes of all three configuration documents, generated
simulation arrays and fold assignments. Every replicate runs in a separate
process so the recorded peak resident memory is not inherited from an earlier
model fit.

Stage A reports deliberately omit coverage, policy values, unsafe-acceptance
rates, contrasts and method rankings. They retain only pass/fail invariant
statuses, elapsed time, peak process memory and environment fingerprints. This
allows feasibility and implementation failures to be examined without using
diagnostic scientific results to tune the gate.

## 11. Scikit-learn compatibility amendment after Stage A

On 14 October 2026, after the disclosure-safe Stage A run and before any
scientific result was examined, the binary interaction model specification was
updated from `penalty: "l2"` to `l1_ratio: 0.0`. Scikit-learn 1.8 deprecates the
former parameter spelling and identifies the latter as its direct L2
replacement. The regularisation strength (`C: 1.0`), solver, model class and
all other statistical choices remain unchanged. Warning suppressions used by
the software tests were removed, and a test now asserts the replacement
parameter explicitly.

Because this edit changes the analysis-configuration hash and code commit, the
Stage A diagnostic will be repeated before later feasibility stages. The
earlier Stage A reports contained only invariant statuses and resource usage;
they were ineligible for paper effect estimates.

## 12. Completed Stage A diagnostic record

The corrected Stage A diagnostic was run on 14 October 2026 at Git commit
`feb2a99ea9f37297e2a7fddcd3b6b54fcdb95b89`. All 12 planned runs completed and
all 12 required invariants passed in every run. The run covered the clean
control, four single-defect scenarios and the combined-defect scenario at
`n=500`, with replicate identifiers 0 and 1. No scientific estimate, method
ranking or policy-performance comparison was exposed. Stage A therefore
establishes software operability only; it is not evidence for the primary
hypothesis.

## 13. Exact implementation of the policy-disagreement comparator

Before Stage B timing and before viewing any method comparison, the following
details were fixed on 14 October 2026:

1. each candidate bootstrap resamples separately within treatment arms;
2. candidate actions used for training-fold value estimation are themselves
   cross-fitted on the same deterministic inner folds used for nuisance
   prediction;
3. each candidate is valued using its row-level inner cross-fitted augmented
   inverse-probability-weighted contributions;
4. “within one standard error of the best” means a candidate value is at least
   the best candidate's estimated value minus the best candidate's own
   standard error;
5. if this retains fewer than five candidates, candidates are added in
   descending training-value order, with fixed candidate order breaking exact
   ties;
6. retained candidates are refitted on treatment-stratified bootstrap samples
   of the complete outer training fold before voting on outer-heldout rows;
7. the disagreement score is one minus the larger binary action-vote share;
   and
8. the lowest-disagreement rows are accepted to exactly match the complete
   gate's count separately within each outer fold.

The outer-heldout outcome is not supplied to candidate fitting, retention or
coverage matching. It enters only the later policy-evaluation score after all
actions have been fixed.

## 14. Results-informed separation of evidence defeat from uncertainty

C000 screening exposed an architectural redundancy: the binary decision-
certainty condition failed for 94.08% of clean-control rows and at still higher
rates in the defect scenarios. Complete-gate coverage fell to 0.38%--5.50%, so
the framework was nearly a default-only policy and could not be distinguished
meaningfully from its uncertainty-only comparator.

Candidate C001 therefore keeps record adequacy, reference support and model
multiplicity as the essential non-compensatory conditions, but makes decision
uncertainty non-essential:

```text
G_i(C001) = D_i * O_i * M_i.
```

`U_i` is still calculated for diagnostic reporting. The uncertainty-only
method continues to rank rows by the prespecified continuous certainty score
and is matched exactly to C001 coverage within each outer fold. This is the
only C001 analysis change; learner specifications, thresholds, default policy,
estimands, scenarios and fairness procedures remain fixed. The decision is
explicitly results-informed Stage C development and supplies no confirmatory
evidence for C001.

## 15. Hierarchical graded uncertainty for C002

C001 finalist robustness showed a boundary condition that the three-check
architecture could not resolve alone. It was safer than uncertainty-only
deferral in the pooled defect-present runs, but worse in the no-defect,
absent-heterogeneity scenario. Candidate C002 is therefore explicitly
results-informed and separates two questions:

1. Is the recommendation's evidential basis defeated?
2. If it is not defeated, how strong is the treatment-effect signal?

The first question remains non-compensatory:

```text
H_i = D_i * O_i * M_i.
```

The second uses the existing continuous uncertainty ranking score:

```text
S_i = (abs(tau_hat_i) - delta) / SE_hat_i.
```

Within each held-out outer fold, `U_i(0.80)` selects the highest-ranked 80% of
`S_i`; exact ties use the locked SHA-256 rule. C002 accepts individualisation
only when both stages pass:

```text
G_i(C002) = H_i * U_i(0.80).
```

The ranking is computed without held-out outcomes. Its threshold is calibrated
within the held-out fold by rank, not by inspecting policy performance. A high
uncertainty score cannot rescue failed record adequacy, reference support or
model multiplicity. The matched uncertainty-only comparator uses the same
score but no evidence-defeat restriction and is reduced to C002's exact final
coverage within each fold.

The 0.80 fraction is a Stage C design choice made after C001 and is not a
universal clinical constant. It is fixed before any C002 run, will not be
tuned on C002 outcomes, and must be independently validated if C002 is later
frozen. Fairness remains a separate safety-and-access audit; no group weight or
weighted fairness score changes acceptance.
