# single_page_dashboard.py
# Baba Jina Toys – Digital Transformation Dashboard (Single Page)
# Run with:  streamlit run single_page_dashboard.py

import os
import math
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from datetime import datetime
from pandas.tseries.offsets import MonthEnd

# ========================== PAGE & THEME ==========================
st.set_page_config(page_title="Baba Jina Toys – Executive Dashboard", layout="wide")

st.markdown("""
<style>
  .block-container {padding-top: 0.6rem; padding-bottom: 0.6rem;}
  .kpi-card, .section {
      background: #ffffff;
      border: 1px solid rgba(0,0,0,0.06);
      border-radius: 12px;
      padding: 14px;
  }
  h1, h2, h3 { color:#1f4bd8; font-weight:700; }
  .caption { color: #6b7280; font-size: 0.9rem; }
  .muted { color: #6b7280; }
</style>
""", unsafe_allow_html=True)

# ========================== FILE PATHS (change if needed) ==========================
DEFAULT_SALES_PATH     = "/mnt/data/(3) BABA JINA SALES DATA.xlsx"
DEFAULT_SUPPLIERS_PATH = "/mnt/data/suppliers_data_cleaned.xlsx"
DEFAULT_RENTALS_PATH   = "/mnt/data/rentals.xlsx"

# ========================== HELPERS ==========================
def _first_present(d: dict, keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None

def parse_excel_any_sheet(path):
    """Reads first sheet if name unknown."""
    try:
        xl = pd.ExcelFile(path)
        return pd.read_excel(path, sheet_name=xl.sheet_names[0])
    except Exception as e:
        st.error(f"Could not load Excel file: {path}\n{e}")
        return pd.DataFrame()

def coerce_datetime(s):
    try:
        out = pd.to_datetime(s, errors="coerce")
        return out
    except Exception:
        return pd.to_datetime(s, errors="coerce")

def month_start(df, col):
    return coerce_datetime(df[col]).dt.to_period("M").dt.to_timestamp("M")

def safe_sum(series):
    return pd.to_numeric(series, errors="coerce").fillna(0).sum()

def month_name(m):
    return pd.Timestamp(2000, int(m), 1).strftime("%B")

# ========================== LOADERS ==========================
@st.cache_data(show_spinner=True)
def load_sales(path):
    """
    Expected (any of these names):
      Date: ["Date","date","ORDER_DATE","Order_Date"]
      Category: ["Category","category","Main Category","Main_Category"]
      Revenue: ["Total_Amount","total_amount","Amount","amount","Revenue","revenue","Total"]
      Quantity * Unit Price will be used if revenue absent.
      Customer: ["Customer_ID","Customer","customer_id"]
      Subcategory optional: ["Subcategory","sub_category","Sub_Category"]
      Product optional: ["Product_Name","Item_EN","Item","product"]
    """
    df = parse_excel_any_sheet(path)
    if df.empty:
        return df

    cols = {c:str(c) for c in df.columns}
    lower = {str(c).strip().lower(): c for c in df.columns}

    date_col      = _first_present(lower, ["date","order_date","order date"])
    cat_col       = _first_present(lower, ["category","main category","main_category"])
    subcat_col    = _first_present(lower, ["subcategory","sub_category","sub category"])
    cust_col      = _first_present(lower, ["customer_id","customer","id"])
    prod_col      = _first_present(lower, ["product_name","item_en","item","product"])
    revenue_col   = _first_present(lower, ["total_amount","amount","revenue","total","sales"])

    qty_col       = _first_present(lower, ["quantity","qty","count"])
    unit_price_col= _first_present(lower, ["unit_price","price","unit price"])

    # Basic renames into a common schema
    out = pd.DataFrame()
    if date_col is None:
        st.warning("Sales file: couldn't find a Date column; please ensure a 'Date' exists.")
        return out

    out["date"] = coerce_datetime(df[date_col])
    if cat_col is not None:
        out["category"] = df[cat_col].astype(str)
    else:
        out["category"] = "Uncategorized"

    if subcat_col is not None:
        out["subcategory"] = df[subcat_col].astype(str)
    if cust_col is not None:
        out["customer_id"] = df[cust_col].astype(str)
    if prod_col is not None:
        out["product"] = df[prod_col].astype(str)

    if revenue_col is not None:
        out["revenue"] = pd.to_numeric(df[revenue_col], errors="coerce")
    else:
        # Try Quantity * Unit Price
        if qty_col is not None and unit_price_col is not None:
            out["revenue"] = pd.to_numeric(df[qty_col], errors="coerce") * pd.to_numeric(df[unit_price_col], errors="coerce")
        else:
            st.warning("Sales file: no revenue column and no (Quantity, Unit_Price) found; setting revenue=0.")
            out["revenue"] = 0.0

    out = out.dropna(subset=["date"]).copy()
    return out

@st.cache_data(show_spinner=True)
def load_suppliers(path):
    """
    Expected suppliers columns (any):
      Supplier: ["Shop","supplier","Supplier","shop"]
      Category: ["Category","category"]
      Amount:   ["Amount","Total_Amount","order_amount","Total"]
      Year:     ["Year","year"]
    """
    df = parse_excel_any_sheet(path)
    if df.empty:
        return df
    lower = {str(c).strip().lower(): c for c in df.columns}

    supplier_col = _first_present(lower, ["shop","supplier"])
    category_col = _first_present(lower, ["category"])
    amount_col   = _first_present(lower, ["amount","total_amount","order_amount","total"])
    year_col     = _first_present(lower, ["year"])

    # Build a normalized frame
    out = pd.DataFrame()
    if supplier_col is None or amount_col is None:
        st.warning("Suppliers file: please ensure 'Shop/Supplier' and 'Amount' columns exist.")
        return out

    out["supplier"] = df[supplier_col].astype(str)
    out["order_amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
    out["category"] = df[category_col].astype(str) if category_col else "Uncategorized"
    if year_col:
        out["year"] = pd.to_numeric(df[year_col], errors="coerce").astype("Int64")
    else:
        # Try to infer year if a date field exists
        date_col = _first_present(lower, ["date","order_date"])
        if date_col:
            out["year"] = coerce_datetime(df[date_col]).dt.year.astype("Int64")
        else:
            out["year"] = pd.NA
    return out

@st.cache_data(show_spinner=True)
def load_rentals(path):
    """
    Expected rentals columns (any):
      Mascot: ["mascot","Mascot","Mascot_Name","name"]
      Start:  ["start_date","Start_Date","start","from"]
      End:    ["end_date","End_Date","end","to"]
    """
    df = parse_excel_any_sheet(path)
    if df.empty:
        return df
    lower = {str(c).strip().lower(): c for c in df.columns}

    mascot_col = _first_present(lower, ["mascot","mascot_name","name"])
    start_col  = _first_present(lower, ["start_date","start","from"])
    end_col    = _first_present(lower, ["end_date","end","to"])

    if mascot_col is None or start_col is None or end_col is None:
        st.warning("Rentals file: please ensure (Mascot, Start_Date, End_Date) columns exist.")
        return pd.DataFrame()

    out = pd.DataFrame()
    out["mascot"] = df[mascot_col].astype(str)
    out["start"]  = coerce_datetime(df[start_col])
    out["end"]    = coerce_datetime(df[end_col])
    out = out.dropna(subset=["start","end"])
    return out

# ========================== BUSINESS LOGIC ==========================
def monthly_sales_with_forecast(sales_df, cat_filter):
    # Filter categories
    df = sales_df.copy()
    if cat_filter:
        df = df[df["category"].isin(cat_filter)]

    # Month-end aggregation
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp("M")
    monthly = df.groupby("month", as_index=False)["revenue"].sum()

    # Seasonal-naïve forecast for 2025: avg of previous years by month-number
    monthly["year"] = monthly["month"].dt.year
    monthly["m"] = monthly["month"].dt.month

    hist = monthly[monthly["year"] <= 2024].copy()
    if hist.empty:
        return monthly.assign(series="Actual"), pd.DataFrame()

    ref = (
        hist.groupby("m")["revenue"]
        .mean()
        .rename("forecast_revenue")
        .reset_index()
    )
    future_index = pd.date_range("2025-01-31", "2025-12-31", freq="M")
    future = pd.DataFrame({"month": future_index})
    future["m"] = future["month"].dt.month
    future = future.merge(ref, on="m", how="left").fillna(method="ffill").fillna(method="bfill")
    future = future[["month","forecast_revenue"]].rename(columns={"forecast_revenue":"revenue"})
    future["series"] = "Forecast (Seasonal-Naïve)"

    actual = monthly[["month","revenue"]].copy()
    actual["series"] = "Actual"
    return actual, future

def supplier_dependence(sup_df, years):
    df = sup_df.copy()
    if years:
        df = df[df["year"].isin(years)]
    agg = df.groupby("supplier", as_index=False)["order_amount"].sum().sort_values("order_amount", ascending=False)
    total = agg["order_amount"].sum()
    top2 = agg.head(2)["order_amount"].sum() if total > 0 else 0
    pct = (top2 / total * 100.0) if total else 0.0
    return pct, agg

def rentals_utilization_monthly(rentals_df):
    """
    For each mascot and calendar month, compute utilization %:
      (booked days within month) / (days in month) * 100
    """
    if rentals_df.empty:
        return rentals_df

    bookings = []
    for _, r in rentals_df.iterrows():
        start = r["start"]
        end   = r["end"]
        if pd.isna(start) or pd.isna(end) or end < start:
            continue
        # enumerate all days within booking
        days = pd.date_range(start.normalize(), end.normalize(), freq="D")
        for d in days:
            bookings.append({"date": d, "mascot": r["mascot"]})

    if not bookings:
        return pd.DataFrame()

    used = pd.DataFrame(bookings)
    used["month"] = used["date"].dt.to_period("M").dt.to_timestamp("M")

    # denom: days in each month
    months = used["month"].drop_duplicates()
    denom = pd.DataFrame({"month": months})
    denom["days_in_month"] = denom["month"].dt.days_in_month

    # per mascot+month unique days booked
    used_unique = used.drop_duplicates(["mascot","date"])
    num = used_unique.groupby(["mascot","month"], as_index=False).size().rename(columns={"size":"booked_days"})
    out = num.merge(denom, on="month", how="left")
    out["utilization_pct"] = (out["booked_days"] / out["days_in_month"] * 100.0).round(1)
    return out[["month","mascot","utilization_pct"]]

def rfm_segmentation(sales_df, asof=None):
    """
    Simple RFM using monthly sales:
      Recency: days since last purchase
      Frequency: number of orders (grouped by date) per customer
      Monetary: total revenue
    Then bin into segments.
    """
    if "customer_id" not in sales_df.columns:
        return pd.DataFrame(), pd.DataFrame()

    df = sales_df.dropna(subset=["customer_id","date"]).copy()
    df["date_only"] = df["date"].dt.date
    asof = asof or df["date"].max()

    grp = df.groupby("customer_id")
    last_date = grp["date_only"].max().apply(pd.to_datetime)
    freq = grp["date_only"].nunique()
    mon  = grp["revenue"].sum()

    rfm = pd.DataFrame({
        "customer_id": last_date.index,
        "recency_days": (pd.Timestamp(asof) - last_date).dt.days,
        "frequency": freq.values,
        "monetary": mon.values
    })

    # Quintiles for R/F/M (lower recency_days is better)
    try:
        rfm["R_score"] = pd.qcut(-rfm["recency_days"], 5, labels=[1,2,3,4,5]).astype(int)  # invert sign
    except Exception:
        rfm["R_score"] = 3
    try:
        rfm["F_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 5, labels=[1,2,3,4,5]).astype(int)
    except Exception:
        rfm["F_score"] = 3
    try:
        rfm["M_score"] = pd.qcut(rfm["monetary"].rank(method="first"), 5, labels=[1,2,3,4,5]).astype(int)
    except Exception:
        rfm["M_score"] = 3

    # Lightweight mapping (can replace with your custom grid)
    def segment_row(r,f):
        if r>=4 and f>=4: return "Champions"
        if r>=4 and f<=3: return "Potential Loyalists"
        if r==3 and f>=4: return "Loyal"
        if r<=2 and f>=4: return "At-risk"
        if r<=2 and f<=2: return "Hibernating"
        if r==5 and f==1: return "New"
        return "Promising"

    rfm["segment"] = [segment_row(r,f) for r,f in zip(rfm["R_score"], rfm["F_score"])]
    seg_counts = rfm["segment"].value_counts().reset_index().rename(columns={"index":"segment","count":"customers"})
    return rfm, seg_counts

# ========================== DATA LOAD ==========================
st.title("Baba Jina Toys – Digital Transformation Dashboard")

with st.container():
    f1, f2, f3 = st.columns([3,3,3])
    sales_path = f1.text_input("Sales file path", value=DEFAULT_SALES_PATH)
    suppliers_path = f2.text_input("Suppliers file path", value=DEFAULT_SUPPLIERS_PATH)
    rentals_path = f3.text_input("Rentals file path", value=DEFAULT_RENTALS_PATH)

sales_raw     = load_sales(sales_path) if os.path.exists(sales_path) else pd.DataFrame()
suppliers_raw = load_suppliers(suppliers_path) if os.path.exists(suppliers_path) else pd.DataFrame()
rentals_raw   = load_rentals(rentals_path) if os.path.exists(rentals_path) else pd.DataFrame()

# Global filters
with st.container():
    c1, c2, c3 = st.columns([2,2,2])
    years_available = sorted(sales_raw["date"].dt.year.unique().tolist()) if not sales_raw.empty else []
    cats_available = sorted(sales_raw["category"].dropna().unique().tolist()) if not sales_raw.empty else []
    year_sel = c1.multiselect("Years (Actual)", years_available, default=[y for y in years_available if y in (2023, 2024)])
    cat_sel  = c2.multiselect("Product Categories", cats_available, default=[c for c in cats_available if c in ["Toys","Halloween","Christmas"]])
    show_fc  = c3.toggle("Overlay 2025 Seasonal Forecast", value=True)

# ========================== KPIs (Row 1) ==========================
with st.container():
    col1, col2, col3, col4 = st.columns(4)
    # KPI 1: Total Sales 2024 vs 2023
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        if not sales_raw.empty:
            base = sales_raw[sales_raw["category"].isin(cat_sel)] if cat_sel else sales_raw
            total_2024 = base[base["date"].dt.year==2024]["revenue"].sum()
            total_2023 = base[base["date"].dt.year==2023]["revenue"].sum()
            growth = ((total_2024 - total_2023) / total_2023 * 100.0) if total_2023 else 0.0
            st.metric("Total Sales (2024)", f"${total_2024:,.0f}", f"{growth:+.1f}% vs 2023")
        else:
            st.metric("Total Sales (2024)", "—", "load sales")
        st.markdown('</div>', unsafe_allow_html=True)

    # KPI 2: Forecasted Peak Month 2025
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        if not sales_raw.empty:
            actual, future = monthly_sales_with_forecast(sales_raw, cat_sel)
            if not future.empty:
                best = future.sort_values("revenue", ascending=False).iloc[0]
                st.metric("Forecasted Peak (2025)", best["month"].strftime("%B %Y"), f"${best['revenue']:,.0f}")
            else:
                st.metric("Forecasted Peak (2025)", "—", "no forecast")
        else:
            st.metric("Forecasted Peak (2025)", "—", "load sales")
        st.markdown('</div>', unsafe_allow_html=True)

    # KPI 3: Supplier Dependence Index (top 2 share)
    with col3:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        if not suppliers_raw.empty:
            years_for_dep = year_sel if year_sel else suppliers_raw["year"].dropna().unique().tolist()
            dep, _ = supplier_dependence(suppliers_raw, years_for_dep)
            st.metric("Supplier Dependence (Top 2)", f"{dep:.1f}%", "share of order amount")
        else:
            st.metric("Supplier Dependence (Top 2)", "—", "load suppliers")
        st.markdown('</div>', unsafe_allow_html=True)

    # KPI 4: Active Loyalty Customers (proxy = nonzero customers in last 180 days)
    with col4:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        if not sales_raw.empty:
            cutoff = (sales_raw["date"].max() - pd.Timedelta(days=180))
            recent_customers = sales_raw[sales_raw["date"]>=cutoff]
            n_active = recent_customers["customer_id"].nunique() if "customer_id" in recent_customers.columns else 0
            st.metric("Active Loyalty Customers", f"{n_active:,}", "last 180 days")
        else:
            st.metric("Active Loyalty Customers", "—", "load sales")
        st.markdown('</div>', unsafe_allow_html=True)

# ========================== Row 2: Sales & Forecast ==========================
with st.container():
    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.subheader("Sales & Forecast")
    if not sales_raw.empty:
        actual, future = monthly_sales_with_forecast(sales_raw, cat_sel)

        chart_df = actual.copy()
        if show_fc and not future.empty:
            chart_df = pd.concat([chart_df, future], ignore_index=True)

        line = alt.Chart(chart_df).mark_line().encode(
            x=alt.X("month:T", title="Month"),
            y=alt.Y("revenue:Q", title="Revenue (USD)"),
            color=alt.Color("series:N", title="Series")
        ).properties(height=300)

        st.altair_chart(line, use_container_width=True)
        st.caption("Forecast uses a simple seasonal-naïve method (average of prior years by month).")
    else:
        st.info("Load the Sales file to view this chart.")
    st.markdown('</div>', unsafe_allow_html=True)

# ========================== Row 3: Suppliers & Inventory (Inventory: info note) ==========================
with st.container():
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Top Suppliers (Order Amount split by Category)")
        if not suppliers_raw.empty:
            filt = suppliers_raw.copy()
            if year_sel:
                filt = filt[filt["year"].isin(year_sel)]
            top5_sup = (
                filt.groupby("supplier", as_index=False)["order_amount"].sum()
                .sort_values("order_amount", ascending=False)
                .head(5)["supplier"]
                .tolist()
            )
            top_df = filt[filt["supplier"].isin(top5_sup)].copy()
            bar = alt.Chart(top_df).mark_bar().encode(
                x=alt.X("sum(order_amount):Q", title="Order Amount"),
                y=alt.Y("supplier:N", sort="-x", title="Supplier"),
                color=alt.Color("category:N", title="Category")
            ).properties(height=320)
            st.altair_chart(bar, use_container_width=True)
        else:
            st.info("Load the Suppliers file to view top suppliers.")
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Inventory Snapshot")
        st.info("No live inventory file provided. You can replace this card with a table from your POS (stock, min threshold).")
        st.markdown('</div>', unsafe_allow_html=True)

# ========================== Row 4: Rentals & Loyalty ==========================
with st.container():
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Mascot Rentals – Monthly Utilization")
        if not rentals_raw.empty:
            util = rentals_utilization_monthly(rentals_raw)
            if util.empty:
                st.info("No valid rental intervals found.")
            else:
                # Heatmap mascot x month
                heat = alt.Chart(util).mark_rect().encode(
                    x=alt.X("month:T", title="Month"),
                    y=alt.Y("mascot:N", title="Mascot", sort=alt.SortField("mascot")),
                    color=alt.Color("utilization_pct:Q", title="Utilization %", scale=alt.Scale(domain=[0,100])),
                    tooltip=[alt.Tooltip("mascot:N"), alt.Tooltip("month:T"), alt.Tooltip("utilization_pct:Q")]
                ).properties(height=320)
                st.altair_chart(heat, use_container_width=True)
        else:
            st.info("Load the Rentals file to view utilization heatmap.")
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Customer Loyalty Snapshot (RFM-based)")
        if not sales_raw.empty:
            rfm, seg_counts = rfm_segmentation(sales_raw)
            if seg_counts.empty:
                st.info("RFM could not be computed (missing customer IDs).")
            else:
                bar = alt.Chart(seg_counts).mark_bar().encode(
                    x=alt.X("segment:N", sort="-y", title="Segment"),
                    y=alt.Y("customers:Q", title="# Customers")
                ).properties(height=320)
                st.altair_chart(bar, use_container_width=True)
        else:
            st.info("Load the Sales file to compute RFM.")
        st.markdown('</div>', unsafe_allow_html=True)

# ========================== Row 5: Marketing & Delivery Simulator ==========================
with st.container():
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Marketing Activity (Placeholder)")
        st.info("Hook this to your social analytics (posts/week, reach). For now, this is a placeholder card.")
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("Delivery Subsidy Simulator")
        with st.form("sim"):
            c1, c2 = st.columns(2)
            with c1:
                monthly_orders = st.number_input("Monthly Orders Eligible", min_value=0, value=100, step=5)
                threshold_usd = st.number_input("Free Delivery Threshold ($)", min_value=0, value=50, step=5)
                avg_basket_base = st.number_input("Avg Basket (Before Policy) $", min_value=0, value=28, step=1)
            with c2:
                subsidy_per_order = st.number_input("Subsidy Per Eligible Order ($)", min_value=0.0, value=3.5, step=0.5)
                uplift_pct = st.number_input("Basket Uplift for Threshold (%)", min_value=0.0, value=18.0, step=1.0)
                margin_pct = st.number_input("Gross Margin (%)", min_value=0.0, value=35.0, step=1.0)
            run = st.form_submit_button("Run Scenario")

        if run:
            # Assume a share hit threshold and uplift realized
            hit_rate = 0.65  # % of orders reach threshold; adjust if you have data
            eligible_orders = int(monthly_orders * hit_rate)
            new_basket = avg_basket_base * (1 + uplift_pct/100.0)
            incremental_rev = (new_basket - avg_basket_base) * eligible_orders
            gross_profit = (new_basket * (margin_pct/100.0)) * eligible_orders
            subsidy_cost = subsidy_per_order * eligible_orders
            net_impact = gross_profit - subsidy_cost

            st.write(f"**Eligible Orders**: {eligible_orders:,}")
            st.write(f"**Incremental Revenue**: ${incremental_rev:,.0f}")
            st.write(f"**Gross Profit on Eligible Orders**: ${gross_profit:,.0f}")
            st.write(f"**Subsidy Cost**: ${subsidy_cost:,.0f}")
            st.metric("Estimated Net Impact (Monthly)", f"${net_impact:,.0f}",
                      delta_color="normal")
        st.markdown('</div>', unsafe_allow_html=True)

# ========================== Footer: Downloads ==========================
with st.container():
    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.subheader("Exports")
    c1, c2, c3 = st.columns(3)
    # Prepare clean aggregates for export
    if not sales_raw.empty:
        sales_export = sales_raw.copy()
        sales_export["month"] = sales_export["date"].dt.to_period("M").dt.to_timestamp("M")
        monthly_sales = sales_export.groupby(["month","category"], as_index=False)["revenue"].sum()
        c1.download_button("Download Monthly Sales CSV", monthly_sales.to_csv(index=False).encode("utf-8"), "monthly_sales.csv", "text/csv")
    else:
        c1.write("—")
    if not suppliers_raw.empty:
        c2.download_button("Download Suppliers CSV", suppliers_raw.to_csv(index=False).encode("utf-8"), "suppliers.csv", "text/csv")
    else:
        c2.write("—")
    if not rentals_raw.empty:
        util = rentals_utilization_monthly(rentals_raw)
        if not util.empty:
            c3.download_button("Download Rentals Utilization CSV", util.to_csv(index=False).encode("utf-8"), "rentals_utilization.csv", "text/csv")
        else:
            c3.write("—")
    else:
        c3.write("—")
    st.caption("Forecasts are indicative and based on historical seasonality; uncertainty increases further into the future.")
    st.markdown('</div>', unsafe_allow_html=True)
