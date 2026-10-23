"""REUSABLE DECISION PATTERN: LocalGigs application guardrail (#guardrails)."""

from __future__ import annotations

import json
from typing import Any

from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed
from decider_kit import Decider
from decider_kit.patterns.guardrails import render_messages

PATTERN_TAG = "#guardrails"
GUARDED_TOOLS = {"submit_application"}

QUESTIONS = {
    "args_grounded": Decider.noul(
        "Are the gig and application details grounded in the conversation or tool results?",
        {
            "true": "The gig ID and applicant details were provided or retrieved.",
            "false": "One or more details were guessed or invented.",
        },
    ),
    "explicit_request": Decider.noul(
        "Has the applicant clearly asked to submit this application now?",
        {
            "true": "The applicant explicitly requests submission.",
            "false": "They are only asking questions or exploring options.",
        },
    ),
    "premature": Decider.noul(
        "Should the assistant clarify or confirm details before submitting?",
        {
            "true": "Important details are unclear or confirmation is needed.",
            "false": "The request and required details are clear.",
        },
    ),
}


class ApplicationGuard(InterventionHandler):
    name = "localgigs-application-guard"

    def __init__(
        self,
        decider: Decider,
        yes: float = 0.5,
        unsure_band: tuple[float, float] = (0.4, 0.6),
    ):
        self.decider = decider
        self.yes = yes
        self.unsure_band = unsure_band
        self.log: list[dict[str, Any]] = []
        self._guided: set[str] = set()

    def before_invocation(self, event, **kwargs):
        self._guided.clear()
        return Proceed()

    def before_tool_call(self, event, **kwargs):
        name = event.tool_use["name"]

        if name not in GUARDED_TOOLS:
            return Proceed()

        args = event.tool_use.get("input") or {}
        sig = f"{name}:{json.dumps(args, sort_keys=True)}"

        if sig in self._guided:
            self.log.append({
                "pattern": PATTERN_TAG,
                "tool": name,
                "verdict": "deny",
                "reason": "retried a guided call",
            })
            return Deny(
                reason="Do not repeat the unchanged application request. Ask the applicant to clarify the details."
            )

        state = (
            "A LocalGigs conversation followed by a proposed application submission.\n\n"
            f"--- CONVERSATION ---\n{render_messages(event.agent.messages)}\n\n"
            f"--- PROPOSED ACTION ---\ntool: {name}\n"
            f"arguments: {json.dumps(args)}"
        )

        answers = self.decider.ask(state, QUESTIONS)
        grounded, explicit, premature = (
            answers[key].p_yes or 0.0
            for key in ("args_grounded", "explicit_request", "premature")
        )

        record = {
            "pattern": PATTERN_TAG,
            "tool": name,
            "args_grounded": round(grounded, 3),
            "explicit_request": round(explicit, 3),
            "premature": round(premature, 3),
            "decider_ms": round(self.decider.last_latency_ms or 0),
        }

        low, high = self.unsure_band

        if grounded < self.yes:
            record["verdict"] = "guide"
            action = Guide(
                feedback="Do not invent application details. Ask for missing information or look up the gig first."
            )
        elif explicit < self.yes:
            record["verdict"] = "guide"
            action = Guide(
                feedback="The applicant has not explicitly asked to submit yet. Answer their question and ask what they want to do."
            )
        elif low <= premature <= high:
            record["verdict"] = "confirm"
            action = Confirm(
                prompt=f"Confirm submitting this LocalGigs application: {json.dumps(args)}?",
                response="yes",
            )
        elif premature > high:
            record["verdict"] = "guide"
            action = Guide(
                feedback="Clarify the application details with the applicant before submitting."
            )
        else:
            record["verdict"] = "proceed"
            action = Proceed()

        if record["verdict"] == "guide":
            self._guided.add(sig)

        self.log.append(record)
        return action
