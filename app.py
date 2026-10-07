"""
WTG Condition Monitoring - temperature analysis & PDF reporting (Streamlit).

Run:  streamlit run wtg_condition_monitoring.py
Data: upload a CSV or place `WTG.csv` next to this file.
      Needs a Time column and one or more temperature columns.
      A WTG column (Name / WTG / Turbine ...) is optional.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from matplotlib.figure import Figure  # no pyplot -> no global state / leaks
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

st.set_page_config(page_title="WTG Condition Monitoring", page_icon="⚡",
                   layout="wide", initial_sidebar_state="collapsed")

# ============================================================
# CONSTANTS
# ============================================================
DEFAULT_FILE = "WTG.csv"
NAME_COL = "Name"                       # internal WTG column name
NAME_ALIASES = {"name", "wtg", "wtg name", "turbine", "turbine name", "asset", "device"}
TIME_ALIASES = ("time", "timestamp", "date time", "datetime", "date")

WARNING_TEMP, HIGH_TEMP = 75.0, 90.0
MAX_PLOT_POINTS = 600
TABLE_ROW_LIMIT = 10_000

PLOT_COLORS = ["#0D47A1", "#06B6D4", "#6A1B9A", "#BF360C", "#C62828",
               "#2E7D32", "#0288D1", "#8E24AA", "#E64A19", "#F9A825"]

DE = r"\b(de|drive end)\b"
NDE = r"\b(nde|non drive end)\b"
# (label, icon, must-match patterns, must-not-match patterns)
KPI_DEFS = [
    ("Generator DE Bearing", "🔩", ["generator", DE, "bearing"], [NDE]),
    ("Generator NDE Bearing", "🔩", ["generator", NDE, "bearing"], []),
    ("Gearbox DE Bearing", "⚙️", ["gearbox", DE, "bearing"], [NDE]),
    ("Gearbox NDE Bearing", "⚙️", ["gearbox", NDE, "bearing"], []),
    ("Gearbox Oil", "🛢️", ["gearbox", r"\boil\b"], []),
    ("Main Bearing", "🔄", ["main", "bearing"], []),
]

# st.dataframe / plotly / image / button changed their "stretch" argument in 1.50
_ver = tuple(int(p) for p in re.findall(r"\d+", st.__version__)[:2])
STRETCH = {"width": "stretch"} if _ver >= (1, 50) else {"use_container_width": True}


@dataclass(frozen=True)
class Selection:
    source: str
    name: str
    parameter: str
    start: date
    end: date


@dataclass(frozen=True)
class Kpis:
    average: float
    maximum: float
    minimum: float
    median: float
    top_wtg: str
    top_max: float


# ============================================================
# STYLING
# ============================================================
APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
#MainMenu, footer, header {visibility:hidden}
html, body, [class*="css"] {font-family:"Inter",sans-serif}
.block-container {padding:0 2rem 3rem !important; margin-top:0 !important;
    background:#e3ebfa; max-width:100% !important; color:#0b1a2b}

@keyframes gradientShift {0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%}}
@keyframes shimmer {0%{background-position:-200% 0} 100%{background-position:200% 0}}

.topbar {background:linear-gradient(135deg,#0C4A6E,#06B6D4); background-size:300% 300%;
    animation:gradientShift 10s ease infinite; padding:14px 28px; display:flex;
    align-items:center; gap:14px; margin-bottom:22px; border-radius:0 0 14px 14px;
    box-shadow:0 10px 30px rgba(12,74,110,.3); border-bottom:4px solid #06B6D4;
    position:relative; overflow:hidden}
.topbar::before {content:''; position:absolute; top:0; left:0; right:0; height:4px;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.7),transparent);
    background-size:200% 100%; animation:shimmer 3s infinite}
.topbar h2 {margin:0; font-size:30px; font-weight:800; color:#fff; letter-spacing:-.5px}
.topbar p {margin:2px 0 0; font-size:13px; color:#fff; text-transform:uppercase;
    letter-spacing:1.2px; font-weight:700}
.topbar-badge {margin-left:auto; display:inline-flex; align-items:center; gap:7px;
    padding:6px 14px; border-radius:20px; background:rgba(255,255,255,.15);
    border:1px solid rgba(255,255,255,.3); color:#fff; font-size:12px; font-weight:700}
.live-dot {width:7px; height:7px; border-radius:50%; background:#31e6a1; box-shadow:0 0 8px #31e6a1}

.sh {font-size:14px; font-weight:900; color:#062e5c; text-transform:uppercase;
    letter-spacing:.08em; margin:22px 0 10px; padding:0 0 8px; border-bottom:3px solid #0d47a1}

.kpi {background:#fff; border-radius:14px; padding:18px 16px; text-align:center;
    border:1.5px solid #9fb7dd; border-top:5px solid #1b5e20; margin-bottom:12px;
    box-shadow:0 2px 10px rgba(13,71,161,.12); transition:transform .25s, box-shadow .25s}
.kpi:hover {transform:translateY(-5px); box-shadow:0 12px 22px rgba(12,74,110,.15)}
.kpi-val {font-size:30px; font-weight:900; line-height:1; color:#062e5c; margin-bottom:6px}
.kpi-val small {font-size:14px; color:#78909c}
.kpi-lbl {font-size:11.5px; font-weight:800; color:#37474f; text-transform:uppercase; letter-spacing:.06em}
.kpi-status {font-size:11.5px; margin-top:6px; font-weight:800; color:#1b5e20}
.kpi.warning {border-top-color:#a83e00} .kpi.warning .kpi-status {color:#a83e00}
.kpi.danger {border-top-color:#a30000}  .kpi.danger .kpi-status {color:#a30000}
.kpi.nodata {border-top-color:#78909c}  .kpi.nodata .kpi-status {color:#78909c}

.status-box {padding:13px 18px; border-radius:10px; background:#d7f0e0; border:2px solid #2e7d32;
    color:#0d3d13; font-weight:800; margin-bottom:14px}
.status-box.warning {background:#ffedb3; border-color:#a83e00; color:#7a2900}
.status-box.danger {background:#fbd0dd; border-color:#a30000; color:#6b0030}

.highlight-box {padding:16px 20px; border-radius:12px; background:#d7f0e0;
    border:2px solid #2e7d32; margin-bottom:14px}
.highlight-box.warning {background:#ffedb3; border-color:#a83e00}
.highlight-box.danger {background:#fbd0dd; border-color:#a30000}
.hb-sensor {font-size:13.5px; color:#37474f; font-weight:800}
.hb-val {font-size:24px; color:#062e5c; font-weight:900}
.hb-val small {font-size:13px; color:#607d8b; font-weight:600}
.hb-meta {font-size:12.5px; color:#2b3d4a; font-weight:600; margin-top:3px}

.detail-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin-bottom:8px}
.detail-item {background:#fff; border:1.5px solid #9fb7dd; border-left:4px solid #1b5e20;
    border-radius:10px; padding:9px 13px}
.detail-item.warning {border-left-color:#a83e00}
.detail-item.danger {border-left-color:#a30000}
.detail-item.is-max {background:#fbd0dd; border-color:#a30000}
.di-name {font-size:10.5px; color:#37474f; font-weight:800; text-transform:uppercase}
.di-val {font-size:18px; color:#062e5c; font-weight:900; margin-top:3px}
.di-val span {font-size:11px; color:#455a64; margin-left:2px; font-weight:700}

[data-testid="stDataFrame"] {border-radius:12px; overflow:hidden; border:2px solid #6f93cf !important}
div[data-baseweb="select"] > div {background:#fff !important; border:1.8px solid #6f93cf !important;
    border-radius:10px !important; color:#0b1a2b !important}

div[data-testid="stRadio"] > label {display:none}
div[data-testid="stRadio"] > div[role="radiogroup"] {flex-direction:row; gap:8px; background:#fff;
    padding:8px; border-radius:18px; border:1.5px solid #9fb7dd;
    box-shadow:0 6px 18px rgba(13,71,161,.10); margin-bottom:20px; width:fit-content}
div[data-testid="stRadio"] label[data-baseweb="radio"] {padding:11px 28px; border-radius:12px;
    transition:all .25s ease; margin:0 !important}
div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {display:none}
div[data-testid="stRadio"] label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {
    font-weight:800 !important; font-size:14.5px !important; color:#062e5c !important}
div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {background:#e3ebfa}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
    background:linear-gradient(135deg,#0C4A6E,#06B6D4); box-shadow:0 6px 16px rgba(6,182,212,.4)}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked)
    div[data-testid="stMarkdownContainer"] p {color:#fff !important}

.analysis-card {background:#fff; border-radius:14px; padding:18px; border:1px solid #c7d5eb;
    box-shadow:0 4px 15px rgba(13,71,161,.08); height:100%}
.analysis-title {color:#062e5c; font-size:12px; font-weight:800; text-transform:uppercase}
.analysis-value {color:#0d47a1; font-size:26px; font-weight:900; margin-top:5px}
.analysis-value.red {color:#C62828}

.report-card {background:#fff; border-left:5px solid #0d47a1; padding:18px 22px;
    border-radius:10px; box-shadow:0 3px 12px rgba(15,23,42,.06); margin-bottom:15px}
.app-footer {text-align:center; padding:25px 0 10px; color:#607D8B; font-size:12px; font-weight:600}
</style>
"""


