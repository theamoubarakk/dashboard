# ---------------------------------------------------------------------------
# Single-file Streamlit Forecasting Dashboard (Forecasts only)
# - Overview
# - Category Detail
# - Diagnostics (residuals)
# - Scenario Planner (simple uplifts for seasonal months)
# ---------------------------------------------------------------------------
import io
from typing import Optional, Tuple
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ----------------------------- CONFIG ---------------------------------------
st.set_page_config(page_title="Forecast Dashboard", layout="wide")

# ----------------------------- DATA -----------------------------------------
@st.cache_data(show_spinner=False)
def load_long_forecasts(path: str = "data/forecasts_long.parquet") -> pd.DataFrame:
    """
    Expects long-format table with at least:
      category, subcategory, ds, [y], model, yhat, yhat_lower, yhat_upper,
      source ('history'|'forecast'), scale_factor (float)
    """
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    df["ds"] = pd.to_datetime(df["ds"])
    # Fill defaults if missing
    if "source" not in df.columns:
        df["source"] = np.where(df["yhat"].notna(), "forecast", "history")
    if "scale_factor" not in df.columns:
        df["scale_factor"] = 1.0
    return df

def filter_df(
    df: pd.DataFrame,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    year: Optional[int] = None,
) -> pd.DataFrame:
    out = df.copy()
    if category and category != "All":
        out = out[out["category"] == category]
    if subcategory and subcategory != "All":
        out = out[out["subcategory"] == subcategory]
    if year:
        out = out[out["ds"].dt.year == year]
    return out.sort_values("ds")

def apply_display_scaling(df: pd.DataFrame, use_scaling: bool) -> pd.DataFrame:
    out = df.copy()
    sf = out["scale_factor"].astype(float).fillna(1.0)
    for col in ["y", "yhat", "yhat_lower", "yhat_upper"]:
        if col in out.columns:
            if use_scaling:
                out[col] = out[col] * sf
            # else keep raw values (no-op)
    return out

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

# ----------------------------- KPIs -----------------------------------------
def compute_kpis(fdf: pd.DataFrame):
    f = fdf[(fdf["source"] == "forecast") & fdf["yhat"].notna()].copy()
    if f.empty:
        return 0.0, "-", 0.0, 0.0
    f["ci_width"] = (f["yhat_upper"] - f["yhat_lower"]).abs()
    total = float(f["yhat"].sum())
    idxmax = f["yhat"].idxmax()
    peak_month = f.loc[idxmax, "ds"].strftime("%b %Y")
    peak_value = float(f.loc[idxmax, "yhat"])
    avg_ci = float(f["ci_width"].mean())
    return total, peak_month, peak_value, avg_ci

# ----------------------------- PLOTS ----------------------------------------
def plot_history_forecast(
    df: pd.DataFrame,
    title: str,
    annotate_peaks: bool = True,
    band_months: Optional[Tuple[int, int]] = None,  # e.g., (10,10) to shade Oct
) -> go.Figure:
    hist = df[(df["source"] == "history") & df["y"].notna()].copy()
    fcst = df[(df["source"] == "forecast") & df["yhat"].notna()].copy()

    fig = go.Figure()

    # CI band
    if not fcst.empty:
        fig.add_traces([
            go.Scatter(x=fcst["ds"], y=fcst["yhat_upper"],
                       line=dict(width=0), showlegend=False, hoverinfo="skip"),
            go.Scatter(x=fcst["ds"], y=fcst["yhat_lower"],
                       line=dict(width=0), fill="tonexty",
                       fillcolor="rgba(43,108,176,0.15)",
                       showlegend=False, hoverinfo="skip")
        ])

    # History
    if not hist.empty:
        fig.add_trace(go.Scatter(
            x=hist["ds"], y=hist["y"],
            mode="lines+markers", name="Historical", line=dict(width=2)
        ))

    # Forecast mean
    if not fcst.empty:
        fig.add_trace(go.Scatter(
            x=fcst["ds"], y=fcst["yhat"], mode="lines",
            name="Forecast", line=dict(width=3)
        ))

    # Optional band (season highlight)
    if band_months:
        m1, m2 = band_months
        years = sorted({d.year for d in df["ds"]})
        for y in years:
            x0 = pd.Timestamp(year=y, month=m1, day=1)
            x1 = pd.Timestamp(year=y, month=m2, day=28) + pd.offsets.MonthEnd(0)
            fig.add_vrect(x0=x0, x1=x1, fillcolor="orange", opacity=0.08, line_width=0)

    # Peak annotation
    if annotate_peaks and not fcst.empty:
        r = fcst.loc[fcst["yhat"].idxmax()]
        fig.add_annotation(x=r["ds"], y=r["yhat"], text=f"Peak: {r['yhat']:.0f}",
                           showarrow=True, arrowhead=2, ax=0, ay=-40)

    fig.update_layout(
        title=title,
        margin=dict(l=40, r=20, t=60, b=40),
        xaxis_title="Date",
        yaxis_title="Quantity Sold",
        template="plotly_white",
        hovermode="x unified"
    )
    return fig

