# app.py — EDA-only, 1-page, meaningful KPIs & charts
import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------- PAGE ----------
st.set_page_config(page_title="Baba Jina | EDA Dashboard", layout="wide")

CSS = """
<style>
.card {background:#fff;border-radius:14px;padding:16px 18px;border:1px solid #eef0f4;box-shadow:0 4px 18px rgba(0,0,0,0.06)}
.kpi-title{font-size:12px;color:#6b7280}
.kpi-val{font-size:28px;font-weight:800;margin-top:2px}
.kpi-sub{font-size:11px;color:#9aa2af}
.h2{font-size:20px;font-weight:800;margin:6px 0 12px}
.section-sub{font-size:12px;color:#64748b;margin-bottom:6px}
.empty{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:12px;padding:16px;color:#475569}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

DATA_DIR = "data"
SALES_XLSX     = os.path.join(DATA_DIR, "(3) BABA JINA SALES DATA.xlsx")
SUPPLIERS_XLSX = os.path.join(DATA_DIR, "suppliers_data_cleaned.xlsx")

# ---------- LOADERS ----------
@st.cache_data(show_spinner=False)
def load_sales_pack():
    """Prefer compact parquet artifacts if present; else load Excel and derive needed aggregates."""
    p_monthly = os.path.join(DATA_DIR, "sales_monthly.parquet")
    p_cat     = os.path.join(DATA_DIR, "sales_by_category.parquet")
    p_slim    = os.path.join(DATA_DIR, "sales_slim.parquet")

    if os.path.exists(p_monthly) and os.path.exists(p_cat):
        monthly = pd.read_parquet(p_monthly)
        by_cat  = pd.read_parquet(p_cat)
        slim    = pd.read_parquet(p_slim) if os.path.exists(p_slim) else None
        return {"monthly": monthly, "by_cat": by_cat, "slim": slim}

    if not os.path.exists(SALES_XLSX):
        return {"monthly": None, "by_cat": None, "slim": None}

    df = pd.read_excel(SALES_XLSX)
    # normalize
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
        df["Year"]  = df["Date"].dt.year
        df["month_num"] = df["Date"].dt.month
    # revenue
    if "Total_Amount" in df.columns:
        df["Revenue"] = pd.to_numeric(df["Total_Amount"], errors="coerce")
    else:
        q = pd.to_numeric(df.get("Quantity", np.nan), errors="coerce")
        p = pd.to_numeric(df.get("Unit_Price", np.nan), errors="coerce")
        df["Revenue"] = q * p
    df["Category"] = df.get("Category", "Unknown").fillna("Unknown")
    df["Customer_ID"] = df.get("Customer_ID")

    monthly = (
        df.dropna(subset=["Month"])
          .groupby("Month", as_index=False)["Revenue"].sum()
          .sort_values("Month")
    )
    by_cat = (
        df.groupby("Category", as_index=False)["Revenue"].sum()
          .sort_values("Revenue", ascending=False)
    )
    slim = df[["Date","Month","Year","month_num","Category","Customer_ID","Revenue"]].copy()
    return {"monthly": monthly, "by_cat": by_cat, "slim": slim}

@st.cache_data(show_spinner=False)
def load_suppliers():
    if not os.path.exists(SUPPLIERS_XLSX):
        return None
    sup = pd.read_excel(SUPPLIERS_XLSX)

    # Order_Amount
    if "Amount" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["Amount"], errors="coerce")
    elif "AMOUNT" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["AMOUNT"], errors="coerce")
    else:
        price = pd.to_numeric(sup.get("Price"), errors="coerce")
        ctn   = pd.to_numeric(sup.get("CTN_Box"), errors="coerce")
        sup["Order_Amount"] = price * ctn

    # Year + Category
    if "New_Year" in sup.columns:
        sup["Year"] = sup["New_Year"]
    elif "Year" not in sup.columns:
        sup["Year"] = np.nan
    sup["Category"] = sup.get("Category", "Unknown").fillna("Unknown")

    # ShopName guess
    for g in ["Shop","Supplier","Supplier_Name","Vendor","Name"]:
        if g in sup.columns:
            sup["ShopName"] = sup[g].astype(str)
            break
    if "ShopName" not in sup.columns:
        sup["ShopName"] = "Unknown"

    return sup.dropna(subset=["Order_Amount"])

sales_pack = load_sales_pack()
suppliers  = load_suppliers()

# ---------- FILTERS ----------
with st.sidebar:
    st.header("Filters")

    # Sales date filter
    if sales_pack["slim"] is not None and "Date" in sales_pack["slim"].columns:
        s = sales_pack["slim"].dropna(subset=["Date"]).copy()
        min_d, max_d = s["Date"].min().date(), s["Date"].max().date()
        d1, d2 = st.date_input("Sales date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        mask = (s["Date"].dt.date >= d1) & (s["Date"].dt.date <= d2)
        sales_rows = s[mask]
        # recompute aggregates within selection
        if "Month" in s.columns:
            sales_monthly = sales_rows.groupby("Month", as_index=False)["Revenue"].sum()
        else:
            sales_monthly = sales_pack["monthly"]
        sales_by_cat = (sales_rows.groupby("Category", as_index=False)["Revenue"].sum()
                        .sort_values("Revenue", ascending=False))
    else:
        sales_rows   = sales_pack["slim"]
        sales_monthly= sales_pack["monthly"]
        sales_by_cat = sales_pack["by_cat"]

    # Suppliers year filter
    if suppliers is not None and suppliers["Year"].notna().any():
        years = sorted([int(y) for y in suppliers["Year"].dropna().unique()])
        year_sel = st.multiselect("Supplier years", years, default=years)
        sup_f = suppliers[suppliers["Year"].isin(year_sel)] if years else suppliers.copy()
    else:
        sup_f = suppliers

# ---------- KPI HELPERS ----------
def fmt_money(x):
    try:
        x = float(x)
    except Exception:
        return "$0"
    if x >= 1_000_000: return f"${x/1_000_000:.1f}M"
    if x >= 1_000:     return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"

# ---------- ROW 1: KPIs ----------
st.markdown('<div class="h2">Key Indicators</div>', unsafe_allow_html=True)
k1, k2, k3, k4, k5 = st.columns([1,1,1,1,1])

with k1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Revenue (YTD)</div>', unsafe_allow_html=True)
    if sales_rows is not None and not sales_rows.empty:
        ytd_year = pd.Timestamp.today().year
        ytd = sales_rows[sales_rows["Date"].dt.year == ytd_year]["Revenue"].sum()
        st.markdown(f'<div class="kpi-val">{fmt_money(ytd)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">$0</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with k2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Average Order Value</div>', unsafe_allow_html=True)
    if sales_rows is not None and not sales_rows.empty:
        aov = sales_rows["Revenue"].mean()
        st.markdown(f'<div class="kpi-val">{fmt_money(aov)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">$0</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with k3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Active Customers</div>', unsafe_allow_html=True)
    if sales_rows is not None and not sales_rows.empty and "Customer_ID" in sales_rows.columns:
        st.markdown(f'<div class="kpi-val">{sales_rows["Customer_ID"].nunique():,}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">0</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with k4:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Supplier Spend (YTD)</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty and sup_f["Year"].notna().any():
        ytd_year = pd.Timestamp.today().year
        spend_ytd = sup_f[sup_f["Year"] == ytd_year]["Order_Amount"].sum()
        st.markdown(f'<div class="kpi-val">{fmt_money(spend_ytd)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">$0</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with k5:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-title">Supplier Dependency (Top 2)</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty:
        by_shop = (sup_f.groupby("ShopName", as_index=False)["Order_Amount"].sum()
                         .sort_values("Order_Amount", ascending=False))
        total = by_shop["Order_Amount"].sum()
        pct = (by_shop.head(2)["Order_Amount"].sum() / total * 100) if total else 0
        st.markdown(f'<div class="kpi-val">{pct:.1f}%</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="kpi-val">0%</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# ---------- ROW 2: SALES (left, wider) + SUPPLIERS (right) ----------
left, right = st.columns([1.6, 1.0])

# SALES COLUMN
with left:
    st.markdown('<div class="h2">Sales (EDA)</div>', unsafe_allow_html=True)

    # 1) Monthly Revenue Trend
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Monthly Revenue Trend</div>', unsafe_allow_html=True)
    if sales_monthly is not None and not sales_monthly.empty:
        fig = px.area(sales_monthly, x="Month", y="Revenue")
        fig.update_layout(height=280, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="sales_monthly_trend")
    else:
        st.markdown('<div class="empty">No monthly sales available.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 2) Revenue by Category (Top 8)
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Revenue by Product Category (Top 8)</div>', unsafe_allow_html=True)
    if sales_by_cat is not None and not sales_by_cat.empty:
        top8 = sales_by_cat.head(8)
        fig = px.bar(top8, x="Category", y="Revenue", text_auto=".2s")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=280, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="sales_by_category")
    else:
        st.markdown('<div class="empty">No category breakdown available.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 3) Year x Month Heatmap (Seasonality)
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Seasonality Heatmap (Year × Month)</div>', unsafe_allow_html=True)
    if sales_rows is not None and not sales_rows.empty and {"Year","month_num"}.issubset(sales_rows.columns):
        mat = (sales_rows
               .groupby(["Year","month_num"], as_index=False)["Revenue"].sum())
        # ensure 1..12 rows per year
        all_months = pd.DataFrame({"month_num": range(1,13)})
        heat = (mat.merge(all_months, how="right", on="month_num")
                   .pivot_table(index="Year", columns="month_num", values="Revenue", aggfunc="sum")
                   .fillna(0).sort_index())
        heat.columns = [str(c) for c in heat.columns]
        fig = px.imshow(heat, aspect="auto", color_continuous_scale="Blues",
                        labels=dict(x="Month", y="Year", color="Revenue"))
        fig.update_layout(height=300, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="sales_seasonality_heatmap")
    else:
        st.markdown('<div class="empty">Not enough date columns to compute seasonality.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# SUPPLIERS COLUMN
with right:
    st.markdown('<div class="h2">Suppliers (EDA)</div>', unsafe_allow_html=True)

    # 4) Supplier Spend by Category over Years
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Spend by Category over Years</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty and sup_f["Year"].notna().any():
        agg = sup_f.groupby(["Year","Category"], as_index=False)["Order_Amount"].sum()
        fig = px.bar(agg, x="Year", y="Order_Amount", color="Category", barmode="stack")
        fig.update_layout(height=300, margin=dict(l=6,r=6,t=6,b=6), legend_title_text="")
        st.plotly_chart(fig, use_container_width=True, key="suppliers_spend_stack")
    else:
        st.markdown('<div class="empty">Need Year & Category columns in suppliers data.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 5) Top 5 Shops by Total Spend (stacked by category)
    st.markdown('<div class="card" style="margin-top:12px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Top 5 Shops by Total Spend (by Category)</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty:
        by_shop_cat = sup_f.groupby(["ShopName","Category"], as_index=False)["Order_Amount"].sum()
        top5_shops = (by_shop_cat.groupby("ShopName", as_index=False)["Order_Amount"].sum()
                                   .sort_values("Order_Amount", ascending=False).head(5)["ShopName"])
        plot_df = by_shop_cat[by_shop_cat["ShopName"].isin(top5_shops)]
        fig = px.bar(plot_df, x="ShopName", y="Order_Amount", color="Category", barmode="stack")
        fig.update_layout(height=300, margin=dict(l=6,r=6,t=6,b=6), legend_title_text="")
        st.plotly_chart(fig, use_container_width=True, key="suppliers_top5_stacked")
    else:
        st.markdown('<div class="empty">No supplier rows to rank.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- FOOTER ----------
st.caption("EDA dashboard — focused on core trends and concentrations. Forecasting to be added later.")
