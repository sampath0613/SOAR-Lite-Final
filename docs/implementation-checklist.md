# SOAR-Lite Implementation Checklist

## Phase 1: Project Setup & Infrastructure

### 1.1 Git Repository Setup
- [ ] Initialize Git repository in `d:\My folder\Career\Security Automation Engineer\Projects\SOAR-Lite-Pro`
- [ ] Create `.gitignore`:
  ```
  __pycache__/
  *.py[cod]
  *$py.class
  *.so
  .env
  .venv
  venv/
  .vscode/
  .pytest_cache/
  htmlcov/
  dist/
  build/
  *.egg-info/
  .DS_Store
  soar_lite.db
  logs/
  ```
- [ ] Create initial commit with README.md
- [ ] Document in `docs/SETUP.md`

### 1.2 Python Virtual Environment
- [ ] Create venv: `python -m venv venv`
- [ ] Activate: `venv\Scripts\activate` (Windows)
- [ ] Upgrade pip: `python -m pip install --upgrade pip`
- [ ] Create `requirements.txt`:
  ```
  fastapi==0.104.1
  uvicorn[standard]==0.24.0
  sqlalchemy==2.0.23
  aiosqlite==0.19.0
  asyncpg==0.29.0
  pydantic==2.5.0
  pydantic-settings==2.1.0
  httpx==0.25.1
  requests==2.31.0
  python-dotenv==1.0.0
  simpleeval==0.9.31
  pyyaml==6.0.1
  pytest==7.4.3
  pytest-asyncio==0.21.1
  pytest-cov==4.1.0
  black==23.12.0
  flake8==6.1.0
  mypy==1.7.1
  ```
- [ ] Install: `pip install -r requirements.txt`

### 1.3 Project Structure
- [ ] Create directories:
  ```
  SOAR-Lite-Pro/
  ├── soar/
  │   ├── __init__.py
  │   ├── main.py              (FastAPI app)
  │   ├── models.py            (Pydantic models)
  │   ├── database.py          (SQLAlchemy setup)
  │   ├── executor.py          (Playbook executor)
  │   ├── connectors/
  │   │   ├── __init__.py
  │   │   ├── base.py
  │   │   ├── virustotal.py
  │   │   ├── abuseipdb.py
  │   │   ├── shodan.py
  │   │   ├── slack.py
  │   │   └── mock_jira.py
  │   ├── state_machine.py
  │   ├── eval_sandbox.py
  │   └── app_state.py
  ├── tests/
  │   ├── __init__.py
  │   ├── test_connectors.py
  │   ├── test_executor.py
  │   ├── test_state_machine.py
  │   └── test_e2e.py
  ├── playbooks/
  │   ├── phishing_triage.yaml
  │   ├── malware_analysis.yaml
  │   └── abuse_report.yaml
  ├── docs/
  │   ├── SETUP.md
  │   ├── API.md
  │   ├── CONNECTORS.md
  │   └── design-decisions.md
  ├── .env.example
  ├── requirements.txt
  ├── pytest.ini
  └── README.md
  ```

---

## Phase 2: Core Data Models & Database

### 2.1 Define Pydantic Models
File: `soar/models.py`

- [ ] `Alert` model (source system → SOAR)
  - [ ] id (str)
  - [ ] alert_type (str, enum: phishing/malware/abuse)
  - [ ] severity (str, enum: low/medium/high/critical)
  - [ ] timestamp (datetime)
  - [ ] source (str)
  - [ ] details (dict)
  - [ ] metadata (dict)
- [ ] `Incident` model (incident object)
  - [ ] id (str UUID)
  - [ ] alert_id (str)
  - [ ] playbook_name (str)
  - [ ] status (IncidentStatus enum)
  - [ ] created_at (datetime)
  - [ ] updated_at (datetime)
  - [ ] verdict (Optional[Verdict], enum: true_positive/false_positive)
- [ ] `StepExecution` model
  - [ ] id (str UUID)
  - [ ] incident_id (str UUID FK)
  - [ ] step_id (str)
  - [ ] connector_name (str)
  - [ ] status (ExecutionStatus enum)
  - [ ] result (dict)
  - [ ] started_at (datetime)
  - [ ] completed_at (Optional[datetime])
  - [ ] error (Optional[str])
  - [ ] duration_ms (Optional[int])
