"""
Theme engine: Dark / Light modes, switchable chart palettes, display heading font (DM Serif Display) against Inter body text.
All component CSS is driven by CSS variables, so a single stylesheet serves both modes.
"""
from __future__ import annotations

import html

HEADING_FONT = "'DM Serif Display', Georgia, 'Times New Roman', serif"
BODY_FONT = "'Inter', 'Segoe UI', Arial, sans-serif"

# ---- surface tokens -----------------------------------------------------------------------
SURFACES = {
    "dark": dict(BG="#0A1426", BG2="#12284D", CARD="#11213B", CARD2="#16294A", BORDER="#243B63", TEXT="#E8EDF6", MUTED="#9FB0C8",
                 STRONG="#FFFFFF", ACCENT="#D6B25E", GRID="#22385C", ZERO="#3A5486", REF="#8FA3C4", CONNECTOR="#5E7399",
                 SHADOW="rgba(0,0,0,.35)", GAUGE_BG="#0A1426",
                 GAUGE_STEPS=["#5A2420", "#5E4A18", "#3E4A2A", "#1E5A45"],
                 STATUS={0: "#1E5A45", 1: "#7D5E1B", 2: "#8E2F27"}, STATUS_TEXT="#FFFFFF",
                 PILL=dict(risk=("#8E2F27", "#FFD9D4"), watch=("#7D5E1B", "#FFF0C7"), ok=("#1E5A45", "#D4F5E6")),
                 UP="#3FBF86", DOWN="#F0685A"),
    "light": dict(BG="#F3F5F9", BG2="#E9EEF7", CARD="#FFFFFF", CARD2="#F6F8FC", BORDER="#DCE3EE", TEXT="#1B2638", MUTED="#5A6B84",
                  STRONG="#0B1F3F", ACCENT="#B8902F", GRID="#E6EBF3", ZERO="#C5CEDD", REF="#8394AF", CONNECTOR="#A9B6CC",
                  SHADOW="rgba(11,31,63,.08)", GAUGE_BG="#F6F8FC",
                  GAUGE_STEPS=["#F6D3CE", "#FBE7B5", "#EDEBC9", "#CFE8DA"],
                  STATUS={0: "#CFE8DA", 1: "#FBE7B5", 2: "#F4B8B0"}, STATUS_TEXT="#162033",
                  PILL=dict(risk=("#F8D3CE", "#7A1209"), watch=("#FBE7B5", "#7A5410"), ok=("#CFE8DA", "#0F5236")),
                  UP="#1E7B4F", DOWN="#B42318"),
}

# ---- chart palettes per mode ----------------------------------------------------------------
PALETTES_DARK = {
    "Navy & Gold": dict(NAVY="#4F86D6", BLUE="#7FA8E6", SKY="#B3CBEE", GOLD="#D6B25E", GREEN="#3FBF86", RED="#F0685A", AMBER="#E3AA45", S5="#8A9BB8", S6="#A88B3A"),
    "Ocean": dict(NAVY="#2BA3C4", BLUE="#5CC2DE", SKY="#A6E0EE", GOLD="#F2C14E", GREEN="#45C486", RED="#EF6A5B", AMBER="#E3AA45", S5="#7AA7B5", S6="#B58E2E"),
    "Emerald": dict(NAVY="#2FB67C", BLUE="#6FD3A3", SKY="#B5EBD0", GOLD="#E0C46A", GREEN="#58D68D", RED="#F0685A", AMBER="#E3AA45", S5="#7FA896", S6="#A88B3A"),
    "Sunset": dict(NAVY="#E4793F", BLUE="#F0A06B", SKY="#F7CBA6", GOLD="#E8C45E", GREEN="#4CC38A", RED="#F0685A", AMBER="#E3AA45", S5="#B59A8A", S6="#C2873A"),
    "Monochrome": dict(NAVY="#C5CEDD", BLUE="#9AA8BF", SKY="#E3E8F1", GOLD="#D6B25E", GREEN="#3FBF86", RED="#F0685A", AMBER="#E3AA45", S5="#7B8AA4", S6="#A88B3A"),
}
PALETTES_LIGHT = {
    "Navy & Gold": dict(NAVY="#12306B", BLUE="#3C6DB0", SKY="#8FB0DD", GOLD="#B8902F", GREEN="#1E8A5A", RED="#C0392B", AMBER="#B7791F", S5="#6B7C99", S6="#8C6D1F"),
    "Ocean": dict(NAVY="#0E6F87", BLUE="#2FA3BF", SKY="#8CCDDD", GOLD="#C9961A", GREEN="#1E8A5A", RED="#C0392B", AMBER="#B7791F", S5="#5F8A97", S6="#8C6D1F"),
    "Emerald": dict(NAVY="#17724B", BLUE="#3FA878", SKY="#9FD9BD", GOLD="#B8942A", GREEN="#1E8A5A", RED="#C0392B", AMBER="#B7791F", S5="#5E8C78", S6="#8C6D1F"),
    "Sunset": dict(NAVY="#B8501A", BLUE="#DB814A", SKY="#EFB992", GOLD="#B8902F", GREEN="#1E8A5A", RED="#B42318", AMBER="#B7791F", S5="#97796A", S6="#8C6D1F"),
    "Monochrome": dict(NAVY="#1F2D47", BLUE="#4F6080", SKY="#9AA8BF", GOLD="#B8902F", GREEN="#1E8A5A", RED="#C0392B", AMBER="#B7791F", S5="#6B7C99", S6="#8C6D1F"),
}
PALETTES = PALETTES_DARK  # names are identical in both modes

