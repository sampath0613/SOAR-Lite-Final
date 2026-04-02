SOAR-Lite: Security Orchestration, Automation and Response Engine
A production-grade SOAR engine built from scratch in Python that automates security incident response — ingesting alerts from SIEM platforms, enriching them with third-party threat intelligence, and executing orchestrated playbooks with conditional logic. Built to directly mirror what security analysts do manually in a SOC, and automate it end to end.

What This Project Does
A security analyst at a SOC receives hundreds of alerts daily. For each one, they manually check IP reputation, look up file hashes, create Jira tickets, and decide whether to escalate or close. SOAR-Lite eliminates that manual loop. An alert arrives, the engine identifies the right playbook, executes each step automatically — querying APIs, enriching context, routing decisions — and presents the analyst with a complete incident timeline ready for a single verdict call.

Architecture
ComponentWhat It DoesAlert IngestionFastAPI webhook accepting Splunk and generic JSON alert formats; normalizes to a unified schemaPlaybook EngineReads YAML-defined workflows; executes steps sequentially with conditional routing and exponential backoff retryConnector FrameworkAbstract base class with registry pattern; current integrations: VirusTotal, AbuseIPDB, Shodan, Mock Jira, SlackIncident StoreSQLAlchemy 2.0 async ORM on SQLite; tracks every alert, step execution, and connector response with full audit trailAnalytics EngineComputes per-step utility scores post-analyst feedback; surfaces which playbook steps drive true positive verdicts and which are noiseDashboardReal-time incident queue with per-incident execution timelines and playbook health metrics via Jinja2 and AJAX polling

Playbook Development
Three reference playbooks ship with the engine, each demonstrating if-then-that automation logic:

phishing_triage.yaml — URL detonation, IP reputation check, conditional block or escalate
malware_detection.yaml — file hash lookup via VirusTotal, ticket creation in Jira, escalation on positive match
bruteforce_response.yaml — failed login threshold trigger, IP block, Slack alert

Playbooks are YAML files that any SOC analyst can read and modify without touching Python. Each step declares its connector, inputs, retry count, timeout, and the condition under which execution proceeds. The engine parses these into Pydantic models and runs them through a state machine: pending → running → completed / failed / escalated.
Jinja2 templating inside step definitions allows dynamic value injection at runtime — for example, {{ incident.src_ip }} is resolved from the live incident record before the connector call is made.

API Integration
All external tool connections are built through a unified BaseConnector interface with a registry pattern — the engine resolves connectors by name at runtime without any hardcoded dispatch logic. Adding a new integration means writing one class; nothing else changes.
Current connectors and what they do:

VirusTotal: file and URL hash lookups with confidence scoring
AbuseIPDB: IP reputation checks returning abuse reports and risk scores
Shodan: host enrichment for open ports and service fingerprints
Mock Jira: ticket creation simulator for testing escalation workflows
Slack: alert notification for escalated incidents

All connector calls are fully async using httpx, with exponential backoff retry (2, 4, 8 seconds with jitter) to handle API outages without cascading failures.

Alert Enrichment
When an alert arrives at POST /alerts, the engine automatically:

Normalizes the alert format to a standard internal schema
Matches it to compatible playbooks based on alert type and severity
Executes each enrichment step — querying VirusTotal, AbuseIPDB, or Shodan as defined in the playbook
Persists every connector response to the incident record
Surfaces the complete enriched context to the analyst on the dashboard

The analyst receives a pre-enriched incident rather than a raw alert — the manual lookup work is already done.

Workflow Testing

102 tests passing, 82% coverage
Unit tests cover connector mocks, YAML parser validation, and state machine transitions
Integration tests run end-to-end alert ingestion through verdict assignment
Load tests verify concurrent handling of 50 alerts per batch
All connector calls use sandboxed expression evaluation via simpleeval — raw Python eval is never used


Step-Utility Analytics
After analysts mark incidents as true or false positives, the analytics engine computes a utility score per playbook step:
Utility Score = Steps flagged true positive / Total steps with analyst verdict
This surfaces which automation steps are genuinely influencing analyst decisions and which are generating noise. It answers the operational question that most SOAR deployments ignore: not "did the step run successfully" but "did the step's output actually matter."

Technology Stack
Python, FastAPI, SQLAlchemy 2.0 async, aiosqlite, Pydantic 2.7, httpx, YAML, Jinja2, pytest, Ruff, mypy