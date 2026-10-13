# Protocol v0.1: Evidence defeat for safe and fair clinical AI deferral

**Status:** Draft for supervisor and statistical review; not yet registered or
locked  
**Version date:** 13 October 2026  
**Repository:** `Meenakshi2121/evidence-defeat-clinical-ai`  
**Planned protocol tag:** `protocol-v1.0`  

## 1. Study title

**Beyond Uncertainty: A Nyāya-Inspired Evidence-Defeat Framework for Safe and
Fair Deferral in Clinical AI**

## 2. Purpose and scope

Individualised treatment models are normally forced to recommend an action for
every patient. Uncertainty-based abstention can prevent some weak
recommendations, but it compresses several distinct reasons for doubt into one
score. A recommendation may be unsafe because the patient's record is
inadequate, the patient is poorly represented by the reference data, credible
models support conflicting actions, or the estimated benefit is too uncertain
or too small to justify individualisation.

This study will test a non-compensatory evidence-defeat gate in which each of
these conditions is assessed separately. A recommendation is accepted only
when all essential checks pass; otherwise the system uses a prespecified
population-level default. The study will also examine whether safety is bought
by imposing an unequal burden of deferral on groups with poorer data or weaker
representation.

The study does **not** claim that Nyāya supplies a statistical estimator or that
the framework guarantees fairness. Nyāya supplies a bounded design rationale:
distinct defeating conditions should be represented explicitly, and failure
of an essential condition should not be cancelled by strength elsewhere. The
empirical claims will stand or fall on modern statistical validation.

## 3. Prior information and independence

The exploratory International Stroke Trial analysis and eight-replicate proof
of concept described in `prior_work_disclosure.md` were seen before this
protocol. They are development evidence and are ineligible for confirmatory
analysis. They will not be used to tune thresholds, choose favourable
estimators or select trials.

No patient-level file or method-comparison result from the confirmatory RCT
Bench source had been opened when version 0.1 was drafted. Public repository
descriptions and file paths were inspected only to establish provenance and
versioning.

## 4. Research questions

1. At the same personalisation coverage, does the complete evidence-defeat
   gate reduce materially unsafe accepted actions compared with
   uncertainty-only deferral?
2. Does each check respond to its intended failure mechanism, and does removing
   that check worsen safety in the corresponding scenario?
3. How do the complete gate, simpler deferral rules and ungated
   individualisation compare in policy regret and expected outcome?
4. How are protection from unsafe recommendations and access to
   personalisation distributed across demographic or clinically relevant
   groups?
5. Do conclusions persist across real trial-shaped covariate distributions and
   a prespecified set of real randomised trials?

## 5. Confirmatory claims and hypotheses

### 5.1 Primary hypothesis

In the prespecified defect-present, known-truth scenarios, the complete gate
will have lower material unsafe acceptance than uncertainty-only deferral at
identical coverage.

The primary estimand is the paired difference

```text
Delta_UA = UA_complete - UA_uncertainty_matched
```

For each scenario, the paired difference will first be averaged across
replicates; the scenario-level means will then be averaged with equal weight.
Lower values favour the complete gate. The primary claim requires a two-sided
95% confidence interval whose upper bound is below zero. Scenario-specific
effects and Monte Carlo standard errors will be reported whether or not the
primary claim is supported.

### 5.2 Mechanism hypothesis

Within each single-defect scenario, removing the check designed for that defect
will increase material unsafe acceptance relative to the complete gate. These
four ablation contrasts are secondary confirmatory tests and will use Holm
adjustment.

### 5.3 Fairness objective

The fairness analysis is an audit, not a parity guarantee. It will test whether
the framework protects groups from unsafe acceptance while making any unequal
loss of access to personalisation visible. Raw group differences and
evidence-standardised differences will be reported separately. No weighted
fairness composite will determine the conclusion.

## 6. Data sources and version freeze

### 6.1 Controlled simulation

Fully synthetic potential outcomes will provide known counterfactual truth and
permit controlled introduction of each evidence defect.

