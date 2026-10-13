# Prior work and result disclosure

**Recorded:** 13 October 2026  
**Applies to:** development of the Evidence Defeat for Responsible Clinical AI
project

## Earlier work

Before this repository was created, an exploratory project applied a
three-check Nyāya-inspired evidence gate to aspirin recommendations in the
International Stroke Trial (IST). That project included:

- a data-adequacy check;
- a reference-support check;
- an estimator-action agreement check;
- an uncertainty-only matched-coverage comparator;
- cross-fitted policy-risk point estimates; and
- a small synthetic POC with eight replicates in four scenarios.

## Results already known

The following findings were known before this new study was designed:

- the IST gate improved the point estimate relative to ungated
  individualisation but did not improve on treating everyone with aspirin or on
  uncertainty-only deferral;
- the small synthetic POC suggested lower unsafe acceptance but did not show
  consistently lower total policy regret than uncertainty-only deferral;
- group-concentrated evidence defects produced a substantial deferral gap; and
- estimator stability appeared to be the most influential check in the POC.

These findings shaped the new focus on evidence defeat, matched coverage,
falsification, ablations and the safety--access fairness trade-off.

## Independence rule

IST and the earlier POC are development evidence, not independent validation.
They will not be pooled with confirmatory estimates, used to select favourable
thresholds, or represented as preregistered results. If included in the final
paper, IST will be labelled an exploratory historical case study.

The independent validation set will consist of trials and semi-synthetic
instances selected using eligibility rules registered before their method
results are examined.

