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

Does checking distinct evidence defects---record adequacy, reference support
and model multiplicity---reduce materially unsafe accepted recommendations
compared with uncertainty-only abstention at the same coverage, and how is the
resulting burden of deferral distributed across groups?

## Planned gate

For patient `i`:

```text
H_i = D_i AND O_i AND M_i
G_i = H_i AND U_i(0.80)
```

- `D`: essential record information is adequate;
- `O`: the patient lies within supported covariate/overlap regions;
- `M`: prespecified credible models agree on the recommended action;

Every evidence check is essential: uncertainty cannot rescue a failure of
`D`, `O` or `M`. Among rows that remain eligible, `U(0.80)` retains those in
the highest 80% of the prespecified continuous uncertainty ranking within each
held-out fold. The individualised action is used only when the hierarchical
gate passes; otherwise the system defers to a prespecified population policy
or human review. An uncertainty-only policy remains the external comparator at
the exact final coverage.

## What is novel

Existing abstention methods primarily use predictive uncertainty or disagreement
among near-optimal policies. This project tests a broader evidence-defect
taxonomy, non-compensatory decision logic, an explicit default policy, and a
joint safety-and-access fairness audit.

Nyāya motivates the logic of separately identifiable defeating conditions. It
does not replace causal inference, statistical validation or clinical evidence.

## Development and validation layers

1. **Diagnostic feasibility:** disclosure-safe software, runtime and memory
   checks; no scientific performance is exposed.
2. **Controlled development:** the framework may be improved using a dedicated
   synthetic development bank, with every candidate and result retained.
3. **Development freeze:** one candidate, commit and configuration are reviewed,
   registered and tagged before validation data are opened.
4. **Independent validation:** untouched controlled simulations, real RCT
   covariates with generated outcomes, and held-out real RCT evaluation.
5. **Fairness audit:** raw and evidence-standardised group differences in
   deferral, unsafe acceptance and policy regret, without a weighted composite.

## Current status

Stage A software diagnostics and Stage B computational feasibility checks have
passed; neither stage exposed scientific performance. Baseline candidate
`C000` completed 60 exploratory Stage C screening runs and was rejected because
its binary decision-certainty check collapsed coverage. Results-informed child
candidate `C001` then completed 60 three-check screening runs, 30 dedicated
fairness-stress runs and 25 finalist-robustness runs without software or
invariant failures.

C001's robustness result was mixed. Across all 25 runs, its matched-coverage
unsafe-acceptance contrast against uncertainty-only deferral was -0.003760
(95% confidence interval -0.015449 to 0.007929). In the 20 runs containing
generated evidence defects, the contrast favoured C001 (-0.014950; -0.023419
to -0.006481), but in the five no-defect runs it favoured uncertainty-only
deferral (0.041000; 0.027083 to 0.054917). Evidence standardisation failed its
balance criterion in every robustness run, so standardised fairness gaps are
not interpreted. The raw coverage gap also remained an adverse access signal.

C001 is therefore not frozen as the final framework. It is recorded as a
rejected final architecture. Results-informed child candidate `C002` combines
C001's three non-compensatory evidence checks with a prespecified graded
uncertainty filter retaining the highest-ranked 80% within each held-out fold.
C002 has now completed all 35 authorised revision-screening runs. At exactly
matched coverage, its material-unsafe-acceptance contrast against uncertainty-
only deferral was -0.009171 (95% confidence interval -0.013435 to -0.004908)
overall and -0.010440 (-0.014358 to -0.006522) in the 25 defect-present runs.
Mean scenario coverage ranged from 43.16% to 57.04%, and deployed utility was
0.003882 (0.002798 to 0.004966) above the population default overall.

C002 subsequently completed all 30 fresh revision-fairness-stress runs. Its
matched-coverage material-unsafe-acceptance contrast against uncertainty-only
deferral was -0.013967 (95% confidence interval -0.019558 to -0.008375), and
all six scenario means favoured C002. Mean coverage was 48.71%. C002 improved
utility over matched random deferral and the population default, but its
utility difference from uncertainty-only deferral was small and uncertain
(0.000124; -0.000229 to 0.000476).

