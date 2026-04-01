# SOAR-Lite: Production-Grade Security Automation Engine

## 🎯 Project Overview

**SOAR-Lite** is a production-ready Security Orchestration, Automation, and Response (SOAR) engine built from scratch in Python. It automates security incident response through a modular, pluggable architecture that ingests alerts from multiple SIEM platforms, correlates threats using third-party threat intelligence APIs, and executes orchestrated playbooks with conditional logic.

**Key Achievement**: 102 passing tests with 82% code coverage, Ruff clean code standards, and full async/await architecture for non-blocking incident processing.

---

## 🏗️ Architecture & Design

### Core Components

| Component | Purpose | Implementation |
|-----------|---------|-----------------|
| **Alert Ingestion** | Webhook endpoint accepting alerts from Splunk, QRadar, generic JSON | FastAPI POST `/alerts` with schema normalization |
| **Connector Framework** | Unified interface for third-party API integration | BaseConnector abstract class with Registry pattern for dynamic resolution |
| **Playbook Engine** | YAML-defined orchestration logic with conditional routing | State machine executor with exponential backoff retry (2, 4, 8s) |
| **Incident Tracking** | Persistent storage of alerts, executions, and analyst verdicts | SQLAlchemy 2.0 async ORM with SQLite backend |
| **Analytics** | Step-level utility scoring to identify high-value automations | True positive ratio per step; identifies low-ROI playbook steps |
| **Dashboard** | Real-time incident queue visualization | Jinja2 + AJAX polling (10s refresh) for incident list and details |

### Architecture Pattern: Registry Pattern
Dynamic connector resolution eliminates hardcoded if/elif chains:
```python
CONNECTOR_REGISTRY = {
    "virustotal": VirusTotal,
    "abuseipdb": AbuseIPDB,
    "jira": MockJira
}
connector = CONNECTOR_REGISTRY[name]()  # Runtime instantiation
```

---

## 🔧 What I Built

### 1. **Async API Framework** (FastAPI)
- Webhook intake endpoint: `POST /alerts` (accepts Splunk, QRadar, generic JSON formats)
- Incident management: `GET /incidents`, `PATCH /incidents/{id}/verdict`
- Connector health checks: `/api/health`
- Analytics dashboard feed: `/api/analytics/summary`
- Playbook listing: `/api/playbooks` with step utility scores

### 2. **Connector Layer** (3 Implementations)
- **VirusTotal**: File/URL hash lookups with confidence scoring
- **AbuseIPDB**: IP reputation checks with abuse reports
- **Mock JIRA**: Ticket creation simulator for testing

All connectors implement `BaseConnector` interface with unified `execute()` and `health_check()` methods, enabling easy addition of new integrations.

### 3. **Playbook-Based Orchestration** (YAML)
3 reference playbooks demonstrating if-then-that automation:
- `phishing_triage.yaml`: Email URL detonation + IP blocking
- `malware_detection.yaml`: Hash lookup + ticket creation + escalation  
- `bruteforce_response.yaml`: Failed login threshold → IP blocking + alerting

Playbooks define:
- `trigger_alert_type`: What SIEM alerts activate this (e.g., "phishing")
- `min_severity`: Minimum threat severity to execute (critical/high/medium/low)
- `steps[]`: Sequential tasks with conditions, retries, timeouts

**Execution Flow**: 
1. Alert arrives → normalizer extracts type+severity
2. Matcher finds compatible playbooks
3. Executor runs steps sequentially with retry logic
4. Each step creates `StepExecution` record (status, output, connector used)
5. Analyst manually sets incident verdict (true_positive/false_positive)

### 4. **Database Layer** (SQLAlchemy 2.0 Async)
Three core tables with relationship tracking:
- `incidents`: Alert metadata + status (pending/running/completed/failed)
- `step_executions`: Per-step outputs, execution time, connector response
- `playbook_metrics`: Aggregated analytics (success rate, avg duration)

100% async with **aiosqlite** for non-blocking SQLite I/O.

### 5. **Analytics Engine**
Computes per-step utility scores to surface high-ROI automations:
```
Utility Score = (Steps with True Positive Verdicts) / (Total Steps with Verdict)
```
Helps security teams identify which playbook steps are worth maintaining vs. tuning/removing.