def md(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def section(title: str) -> None:
    md(f'<div class="sh">{title}</div>')


def render_header() -> None:
    md(APP_CSS)
    md("""
    <div class="topbar">
      <div><h2>⚡ WTG Condition Monitoring</h2>
           <p>Wind Turbine Generator · Thermal &amp; Bearing Health</p></div>
      <span class="topbar-badge"><span class="live-dot"></span>MONITORING ACTIVE</span>
    </div>""")


# ============================================================
# HELPERS
# ============================================================
def temperature_status(value: float) -> tuple[str, str]:
    """-> (status label, css class). Normal has an empty css class."""
    if pd.isna(value):
        return "NO DATA", "nodata"
    if value >= HIGH_TEMP:
        return "HIGH", "danger"
    if value >= WARNING_TEMP:
        return "WARNING", "warning"
    return "NORMAL", ""


def _norm(text) -> str:
    """'Gen. Non-Drive-End Bearing (°C)' -> 'gen non drive end bearing c'"""
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def find_column(columns, include, exclude=()):
    """First column whose normalised name matches ALL `include` and NONE of `exclude` regexes."""
    for col in columns:
        name = _norm(col)
        if all(re.search(p, name) for p in include) and not any(re.search(p, name) for p in exclude):
            return col
    return None


def clean_column_name(col) -> str:
    col = re.sub(r"\(\s*[^\w\s]{1,4}C?\)", "(°C)", str(col).strip())
    return re.sub(r"\s{2,}", " ", col).strip()


def natural_key(text: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


# ============================================================
# DATA LAYER
# ============================================================
@st.cache_data(show_spinner="Reading CSV…", max_entries=5)
def load_data(file_bytes: bytes):
    """Parse + clean the CSV once. Returns (df, time_col, temperature_columns)."""
    try:
        df = pd.read_csv(BytesIO(file_bytes), encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(BytesIO(file_bytes), encoding="latin1")

    df.columns = [clean_column_name(c) for c in df.columns]
    df = df.dropna(how="all")

    # --- time column (exact aliases first, then any "time"-like column)
    time_col = next((c for c in df.columns if _norm(c) in TIME_ALIASES), None) \
        or find_column(df.columns, ["time"])
    if time_col is None:
        raise ValueError("No `Time` column found in the CSV.")
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col])

    # --- WTG column (always exposed as NAME_COL)
    name_src = next((c for c in df.columns if _norm(c) in NAME_ALIASES), None)
    if name_src and name_src != NAME_COL:
        df = df.rename(columns={name_src: NAME_COL})
    if NAME_COL not in df.columns:
        df[NAME_COL] = "WTG"
    names = df[NAME_COL].astype(str).str.strip()
    cats = sorted(names.unique(), key=natural_key)
    df[NAME_COL] = pd.Categorical(names, categories=cats)       # compact + fast groupby

    df = (df.sort_values(time_col)
            .drop_duplicates(subset=[NAME_COL, time_col], keep="last")
            .reset_index(drop=True))

    # --- temperature columns -> numeric
    temp_cols = [c for c in df.columns
                 if c not in (time_col, NAME_COL) and re.search(r"\btemp(erature)?\b", _norm(c))]
    for col in temp_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = (df[col].astype(str)
                       .str.replace(r"(?<=\d),(?=\d)", ".", regex=True)   # decimal comma
                       .str.extract(r"(-?\d+\.?\d*)")[0])
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df, time_col, temp_cols


def load_source(uploaded):
    """Resolve the data source and load it; stops the app with a clear message on failure."""
    if uploaded is not None:
        raw, source = uploaded.getvalue(), uploaded.name
    else:
        path = Path(DEFAULT_FILE)
        if not path.exists():
            st.error(f"❌ `{DEFAULT_FILE}` not found. Upload a WTG CSV above.")
            st.stop()
        raw, source = path.read_bytes(), path.name

    try:
        df, time_col, temp_cols = load_data(raw)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unable to read CSV file: {exc}")
        st.stop()

    if not temp_cols:
        st.error("❌ No temperature columns detected.")
        with st.expander("Detected columns"):
            st.write(list(df.columns))
        st.stop()
    if df[temp_cols].dropna(how="all").empty:
        st.error("❌ All temperature columns are empty or non-numeric.")
        st.stop()
    return df, time_col, temp_cols, source


def apply_filters(df, time_col, sel: Selection):
    end = pd.Timestamp(sel.end) + pd.Timedelta(days=1)
    mask = (df[time_col] >= pd.Timestamp(sel.start)) & (df[time_col] < end)
    if sel.name != "All":
        mask &= df[NAME_COL] == sel.name
    return df.loc[mask]


def latest_readings(data, temp_cols):
    """Last valid value of every sensor, per WTG (rows = WTG, cols = sensor)."""
    return data.groupby(NAME_COL, observed=True)[temp_cols].last()


def fleet_latest(latest_df):
    """Hottest latest value per sensor across the selected WTGs, with the WTG it came from."""
    valid = latest_df.dropna(axis=1, how="all")
    if valid.empty:
        return pd.DataFrame(columns=["value", "wtg"])
    return pd.DataFrame({"value": valid.max(), "wtg": valid.idxmax().astype(str)})


def wtg_statistics(data, column):
    work = data[[NAME_COL, column]].dropna(subset=[column])
    if work.empty:
        return pd.DataFrame()
    out = (work.groupby(NAME_COL, observed=True)[column]
           .agg(Average="mean", Maximum="max", Minimum="min", Median="median", Records="count")
           .reset_index())
    out[NAME_COL] = out[NAME_COL].astype(str)
    return out


def downsample(data, time_col, value_col, by_wtg=False):
    """Time-bucket average so a trace never holds more than MAX_PLOT_POINTS points."""
    if len(data) <= MAX_PLOT_POINTS:
        return data
    span = data[time_col].max() - data[time_col].min()
    rule = f"{max(1, int(span.total_seconds() // MAX_PLOT_POINTS))}s"
    # pd.Grouper is independent of the row index (groupby().resample(on=...) breaks on filtered frames)
    keys = [NAME_COL, pd.Grouper(key=time_col, freq=rule)] if by_wtg else [pd.Grouper(key=time_col, freq=rule)]
    out = data.groupby(keys, observed=True)[value_col].mean().dropna().reset_index()
    return out.sort_values(time_col)


# ============================================================
# STATIC CHARTS (shared by the app and the PDF; rendered once, cached)
# ============================================================
@st.cache_data(show_spinner=False, max_entries=30)
def chart_png(kind: str, summary: pd.DataFrame, column: str) -> bytes:
    """kind: 'max' | 'avg' | 'compare'"""
    order = "Average" if kind == "avg" else "Maximum"
    data = summary.sort_values(order, ascending=False)
    names = data[NAME_COL].tolist()
    x = list(range(len(names)))

    fig = Figure(figsize=(12, 6), dpi=150)
    ax = fig.subplots()

    if kind == "compare":
        w = 0.38
        ax.bar([i - w / 2 for i in x], data["Average"], w, label="Average", color="#1976D2")
        ax.bar([i + w / 2 for i in x], data["Maximum"], w, label="Maximum", color="#E53935")
        title, top = f"Average vs Maximum Temperature — {column}", data["Maximum"].max()
    else:
        vals = data[order].tolist()
        bar_colors = ("#1976D2" if kind == "avg" else
                      ["#C62828" if v >= HIGH_TEMP else "#EF6C00" if v >= WARNING_TEMP else "#2E7D32"
                       for v in vals])
        bars = ax.bar(x, vals, color=bar_colors, edgecolor="#263238", linewidth=.5)
        ax.bar_label(bars, fmt="%.2f", rotation=90, fontsize=8, fontweight="bold", padding=2)
        label = "Average" if kind == "avg" else "Maximum"
        title, top = f"{label} Temperature by WTG — {column}", max(vals)

    ax.axhline(WARNING_TEMP, ls="--", color="#EF6C00", lw=1, label=f"Warning {WARNING_TEMP:g}°C")
    ax.axhline(HIGH_TEMP, ls="--", color="#C62828", lw=1, label=f"High {HIGH_TEMP:g}°C")
    ax.set_ylim(min(0, data["Minimum"].min()), max(top, HIGH_TEMP) * 1.18)   # room for labels
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=60, ha="right")
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xlabel("WTG Name", fontweight="bold")
    ax.set_ylabel("Temperature (°C)", fontweight="bold")
    ax.grid(axis="y", ls="--", alpha=.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    return buf.getvalue()


# ============================================================
# PDF REPORT
# ============================================================
def _table(rows, widths_mm, header_bg="#1E3A8A", grid="#CBD5E1",
           zebra=("#FFFFFF", "#F8FAFC"), font_size=8, extra=()):
    table = Table(rows, colWidths=[w * mm for w in widths_mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor(grid)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor(c) for c in zebra]),
        ("PADDING", (0, 0), (-1, -1), 5),
        *extra,
    ]))
    return table


