from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="UAC System Capacity & Care Load Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- File paths ----------
BASE = Path(__file__).parent

FILES = {
    "data": BASE / "UAC_System_Capacity_Complete_Analysis.csv",
    "kpi": BASE / "UAC_System_Capacity_KPI_Summary.csv",
    "yearly": BASE / "UAC_Yearly_Capacity_Summary.csv",
    "high_load": BASE / "UAC_Top_High_Load_Periods.csv",
    "stress": BASE / "UAC_Prolonged_High_Load_Windows.csv",
    "relief": BASE / "UAC_Capacity_Relief_Periods.csv",
    "forecast": BASE / "UAC_System_Load_Forecast.csv",
    "findings": BASE / "UAC_Executive_Findings.csv",
}

@st.cache_data
def load_csv(path):
    return pd.read_csv(path)

missing = [str(p.name) for p in FILES.values() if not p.exists()]
if missing:
    st.error("The following required files are missing from the project folder:")
    for name in missing:
        st.write(f"- {name}")
    st.stop()

data = load_csv(FILES["data"])
kpi = load_csv(FILES["kpi"])
yearly = load_csv(FILES["yearly"])
high_load = load_csv(FILES["high_load"])
stress = load_csv(FILES["stress"])
relief = load_csv(FILES["relief"])
forecast = load_csv(FILES["forecast"])
findings = load_csv(FILES["findings"])

data["date"] = pd.to_datetime(data["date"], errors="coerce")
high_load["date"] = pd.to_datetime(high_load["date"], errors="coerce")
relief["date"] = pd.to_datetime(relief["date"], errors="coerce")
stress["start_date"] = pd.to_datetime(stress["start_date"], errors="coerce")
stress["end_date"] = pd.to_datetime(stress["end_date"], errors="coerce")
forecast["date"] = pd.to_datetime(forecast["date"], errors="coerce")
data = data.sort_values("date")

# ---------- Helpers ----------
def fmt_num(x):
    return f"{x:,.0f}" if pd.notna(x) else "N/A"

def get_metric_mean(name):
    row = kpi[kpi["KPI"].astype(str).str.strip().eq(name)]
    if row.empty:
        return None
    return float(row.iloc[0]["Mean"])

# ---------- Sidebar ----------
st.sidebar.title("Dashboard Controls")

min_date = data["date"].min().date()
max_date = data["date"].max().date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
else:
    start_date = pd.Timestamp(min_date)
    end_date = pd.Timestamp(max_date)

granularity = st.sidebar.selectbox(
    "Time granularity",
    ["Daily", "Weekly", "Monthly"],
)

metric = st.sidebar.selectbox(
    "Metric",
    [
        "Total system load",
        "Net intake pressure",
        "HHS care load",
        "CBP custody",
        "Care load volatility",
    ],
)

filtered = data[(data["date"] >= start_date) & (data["date"] <= end_date)].copy()

if filtered.empty:
    st.warning("No records exist for the selected date range.")
    st.stop()

# ---------- Header ----------
st.title("UAC System Capacity & Care Load Analytics")
st.caption(
    "Analytical dashboard for monitoring system load, capacity pressure, "
    "inflow/outflow balance, stress periods, relief periods, and forecasted load."
)

# ---------- KPI cards ----------
avg_load = filtered["total_children_under_care"].mean()
peak_row = filtered.loc[filtered["total_children_under_care"].idxmax()]
low_row = filtered.loc[filtered["total_children_under_care"].idxmin()]
avg_net = filtered["net_intake_kpi"].mean()

high_periods = int(filtered["high_load_flag"].fillna(False).astype(bool).sum()) if "high_load_flag" in filtered else int((filtered["load_level"].isin(["High", "Very High"])).sum())
very_high = int((filtered["load_level"] == "Very High").sum())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Average system load", fmt_num(avg_load))
c2.metric("Peak system load", fmt_num(peak_row["total_children_under_care"]))
c3.metric("Lowest system load", fmt_num(low_row["total_children_under_care"]))
c4.metric("Avg. net intake pressure", f"{avg_net:,.2f}")
c5.metric("High-load periods", f"{high_periods:,}")
c6.metric("Very-high periods", f"{very_high:,}")

st.divider()

# ---------- Executive overview ----------
st.header("1. Executive Overview")

peak_date = peak_row["date"].strftime("%d %b %Y")
low_date = low_row["date"].strftime("%d %b %Y")