# ----------------------------- PAGES ----------------------------------------
def page_overview(df: pd.DataFrame):
    st.title("Forecast Overview")

    with st.sidebar:
        st.markdown("### Filters")
        category = st.selectbox("Category", ["All"] + sorted(df["category"].unique().tolist()))
        subcats = ["All"] + sorted(df.loc[df["category"].eq(category) | (category=="All"), "subcategory"].unique().tolist())
        subcategory = st.selectbox("Subcategory", subcats)
        # show all years available; you likely want 2025 for forecast table
        years = sorted(df["ds"].dt.year.unique().tolist())
        year = st.selectbox("Year", years, index=len(years)-1 if years else 0)
        use_scaling = st.checkbox("Apply display scaling", value=True)
        annotate = st.checkbox("Annotate peak", value=True)

    f = filter_df(df, category=category, subcategory=subcategory, year=year)
    f = apply_display_scaling(f, use_scaling)

    if f.empty:
        st.info("No data for the selected filters.")
        return

    total, peak_month, peak_value, avg_ci = compute_kpis(f)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Forecast (selected year)", f"{total:,.0f}")
    c2.metric("Peak Month", peak_month)
    c3.metric("Peak Value", f"{peak_value:,.0f}")
    c4.metric("Avg CI Width", f"{avg_ci:,.0f}")

    title = f"History & Forecast — {subcategory if subcategory!='All' else category}"
    band = (10,10) if (category=="Halloween" or subcategory=="Costume") else None
    st.plotly_chart(plot_history_forecast(f, title, annotate_peaks=annotate, band_months=band),
                    use_container_width=True)

    st.subheader("Forecast Table")
    tbl_cols = [c for c in ["category","subcategory","ds","yhat","yhat_lower","yhat_upper","model","scale_factor","source"] if c in f.columns]
    ftbl = f[(f["source"]=="forecast") & (f["ds"].dt.year==year)][tbl_cols].round(2)
    st.dataframe(ftbl, use_container_width=True)
    st.download_button("Download forecast (CSV)", data=df_to_csv_bytes(ftbl),
                       file_name="forecast_selected.csv", mime="text/csv")

def page_category_detail(df: pd.DataFrame):
    st.title("Category Detail")

    with st.sidebar:
        category = st.selectbox("Category", sorted(df["category"].unique()))
        subcats = sorted(df.loc[df["category"].eq(category), "subcategory"].unique())
        subcategory = st.selectbox("Subcategory", subcats)
        use_scaling = st.checkbox("Apply display scaling", value=True)
        annotate = st.checkbox("Annotate peak", value=True)

    f = filter_df(df, category=category, subcategory=subcategory)
    f = apply_display_scaling(f, use_scaling)

    left, right = st.columns([2,1], gap="large")

    with left:
        band = (10,10) if (category=="Halloween" or subcategory=="Costume") else None
        st.plotly_chart(
            plot_history_forecast(f, f"{category} — {subcategory}", annotate_peaks=annotate, band_months=band),
            use_container_width=True
        )

    with right:
        st.markdown("#### Model Settings")
        model = f["model"].dropna().iloc[0] if "model" in f.columns and not f["model"].dropna().empty else "—"
        st.write("**Model:**", model)
        if str(model).upper().startswith("SARIMA"):
            st.caption("SARIMA applied to capture strong calendar-driven seasonality (e.g., Halloween).")
        elif str(model).upper().startswith("PROPHET"):
            st.caption("Prophet used for trend + seasonality with robustness to shifts/outliers.")
        if "scale_factor" in f.columns:
            st.write("**Display scale factor:**", int(f["scale_factor"].dropna().unique()[0]))

        st.markdown("#### 2025 Forecast")
        yr = 2025
        tcols = [c for c in ["ds","yhat","yhat_lower","yhat_upper"] if c in f.columns]
        yr_tbl = f[(f["source"]=="forecast") & (f["ds"].dt.year==yr)][tcols].round(2)
        st.dataframe(yr_tbl, height=420)
        st.download_button("Download 2025 forecast (CSV)", data=df_to_csv_bytes(yr_tbl),
                           file_name=f"{category}_{subcategory}_2025_forecast.csv", mime="text/csv")

