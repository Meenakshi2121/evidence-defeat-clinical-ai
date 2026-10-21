# Development candidate log v0.2

**Status:** C000 and C001 development results recorded; C001 requires revision and is not frozen

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
| C001 | C000 | Development complete; rejected as final architecture | Screening: `stage-c-c001-pre-run-v0.1`, commit `562f02cd30ed10dd5b9b070e53b42dd3b97b4179`; fairness stress: `stage-c-c001-fairness-pre-run-v0.1`, commit `564cb6c6f8d9d2b5d94ca5213a9f7233cdc96859`; robustness: `stage-c-c001-robustness-pre-run-v0.1`, commit `40d654241480f0f612218c15d79efae563cdbddf` | Captured in the manifests below | v0.1 | Revise through a prospectively specified child; do not freeze or validate C001 |

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

- Run manifest and development-bank version: 60 of 60 screening units completed
  under development bank v0.1 at commit
  `562f02cd30ed10dd5b9b070e53b42dd3b97b4179`; output
  `results/development/stage-c/C001/c001-screening-v0.1/manifest.json`.
  Every report identified C001 and the frozen pre-run commit. The archived
  output SHA-256 is
  `d592d018e2dffb8496acb23717cc0aecfeb4ae3abd754ae183c7fe04042a4244`.
- Material unsafe acceptance at matched coverage: across all 60 screening
  runs, the complete-gate minus uncertainty-only contrast was -0.013000 (95%
  confidence interval -0.019128 to -0.006872). The clean-control scenario is
  a negative control rather than part of the planned primary defect grid. In
  the 50 defect-scenario runs alone, the contrast was -0.013640 (95%
  confidence interval -0.020534 to -0.006746). All six scenario means favoured
  C001, ranging from -0.0356 for record inadequacy to -0.0034 for combined
  defects, although only the record-adequacy and reference-support
  scenario-specific intervals excluded zero with ten replicates each.
- Coverage: mean complete-gate coverage was 55.26% overall and ranged from
  46.36% to 61.58% by scenario, compared with 0.38% to 5.50% for C000. Exact
  matched coverage with the uncertainty-only comparator was preserved in
  every run.
- Deployed policy utility: averaged across all 60 runs, C001 utility exceeded
  uncertainty-only deferral by 0.000535 (95% confidence interval 0.000203 to
  0.000866), matched random deferral by 0.000746 (0.000392 to 0.001100), and
  the population default by 0.002462 (0.001670 to 0.003254). It was 0.000666
  lower than ungated individualisation (-0.001012 to -0.000320), showing the
  expected small utility cost of safety-selective deferral.
- Oracle regret and regret relative to default: C001 reduced oracle regret
  relative to uncertainty-only deferral by 0.000535 and relative to the
  population default by 0.002462 across all runs. Mean regret relative to the
  default was negative in every scenario, ranging from -0.004104 to -0.001327;
  no scenario showed mean harm relative to the default.
- Raw group differences: across all runs, the mean raw coverage gap (group 1
  minus group 0) was -0.02300 (95% confidence interval -0.04465 to -0.00135),
  whereas the mean material-unsafe-acceptance gap was 0.00104 (-0.01384 to
  0.01592). The mean absolute coverage gap was 0.06780 and its maximum was
  0.21576. These screening runs had approximately 100 group-1 observations
  each and equal defect allocation, so these results identify a fairness
  question but do not resolve it.
- Evidence-standardised group differences: standardisation was eligible in
  19 of 60 runs and met the prespecified balance criterion in only 1 of 60.
  Evidence-standardised gaps are therefore not interpreted. The dedicated
  n=2,000 group-concentrated fairness tier is required before any fairness
  conclusion.
- Scenario and seed stability: the primary contrast favoured C001 in every
  scenario and the gate improved utility over the default in every scenario.
  Record adequacy recovered its generated defect with sensitivity and
  specificity of 1.000. Reference support had mean sensitivity 0.9774 and
  specificity 0.9905. Model multiplicity remained weak against its generated
  defect label (sensitivity 0.3857; specificity 0.6158), an adverse result that
  must remain visible. Despite that label-recovery limitation, the complete
  gate's accepted-actionable error rate was 0.0193 lower than matched
  uncertainty-only deferral across all runs (95% confidence interval -0.0348
  to -0.0039).
