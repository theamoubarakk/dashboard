# app.py — One-Page EDA (2 charts left, 3 charts right)
import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------- PAGE ----------
st.set_page_config(page_title="Baba Jina | EDA (One Page)", layout="wide")
st.markdown("""
<style>
.wrap{max-width:1400px;margin:0 auto}
.card{background:#fff;border-radius:14px;padding:10px 12px;border:1px solid #eef0f4;box-shadow:0 4px 14px rgba(0,0,0,.05)}
.h2{font-size:20px;font-weight:800;margin:8px 0 12px}
.section-sub{font-size:12px;color:#64748b;margin:0 0 6px}
.empty{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px;color:#475569}
</style>
""", unsafe_allow_html=True)

# ---------- FILES ----------
DATA_DIR = "data"
SALES_XLSX     = os.path.join(DATA_DIR, "(3) BABA JINA SALES DATA.xlsx")
SUPPLIERS_XLSX = os.path.join(DATA_DIR, "suppliers_data_cleaned.xlsx")

# ---------- COLORS (consistent palette) ----------
CAT_COLORS = {
    "Christmas": "#4C78A8",
    "Toys": "#F58518",
    "Halloween": "#E45756",
    "Summer": "#72B7B2",
    "Birthdays/Celebrations": "#54A24B",
    "Fees/Admin": "#B279A2",
    "Unknown": "#9C9C9C",
}
COLOR_SEQ = list(CAT_COLORS.values())

# ---------- LOADERS ----------
@st.cache_data(show_spinner=False)
def load_sales():
    if not os.path.exists(SALES_XLSX):
        return None
    df = pd.read_excel(SALES_XLSX)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
        df["Year"]  = df["Date"].dt.year
        df["month_num"] = df["Date"].dt.month
    if "Total_Amount" in df.columns:
        df["Revenue"] = pd.to_numeric(df["Total_Amount"], errors="coerce")
    else:
        q = pd.to_numeric(df.get("Quantity", np.nan), errors="coerce")
        p = pd.to_numeric(df.get("Unit_Price", np.nan), errors="coerce")
        df["Revenue"] = q * p
    df["Category"] = df.get("Category", "Unknown").fillna("Unknown")
    return df

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

    # Year & Category
    if "New_Year" in sup.columns:
        sup["Year"] = sup["New_Year"]
    elif "Year" not in sup.columns:
        sup["Year"] = np.nan
    sup["Category"] = sup.get("Category", "Unknown").fillna("Unknown")

    # Shop name guess
    for g in ["Shop","Supplier","Supplier_Name","Vendor","Name"]:
        if g in sup.columns:
            sup["ShopName"] = sup[g].astype(str)
            break
    if "ShopName" not in sup.columns:
        sup["ShopName"] = "Unknown"

    # Quantity column (optional)
    qty_col = None
    for c in ["T_QTY","Total_Qty","Total_QTY","Quantity","QTY","Qty"]:
        if c in sup.columns:
            qty_col = c
            break
    return sup, qty_col

sales = load_sales()
suppliers_pack = load_suppliers()
suppliers, qty_col = suppliers_pack if suppliers_pack is not None else (None, None)