def _page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawCentredString(A4[0] / 2, 8 * mm, f"WTG Condition Monitoring Report  |  Page {doc.page}")
    canvas.restoreState()


def create_pdf_report(summary, sel: Selection, data, k: Kpis) -> bytes:
    base = getSampleStyleSheet()
    title = ParagraphStyle("T", parent=base["Title"], fontName="Helvetica-Bold", fontSize=23,
                           textColor=colors.HexColor("#0F172A"), alignment=TA_CENTER, spaceAfter=8)
    subtitle = ParagraphStyle("S", parent=base["Normal"], fontSize=10,
                              textColor=colors.HexColor("#64748B"), alignment=TA_CENTER, spaceAfter=15)
    heading = ParagraphStyle("H", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=15,
                             textColor=colors.HexColor("#1E3A8A"), spaceBefore=10, spaceAfter=8)
    body = ParagraphStyle("B", parent=base["Normal"], fontSize=9, leading=13,
                          textColor=colors.HexColor("#334155"))
    foot = ParagraphStyle("F", parent=body, fontSize=9, alignment=TA_CENTER,
                          textColor=colors.HexColor("#64748B"))

    def P(text, style=body):
        return Paragraph(text, style)

    def chart(kind):
        return Image(BytesIO(chart_png(kind, summary, sel.parameter)), width=175 * mm, height=87.5 * mm)

    n_high = int((summary["Maximum"] >= HIGH_TEMP).sum())
    n_warn = int(((summary["Maximum"] >= WARNING_TEMP) & (summary["Maximum"] < HIGH_TEMP)).sum())
    param = xml_escape(sel.parameter)
    fmt = "%d %b %Y"

    story = [
        P("WTG Condition Monitoring Report", title),
        P("Temperature, bearing and thermal health analysis", subtitle),
    ]

    info = [
        ("Report Generated", datetime.now().strftime("%d %B %Y, %I:%M %p")),
        ("Source File", sel.source),
        ("WTG Filter", sel.name),
        ("WTGs in Report", str(len(summary))),
        ("Temperature Measurement", sel.parameter),
        ("Date Range", f"{sel.start.strftime(fmt)} to {sel.end.strftime(fmt)}"),
        ("Records", f"{len(data):,}"),
    ]
    info_table = Table([[k_, P(xml_escape(v))] for k_, v in info], colWidths=[55 * mm, 115 * mm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EFF6FF")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1E3A8A")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#DBEAFE")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [info_table, Spacer(1, 12)]

    # 1. Executive summary
    story += [
        P("1. Executive Summary", heading),
        P(f"The analysis covers <b>{len(data):,}</b> records of <b>{param}</b> across "
          f"<b>{len(summary)}</b> WTG(s). The overall average is <b>{k.average:.2f} °C</b> and the highest "
          f"recorded value is <b>{k.maximum:.2f} °C</b>, reached by <b>{xml_escape(k.top_wtg)}</b>. "
          f"<b>{n_high}</b> WTG(s) exceeded the high threshold ({HIGH_TEMP:g} °C) and "
          f"<b>{n_warn}</b> peaked in the warning band ({WARNING_TEMP:g}-{HIGH_TEMP:g} °C)."),
        Spacer(1, 12),
        P("2. Key Temperature Indicators", heading),
        _table([["Indicator", "Value"],
                ["Average Temperature", f"{k.average:.2f} °C"],
                ["Maximum Temperature", f"{k.maximum:.2f} °C"],
                ["Minimum Temperature", f"{k.minimum:.2f} °C"],
                ["Median Temperature", f"{k.median:.2f} °C"],
                ["Highest Maximum WTG", k.top_wtg],
                ["Highest Maximum Value", f"{k.top_max:.2f} °C"]],
               [95, 75], font_size=9, extra=[("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold")]),
        PageBreak(),
    ]

    # 3. Maximum ranking
    ranked = summary.sort_values("Maximum", ascending=False)
    rank_rows = [["Rank", "WTG Name", "Maximum °C"]] + [
        [str(i), r.Name, f"{r.Maximum:.2f}"] for i, r in enumerate(ranked.itertuples(), 1)]
    story += [
        P("3. Maximum Temperature Analysis", heading),
        P("WTGs are ranked from highest to lowest maximum temperature."),
        chart("max"), Spacer(1, 8),
        _table(rank_rows, [25, 100, 45], header_bg="#B91C1C", grid="#FECACA",
               zebra=("#FFFFFF", "#FEF2F2"), font_size=9,
               extra=[("ALIGN", (0, 0), (0, -1), "CENTER"), ("ALIGN", (2, 0), (2, -1), "RIGHT")]),
        PageBreak(),
        # 4 + 5. Average and comparison share a page
        P("4. Average Temperature Analysis", heading), chart("avg"),
        P("5. Average vs Maximum Temperature", heading), chart("compare"),
        P("This comparison highlights WTGs whose peak temperature is far above their normal operating average."),
        PageBreak(),
    ]

    # 6. Detailed table with status
    status_colors = {"HIGH": "#C62828", "WARNING": "#EF6C00", "NORMAL": "#2E7D32"}
    rows, extra = [["WTG", "Average", "Maximum", "Minimum", "Median", "Records", "Status"]], []
    for i, r in enumerate(summary.itertuples(), 1):
        status = temperature_status(r.Maximum)[0]
        rows.append([r.Name, f"{r.Average:.2f}", f"{r.Maximum:.2f}", f"{r.Minimum:.2f}",
                     f"{r.Median:.2f}", f"{int(r.Records):,}", status])
        extra += [("TEXTCOLOR", (6, i), (6, i), colors.HexColor(status_colors[status])),
                  ("FONTNAME", (6, i), (6, i), "Helvetica-Bold")]
    story += [
        P("6. Detailed WTG Temperature Summary", heading),
        _table(rows, [44, 23, 23, 23, 23, 20, 20], font_size=7.5,
               extra=[("ALIGN", (1, 1), (-2, -1), "RIGHT"), *extra]),
        Spacer(1, 15),
        P("7. Report Notes", heading),
    ]
    notes = [
        "All calculations use the selected WTG and date filters.",
        "Maximum / minimum are the highest / lowest valid readings per WTG; median is the middle value.",
        "Average is the arithmetic mean of valid readings.",
        f"Warning threshold is {WARNING_TEMP:g} °C; high-temperature threshold is {HIGH_TEMP:g} °C.",
        "Status in section 6 is based on each WTG's maximum reading.",
        "Values are rounded to two decimal places.",
    ]
    story += [P(f"&bull; {n}") for n in notes]
    story += [Spacer(1, 15), P("End of WTG Condition Monitoring Report", foot)]

    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                      topMargin=15 * mm, bottomMargin=15 * mm,
                      title="WTG Condition Monitoring Report"
                      ).build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buf.getvalue()


# ============================================================
# UI COMPONENTS
# ============================================================
KPI_STATUS_TEXT = {"": "● Normal", "warning": "▲ Monitor", "danger": "● High", "nodata": "○ No data"}


def kpi_card(label, value, icon, wtg=None) -> str:
    _, css = temperature_status(value)
    shown = "—" if pd.isna(value) else f"{value:.1f}"
    suffix = f" · {html.escape(wtg)}" if wtg and not pd.isna(value) else ""
    return (f'<div class="kpi {css}"><div class="kpi-lbl">{icon} &nbsp;{html.escape(label)}</div>'
            f'<div class="kpi-val">{shown} <small>°C</small></div>'
            f'<div class="kpi-status">{KPI_STATUS_TEXT[css]}{suffix}</div></div>')


def analysis_card(title, value, red=False) -> str:
    return (f'<div class="analysis-card"><div class="analysis-title">{title}</div>'
            f'<div class="analysis-value {"red" if red else ""}">{html.escape(str(value))}</div></div>')


def base_layout(fig, height, legend=False):
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fff",
        font=dict(color="#1a2733", family="Inter", size=13),
        margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
        xaxis=dict(title="Time", showgrid=True, gridcolor="#c9d6e8"),
        yaxis=dict(title="Temperature (°C)", showgrid=True, gridcolor="#c9d6e8"),
        **(dict(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)) if legend else {}),
    )
    return fig