def page_diagnostics(df: pd.DataFrame):
    st.title("Diagnostics (Residuals & Fit)")

    with st.sidebar:
        category = st.selectbox("Category", sorted(df["category"].unique()))
        subcats = sorted(df.loc[df["category"].eq(category), "subcategory"].unique())
        subcategory = st.selectbox("Subcategory", subcats)
        use_scaling = st.checkbox("Apply display scaling", value=False)

    f = filter_df(df, category=category, subcategory=subcategory)
    f = apply_display_scaling(f, use_scaling)

    st.markdown("#### Residuals (in-sample), where available")
    if {"y","yhat"}.issubset(f.columns):
        hist = f[(f["source"]=="history") & f["y"].notna()].copy()
        fitted = hist.merge(f[["ds","yhat"]], on="ds", how="left").dropna(subset=["yhat"]).copy()
        fitted["resid"] = fitted["y"] - fitted["yhat"]

        # Time plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=fitted["ds"], y=fitted["resid"], mode="lines", name="Residual"))
        fig.add_hline(y=0, line_width=1)
        fig.update_layout(title="Residuals over Time", template="plotly_white", xaxis_title="Date", yaxis_title="Residual")
        st.plotly_chart(fig, use_container_width=True)

        # Histogram
        hist_fig = go.Figure()
        hist_fig.add_trace(go.Histogram(x=fitted["resid"], nbinsx=20, name="Residuals"))
        hist_fig.update_layout(title="Residual Distribution", template="plotly_white")
        st.plotly_chart(hist_fig, use_container_width=True)

        # Summary
        mean = float(fitted["resid"].mean())
        mae = float(fitted["resid"].abs().mean())
        rmse = float(np.sqrt((fitted["resid"]**2).mean()))
        st.write(f"**Summary:** mean={mean:.2f} (≈0 is good), MAE={mae:.2f}, RMSE={rmse:.2f}")
    else:
        st.info("Residual vectors were not provided in the dataset for this selection.")

def page_scenarios(df: pd.DataFrame):
    st.title("Scenario Planner")

    with st.sidebar:
        category = st.selectbox("Category", sorted(df["category"].unique()))
        subcats = sorted(df.loc[df["category"].eq(category), "subcategory"].unique())
        subcategory = st.selectbox("Subcategory", subcats)
        use_scaling = st.checkbox("Apply display scaling", value=True)

    base = filter_df(df, category=category, subcategory=subcategory)
    base = apply_display_scaling(base, use_scaling)
    fc = base[base["source"]=="forecast"].copy()

    st.markdown("#### Uplift Assumptions")
    col1, col2, col3 = st.columns(3)
    with col1:
        oct_uplift = st.slider("October uplift (%)", 0, 100, 0)     # Costumes/Halloween
    with col2:
        dec_uplift = st.slider("December uplift (%)", 0, 100, 0)    # Toys
    with col3:
        spring_uplift = st.slider("Spring uplift (Mar–May, %)", 0, 100, 0)  # Bicycles

    adj = fc.copy()
    adj["month"] = adj["ds"].dt.month
    adj["yhat_adj"] = adj["yhat"]
    # Apply uplifts multiplicatively by month
    adj.loc[adj["month"].eq(10), "yhat_adj"] *= (1 + oct_uplift/100)
    adj.loc[adj["month"].eq(12), "yhat_adj"] *= (1 + dec_uplift/100)
    adj.loc[adj["month"].isin([3,4,5]), "yhat_adj"] *= (1 + spring_uplift/100)

    plot_df = pd.concat([
        base[base["source"]=="history"][["ds","y"]].assign(series="Historical"),
        fc.rename(columns={"yhat":"y"})[["ds","y"]].assign(series="Base Forecast"),
        adj.rename(columns={"yhat_adj":"y"})[["ds","y"]].assign(series="Scenario Forecast"),
    ]).sort_values("ds")

    st.line_chart(plot_df.pivot(index="ds", columns="series", values="y"))

    st.markdown("#### Scenario Totals (selected forecast rows)")
    base_total = float(fc["yhat"].sum())
    scen_total = float(adj["yhat_adj"].sum())
    st.write(f"Base forecast total: **{base_total:,.0f}**")
    st.write(f"Scenario forecast total: **{scen_total:,.0f}**  (Δ = {scen_total-base_total:,.0f})")

    st.download_button(
        "Download Scenario Forecast (CSV)",
        data=df_to_csv_bytes(adj[["ds","yhat_adj"]].rename(columns={"yhat_adj":"yhat"})),
        file_name=f"{category}_{subcategory}_scenario_forecast.csv",
        mime="text/csv"
    )

# ----------------------------- ROUTER ---------------------------------------
def main():
    df = load_long_forecasts("data/forecasts_long.parquet")

    with st.sidebar:
        st.title("Navigation")
        page = st.radio("Go to", ["Overview", "Category Detail", "Diagnostics", "Scenario Planner"])

    if page == "Overview":
        page_overview(df)
    elif page == "Category Detail":
        page_category_detail(df)
    elif page == "Diagnostics":
        page_diagnostics(df)
    elif page == "Scenario Planner":
        page_scenarios(df)

if __name__ == "__main__":
    main()
