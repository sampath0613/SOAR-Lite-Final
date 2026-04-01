# SOAR-Lite Architecture

SOAR-Lite is a distributed Security Orchestration, Automation and Response (SOAR) engine built entirely from scratch in Python. This document describes the system architecture, data flow, and key design patterns.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SYSTEMS                            │
│   Splunk │ QRadar │ Falco │ SIEM │ IDS/IPS │ SOAR Platforms    │
└────────┬─────────────────────────────────────────────────────┬──┘
         │  (Send Alerts)                 (Receive Status)     │
         │                                                      │
    ┌────▼──────────────────────────────────────────────────────▼───┐
    │                    SOAR-LITE API                              │
    │  ┌──────────────────────────────────────────────────────────┐ │
    │  │  POST /alerts              POST /incidents/{id}/verdict │ │
    │  │  GET /incidents            GET /playbooks              │ │
    │  │  GET /health               GET /analytics/summary      │ │
    │  └──────────────────────────────────────────────────────────┘ │
    └────┬──────────────────────────────────────┬─────────────────┘
         │                                      │
    ┌────▼──────────────────┐     ┌─────────────▼──────────────┐
    │   ORCHESTRATION       │     │   DATA PERSISTENCE        │
    │   ENGINE              │     │   & ANALYTICS              │
    │ ┌─────────────────┐   │     │ ┌────────────────────────┐ │
    │ │ Parser: Load    │   │     │ │ SQLite / PostgreSQL    │ │
    │ │ YAML playbooks  │   │     │ │ Incidents table        │ │
    │ │ Matcher: Route  │   │     │ │ Step Executions        │ │
    │ │ alerts to plans │   │     │ │ Playbook Metrics       │ │
    │ │ StateMachine:   │   │     │ │ Utility Scores         │ │
    │ │ Enforce valid   │   │     │ └────────────────────────┘ │
    │ │ transitions     │   │     │                             │
    │ │ Executor: Run   │   │     │ Analytics Module:           │
    │ │ steps w/ retry  │   │     │ • Compute per-step utility  │
    │ │ logic           │   │     │ • Track connector errors    │
    │ │ Condition eval  │   │     │ • False positive rate       │
    │ │ (simpleeval)    │   │     │                             │
    │ └─────────────────┘   │     │                             │
    └────────┬──────────────┘     └────────┬────────────────────┘
             │                             │
             └──────────────┬──────────────┘
                            │
    ┌───────────────────────▼─────────────────────────────────┐
    │         CONNECTOR REGISTRY & EXECUTION                  │
    │ ┌────────────────┬────────────────┬────────────────────┐ │
    │ │ VirusTotal     │ AbuseIPDB      │ Shodan             │ │
    │ │ IP Reputation  │ Abuse Scoring  │ Internet Recon     │ │
    │ ├────────────────┼────────────────┼────────────────────┤ │
    │ │ Slack          │ MockJira       │ ...extensible...   │ │
    │ │ Notifications  │ Ticket         │ User Connectors    │ │
    │ │                │ Management     │                    │ │
    │ └────────────────┴────────────────┴────────────────────┘ │
    │ ┌────────────────────────────────────────────────────────┐ │
    │ │ Execution: Async + Retry (Exponential Backoff)        │ │
    │ │ Timeout: Configurable per-step (default 30s)          │ │
    │ │ Retries: Exponential backoff 2^attempt seconds        │ │
    │ └────────────────────────────────────────────────────────┘ │
    └───────────────────────┬──────────────────────────────────┘
                            │
                ┌───────────▼──────────────┐
                │ External APIs            │
                │ • api.virustotal.com    │
                │ • api.abuseipdb.com     │
                │ • api.shodan.io         │
                │ • api.slack.com         │
                └──────────────────────────┘
```

## Data Flow: Alert → Incident → Resolution

### 1. Alert Ingestion
```
Client POST /alerts {
  alert_type: "phishing",
  severity: "high",
  source_ip: "192.168.1.100",
  source_system: "splunk"
}
   ↓
Normalize: Convert Splunk/QRadar/Mock → Unified Alert Schema
   ↓
Match: Find playbook where alert_type matches AND severity >= min_severity
   ↓
Create: Incident(id, alert_id, playbook_name, status=PENDING)
   ↓
Background Task: execute_playbook(incident) [non-blocking 202 response]
   ↓
Response: 202 Accepted {
  incident_id: "550e8400-e29b",
  playbook_matched: "phishing_triage",
  status: "accepted"
}
```

### 2. Playbook Execution
```
Incident(status=PENDING)
   ↓ Validate state transition
Incident(status=RUNNING) [persisted to DB]
   ↓
