# Computational feasibility plan v0.1

**Status:** Diagnostic plan; no confirmatory inference
**Date:** 14 October 2026
**Machine-readable configuration:** `config/poc.yaml`

## 1. Why a proof of concept is required

The planned pipeline repeats five-fold cross-fitting, three treatment-effect
learners, matched-coverage comparators and, for final real-outcome inference, a
full-pipeline bootstrap. Multiplying nominal replicate counts without timing
the implemented pipeline could produce an infeasible protocol or encourage
undocumented shortcuts later. The proof of concept therefore measures
correctness, runtime and memory before the protocol is locked.

It is not a miniature effectiveness study. Its mean policy contrasts will not
be inspected, reported or used to change the framework.

## 2. Stage A: deterministic software smoke test

Run replicate identifiers 0 and 1 for the clean, four single-defect and
combined scenarios at `n=500`. Use the final analysis hyperparameters. Include
the population default, ungated policy, uncertainty-only comparator, random
deferral, single-check selectors and leave-one-check-out gates. The expensive
near-optimal-policy comparator and full bootstrap are omitted from this first
stage.

Stage A passes only when the invariants in `config/poc.yaml` pass, including
fold isolation, exact coverage matching, logical-AND gate construction,
correct metric denominators and complete run fingerprints.

Each replicate runs in a fresh process so its peak resident memory is
interpretable. The runner requires a clean Git worktree and records the full
commit, configuration hashes, generated-data hash, fold-assignment hash,
package versions and computing environment. Its saved reports contain only
invariant statuses and resource/fingerprint metadata; policy values, safety
rates, contrasts and method rankings remain concealed during this stage.

After committing the runner, the diagnostic plan and complete Stage A grid are
invoked with:

```text
poetry run evidence-defeat-poc plan
poetry run evidence-defeat-poc smoke
```

## 3. Stage B: full-comparator timing

Run one reserved replicate of the combined scenario at `n=500` and `n=2,000`
with the complete policy-disagreement comparator. Record wall-clock time, peak
memory, CPU count, operating system and package versions. Then run five
full-pipeline bootstrap resamples at `n=2,000` solely to estimate the marginal
cost of the final bootstrap.

These timing identifiers are outside the confirmatory replicate range and may
never be included in scientific summaries.

The Stage B plan and its first, smallest timing unit are invoked with:

```text
poetry run evidence-defeat-poc timing-plan
poetry run evidence-defeat-poc timing-run --timing-id full_comparator_n500
```

The `n=2,000` comparator and each bootstrap timing repetition are authorised
only after the preceding timing report has been inspected for runtime, memory
and invariant failures. Running the units separately prevents a long or
memory-intensive job from silently consuming the entire feasibility budget.

## 4. Stage C: blinded variance pilot

After Stages A and B pass, run 25 reserved replicates for each of the ten
primary scenarios. The software may expose the standard deviation of the
paired primary contrast and runtime distribution, but not its mean or method
ranking. The provisional required count is

```text
R = max[1000, max over primary scenarios of
        ceiling{(pilot_SD_scenario / 0.0025)^2}].
```

Counts above 5,000 require statistical and computational review. If the
planned run is infeasible, the amendment must change precision or scope before
confirmatory analysis; it cannot use observed rankings to retain only
favourable scenarios.

## 5. Decision record after timing

The feasibility report will record:

1. measured time and memory for each stage;
2. projected CPU-hours and storage for controlled simulation, semi-synthetic
   analysis and real-outcome bootstrap;
3. the replicate count implied by the precision rule;
4. the available computing environment;
5. any proposed amendment and its effect on Monte Carlo precision; and
6. confirmation that no confirmatory or real trial outcome was opened.

Only after this record, supervisor/statistical review and passing tests should
the repository be tagged `protocol-v1.0` and registered.