col1, col2 = st.columns(2)
with col1:
    st.info(
        f"**Peak recorded system load:** {fmt_num(peak_row['total_children_under_care'])} "
        f"children on {peak_date}. "
        f"HHS care accounted for {fmt_num(peak_row['children_in_hhs_care'])} children."
    )
with col2:
    st.success(
        f"**Lowest recorded system load:** {fmt_num(low_row['total_children_under_care'])} "
        f"children on {low_date}. "
        f"HHS care accounted for {fmt_num(low_row['children_in_hhs_care'])} children."
    )

with st.expander("Key findings from the completed analysis"):
    for _, row in findings.iterrows():
        st.write(f"**{row['Finding']}:** {row['Value']}")

# ---------- System load ----------
st.header("2. System Load Overview")

plot_data = filtered.copy()
if granularity == "Weekly":
    plot_data = (
        plot_data.set_index("date")
        .resample("W")
        .agg({
            "total_children_under_care": "mean",
            "system_load_7day_avg": "mean",
            "system_load_14day_avg": "mean",
        })
        .reset_index()
    )
elif granularity == "Monthly":
    plot_data = (
        plot_data.set_index("date")
        .resample("ME")
        .agg({
            "total_children_under_care": "mean",
            "system_load_7day_avg": "mean",
            "system_load_14day_avg": "mean",
        })
        .reset_index()
    )

