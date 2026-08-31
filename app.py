import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="WTG Condition Monitoring", page_icon="⚡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding:0 2rem 3rem !important;margin-top:0 !important;background:#e3ebfa;max-width:100% !important;color:#0b1a2b;}
@keyframes shimmer{0%{background-position:-200% 0;}100%{background-position:200% 0;}}
@keyframes gradientShift{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
.topbar{background:linear-gradient(135deg,#0C4A6E,#06B6D4);background-size:300% 300%;animation:gradientShift 10s ease infinite;
padding:14px 28px;display:flex;align-items:center;gap:14px;margin-bottom:22px;border-radius:0 0 14px 14px;
box-shadow:0 10px 30px rgba(12,74,110,.3);border-bottom:4px solid #06B6D4;position:relative;overflow:hidden;}
.topbar::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;
background:linear-gradient(90deg,transparent,rgba(255,255,255,.7),transparent);animation:shimmer 3s infinite;}
.topbar h2{margin:0;font-size:30px;font-weight:800;color:#fff;letter-spacing:-.5px;}
.topbar p{margin:2px 0 0;font-size:13px;color:#ffffff;text-transform:uppercase;letter-spacing:1.2px;font-weight:700;text-shadow:0 1px 3px rgba(0,0,0,.35);}
.topbar-badge{margin-left:auto;display:inline-flex;align-items:center;gap:7px;padding:6px 14px;border-radius:20px;
background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);color:#fff;font-size:12px;font-weight:700;}
.live-dot{width:7px;height:7px;border-radius:50%;background:#31e6a1;box-shadow:0 0 8px #31e6a1;}
.sh{font-size:14px;font-weight:900;color:#062e5c;text-transform:uppercase;letter-spacing:.08em;margin:22px 0 10px;padding:0 0 8px;border-bottom:3px solid #0d47a1;}
.kpi{background:#fff;border-radius:14px;padding:18px 16px;text-align:center;border:1.5px solid #9fb7dd;border-top:5px solid #1b5e20;
box-shadow:0 2px 10px rgba(13,71,161,.12);transition:transform .25s,box-shadow .25s;}
.kpi:hover{transform:translateY(-5px);box-shadow:0 12px 22px rgba(12,74,110,.15);}
.kpi-val{font-size:30px;font-weight:900;line-height:1;color:#062e5c;margin-bottom:6px;}
.kpi-lbl{font-size:11.5px;font-weight:800;color:#37474f;text-transform:uppercase;letter-spacing:.06em;}
.kpi-status{font-size:11.5px;margin-top:6px;font-weight:800;color:#1b5e20;}
.kpi.warning{border-top-color:#a83e00;} .kpi.warning .kpi-status{color:#a83e00;}
.kpi.danger{border-top-color:#a30000;} .kpi.danger .kpi-status{color:#a30000;}
.status-box{padding:13px 18px;border-radius:10px;background:#d7f0e0;border:2px solid #2e7d32;color:#0d3d13;font-weight:800;margin-bottom:14px;}
.status-box.warning{background:#ffedb3;border-color:#a83e00;color:#7a2900;}
.status-box.danger{background:#fbd0dd;border-color:#a30000;color:#6b0030;}
.highlight-box{padding:16px 20px;border-radius:12px;background:#fbd0dd;border:2px solid #a30000;margin-bottom:14px;}
.hb-sensor{font-size:13.5px;color:#6b0030;font-weight:800;}
.hb-val{font-size:24px;color:#062e5c;font-weight:900;}
.hb-meta{font-size:12.5px;color:#2b3d4a;font-weight:600;margin-top:3px;}
.detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:8px;}
.detail-item{background:#fff;border:1.5px solid #9fb7dd;border-left:4px solid #1b5e20;border-radius:10px;padding:9px 13px;}
.detail-item.warning{border-left-color:#a83e00;} .detail-item.danger{border-left-color:#a30000;}
.detail-item.is-max{background:#fbd0dd;border-color:#a30000;}
.di-name{font-size:10.5px;color:#37474f;font-weight:800;text-transform:uppercase;}
.di-val{font-size:18px;color:#062e5c;font-weight:900;margin-top:3px;}
.di-val span{font-size:11px;color:#455a64;margin-left:2px;font-weight:700;}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden;border:2px solid #6f93cf !important;}
div[data-baseweb="select"]>div{background:#fff !important;border:1.8px solid #6f93cf !important;border-radius:10px !important;color:#0b1a2b !important;}
div[data-testid="stRadio"] > label{display:none;}
div[data-testid="stRadio"] > div[role="radiogroup"]{flex-direction:row;gap:8px;background:#fff;padding:8px;
border-radius:18px;border:1.5px solid #9fb7dd;box-shadow:0 6px 18px rgba(13,71,161,.10);margin-bottom:20px;width:fit-content;}
div[data-testid="stRadio"] label[data-baseweb="radio"]{padding:11px 28px;border-radius:12px;transition:all .25s ease;margin:0 !important;}
div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child{display:none;}
div[data-testid="stRadio"] label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p{font-weight:800 !important;
font-size:14.5px !important;color:#062e5c !important;letter-spacing:.02em;}
div[data-testid="stRadio"] label[data-baseweb="radio"]:hover{background:#e3ebfa;}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked){background:linear-gradient(135deg,#0C4A6E,#06B6D4);
box-shadow:0 6px 16px rgba(6,182,212,.4);}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) div[data-testid="stMarkdownContainer"] p{color:#fff !important;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="topbar"><div><h2>⚡ WTG Condition Monitoring</h2>
<p>Wind Turbine Generator · Thermal & Bearing Health</p></div>
<span class="topbar-badge"><span class="live-dot"></span>MONITORING ACTIVE</span></div>
""", unsafe_allow_html=True)

DEFAULT_FILE = "WTG.csv"

def clean_column_name(col):
    col = str(col).strip()
    col = re.sub(r"\(\s*[^\w\s]{1,4}C?\)", "(°C)", col)
    return re.sub(r"\s{2,}", " ", col).strip()

def find_column(df, keywords):
    for col in df.columns:
        cl = col.lower()
        if all(k.lower() in cl for k in keywords):
            return col
    return None

def temperature_status(value):
    if pd.isna(value):
        return "NO DATA", "danger"
    if value >= 90:
        return "HIGH", "danger"
    if value >= 75:
        return "WARNING", "warning"
    return "NORMAL", "normal"

def create_kpi(label, value, unit="°C", icon="●"):
    status, css = temperature_status(value)
    css = "" if css == "normal" else css
    status_text = {"": "● Normal", "warning": "▲ Monitor", "danger": "● High"}[css]
    return f"""<div class="kpi {css}"><div class="kpi-lbl">{icon} &nbsp;{label}</div>
    <div class="kpi-val">{value:.1f}<span style="font-size:14px;color:#78909c">{unit}</span></div>
    <div class="kpi-status">{status_text}</div></div>"""

nav_col, upload_col = st.columns([2, 1.4])
with nav_col:
    active_tab = st.radio("Navigate", ["📊 Overview", "📈 Trends", "🩺 Data & Health"], horizontal=True, label_visibility="collapsed")
with upload_col:
    uploaded_file = st.file_uploader("Upload WTG CSV", type=["csv"], label_visibility="collapsed")

# ── CONTROLS (moved from sidebar) ─────────────────────────────────────────
st.markdown('<div class="sh">🔍 &nbsp;Filters & Data Source</div>', unsafe_allow_html=True)

try:
    src = uploaded_file if uploaded_file is not None else DEFAULT_FILE
    if uploaded_file is None and not Path(DEFAULT_FILE).exists():
        st.error(f"❌ `{DEFAULT_FILE}` not found. Upload a WTG CSV above.")
        st.stop()
    try:
        df = pd.read_csv(src, encoding="utf-8-sig")
    except UnicodeDecodeError:
        if uploaded_file is not None:
            uploaded_file.seek(0)
        df = pd.read_csv(src, encoding="latin1")
except Exception as e:
    st.error(f"Unable to read CSV file: {e}")
    st.stop()

df.columns = [clean_column_name(c) for c in df.columns]
time_column = find_column(df, ["time"])
if time_column is None:
    st.error("❌ No `Time` column found in the CSV.")
    st.stop()

df[time_column] = pd.to_datetime(df[time_column], errors="coerce")
df = df.dropna(subset=[time_column]).sort_values(time_column)
dedup_subset = ["Name", time_column] if "Name" in df.columns else [time_column]
df = df.drop_duplicates(subset=dedup_subset, keep="last")

temperature_columns = [c for c in df.columns if "temperature" in c.lower() or "temp" in c.lower()]
for c in temperature_columns:
    if df[c].dtype == object:
        df[c] = df[c].astype(str).str.replace(",", ".", regex=False).str.extract(r"(-?\d+\.?\d*)")[0]
    df[c] = pd.to_numeric(df[c], errors="coerce")

if not temperature_columns:
    st.error("❌ No temperature columns detected.")
    st.stop()
if df[temperature_columns].dropna(how="all").empty:
    st.error("❌ All temperature columns are empty/non-numeric after parsing.")
    with st.expander("Detected columns (debug)"):
        st.write(list(df.columns))
    st.stop()


min_time, max_time = df[time_column].min(), df[time_column].max()
c1, c2, c3, c4 = st.columns([1.3, 1.3, 1, 1])
with c1:
    if "Name" in df.columns:
        names = ["All"] + sorted(df["Name"].dropna().unique().tolist())
        selected_name = st.selectbox("WTG Name", names)
        if selected_name != "All":
            df = df[df["Name"] == selected_name]
    else:
        selected_name = "Unknown"
with c2:
    selected_parameter = st.selectbox("Primary trend", temperature_columns)
with c3:
    start_date = st.date_input("Start date", value=min_time.date(), min_value=min_time.date(), max_value=max_time.date())
with c4:
    end_date = st.date_input("End date", value=max_time.date(), min_value=min_time.date(), max_value=max_time.date())

if start_date > end_date:
    st.error("❌ Start date must be before end date.")
    st.stop()

time_range = (pd.Timestamp(start_date), pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
filtered_df = df[(df[time_column] >= time_range[0]) & (df[time_column] <= time_range[1])].copy()
if filtered_df.empty:
    st.warning("No data in the selected time range.")
    st.stop()



def last_valid(col):
    s = filtered_df[col].dropna()
    return s.iloc[-1] if not s.empty else float("nan")

latest_row = filtered_df.iloc[-1]

def smooth(s, max_points=600):
    if len(s) <= max_points:
        return s
    span = s[time_column].max() - s[time_column].min()
    rule = max(pd.Timedelta(seconds=1), span / max_points)
    return s.set_index(time_column).resample(rule).mean().dropna().reset_index()

if active_tab == "📊 Overview":
    # ── OVERALL STATUS + MAX-TEMP HIGHLIGHT ────────────────────────────────
    latest_readings = {c: last_valid(c) for c in temperature_columns}
    latest_readings = {k: v for k, v in latest_readings.items() if pd.notna(v)}
    max_sensor, max_value = (max(latest_readings, key=latest_readings.get), None) if latest_readings else (None, None)
    if max_sensor:
        max_value = latest_readings[max_sensor]
    overall_status, overall_css = temperature_status(max_value if max_sensor else float("nan"))
    box_css = "" if overall_css == "normal" else overall_css
    box_msg = {
        "": "🟢 <b>WTG HEALTH STATUS: NORMAL</b><br>All monitored temperatures are within range.",
        "warning": "🟡 <b>WTG HEALTH STATUS: WARNING</b><br>One or more temperatures require attention.",
        "danger": "🔴 <b>WTG HEALTH STATUS: HIGH TEMPERATURE</b><br>One or more temperatures are above threshold.",
    }[box_css]
    st.markdown(f'<div class="status-box {box_css}">{box_msg}</div>', unsafe_allow_html=True)

    if max_sensor:
        detail_items = ""
        for c in temperature_columns:
            v = latest_row[c]
            if pd.isna(v):
                continue
            _, css_c = temperature_status(v)
            css_c = "" if css_c == "normal" else css_c
            is_max = "is-max" if c == max_sensor else ""
            detail_items += f'<div class="detail-item {css_c} {is_max}"><div class="di-name">{c}</div><div class="di-val">{v:.1f}<span>°C</span></div></div>'
        st.markdown(f"""
        <div class="highlight-box"><div class="hb-sensor">🌡️ Highest Current Reading — {selected_name}</div>
        <div class="hb-val">{max_value:.2f} °C <span style="font-size:13px;color:#607d8b;">({max_sensor})</span></div>
        <div class="hb-meta">Recorded at {latest_row[time_column].strftime('%d %b %Y %H:%M')} · Status: {overall_status}</div></div>
        <div class="sh">📇 &nbsp;Full Sensor Snapshot (Latest Reading)</div>
        <div class="detail-grid">{detail_items}</div>
        """, unsafe_allow_html=True)

    # ── KPIs ────────────────────────────────────────────────────────────────
    st.markdown('<div class="sh">📊 &nbsp;Key Performance Indicators</div>', unsafe_allow_html=True)
    kpi_columns = [
        ("Generator DE Bearing", find_column(df, ["generator", "drive-end", "bearing"]), "🔩"),
        ("Generator NDE Bearing", find_column(df, ["generator", "non-drive-end", "bearing"]), "🔩"),
        ("Gearbox DE Bearing", find_column(df, ["gearbox", "de", "bearing"]), "⚙️"),
        ("Gearbox NDE Bearing", find_column(df, ["gearbox", "nde", "bearing"]), "⚙️"),
        ("Gearbox Oil", find_column(df, ["gearbox", "oil"]), "🛢️"),
        ("Main Bearing", find_column(df, ["main", "bearing"]), "🔄"),
    ]
    valid_kpis = [k for k in kpi_columns if k[1] is not None]
    kcols = st.columns(3)
    for i, (label, column, icon) in enumerate(valid_kpis):
        value = last_valid(column)
        value = 0 if pd.isna(value) else value
        with kcols[i % 3]:
            st.markdown(create_kpi(label, value, "°C", icon), unsafe_allow_html=True)


if active_tab == "📈 Trends":
    # ── MAIN TREND ──────────────────────────────────────────────────────────
    st.markdown('<div class="sh">📈 &nbsp;Temperature Trend</div>', unsafe_allow_html=True)
    plot_df = smooth(filtered_df[[time_column, selected_parameter]].dropna())
    if plot_df.empty:
        st.warning(f"No numeric data for '{selected_parameter}' in this selection.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=plot_df[time_column], y=plot_df[selected_parameter], mode="lines", name=selected_parameter,
            line=dict(color="#0d47a1", width=2), fill="tozeroy", fillcolor="rgba(6,182,212,0.10)",
            hovertemplate="<b>%{y:.2f} °C</b><br>%{x}<extra></extra>"))
        fig.add_hline(y=75, line_dash="dash", line_color="#bf360c", annotation_text="Warning 75°C", annotation_position="top right")
        fig.add_hline(y=90, line_dash="dash", line_color="#c62828", annotation_text="High 90°C", annotation_position="top right")
        fig.update_layout(height=500, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fff",
            font=dict(color="#1a2733", family="Inter", size=13), margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
            xaxis=dict(title="Time", showgrid=True, gridcolor="#c9d6e8"),
            yaxis=dict(title="Temperature (°C)", showgrid=True, gridcolor="#c9d6e8"))
        st.plotly_chart(fig, use_container_width=True, key="main_trend_chart")

    # ── ALL SENSOR TRENDS ──────────────────────────────────────────────────
    st.markdown('<div class="sh">🌡️ &nbsp;All Temperature Sensors</div>', unsafe_allow_html=True)
    colors = ["#0d47a1", "#06B6D4", "#6a1b9a", "#bf360c", "#c62828", "#2e7d32", "#0288d1", "#8e24aa", "#e64a19", "#fbc02d"]
    fig_all = go.Figure()
    any_data = False
    for i, col in enumerate(temperature_columns):
        s = smooth(filtered_df[[time_column, col]].dropna())
        if s.empty:
            continue
        any_data = True
        fig_all.add_trace(go.Scatter(x=s[time_column], y=s[col], mode="lines", name=col,
            line=dict(color=colors[i % len(colors)], width=1.5), hovertemplate=f"<b>{col}</b><br>%{{y:.2f}} °C<extra></extra>"))
    if not any_data:
        st.warning("No numeric sensor data available for this selection.")
    else:
        fig_all.update_layout(height=550, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fff",
            font=dict(color="#1a2733", family="Inter", size=13), margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
            xaxis=dict(title="Time", showgrid=True, gridcolor="#c9d6e8"),
            yaxis=dict(title="Temperature (°C)", showgrid=True, gridcolor="#c9d6e8"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
        st.plotly_chart(fig_all, use_container_width=True, key="all_sensors_chart")


if active_tab == "🩺 Data & Health":
    # ── SENSOR HEALTH TABLE ─────────────────────────────────────────────────
    st.markdown('<div class="sh">🩺 &nbsp;Sensor Health Overview</div>', unsafe_allow_html=True)
    health_data = []
    for col in temperature_columns:
        series = filtered_df[col].dropna()
        if series.empty:
            continue
        latest = series.iloc[-1]
        status, _ = temperature_status(latest)
        health_data.append({"Sensor": col, "Latest (°C)": round(latest, 2), "Average (°C)": round(series.mean(), 2),
            "Minimum (°C)": round(series.min(), 2), "Maximum (°C)": round(series.max(), 2), "Status": status})
    if health_data:
        health_df = pd.DataFrame(health_data).sort_values("Latest (°C)", ascending=False).reset_index(drop=True)
        st.dataframe(health_df, use_container_width=True, hide_index=True)
    else:
        st.info("No valid sensor readings in the selected time range.")


    # ──  ────────────────────────────────────────────────────
    df_plot = pd.DataFrame({
    "Columns": df.select_dtypes(include="number").columns,
    "Max": df.select_dtypes(include="number").max().values,
    "Min": df.select_dtypes(include="number").min().values,
    "Average": df.select_dtypes(include="number").mean().values
})
    fig, axes = plt.subplots(3, 1, figsize=(20, 30))

    stats = ["Max", "Average", "Min"]
    colors = ["#E76F51", "#2A9D8F", "#457B9D"]
    
    for ax, stat, color in zip(axes, stats, colors):
    
        temp = df_plot.sort_values(stat, ascending=False)
    
        sns.barplot(
            data=temp,
            x="Columns",
            y=stat,
            color=color,
            ax=ax
        )
    
        # Show values on top of bars
        for container in ax.containers:
            ax.bar_label(
                container,
                fmt="%.2f",
                padding=3,
                fontsize=15,
                rotation=90
            )
    
        ax.set_title(
            f"{stat} Values",
            fontsize=26,
            fontweight="bold",
            pad=15
        )
    
        ax.set_xlabel("Columns", fontsize=12)
        ax.set_ylabel(stat, fontsize=12)
    
        # Rotate column names
        ax.tick_params(axis="x", rotation=90, labelsize=12)
    
        # Grid
        ax.grid(
            axis="y",
            linestyle="--",
            alpha=0.3
        )
    
        sns.despine(ax=ax)
    
    plt.tight_layout()
    plt.show()
    # ── DATA INFORMATION ────────────────────────────────────────────────────
    st.markdown('<div class="sh">📋 &nbsp;Data Information</div>', unsafe_allow_html=True)
    info1, info2, info3, info4 = st.columns(4)
    info1.metric("WTG Name", str(selected_name))
    info2.metric("Data Points", f"{len(filtered_df):,}")
    info3.metric("Sensors", len(temperature_columns))
    info4.metric("Latest Record", latest_row[time_column].strftime("%d %b %Y %H:%M"))

    # ── SUMMARY STATISTICS ───────────────────────────────────────────────────
    st.markdown('<div class="sh">📐 &nbsp;Summary Statistics</div>', unsafe_allow_html=True)
    selected_cols = st.multiselect("Select columns", options=df.columns.tolist(),
        default=df.select_dtypes(include="number").columns.tolist())
    all_stats = ["count", "mean", "std", "min", "25%", "50%", "75%", "max", "range"]
    selected_stats = st.multiselect("Select statistics", options=all_stats, default=all_stats)
    include_categorical = st.checkbox("Include categorical columns", value=False)

    if selected_cols:
        desc = df[selected_cols].describe(include="all") if include_categorical else df[selected_cols].describe()
        if "max" in desc.index and "min" in desc.index:
            desc.loc["Difference"] = desc.loc["max"] - desc.loc["mean"]
        available_stats = [s for s in selected_stats if s in desc.index]
        if available_stats:
            desc = desc.loc[available_stats]
        st.dataframe(desc)
    else:
        st.info("Select at least one column to see the summary.")
