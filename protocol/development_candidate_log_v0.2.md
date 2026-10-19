# Development candidate log v0.2

**Status:** C000 result recorded; C001 committed before execution

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
| C000 | — | Screening complete | `stage-c-c000-pre-run-v0.1`; `be9d331e1a5e4654623fc77f7a670f9ef1e6b167` in the manifest | Captured in the manifest below | v0.1 | Revise; four-check architecture not retained |
| C001 | C000 | Pre-run committed | `stage-c-c001-pre-run-v0.1`; exact SHA to be captured by the plan and manifest | Captured by the plan and manifest | v0.1 | Pending run |

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

- Run manifest and development-bank version: 60 of 60 screening units completed
  under development bank v0.1 at commit
  `be9d331e1a5e4654623fc77f7a670f9ef1e6b167`; output
  `results/development/stage-c/C000/c000-screening-v0.1/manifest.json`.
  The archived output SHA-256 is
  `bc898e7a2554ab2a5c298062b45a7f2e97ef1b6f0b6c0d8cfcedf1601c329705`.
- Material unsafe acceptance at matched coverage: the overall complete-gate
  minus uncertainty-only contrast was -0.000233 (95% confidence interval
  -0.000746 to 0.000280; 60 runs). The interval included zero and the
  difference was too small to establish a meaningful advantage.
- Coverage: mean complete-gate coverage by scenario ranged from 0.38% to
  5.50%. Decision certainty failed for 94.08% of clean-control rows and for
  95.50% to 99.52% of rows in the five defect scenarios.
- Deployed policy utility: the complete gate was effectively the population
  default because almost every recommendation was deferred. Mean regret
  relative to the default ranged from -0.000014 to 0.000010 across scenarios.
- Oracle regret and regret relative to default: no stable material advantage
  over the default was observed for the complete gate; the three-check
  `without_decision_uncertainty` ablation had 47.44% to 60.64% coverage and
  lower regret than the default in all six scenarios, but this is
  results-informed development evidence rather than validation.
- Raw group differences: reported for all scenarios, but sparse acceptance
  made a stable substantive comparison inappropriate.
- Evidence-standardised group differences: estimation was eligible in only
  19 of 60 runs and passed the prespecified balance check in only 2 of 60;
  C000 therefore cannot support a fairness conclusion.
- Scenario and seed stability: the primary contrast changed direction across
  scenarios (scenario means from -0.0016 to 0.0004), while near-zero coverage
  was consistent. Record adequacy recovered its target defect perfectly in
  the screening bank. Reference support had mean sensitivity 0.9774 and
  specificity 0.9905 in its target scenario. Model multiplicity was weak in
  its target scenario (sensitivity 0.3875; specificity 0.6077).
- Software or invariant failures: none; all required invariants passed in all
  60 runs.
- Interpretation, including adverse findings: C000 did not demonstrate a
  useful advantage over uncertainty-only deferral. Its certainty condition
  dominated the other checks, collapsed access, prevented a meaningful
  fairness audit and made the proposed “beyond uncertainty” contribution
  empirically unidentifiable.
- Decision: reject C000 as the final architecture and revise through child
  candidate C001. This is an explicitly results-informed Stage C decision and
  is not independent evidence for C001.
- Reviewer initials and date: study author, 19 October 2026; supervisor and
  statistical review pending.

### Candidate `C001`

**Pre-run record**

- Parent candidate: C000.
- Date and author: 19 October 2026; study author.
- Scientific or engineering rationale: C000 showed that the binary decision-
  certainty condition admitted almost no rows and made the complete gate
  functionally similar to uncertainty-only deferral. The distinct Nyāya-
  inspired defeating conditions are record inadequacy, unsupported extension
  to a covariate region and counterbalanced inference across estimators.
  Uncertainty is therefore better retained as the external benchmark than
  duplicated inside the framework being compared with it.
- Exact intended change: the complete gate becomes
  `G_i = D_i AND O_i AND M_i`. Decision uncertainty (`U_i`) is still computed
  and reported, and uncertainty-only deferral remains the primary comparator
  at exactly matched coverage. No threshold, learner, scenario, outcome,
  estimand, fairness rule or default policy changes.
- Expected benefit: restore enough access for a meaningful safety and fairness
  test while asking whether the three distinct evidence defects select safer
  recommendations than uncertainty alone. The C000 ablation suggests, but
  does not prove, expected screening coverage of approximately 47% to 61%.
- Possible failure mode: increased coverage may not improve material unsafe
  acceptance relative to uncertainty-only deferral; model multiplicity may
  remain a weak discriminator; or group harms may emerge.
- Metrics that could falsify the rationale: a non-negative primary unsafe-
  acceptance contrast; materially increased regret relative to the default;
  unstable or harmful group-specific results; or persistently weak recovery of
  the generated multiplicity defect.
- Git commit: full SHA will be recorded by `evidence-defeat-dev plan` and each
  run manifest before execution; annotated tag
  `stage-c-c001-pre-run-v0.1` names the clean pre-run commit.
- Configuration hashes: to be recorded by the plan and each report for the
  base analysis, simulation, governance, development bank, candidate register,
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