### 6. **Full-Stack Dashboard**
- **Backend**: Jinja2 template rendering incident queue
- **Frontend**: HTML/CSS/JavaScript with AJAX polling
- **Features**: Incident status cards, chronological step execution timeline, analyst verdict buttons

---

## 🛠️ How I Built It

### Technology Stack
- **Framework**: FastAPI 0.111+ (async REST with automatic OpenAPI docs)
- **ORM**: SQLAlchemy 2.0+ (async Mapped[] syntax) + aiosqlite
- **Validation**: Pydantic 2.7+ (model validation, field validators)
- **Orchestration**: YAML playbooks parsed into Pydantic models (safe eval with simpleeval, not Python eval)
- **HTTP Client**: httpx (async connector calls)
- **Frontend**: Jinja2 templates + vanilla JavaScript
- **Testing**: pytest + pytest-asyncio (102 tests, 82% coverage)
- **Code Quality**: Ruff (all checks passing), mypy type hints

### Key Engineering Decisions

**1. Async/Await Throughout**
- All database operations non-blocking (aiosqlite)
- All connector API calls concurrent (httpx)
- Alert processing spawned as background tasks (asyncio.create_task)
- Enables handling 50+ concurrent alerts without thread pools

**2. YAML as Single Source of Truth**
- No orchestration logic hardcoded in Python
- Playbooks human-readable for SOCs to modify
- Jinja2 templating in steps for dynamic values (e.g., `{{ incident.src_ip }}`)

**3. Exponential Backoff Retry**
- Failed connector calls retry: 2, 4, 8 seconds with jitter
- Prevents cascading failures during API outages
- Configurable per-step via `retries` field

**4. Registry Pattern for Connectors**
- Dynamic loading eliminates hardcoded connector dispatch
- New connectors added without modifying executor code
- Health checks at startup verify API connectivity

---

## 📊 Quality Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Test Coverage | 82% | 80% ✅ |
| Passing Tests | 102 | - |
| Lint Violations | 0 | 0 ✅ |
| Lines of Code | ~1,200 | - |
| Async Operations | 100% | - |

### Test Suite Breakdown
- **Unit**: Connector mocks, parser validation, state machine logic (50 tests)
- **Integration**: End-to-end alert ingestion through verdict assignment (30 tests)
- **Load**: Concurrent alert handling at 50 alerts/batch (15 tests)
- **E2E**: Full playbook execution with real Pydantic models (7 tests)

---

## 🎓 Key Learnings & Technical Skills Demonstrated

✅ **Async Python**: Non-blocking I/O with asyncio, aiosqlite, httpx  
✅ **API Design**: RESTful endpoints with FastAPI, automatic OpenAPI documentation  
✅ **Database Design**: Relational schema with SQLAlchemy 2.0 async ORM  
✅ **Software Architecture**: Registry pattern, dependency injection, separation of concerns  
✅ **Testing Discipline**: 82% coverage with unit + integration + load tests  
✅ **Security Practices**: Sandboxed expression evaluation (simpleeval, never raw eval)  
✅ **DevOps Thinking**: Environment-driven config, health checks, graceful degradation  
✅ **Documentation**: Clear SOPs and architectural decision records  

---

## 🚀 Why This Project Matters

SOAR platforms are **force multipliers in InfoSec**. By automating repetitive alert triage and response workflows, teams can:
- Reduce incident response time from **hours to minutes**
- Scale threat detection without hiring more analysts
- Ensure consistent, documented response procedures
- Free analysts for complex investigations and threat hunting

This project demonstrates understanding of both the **technical architecture** (async APIs, connectors, databases) and **business value** (automation ROI, incident resolution speed).

---

## 💡 Future Enhancements

- [ ] DAG-based playbook execution (parallel step handling)
- [ ] WebSocket live dashboard refresh (vs. polling)
- [ ] Playbook versioning + rollback
- [ ] Advanced alerting rules (ML-based anomaly detection)
- [ ] Multi-tenant incident isolation

---

## 📝 License

MIT

---

**Built by a Security Automation Engineer for S&P Global | April 2026**
