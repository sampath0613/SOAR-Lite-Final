# Adding a Connector

This SOP describes how to add a new connector to SOAR-Lite.

## 1. Create Connector Class

Create a module in `soar/connectors/`.

Example: `soar/connectors/myintel.py`

Implement `BaseConnector`:

- class attribute `name`
- `async execute(self, params) -> ConnectorResult`
- optional `async health_check(self) -> bool`

## 2. Implement Execute Contract

Your `execute` method should:

- validate required input params
- make external API call(s)
- return a `ConnectorResult` with normalized fields
- avoid raising unhandled exceptions for expected API failures

Example result shape:

```python
ConnectorResult(
    success=True,
    data={"score": 42, "indicator": "1.2.3.4"},
)
```

## 3. Register Connector

Edit `soar/connectors/registry.py`.

- import your connector class in `init_connectors()`
- add it to `CONNECTOR_REGISTRY`

## 4. Add Configuration

If API credentials are needed:

- add settings fields in `soar/config.py`
- add placeholders in `.env.example`
- document required variables in README

## 5. Add Unit Tests

Create tests in `tests/unit/`.

Minimum test set:

- success response parsing
- API/auth failure handling
- timeout handling
- health check behavior

## 6. Validate End-to-End

- include connector in a sample playbook
- ingest alert that triggers playbook
- verify step execution record and incident routing behavior

## 7. Definition of Done

A connector is complete when:

1. It is registered and discoverable.
2. Unit tests pass.
3. It participates in at least one playbook execution.
4. It reports health status correctly.