The fairness result is a safety--access trade-off rather than a parity claim.
Group 1 received less individualised access under C002 but its raw unsafe-
acceptance disadvantage under uncertainty-only deferral was removed. Evidence
standardisation met its balance criterion in all 15 runs with 50% group
prevalence and none of the 15 runs with 20% prevalence. In balanced runs, the
standardised unsafe-acceptance gap was compatible with no residual group-1
disadvantage; the failed 20% balance diagnostics and raw access burden still
prohibit claims of proven fairness.

C002 subsequently completed all 25 fresh revision-finalist-robustness runs.
Its matched-coverage material-unsafe-acceptance contrast against uncertainty-
only deferral was -0.010160 (95% confidence interval -0.014963 to -0.005357)
overall and -0.011825 (-0.016551 to -0.007099) in the 20 defect-present runs.
All five scenario means favoured C002. Mean coverage was 45.24%, and every
scenario remained above the prespecified 25% development floor.

The robustness utility difference from uncertainty-only deferral was small and
uncertain (-0.000224; -0.001065 to 0.000617). C002 exceeded matched random
deferral by 0.002819 (0.000348 to 0.005291) and the population default by
0.007747 (0.003344 to 0.012150), but was 0.005906 lower than ungated
individualisation (-0.009837 to -0.001976). The no-defect mean met the recorded
development boundary, but four of its five runs slightly favoured uncertainty-
only deferral and one run strongly favoured C002. This seed sensitivity must be
tested in independent validation.

C002 was frozen unchanged as the final development candidate in public tag
`protocol-v1.0`. The subsequent blinded Stage E variance pilot completed all
ten scenario groups and 250 pilot replicates without exposing effect direction,
method rankings or group differences. The prespecified variance rule selected
the protocol minimum of 1,000 Stage F replicates per primary scenario. This is
a precision-planning result, not evidence that C002 is effective. Stage F has
not yet been run, and no confirmatory result exists.

The dated development/validation boundary is defined in
`protocol/development_validation_amendment_v0.2.md`. Protocol v0.1 remains as
the historical pre-amendment record. C002's results-informed design and fresh
development boundary are fixed in
`protocol/c002_development_amendment_v0.3.md`.

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

Development is allowed only on its named synthetic bank and is fully logged.
No independent validation will be run until one candidate is frozen, the
protocol is tagged and registered, and validation sources remain untouched.
Every post-freeze change must be dated and classified; a framework changed
after validation requires new independent evidence.

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

Stage B is deliberately run one timing unit at a time:

```bash
poetry run evidence-defeat-poc timing-plan
poetry run evidence-defeat-poc timing-run --timing-id full_comparator_n500
```

The first timing unit is reviewed before authorising the `n=2,000` comparator
and five bootstrap timing units. Stage B reports contain resource usage,
invariant statuses and reproducibility fingerprints only.

## Development and prospective validation status

Stage C runs expose scientific simulation results and therefore require a
clean, committed worktree. C001 and C002 completed their authorised development
tiers and must not be rerun or tuned. C002's results, adverse findings and
selection rationale remain in the append-only development record.

Stage D froze C002, the primary estimand, success rule and validation grid in
`protocol-v1.0`. Stage E then used only blinded paired-contrast variances to
lock the Stage F count at 1,000 replicates in each of ten primary cells. The
completion record is `protocol/stage_e_variance_record_v1.0.md`. The next step
is the one-time 10,000-run Stage F confirmatory simulation. Its resumable,
complete-first-unblinding procedure is specified in
`protocol/stage_f_execution_v1.0.md`. Real and semisynthetic trial evaluations
remain later validation layers and are not replaced by simulation.

## Stage F confirmatory execution

Stage F may run only from the exact public `stage-f-runner-v1.0` tag and an
otherwise clean repository. Initialise the immutable run identity, then execute
one scenario at a time with resumable per-replicate checkpoints:

```bash
poetry run evidence-defeat-confirm plan
poetry run evidence-defeat-confirm init
poetry run evidence-defeat-confirm run-scenario \
  --scenario-id confirmatory_v1__record_adequacy_n500 \
  --max-new-runs 10
poetry run evidence-defeat-confirm status
```

The summary command remains locked until all 10,000 primary reports pass. No
interim scientific result should be inspected or used to stop the experiment.

Development results may motivate a new child candidate only after its parent,
exact change, rationale and falsification criteria are appended to the
candidate register and committed. They cannot be presented as independent
validation.
