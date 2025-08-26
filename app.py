# app.py — EDA One-Page (2 left + 3 right), compact & consistent colors

import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------- PAGE ----------
st.set_page_config(page_title="Baba Jina | EDA One Page", layout="wide")

# Tiny CSS to compress spacing so it fits a single screen
st.markdown("""
<style>
h2, h3 {margin: 0 0 6px 0;}
.block-container {padding-top: 0.6rem; padding-bottom: 0.6rem;}
hr {margin: 10px 0;}
.small-title {font-weight: 700; margin: 6px 0 4px;}
</style>
""", unsafe_allow_html=True)

st.markdown("## Exploratory Data Overview")

DATA_DIR = "data"
SALES_XLSX     = os.path.join(DATA_DIR, "(3) BABA JINA SALES DATA.xlsx")
SUPPLIERS_XLSX = os.path.join(DATA_DIR, "suppliers_data_cleaned.xlsx")

# Locked colors by category (same across all charts)
CAT_COLORS = {
    "Christmas": "#3b82f6",
    "Toys": "#22c55e",
    "Halloween": "#ef4444",
    "Summer": "#10b981",
    "Birthdays/Celebrations": "#6366f1",
    "Fees/Admin": "#a3a3a3",
    "Unknown": "#94a3b8",
}

# ---------- LOADERS ----------
@st.cache_data(show_spinner=False)
def load_sales():
    if not os.path.exists(SALES_XLSX): 
        return None
    df = pd.read_excel(SALES_XLSX)
    df["Date"]  = pd.to_datetime(df.get("Date"), errors="coerce")
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    df["Year"]  = df["Date"].dt.year
    # Revenue fallback if Total_Amount not present
    if "Total_Amount" in df.columns:
        df["Revenue"] = pd.to_numeric(df["Total_Amount"], errors="coerce")
    else:
        q = pd.to_numeric(df.get("Quantity", 0), errors="coerce")
        p = pd.to_numeric(df.get("Unit_Price", 0), errors="coerce")
        df["Revenue"] = q * p
    df["Category"] = df.get("Category", "Unknown").fillna("Unknown")
    return df.dropna(subset=["Revenue"])

