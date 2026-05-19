"""Seed the local SQLite DB with CLINs, workstreams, sprints, features, settings, and a few users.

Run via ``make seed``. Idempotent: drops + recreates the DB file each run.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from compass import db  # noqa: E402
from compass.auth import hash_password  # noqa: E402


def reset_db() -> None:
    p = db.db_path()
    if p.exists():
        p.unlink()
    db.init_db()


def seed_settings() -> None:
    rows = [
        ("predictability", 0.85, 0.75, "high_is_good", "pct", "Sprint commit accuracy", "sprint"),
        ("story_completion", 0.90, 0.80, "high_is_good", "pct", "Stories accepted vs committed", "sprint"),
        (
            "defect_leakage",
            0.05,
            0.08,
            "low_is_good",
            "pct",
            "Post-release defects per accepted story",
            "sprint",
        ),
        ("uat_first_pass", 0.95, 0.90, "high_is_good", "pct", "UAT first-pass rate", "sprint"),
        ("cycle_time", 7.0, 10.0, "low_is_good", "days", "Average story cycle time", "sprint"),
        ("availability", 0.995, 0.99, "high_is_good", "pct", "System uptime per CLIN", "clin"),
        ("burn_variance", 0.10, 0.15, "low_is_good", "pct", "|Actual - Planned| / Planned", "clin"),
    ]
    for r in rows:
        db.execute(
            """INSERT INTO settings (kpi_name, green_threshold, yellow_threshold, direction, unit, pws_target_text, applies_to)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            r,
        )


def seed_users() -> None:
    users = [
        ("cor@example.gov", "COR Reviewer", "COR", "compass-demo"),
        ("pm@example.gov", "Program Manager", "PM", "compass-demo"),
        ("po@example.gov", "Product Owner", "PO", "compass-demo"),
        ("auditor@example.gov", "Auditor", "READONLY", "compass-demo"),
    ]
    for email, name, role, pw in users:
        db.execute(
            "INSERT INTO users (email, name, role, password_hash) VALUES (?, ?, ?, ?)",
            (email, name, role, hash_password(pw)),
        )


CLINS = [
    ("CLIN 001", "Operations & Management", "Day-to-day program ops and reporting"),
    ("CLIN 002", "Shared Development", "Cross-cutting platform engineering"),
    ("CLIN 003", "Program Support", "Surge capacity for stakeholder requests"),
    ("CLIN 004", "Capital Investment", "Net-new modernization investments"),
]

WORKSTREAMS = [
    ("Platform Modernization", "Cloud and shared services", "Active", "PM"),
    ("Data & Analytics", "Reporting and decision support", "Active", "PM"),
    ("Identity & Access", "SSO, RBAC, audit", "Active", "PM"),
    ("Operations Support", "Monitoring, incident response", "Active", "PM"),
]

PROJECT_SYSTEMS = [
    ("Filing Intake System", 1),
    ("Analyst Workbench", 2),
    ("Identity Service", 3),
    ("Operations Console", 4),
]

FEATURES = [
    ("Feature-001", "Dashboard filtering", 1, 1, 1, "Reviewers can filter filings by docket attributes."),
    ("Feature-002", "Notification flow", 2, 2, 2, "Subscribers receive alerts on docket status change."),
    ("Feature-003", "Incident quick update", 3, 4, 4, "On-call updates incident status from mobile."),
    ("Feature-004", "Intake tracking", 4, 1, 1, "Inbound filings tracked from receipt to assignment."),
]


def seed_clins_workstreams_systems() -> dict[str, int]:
    ids: dict[str, int] = {}
    for code, name, scope in CLINS:
        ids[code] = db.execute(
            "INSERT INTO clin (code, name, scope, status_rag, acceptance_decision, invoice_position) VALUES (?, ?, ?, ?, ?, ?)",
            (code, name, scope, "amber", "pending", "hold"),
        )
    for name, desc, status, role in WORKSTREAMS:
        db.execute(
            "INSERT INTO workstream (name, description, status, owner_role) VALUES (?, ?, ?, ?)",
            (name, desc, status, role),
        )
    for name, ws_id in PROJECT_SYSTEMS:
        db.execute(
            "INSERT INTO project_system (name, workstream_id, notes) VALUES (?, ?, ?)",
            (name, ws_id, ""),
        )
    return ids


