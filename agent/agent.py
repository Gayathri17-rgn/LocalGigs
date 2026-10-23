"""LocalGigs agent using Strands and the Decider 2B application guard."""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking

from .decision import ApplicationGuard
from .tools import TOOLS

NAME = "LocalGigs application assistant"

SYSTEM_PROMPT = """You are the LocalGigs assistant for short-term, offline local event work.

Help users browse sample gigs, understand their requirements, and check their applications.
Use the available tools to retrieve gig details and application status. Never invent gigs,
pay rates, requirements, or application results. The current gigs are sample data, not verified
live listings. Do not claim that an organizer is genuinely verified solely because sample data
says so.

Before submitting an application, collect the gig ID, applicant name, age, availability,
and explicit consent. The tool enforces the sample gig's minimum age requirement.
Never claim an application was submitted unless the tool confirms success.
Be concise, friendly, and transparent. Do not submit an application merely because the user
asks how applications work."""


EAGER_PROMPT = SYSTEM_PROMPT


class HackathonAgent:
    """One Strands agent per session, with the LocalGigs guardrail attached."""

    def __init__(
        self,
        decider: Decider | None = None,
        model_id: str | None = None,
        eager: bool | None = None,
    ):
        import os

        self.decider = decider or Decider()
        self.eager = eager if eager is not None else os.environ.get("DEMO_EAGER") == "1"
        self.model_id = model_id or default_model_id()
        self.sessions: dict[str, tuple[Agent, ApplicationGuard]] = {}

    def _session(self, session_id: str) -> tuple[Agent, ApplicationGuard]:
        if session_id not in self.sessions:
            guard = ApplicationGuard(self.decider)
            agent = Agent(
                model=agent_model(self.model_id),
                system_prompt=EAGER_PROMPT if self.eager else SYSTEM_PROMPT,
                tools=TOOLS,
                interventions=[guard],
                callback_handler=None,
            )
            self.sessions[session_id] = (agent, guard)
        return self.sessions[session_id]

    def chat(
        self,
        message: str,
        session_id: str = "default",
        images: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Run a chat turn and return the reply and any Decider decisions."""
        agent, guard = self._session(session_id)
        before = len(guard.log)
        t0 = time.perf_counter()

        result = agent(
            [*image_blocks(images), {"text": message}] if images else message,
            invocation_state={"images": list(images or [])},
        )
        reply = strip_thinking(str(result))

        return {
            "reply": reply,
            "decisions": guard.log[before:],
            "model_id": self.model_id,
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "agent": NAME,
            "eager": self.eager,
        }


if __name__ == "__main__":
    import json
    import sys

    assistant = HackathonAgent()
    messages = sys.argv[1:] or [
        "Show me the available local gigs.",
        "Can you explain the application process?",
    ]
    for message in messages:
        print(json.dumps(assistant.chat(message), indent=2))
