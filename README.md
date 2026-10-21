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
G_i = D_i AND O_i AND M_i
```

- `D`: essential record information is adequate;
- `O`: the patient lies within supported covariate/overlap regions;
- `M`: prespecified credible models agree on the recommended action;

Every gate check is essential. Strength in one check cannot compensate for
failure of another. The individualised action is used when the gate passes;
otherwise the system defers to a prespecified population policy or human
review. Decision uncertainty remains computed and reported, but it is tested
as the external matched-coverage comparator rather than duplicated inside the
current gate.

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
rejected final architecture and may serve only as the disclosed parent of a
new, results-informed development candidate. The independent validation bank
and proposed multitrial data remain unopened. Any child candidate must be
specified and committed before execution, use fresh development runs, and
complete the development, review and registration sequence before validation.

The dated development/validation boundary is defined in
`protocol/development_validation_amendment_v0.2.md`. Protocol v0.1 remains as
the historical pre-amendment record.

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

## Transparent Stage C development

Stage C runs expose scientific simulation results and therefore require a
clean, committed worktree. C001 has completed its authorised development tiers
and must not be rerun or tuned. The next executable development plan will be
documented only after a child candidate has been specified, reviewed, committed
and tagged before its results are exposed.

The batch is resumable and writes ignored outputs under
`results/development/stage-c/`. Each report records the candidate, code commit,
configuration hashes, generated-data hash and fold hash. The summary reports
safety, utility, access, check recovery, raw group gaps and
evidence-standardised group gaps separately. It never calculates a weighted
fairness composite or an automatic candidate score.

Development results may motivate a new child candidate only after its parent,
exact change, rationale and falsification criteria are appended to the
candidate register and committed. They cannot be presented as independent
validation.