def seed_sprints(clin_ids: dict[str, int]) -> None:
    sprints = [
        # (sprint_num, start, end, clin_code, ws_id, ps_id, committed, completed, accepted, defects, uat_tests, uat_pass, cycle, planned, actual, avail)
        (12, "2026-04-07", "2026-04-20", "CLIN 001", 1, 1, 42, 40, 18, 1, 22, 22, 6.2, 85000, 84200, 0.998),
        (13, "2026-04-21", "2026-05-04", "CLIN 001", 1, 1, 44, 38, 17, 3, 24, 22, 7.8, 85000, 92500, 0.996),
        (12, "2026-04-07", "2026-04-20", "CLIN 002", 2, 2, 38, 35, 14, 2, 19, 18, 8.1, 70000, 71200, 0.994),
        (13, "2026-04-21", "2026-05-04", "CLIN 002", 2, 2, 40, 36, 16, 2, 20, 19, 7.5, 70000, 73800, 0.997),
        (12, "2026-04-07", "2026-04-20", "CLIN 003", 4, 4, 30, 22, 9, 4, 12, 10, 11.2, 45000, 46800, 0.989),
        (13, "2026-04-21", "2026-05-04", "CLIN 003", 4, 4, 32, 24, 10, 3, 13, 12, 9.8, 45000, 50100, 0.992),
        (12, "2026-04-07", "2026-04-20", "CLIN 004", 1, 1, 50, 47, 22, 1, 28, 27, 6.5, 120000, 116000, 0.997),
        (13, "2026-04-21", "2026-05-04", "CLIN 004", 1, 1, 52, 45, 21, 2, 30, 28, 7.2, 120000, 124500, 0.998),
    ]
    for s in sprints:
        sn, start, end, clin_code, ws_id, ps_id, comm, comp, acc, def_, uat, uatp, cycle, pl, act, av = s
        db.execute(
            """INSERT INTO sprint (sprint_number, start_date, end_date, clin_id, workstream_id, project_system_id,
                                   committed_points, completed_points, accepted_stories, post_release_defects,
                                   uat_tests, uat_first_pass_count, avg_cycle_time_days,
                                   planned_burn_usd, actual_burn_usd, availability_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sn,
                start,
                end,
                clin_ids[clin_code],
                ws_id,
                ps_id,
                comm,
                comp,
                acc,
                def_,
                uat,
                uatp,
                cycle,
                pl,
                act,
                av,
            ),
        )


def seed_customer_value(clin_ids: dict[str, int]) -> None:
    rows = [
        # (clin_code, biz, satisfaction, adoption, rework, utilization)
        ("CLIN 001", 0.82, 0.78, 0.74, 0.06, 0.81),
        ("CLIN 002", 0.74, 0.71, 0.62, 0.12, 0.65),
        ("CLIN 003", 0.58, 0.55, 0.41, 0.22, 0.46),
        ("CLIN 004", 0.86, 0.83, 0.79, 0.04, 0.84),
    ]
    for code, bv, sat, ad, rw, ut in rows:
        db.execute(
            """INSERT INTO customer_value_input (clin_id, business_value_rate, user_satisfaction,
                                                  adoption_rate, rework_rate, feature_utilization)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (clin_ids[code], bv, sat, ad, rw, ut),
        )