For each Step in Playbook.steps:
   ├─ Create StepExecution(status=PENDING)
   ├─ Extract input from alert by step.input_field
   ├─ Get connector from registry
   ├─ Retry loop (max attempts = step.retries):
   │  ├─ Update StepExecution(status=RUNNING)
   │  ├─ Execute: await asyncio.wait_for(
   │  │    connector.execute(params), 
   │  │    timeout=step.timeout
   │  │  )
   │  ├─ On success: break, StepExecution(status=COMPLETED)
   │  ├─ On TimeoutError/HTTPError: 
   │  │  sleep(2^attempt), retry
   │  └─ On max retries: StepExecution(status=FAILED)
   │     Incident(status=ESCALATED), return early
   ├─ Evaluate on_result conditions:
   │  ├─ For each Condition in step.on_result:
   │  │  ├─ Evaluate: if_expr against result using simpleeval
   │  │  └─ Route based on then:
   │  │     - escalate: Incident(status=ESCALATED), return
   │  │     - close: Incident(status=COMPLETED), return
   │  │     - continue: proceed to next step
   │  │     - step_id: jump to named step
   │  └─ If no condition matches: proceed to next step
   └─
After all steps: Incident(status=COMPLETED)
```

### 3. Verdict & Utility Scoring
```
Analyst reviews incident and submits:
  PATCH /incidents/{id}/verdict {
    verdict: "true_positive" | "false_positive"
  }
   ↓
Update: Incident.analyst_verdict
   ↓
Compute Step Utility: 
   For each step in playbook:
     utility_score = 
       (true_positive_count) / (total_with_verdict)
   OR 0.5 (neutral) if no verdicts
   ↓
Recommendation:
   score >= 0.4 → "keep"
   score < 0.4  → "review"
```

## Key Architectural Decisions

### 1. **YAML Playbooks (Not JSON)**
**Why:** 
- Comments support for documentation inside playbooks
- More human-readable for security teams
- Aligns with Infrastructure-as-Code (Kubernetes pattern)
- Industry standard (Splunk also uses YAML for automation)

**Code Pattern:**
```yaml
name: phishing_triage
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
        then: close
```

### 2. **simpleeval vs eval() for Condition Evaluation**
**Decision:** Use `simpleeval.EvalWithCompoundTypes()` for all condition expressions

**Why:**
- `eval()` is a **critical security risk** - executes arbitrary Python code
- `simpleeval` restricts to math/comparison/logic operations only
- Zero access to `__builtins__`, `__import__`, system functions
- Deterministic: Same input → Same output
- **Real-world SOAR attack vector:** Malicious actors could inject code into YAML playbooks

**Example:**
```python
# SAFE: simpleeval
condition_str = "score > 70 and abuse_score < 50"
result = EvalWithCompoundTypes(condition_str, names=step_result.data)

# UNSAFE: eval (never use)
eval(condition_str)  # Could execute: __import__('os').system('rm -rf /')
```

### 3. **Async/Await Throughout (Non-Blocking I/O)**
**Why:**
- HTTP connectors (VirusTotal, AbuseIPDB, Shodan) are I/O-bound
- Standard Python `httpx` is async-native
- 50+ concurrent incidents processed without thread overhead
- Critical for SOAR: Incident orchestration is waiting-intensive

**Pattern:**
```python
# Parallel execution of independent steps (future enhancement)
tasks = [
    execute_step(step1),
    execute_step(step2),
    execute_step(step3),
]
results = await asyncio.gather(*tasks)

# Current: Sequential (simpler error handling)
for step in playbook.steps:
    result = await execute_step(step)
    if error: handle_escalation()
```

### 4. **Exponential Backoff Retry Logic**
**Algorithm:**
```
Attempt 1: Fail → Sleep 2^1 = 2 seconds
Attempt 2: Fail → Sleep 2^2 = 4 seconds
Attempt 3: Fail → Sleep 2^3 = 8 seconds
Max attempts: 3 (configurable per step)
```

**Why:**
- Handles transient failures (rate limits, timeouts, network hiccups)
- Reduces thundering herd (distributed backoff)
- VirusTotal rate limit: 4 req/min → 60 sec between attempts using backoff
- Incident doesn't fail on first hiccup

### 5. **Registry Pattern for Connectors (No Hardcoding)**
**Why:**
- Add new connectors without touching executor code
- Runtime discovery via `get_connector(name)` from registry
- Dependency inversion: Executor depends on interface, not implementations
- Easy testing: Mock connector registration

**Structure:**
```python
CONNECTOR_REGISTRY = {
    "virustotal": VirusTotalConnector(),
    "abuseipdb": AbuseIPDBConnector(),
    "shodan": ShodanConnector(),
    "slack": SlackConnector(),
    "mock_jira": MockJiraConnector(),
}

async def execute_step(step):
    connector = get_connector(step.connector)  # Dynamic
    result = await connector.execute(params)
