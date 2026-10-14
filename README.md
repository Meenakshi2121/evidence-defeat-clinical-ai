# Evidence Defeat for Responsible Clinical AI

Research code and protocols for a general framework that decides when an
individualised treatment recommendation should be accepted and when it should
defer to a safer population-level policy or human review.

## Working paper

**Beyond Uncertainty: A Nyāya-Inspired Evidence-Defeat Framework for Safe and
Fair Deferral in Clinical AI**

The project is not an aspirin paper and is not tied to a single dataset. It will
evaluate a general non-compensatory gate across controlled simulations,
semi-synthetic benchmarks based on real randomized-trial covariates, and a
prespecified set of real randomized trials.

## Central research question

Does checking distinct evidence defects---record adequacy, reference support,
model multiplicity and decision uncertainty---reduce materially unsafe accepted
recommendations compared with uncertainty-only abstention at the same coverage,
and how is the resulting burden of deferral distributed across groups?

## Planned gate

For patient `i`:

```text
G_i = D_i AND O_i AND M_i AND U_i
```

- `D`: essential record information is adequate;
- `O`: the patient lies within supported covariate/overlap regions;
- `M`: prespecified credible models agree on the recommended action;
- `U`: uncertainty does not cross a prespecified clinical indifference margin.

Every check is essential. Strength in one check cannot compensate for failure
of another. The individualised action is used when the gate passes; otherwise
the system defers to a prespecified population policy or human review.

## What is novel

Existing abstention methods primarily use predictive uncertainty or disagreement
among near-optimal policies. This project tests a broader evidence-defect
taxonomy, non-compensatory decision logic, an explicit default policy, and a
joint safety-and-access fairness audit.

Nyāya motivates the logic of separately identifiable defeating conditions. It
does not replace causal inference, statistical validation or clinical evidence.

## Validation layers

1. **Controlled simulation:** counterfactual truth is fully known.
2. **Multitrial semi-synthetic benchmark:** real RCT covariates with generated
   potential outcomes and known individual truth.
3. **Real RCT evaluation:** held-out, doubly robust policy evaluation across all
   trials meeting criteria fixed before outcomes are analysed.
4. **Fairness audit:** raw and evidence-standardised group differences in
   deferral, unsafe acceptance and policy regret.

## Current status

Design stage only. No data from the proposed multitrial validation have been
analysed. The protocol and eligibility rules must be reviewed and registered
before outcome analysis begins.

Earlier exploratory work using the International Stroke Trial informed the
research question but will not be treated as independent validation. See
`protocol/prior_work_disclosure.md`.

## Repository structure

```text
config/       Locked machine-readable specifications
data/         Data access instructions; no patient data in Git
docs/         Research concept and design rationale
protocol/     Eligibility rules, preregistration and deviations
src/          Reusable implementation
tests/        Unit, integration and simulation checks
results/      Aggregate, disclosure-safe outputs only
```

## Reproducibility rule

No confirmatory analysis will be run until the protocol is tagged and
registered. Every post-lock change must be dated and classified as
confirmatory, sensitivity or exploratory.

## Pre-lock proof of concept

After the diagnostic runner has been committed and the worktree is clean:

```bash
poetry install
poetry run evidence-defeat-poc plan
poetry run evidence-defeat-poc smoke
```

The first command installs the repository's command-line entry point. `plan`
validates and displays the frozen 12-run Stage A grid. `smoke` executes each
replicate in an isolated process and writes ignored diagnostic reports under
`results/poc/stage-a/`. These reports contain invariant statuses, runtime,
memory and reproducibility fingerprints only. They intentionally conceal
policy performance and method rankings.

