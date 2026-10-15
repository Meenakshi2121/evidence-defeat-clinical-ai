# Development candidate log v0.2

**Status:** Baseline candidate committed; no Stage C result inspected

**Date opened:** 14 October 2026

**Baseline specified:** 15 October 2026

**Applies to:** Controlled-simulation development bank only

This is an append-only record. A candidate row and its pre-run rationale must
be committed before the candidate is evaluated. Post-run fields are added
without deleting or rewriting the pre-run entry. Failed and rejected
candidates remain visible.

## Candidate register

| Candidate ID | Parent ID | Status | Pre-run commit | Configuration hash | Development-bank version | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| C000 | — | Pre-run committed | `stage-c-c000-pre-run-v0.1`; exact SHA captured by the plan and manifest | Captured by the plan and manifest | v0.1 | Pending run |

The pre-run Git hash cannot be written self-referentially into the commit it
identifies. The annotated tag names that clean commit; the machine-generated
plan and batch manifest record its full SHA and configuration hashes before
any result is exposed.

### Candidate `C000`

**Pre-run record**

- Parent candidate: none; this is the baseline.
- Date and author: 15 October 2026; study author.
- Scientific or engineering rationale: establish the performance of the
  prespecified four-check, non-compensatory gate before adapting any component.
- Exact intended change: none relative to the v0.1 implementation.
- Expected benefit: separately testing record adequacy, reference support,
  model multiplicity and decision uncertainty may reduce materially unsafe
  accepted recommendations beyond uncertainty-only deferral at exactly matched
  coverage.
- Possible failure mode: the additional checks may mainly reduce access to
  individualisation without concentrating safety gains.
- Metrics that could falsify the rationale: a non-negative primary
  unsafe-acceptance contrast; materially greater regret relative to the default;
  or persistent group harm after evidence standardisation.
- Git commit: full SHA recorded by `evidence-defeat-dev plan` and every run
  manifest before execution; annotated tag `stage-c-c000-pre-run-v0.1`.
- Configuration hashes: recorded by the plan and each report for the base
  analysis, simulation, governance, development bank, candidate register,
  effective candidate analysis and their labelled combination.
- Reserved validation and RCT Bench patient-level data accessed: no.

**Post-run record**

- Not yet available. Append results here; do not rewrite the pre-run record.

## Required entry for each candidate

### Candidate `[identifier]`

**Pre-run record**

- Parent candidate:
- Date and author:
- Scientific or engineering rationale:
- Exact intended change:
- Expected benefit and possible failure mode:
- Metrics that could falsify the rationale:
- Git commit:
- Analysis, simulation, development-bank and combined configuration hashes:
- Confirmation that reserved validation and RCT Bench patient-level data were
  not accessed:

**Post-run record**

- Run manifest and development-bank version:
- Material unsafe acceptance at matched coverage:
- Coverage:
- Deployed policy utility:
- Oracle regret and regret relative to default:
- Raw group differences:
- Evidence-standardised group differences:
- Scenario and seed stability:
- Software or invariant failures:
- Interpretation, including adverse findings:
- Decision: retain, revise or reject:
- Reviewer initials and date:

## Freeze record

To be completed once, after development and before any validation access:

- Final candidate ID:
- Clean Git commit:
- Configuration hashes:
- Candidate-history completeness check:
- Written selection rationale location:
- Supervisor approval:
- Statistical approval:
- Registration identifier and date:
- `protocol-v1.0` tag:
