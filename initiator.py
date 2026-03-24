"""
Initiator — Sends a document through the compliance + risk pipeline.

Sends a compliance_check intent to Agent A, then observes the full lifecycle
as it flows through Agent A -> Agent B -> human approval -> completion.

Requires: AXME_API_KEY
"""

from __future__ import annotations

import json
import os
import sys

from axme import AxmeClient, AxmeClientConfig


SAMPLE_DOCUMENT = """
VENDOR AGREEMENT — Acme Corp & GlobalTech Ltd.

1. Payment terms: Net-90 with 2% early payment discount.
2. Data handling: Vendor stores customer PII in US-based data centers.
3. Liability cap: Limited to 12 months of fees paid.
4. Termination: Either party may terminate with 30 days written notice.
5. Compliance: Vendor certifies SOC 2 Type II and GDPR compliance.
6. Subprocessors: Vendor may engage subprocessors without prior notice.
"""


def main() -> None:
    api_key = os.environ.get("AXME_API_KEY")
    if not api_key:
        print("Error: AXME_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))

    print("Sending compliance check intent to Agent A...")
    intent_id = client.send_intent({
        "intent_type": "compliance_check",
        "to_agent": "agent://compliance-checker",
        "payload": {
            "document": SAMPLE_DOCUMENT.strip(),
            "check_type": "vendor_agreement",
        },
    })
    print(f"Intent created: {intent_id}")
    print("Observing lifecycle events...\n")

    for event in client.observe(intent_id):
        event_type = event.get("event_type", "unknown")
        print(f"  [{event_type}] {json.dumps(event.get('data', {}), indent=2)[:200]}")

        if event_type in ("intent.completed", "intent.failed", "intent.cancelled"):
            break

    # Fetch final state
    final = client.get_intent(intent_id)
    print(f"\nFinal status: {final.get('status')}")
    print(f"Result: {json.dumps(final.get('result', {}), indent=2)}")


if __name__ == "__main__":
    main()