- [ ] `IncidentStatus` enum: PENDING, RUNNING, COMPLETED, FAILED, ESCALATED
- [ ] `ExecutionStatus` enum: PENDING, RUNNING, COMPLETED, FAILED, TIMEOUT
- [ ] `Verdict` enum: TRUE_POSITIVE, FALSE_POSITIVE
- [ ] `Alert` request/response schemas
- [ ] `Incident` response schema (with step executions)

### 2.2 SQLAlchemy Models
File: `soar/database.py`

- [ ] Create Base class
- [ ] `IncidentSchema` (SQLAlchemy model)
  - [ ] Table name: "incidents"
  - [ ] Columns: id, alert_id, playbook_name, status, verdict, created_at, updated_at
  - [ ] Indexes on: (alert_id), (status), (created_at)
- [ ] `StepExecutionSchema` (SQLAlchemy model)
  - [ ] Table name: "step_executions"
  - [ ] Columns: id, incident_id, step_id, connector_name, status, result (JSON), error, started_at, completed_at
  - [ ] Foreign key: incident_id → incidents(id) with cascade delete
  - [ ] Indexes on: (incident_id), (status), (started_at)
- [ ] `MetricSchema` (SQLAlchemy model, optional Phase 1)
  - [ ] Table name: "metrics"
  - [ ] Columns: id, incident_id, step_id, utility_score, processed_at
- [ ] Database engine setup
  - [ ] SQLite for dev: `sqlite+aiosqlite:///./soar_lite.db`
  - [ ] Async session factory
- [ ] `create_tables()` function (run at startup)
- [ ] Add to `main.py`: `@app.on_event("startup")`

### 2.3 Environment Configuration
File: `.env.example` and `.env`

- [ ] Create `.env.example`:
  ```
  DATABASE_URL=sqlite+aiosqlite:///./soar_lite.db
  VIRUSTOTAL_API_KEY=your-key-here
  ABUSEIPDB_API_KEY=your-key-here
  SHODAN_API_KEY=your-key-here
  SLACK_WEBHOOK_URL=your-webhook-here
  LOG_LEVEL=INFO
  DEBUG=false
  ```
- [ ] Create `.env` (local development, NOT committing)
- [ ] Load in `main.py` using `pydantic-settings`
- [ ] Document in `docs/SETUP.md`

---

## Phase 3: Base Connector Architecture

### 3.1 Connector Base Class
File: `soar/connectors/base.py`

- [ ] Abstract class `BaseConnector`:
  - [ ] `name` property (str)
  - [ ] `description` property (str)
  - [ ] `async execute(params: dict) → dict` (abstract)
  - [ ] `_validate_params(params)` helper
  - [ ] `_handle_rate_limit(error)` helper
- [ ] Retry mechanism with exponential backoff:
  - [ ] Default: 3 attempts, `2^attempt` second delay
  - [ ] Max 14 second total wait per step
  - [ ] Retry on: timeout, HTTP 429, HTTP 5xx
  - [ ] Don't retry on: 401, 403, 404, 400
- [ ] Timeout enforcement:
  - [ ] Default: 30 seconds per connector call
  - [ ] Respect YAML playbook override
- [ ] Error handling:
  - [ ] `ConnectorError` exception class
  - [ ] `ConnectorTimeoutError` exception class
  - [ ] `ConnectorRateLimitError` exception class
- [ ] Logging:
  - [ ] Log all client requests: "Executing '{connector}' with {params}"
  - [ ] Log retries: "Retry 2/3: {error}, backing off {seconds}s"
  - [ ] Log success: "Connector '{connector}' completed in {ms}ms"
  - [ ] Log failures: "Connector failed after 3 attempts: {error}"

### 3.2 Connector Registry
File: `soar/connectors/__init__.py`

- [ ] Create `CONNECTOR_REGISTRY` dict
- [ ] Function `get_connector(name: str) → BaseConnector`
  - [ ] Raise `ConnectorNotFoundError` if missing
