"""Story Builder — generate user stories from a project description.

Available to all signed-in roles. PO / PM / COR can save generated stories
straight into the feature_value table; READONLY users see results in the
page and can download CSV / Markdown.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import audit, auth, claude_client, db, spend_cap, stories


def _save_as_features(picked: list[stories.UserStory], user) -> int:
    """Persist selected stories as feature_value rows. Returns count saved."""
    clins = db.fetch_all("SELECT id, code FROM clin ORDER BY code")
    default_clin = clins[0]["id"] if clins else None
    n = 0
    for i, s in enumerate(picked, 1):
        code = f"STORY-{user.id}-{i:03d}"
        fid = db.execute(
            """INSERT INTO feature_value
               (clin_id, feature_code, feature_name, outcome_statement,
                acceptance_stage, payment_status, holdback_pct)
               VALUES (?, ?, ?, ?, 'value_pending', 'held_pending', 0.30)""",
            (default_clin, code, s.title, s.narrative),
        )
        audit.log(
            user,
            entity="feature_value",
            entity_id=fid,
            action="create",
            field="acceptance_stage",
            new_value="value_pending",
            rationale=f"Created from Story Builder. Points={s.story_points}; AC count={len(s.acceptance_criteria)}.",
        )
        n += 1
    return n


def render() -> None:
    user = auth.require_role("READONLY")

    st.markdown(
        '<div class="cps-section">'
        "<h2>Story Builder</h2>"
        '<p class="lead">Describe what you are trying to build. Claude returns three to eight user stories — INVEST-checked, '
        "with Gherkin acceptance criteria, Fibonacci-points estimates, and a build prompt your engineers can feed to a "
        "code-generation tool. Save selected stories straight into your CLIN backlog.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not claude_client.is_enabled():
        st.warning(
            "**Anthropic API key not configured.** Add `ANTHROPIC_API_KEY` to Streamlit Cloud secrets "
            "(or your local `.env`) to enable story generation. Everything else in Compass works without it."
        )
        return

    # Show today's budget burn so the team can see how much of the daily cap
    # has been consumed before they hit "generate" again.
    snap = spend_cap.usage_today()
    pct = min(100.0, 100.0 * snap["spend_usd"] / max(snap["cap_usd"], 0.01))
    st.caption(
        f"Anthropic budget today: ${snap['spend_usd']:.3f} of ${snap['cap_usd']:.2f} cap  "
        f"({snap['calls']} generations · {pct:.0f}% used)"
    )

    with st.form("story_builder_form"):
        c1, c2 = st.columns(2)
        description = c1.text_area(
            "Project / feature description",
            height=140,
            placeholder=(
                "e.g., A reviewer dashboard that lets OEP analysts filter pending FERC pipeline filings "
                "by completeness score, surface red-verdict controls, and request additional information "
                "from the applicant in one click."
            ),
        )
        constraints = c2.text_area(
            "Constraints / must-not-do (optional)",
            height=140,
            placeholder=(
                "e.g., No personally identifiable information. Must integrate with existing eFiling system. "
                "Internal users only — no public access."
            ),
        )

        c3, c4, c5 = st.columns(3)
        role = c3.text_input("Target role (optional)", placeholder="OEP analyst, ISSO, CISO, ...")
        outcome = c4.text_input(
            "Business outcome (optional)", placeholder="Cut sufficiency-letter cycle from 14d to 5d"
        )
        stack = c5.text_input("Stack hint (optional)", placeholder="Streamlit + Azure SQL + Azure AD")

        story_count = st.slider("How many stories to generate?", min_value=3, max_value=8, value=5)
        submitted = st.form_submit_button("Generate user stories", type="primary")

    if submitted:
        if not description.strip():
            st.error("Project description is required.")
            return

        ctx = stories.GenerationContext(
            project_description=description.strip(),
            target_role=role.strip(),
            business_outcome=outcome.strip(),
            constraints=constraints.strip(),
            stack_hint=stack.strip(),
            story_count=story_count,
        )

        ok, reason = spend_cap.can_spend()
        if not ok:
            st.error(reason)
            return

        with st.spinner("Generating user stories..."):
            try:
                generated, cost = stories.generate_stories(ctx)
            except Exception as exc:
                st.error(f"Story generation failed: {exc}")
                return

        spend_cap.record_spend(cost)

        st.session_state["last_stories"] = [s.to_dict() for s in generated]
        st.session_state["last_stories_context"] = ctx
        st.session_state["last_stories_cost"] = cost
        st.success(f"Generated {len(generated)} stories (≈ ${cost:.4f}).")

    # Render whatever's in session — survives reruns from the save-buttons
    if not st.session_state.get("last_stories"):
        return

    raw_stories = st.session_state["last_stories"]
    ctx = st.session_state["last_stories_context"]
    cost = st.session_state.get("last_stories_cost", 0.0)

    st.markdown(
        f"<div class='cps-section'><h2>{len(raw_stories)} stories generated</h2>"
        f"<p class='lead'>Estimated cost: ${cost:.4f}. Pick the ones you want to push into Compass as features.</p></div>",
        unsafe_allow_html=True,
    )

    # Per-story rendering with a checkbox to pick for save
    picked: list[stories.UserStory] = []
    for i, raw in enumerate(raw_stories):
        s = stories.UserStory(
            title=raw["title"],
            as_a=raw["as_a"],
            i_want=raw["i_want"],
            so_that=raw["so_that"],
            acceptance_criteria=tuple(raw["acceptance_criteria"]),
            story_points=raw["story_points"],
            points_rationale=raw["points_rationale"],
            invest_check=raw["invest_check"],
            build_prompt=raw["build_prompt"],
        )
        with st.container():
            cols = st.columns([1, 11])
            picked_yn = cols[0].checkbox(" ", key=f"pick_{i}", label_visibility="collapsed")
            if picked_yn:
                picked.append(s)
            cols[1].markdown(
                f"<div style='font-weight:700; color:#0B2A4A; font-size:1.05rem'>{i + 1}. {s.title}  "
                f"<span style='color:#48515E; font-weight:500; font-size:0.85rem'>({s.story_points} pts)</span></div>"
                f"<div style='color:#1A2333; font-size:0.95rem; margin-top:0.2rem'>{s.narrative}</div>",
                unsafe_allow_html=True,
            )
            with cols[1].expander("Acceptance criteria + INVEST + build prompt"):
                st.markdown("**Acceptance criteria**")
                for c in s.acceptance_criteria:
                    st.markdown(f"- {c}")
                st.markdown(f"\n**Points rationale.** {s.points_rationale}")
                st.markdown(f"\n**INVEST.** {s.invest_check}")
                st.markdown("\n**Build prompt** _(paste into a code-gen tool)_")
                st.code(s.build_prompt, language="text")
        st.markdown(
            "<div style='border-bottom:1px solid #E6EAF0; margin:0.3rem 0'></div>", unsafe_allow_html=True
        )

    # Action bar
    c1, c2, c3 = st.columns(3)
    if auth.can_edit(user) and picked and c1.button(f"Save {len(picked)} as features", type="primary"):
        saved = _save_as_features(picked, user)
        st.success(f"Saved {saved} stories into Compass features.")

    md = stories.stories_to_markdown(
        [stories.UserStory(**{k: v for k, v in r.items() if k != "narrative"}) for r in raw_stories],
        ctx,
    )
    c2.download_button(
        "Download as Markdown",
        data=md.encode("utf-8"),
        file_name="user-stories.md",
        mime="text/markdown",
    )
    csv_df = pd.DataFrame(
        stories.stories_to_csv_rows(
            [stories.UserStory(**{k: v for k, v in r.items() if k != "narrative"}) for r in raw_stories]
        )
    )
    c3.download_button(
        "Download as CSV",
        data=csv_df.to_csv(index=False).encode("utf-8"),
        file_name="user-stories.csv",
        mime="text/csv",
    )