@st.cache_data(show_spinner=False)
def load_suppliers():
    if not os.path.exists(SUPPLIERS_XLSX): 
        return None
    df = pd.read_excel(SUPPLIERS_XLSX)

    if "Amount" in df.columns:
        df["Order_Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    elif "AMOUNT" in df.columns:
        df["Order_Amount"] = pd.to_numeric(df["AMOUNT"], errors="coerce")
    else:
        price = pd.to_numeric(df.get("Price", 0), errors="coerce")
        ctn   = pd.to_numeric(df.get("CTN_Box", 0), errors="coerce")
        df["Order_Amount"] = price * ctn

    if "New_Year" in df.columns:
        df["Year"] = df["New_Year"]

    # Normalize shop name
    shop_col = None
    for g in ["ShopName", "Shop", "Supplier", "Supplier_Name", "Vendor", "Name"]:
        if g in df.columns:
            shop_col = g
            break
    if shop_col is None:
        df["ShopName"] = "Unknown"
        shop_col = "ShopName"

    df["ShopName"] = df[shop_col].astype(str)
    df["Category"] = df.get("Category", "Unknown").fillna("Unknown")
    return df.dropna(subset=["Order_Amount"])

sales     = load_sales()
suppliers = load_suppliers()

# Pre-aggregations for speed & clarity
sales_monthly = None
sales_by_cat  = None
if sales is not None and not sales.empty:
    if "Month" in sales.columns:
        sales_monthly = sales.groupby("Month", as_index=False)["Revenue"].sum()
    sales_by_cat = (
        sales.groupby("Category", as_index=False)["Revenue"]
             .sum().sort_values("Revenue", ascending=False).head(6)
    )

sup_cat_year = None
if suppliers is not None and not suppliers.empty:
    sup_cat_year = (
        suppliers.groupby(["Year", "Category"], as_index=False)["Order_Amount"].sum()
    )

# ---------- LAYOUT: 2 charts (left) + 3 charts (right) ----------
# Heights trimmed to 210px each; margins reduced to minimize scroll
H = 210
M = dict(l=4, r=4, t=22, b=4)

left_col, right_col = st.columns([1.25, 1.25])  # equal widths

# LEFT — Chart 1 & 2
with left_col:
    # 1) Monthly Revenue Trend
    st.markdown('<div class="small-title">Monthly Revenue Trend (2017–2024)</div>', unsafe_allow_html=True)
    if sales_monthly is not None and not sales_monthly.empty:
        fig1 = px.line(sales_monthly, x="Month", y="Revenue", markers=True)
        fig1.update_traces(line=dict(width=2))
        fig1.update_layout(height=H, margin=M, legend_title_text="")
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("No monthly sales available.")

    # 2) Annual Order Amount Trend by Category (line)
    st.markdown('<div class="small-title">Annual Order Amount Trend by Category</div>', unsafe_allow_html=True)
    if sup_cat_year is not None and not sup_cat_year.empty:
        # keep color order stable
        color_seq = [CAT_COLORS.get(c, "#64748b") for c in sup_cat_year["Category"].unique()]
        fig2 = px.line(
            sup_cat_year, x="Year", y="Order_Amount", color="Category",
            markers=True, color_discrete_sequence=color_seq
        )
        fig2.update_traces(line=dict(width=2))
        fig2.update_layout(height=H, margin=M, legend_title_text="", legend=dict(font=dict(size=9)))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Supplier/year breakdown not available.")

# RIGHT — Chart 3, 4, 5
with right_col:
    # 3) Revenue by Product Category (horizontal bar)
    st.markdown('<div class="small-title">Revenue by Product Category</div>', unsafe_allow_html=True)
    if sales_by_cat is not None and not sales_by_cat.empty:
        # lock colors to categories shown
        color_seq = [CAT_COLORS.get(c, "#64748b") for c in sales_by_cat["Category"]]
        fig3 = px.bar(
            sales_by_cat, x="Revenue", y="Category",
            orientation="h", text_auto=".2s",
            color="Category", color_discrete_sequence=color_seq
        )
        # show one color per bar but hide legend (labels already on axis)
        fig3.update_layout(showlegend=False, height=H, margin=M)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No category breakdown available.")

    # 4) Category Mix across Top 5 Shops (stacked)
    st.markdown('<div class="small-title">Category Mix across Top 5 Shops</div>', unsafe_allow_html=True)
    if suppliers is not None and not suppliers.empty:
        top5 = (
            suppliers.groupby("ShopName", as_index=False)["Order_Amount"]
                     .sum().sort_values("Order_Amount", ascending=False).head(5)
        )
        sup_top = suppliers[suppliers["ShopName"].isin(top5["ShopName"])]
        color_seq = [CAT_COLORS.get(c, "#64748b") for c in sup_top["Category"].unique()]
        fig4 = px.bar(
            sup_top, x="ShopName", y="Order_Amount", color="Category",
            barmode="stack", color_discrete_sequence=color_seq
        )
        fig4.update_layout(height=H, margin=M, legend=dict(font=dict(size=9)), legend_title_text="")
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Supplier data not available.")

    # 5) Total Product Quantity Ordered per Year (bar)
    st.markdown('<div class="small-title">Total Product Quantity Ordered per Year</div>', unsafe_allow_html=True)
    qty = None
    if suppliers is not None and "T_QTY" in suppliers.columns:
        qty = suppliers.groupby("Year", as_index=False)["T_QTY"].sum()
    if qty is not None and not qty.empty:
        fig5 = px.bar(qty, x="Year", y="T_QTY", text_auto=".2s", color_discrete_sequence=["#2563eb"])
        fig5.update_layout(height=H, margin=M, showlegend=False)
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("Quantity per year not available.")

st.caption("📊 One-page EDA — Monthly trend, category revenue, supplier trends & concentration. Colors locked for consistency with the report.")