- [ ] Function `init_connectors(api_keys: dict)`
  - [ ] Initialize each connector with API keys from config
  - [ ] Call at app startup
- [ ] Registry will contain (placeholder, implement in Phase 4):
  ```python
  CONNECTOR_REGISTRY = {
      "virustotal": None,          # Phase 4.1
      "abuseipdb": None,           # Phase 4.2
      "shodan": None,              # Phase 4.3
      "slack": None,               # Phase 4.4
      "mock_jira": None,           # Phase 4.5
  }
  ```

---

## Phase 4: Implement All 5 Connectors

### 4.1 VirusTotal Connector
File: `soar/connectors/virustotal.py`

- [ ] Create `VirusTotalConnector(BaseConnector)`
- [ ] API endpoint: `https://www.virustotal.com/api/v3/`
- [ ] Implement `execute(params)` for:
  - [ ] Input params: `file_hash` (MD5/SHA1/SHA256) OR `ip_address` OR `domain`
  - [ ] Make async HTTP GET request (httpx)
  - [ ] Parse response: extract detection stats + vendor names
  - [ ] Return dict:
    ```python
    {
        "hash": "abc123...",
        "type": "file|ip|domain",
        "detected": 5,              # Number of vendors flagging as malicious
        "total": 70,                # Total vendors checked
        "score": 7.14,              # (detected/total)*100
        "vendors": {
            "Kaspersky": "Trojan",
            "Avast": "Win32:Trojan-gen"
        },
        "permalink": "https://www.virustotal.com/gui/..."
    }
    ```
- [ ] Handle rate limiting:
  - [ ] API limit: 4 requests/minute
  - [ ] Exponential backoff on 429
  - [ ] Log: "Rate limit reached, backing off"
- [ ] Test: `pytest tests/test_connectors.py::test_virustotal_file_hash`
- [ ] Register: Update `CONNECTOR_REGISTRY["virustotal"]`

### 4.2 AbuseIPDB Connector
File: `soar/connectors/abuseipdb.py`

- [ ] Create `AbuseIPDBConnector(BaseConnector)`
- [ ] API endpoint: `https://api.abuseipdb.com/api/v2/`
- [ ] Implement `execute(params)` for:
  - [ ] Input params: `ip_address`, optional `days` (default 90)
  - [ ] Make async HTTP GET with API key in header
  - [ ] Return dict:
    ```python
    {
        "ip": "192.168.1.1",
        "abuseConfidenceScore": 85,    # 0-100
        "usageType": "Data Center",
        "isp": "Example ISP",
        "domain": "example.com",
        "reports": [
            {
                "category": "SSH",
                "comment": "Port scanning",
                "reportedAt": "2024-01-15T10:00:00Z"
            }
        ],
        "totalReports": 12
    }
    ```
- [ ] Handle rate limiting:
  - [ ] API limit: 1500 requests/day (higher tier)
  - [ ] Throttle as needed
- [ ] Test: `pytest tests/test_connectors.py::test_abuseipdb_ip`
- [ ] Register: Update `CONNECTOR_REGISTRY["abuseipdb"]`

### 4.3 Shodan Connector
File: `soar/connectors/shodan.py`

- [ ] Create `ShodanConnector(BaseConnector)`
- [ ] API endpoint: `https://api.shodan.io/`
- [ ] Implement `execute(params)` for:
  - [ ] Input params: `ip_address` OR `query` (search string)
  - [ ] For IP: GET `/shodan/host/{ip}`
  - [ ] For query: GET `/shodan/host/search?query={query}`
  - [ ] Return dict (for IP):
    ```python
    {
        "ip": "192.168.1.1",
        "country": "US",
        "ports": [22, 80, 443, 8080],
        "services": {
            "22": {"service": "ssh", "banner": "OpenSSH 7.4"},
            "80": {"service": "http", "banner": "Apache 2.4"}
        },
        "vulns": ["CVE-2021-1234", "CVE-2021-5678"],
        "hostnames": ["example.com", "old.example.com"],
        "os": "Linux 3.10"
    }
    ```
