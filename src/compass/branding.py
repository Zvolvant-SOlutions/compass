"""Zvolvant brand styling for Compass — navy/gold, DM Serif Display + Inter."""

from __future__ import annotations

NAVY = "#0B2A4A"
NAVY_DEEP = "#08213A"
GOLD = "#C9A227"
GOLD_DEEP = "#9F8120"
INK = "#1A2333"
INK_SOFT = "#48515E"
PAPER = "#F7F9FC"
SURFACE = "#FFFFFF"
GREEN = "#1F8A4C"
AMBER = "#D6932A"
RED = "#B0322B"
HAIRLINE = "#E6EAF0"

RAG_COLORS = {"green": GREEN, "amber": AMBER, "red": RED}

GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=DM+Serif+Display&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0..1,-50..200');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined');

html, body, [data-testid="stAppViewContainer"] * {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

/* Streamlit's expanders / tabs / buttons emit Material Symbol ligatures
   (like "arrow_right", "expand_more"). If the icon font is slow or fails
   to load, browsers render the ligature names as raw text — landing on
   top of the label. Pin the icon-font family explicitly to every span
   Streamlit uses for icons so the glyph renders instead of the text. */
[data-testid="stExpanderToggleIcon"],
[data-testid="stIconMaterial"],
[class*="MaterialIcon"],
[class*="material-symbols"],
.material-symbols-rounded,
.material-symbols-outlined,
span.st-emotion-cache-1u4jdkc,
span[data-testid="stMarkdownContainer"] svg + span {{
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important;
    font-weight: normal;
    font-style: normal;
    line-height: 1;
    text-transform: none;
    letter-spacing: normal;
    word-wrap: normal;
    -webkit-font-smoothing: antialiased;
    font-feature-settings: 'liga';
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}}

footer {{ display:none !important; }}
#MainMenu {{ visibility:hidden !important; }}
[data-testid="stToolbar"] {{ display:none !important; }}
[data-testid="stStatusWidget"] {{ display:none !important; }}
[class*="viewerBadge"] {{ display:none !important; }}

.cps-header {{
    background: linear-gradient(135deg, {NAVY} 0%, {NAVY_DEEP} 100%);
    color: white; padding: 1rem 1.4rem; border-radius: 10px;
    margin-bottom: 1.2rem; display:flex; align-items:center; justify-content:space-between;
}}
.cps-header .brand {{
    font-family: 'DM Serif Display', serif; font-size: 1.4rem;
}}
.cps-header .brand-sub {{ color:{GOLD}; font-size:0.78rem; letter-spacing:0.16em; text-transform:uppercase; }}
.cps-header .who {{ color:#C9D4E5; font-size:0.84rem; }}

.cps-section {{ margin-top:1.4rem; }}
.cps-section h2 {{
    font-family: 'DM Serif Display', serif; color:{NAVY};
    font-size:1.45rem; margin: 0 0 0.5rem;
}}
.cps-section .lead {{ color:{INK_SOFT}; font-size:0.96rem; max-width:760px; margin:0 0 1rem; }}

.tile {{
    background:{SURFACE}; border:1px solid {HAIRLINE}; border-radius:10px;
    padding:0.9rem 1.05rem; min-height:88px;
}}
.tile .label {{ text-transform:uppercase; letter-spacing:0.08em; font-size:0.72rem; color:{INK_SOFT}; font-weight:600; }}
.tile .value {{ font-family:'DM Serif Display', serif; font-size:2rem; color:{NAVY}; line-height:1.1; margin-top:0.15rem; }}
.tile .sub {{ font-size:0.78rem; color:{INK_SOFT}; margin-top:0.1rem; }}

.clin-card {{
    background:{SURFACE}; border:1px solid {HAIRLINE}; border-left:5px solid {NAVY};
    border-radius:10px; padding:1rem 1.2rem; margin-bottom:0.8rem;
}}
.clin-card.rag-green {{ border-left-color:{GREEN}; }}
.clin-card.rag-amber {{ border-left-color:{AMBER}; }}
.clin-card.rag-red {{ border-left-color:{RED}; }}
.clin-card h3 {{ color:{NAVY}; font-size:1.1rem; margin:0; }}
.clin-card .scope {{ color:{INK_SOFT}; font-size:0.86rem; margin-top:0.2rem; }}

.rag-pill {{
    display:inline-block; padding:0.15rem 0.55rem; border-radius:999px;
    font-weight:600; font-size:0.74rem; letter-spacing:0.04em; text-transform:uppercase;
}}
.rag-pill.green {{ background:rgba(31,138,76,0.13); color:{GREEN}; }}
.rag-pill.amber {{ background:rgba(214,147,42,0.15); color:{AMBER}; }}
.rag-pill.red   {{ background:rgba(176,50,43,0.13); color:{RED}; }}

div.stButton > button {{
    background:{NAVY}; color:white; border:none; border-radius:8px;
    padding:0.45rem 1rem; font-weight:600;
}}
div.stButton > button:hover {{ background:{NAVY_DEEP}; }}
div.stButton > button[kind="primary"] {{ background:{GOLD}; color:{NAVY_DEEP}; }}
div.stButton > button[kind="primary"]:hover {{ background:{GOLD_DEEP}; }}

.cps-footer {{
    margin-top:2.4rem; padding:1.1rem 1.3rem; background:{NAVY_DEEP};
    color:#C9D4E5; border-radius:10px; font-size:0.82rem;
}}
.cps-footer .brand {{ color:white; font-weight:600; font-size:0.95rem; }}
.cps-footer a {{ color:{GOLD}; text-decoration:none; }}
</style>
"""


def rag_pill(rag: str) -> str:
    cls = (rag or "").lower()
    label = (cls or "—").upper()
    return f'<span class="rag-pill {cls}">{label}</span>'


def header_html(user_name: str | None = None, role: str | None = None) -> str:
    who = (
        f'<div class="who">{user_name} · {role}</div>'
        if user_name and role
        else '<div class="who">Not signed in</div>'
    )
    return (
        '<div class="cps-header">'
        '<div><div class="brand-sub">Zvolvant Solutions</div>'
        '<div class="brand">Compass</div></div>'
        f"{who}"
        "</div>"
    )


def footer_html() -> str:
    return (
        '<div class="cps-footer">'
        '<div class="brand">Compass by Zvolvant Solutions LLC</div>'
        '<div style="margin-top:0.35rem">'
        "Executive oversight for agile federal delivery  ·  "
        '<a href="mailto:software@zvolvant.com">software@zvolvant.com</a>  ·  '
        '<a href="https://zvolvant.com/">zvolvant.com</a>'
        "</div>"
        '<div style="margin-top:0.45rem; font-size:0.74rem; color:#7989A1">'
        "SBA-Certified 8(a) Small Business  ·  ISO 9001  ·  ISO 27001"
        "</div>"
        "</div>"
    )


def tile_html(label: str, value: str, sub: str | None = None) -> str:
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="tile"><div class="label">{label}</div><div class="value">{value}</div>{sub_html}</div>'
    )