def add_thresholds(fig):
    fig.add_hline(y=WARNING_TEMP, line_dash="dash", line_color="#BF360C",
                  annotation_text=f"Warning {WARNING_TEMP:g}°C", annotation_position="top right")
    fig.add_hline(y=HIGH_TEMP, line_dash="dash", line_color="#C62828",
                  annotation_text=f"High {HIGH_TEMP:g}°C", annotation_position="top right")


def style_status(df: pd.DataFrame):
    palette = {"HIGH": "background-color:#fbd0dd;color:#6b0030",
               "WARNING": "background-color:#ffedb3;color:#7a2900",
               "NORMAL": "background-color:#d7f0e0;color:#0d3d13"}
    styler = df.style.format({c: "{:.2f}" for c in df.select_dtypes("number").columns})
    apply_cell = getattr(styler, "map", None) or styler.applymap     # pandas >=2.1 / older
    return apply_cell(lambda v: palette.get(v, ""), subset=["Status"])


# ============================================================
# FILTERS
# ============================================================
def render_filters(df, time_col, temp_cols, source) -> Selection:
    section("🔍 &nbsp;Filters &amp; Data Source")
    lo, hi = df[time_col].min().date(), df[time_col].max().date()
    names = ["All"] + list(df[NAME_COL].cat.categories)

    c1, c2, c3, c4 = st.columns([1.3, 1.5, 1, 1])
    name = c1.selectbox("WTG Name", names)
    parameter = c2.selectbox("Primary Temperature", temp_cols)
    start = c3.date_input("Start date", value=lo, min_value=lo, max_value=hi)
    end = c4.date_input("End date", value=hi, min_value=lo, max_value=hi)

    if start > end:
        st.error("❌ Start date must be before end date.")
        st.stop()
    return Selection(source, name, parameter, start, end)