- [ ] Handle rate limiting:
  - [ ] API limit: 1 request/second
  - [ ] Use timeout parameter
- [ ] Test: `pytest tests/test_connectors.py::test_shodan_ip`
- [ ] Register: Update `CONNECTOR_REGISTRY["shodan"]`

### 4.4 Slack Connector
File: `soar/connectors/slack.py`

- [ ] Create `SlackConnector(BaseConnector)`
- [ ] Webhook integration (not REST API for simplicity)
- [ ] Implement `execute(params)` to:
  - [ ] Input params: `channel` (e.g., #security-alerts), `message` (str)
  - [ ] Make async POST to Slack webhook
  - [ ] Format message as Slack Block Kit JSON:
    ```python
    {
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": ":warning: *Alert*\n{message}"}
            }
        ]
    }
    ```
  - [ ] Return dict:
    ```python
    {
        "status": "sent",
        "channel": "#security-alerts",
        "ts": "1234567890.000100"  # Slack message timestamp
    }
    ```
- [ ] Webhook URL from `.env`: `SLACK_WEBHOOK_URL`
- [ ] No rate limiting (webhooks handled by Slack)
- [ ] Test: `pytest tests/test_connectors.py::test_slack_notification` (mock webhook)
- [ ] Register: Update `CONNECTOR_REGISTRY["slack"]`

### 4.5 MockJira Connector
File: `soar/connectors/mock_jira.py`

- [ ] Create `MockJiraConnector(BaseConnector)` (simulates Jira without real API)
- [ ] Implement `execute(params)` to:
  - [ ] Input params: `project` (e.g., "SEC"), `issue_type` (e.g., "Incident"), `summary`, `description`
  - [ ] Simulate creating ticket (no real API call)
  - [ ] Return dict:
    ```python
    {
        "status": "created",
        "issue_key": "SEC-{random_id}",
        "url": f"https://jira.example.com/browse/SEC-{random_id}",
        "created_at": "2024-01-15T10:00:00Z"
    }
    ```
  - [ ] Could later replace with real Jira integration
- [ ] Simulate delay: `await asyncio.sleep(0.1)` (pretend API call)
- [ ] Test: `pytest tests/test_connectors.py::test_mock_jira_ticket`
- [ ] Register: Update `CONNECTOR_REGISTRY["mock_jira"]`

---

## Phase 5: Executor & State Machine

### 5.1 State Machine
File: `soar/state_machine.py`

- [ ] Define `IncidentStatus` enum
  - [ ] PENDING: Waiting to run
  - [ ] RUNNING: Executing playbook
  - [ ] COMPLETED: All steps succeeded
  - [ ] ESCALATED: Human action needed
  - [ ] FAILED: Error occurred
- [ ] Define `ExecutionStatus` enum
  - [ ] PENDING, RUNNING, COMPLETED, FAILED, TIMEOUT
- [ ] Function `validate_incident_transition(from_state, to_state)`
  - [ ] Define valid transitions:
    ```
    PENDING → RUNNING
    RUNNING → COMPLETED
    RUNNING → ESCALATED
    RUNNING → FAILED
    COMPLETED → (no change)
    ESCALATED → (no change)
    FAILED → (no change)
    ```
  - [ ] Raise `StateTransitionError` for invalid transitions
- [ ] Function `is_terminal_state(state)` → bool
- [ ] Unit tests: `tests/test_state_machine.py`

### 5.2 Evaluation Sandbox
File: `soar/eval_sandbox.py`

- [ ] Create `SafeConditionEvaluator` class using `simpleeval`
- [ ] Function `evaluate_condition(expr: str, context: dict) → bool`
  - [ ] Set up safe names (only allow context variables)
  - [ ] Disallow dangerous functions
  - [ ] Return result of expression (e.g., "score > 70")
  - [ ] Catch and log `ForbiddenNode` exceptions
  - [ ] Log: "Evaluating condition: '{expr}' with context {context} → {result}"
- [ ] Support operators: `==`, `<`, `>`, `<=`, `>=`, `!=`, `and`, `or`, `not`
- [ ] Support math: `+`, `-`, `*`, `/`, `%`
- [ ] Unit tests: `tests/test_eval_sandbox.py`
  - [ ] Test valid expressions (score > 70, status == "active")
  - [ ] Test invalid expressions (imports, function calls)

### 5.3 Playbook Parser
File: `soar/executor.py` (or separate `soar/playbook_parser.py`)

- [ ] Load YAML playbooks from `playbooks/` directory
- [ ] Create `Playbook` dataclass:
  ```python
  @dataclass
  class Playbook:
      name: str
      trigger_alert_type: str
      min_severity: str
      steps: List[PlaybookStep]
  
  @dataclass
  class PlaybookStep:
      id: str
      connector: str
      input_field: Optional[str]      # Which alert field to pass
      timeout: int                     # Seconds
      retries: int
      on_result: List[PlaybookAction]  # What to do based on result
  
  @dataclass
  class PlaybookAction:
      if_expr: Optional[str]           # None = always, or condition like "score > 70"
      then: str                        # "continue" OR "escalate" OR "fail"
  ```
- [ ] Function `load_playbook(filename: str) → Playbook`
  - [ ] Parse YAML
  - [ ] Validate: all fields present, valid connector names, valid actions
  - [ ] Raise `PlaybookValidationError` if invalid
- [ ] Function `match_playbook(alert: Alert) → Optional[str]`
  - [ ] Find playbooks matching `trigger_alert_type` AND alert severity ≥ `min_severity`
  - [ ] Return playbook name or None
- [ ] Unit tests: `tests/test_playbook_parser.py`

### 5.4 Executor Core
File: `soar/executor.py`

- [ ] Create `Executor` class
- [ ] Function `async execute_playbook(incident: Incident) → Incident`
  - [ ] Load playbook from `playbooks/{incident.playbook_name}.yaml`
  - [ ] Validate incident state transition: PENDING → RUNNING
  - [ ] For each step in playbook:
    - [ ] Create StepExecution record (db save)
    - [ ] Call `execute_step(step, alert, previous_result)`
    - [ ] Update StepExecution: completed_at, result, status
    - [ ] Based on `on_result` actions:
      - [ ] Evaluate condition using `SafeConditionEvaluator`
      - [ ] If action is "continue": proceed to next step
      - [ ] If action is "escalate": break loop, set incident.status = ESCALATED, log
      - [ ] If action is "fail": break loop, set incident.status = FAILED, log
  - [ ] After all steps:
    - [ ] If no escalation/failure: incident.status = COMPLETED
    - [ ] Save incident to database
  - [ ] Handle exceptions:
    - [ ] Connector timeout → log, retry (exponential backoff)
    - [ ] Connector error → log, escalate if too many failures
    - [ ] All steps failed → incident.status = FAILED
- [ ] Function `async execute_step(step, alert, previous_results) → dict`
  - [ ] Get connector from registry
  - [ ] Extract input from alert using `step.input_field`
  - [ ] Call `connector.execute(params)` with retry logic
  - [ ] Return result dict
- [ ] Logging:
  - [ ] "Started playbook '{name}' for incident {id}"
  - [ ] "Executing step '{step_id}' (connector: {connector})"
  - [ ] "Step '{step_id}' completed with result: {result}"
  - [ ] "Incident {id} escalated at step '{step_id}'"
  - [ ] "Incident {id} completed successfully"
- [ ] Unit tests: `tests/test_executor.py`
  - [ ] Mock each connector
  - [ ] Test each action type (continue, escalate, fail)
  - [ ] Test retry logic
  - [ ] Test condition evaluation

---

## Phase 6: FastAPI Application & Endpoints

### 6.1 Application Setup
File: `soar/main.py`

- [ ] Initialize FastAPI app
- [ ] CORS middleware (for testing)
- [ ] Request logging middleware
- [ ] Exception handlers:
  - [ ] 404 for invalid routes
  - [ ] 500 for unhandled exceptions
  - [ ] Custom handlers for `ConnectorError`, `StateTransitionError`
- [ ] Startup events:
  - [ ] Initialize database
  - [ ] Initialize connector registry
  - [ ] Initialize APP_STATE
  - [ ] Load playbooks
  - [ ] Log: "SOAR-Lite started successfully"
- [ ] Shutdown events:
  - [ ] Close database connections
  - [ ] Cancel pending tasks
  - [ ] Log: "SOAR-Lite shutting down gracefully"

### 6.2 Alert Ingestion Endpoint
File: `soar/main.py` (routes)

- [ ] `POST /alerts/` - Ingest alert
  - [ ] Request body: `Alert` schema
  - [ ] Response: 202 Accepted with incident_id
  - [ ] Logic:
    1. Validate alert
    2. Create incident in database (PENDING status)
    3. Find matching playbook
    4. Start background task: `execute_playbook(incident)`
    5. Return: `{"incident_id": uuid, "status": "accepted"}`
  - [ ] Error handling:
    - [ ] 400 if alert validation fails
    - [ ] 500 if database error
  - [ ] Log: "Alert received from {source}: {alert_type} (severity: {severity})"

### 6.3 Incident Status Endpoint
File: `soar/main.py` (routes)

- [ ] `GET /incidents/{incident_id}` - Get incident details
  - [ ] Query database for incident + all step_executions
  - [ ] Response: 200 with Incident schema (includes steps)
  - [ ] Error handling:
    - [ ] 404 if incident not found
    - [ ] 500 if database error
  - [ ] Example response:
    ```json
    {
        "id": "uuid-123",
        "alert_id": "alert-456",
        "playbook_name": "phishing_triage",
        "status": "running",
        "verdict": null,
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:01:45Z",
        "steps": [
            {
                "id": "enrich_ip",
                "connector": "virustotal",
                "status": "completed",
                "result": {"score": 85, "vendors": {...}},
                "duration_ms": 1245,
                "started_at": "2024-01-15T10:00:05Z",
                "completed_at": "2024-01-15T10:00:06Z"
            }
        ]
    }
    ```

### 6.4 Verdict Endpoint (Analyst Input)
File: `soar/main.py` (routes)

- [ ] `POST /incidents/{incident_id}/verdict` - Analyst provides verdict
  - [ ] Request body: `{"verdict": "true_positive" | "false_positive"}`
  - [ ] Update incident.verdict in database
  - [ ] Trigger utility scoring (future Phase)
  - [ ] Log: "Verdict recorded for incident {id}: {verdict}"
  - [ ] Error handling:
    - [ ] 404 if incident not found
    - [ ] 400 if invalid verdict
    - [ ] 409 if incident not in terminal state (recommendation: only verdict COMPLETED incidents)

### 6.5 Health Check Endpoint
File: `soar/main.py` (routes)

- [ ] `GET /health` - Simple health check
  - [ ] Response: 200 OK with status
  - [ ] Example: `{"status": "healthy", "database": "connected", "tasks_running": 2}`

### 6.6 Playbooks Listing Endpoint
File: `soar/main.py` (routes)

- [ ] `GET /playbooks/` - List all available playbooks
  - [ ] Response: 200 with array of playbook names + descriptions
  - [ ] Example:
    ```json
    [
        {
            "name": "phishing_triage",
            "description": "Enriches phishing alerts with reputation data",
            "trigger_alert_type": "phishing",
            "min_severity": "medium",
            "step_count": 3
        }
    ]
    ```

### 6.7 Metrics Endpoint (Optional Phase 6)
File: `soar/main.py` (routes)

- [ ] `GET /metrics/` - System and playbook metrics
  - [ ] Query metrics from database
  - [ ] Response: 200 with metrics summary
  - [ ] Example:
    ```json
    {
        "total_incidents": 1542,
        "completed": 1200,
        "escalated": 250,
        "failed": 92,
        "playbook_utility": {
            "phishing_triage": 0.87,
            "malware_analysis": 0.72
        }
    }
    ```

---

## Phase 7: Playbook Files

### 7.1 Phishing Triage Playbook
File: `playbooks/phishing_triage.yaml`

```yaml
name: phishing_triage
description: Enriches phishing alerts with IP/domain/attachment reputation
trigger_alert_type: phishing
min_severity: medium

steps:
  - id: enrich_ip
    connector: virustotal
    input_field: source_ip
    timeout: 30
    retries: 3
    on_result:
      - if_expr: "score > 70"
        then: escalate
      - if_expr: null
        then: continue

  - id: check_abuse_ip
    connector: abuseipdb
    input_field: source_ip
    timeout: 20
    retries: 2
    on_result:
      - if_expr: "abuseConfidenceScore > 50"
        then: escalate
      - if_expr: null
        then: continue

  - id: notify_slack
    connector: slack
    input_field: null
    timeout: 10
    retries: 1
    on_result:
      - if_expr: null
        then: continue
```

### 7.2 Malware Analysis Playbook
File: `playbooks/malware_analysis.yaml`

```yaml
name: malware_analysis
description: Analyzes file hashes and IP indicators
trigger_alert_type: malware
min_severity: high

steps:
  - id: analyze_hash
    connector: virustotal
    input_field: file_hash
    timeout: 30
    retries: 3
    on_result:
      - if_expr: "score > 50"
        then: escalate
      - if_expr: null
        then: continue

  - id: create_ticket
    connector: mock_jira
    input_field: null
    timeout: 15
    retries: 2
    on_result:
      - if_expr: null
        then: continue
```

### 7.3 Abuse Report Playbook
File: `playbooks/abuse_report.yaml`

```yaml
name: abuse_report
description: Reports abusive IP/domain to Shodan and Slack
trigger_alert_type: abuse
min_severity: low

steps:
  - id: search_shodan
    connector: shodan
    input_field: ip_address
    timeout: 25
    retries: 2
    on_result:
      - if_expr: "len(ports) > 5"
        then: escalate
      - if_expr: null
        then: continue

  - id: alert_team
    connector: slack
    input_field: null
    timeout: 10
    retries: 1
    on_result:
      - if_expr: null
        then: continue
```

---

## Phase 8: Testing & Quality Assurance

### 8.1 Unit Tests: State Machine
File: `tests/test_state_machine.py`

- [ ] Test valid transitions (PENDING → RUNNING → COMPLETED)
- [ ] Test invalid transitions (COMPLETED → RUNNING)
- [ ] Test all terminal states are immutable
- [ ] Test state strings

### 8.2 Unit Tests: Evaluation Sandbox
File: `tests/test_eval_sandbox.py`

- [ ] Test valid conditions: `score > 70`, `x == 5`, `a and b`
- [ ] Test invalid expressions: `__import__`, `eval()`, `exec()`
- [ ] Test with various data types: int, str, list, dict
- [ ] Test operators: `+`, `-`, `*`, `/`, `%`, `<`, `>`, `==`, `!=`

### 8.3 Unit Tests: Connectors
File: `tests/test_connectors.py`

For each connector:
- [ ] Test successful execution with mock responses
- [ ] Test retry logic with exponential backoff
- [ ] Test timeout handling
- [ ] Test invalid input (malformed IP, wrong hash format)
- [ ] Test rate limit handling (HTTP 429)
- [ ] Test HTTP errors (401, 403, 500)

Example test:
```python
@pytest.mark.asyncio
async def test_virustotal_file_hash():
    connector = VirusTotalConnector(api_key="test-key")
    result = await connector.execute({"file_hash": "abc123"})
    
    assert "score" in result
    assert "vendors" in result
    assert result["score"] >= 0 and result["score"] <= 100
```

### 8.4 Unit Tests: Executor
File: `tests/test_executor.py`

- [ ] Test playbook execution with all steps successful
- [ ] Test playbook execution with condition triggering "escalate"
- [ ] Test playbook execution with connector error (retry then fail)
- [ ] Test playbook execution with timeout
- [ ] Test state transitions during execution
- [ ] Mock all connectors

### 8.5 Integration Tests
File: `tests/test_e2e.py`

- [ ] Full workflow: Alert ingestion → Incident creation → Playbook execution → Completion
- [ ] Use real database (temp SQLite)
- [ ] Mock external APIs (VirusTotal, Slack, etc.)
- [ ] Verify database state at each step
- [ ] Verify logging output

### 8.6 Coverage Report
- [ ] Target: 80%+ code coverage
- [ ] Run: `pytest --cov=soar tests/`
- [ ] Generate HTML report: `pytest --cov=soar --cov-report=html tests/`

### 8.7 Code Quality Checks
- [ ] Format with Black: `black soar/ tests/`
- [ ] Lint with Flake8: `flake8 soar/ tests/ --max-line-length=100`
- [ ] Type check with MyPy: `mypy soar/ --strict`
- [ ] Sort imports: `isort soar/ tests/`

### 8.8 Manual Testing Workflow
- [ ] Start app: `uvicorn soar.main:app --reload`
- [ ] Test health endpoint: `curl http://localhost:8000/health`
- [ ] Ingest alert: `curl -X POST http://localhost:8000/alerts/ -d {...}`
- [ ] Check incident status: `curl http://localhost:8000/incidents/{id}`
- [ ] Provide verdict: `curl -X POST http://localhost:8000/incidents/{id}/verdict -d {...}`

---

## Phase 9: Documentation

### 9.1 README.md
- [ ] Project overview
- [ ] Quick start guide
- [ ] Features list
- [ ] Architecture diagram
- [ ] Example alert ingestion + response

### 9.2 API Documentation (Auto-generated)
- [ ] OpenAPI spec at `/docs` (FastAPI auto-generated)
- [ ] Swagger UI at `/redoc`

### 9.3 CONNECTORS.md
- [ ] Each connector: required API keys, rate limits, example output
- [ ] How to add new connectors (registry pattern)

### 9.4 SETUP.md
- [ ] Environment setup steps
- [ ] API key configuration
- [ ] Running locally (uvicorn)
- [ ] Running tests
- [ ] Troubleshooting

### 9.5 ARCHITECTURE.md
- [ ] System design diagram
- [ ] Database schema diagram
- [ ] Request flow: Alert → Incident → Playbook → Execution
- [ ] Async execution model

---

## Phase 10: Deployment & Future Enhancements

### 10.1 Docker Setup (Optional)
- [ ] `Dockerfile` for containerized app
- [ ] `docker-compose.yml` with PostgreSQL
- [ ] Build & run instructions in `docs/DEPLOY.md`

### 10.2 Performance Optimization
- [ ] Add Redis caching for connector results (24-hour TTL)
- [ ] Batch similar queries (e.g., 10 IP lookups → 1 bulk VirusTotal call)
- [ ] Database connection pooling tuning

### 10.3 Advanced Features
- [ ] WebSocket dashboard (real-time incident updates)
- [ ] Utility scoring algorithm (Phase 11+)
- [ ] Playbook versioning (git-backed)
- [ ] Role-based access control (analyst, admin)
- [ ] Notification plugins (Teams, PagerDuty, etc.)

### 10.4 Observability
- [ ] Structured logging (JSON format)
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Prometheus metrics export
- [ ] ELK stack integration (optional)

---

## Verification Checklist (End of Each Phase)

Before moving to next phase:

- [ ] All unit tests pass: `pytest -v`
- [ ] Code coverage ≥ 80%: `pytest --cov`
- [ ] No flake8 errors: `flake8 soar/`
- [ ] No type errors: `mypy soar/`
- [ ] Manual testing workflow completed
- [ ] Documentation updated
- [ ] Git commits are atomic and well-messaged
- [ ] No hard-coded secrets in code

---

## Quick Reference: Commands

```bash
# Setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Run
uvicorn soar.main:app --reload

# Test
pytest -v                          # Run all tests
pytest tests/test_executor.py      # Run specific file
pytest --cov=soar                  # Coverage report
pytest -k "test_virustotal"        # Run specific test

# Code Quality
black soar/ tests/
flake8 soar/
mypy soar/ --strict
isort soar/ tests/

# Database
# SQLite: Auto-created on first run
# PostgreSQL: Set DATABASE_URL env var and tables auto-migrate
```

---

**Last Updated:** April 1, 2026  
**Version:** 1.0  
**Status:** Ready for Phase 1 implementation