### 6.2 RCT-shaped semi-synthetic benchmark

Real baseline-covariate distributions and treatment allocations will be taken
from eligible RCT Bench trials, but outcomes will be generated from
prespecified mechanisms. Patient-level optimal actions and regret will
therefore remain known.

### 6.3 Real-outcome multitrial evaluation

The same eligible trial set will be analysed using the published outcomes.
This component can estimate policy utility under randomisation but cannot
establish whether a recommendation was correct for a particular patient.

### 6.4 Frozen benchmark source

The intended source is the 125-trial RCT Bench repository:

```text
Repository: https://github.com/bingkaiwang/RCT_Bench-main
Commit:    b7b927e9d9ee71b16d0645cded909b35fc23d58b
Commit date: 2026-08-28
```

The older `syl051088/RCT_Bench` repository describes a 50-trial release and is
not the frozen source for this study. Before any patient-level file is opened,
the acquisition script will record the commit, retrieval date, file list,
byte sizes and SHA-256 checksums in a machine-readable manifest. Raw data will
not be committed to this repository.

## 7. Trial eligibility and blinded screening

Screening rules will be applied without viewing gate performance, estimated
treatment-effect heterogeneity or policy comparisons.

A trial is eligible for the primary multitrial analysis when all of the
following hold:

1. it is an individually randomised, parallel-group trial;
2. the cleaned data contain exactly two analysable treatment levels;
3. at least 500 participants have non-missing treatment and primary outcome;
4. each treatment arm contains at least 100 analysable participants;
5. at least five genuine pretreatment covariates remain after identifiers,
   outcomes and post-randomisation variables are removed;
6. the primary outcome is binary or continuous, its direction can be
   established from the dictionary or primary publication, and its timepoint
   is identifiable;
7. primary-outcome missingness is no greater than 20%;
8. for a binary outcome, each treatment-by-outcome cell contains at least 20
   observations; and
9. provenance and licence permit reproducible analysis.

Multi-arm, cluster-randomised, crossover, survival-only and irreducibly ordinal
trials are excluded from the primary analysis. Any later extension to these
designs will be labelled exploratory.

The safety analysis does not require a demographic group variable. A trial
enters a group-specific fairness analysis only when a documented baseline sex,
race/ethnicity, age or other clinically relevant attribute is available and
the reporting rule in Section 15 is met.

Screening will produce a public table containing the trial identifier,
inclusion decision and one primary exclusion reason. The number of eligible
trials is an outcome of the rules, not a target to be achieved by changing
them.

## 8. Outcome orientation and notation

All outcomes will be transformed to a utility scale on which higher values are
better. For an adverse binary outcome, utility is `1 - outcome`. Continuous
outcomes will be sign-oriented using the data dictionary or primary
publication and standardised using the outer-training-fold mean and standard
deviation.

For treatment `a` in `{0, 1}`, let:

```text
mu_a(x) = E[Y(a) | X=x]
tau(x)  = mu_1(x) - mu_0(x)
```

The optimal known-truth action is `pi*(x) = 1{tau(x) > 0}`. The ungated
individualised action uses the sign of the primary treatment-effect learner's
held-out estimate.

The materiality margin is:

- **binary utility:** `delta = 0.02` absolute probability;
- **continuous utility:** `delta = 0.10` outer-training-fold standard
  deviations.

Sensitivity analyses will use `0.01` and `0.05` for binary outcomes and `0.05`
and `0.20` standard deviations for continuous outcomes. These values will not
be selected using method-performance results.

## 9. Data preparation and leakage control

All transformations will be fitted within the outer training fold and applied
unchanged to the held-out fold. Treatment and outcome will not be used to
impute baseline covariates. The preprocessing pipeline will:

1. remove identifiers and confirmed post-randomisation fields;
2. retain missingness indicators;
3. median-impute continuous variables and use an explicit missing category for
   categorical variables;
4. one-hot encode categorical variables; and
5. robustly scale continuous variables where required by the learner.