def seed_features(clin_ids: dict[str, int]) -> None:
    rows = [
        # feature: (code, name, clin_code, ws_id, ps_id, outcome, satisfaction, adoption, utilization, rework,
        #          tech_status, value_confirmed, stage, payment, holdback, backlog, rework_yn)
        (
            "Feature-001",
            "Dashboard filtering",
            "CLIN 001",
            1,
            1,
            "Reviewers cut triage time in half by filtering filings by docket attributes.",
            0.82,
            0.74,
            0.81,
            0.06,
            "accepted",
            1,
            "fully_accepted",
            "released",
            0.30,
            "continue",
            0,
        ),
        (
            "Feature-002",
            "Notification flow",
            "CLIN 002",
            2,
            2,
            "Subscribers receive immediate alerts on docket status change.",
            0.71,
            0.62,
            0.65,
            0.12,
            "accepted",
            0,
            "technically_accepted",
            "held_pending",
            0.30,
            "continue",
            0,
        ),
        (
            "Feature-003",
            "Incident quick update",
            "CLIN 003",
            4,
            4,
            "On-call updates incident status from mobile in under 30 seconds.",
            0.55,
            0.41,
            0.46,
            0.22,
            "accepted",
            0,
            "rework_required",
            "held_pending",
            0.30,
            "reprioritize",
            1,
        ),
        (
            "Feature-004",
            "Intake tracking",
            "CLIN 004",
            1,
            1,
            "Inbound filings tracked from receipt to analyst assignment.",
            0.83,
            0.79,
            0.84,
            0.04,
            "accepted",
            1,
            "fully_accepted",
            "released",
            0.30,
            "continue",
            0,
        ),
    ]
    for r in rows:
        (
            code,
            name,
            clin_code,
            ws_id,
            ps_id,
            outcome,
            sat,
            ad,
            ut,
            rw,
            tech,
            vc,
            stage,
            pay,
            hb,
            bl,
            rwyn,
        ) = r
        db.execute(
            """INSERT INTO feature_value
               (clin_id, workstream_id, project_system_id, feature_code, feature_name, outcome_statement,
                customer_satisfaction, adoption_rate, feature_utilization, rework_rate, tangible_evidence,
                technical_acceptance_status, technical_acceptance_date, value_validation_start, value_validation_end,
                value_confirmed_yn, acceptance_stage, payment_status, rework_required_yn, backlog_impact, holdback_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                clin_ids[clin_code],
                ws_id,
                ps_id,
                code,
                name,
                outcome,
                sat,
                ad,
                ut,
                rw,
                "https://sharepoint.example/evidence/" + code.lower(),
                tech,
                "2026-04-30",
                "2026-05-01",
                "2026-05-31",
                vc,
                stage,
                pay,
                rwyn,
                bl,
                hb,
            ),
        )


def seed_risks(clin_ids: dict[str, int]) -> None:
    rows = [
        (
            "high",
            "Cycle time on CLIN 003 trending above 10-day threshold; surge support load.",
            clin_ids["CLIN 003"],
            4,
            "open",
            "PM exploring temporary capacity reallocation; COR review at next standup.",
            "PM",
            "2026-06-01",
        ),
        (
            "medium",
            "Rework rate spike on Feature-003 suggests acceptance criteria ambiguity.",
            clin_ids["CLIN 003"],
            4,
            "open",
            "PO rewriting acceptance criteria; re-baseline Stage 1 review next sprint.",
            "PO",
            "2026-05-30",
        ),
        (
            "low",
            "Burn variance on CLIN 002 ticked above 5% — watch for trend.",
            clin_ids["CLIN 002"],
            2,
            "monitor",
            "Monitor next two sprints.",
            "PM",
            "2026-06-15",
        ),
    ]
    for r in rows:
        db.execute(
            """INSERT INTO risk_issue (priority, risk_issue_text, impacted_clin_id, impacted_workstream_id,
                                        status, mitigation, owner_role, due_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            r,
        )


def main() -> int:
    os.environ.setdefault("COMPASS_HASH_SALT", "compass-seed")
    reset_db()
    seed_settings()
    seed_users()
    clin_ids = seed_clins_workstreams_systems()
    seed_sprints(clin_ids)
    seed_customer_value(clin_ids)
    seed_features(clin_ids)
    seed_risks(clin_ids)
    print(f"Seeded {db.db_path()}")
    print("Demo users (password: compass-demo):")
    print("  cor@example.gov       (COR — full access)")
    print("  pm@example.gov        (PM — data entry + mitigations)")
    print("  po@example.gov        (PO — data entry + mitigations)")
    print("  auditor@example.gov   (READONLY — dashboards only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
