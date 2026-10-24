# Simulation design v0.1

**Status:** Draft for supervisor and statistical review before protocol lock
**Date:** 14 October 2026
**Machine-readable specification:** `config/simulation_scenarios.yaml`

## 1. Purpose

The controlled simulation asks whether the evidence-defeat gate protects
against unsafe accepted treatment recommendations when individual
counterfactual truth is known. It is not designed to guarantee a favourable
result. In particular, the model-multiplicity and decision-uncertainty checks
may add little or may cause unnecessary deferral; those are falsifiable
possibilities.

The primary comparison is the complete four-check gate versus
uncertainty-only deferral at exactly matched coverage. The clean scenario and
all proof-of-concept runs are excluded from that superiority claim.

## 2. Common data-generating mechanism

For participant `i`, generate ten independent baseline covariates

```text
X_ij ~ Normal(0,1),  j = 1,...,10,
S_i  ~ Bernoulli(q),
A_i  ~ Bernoulli(0.5).
```

`S` is the group variable, is always observed and is available to the fitted
models. It has no direct prognostic or treatment-effect role in the primary
fairness null, so equal-defect scenarios have equal evidence and outcome
mechanisms by construction. A secondary robustness scenario adds a prognostic
group coefficient of 0.20. Treatment is independent of covariates, group
membership and defect flags.

For binary utility, define either a linear or nonlinear baseline function:

```text
eta_linear = -0.40 + 0.45 X1 - 0.35 X2 + 0.25 X3
             + 0.20 X4

eta_nonlinear = -0.40 + 0.55 sin(X1)
                + 0.35 (X2^2 - 1)/sqrt(2)
                - 0.40 X3 X4 + 0.25 I(X5 > 0)

mu_0(X) = 0.10 + 0.70 expit(eta)
mu_1(X) = clip(mu_0(X) + tau(X), 0.01, 0.99)
Y | A,X ~ Bernoulli(mu_A(X)).
```

The transformation keeps baseline risks away from zero and one while allowing
clinically material positive and negative risk differences. After clipping,
the realised conditional treatment effect `tau_true(X) = mu_1(X) - mu_0(X)`
is retained as truth; the pre-clipping target is never used for scoring.

For continuous utility, the corresponding baseline predictor is multiplied by
0.50 and

```text
Y = mu_A(X) + epsilon,   epsilon ~ Normal(0,1).
```

Within each outer fold, the observed outcome, true conditional means and true
effect are divided by the outer-training outcome standard deviation. This
matches the scale on which the continuous materiality margin is applied.

## 3. Baseline treatment-effect surfaces

Define

```text
h_linear = (X1 + X2) / sqrt(2)

h_nonlinear = [sin(X1) + 0.5 (X2^2 - 1)/sqrt(2) + 0.5 X3 X4]
              / sqrt((1-exp(-2))/2 + 0.25 + 0.25).
```

The binary treatment-effect surfaces are:

```text
absent:    tau = 0.04
moderate:  tau = clip(0.01 + 0.05 h_linear, -0.12, 0.12)
strong:    tau = clip(0.01 + 0.09 h_nonlinear, -0.18, 0.18).
```

Continuous-outcome effects are four times the corresponding binary surface.
This is a prespecified scale conversion, not a result-dependent calibration.

## 4. Evidence-defect mechanisms

### 4.1 Record inadequacy

Generate `R_D` with overall prevalence 0.20. When `R_D=1`, the true treatment
effect is `+0.08` if the latent complete `X1 > -0.50` and `-0.08` otherwise.
Only after outcome truth is fixed, set `X1`, `X2` and `X3` to missing. The
record then has 70% observed clinical covariates and conceals the value that
determines the optimal action. Continuous effects are four times these values.

The primary record-defect scenario is outcome-related because it tests whether
record adequacy adds protection beyond a model interval. A prespecified
outcome-independent missingness variant is included as a negative-control
sensitivity analysis.

### 4.2 Limited reference support

Generate `R_O` with overall prevalence 0.02. For `R_O=1`, add 4.0 to each of
`X1`, `X2` and `X3`, creating a small separated covariate component, and set
the true binary treatment effect to `-0.08` (`-0.32` for continuous utility).
The main-population relation at these covariate values suggests the opposite
direction. The 2% prevalence was fixed before fitting because it lies inside
the 2.5% tail targeted by the primary support threshold and still gives an
expected ten affected observations when `n=500`.