The primary analysis will use deterministic five-fold outer cross-fitting,
stratified by treatment only; held-out outcomes will not influence fold
assignment. Hyperparameter selection, support calibration and any
nuisance-model fitting will occur only inside the corresponding outer training
fold. Four additional prespecified fold seeds will be used as a
partition-stability sensitivity analysis; they will not replace the primary
split because of a more favourable result.

## 10. Individualised policy and population-level default

The primary individualised policy will use a prespecified causal-forest
treatment-effect learner. Two structurally different learners—a penalised
treatment-interaction model and a doubly robust learner with boosted trees—will
be used for the multiplicity check. Exact software versions and
hyperparameters must be written to `config/analysis.yaml` and pass simulation
recovery tests before this protocol is locked.

Within each outer training fold, the population-level default will be chosen
without held-out outcomes. Treatment 1 will be the default only when its
training-fold randomisation-aware augmented inverse-probability-weighted mean
utility exceeds that of treatment 0 by more than the applicable materiality
margin. Otherwise treatment 0 will be the default. An oracle default will be
reported only in known-truth sensitivity analyses.

## 11. Evidence-defeat gate

For held-out participant `i`, define four binary checks:

```text
D_i = record adequacy
O_i = reference support
M_i = action stability across prespecified estimators
U_i = decision certainty beyond the materiality margin

G_i = D_i * O_i * M_i * U_i
```

The gated policy is:

```text
pi_gate,i = G_i * pi_ind,i + (1 - G_i) * pi_default
```

All four checks are essential in the primary method. No weighted sum can allow
one check to compensate for another.

### 11.1 Record adequacy (`D`)

`D_i = 1` when at least 80% of the prespecified model covariates are observed
before imputation and no dictionary-defined impossible value or invalid level
is present. Generic clinical ranges will not be invented for variables whose
units or meanings are unclear. Threshold sensitivities are 90% and 100%
observed.

### 11.2 Reference support (`O`)

Support will be assessed after training-fold preprocessing using
treatment-arm-specific nearest-neighbour distances. The number of neighbours
is

```text
k = min(50, max(10, ceiling(sqrt(n_train))))
```

For each participant, the score is the larger of the mean distances to the
`k` nearest training observations in treatment arms 0 and 1. The pass
threshold is the 97.5th percentile of analogous leave-one-out scores in the
outer training fold. Sensitivities will use the 95th and 99th percentiles. This
is a covariate-support check, not a test of clinical transportability to an
external population.

### 11.3 Model multiplicity (`M`)

For each of the three prespecified estimators, classify its held-out effect as
favouring treatment 1 (`tau_hat > delta`), favouring treatment 0
(`tau_hat < -delta`) or clinically indeterminate. `M_i = 1` when:

1. at least two estimators favour the primary learner's proposed action; and
2. no estimator materially favours the opposite action.

Thus tiny sign changes inside the indifference region do not count as material
conflict.

### 11.4 Decision uncertainty (`U`)

`U_i = 1` only when the primary learner's 95% held-out interval lies entirely
above `+delta` or entirely below `-delta`. A 90% interval will be examined as a
prespecified sensitivity analysis. This within-estimator uncertainty is kept
separate from between-estimator disagreement.

## 12. Comparators

The complete gate will be compared with:

1. the population-level default for everyone;
2. ungated individualisation for everyone;
3. uncertainty-only deferral at matched coverage;
4. policy-disagreement deferral at matched coverage;
5. random deferral at matched coverage;
6. each single-check selector; and
7. each leave-one-check-out ablation.

Within every held-out fold, matched-coverage comparators will accept exactly
the same number of participants as the complete gate. Matching may use held-out
covariates, model predictions and uncertainty scores but never held-out
outcomes. Ties will be resolved by a deterministic hash of the trial and row
identifier. Random deferral will be averaged across 100 prespecified seeds.

Uncertainty-only deferral will rank participants by the primary learner's
standardised distance beyond the indifference region. Policy-disagreement
deferral will rank them by disagreement among the prespecified candidate
policies. Its exact score must be reproduced from a named published method and
fixed in `config/analysis.yaml` before protocol lock.

