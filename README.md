# LangGraph Distributed Agents with AXME

Your LangGraph agent works great on one machine. But now you need two agents on
different servers to coordinate — with human approval in between. LangGraph
handles state machines and reasoning beautifully, but it doesn't handle durable
cross-machine delivery, retries on failure, or waiting days for human approval.
That's what AXME adds.

> **Alpha** -- AXME is in alpha. APIs may change. Not recommended for production
> workloads without contacting the team first. See [AXME Cloud Alpha](https://cloud.axme.ai/alpha).

---

## Before / After

### Before: DIY Infrastructure

```python
# You end up building this yourself:
import redis, celery, requests, json, smtplib

# Message queue for cross-machine delivery
celery_app = Celery('agents', broker='redis://...')

# Manual retry logic
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_to_risk_assessor(self, data):
    try:
        requests.post("http://agent-b:8000/assess", json=data)
    except Exception as exc:
        self.retry(exc=exc)

# Human approval? Build a whole web app...
# Timeouts? Write a cron job...
# Observability? Add logging everywhere...
# 200+ lines before any actual agent logic
```

### After: AXME Handles It

```python
# Agent A: LangGraph compliance checker sends to Agent B via AXME
intent_id = client.send_intent({
    "intent_type": "risk_assessment",
    "to_agent": "agent://risk-assessor",
    "payload": {"document": compliance_result, "requires_human_approval": True}
})
# AXME handles: delivery, retries, human approval gate, timeouts, observability
result = client.wait_for(intent_id, timeout_seconds=86400)
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your AXME API key and OpenAI API key
```

### 3. Run the scenario

```bash
# Terminal 1: Start the compliance agent (Agent A)
python agent_a.py

# Terminal 2: Start the risk assessor agent (Agent B) — can be a different machine
python agent_b.py

# Terminal 3: Send a document for processing
python initiator.py
```

The initiator sends a document through the compliance pipeline. Agent A runs
LangGraph compliance checks, then AXME delivers the result to Agent B for risk
assessment. A human approval step is required before final processing.

---

## How It Works

```
┌───────────────────┐       ┌──────────────────┐       ┌───────────────────┐
│  Machine 1        │       │   AXME Cloud     │       │  Machine 2        │
│                   │       │                  │       │                   │
│  ┌─────────────┐  │ send  │  ┌────────────┐  │deliver│  ┌─────────────┐  │
│  │  Agent A    │──┼─────> │  │  Intent    │──┼─────> │  │  Agent B    │  │
│  │  LangGraph  │  │       │  │  Queue     │  │       │  │  LangGraph  │  │
│  │  Compliance │  │       │  │  + Retry   │  │       │  │  Risk Assess│  │
│  └─────────────┘  │       │  │  + Timeout │  │       │  └──────┬──────┘  │
│                   │       │  └────────────┘  │       │         │         │
│                   │       │  ┌────────────┐  │       │         │         │
│                   │       │  │  Human     │<─┼───────┼─────────┘         │
│                   │       │  │  Approval  │  │       │                   │
│                   │       │  │  Gate      │  │       │                   │
│                   │       │  └────────────┘  │       │                   │
└───────────────────┘       └──────────────────┘       └───────────────────┘
```

1. **Initiator** sends a compliance-check intent to Agent A via AXME
2. **Agent A** (LangGraph) runs compliance analysis using LLM reasoning
3. Agent A sends a `risk_assessment` intent to Agent B via AXME (durable, retried)
4. **Agent B** (LangGraph) receives and runs risk assessment
5. Agent B requests **human approval** via AXME before finalizing
6. Human approves (can be hours or days later) — AXME holds state durably
7. Agent B completes, result flows back through AXME to the initiator

---

## What Each Component Does

| Component | Role | Framework |
|-----------|------|-----------|
| `agent_a.py` | Compliance checker — validates documents using LLM | LangGraph |
| `agent_b.py` | Risk assessor — scores risk and requests human approval | LangGraph |
| `initiator.py` | Sends a document into the pipeline, waits for result | AXME SDK |
| `scenario.json` | Defines agents, workflow, and approval gates | AXP Scenario |

**LangGraph** does the AI thinking (compliance rules, risk scoring, LLM calls).
**AXME** does the infrastructure (cross-machine delivery, human gates, retries, timeouts).

---

## Works With

This pattern works with any LangGraph agent. AXME is framework-agnostic — it
coordinates between agents regardless of what framework they use internally:

- **LangGraph** / **LangChain** agents
- **OpenAI Agents SDK** agents
- **AutoGen** agents
- **CrewAI** agents
- Plain Python scripts
- Any HTTP-capable service

---

## Run the Full Example

### Prerequisites

```bash
# Install CLI (one-time)
curl -fsSL https://raw.githubusercontent.com/AxmeAI/axme-cli/main/install.sh | sh
# Open a new terminal, or run the "source" command shown by the installer

# Log in
axme login

# Install Python SDK
pip install axme
```

### Terminal 1 - submit the intent

```bash
axme scenarios apply scenario.json
# Note the intent_id in the output
```

### Terminal 2 - start the agent

Get the agent key after scenario apply:

```bash
# macOS
cat ~/Library/Application\ Support/axme/scenario-agents.json | grep -A2 langgraph-compliance-demo

# Linux
cat ~/.config/axme/scenario-agents.json | grep -A2 langgraph-compliance-demo
```

Then run the agent:

```bash
# Python (SSE stream listener)
AXME_API_KEY=<agent-key> python agent.py
```

### Verify

```bash
axme intents get <intent_id>
# lifecycle_status: COMPLETED
```

---

## Related

- [AXME Python SDK](https://github.com/AxmeAI/axme-sdk-python) -- `pip install axme`
- [AXME Documentation](https://github.com/AxmeAI/axme-docs)
- [AXME Examples](https://github.com/AxmeAI/axme-examples) -- more patterns (delivery, durability, human-in-the-loop)
- [AXP Intent Protocol Spec](https://github.com/AxmeAI/axme-spec)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)

---

Built with [AXME](https://github.com/AxmeAI/axme) (AXP Intent Protocol).