p90 = data["total_children_under_care"].quantile(0.90)

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=plot_data["date"], y=plot_data["total_children_under_care"],
    mode="lines", name="Total system load"
))
fig.add_trace(go.Scatter(
    x=plot_data["date"], y=plot_data["system_load_7day_avg"],
    mode="lines", name="7-period average"
))
fig.add_trace(go.Scatter(
    x=plot_data["date"], y=plot_data["system_load_14day_avg"],
    mode="lines", name="14-period average"
))
fig.add_hline(
    y=p90, line_dash="dash",
    annotation_text=f"90th percentile: {p90:,.0f}"
)
fig.update_layout(
    title="Total UAC System Load Over Time",
    xaxis_title="Date",
    yaxis_title="Children under care",
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# ---------- CBP vs HHS ----------
st.header("3. CBP vs HHS Care Load")

cbp_hhs = filtered[[
    "date", "children_in_cbp_custody", "children_in_hhs_care"
]].copy()

fig2 = px.line(
    cbp_hhs,
    x="date",
    y=["children_in_cbp_custody", "children_in_hhs_care"],
    labels={"value": "Children", "variable": "Care location"},
    title="CBP Custody vs HHS Care",
)
fig2.update_layout(hovermode="x unified")
st.plotly_chart(fig2, use_container_width=True)

# ---------- Net intake ----------
st.header("4. Net Intake & Backlog Pressure")

fig3 = go.Figure()
fig3.add_trace(go.Scatter(
    x=filtered["date"], y=filtered["net_intake_kpi"],
    mode="lines", name="Net intake pressure"
))
fig3.add_trace(go.Scatter(
    x=filtered["date"], y=filtered["net_intake_7day_avg"],
    mode="lines", name="7-period net intake average"
))
fig3.add_trace(go.Scatter(
    x=filtered["date"], y=filtered["backlog_accumulation_rate"],
    mode="lines", name="Backlog accumulation rate"
))
fig3.add_hline(y=0, line_dash="dash")
fig3.update_layout(
    title="Net Intake Pressure and Backlog Accumulation",
    xaxis_title="Date",
    yaxis_title="Children / analytical rate",
    hovermode="x unified",
)
st.plotly_chart(fig3, use_container_width=True)

st.caption(
    "Negative net intake pressure indicates that the measured outflow exceeded "
    "the corresponding inflow measure for that reporting period. It is an "
    "operational flow indicator, not a causal measure."
)

# ---------- Capacity classification ----------
st.header("5. Capacity Classification")

counts = (
    filtered["load_level"]
    .value_counts()
    .reindex(["Normal", "Elevated", "High", "Very High"], fill_value=0)
    .reset_index()
)
counts.columns = ["Load level", "Periods"]

fig4 = px.bar(
    counts,
    x="Load level",
    y="Periods",
    title="Distribution of Capacity Load Levels",
    text="Periods",
)
fig4.update_traces(textposition="outside")
st.plotly_chart(fig4, use_container_width=True)

q75 = data["total_children_under_care"].quantile(0.75)
q90 = data["total_children_under_care"].quantile(0.90)
q95 = data["total_children_under_care"].quantile(0.95)

a, b, c = st.columns(3)
a.metric("75th percentile", f"{q75:,.1f}")
b.metric("90th percentile", f"{q90:,.1f}")
c.metric("95th percentile", f"{q95:,.1f}")

# ---------- High-load periods ----------
st.header("6. High-Load / Stress Periods")

st.dataframe(
    high_load.sort_values("total_children_under_care", ascending=False),
    use_container_width=True,
    hide_index=True,
)

if not high_load.empty:
    fig5 = px.bar(
        high_load.sort_values("total_children_under_care"),
        x="total_children_under_care",
        y="date",
        color="load_level",
        orientation="h",
        title="Top High-Load Reporting Periods",
        labels={"total_children_under_care": "Children under care", "date": "Date"},
    )
    st.plotly_chart(fig5, use_container_width=True)

# ---------- Prolonged stress ----------
st.header("7. Prolonged High-Load Windows")

if stress.empty:
    st.info("No prolonged high-load windows are present in the exported analysis.")
else:
    st.dataframe(stress, use_container_width=True, hide_index=True)

# ---------- Relief ----------
st.header("8. Capacity Relief Periods")

st.dataframe(
    relief.sort_values("total_children_under_care"),
    use_container_width=True,
    hide_index=True,
)

# ---------- Yearly ----------
st.header("9. Yearly Capacity Analysis")

fig6 = px.bar(
    yearly,
    x="year",
    y=["average_load", "peak_load"],
    barmode="group",
    title="Average and Peak System Load by Year",
    labels={"value": "Children", "variable": "Measure"},
)
st.plotly_chart(fig6, use_container_width=True)

st.dataframe(yearly, use_container_width=True, hide_index=True)

# ---------- Forecast ----------
st.header("10. System Load Forecast")

historical_tail = data[["date", "total_children_under_care"]].copy()

fig7 = go.Figure()
fig7.add_trace(go.Scatter(
    x=historical_tail["date"],
    y=historical_tail["total_children_under_care"],
    mode="lines",
    name="Historical system load",
))
fig7.add_trace(go.Scatter(
    x=forecast["date"],
    y=forecast["forecast_system_load"],
    mode="lines+markers",
    name="Forecast system load",
))
fig7.add_hline(
    y=p90, line_dash="dash",
    annotation_text=f"90th percentile: {p90:,.0f}"
)
fig7.update_layout(
    title="Historical System Load and Forecast",
    xaxis_title="Date",
    yaxis_title="Children under care",
    hovermode="x unified",
)
st.plotly_chart(fig7, use_container_width=True)

st.caption(
    "The forecast is an analytical projection based on the supplied project "
    "forecast file. It should not be interpreted as an official government forecast."
)

# ---------- Downloads ----------
st.header("11. Data Downloads")

download_files = [
    ("Complete analysis", FILES["data"]),
    ("KPI summary", FILES["kpi"]),
    ("Yearly capacity summary", FILES["yearly"]),
    ("High-load periods", FILES["high_load"]),
    ("Prolonged stress windows", FILES["stress"]),
    ("Relief periods", FILES["relief"]),
    ("System load forecast", FILES["forecast"]),
    ("Executive findings", FILES["findings"]),
]

for label, path in download_files:
    st.download_button(
        label=f"Download {label}",
        data=path.read_bytes(),
        file_name=path.name,
        mime="text/csv",
    )

# ---------- Methodology ----------
st.header("12. Methodology")

with st.expander("View KPI definitions and analytical methodology"):
    st.markdown("""
**Total System Load**  
Combined children in CBP custody and HHS care.

**Net Intake Pressure**  
The project's calculated flow-balance indicator comparing the relevant
HHS inflow and discharge/outflow measures.

**Care Load Growth Rate**  
Day-over-day percentage change in system care load.

**Rolling averages**  
7-period and 14-period averages are used to smooth short-term variation
and make sustained changes easier to identify.

**Capacity classification**  
The dashboard uses the load classifications already produced in the
completed analysis rather than creating a new classification.

**High-load thresholds**  
The dashboard displays the 75th, 90th, and 95th percentile system-load
thresholds calculated from the supplied analytical dataset.

**Forecast**  
The dashboard displays the forecast already generated and exported by
the project analysis.
""")

st.caption(
    "Source: completed UAC System Capacity & Care Load Analytics project files."
)