PAL: dict = {}
SERIES: list = []


def apply_theme(palette: str = "Navy & Gold", dark: bool = True) -> dict:
    """Activate a colour palette + light/dark surface set. Read colours from the returned PAL dict."""
    mode = "dark" if dark else "light"
    pals = PALETTES_DARK if dark else PALETTES_LIGHT
    PAL.clear()
    PAL.update(SURFACES[mode])
    PAL.update(pals.get(palette, pals["Navy & Gold"]))
    PAL.update(MODE=mode, NAME=palette, INK=PAL["TEXT"], HEIGHT=1.0)
    SERIES[:] = [PAL["NAVY"], PAL["GOLD"], PAL["BLUE"], PAL["SKY"], PAL["S5"], PAL["S6"], PAL["GREEN"], PAL["AMBER"]]
    return PAL


apply_theme()


def rgba(hex_colour: str, alpha: float) -> str:
    h = hex_colour.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def build_css(dark: bool = True) -> str:
    s = SURFACES["dark" if dark else "light"]
    P = s["PILL"]
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@400;500;600;700&display=swap');
:root {{ --bg:{s['BG']}; --bg2:{s['BG2']}; --card:{s['CARD']}; --card2:{s['CARD2']}; --border:{s['BORDER']}; --text:{s['TEXT']};
        --muted:{s['MUTED']}; --strong:{s['STRONG']}; --accent:{s['ACCENT']}; --shadow:{s['SHADOW']}; --up:{s['UP']}; --down:{s['DOWN']}; }}
