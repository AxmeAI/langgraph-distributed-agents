"""
Agent A — Compliance Checker (LangGraph + AXME)

Listens for compliance-check intents via AXME inbox, runs a LangGraph
compliance analysis graph, then sends the result to Agent B (risk assessor)
via AXME for cross-machine delivery.

Requires: AXME_API_KEY, OPENAI_API_KEY
"""

from __future__ import annotations

import json
import os
import sys
import time

from axme import AxmeClient, AxmeClientConfig
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from typing import TypedDict

# ---------------------------------------------------------------------------
# LangGraph: Compliance Analysis Graph
# ---------------------------------------------------------------------------

class ComplianceState(TypedDict):
    document: str
    compliance_issues: list[str]
    is_compliant: bool
    summary: str


def analyze_compliance(state: ComplianceState) -> ComplianceState:
    """Use LLM to analyze document for compliance issues."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    response = llm.invoke(
        f"Analyze this document for regulatory compliance issues. "
        f"List any problems found. If compliant, say 'No issues found.'\n\n"
        f"Document:\n{state['document']}"
    )
    content = response.content
    issues = [
        line.strip("- ").strip()
        for line in content.strip().split("\n")
        if line.strip() and line.strip().lower() != "no issues found."
    ]
    return {
        **state,
        "compliance_issues": issues,
        "is_compliant": len(issues) == 0,
        "summary": content,
    }


def format_result(state: ComplianceState) -> ComplianceState:
    """Format the compliance result for downstream consumption."""
    return state


def build_compliance_graph() -> StateGraph:
    graph = StateGraph(ComplianceState)
    graph.add_node("analyze", analyze_compliance)
    graph.add_node("format", format_result)
    graph.add_edge("analyze", "format")
    graph.add_edge("format", END)
    graph.set_entry_point("analyze")
    return graph.compile()


# ---------------------------------------------------------------------------
# AXME: Agent Loop
# ---------------------------------------------------------------------------

AGENT_URI = "agent://compliance-checker"

def main() -> None:
    api_key = os.environ.get("AXME_API_KEY")
    if not api_key:
        print("Error: AXME_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))
    graph = build_compliance_graph()

    print(f"Agent A (Compliance Checker) running as {AGENT_URI}")
    print("Polling AXME inbox for compliance_check intents...")

    while True:
        try:
            inbox = client.list_inbox(owner_agent=AGENT_URI)
            threads = inbox.get("threads", [])

            for thread in threads:
                intent_id = thread.get("intent_id")
                intent = client.get_intent(intent_id)
                payload = intent.get("payload", {})
                intent_type = intent.get("intent_type", "")

                if intent_type != "compliance_check":
                    continue

                if intent.get("status") != "pending_action":
                    continue

                print(f"\n--- Processing compliance check: {intent_id} ---")
                document = payload.get("document", "")

                # Run LangGraph compliance analysis
                result = graph.invoke({
                    "document": document,
                    "compliance_issues": [],
                    "is_compliant": False,
                    "summary": "",
                })

                print(f"Compliance result: {'COMPLIANT' if result['is_compliant'] else 'NON-COMPLIANT'}")
                print(f"Issues: {result['compliance_issues']}")

                # Send result to Agent B (risk assessor) via AXME
                risk_intent_id = client.send_intent({
                    "intent_type": "risk_assessment",
                    "to_agent": "agent://risk-assessor",
                    "payload": {
                        "document": document,
                        "compliance_result": {
                            "is_compliant": result["is_compliant"],
                            "issues": result["compliance_issues"],
                            "summary": result["summary"],
                        },
                        "source_intent_id": intent_id,
                        "requires_human_approval": True,
                    },
                })
                print(f"Sent risk_assessment intent to Agent B: {risk_intent_id}")

                # Resolve our intent with the compliance result
                client.resolve_intent(
                    intent_id,
                    {
                        "status": "compliance_checked",
                        "is_compliant": result["is_compliant"],
                        "risk_intent_id": risk_intent_id,
                    },
                    owner_agent=AGENT_URI,
                )
                print(f"Resolved compliance check intent: {intent_id}")

        except KeyboardInterrupt:
            print("\nShutting down Agent A...")
            break
        except Exception as exc:
            print(f"Error processing inbox: {exc}", file=sys.stderr)

        time.sleep(3)


if __name__ == "__main__":
    main()
