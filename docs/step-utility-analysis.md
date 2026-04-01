# Step Utility Analysis

SOAR-Lite computes per-step utility to identify low-value playbook steps.

## Formula

For a given playbook step:

`utility = true_positive_step_executions / total_step_executions_with_verdict`

If no verdicted executions exist, utility defaults to `0.5` (neutral).

## Interpretation

- `>= 0.4`: keep step
- `< 0.4`: review step for redesign or removal

## Why This Metric

Utility focuses on operational value rather than only detector quality.
It helps answer: "Did this step contribute to incidents that were truly malicious?"

## Data Inputs

Utility uses:

- `Incident.analyst_verdict`
- `StepExecution` records scoped by playbook + step ID

## Operational Workflow

1. Analyst sets verdict (`true_positive` or `false_positive`).
2. Utility can be recomputed per step.
3. `/playbooks/{name}/step-utility` shows score + recommendation.
4. Low-utility steps are candidates for optimization.

## Practical Guidance

- Do not optimize based on a tiny sample size.
- Review utility trends over time, not one batch.
- Pair utility with execution cost (latency and API quota).
- Keep context: some low-utility steps may still satisfy compliance requirements.

## Example

If a step executed for 20 incidents with analyst verdicts:

- 15 true positive
- 5 false positive

Utility is:

`15 / 20 = 0.75`

Recommendation: keep.
