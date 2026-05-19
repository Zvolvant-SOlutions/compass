"""User-story generator.

Takes a freeform project / feature description and asks Claude to produce
structured user stories with INVEST checks, Gherkin acceptance criteria, a
Fibonacci-points estimate, and a build prompt the team can feed to a
downstream code-generation tool.

The engine is a single pure-ish function: ``generate_stories(context) -> list[UserStory]``.
It only depends on the Anthropic SDK; the UI in ``pages/story_builder.py``
calls it and renders the result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .claude_client import (
    DEFAULT_MODEL,
    call_with_retry,
    estimate_call_cost_usd,
    extract_text,
    get_client,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a senior product owner working with a federal agile delivery team. "
    "You write user stories in the canonical INVEST format with Gherkin "
    "acceptance criteria. Your stories are scoped to be implementable in a "
    "single two-week sprint by a team of three to five engineers.\n\n"
    "Voice and style:\n"
    "- Write 'As a <specific role>, I want <specific capability>, so that <observable outcome>.' "
    "Never use 'As a user'; pick the actual role (analyst, reviewer, CISO, etc.).\n"
    "- Acceptance criteria use Given / When / Then. Three to six criteria per story. "
    "Each criterion is testable; vague terms like 'fast' or 'easy' are not acceptable.\n"
    "- Story points use the Fibonacci scale (1, 2, 3, 5, 8, 13). Explain the estimate "
    "in one sentence referencing the actual work (e.g., 'one new DB column, one form "
    "field, one validation rule = 2 points').\n"
    "- The INVEST check is the single weakest dimension with a one-line note on why. "
    "If the story is genuinely strong on all six, write 'All dimensions clean.'\n"
    "- The build_prompt is the engineering prompt a developer could paste into a "
    "code-generation tool to scaffold the implementation. Be specific: name the "
    "data model changes, the API endpoints, the UI components, and the test cases. "
    "Two to four paragraphs.\n\n"
    "Do not invent technology choices the user has not specified. If the prompt "
    "implies a stack (e.g. 'Streamlit + SQLite'), honor it; otherwise stay stack-neutral."
)


STORIES_TOOL = {
    "name": "record_user_stories",
    "description": (
        "Record a list of three to eight user stories generated from the project context. "
        "Must be called exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "stories": {
                "type": "array",
                "minItems": 3,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Short title, under 8 words.",
                        },
                        "as_a": {
                            "type": "string",
                            "description": "Specific role — never 'user'.",
                        },
                        "i_want": {
                            "type": "string",
                            "description": "Specific capability the role wants.",
                        },
                        "so_that": {
                            "type": "string",
                            "description": "Observable outcome / benefit.",
                        },
                        "acceptance_criteria": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 6,
                            "items": {"type": "string"},
                            "description": "Gherkin-style Given/When/Then; each criterion testable.",
                        },
                        "story_points": {
                            "type": "integer",
                            "enum": [1, 2, 3, 5, 8, 13],
                            "description": "Fibonacci estimate.",
                        },
                        "points_rationale": {
                            "type": "string",
                            "description": "One sentence on why the estimate.",
                        },
                        "invest_check": {
                            "type": "string",
                            "description": "Weakest INVEST dimension + one-line note, or 'All dimensions clean.'",
                        },
                        "build_prompt": {
                            "type": "string",
                            "description": (
                                "Engineering prompt that scaffolds the implementation. Two to four paragraphs."
                            ),
                        },
                    },
                    "required": [
                        "title",
                        "as_a",
                        "i_want",
                        "so_that",
                        "acceptance_criteria",
                        "story_points",
                        "points_rationale",
                        "invest_check",
                        "build_prompt",
                    ],
                },
            },
        },
        "required": ["stories"],
    },
}


@dataclass(frozen=True)
class UserStory:
    title: str
    as_a: str
    i_want: str
    so_that: str
    acceptance_criteria: tuple[str, ...]
    story_points: int
    points_rationale: str
    invest_check: str
    build_prompt: str

    @property
    def narrative(self) -> str:
        return f"As a {self.as_a}, I want {self.i_want}, so that {self.so_that}."

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "as_a": self.as_a,
            "i_want": self.i_want,
            "so_that": self.so_that,
            "narrative": self.narrative,
            "acceptance_criteria": list(self.acceptance_criteria),
            "story_points": self.story_points,
            "points_rationale": self.points_rationale,
            "invest_check": self.invest_check,
            "build_prompt": self.build_prompt,
        }


@dataclass(frozen=True)
class GenerationContext:
    project_description: str
    target_role: str = ""  # e.g. "OEP analyst", "ISSO" — blank if unknown
    business_outcome: str = ""  # what success looks like
    constraints: str = ""  # must-not-do, integrations, compliance reqs
    stack_hint: str = ""  # e.g. "Streamlit + SQLite + Azure AD"
    story_count: int = 5  # target number of stories


def _build_user_message(ctx: GenerationContext) -> str:
    lines = [
        "Project / feature description:",
        ctx.project_description.strip(),
        "",
    ]
    if ctx.target_role.strip():
        lines += [f"Primary target role: {ctx.target_role.strip()}", ""]
    if ctx.business_outcome.strip():
        lines += [f"Desired business outcome: {ctx.business_outcome.strip()}", ""]
    if ctx.constraints.strip():
        lines += [f"Constraints / must-not-do: {ctx.constraints.strip()}", ""]
    if ctx.stack_hint.strip():
        lines += [f"Stack hint (honor if specified): {ctx.stack_hint.strip()}", ""]
    lines += [
        f"Generate {ctx.story_count} user stories.",
        "Call record_user_stories exactly once with the full list.",
    ]
    return "\n".join(lines)


def _extract_tool_input(response: Any) -> dict[str, Any]:
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and isinstance(getattr(block, "input", None), dict):
            return dict(block.input)
    raise ValueError(f"No tool_use block: {extract_text(response)[:200]!r}")


def generate_stories(ctx: GenerationContext) -> tuple[list[UserStory], float]:
    """Generate user stories via Claude. Returns (stories, estimated_usd_cost).

    Raises RuntimeError if no API key is configured — callers should check
    ``claude_client.is_enabled()`` first to display a helpful banner.
    """
    client = get_client()
    if client is None:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured. Set it in Streamlit Cloud secrets.")

    resp = call_with_retry(
        client,
        model=DEFAULT_MODEL,
        max_tokens=4000,
        temperature=0.4,
        system=[
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        tools=[STORIES_TOOL],
        tool_choice={"type": "tool", "name": STORIES_TOOL["name"]},
        messages=[{"role": "user", "content": _build_user_message(ctx)}],
    )
    data = _extract_tool_input(resp)
    cost = estimate_call_cost_usd(resp)

    stories = []
    for raw in data.get("stories", []) or []:
        try:
            stories.append(
                UserStory(
                    title=str(raw["title"]).strip(),
                    as_a=str(raw["as_a"]).strip(),
                    i_want=str(raw["i_want"]).strip(),
                    so_that=str(raw["so_that"]).strip(),
                    acceptance_criteria=tuple(str(c).strip() for c in raw.get("acceptance_criteria", [])),
                    story_points=int(raw.get("story_points", 3)),
                    points_rationale=str(raw.get("points_rationale", "")).strip(),
                    invest_check=str(raw.get("invest_check", "")).strip(),
                    build_prompt=str(raw.get("build_prompt", "")).strip(),
                )
            )
        except Exception as exc:
            logger.warning("Skipping malformed story: %s", exc)
    return stories, cost


def stories_to_markdown(stories: list[UserStory], context: GenerationContext) -> str:
    """Render a list of stories to Markdown for easy hand-off to a backlog."""
    lines = [
        f"# User stories — {context.project_description[:80]}",
        "",
        f"_Generated {len(stories)} stories. Target role: {context.target_role or 'unspecified'}._",
        "",
    ]
    for i, s in enumerate(stories, 1):
        lines += [
            f"## {i}. {s.title}  ({s.story_points} pts)",
            "",
            f"**{s.narrative}**",
            "",
            "### Acceptance criteria",
            *[f"- {c}" for c in s.acceptance_criteria],
            "",
            f"**Points rationale:** {s.points_rationale}",
            "",
            f"**INVEST:** {s.invest_check}",
            "",
            "### Build prompt",
            s.build_prompt,
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


def stories_to_csv_rows(stories: list[UserStory]) -> list[dict[str, Any]]:
    """Flat CSV-ready rows."""
    return [
        {
            "Title": s.title,
            "Narrative": s.narrative,
            "Acceptance criteria": " | ".join(s.acceptance_criteria),
            "Story points": s.story_points,
            "Points rationale": s.points_rationale,
            "INVEST check": s.invest_check,
            "Build prompt": s.build_prompt,
        }
        for s in stories
    ]
