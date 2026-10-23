"""Evidence fusion and policy outcomes (service steps 4 and 5; docs/CONTRACT.md section 8).

K2 needs only the customer message; `fuse()` arrives with K6.
"""

from __future__ import annotations

from pulselens.contracts import CustomerMessage, CustomerStatus, Decision, SessionState


def customer_message(state: SessionState, decision: Decision | None) -> CustomerStatus:
    """The only result a customer ever sees (CONTRACT section 2): never a score, family, check or outcome."""
    message: CustomerMessage = "please_wait"
    if state == "done" and decision is not None:
        if decision.outcome == "PASS":
            message = "continue"
        elif decision.outcome == "RETRY_STEP_UP":
            message = {"fresh_challenge": "please_retry", "assisted_kyc": "assisted_route"}.get(
                decision.step_up or "", "please_wait"
            )
    return CustomerStatus(state=state, message=message)
