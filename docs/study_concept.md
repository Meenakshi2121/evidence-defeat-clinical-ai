# Study concept

## 1. Why a new study

Individualised treatment models are ordinarily forced to recommend an action
for every patient. Abstention addresses this problem, but a single uncertainty
score does not necessarily distinguish why a recommendation may be unreliable.
For example, a model can be confident when a required patient field is
implausible, when the patient lies outside the reference population, or when a
different credible estimator recommends the opposite action.

The new study therefore asks a general question:

> When should clinical AI not personalise treatment, and can a structured
> evidence-defeat gate reduce unsafe recommendations without hiding unequal
> access to personalisation?

This question is broader and more defensible than attempting to prove that one
gate improves outcomes in one historical aspirin trial.

## 2. Proposed contribution

The paper will contribute:

1. a formal non-compensatory gate for four distinguishable evidence defects;
2. a safety evaluation based on materially wrong accepted actions and policy
   regret under known counterfactual truth;
3. matched-coverage comparisons with uncertainty-only abstention, policy-
   disagreement abstention and random deferral;
4. ablations showing which check contributes under which failure mechanism;
5. a fairness analysis that separates protection from unsafe action from access
   to individualisation; and
6. multitrial validation rather than reliance on a favourable single dataset.

## 3. Relationship to Nyāya

Nyāya is used as a bounded source of design logic. Its treatment of defeating
flaws in reasoning motivates two propositions:

1. different evidential defects should be represented separately; and
2. failure of an essential evidential condition should not be cancelled by
   strength elsewhere.

Possible interpretive parallels include an unestablished reason in the case,
an evidential relation not established for comparable cases, and an inference
counterbalanced by a credible opposing inference. These parallels will be
checked with authoritative Nyāya scholarship before manuscript claims are
fixed. The algorithms themselves will be justified by modern statistical and
clinical reasoning, not by philosophical analogy alone.

## 4. Formal architecture

Let `pi_ind(X)` be an individualised treatment policy and `pi_default` the
prespecified population-level policy. Define:

```text
D_i = record-adequacy check
O_i = overlap/reference-support check
M_i = action-stability check across prespecified models
U_i = uncertainty/clinical-indifference check

G_i = D_i x O_i x M_i x U_i

pi_gate,i = G_i pi_ind,i + (1 - G_i) pi_default
```

The gate is deliberately non-compensatory. The four-check gate is the proposed
primary method; three-check and single-check variants are ablations rather than
post-hoc alternatives.

## 5. Strongest validation design

### 5.1 Controlled simulation

Use a prespecified factorial design varying:

- treatment-effect strength and functional form;
- reference sample size;
- outcome prevalence;
- record missingness and implausibility;
- overlap/support shift;
- model misspecification and multiplicity;
- group concentration of evidence defects; and
- quality of the default policy.

Potential-outcome risks are known, so materially wrong actions and policy regret
are directly observable.

### 5.2 RCT-shaped semi-synthetic benchmark

Screen the frozen version of RCT Bench using rules fixed before accessing trial
outcomes. For every eligible trial, retain real baseline-covariate distributions
and treatment allocation, then generate calibrated potential outcomes with
known heterogeneous effects. This tests the framework across realistic
covariate structures without pretending that real patient-level counterfactuals
are observed.

All eligible trials will be used. Trials will not be chosen because they give
favourable gate results.

### 5.3 Real-outcome multitrial evaluation

Using the same eligible trial set, evaluate population-level, ungated and gated
policies using nested cross-fitting and randomisation-aware doubly robust
estimators. Real-outcome analyses cannot establish patient-level correctness;
they estimate policy risk/value and external robustness across trials.

The population-level default will be defined from training data or external
trial evidence according to a rule fixed before evaluation. It will not be
chosen on the held-out outcomes.

## 6. Prespecified trial eligibility

The draft eligibility rules are:

1. individually randomized trial;
2. treatment contrast is binary or reducible to one clinically coherent binary
   comparison without inspecting treatment-effect heterogeneity;
3. at least 500 analysable participants;
4. at least five genuine pretreatment covariates;
5. outcome timing and preferred direction are recoverable from metadata or the
   primary publication;
6. no post-randomisation variable is used as a predictor;
7. outcome missingness does not exceed a threshold fixed before screening;
8. at least one usable group attribute such as age or sex for the fairness
   audit; and
9. licence and provenance permit reproducible analysis.

The final threshold and adjudication rules will be registered. Screening will
be logged with one exclusion reason per trial and performed without viewing
method-comparison results.

## 7. Comparators

- population-level default;
- ungated individualisation;
- uncertainty-only abstention at matched coverage;
- disagreement among near-optimal policies at matched coverage;
- random deferral at matched coverage;
- each single-check selector;
- leave-one-check-out ablations;
- the complete non-compensatory gate.

## 8. Primary outcomes

With known truth, the primary outcome is material unsafe acceptance:

```text
UA_m(delta) = mean[A_i^m x 1{pi_ind,i != pi*_i and |tau_i| >= delta}]
```

The primary comparison is the complete gate minus uncertainty-only abstention at
identical coverage. Secondary outcomes are true policy regret, risk relative to
the default, coverage, error among accepted recommendations and the full
coverage--safety frontier.

The clinical materiality margin `delta` will be fixed before validation and
varied only in prespecified sensitivity analyses.

## 9. Fairness and bias analysis

Fairness is not reduced to one score. For each protected or clinically relevant
group, report:

- personalisation coverage and deferral;
- failure of each evidence check;
- material unsafe acceptance;
- error among accepted recommendations;
- policy regret and benefit relative to the default.

Two views are required:

1. **raw distributional outcomes**, showing the actual burden experienced by
   each group; and
2. **evidence-standardised outcomes**, giving groups the same distribution of
   evidence states to distinguish unequal evidence availability from unequal
   selector behaviour conditional on evidence.

A weighted fairness composite may be reported only as a secondary sensitivity
analysis with all components and weights shown. It will not determine the main
conclusion.

## 10. Falsification conditions

The central claim will be weakened or rejected if:

- the complete gate does not reduce material unsafe acceptance relative to
  uncertainty-only abstention at matched coverage;
- reductions arise solely from lower coverage;
- the corresponding ablation does not worsen performance in its target failure
  scenario;
- the result fails across real trial-shaped covariate distributions; or
- safety gains systematically transfer an excessive deferral or regret burden
  to an already poorly represented group.

If the gate improves safety but worsens policy value, the result will be
reported as a safety--utility trade-off, not as overall superiority.

## 11. Intended positioning

The principal novelty is not abstention itself. Recent policy-learning work
already studies abstention using disagreement among near-optimal policies. The
new contribution is structured evidence defeat beyond uncertainty, combined
with non-compensatory logic, an explicit default policy, multitrial validation
and a safety--access fairness audit.

The preferred initial target is the *Journal of Healthcare Informatics
Research*. A stronger methods result could justify submission to *BMC Medical
Research Methodology* or *JAMIA*.