## 13. Known-truth estimands

Let `A_i^m` indicate that method `m` accepts an individualised recommendation.
Material unsafe acceptance is:

```text
UA_m(delta) = (1/N) * sum_i [
    A_i^m
    * 1{pi_ind,i^m != pi*_i}
    * 1{|tau_i| >= delta}
]
```

This population-denominator definition prevents a method from appearing safe
merely because it reports error only among a small accepted subset. Coverage
will always be reported beside it.

Secondary known-truth estimands are:

- personalisation coverage;
- materially wrong action rate among accepted actionable cases;
- expected utility of the complete deployed policy, including the default for
  deferred participants;
- policy regret relative to the oracle policy;
- regret relative to the population-level default; and
- the coverage-safety and coverage-regret frontiers.

## 14. Real-outcome policy evaluation

Real-outcome evaluation will use randomisation-aware augmented
inverse-probability weighting. For policy `pi`, the held-out value estimator is

```text
V_hat(pi) = (1/N) * sum_i [
    m_hat_pi(X_i)
    + 1{A_i = pi(X_i)} / e_hat(A_i | X_i)
      * (Y_i - m_hat_Ai(X_i))
]
```

Randomisation probabilities will be taken from documented trial allocation
when available; otherwise the outer-training-fold treatment proportion will be
used and the limitation recorded. Outcome regressions will be cross-fitted.
Because the propensity is supplied by randomisation, outcome regression is
used for precision rather than identification.

The gate, policies and default are all data-dependent. Final confidence
intervals for policy contrasts will therefore use a stratified participant
bootstrap that repeats the complete preprocessing, model fitting, gate
construction, coverage matching and policy evaluation pipeline. The final run
will use at least 500 bootstrap resamples. A smaller run may be used only for
runtime testing and will not be reported as inferential evidence.

Trial-specific estimates will be shown rather than hidden behind a pooled
number. Any across-trial summary will give trials equal weight in the primary
summary, with sample-size weighting and random-effects meta-analysis as
sensitivities.

## 15. Fairness and bias audit

For every reportable group, the study will present:

- personalisation coverage and deferral;
- failure rate of each check;
- material unsafe acceptance where truth is known;
- error among accepted actionable cases;
- expected policy utility and regret; and
- benefit or harm relative to the population-level default.

Pairwise differences and ratios will be reported with uncertainty intervals.
No group will be described as protected or disadvantaged solely from a
statistical difference; interpretation will consider the clinical and data
context.

A group-specific estimate is reportable when the group contains at least 100
participants and the relevant metric has at least 20 observations in its
denominator. Smaller groups will be described as unavailable for reliable
estimation rather than combined into an artificial category.

Two views will be reported:

1. **Raw distributional results**, representing the burden actually
   experienced by each group.
2. **Evidence-standardised results**, reweighting each group to the pooled
   distribution of prespecified evidence scores: record completeness, support
   distance, estimator disagreement and decision uncertainty.

Standardisation weights will be estimated by cross-fitted group-propensity
models, stabilised and truncated at the 1st and 99th percentiles. Covariate
balance after weighting will be reported. Failure to achieve an absolute
standardised mean difference below 0.10 for any evidence score will be flagged,
and the standardised comparison will not be treated as reliable.

The simulation will include both equal-defect and group-concentrated-defect
scenarios. This distinguishes unequal selector behaviour from unequal evidence
availability. A weighted fairness score is omitted from the confirmatory
analysis because a composite could conceal a serious deficit in one component.

## 16. Simulation framework

The final simulation will follow ADEMP: aims, data-generating mechanisms,
estimands, methods and performance measures will be separately documented.

The confirmatory grid will include:

- sample sizes 500 and 2,000;
- binary outcomes as primary and continuous outcomes as sensitivity;
- linear and nonlinear baseline risk;
- absent, moderate and strong treatment-effect heterogeneity;
- no defect, each single defect, combined defects and a negative-control
  scenario in which the gate has no relevant defect to detect;
- group prevalence of 20% and 50%; and
- equal versus group-concentrated evidence defects.

