# Playbook Authoring Guide

This guide explains how to create and maintain YAML playbooks for SOAR-Lite.

## File Location

Store playbooks in the `playbooks/` directory.

Example filename: `playbooks/phishing_triage.yaml`

## Schema

Each playbook must define:

- `name`: unique playbook name
- `trigger_alert_type`: alert type that activates this playbook
- `min_severity`: one of `low`, `medium`, `high`, `critical`
- `steps`: ordered list of execution steps

Each step must define:

- `id`: unique step ID within the playbook
- `connector`: registered connector name
- `input_field`: alert field to pass into connector
- `timeout`: timeout in seconds (`> 0`)
- `retries`: retry count (`>= 0`)
- `on_result`: conditional routing list

## Example

```yaml
name: phishing_triage
trigger_alert_type: phishing
min_severity: medium
steps:
  - id: enrich_ip
    connector: virustotal
    input_field: source_ip
    timeout: 20
    retries: 2
    on_result:
      - if_expr: "score > 70"
        then: escalate
      - if_expr: null
        then: continue
```

## Condition Routing

`on_result` supports:

- `escalate`: set incident to escalated
- `continue`: move to next step
- `close`: mark incident completed

Condition expressions are evaluated with `simpleeval` against connector output fields.

## Authoring Rules

- Keep step IDs unique per playbook.
- Keep connectors and input fields aligned with alert schema.
- Put broad fallback logic last (`if_expr: null`).
- Keep timeouts realistic for external API latency.
- Use small retry counts to avoid long incident blocking.

## Validation Checklist

Before committing a playbook:

1. Confirm YAML is valid.
2. Confirm all step IDs are unique.
3. Confirm connector names exist in registry.
4. Confirm all `if_expr` expressions compile and evaluate safely.
5. Run test suite and ingest a sample alert for this playbook.