# ============================================================
# TAB: OVERVIEW
# ============================================================
def render_overview(data, sel, temp_cols, time_col):
    latest = fleet_latest(latest_readings(data, temp_cols))
    if latest.empty:
        st.warning("No valid sensor readings in the selected range.")
        return

    show_wtg = sel.name == "All"
    top_sensor = latest["value"].idxmax()
    top_value, top_wtg = latest.at[top_sensor, "value"], latest.at[top_sensor, "wtg"]
    status, css = temperature_status(top_value)

    messages = {
        "": "🟢 <b>WTG HEALTH STATUS: NORMAL</b><br>All monitored temperatures are within range.",
        "warning": "🟡 <b>WTG HEALTH STATUS: WARNING</b><br>One or more temperatures require attention.",
        "danger": "🔴 <b>WTG HEALTH STATUS: HIGH TEMPERATURE</b><br>One or more temperatures are above threshold.",
    }
    md(f'<div class="status-box {css}">{messages[css]}</div>')

    items = "".join(
        f'<div class="detail-item {temperature_status(row.value)[1]} {"is-max" if sensor == top_sensor else ""}">'
        f'<div class="di-name">{html.escape(str(sensor))}'
        f'{" · " + html.escape(row.wtg) if show_wtg else ""}</div>'
        f'<div class="di-val">{row.value:.1f}<span>°C</span></div></div>'
        for sensor, row in latest.iterrows())

    where = f"All WTGs (hottest: {html.escape(top_wtg)})" if show_wtg else html.escape(sel.name)
    stamp = data[time_col].max().strftime("%d %b %Y %H:%M")
    md(f"""
    <div class="highlight-box {css}">
      <div class="hb-sensor">🌡️ Highest Latest Reading — {where}</div>
      <div class="hb-val">{top_value:.2f} °C <small>({html.escape(str(top_sensor))})</small></div>
      <div class="hb-meta">Data up to {stamp} · Status: {status}</div>
    </div>
    <div class="sh">📇 &nbsp;Full Sensor Snapshot</div>
    <div class="detail-grid">{items}</div>""")

    section("📊 &nbsp;Key Performance Indicators")
    cols = st.columns(3)
    shown = 0
    for label, icon, include, exclude in KPI_DEFS:
        col = find_column(temp_cols, include, exclude)
        if col is None:
            continue
        value = latest["value"].get(col, float("nan"))
        wtg = latest["wtg"].get(col) if show_wtg else None
        cols[shown % 3].markdown(kpi_card(label, value, icon, wtg), unsafe_allow_html=True)
        shown += 1
    if shown == 0:
        st.info("No standard bearing / gearbox sensors recognised in this file — "
                "see the Sensor Snapshot above for all temperatures.")