Defects will be generated independently of outcomes where appropriate, then in
prespecified outcome-related and group-related variants. The exact equations,
coefficients and random seeds will be stored in
`config/simulation_scenarios.yaml` before protocol lock.

The final analysis will use at least 1,000 Monte Carlo replicates per primary
scenario. Monte Carlo standard errors will accompany all simulation summaries.
If computing constraints require a change, the replicate count will be altered
by a dated amendment based on a precision calculation, not on observed method
rankings.

## 17. RCT-shaped semi-synthetic outcomes

For each eligible trial, the observed baseline covariates and randomised
treatment assignments will be retained. Potential-outcome functions will be
generated from deterministic transformations of the covariates under the same
prespecified failure mechanisms as the controlled simulation. Real trial
outcomes will not be used to choose a favourable mechanism.

Every eligible trial will be used. Results will be reported by trial and as an
equal-trial-weighted summary. At least 200 outcome replications per
trial-scenario combination are planned, subject to the same pre-result Monte
Carlo precision amendment rule as Section 16.

## 18. Missing outcomes and sensitivity analyses

Participants without the primary outcome will not enter outcome-model training
or policy-value estimation. They may contribute to covariate-only support
calibration if doing so does not leak outcome availability. The primary
analysis assumes outcomes are missing at random conditional on treatment and
baseline covariates. Sensitivities will include inverse-probability-of-
observation weighting and a bounded pattern-mixture analysis when missingness
exceeds 5%.

Prespecified sensitivities also include:

- alternative materiality margins;
- 90% rather than 95% decision intervals;
- 95th and 99th percentile support thresholds;
- 90% and 100% record-completeness thresholds;
- four alternative cross-fitting partitions;
- control-for-all and oracle defaults where meaningful; and
- equal-trial, sample-size and random-effects aggregation.

Sensitivity analyses cannot replace the primary specification in the abstract
or conclusion.

## 19. Falsification and interpretation rules

The central safety claim will be rejected or materially weakened when any of
the following occurs:

1. the complete gate does not reduce material unsafe acceptance relative to
   uncertainty-only deferral at matched coverage;
2. the apparent benefit disappears when coverage is matched;
3. a targeted check's removal does not worsen performance in the defect it is
   meant to detect;
4. improvements are confined to a single favourable data-generating mechanism
   or trial-shaped covariate distribution;
5. reduced unsafe acceptance is accompanied by greater overall policy regret
   without a clearly reported safety-utility trade-off; or
6. safety gains systematically move an excessive deferral or harm burden to a
   poorly represented group.

The framework may therefore be supported as a safety selector without being
superior as a treatment policy. These are separate claims and will remain
separate in the manuscript.

## 20. Reproducibility, amendments and reporting

Before confirmatory analysis:

1. all unresolved fields in this protocol will be completed;
2. `config/analysis.yaml` and `config/simulation_scenarios.yaml` will be frozen;
3. unit, invariant and leakage tests will pass;
4. the protocol will receive supervisor and statistical review;
5. a dated `protocol-v1.0` tag will be created; and
6. the protocol and repository commit will be registered on OSF.

Any later change will be recorded in `protocol/amendments.md` with its date,
reason, affected analyses and whether outcomes or method comparisons had been
seen. Deviations will be reported in the paper.

Code will generate every final table and figure from immutable result files.
Random seeds, package versions, data checksums, exclusions and run fingerprints
will be archived. Reporting will use the applicable TRIPOD+AI items, simulation
reporting guidance and journal requirements without implying that this methods
study is a clinical prediction-model validation.

## 21. Decisions still required before lock

Version 0.1 deliberately leaves four matters open for review:

1. exact causal-learner implementations and hyperparameters;
2. the published policy-disagreement comparator and its score;
3. complete simulation equations and scenario coefficients; and
4. confirmation that the planned computational budget supports the bootstrap
   and Monte Carlo replicate counts.

These decisions must be made before any confirmatory outcome analysis and may
not be selected because they improve the framework's observed result.