# ---------- FILTERS ----------
with st.sidebar:
    st.header("Filters")
    # Sales date
    if sales is not None and "Date" in sales.columns:
        s = sales.dropna(subset=["Date"])
        min_d, max_d = s["Date"].min().date(), s["Date"].max().date()
        d1, d2 = st.date_input("Sales date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        mask = (s["Date"].dt.date >= d1) & (s["Date"].dt.date <= d2)
        sales_f = s[mask]
    else:
        sales_f = sales

    # Supplier years
    if suppliers is not None and suppliers["Year"].notna().any():
        years = sorted([int(y) for y in suppliers["Year"].dropna().unique()])
        year_sel = st.multiselect("Supplier years", years, default=years)
        sup_f = suppliers[suppliers["Year"].isin(year_sel)] if years else suppliers.copy()
    else:
        sup_f = suppliers

st.markdown('<div class="wrap">', unsafe_allow_html=True)
st.markdown('<div class="h2">Exploratory Data Overview</div>', unsafe_allow_html=True)

# ---------- LAYOUT: 2 charts left (taller), 3 charts right (compact) ----------
left, right = st.columns([1.3, 1.0])

# ===== LEFT COLUMN (2 charts) =====
with left:
    # 1) Monthly Sales Trend
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Monthly Sales Trend (2017–2024)</div>', unsafe_allow_html=True)
    if sales_f is not None and not sales_f.empty and "Month" in sales_f.columns:
        m = (sales_f.groupby("Month", as_index=False)["Revenue"].sum()
                    .sort_values("Month"))
        fig = px.line(m, x="Month", y="Revenue", markers=True, template="plotly_white")
        fig.update_traces(line=dict(width=2), marker=dict(size=4))
        fig.update_layout(height=280, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="l_trend")
    else:
        st.markdown('<div class="empty">No monthly sales available.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 2) Monthly Revenue Heatmap
    st.markdown('<div class="card" style="margin-top:10px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Monthly Revenue Heatmap (Year × Month)</div>', unsafe_allow_html=True)
    if sales_f is not None and not sales_f.empty and {"Year","month_num"}.issubset(sales_f.columns):
        mat = sales_f.groupby(["Year","month_num"], as_index=False)["Revenue"].sum()
        heat = (mat.pivot_table(index="Year", columns="month_num", values="Revenue", aggfunc="sum")
                   .fillna(0).sort_index())
        heat.columns = [str(m) for m in heat.columns]
        fig = px.imshow(heat, aspect="auto", template="plotly_white",
                        color_continuous_scale=["#dbeafe","#60a5fa","#1d4ed8"],
                        labels=dict(x="Month", y="Year", color="Revenue"))
        fig.update_layout(height=280, margin=dict(l=6,r=6,t=6,b=6))
        st.plotly_chart(fig, use_container_width=True, key="l_heat")
    else:
        st.markdown('<div class="empty">Not enough date fields for seasonality.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ===== RIGHT COLUMN (3 charts) =====
with right:
    # 3) Total Revenue by Product Category (horizontal)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Total Revenue by Product Category</div>', unsafe_allow_html=True)
    if sales_f is not None and not sales_f.empty:
        by_cat = (sales_f.groupby("Category", as_index=False)["Revenue"].sum()
                         .sort_values("Revenue", ascending=True))
        fig = px.bar(by_cat, x="Revenue", y="Category", orientation="h",
                     template="plotly_white", color="Category",
                     color_discrete_map=CAT_COLORS)
        fig.update_layout(height=210, margin=dict(l=6,r=6,t=6,b=6), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key="r_cat")
    else:
        st.markdown('<div class="empty">No category breakdown available.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 4) Category Mix across Top 5 Shops (stacked)
    st.markdown('<div class="card" style="margin-top:10px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Category Mix across Top 5 Shops (by Order Amount)</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty:
        by_shop_cat = sup_f.groupby(["ShopName","Category"], as_index=False)["Order_Amount"].sum()
        top5 = (by_shop_cat.groupby("ShopName", as_index=False)["Order_Amount"].sum()
                            .sort_values("Order_Amount", ascending=False).head(5)["ShopName"])
        plot_df = by_shop_cat[by_shop_cat["ShopName"].isin(top5)]
        fig = px.bar(plot_df, x="ShopName", y="Order_Amount", color="Category",
                     barmode="stack", template="plotly_white",
                     color_discrete_map=CAT_COLORS)
        fig.update_layout(height=210, margin=dict(l=6,r=6,t=6,b=6), legend_title_text="")
        st.plotly_chart(fig, use_container_width=True, key="r_top5")
    else:
        st.markdown('<div class="empty">No supplier rows to rank.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 5) Total Product Quantity Ordered per Year (if a quantity column exists)
    st.markdown('<div class="card" style="margin-top:10px;">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Total Product Quantity Ordered per Year</div>', unsafe_allow_html=True)
    if sup_f is not None and not sup_f.empty and qty_col is not None:
        q = (sup_f.groupby("Year", as_index=False)[qty_col].sum()
                 .rename(columns={qty_col: "Total_Quantity"}))
        fig = px.bar(q, x="Year", y="Total_Quantity", template="plotly_white", text_auto=".3s",
                     color_discrete_sequence=["#4C78A8"])
        fig.update_traces(textposition="outside")
        fig.update_layout(height=210, margin=dict(l=6,r=6,t=6,b=6), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key="r_qty")
    else:
        st.markdown('<div class="empty">Quantity column not found in suppliers data.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ---------- FOOTER ----------
st.caption("One-page EDA — trend & seasonality on the left; category revenue, top shops mix, and yearly quantity on the right. Colors unified with the report.")