# ============================================================
# TAB: TRENDS
# ============================================================
def render_trends(data, sel, temp_cols, time_col):
    multi = sel.name == "All" and data[NAME_COL].nunique() > 1

    section("📈 &nbsp;Temperature Trend")
    param = sel.parameter
    base = data[[time_col, NAME_COL, param]].dropna(subset=[param])
    if base.empty:
        st.warning(f"No numeric data for '{param}'.")
    else:
        plot = downsample(base, time_col, param, by_wtg=multi)
        fig = go.Figure()
        groups = plot.groupby(NAME_COL, observed=True) if multi else [(sel.name, plot)]
        for i, (wtg, g) in enumerate(groups):
            if g.empty:
                continue
            fig.add_trace(go.Scatter(
                x=g[time_col], y=g[param], mode="lines", name=str(wtg),
                line=dict(color=PLOT_COLORS[i % len(PLOT_COLORS)] if multi else "#0D47A1",
                          width=1.6 if multi else 2),
                **({} if multi else dict(fill="tozeroy", fillcolor="rgba(6,182,212,0.10)")),
                hovertemplate=f"<b>{wtg}</b> %{{y:.2f}} °C<extra></extra>"))
        add_thresholds(fig)
        base_layout(fig, 500, legend=multi)
        st.plotly_chart(fig, **STRETCH)

    section("🌡️ &nbsp;All Temperature Sensors")
    if multi:
        st.caption("Fleet average across the selected WTGs. Choose a single WTG to see its individual sensors.")
    fig_all = go.Figure()
    for i, col in enumerate(temp_cols):
        sub = data[[time_col, col]].dropna()
        if sub.empty:
            continue
        s = downsample(sub, time_col, col)
        fig_all.add_trace(go.Scatter(
            x=s[time_col], y=s[col], mode="lines", name=col,
            line=dict(color=PLOT_COLORS[i % len(PLOT_COLORS)], width=1.5),
            hovertemplate=f"<b>{col}</b><br>%{{y:.2f}} °C<extra></extra>"))
    if not fig_all.data:
        st.warning("No numeric sensor data available.")
        return
    add_thresholds(fig_all)
    base_layout(fig_all, 550, legend=True)
    st.plotly_chart(fig_all, **STRETCH)


# ============================================================
# TAB: DATA & HEALTH
# ============================================================
def render_health_table(data, sel, temp_cols):
    section("🩺 &nbsp;Sensor Health Overview")
    latest = fleet_latest(latest_readings(data, temp_cols))
    if latest.empty:
        st.info("No valid sensor readings.")
        return
    stats = data[temp_cols].agg(["mean", "min", "max"]).T
    health = stats.join(latest).dropna(subset=["value"])
    out = pd.DataFrame({
        "Sensor": health.index,
        "Latest (°C)": health["value"].to_numpy(),
        "Average (°C)": health["mean"].to_numpy(),
        "Minimum (°C)": health["min"].to_numpy(),
        "Maximum (°C)": health["max"].to_numpy(),
        "Status": [temperature_status(v)[0] for v in health["value"]],
    })
    if sel.name == "All":
        out.insert(2, "Latest from", health["wtg"].to_numpy())
    out = out.sort_values("Latest (°C)", ascending=False).reset_index(drop=True)
    st.dataframe(style_status(out), hide_index=True, **STRETCH)


