# app.py
import os
import math
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =============== PAGE ===============
st.set_page_config(page_title="Baba Jina | One-Page Ops Dashboard", layout="wide")

CSS = """
<style>
.card {background:#fff;border-radius:14px;padding:16px 18px;border:1px solid #eef0f4;box-shadow:0 4px 18px rgba(0,0,0,0.06)}
.kpi-title{font-size:12px;color:#6b7280}
.kpi-val{font-size:28px;font-weight:800;margin-top:2px}
.kpi-sub{font-size:11px;color:#9aa2af}
.h2{font-size:22px;font-weight:800;margin:6px 0 12px}
.section-sub{font-size:12px;color:#64748b;margin-bottom:6px}
.empty{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:12px;padding:16px;color:#475569}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

DATA_DIR = "data"
SALES_XLSX     = os.path.join(DATA_DIR, "(3) BABA JINA SALES DATA.xlsx")
SUPPLIERS_XLSX = os.path.join(DATA_DIR, "suppliers_data_cleaned.xlsx")
RENTALS_XLSX   = os.path.join(DATA_DIR, "rentals.xlsx")

# =============== LOADERS ===============
@st.cache_data(show_spinner=False)
def load_sales_pack():
    """Prefer compact parquet artifacts if present; else load Excel."""
    p_monthly = os.path.join(DATA_DIR, "sales_monthly.parquet")
    p_cat     = os.path.join(DATA_DIR, "sales_by_category.parquet")
    p_slim    = os.path.join(DATA_DIR, "sales_slim.parquet")
    if os.path.exists(p_monthly) and os.path.exists(p_cat):
        return {
            "monthly": pd.read_parquet(p_monthly),
            "by_cat": pd.read_parquet(p_cat),
            "slim": pd.read_parquet(p_slim) if os.path.exists(p_slim) else None
        }

    if not os.path.exists(SALES_XLSX):
        return {"monthly": None, "by_cat": None, "slim": None}

    df = pd.read_excel(SALES_XLSX)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    # Revenue
    if "Total_Amount" in df.columns:
        df["Revenue"] = pd.to_numeric(df["Total_Amount"], errors="coerce")
    else:
        q = pd.to_numeric(df.get("Quantity", np.nan), errors="coerce")
        p = pd.to_numeric(df.get("Unit_Price", np.nan), errors="coerce")
        df["Revenue"] = q * p
    df["Category"] = df.get("Category", "Unknown").fillna("Unknown")
    df["Subcategory"] = df.get("Subcategory", "Unknown").fillna("Unknown")
    monthly = (
        df.dropna(subset=["Month"])
          .groupby("Month", as_index=False)["Revenue"].sum()
          .sort_values("Month")
    )
    by_cat = (
        df.groupby("Category", as_index=False)["Revenue"].sum()
          .sort_values("Revenue", ascending=False)
    )
    slim = df[["Date","Month","Category","Subcategory","Customer_ID","Revenue"]].copy()
    return {"monthly": monthly, "by_cat": by_cat, "slim": slim}

@st.cache_data(show_spinner=False)
def load_suppliers():
    if not os.path.exists(SUPPLIERS_XLSX):
        return None
    sup = pd.read_excel(SUPPLIERS_XLSX)
    # Order amount
    if "Amount" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["Amount"], errors="coerce")
    elif "AMOUNT" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["AMOUNT"], errors="coerce")
    else:
        price = pd.to_numeric(sup.get("Price"), errors="coerce")
        ctn   = pd.to_numeric(sup.get("CTN_Box"), errors="coerce")
        sup["Order_Amount"] = price * ctn
    # Year
    if "New_Year" in sup.columns:
        sup["Year"] = sup["New_Year"]
    elif "Year" not in sup.columns:
        sup["Year"] = np.nan
    # Category
    sup["Category"] = sup.get("Category", "Unknown").fillna("Unknown")
    # Shop / Supplier name column guess
    for g in ["Shop","Supplier","Supplier_Name","Vendor","Name"]:
        if g in sup.columns:
            sup["ShopName"] = sup[g].astype(str)
            break
    if "ShopName" not in sup.columns:
        sup["ShopName"] = "Unknown"
    return sup.dropna(subset=["Order_Amount"])

@st.cache_data(show_spinner=False)
def load_rentals():
    if not os.path.exists(RENTALS_XLSX):
        return None
    ren = pd.read_excel(RENTALS_XLSX)
    for col in ["Start_Date","start_date","Date","date"]:
        if col in ren.columns:
            ren[col] = pd.to_datetime(ren[col], errors="coerce")
    # unify a start column
    ren["start_any"] = None
    for c in ["Start_Date","start_date","Date","date"]:
        if c in ren.columns:
            ren["start_any"] = ren[c]; break
    for g in ["Rental Price","Rental_Price","rent_price","Price","price"]:
        if g in ren.columns:
            ren["RentalPrice"] = pd.to_numeric(ren[g], errors="coerce"); break
    for g in ["Mascot Name","Mascot_Name","Name","name","Mascot"]:
        if g in ren.columns:
            ren["Mascot"] = ren[g].astype(str); break
    return ren

sales_pack = load_sales_pack()
suppliers  = load_suppliers()
rentals    = load_rentals()

# =============== FILTERS ===============
with st.sidebar:
    st.header("Filters")

    # Sales date range
    if sales_pack["slim"] is not None and "Date" in sales_pack["slim"].columns:
        s = sales_pack["slim"]
        min_d, max_d = s["Date"].min(), s["Date"].max()
        d1, d2 = st.date_input(
            "Sales date range",
            value=(min_d.date(), max_d.date()),
            min_value=min_d.date(), max_value=max_d.date()
        )
        mask_sales = (s["Date"].dt.date >= d1) & (s["Date"].dt.date <= d2)
        sales_rows = s[mask_sales].copy()
        sales_monthly = sales_rows.groupby("Month", as_index=False)["Revenue"].sum() if "Month" in s.columns else sales_pack["monthly"]
        sales_by_cat  = sales_rows.groupby("Category", as_index=False)["Revenue"].sum().sort_values("Revenue", ascending=False)
    else:
        sales_rows   = sales_pack["slim"]
        sales_monthly= sales_pack["monthly"]
        sales_by_cat = sales_pack["by_cat"]

    # Supplier years
    if suppliers is not None and suppliers["Year"].notna().any():
        years = sorted([int(y) for y in suppliers["Year"].dropna().unique()])
        year_sel = st.multiselect("Supplier years", years, default=years)
        sup_f = suppliers[suppliers["Year"].isin(year_sel)] if years else suppliers.copy()
    else:
        sup_f = suppliers

    # Rentals period
    if rentals is not None and rentals["start_any"].notna().any():
        min_r, max_r = rentals["start_any"].min(), rentals["start_any"].max()
        r1, r2 = st.date_input(
            "Rental period",
            value=(min_r.date(), max_r.date()),
            min_value=min_r.date(), max_value=max_r.date()
        )
        ren_f = rentals[(rentals["start_any"].dt.date >= r1) & (rentals["start_any"].dt.date <= r2)].copy()
    else:
        ren_f = rentals

# =============== ROW 1: TOP KPIs ===============
st.markdown('<div class="h2">Overview</div>', unsafe_allow_html=True)
k1, k2, k3, k4, k5 = st.columns(5)

def _fmt_money(x): 
    if pd.isna(x): return "$0"
    if x >= 1_000_000: return f"${x/1_000_000:.1f}M"
    if x >= 1_000:     return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"

with k1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Total Revenue (YTD)</div>', unsafe_allow_html=True)
    if sales_rows is not None and not sales_rows.empty:
        ytd = sales_rows[sales_rows["Date"].dt.year == pd.Timestamp.today().year]["Revenue"].sum()
        st.markdown(f'<div class="kpi-val">{_fmt_money(float(ytd))}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">$0</div><div class="kpi-sub">No sales loaded</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with k2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Avg Order Value (AOV)</div>', unsafe_allow_html=True)
    if sales_rows is not None and not sales_rows.empty:
        aov = sales_rows["Revenue"].mean()
        st.markdown(f'<div class="kpi-val">{_fmt_money(float(aov))}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-sub">{len(sales_rows):,} orders</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">$0</div><div class="kpi-sub">—</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with k3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Supplier Spend (YTD)</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty and sup_f["Year"].notna().any():
        current_year = pd.Timestamp.today().year
        spend_ytd = sup_f[sup_f["Year"] == current_year]["Order_Amount"].sum()
        st.markdown(f'<div class="kpi-val">{_fmt_money(float(spend_ytd))}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">$0</div><div class="kpi-sub">No supplier data</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with k4:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Active Customers</div>', unsafe_allow_html=True)
    if sales_rows is not None and not sales_rows.empty and "Customer_ID" in sales_rows.columns:
        st.markdown(f'<div class="kpi-val">{sales_rows["Customer_ID"].nunique():,}</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-sub">in selected range</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">0</div><div class="kpi-sub">—</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with k5:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Mascot Rentals (This Month)</div>', unsafe_allow_html=True)
    if ren_f is not None and not ren_f.empty and ren_f["start_any"].notna().any():
        this_month = pd.Timestamp.today().to_period("M")
        count = (ren_f["start_any"].dt.to_period("M") == this_month).sum()
        st.markdown(f'<div class="kpi-val">{int(count):,}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">0</div><div class="kpi-sub">—</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# =============== ROW 2: SALES & FORECASTING + SUPPLIERS ===============
left, right = st.columns([2, 1])

with left:
    st.markdown('<div class="h2">Sales & Forecasting</div>', unsafe_allow_html=True)

    # Monthly Sales Trend
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Monthly Sales Trend</div>', unsafe_allow_html=True)
    if sales_monthly is not None and not sales_monthly.empty:
        fig = px.area(sales_monthly, x="Month", y="Revenue")
        fig.update_layout(height=300, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="sales_monthly_trend")
    else:
        st.markdown('<div class="empty">No monthly sales available.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Category Revenue
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Revenue by Product Category</div>', unsafe_allow_html=True)
    if sales_by_cat is not None and not sales_by_cat.empty:
        fig = px.bar(sales_by_cat.head(12), x="Category", y="Revenue", text_auto=".2s")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=320, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="sales_by_category")
    else:
        st.markdown('<div class="empty">No category breakdown available.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Forecast Tabs (placeholder until you plug Prophet/SARIMA)
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Forecast (demo)</div>', unsafe_allow_html=True)
    if sales_monthly is not None and not sales_monthly.empty:
        df = sales_monthly.copy()
        df["SMA3"] = df["Revenue"].rolling(3).mean()
        df["SMA6"] = df["Revenue"].rolling(6).mean()

        tab_names = ["Halloween", "Toys", "Bicycles"]
        tabs = st.tabs(tab_names)
        for name, tab in zip(tab_names, tabs):
            with tab:
                fig = px.line(df, x="Month", y=["Revenue","SMA3","SMA6"], labels={"value":"Revenue"})
                fig.update_layout(height=280, legend_title_text="", margin=dict(l=6,r=6,t=6,b=6))
                st.plotly_chart(fig, use_container_width=True, key=f"forecast_{name.lower()}")
                st.caption("Replace with SARIMA/Prophet per category once ready.")
    else:
        st.markdown('<div class="empty">Add monthly series to enable forecast view.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="h2">Suppliers</div>', unsafe_allow_html=True)

    # Top 5 Suppliers by Order Amount
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Top 5 Supplier Shops by Order Amount</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty:
        top5 = sup_f.groupby("ShopName", as_index=False)["Order_Amount"].sum().sort_values("Order_Amount", ascending=False).head(5)
        fig = px.bar(top5, x="ShopName", y="Order_Amount", text_auto=".2s")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=280, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="suppliers_top5")
    else:
        st.markdown('<div class="empty">No supplier rows available for the selected years.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Supplier Order Amount by Category over Years
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Supplier Spend by Category over Years</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty and sup_f["Year"].notna().any():
        agg = sup_f.groupby(["Year","Category"], as_index=False)["Order_Amount"].sum()
        fig = px.bar(agg, x="Year", y="Order_Amount", color="Category", barmode="stack")
        fig.update_layout(height=300, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="suppliers_spend_stack")
    else:
        st.markdown('<div class="empty">Add Year and Category in suppliers to see this chart.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # KPI: Supplier Dependency (% from top 2 suppliers)
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Supplier Dependency</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty:
        by_shop = sup_f.groupby("ShopName", as_index=False)["Order_Amount"].sum().sort_values("Order_Amount", ascending=False)
        total = by_shop["Order_Amount"].sum()
        top2 = by_shop.head(2)["Order_Amount"].sum()
        pct = (top2/total*100) if total else 0
        st.markdown(f'<div class="kpi-val">{pct:.1f}%</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi-sub">Share of spend from top 2 suppliers</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">0%</div><div class="kpi-sub">—</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# =============== ROW 3: RENTALS + LOYALTY/MARKETING ===============
colA, colB = st.columns(2)

with colA:
    st.markdown('<div class="h2">Rentals</div>', unsafe_allow_html=True)

    # Bookings Over Time
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Rental Bookings Over Time</div>', unsafe_allow_html=True)
    if ren_f is not None and not ren_f.empty and ren_f["start_any"].notna().any():
        r = ren_f.dropna(subset=["start_any"]).copy()
        r["Month"] = r["start_any"].dt.to_period("M").dt.to_timestamp()
        r_agg = r.groupby("Month", as_index=False).size().rename(columns={"size":"Bookings"})
        fig = px.area(r_agg, x="Month", y="Bookings")
        fig.update_layout(height=280, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="rentals_over_time")
    else:
        st.markdown('<div class="empty">No dated rental records available.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Upcoming Rentals Table
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Upcoming 10 Rentals</div>', unsafe_allow_html=True)
    if ren_f is not None and not ren_f.empty and ren_f["start_any"].notna().any():
        upcoming = ren_f.dropna(subset=["start_any"]).sort_values("start_any").head(10)
        view_cols = [c for c in ["Mascot","start_any","End_Date","Customer","RentalPrice"] if c in upcoming.columns]
        st.dataframe(upcoming[view_cols])
    else:
        st.markdown('<div class="empty">No upcoming rentals.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Rentals KPIs
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Rental KPIs</div>', unsafe_allow_html=True)
    if ren_f is not None and not ren_f.empty:
        top_mascot = (ren_f["Mascot"].mode()[0] if "Mascot" in ren_f.columns and not ren_f["Mascot"].isna().all() else "—")
        avg_price  = (float(ren_f["RentalPrice"].mean()) if "RentalPrice" in ren_f.columns else np.nan)
        st.markdown(f'<div class="kpi-title">Most Rented Mascot</div><div class="kpi-val">{top_mascot}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-title" style="margin-top:10px;">Avg Rental Price</div><div class="kpi-val">{_fmt_money(avg_price) if not math.isnan(avg_price) else "—"}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">—</div><div class="kpi-sub">No rental data</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with colB:
    st.markdown('<div class="h2">Loyalty & Marketing</div>', unsafe_allow_html=True)

    # Loyalty Gauge (simple progress using current unique customers vs a target)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Loyalty Members Enrolled (proxy)</div>', unsafe_allow_html=True)
    if sales_rows is not None and not sales_rows.empty and "Customer_ID" in sales_rows.columns:
        members = sales_rows["Customer_ID"].nunique()
        target = max(100, members)  # set your own target
        pct = int(members / target * 100) if target else 0
        st.progress(min(pct, 100), text=f"{members:,} of {target:,}")
    else:
        st.markdown('<div class="empty">No customers to display.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Points Earned vs Redeemed (placeholder—replace with your loyalty table when ready)
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Points Earned vs Redeemed</div>', unsafe_allow_html=True)
    # Prototype data until you connect the real loyalty table
    pts = pd.DataFrame({
        "Month": pd.date_range("2024-01-01", periods=12, freq="MS"),
        "Earned": np.random.randint(800, 1600, 12),
        "Redeemed": np.random.randint(300, 1100, 12)
    })
    fig = px.bar(pts, x="Month", y=["Earned","Redeemed"], barmode="group")
    fig.update_layout(height=280, margin=dict(l=6,r=6,t=6,b=6), legend_title_text="")
    st.plotly_chart(fig, use_container_width=True, key="loyalty_points_earned_redeemed")
    st.caption("Hook this to your loyalty transactions when available.")
    st.markdown('</div>', unsafe_allow_html=True)

    # Campaign mini-cards
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Active Campaigns</div>', unsafe_allow_html=True)
    st.write("- Instagram Reels: New arrivals / rentals")
    st.write("- Halloween bundles: upsell glow sticks & accessories")
    st.write("- Referral code: +points for both sides")
    st.markdown('</div>', unsafe_allow_html=True)

# =============== FOOTER ===============
st.caption("Prototype complete. Replace placeholders (forecast model, loyalty points) with your actual tables as they become available.")