- Software or invariant failures: none; all required invariants passed in all
  60 runs, and the manifest and independently uploaded summary agreed with the
  archived copies.
- Interpretation, including adverse findings: C001 restored meaningful access
  and showed a favourable exploratory safety-utility profile against both
  uncertainty-only and random deferral. This is development evidence, not
  independent validation. Weak recovery of the generated multiplicity defect
  and failure of most evidence-standardisation fits prevent finalist status
  or a fairness claim. The next prespecified tier must test whether safety and
  access remain acceptable when record and support defects are concentrated
  by audited group.
- Decision: retain C001 for the fairness-stress tier only. Do not designate it
  a finalist, freeze it, access reserved validation data, or describe the
  screening result as proof. Promotion beyond fairness stress requires a new
  append-only review of the complete safety, utility, access and fairness
  profile, including the adverse multiplicity result.
- Reviewer initials and date: provisional study-author decision, 19 October
  2026; supervisor and statistical review pending.

**Fairness-stress post-run record**

- Run manifest and development-bank version: 30 of 30 fairness-stress units
  completed under development bank v0.1 at clean pre-run commit
  `564cb6c6f8d9d2b5d94ca5213a9f7233cdc96859`; output
  `results/development/stage-c/C001/c001-fairness-stress-v0.1/manifest.json`.
  Every run identified candidate C001, used the fairness-stress namespace and
  remained ineligible for confirmatory evidence. The archived output SHA-256
  is `bcddcc1d3536a2554597b422f29b67f4191ad7026ba526de7a42a356faf2576d`.
- Material unsafe acceptance at matched coverage: across all 30 runs, the
  complete-gate minus uncertainty-only contrast was -0.015033 (95% confidence
  interval -0.019802 to -0.010265). All six scenario means favoured C001,
  ranging from -0.0300 to -0.0088; four scenario-specific intervals excluded
  zero. Exact matched coverage was preserved in every run.
- Coverage: mean complete-gate coverage was 53.37% overall and ranged from
  47.97% to 60.58% by scenario. This restored meaningful access while leaving
  46.63% of recommendations on the population default or human-review path.
- Deployed policy utility: C001 exceeded uncertainty-only deferral by 0.000506
  (95% confidence interval 0.000145 to 0.000866), matched random deferral by
  0.001327 (0.000833 to 0.001821), and the population default by 0.004430
  (0.003301 to 0.005559). It was 0.001448 lower than ungated
  individualisation (-0.001991 to -0.000904), retaining the expected small
  utility cost of safety-selective deferral.
- Oracle regret and regret relative to default: relative to uncertainty-only
  deferral, C001 reduced oracle regret by 0.000506. Mean regret relative to the
  default was -0.004430 (95% confidence interval -0.005559 to -0.003301), so
  the gate improved utility over the default on average in this development
  tier.
- Raw group differences: the audited group had lower access to
  individualisation under C001. The mean coverage gap (group 1 minus group 0)
  was -0.129562 (95% confidence interval -0.170335 to -0.088789). The raw
  material-unsafe-acceptance gap was -0.004663 (-0.018518 to 0.009192),
  compared with 0.037583 (0.021189 to 0.053977) under uncertainty-only
  deferral. Within group 1, C001 reduced material unsafe acceptance relative
  to uncertainty-only deferral by 0.044718 (0.031637 to 0.057798 in absolute
  reduction). The result is therefore a safety--access trade-off: C001
  directed more deferral toward the group with concentrated evidence defects
  and removed the clear raw safety disadvantage seen under the comparator.