def render_pdf_section(summary, sel, data, k):
    section("📄 &nbsp;Professional PDF Report")
    md("""<div class="report-card"><b>Report contents</b><br><br>
        • Filters, source file and temperature measurement<br>
        • Executive summary and overall KPIs<br>
        • Maximum / average rankings and comparison charts<br>
        • Detailed per-WTG statistics with status<br>
        • Thresholds, notes and generation timestamp</div>""")

    sig = (sel.source, sel.name, sel.parameter, sel.start, sel.end)
    if st.button("📄 Generate Complete PDF Report", type="primary", **STRETCH):
        with st.spinner("Creating professional PDF report…"):
            try:
                st.session_state["wtg_pdf"] = {
                    "sig": sig,
                    "bytes": create_pdf_report(summary, sel, data, k),
                    "name": f"WTG_Temperature_Report_{datetime.now():%Y%m%d_%H%M}.pdf",
                }
                st.success("✅ PDF report generated successfully.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"PDF generation failed: {exc}")

    stored = st.session_state.get("wtg_pdf")
    if stored and stored["sig"] == sig:          # never offer a PDF that doesn't match the filters
        st.download_button("⬇️ Download Temperature Analysis PDF", data=stored["bytes"],
                           file_name=stored["name"], mime="application/pdf", **STRETCH)
    elif stored:
        st.caption("Filters changed since the last report — generate a new PDF.")


def render_health(data, sel, temp_cols, time_col):
    render_health_table(data, sel, temp_cols)

    section("📊 &nbsp;WTG Temperature Analysis")
    md(f'<div class="report-card"><b>Selected Measurement:</b> {html.escape(sel.parameter)}<br><br>'
       'Compares the selected measurement across WTGs for the chosen date range.</div>')

    summary = wtg_statistics(data, sel.parameter)
    if summary.empty:
        st.warning("No valid data is available for WTG analysis.")
        return

    series = data[sel.parameter].dropna()
    top = summary.loc[summary["Maximum"].idxmax()]
    k = Kpis(series.mean(), series.max(), series.min(), series.median(), top[NAME_COL], top["Maximum"])

    cards = [("Overall Average", f"{k.average:.2f} °C", False), ("Overall Maximum", f"{k.maximum:.2f} °C", True),
             ("Highest WTG", k.top_wtg, False), ("Highest WTG Maximum", f"{k.top_max:.2f} °C", True)]
    for col, (title, value, red) in zip(st.columns(4), cards):
        col.markdown(analysis_card(title, value, red), unsafe_allow_html=True)

    section("📋 &nbsp;WTG Statistical Summary")
    table = summary.rename(columns={NAME_COL: "WTG Name", "Average": "Average °C", "Maximum": "Maximum °C",
                                    "Minimum": "Minimum °C", "Median": "Median °C"}).round(2)
    st.dataframe(table, hide_index=True, **STRETCH)

    for heading, kind in [("🔥 &nbsp;Maximum Temperature Ranking", "max"),
                          ("📈 &nbsp;Average Temperature Ranking", "avg"),
                          ("⚖️ &nbsp;Average vs Maximum", "compare")]:
        section(heading)
        st.image(chart_png(kind, summary, sel.parameter), **STRETCH)

    render_pdf_section(summary, sel, data, k)

    section("📋 &nbsp;Data Information")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("WTG Selection", sel.name)
    m2.metric("Data Points", f"{len(data):,}")
    m3.metric("Sensors", len(temp_cols))
    m4.metric("Latest Record", data[time_col].max().strftime("%d %b %Y %H:%M"))

    section("📐 &nbsp;Summary Statistics")
    numeric = data.select_dtypes("number").columns.tolist()
    chosen = st.multiselect("Select columns", numeric, default=numeric)
    stat_names = ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]
    chosen_stats = st.multiselect("Select statistics", stat_names, default=stat_names)
    if chosen:
        st.dataframe(data[chosen].describe().loc[chosen_stats or stat_names], **STRETCH)
    else:
        st.info("Select at least one column.")

    section("🔍 &nbsp;Raw Filtered Data")
    with st.expander("View filtered raw data"):
        shown = min(len(data), TABLE_ROW_LIMIT)
        st.write(f"Showing **{shown:,}** of **{len(data):,}** records")
        st.dataframe(data.head(shown), hide_index=True, **STRETCH)


# ============================================================
# MAIN
# ============================================================
TABS = {"📊 Overview": render_overview, "📈 Trends": render_trends, "🩺 Data & Health": render_health}


def main():
    render_header()

    nav_col, upload_col = st.columns([2, 1.4])
    active = nav_col.radio("Navigate", list(TABS), horizontal=True, label_visibility="collapsed")
    uploaded = upload_col.file_uploader("Upload WTG CSV", type=["csv"], label_visibility="collapsed")

    df, time_col, temp_cols, source = load_source(uploaded)
    sel = render_filters(df, time_col, temp_cols, source)

    data = apply_filters(df, time_col, sel)
    if data.empty:
        st.warning("No data exists for the selected filters.")
        st.stop()

    TABS[active](data, sel, temp_cols, time_col)      # only the active tab is computed

    md('<div class="app-footer">⚡ WTG Condition Monitoring · Thermal &amp; Bearing Health · '
       'Temperature Analysis &amp; Reporting</div>')


main()
