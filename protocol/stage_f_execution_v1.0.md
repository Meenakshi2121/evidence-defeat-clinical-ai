# Stage F confirmatory execution procedure v1.0

**Candidate:** C002

**Authorisation:** `stage-e-variance-complete-v1.0`

**Runner freeze:** `stage-f-runner-v1.0`

**Primary run set:** ten scenario cells, 1,000 replicates per cell, 10,000
runs in total

## Purpose

Stage F is the first confirmatory test of the frozen framework. It estimates
whether C002 reduces material unsafe acceptance relative to uncertainty-only
deferral at exactly matched coverage. All results are reported regardless of
direction. Stage C development results and Stage E variances do not enter the
Stage F effect estimate.

## Immutable run set

The ten primary scenario cells and their common parameters are read from
`config/validation.yaml`. Replicate identifiers are 300000 through 300999 in
every cell. C002, its thresholds, the learner set, materiality margins,
comparators, outcome, primary estimand, confidence interval and coverage floor
remain unchanged.

The public `stage-f-runner-v1.0` tag must identify the exact execution commit.
The runner refuses to start from another commit, a dirty worktree or altered
Stage E-authorised files.

## Checkpointing and interruption

Every replicate is executed in an isolated process and written atomically to
the ignored `results/validation/stage-f/` tree. A Codespace interruption can
therefore lose only the active replicate. Repeating the same scenario command
validates and skips completed reports before continuing. The optional
`--max-new-runs` argument is a result-independent computational checkpoint; it
does not select or remove replicates.

Only one process may run a particular scenario at a time. Different scenarios
may be run in separate terminals if memory permits. Two concurrent n=2,000
scenarios should not be attempted without first confirming adequate memory.

## Complete-first unblinding

Individual reports contain the metrics needed for reproducibility but remain
inside the ignored results tree. During execution, the supported status command
displays completion counts only. Investigators must not inspect or aggregate
interim scientific results.

The summary command checks all 10,000 run identifiers, code and configuration
hashes, invariant status and balanced scenario counts. It refuses to create a
summary unless the complete primary grid is present. The resulting summary is
the single planned scientific unblinding.

## Primary decision

The primary estimate is C002 material unsafe acceptance minus uncertainty-only
material unsafe acceptance at exact matched coverage, with equal scenario
weight. Negative values favour C002. The primary safety claim is supported only
when both conditions hold:

1. the upper limit of the two-sided 95% Student-t confidence interval is below
   zero; and
2. mean C002 coverage is at least 25%.

Secondary policy contrasts, leave-one-check-out mechanism analyses with Holm
adjustment, and the safety-access fairness audit cannot rescue a failed primary
result. Simulation success is not evidence of clinical effectiveness.

## Commands

After committing and tagging the runner:

```bash
poetry install
poetry run evidence-defeat-confirm plan
poetry run evidence-defeat-confirm init
poetry run evidence-defeat-confirm run-scenario \
  --scenario-id confirmatory_v1__record_adequacy_n500 \
  --max-new-runs 10
poetry run evidence-defeat-confirm status
```

The same `run-scenario` command is repeated until that cell reaches 1,000, then
for each remaining cell. Once status reaches 10,000 of 10,000:

```bash
poetry run evidence-defeat-confirm summarize
```

The prespecified no-defect negative control is a secondary validation extension
outside the 10,000-run primary grid. Its separately frozen execution must not
alter or determine the primary Stage F result.