- Evidence-standardised group differences: estimation was eligible in all 30
  runs but met the prespecified balance criterion in only 15, comprising all
  runs with 50% group prevalence and none with 20% prevalence. Among those 15
  balanced runs, the standardised coverage gap was -0.006593 (95% confidence
  interval -0.013012 to -0.000174), the material-unsafe-acceptance gap was
  0.022933 (0.002185 to 0.043682), the utility gap was 0.000104 (-0.003602 to
  0.003811), and the oracle-regret gap was 0.001639 (0.000031 to 0.003246).
  The standardised unsafe-gap difference between C001 and uncertainty-only
  deferral was 0.003450 (-0.006913 to 0.013814). These diagnostics do not show
  clear comparative worsening, but the residual within-C001 gap and failed
  balance at 20% prevalence prohibit a fairness guarantee.
- Scenario and seed stability: the primary contrast favoured C001 in every
  scenario. Record adequacy recovered its generated defect with pooled
  sensitivity and specificity of 1.000. Reference support had sensitivity
  0.8737 and specificity 0.9853. Model multiplicity remained weak against its
  generated label (sensitivity 0.3739; specificity 0.6234). Decision
  uncertainty, retained only as a comparator, had sensitivity 0.9803 but
  specificity 0.0233. In ablations, removing record adequacy, reference
  support or model multiplicity increased material unsafe acceptance by
  0.030217, 0.008100 and 0.116567, respectively. The multiplicity check is
  therefore safety-relevant despite its weak defect-label recovery.
- Software or invariant failures: none. All 30 reports passed, all 240
  invariant evaluations passed, every worktree was clean at run start, the
  separately uploaded summary matched the archived summary byte for byte, and
  the archive passed integrity verification.
- Interpretation, including adverse findings: C001 met the prespecified
  development safety-support rule at exactly matched coverage and produced a
  small utility advantage over uncertainty-only and random deferral. It also
  showed why equal deferral is not automatically fair when evidence defects
  are group-concentrated: additional deferral reduced the exposed group's raw
  safety disadvantage. This remains exploratory development evidence. The
  access gap, residual standardised safety gap, failed standardisation balance
  at 20% group prevalence and weak multiplicity-label recovery must remain
  visible and prohibit claims of proven fairness, deployment readiness or
  independent validation.
- Decision: promote C001 unchanged to the prespecified finalist-robustness
  tier. Do not tune thresholds or checks against these observed results. C001
  is a finalist, not the frozen final candidate; reserved validation and RCT
  Bench patient-level data remain unopened. Development freeze requires the
  complete robustness profile, written selection rationale, supervisor and
  statistical review, and registration.
- Reviewer initials and date: provisional study-author decision, 19 October
  2026; supervisor and statistical review pending.

**Finalist-robustness post-run record**

- Run manifest and development-bank version: 25 of 25 finalist-robustness
  units completed under development bank v0.1 at clean pre-run commit
  `40d654241480f0f612218c15d79efae563cdbddf`; output
  `results/development/stage-c/C001/c001-finalist-robustness-v0.1/manifest.json`.
  Every run used 2,000 observations, every report passed, and all 200 invariant
  evaluations passed. The archived output SHA-256 is
  `66fb0c722ccd2c9e1e5039da93d4aa2302e0109fe780cc307b155518f5938889`;
  the separately exported summary SHA-256 is
  `fd3d62c6d73f9408cda1d850601d76dee07caaef9425ce0c49f080746b2c61e8`
  and matched the archived summary byte for byte.
- Material unsafe acceptance at matched coverage: across all 25 robustness
  runs, the complete-gate minus uncertainty-only contrast was -0.003760 (95%
  confidence interval -0.015449 to 0.007929), so the planned overall
  robustness comparison was inconclusive. In the 20 defect-present runs, the
  contrast favoured C001 (-0.014950; -0.023419 to -0.006481), as did the
  contrast with matched random deferral (-0.026461; -0.034871 to -0.018051).
  In the five no-defect runs, however, uncertainty-only deferral was safer:
  the C001 minus uncertainty-only contrast was 0.041000 (0.027083 to
  0.054917). Scenario means for the primary contrast were -0.021200 for
  continuous defects, -0.019800 for group shift, -0.009800 for linear
  effects, -0.009000 for strong effects and 0.041000 when heterogeneity and
  generated evidence defects were absent.