### 4.3 Model multiplicity

Define `R_M = I[X5 > Phi^-1(0.75)]`, giving prevalence 0.25. Within this
region, set the binary effect to `+0.10` when `X1*X2 > 0` and `-0.06`
otherwise. This quadrant interaction is not available to the prespecified
additive treatment-interaction model, but it can be represented by the two
tree-based learners. The scenario is intended to create a genuine opportunity
for model disagreement; it does not assume in advance that disagreement will
identify errors by the primary learner.

### 4.4 Decision uncertainty

Define

```text
R_U = I[|X6| <= Phi^-1(0.65)],
```

which has prevalence 0.30. Outside that region, the binary effect is `+0.08`
when `X1 >= 0` and `-0.08` otherwise. Within it, the corresponding effects are
`+0.03` and `-0.03`. Thus the optimal direction exists and the effect is
material under the primary 0.02 margin, but it is deliberately close to that
margin. Continuous values are again four times the binary values.

### 4.5 Combined defects

The combined scenario uses prevalences 0.15, 0.02, 0.20 and 0.25 for record,
support, multiplicity and uncertainty defects, respectively. Flags are
retained separately. When effect rules overlap, the fixed priority is support,
record, multiplicity, uncertainty and then the base moderate surface. Record
missingness and the support shift are both applied even when another rule
determines the final true effect.

## 5. Group allocation and fairness scenarios

Equal-allocation scenarios use the same defect prevalence in both groups. In
group-concentrated scenarios, the affected group has four times the defect
probability of the reference group while the overall prevalence is preserved:

```text
p0 = r / [(1-q) + 4q]
p1 = 4 p0,
```

where `r` is the target overall prevalence and `q=P(S=1)`. For deterministic
normal regions, group-specific normal quantiles implement these probabilities.

This design separates two questions. Equal-allocation scenarios test whether
the selector itself creates a group disparity when evidence quality is equal.
Group-concentrated scenarios test whether the audit exposes unequal access to
personalisation when evidence defects are genuinely distributed unequally.
Evidence standardisation may explain such a gap; it cannot erase the raw
burden.

## 6. Prespecified grids

The primary safety grid contains ten scenarios: five defect types (the four
single defects and the combined defect) at `n=500` and `n=2,000`. All use a
binary outcome, nonlinear baseline risk, moderate treatment-effect
heterogeneity, group prevalence 20% and equal defect allocation. Scenarios
receive equal weight in the primary contrast.

The check-specific mechanism tests reuse the eight single-defect scenarios.
The corresponding leave-one-check-out gate is compared with the complete gate,
with Holm adjustment across the four check-level hypotheses.

Two clean scenarios at `n=500` and `n=2,000` test unnecessary deferral and are
excluded from the primary superiority contrast. Secondary fairness scenarios
cross group prevalence 20% and 50%, equal versus group-concentrated allocation,
and record, support and combined defects at `n=2,000`. One-factor-at-a-time
robustness scenarios cover linear baseline risk, absent and strong
heterogeneity, continuous outcomes and outcome-independent missingness.

## 7. Estimands and interpretation

The optimal action is `I[tau(X)>0]`. An action is materially actionable when
`|tau(X)|` is at least the applicable margin. The primary outcome remains
material unsafe acceptance on the population denominator. Coverage, accepted
error, deployed-policy utility, oracle regret, regret relative to the default
and each check's failure rate are mandatory companion results.

Check sensitivity and specificity for generated defect flags are diagnostic
mechanism measures, not substitutes for the policy-safety estimand. A check can
recover its flag accurately and still fail to improve decisions.

## 8. Monte Carlo precision and prohibited adaptation

The planned minimum is 1,000 replicates for each primary scenario. Every
summary will include a Monte Carlo standard error. A diagnostic variance pilot
may alter the count through a dated amendment using variance and runtime only.
The target Monte Carlo standard error is 0.0025 for the primary paired contrast
and 0.005 for secondary summaries, with a maximum of 5,000 replicates before
new statistical review.

No scenario, coefficient, threshold or estimator may be changed because the
complete gate performs poorly. Proof-of-concept results cannot appear as
confirmatory evidence. Any repair following a software or recovery-test
failure must be documented before the protocol is locked and all diagnostic
runs must then be repeated.