html, body, [class*="css"] {{ font-family: {BODY_FONT}; }}
.stApp {{ background: {"radial-gradient(1200px 520px at 12% -12%, " + s['BG2'] + " 0%, " + s['BG'] + " 62%)" if dark else s['BG']}; color: var(--text); }}
.stApp p, .stApp li, .stApp label, .stApp span, .stApp div[data-testid="stMarkdownContainer"] {{ color: var(--text); }}
div[data-testid="stCaptionContainer"], div[data-testid="stCaptionContainer"] * {{ color: var(--muted) !important; }}
header[data-testid="stHeader"] {{ background: transparent; }}
section[data-testid="stSidebar"], div[data-testid="collapsedControl"] {{ display: none; }}
.block-container {{ padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1560px; }}
/* ---- display heading font (contrasts with Inter body) ---- */
h1, h2, h3, h4, .hf, .sec-title, .hero h1, .kpi .v, .snap .s .v, .panel h4 {{ font-family: {HEADING_FONT} !important; font-weight: 400 !important; letter-spacing: .2px; }}
h1, h2, h3, h4 {{ color: var(--strong); }}
/* ---- hero ---- */
.hero {{ background: linear-gradient(115deg, #0B1F3F 0%, #17356A 100%); border-radius: 18px; padding: 1.2rem 1.6rem 1.1rem 1.6rem;
        border-bottom: 3px solid #D6B25E; margin-bottom: .9rem; box-shadow: 0 10px 28px var(--shadow); }}
.hero h1 {{ color: #FFFFFF !important; margin: 0; font-size: 2.15rem; line-height: 1.1; }}
.hero .sub {{ color: #B9C7DD !important; font-size: .86rem; margin-top: .3rem; }}
.hero .chip {{ display:inline-block; background: rgba(214,178,94,.16); border:1px solid #D6B25E; color:#F1DFA9 !important; padding:.12rem .7rem;
        border-radius: 999px; font-size:.72rem; margin-right:.4rem; margin-top:.55rem; }}
.snap {{ display:flex; gap:.7rem; flex-wrap:wrap; margin-top:.95rem; }}
.snap .s {{ background: rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.14); border-radius:12px; padding:.5rem .85rem; min-width:136px; }}
.snap .s .l {{ font-size:.63rem; letter-spacing:1.1px; text-transform:uppercase; color:#B9C7DD !important; }}
.snap .s .v {{ font-size:1.3rem; color:#FFFFFF !important; }}
.snap .s .d {{ font-size:.7rem; font-weight:600; }}
.snap .up {{ color:#52D6A0 !important; }} .snap .dn {{ color:#FF8A7C !important; }} .snap .fl {{ color:#B9C7DD !important; }}
/* ---- navigation / pills ---- */
div[data-testid="stRadio"] > div[role="radiogroup"] {{ gap:.45rem; flex-wrap:wrap; }}
div[data-testid="stRadio"] label[data-baseweb="radio"] {{ background:var(--card); border:1px solid var(--border); border-radius:999px;
        padding:.3rem .95rem; margin:0; cursor:pointer; transition: all .15s; box-shadow: 0 1px 3px var(--shadow); }}
div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {{ border-color:var(--accent); transform: translateY(-1px); }}
div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {{ display:none; }}
div[data-testid="stRadio"] label[data-baseweb="radio"] p {{ color: var(--text); font-size:.86rem; }}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {{ background:var(--accent); border-color:var(--accent); }}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p {{ color:#0A1426 !important; font-weight:700; }}
/* ---- widgets (explicit so both modes look identical in structure) ---- */
div[data-baseweb="select"] > div {{ background: var(--card) !important; border-color: var(--border) !important; color: var(--text) !important; }}
div[data-baseweb="select"] * {{ color: var(--text) !important; }}
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li, div[data-baseweb="menu"] {{ background: var(--card) !important; color: var(--text) !important; }}
div[data-baseweb="popover"] li:hover {{ background: var(--card2) !important; }}
span[data-baseweb="tag"] {{ background: var(--accent) !important; }} span[data-baseweb="tag"] * {{ color:#0A1426 !important; }}
div[data-testid="stPopoverBody"], div[data-testid="stPopover"] + div [data-baseweb="popover"] > div {{ background: var(--card) !important; border:1px solid var(--border); }}
div[data-testid="stPopover"] button, div[data-testid="stDownloadButton"] button, div[data-testid="stButton"] button {{
        background: var(--card) !important; color: var(--text) !important; border:1px solid var(--border) !important; border-radius: 10px; }}
div[data-testid="stPopover"] button:hover, div[data-testid="stDownloadButton"] button:hover {{ border-color: var(--accent) !important; }}
div[data-testid="stExpander"] details {{ background: var(--card); border:1px solid var(--border); border-radius:12px; }}
div[data-testid="stExpander"] summary, div[data-testid="stExpander"] summary * {{ color: var(--text) !important; }}
div[data-testid="stSliderThumbValue"], div[data-testid="stTickBarMin"], div[data-testid="stTickBarMax"] {{ color: var(--text) !important; }}
button[data-baseweb="tab"] p {{ color: var(--muted); font-weight:600; }}
button[data-baseweb="tab"][aria-selected="true"] p {{ color: var(--accent); }}
div[data-testid="stAlert"] {{ background: var(--card2); color: var(--text); border:1px solid var(--border); }}
/* ---- headings, cards ---- */
.sec-title {{ color: var(--strong); font-size: 1.65rem; margin: 1.2rem 0 .2rem 0; padding-bottom: .2rem; border-bottom: 3px solid var(--accent); display: inline-block; }}
.sec-sub {{ color: var(--muted); font-size: .88rem; margin: .1rem 0 .7rem 0; }}
.intro {{ background: linear-gradient(90deg, var(--card2), var(--card)); border:1px solid var(--border); border-radius:14px; padding:.8rem 1.1rem;
        margin: .3rem 0 1rem 0; font-size:.9rem; line-height:1.55; box-shadow: 0 2px 8px var(--shadow); }}
.intro b {{ color: var(--accent); }}
.kpi {{ background: linear-gradient(160deg, var(--card2) 0%, var(--card) 100%); border-radius: 16px; padding: 1rem 1.1rem .85rem 1.1rem;
        border: 1px solid var(--border); border-top: 3px solid var(--accent); box-shadow: 0 6px 18px var(--shadow); height: 100%; cursor: help; }}
.kpi .l {{ font-size: .7rem; text-transform: uppercase; letter-spacing: 1.1px; color: var(--muted); font-weight: 600; }}
.kpi .v {{ font-size: 1.85rem; color: var(--strong); margin: .1rem 0; line-height:1.15; }}
.kpi .d {{ font-size: .8rem; font-weight: 600; }}
.kpi .d.good {{ color: var(--up); }} .kpi .d.bad {{ color: var(--down); }} .kpi .d.flat {{ color: var(--muted); }}
.kpi .f {{ font-size: .72rem; color: var(--muted); margin-top: .2rem; }}
.chart-head {{ margin: .6rem 0 .25rem 0; }}
.chart-head .t {{ font-family: {HEADING_FONT}; font-size: 1.2rem; color: var(--strong); line-height:1.2; }}
.chart-head .h {{ font-size: .8rem; color: var(--muted); margin-top:.15rem; line-height:1.45; }}
.chart-head .h b {{ color: var(--accent); font-weight:700; }}
.insight {{ background: var(--card); border:1px solid var(--border); border-left: 4px solid var(--accent); border-radius: 10px; padding: .7rem 1rem;
        margin: .3rem 0 1.1rem 0; font-size: .87rem; color: var(--text); line-height:1.55; box-shadow: 0 2px 8px var(--shadow); }}
.insight .h {{ font-size: .66rem; letter-spacing: 1.2px; text-transform: uppercase; color: var(--accent); font-weight: 700; margin-bottom: .15rem; }}
.panel {{ background: var(--card); border:1px solid var(--border); border-radius:16px; padding: 1rem 1.2rem; box-shadow: 0 6px 18px var(--shadow); }}
.panel.good {{ border-top: 4px solid var(--up); }} .panel.bad {{ border-top: 4px solid #E3AA45; }} .panel.navy {{ border-top: 4px solid var(--accent); }}
.panel h4 {{ margin: 0 0 .5rem 0; color: var(--strong); font-size: 1.25rem; }}
.panel li {{ margin-bottom: .45rem; font-size: .88rem; line-height: 1.5; color: var(--text); }}
.pill {{ display:inline-block; padding:.1rem .65rem; border-radius:999px; font-size:.72rem; font-weight:700; }}
.pill.Risk {{ background:{P['risk'][0]}; color:{P['risk'][1]} !important; }}
.pill.Watch {{ background:{P['watch'][0]}; color:{P['watch'][1]} !important; }}
.pill.Healthy {{ background:{P['ok'][0]}; color:{P['ok'][1]} !important; }}
.tbl-wrap {{ overflow:auto; border:1px solid var(--border); border-radius:12px; box-shadow: 0 2px 8px var(--shadow); }}
table.rt {{ width:100%; border-collapse: collapse; font-size:.83rem; background: var(--card); }}
table.rt th {{ background: {"#0E2347" if dark else "#0B1F3F"}; color:#FFFFFF !important; padding:.55rem .65rem; text-align:left; font-weight:600; position:sticky; top:0; border-bottom:2px solid var(--accent); }}
table.rt td {{ padding:.5rem .65rem; border-bottom:1px solid var(--border); vertical-align: top; color: var(--text); }}
table.rt tr:nth-child(even) td {{ background: var(--card2); }}
table.rt td.num {{ text-align:right; font-variant-numeric: tabular-nums; white-space:nowrap; }}
table.rt td.f {{ color: var(--muted); font-size:.76rem; max-width:300px; }}
.gl dt {{ color: var(--accent); font-weight:700; margin-top:.5rem; }} .gl dd {{ margin:0 0 .2rem 0; color: var(--text); font-size:.86rem; }}
.foot {{ color: var(--muted); font-size:.74rem; text-align:center; margin-top:2rem; border-top:1px solid var(--border); padding-top:.7rem; }}
@media (max-width: 900px) {{ .kpi .v {{ font-size: 1.4rem; }} .hero h1 {{ font-size: 1.5rem; }} }}
</style>
"""


def sparkline(values: list, color: str | None = None, w: int = 120, h: int = 30) -> str:
    color = color or PAL["NAVY"]
    vals = [v for v in values if v == v]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    pts = [(i * (w - 4) / (len(vals) - 1) + 2, h - 3 - (v - lo) / rng * (h - 6)) for i, v in enumerate(vals)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lx, ly = pts[-1]
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
            f'<polyline fill="none" stroke="{color}" stroke-width="1.8" points="{path}"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.8" fill="{PAL["ACCENT"]}"/></svg>')


def kpi_card(label: str, value: str, delta_txt: str, tone: str, spark: list, foot: str = "", hint: str = "") -> str:
    cls = {"good": "good", "bad": "bad"}.get(tone, "flat")
    tip = f' title="{html.escape(hint, quote=True)}"' if hint else ""
    return (f'<div class="kpi"{tip}><div class="l">{html.escape(label)}</div><div class="v">{html.escape(value)}</div>'
            f'<div class="d {cls}">{html.escape(delta_txt)}</div>'
            f'<div style="margin-top:.2rem">{sparkline(spark, PAL["NAVY"])}</div><div class="f">{html.escape(foot)}</div></div>')


def insight_box(text: str, title: str = "What this means") -> str:
    if not text:
        return ""
    return f'<div class="insight"><div class="h">{html.escape(title)}</div>{html.escape(text)}</div>'


def chart_head(title: str, how: str) -> str:
    """Heading + plain-English 'how to read this chart' line rendered above a chart."""
    return (f'<div class="chart-head"><div class="t">{html.escape(title)}</div>'
            f'<div class="h"><b>How to read:</b> {html.escape(how)}</div></div>')


def style_fig(fig, title: str | None = None, height: int = 420, yaxis_title: str | None = None, legend: bool = True,
              hover: str = "x unified", xaxis_title: str | None = "Financial year"):
    """Apply the corporate Plotly template (dark or light) to any figure."""
    ink, grid, card, strong = PAL["INK"], PAL["GRID"], PAL["CARD"], PAL["STRONG"]
    fig.update_layout(
        template="plotly_dark" if PAL["MODE"] == "dark" else "plotly_white",
        title=dict(text=title, x=0.01, xanchor="left", font=dict(size=15, color=strong, family=BODY_FONT)) if title else None,
        font=dict(family=BODY_FONT, color=ink, size=12),
        height=int(height * float(PAL["HEIGHT"])), margin=dict(l=10, r=10, t=55 if title else 20, b=10),
        paper_bgcolor=card, plot_bgcolor=card, hovermode=hover,
        legend=dict(orientation="h", yanchor="bottom", y=-0.32, xanchor="left", x=0, font=dict(color=ink)) if legend else None,
        showlegend=legend, colorway=list(SERIES),
        hoverlabel=dict(bgcolor=PAL["BG"], bordercolor=PAL["ACCENT"], font=dict(color=strong)),
    )
    fig.update_xaxes(showgrid=False, linecolor=grid, tickfont=dict(size=11, color=ink), title_text=xaxis_title,
                     title_font=dict(size=11, color=PAL["MUTED"]))
    fig.update_yaxes(gridcolor=grid, zeroline=True, zerolinecolor=PAL["ZERO"], tickfont=dict(size=11, color=ink), title_text=yaxis_title,
                     title_font=dict(size=11, color=PAL["MUTED"]))
    return fig
