# Stage E blinded variance-pilot procedure v1.0

**Candidate:** C002

**Protocol:** `protocol-v1.0`

**Scientific role:** Replicate-count and computational planning only

## Disclosure boundary

Each of the ten frozen primary scenario cells is run for replicate identifiers
100000 through 100024. During Stage E, the software may save only:

- the standard deviation of the paired primary contrast;
- runtime and peak process memory;
- configuration, generated-data-collection and fold-collection hashes; and
- non-scientific invariant results.

The software does not save the individual paired contrasts, their mean, either
method's mean performance, method rankings or group differences. Stage E
therefore cannot support a scientific-effect claim.

## Replicate-count decision

For scenario `s`, the variance-only calculation is

```text
R_s = ceiling((SD_s / 0.0025)^2).
```

The common Stage F count is the maximum `R_s` across the ten cells, with a
minimum of 1,000 and maximum of 5,000 replicates per cell. If the calculated
requirement exceeds 5,000, the report flags that the target Monte Carlo
standard error cannot be reached within the frozen cap.

The Stage E summary must be committed and tagged before Stage F begins. Only
the replicate count and computational batching may change. C002, its
thresholds, scenario definitions, outcomes, comparators and decision rules
remain frozen.

## Execution and resumption

The batch runner executes one complete 25-replicate scenario group at a time.
Completed groups can be resumed safely because each group report records its
code commit, frozen configuration hashes and collection hashes. Partial
within-group scientific values are held only in process memory and are not
written to disk.

The command is:

```text
poetry run evidence-defeat-validate pilot-batch
```

Before execution, the runner verifies that the repository is clean, the
`protocol-v1.0` tag is an ancestor of the current commit and all frozen files
still match the tagged versions.
