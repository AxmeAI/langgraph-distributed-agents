"""LangGraph compliance agent - AXME integration handler.

Listens for intents via SSE, runs compliance check, resumes with result.
The LangGraph integration is in agent_a.py/agent_b.py (requires OPENAI_API_KEY).
This simplified agent tests the AXME delivery and resume flow.

Usage:
    export AXME_API_KEY="<agent-key>"
    python agent.py
"""

import os, sys, time
sys.stdout.reconfigure(line_buffering=True)
from axme import AxmeClient, AxmeClientConfig

AGENT_ADDRESS = "langgraph-compliance-demo"

def handle_intent(client, intent_id):
    intent_data = client.get_intent(intent_id)
    intent = intent_data.get("intent", intent_data)
    payload = intent.get("payload", {})
    if "parent_payload" in payload:
        payload = payload["parent_payload"]

    change_id = payload.get("change_id", "unknown")
    service = payload.get("service", "unknown")
    env = payload.get("environment", "unknown")

    print(f"  [LangGraph] Checking compliance for {change_id}: {service} -> {env}...")
    time.sleep(1)
    print(f"  [LangGraph] Running policy validation graph...")
    time.sleep(1)

    result = {
        "action": "complete",
        "change_id": change_id,
        "compliant": True,
        "checks_passed": ["security_policy", "data_retention", "access_control"],
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    client.resume_intent(intent_id, result)
    print(f"  [LangGraph] Compliance check passed for {change_id}")

def main():
    api_key = os.environ.get("AXME_API_KEY", "")
    if not api_key:
        print("Error: AXME_API_KEY not set."); sys.exit(1)
    client = AxmeClient(AxmeClientConfig(api_key=api_key))
    print(f"Agent listening on {AGENT_ADDRESS}...")
    print("Waiting for intents (Ctrl+C to stop)\n")
    for delivery in client.listen(AGENT_ADDRESS):
        intent_id = delivery.get("intent_id", "")
        status = delivery.get("status", "")
        if intent_id and status in ("DELIVERED", "CREATED", "IN_PROGRESS"):
            print(f"[{status}] Intent received: {intent_id}")
            try:
                handle_intent(client, intent_id)
            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    main()
