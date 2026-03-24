"""
Agent B — Risk Assessor (LangGraph + AXME)

Listens for risk_assessment intents via AXME inbox, runs a LangGraph
risk scoring graph, then requests human approval via AXME before
completing the assessment.

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
# LangGraph: Risk Assessment Graph
# ---------------------------------------------------------------------------

class RiskState(TypedDict):
    document: str
    compliance_result: dict
    risk_score: float
    risk_level: str
    risk_factors: list[str]
    recommendation: str


def assess_risk(state: RiskState) -> RiskState:
    """Use LLM to perform risk assessment."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    compliance_info = json.dumps(state["compliance_result"], indent=2)
    response = llm.invoke(
        f"Based on this document and compliance analysis, provide a risk assessment.\n"
        f"Rate risk from 0.0 (no risk) to 1.0 (extreme risk).\n"
        f"Format: first line is the numeric score, then list risk factors.\n\n"
        f"Compliance Analysis:\n{compliance_info}\n\n"
        f"Document:\n{state['document']}"
    )
    content = response.content.strip()
    lines = content.split("\n")

    # Parse risk score from first line
    score = 0.5
    for line in lines:
        try:
            score = float(line.strip().rstrip("."))
            break
        except ValueError:
            continue

    risk_factors = [
        line.strip("- ").strip()
        for line in lines[1:]
        if line.strip() and line.strip().startswith("-")
    ]

    if score >= 0.7:
        risk_level = "high"
    elif score >= 0.4:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        **state,
        "risk_score": score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "recommendation": f"Risk level: {risk_level} ({score:.2f}). "
                         f"{'Requires immediate attention.' if risk_level == 'high' else 'Standard review process.'}",
    }


def prepare_report(state: RiskState) -> RiskState:
    """Prepare final risk report."""
    return state


def build_risk_graph() -> StateGraph:
    graph = StateGraph(RiskState)
    graph.add_node("assess", assess_risk)
    graph.add_node("report", prepare_report)
    graph.add_edge("assess", "report")
    graph.add_edge("report", END)
    graph.set_entry_point("assess")
    return graph.compile()


# ---------------------------------------------------------------------------
# AXME: Agent Loop
# ---------------------------------------------------------------------------

AGENT_URI = "agent://risk-assessor"

def main() -> None:
    api_key = os.environ.get("AXME_API_KEY")
    if not api_key:
        print("Error: AXME_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))
    graph = build_risk_graph()

    print(f"Agent B (Risk Assessor) running as {AGENT_URI}")
    print("Polling AXME inbox for risk_assessment intents...")

    while True:
        try:
            inbox = client.list_inbox(owner_agent=AGENT_URI)
            threads = inbox.get("threads", [])

            for thread in threads:
                intent_id = thread.get("intent_id")
                intent = client.get_intent(intent_id)
                payload = intent.get("payload", {})
                intent_type = intent.get("intent_type", "")

                if intent_type != "risk_assessment":
                    continue

                if intent.get("status") != "pending_action":
                    continue

                print(f"\n--- Processing risk assessment: {intent_id} ---")

                # Run LangGraph risk assessment
                result = graph.invoke({
                    "document": payload.get("document", ""),
                    "compliance_result": payload.get("compliance_result", {}),
                    "risk_score": 0.0,
                    "risk_level": "",
                    "risk_factors": [],
                    "recommendation": "",
                })

                print(f"Risk score: {result['risk_score']:.2f} ({result['risk_level']})")
                print(f"Factors: {result['risk_factors']}")

                if payload.get("requires_human_approval", False):
                    # Request human approval via AXME — durable wait
                    print("Requesting human approval via AXME...")
                    client.resume_intent(
                        intent_id,
                        {
                            "status": "pending_human_approval",
                            "risk_assessment": {
                                "risk_score": result["risk_score"],
                                "risk_level": result["risk_level"],
                                "risk_factors": result["risk_factors"],
                                "recommendation": result["recommendation"],
                            },
                            "message": "Risk assessment complete. Awaiting human approval to proceed.",
                        },
                        owner_agent=AGENT_URI,
                    )
                    print(f"Intent {intent_id} waiting for human approval (can take hours/days)")
                    print("Use AXME CLI or dashboard to approve:")
                    print(f"  axme intent resume {intent_id} --payload '{{\"approved\": true}}'")
                else:
                    # No approval needed — resolve directly
                    client.resolve_intent(
                        intent_id,
                        {
                            "status": "completed",
                            "risk_assessment": {
                                "risk_score": result["risk_score"],
                                "risk_level": result["risk_level"],
                                "risk_factors": result["risk_factors"],
                                "recommendation": result["recommendation"],
                            },
                        },
                        owner_agent=AGENT_URI,
                    )
                    print(f"Resolved risk assessment intent: {intent_id}")

        except KeyboardInterrupt:
            print("\nShutting down Agent B...")
            break
        except Exception as exc:
            print(f"Error processing inbox: {exc}", file=sys.stderr)

        time.sleep(3)


if __name__ == "__main__":
    main()
