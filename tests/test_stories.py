"""Story engine tests — exercise pure helpers without hitting the API."""

from __future__ import annotations

from compass.stories import (
    GenerationContext,
    UserStory,
    stories_to_csv_rows,
    stories_to_markdown,
)


def _sample_story(title: str = "Filter pending filings", points: int = 3) -> UserStory:
    return UserStory(
        title=title,
        as_a="OEP analyst",
        i_want="filter pending Section 7(c) filings by completeness score",
        so_that="I can triage the deficient ones first",
        acceptance_criteria=(
            "Given pending filings exist, when I open the dashboard, then a score slider is visible.",
            "Given I set the slider to <70, when I apply, then only filings below 70 appear.",
            "Given no filings match, when the filter applies, then an empty-state message renders.",
        ),
        story_points=points,
        points_rationale="One new UI control + one SQL filter clause + one empty-state copy = 3 points.",
        invest_check="All dimensions clean.",
        build_prompt="Add a Streamlit slider to the filings list page bound to a SQL WHERE clause...",
    )


def test_narrative_format():
    s = _sample_story()
    assert s.narrative == (
        "As a OEP analyst, I want filter pending Section 7(c) filings by completeness score, "
        "so that I can triage the deficient ones first."
    )


def test_to_dict_includes_narrative():
    s = _sample_story()
    d = s.to_dict()
    assert d["narrative"].startswith("As a OEP analyst")
    assert d["story_points"] == 3
    assert isinstance(d["acceptance_criteria"], list)
    assert len(d["acceptance_criteria"]) == 3


def test_markdown_rendering_has_per_story_sections():
    ctx = GenerationContext(project_description="Reviewer dashboard for OEP", target_role="OEP analyst")
    md = stories_to_markdown([_sample_story("First"), _sample_story("Second", points=5)], ctx)
    assert "# User stories" in md
    assert "## 1. First" in md
    assert "## 2. Second" in md
    assert "Acceptance criteria" in md
    assert "Build prompt" in md


def test_csv_rows_have_flat_strings():
    rows = stories_to_csv_rows([_sample_story("A"), _sample_story("B")])
    assert len(rows) == 2
    assert rows[0]["Title"] == "A"
    assert "|" in rows[0]["Acceptance criteria"]  # criteria joined with " | "
    assert rows[0]["Story points"] == 3


def test_generation_context_defaults():
    ctx = GenerationContext(project_description="A dashboard")
    assert ctx.story_count == 5
    assert ctx.target_role == ""
    assert ctx.stack_hint == ""