```

### 6. **Three-Layer Persistence: (Incidents, Steps, Metrics)**
**Tables:**

| Table | Purpose | Uses |
|-------|---------|------|
| `Incident` | Case management | Status tracking, verdict collection, timeline |
| `StepExecution` | Audit trail | Per-step granularity, debugging, retry history |
| `PlaybookMetrics` | Performance tracking | Utility scores, connector error rates |

**Why separate:**
- **Incidents** = "What happened to the alert?"
- **StepExecution** = "In detail, what did each step do?"
- **PlaybookMetrics** = "How well is this playbook performing?"

**Real scenario:**
```
Incident: "Phishing alert on john@company.com - CLOSED (analyst: false_positive)"
    ↓ StepExecution (timeline):
    ├─ 14:23:01 VirusTotal: "score=15" 
    ├─ 14:23:04 AbuseIPDB: "abuse_score=12"
    ├─ 14:23:07 MockJira: "ticket_id=SOAR-5432"
    ↓ PlaybookMetrics (trending):
    ├─ phishing_triage overall: 87% utility (high value)
    ├─ VirusTotal step: 91% utility (detect real threats)
    ├─ MockJira: 12% utility (rarely creates useful tickets)
```

### 7. **Database Agnostic: SQLite MVP → PostgreSQL Production**
**Connection String:**
```python
# Development
DATABASE_URL = "sqlite+aiosqlite:///./soar_lite.db"

# Production (just swap, no code changes)
DATABASE_URL = "postgresql+asyncpg://user:pwd@db.company.com:5432/soar"
```

**Why:**
- SQLite for rapid prototyping, no Docker needed
- PostgreSQL scales to 10k+ incidents/day
- Same async SQLAlchemy 2.x code works for both

### 8. **State Machine Enforces Valid Transitions**
**Incident states:**
```
PENDING → RUNNING → [COMPLETED | FAILED | ESCALATED]
                    (terminal states)
```

**Why:**
- Prevent impossible state changes (COMPLETED → RUNNING)
- Safety: Invalid transitions raise `StateTransitionError`
- Audit: Every status change is logged and persisted

**Code:**
```python
await validate_incident_transition(
    IncidentState.PENDING, 
    IncidentState.RUNNING
)  # OK

await validate_incident_transition(
    IncidentState.COMPLETED, 
    IncidentState.RUNNING
)  # Raises StateTransitionError
```

## Scalability Considerations

### Current (MPV):
- **Throughput:** 50+ concurrent alerts (testing validated)
- **Latency:** Sub-second playbook execution for cacheable lookups
- **Storage:** SQLite on single machine (limited to ~1GB active incident data)

### Production Path:
1. **PostgreSQL** for multi-instance database
2. **Redis cache** for connector responses (VirusTotal reputation scores change infrequently)
3. **Kafka/RabbitMQ** for alert queue (decouple ingestion from processing)
4. **Horizontal scaling:** Multiple SOAR worker pods, shared database
5. **Coordinator:** Prevent duplicate processing of same incident

### Design for Scale:
```
Load Balancer
    ↓
[SOAR Worker 1] ─┐
[SOAR Worker 2] ─┼─→ PostgreSQL + Redis
[SOAR Worker 3] ─┘
    ↑
Kafka Queue (Alert Buffer)
    ↑
    └─ Splunk / QRadar / Falco
```

## Next Phases (Future Work)

### Phase 7: WebSocket Dashboard
- Real-time incident updates
- Live playbook execution visualization
- Analyst verdict form (already in API)

### Phase 11+: Advanced Features
- Parallel step execution (currently sequential)
- Cross-playbook incident correlation
- ML-based playbook optimization
- Slack interactive buttons (approve/reject actions)
- Webhook callbacks (incident resolved → notify Slack)
- Responder tracking: Which playbook caught how many incidents?

## Monitoring & Observability

### Metrics to track:
1. **Incident**: total, by_status, avg_resolution_time
2. **Connectors**: execution_count, failed_count, error_rate, latency_p95
3. **Playbooks**: execution_count, step_utility_scores, false_positive_rate
4. **System**: queue_depth, worker_utilization, db_query_latency

### Logging:
```python
# Structured logging template:
logger.info(f"[{incident_id}] [step_id] message")
# Example:
logger.info("[550e8400-e29b] [enrich_ip] VirusTotal returned score=85")
```

## Deployment Checklist

- [ ] Configure `.env` with API keys (VirusTotal, AbuseIPDB, Shodan, Slack)
- [ ] Set `DATABASE_URL` (SQLite for test, PostgreSQL for prod)
- [ ] Load playbooks from `playbooks/` directory
- [ ] Start: `uvicorn soar.main:app --host 0.0.0.0 --port 8000`
- [ ] Test health: `curl http://localhost:8000/health/`
- [ ] Monitor logs for errors
- [ ] Backup incidents database nightly (PostgreSQL backups)

---

**Last Updated:** April 1, 2026  
**Version:** 0.1.0 (MVP)  
**Author:** Security Automation Engineer