- Coverage: mean complete-gate coverage was 44.60% in the 20 defect-present
  runs (95% confidence interval 39.65% to 49.54%) and 60.96% in the five
  no-defect runs. Exact matched coverage with uncertainty-only deferral was
  maintained within every run.
- Deployed policy utility: in defect-present runs, C001 exceeded matched random
  deferral by 0.001933 (95% confidence interval 0.000189 to 0.003676) and the
  population default by 0.006909 (0.003479 to 0.010339). Its utility difference
  from uncertainty-only deferral was 0.000759 (-0.000737 to 0.002254), while
  its difference from ungated individualisation was -0.007428 (-0.012090 to
  -0.002766). In the no-defect runs, C001 was worse than uncertainty-only
  deferral by -0.001640 (-0.002197 to -0.001083).
- Oracle regret and regret relative to default: the utility profile shows that
  C001 retained benefit over the default when defects were present but paid a
  cost relative to ungated individualisation. Its no-defect disadvantage
  demonstrates that the evidence-defeat gate cannot replace graded decision
  uncertainty as a general safeguard.
- Raw group differences: in the 20 defect-present runs, the mean coverage gap
  (group 1 minus group 0) was -0.052139 (95% confidence interval -0.095276 to
  -0.009002), and the raw material-unsafe-acceptance gap was -0.026989
  (-0.049337 to -0.004641). These are descriptive group differences under the
  generated scenarios, not evidence of equal access or a fairness guarantee.
- Evidence-standardised group differences: estimation was technically
  eligible in all 25 runs, but none met the prespecified balance criterion.
  Evidence-standardised gaps are therefore not interpreted.
- Scenario and seed stability: C001's direction of advantage depended on the
  evidence state. The primary contrast favoured C001 in the defect-present
  pool but clearly favoured uncertainty-only deferral in the no-defect
  scenario. Record adequacy recovered its generated defect with sensitivity
  and specificity of 1.000. Reference support had pooled sensitivity 0.8291
  and specificity 0.9912. Model multiplicity remained weak against its
  generated label (sensitivity 0.4338; specificity 0.5559), while the
  uncertainty check had sensitivity 0.9861 but specificity 0.0119.
- Ablations and action errors: in defect-present runs, removing record
  adequacy, reference support or model multiplicity increased material unsafe
  acceptance by 0.044450 (0.036914 to 0.051986), 0.007725 (0.005576 to
  0.009874), and 0.145700 (0.132535 to 0.158865), respectively. The accepted
  actionable-error contrast against uncertainty-only deferral was -0.030993
  (-0.057650 to -0.004337). These results show that the three checks can carry
  safety information even though the multiplicity check is a weak classifier
  of its generated defect label.
- Software or invariant failures: none. All 25 reports passed, all 200
  invariant evaluations passed, every worktree was clean at run start, and
  generated-data and fold hashes were unique as required. The outputs remain
  exploratory and explicitly ineligible for confirmatory evidence.
- Interpretation, including adverse findings: C001 provides exploratory
  evidence that non-compensatory evidence-defeat checks improve safety when
  the tested evidence defects are present. It does not establish superiority
  across evidence states, because uncertainty-only deferral was superior in
  the no-defect scenario and the overall interval included zero. The raw access
  gap, failed standardisation balance and weak multiplicity-label recovery also
  prohibit claims of proven fairness, universal benefit or deployment
  readiness. The results instead support treating distinct evidence defeaters
  and graded uncertainty as complementary safeguards.
- Decision: reject C001 as the final architecture and do not freeze, register
  or validate it. A results-informed child candidate may be developed only
  after its hierarchical combination of hard evidence defeaters and graded
  uncertainty, fresh development runs, expected benefit and falsification
  criteria are specified and committed. Reserved validation and RCT Bench
  patient-level data remain unopened.
- Reviewer initials and date: provisional study-author decision, 21 October
  2026; supervisor and statistical review pending.

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
