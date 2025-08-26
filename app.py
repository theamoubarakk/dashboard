# app.py — EDA One-Page Dashboard (no scroll, fixed grid)

import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ---- PAGE ----
st.set_page_config(page_title="Baba Jina | EDA One Page", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 0.5rem; padding-bottom: 0.5rem;}
h2, h3 {margin: 0 0 4px 0;}
</style>
""", unsafe_allow_html=True)

st.markdown("## Exploratory Data Overview")

DATA_DIR = "data"
SALES_XLSX     = os.path.join(DATA_DIR, "(3) BABA JINA SALES DATA.xlsx")
SUPPLIERS_XLSX = os.path.join(DATA_DIR, "suppliers_data_cleaned.xlsx")

CAT_COLORS = {
    "Christmas": "#3b82f6",
    "Toys": "#22c55e",
    "Halloween": "#ef4444",
    "Summer": "#10b981",
    "Birthdays/Celebrations": "#6366f1",
    "Fees/Admin": "#a3a3a3",
    "Unknown": "#94a3b8",
}

# ---- LOADERS ----
@st.cache_data
def load_sales():
    if not os.path.exists(SALES_XLSX): return None
    df = pd.read_excel(SALES_XLSX)
    df["Date"]  = pd.to_datetime(df.get("Date"), errors="coerce")
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    df["Year"]  = df["Date"].dt.year
    if "Total_Amount" in df.columns:
        df["Revenue"] = pd.to_numeric(df["Total_Amount"], errors="coerce")
    else:
        df["Revenue"] = pd.to_numeric(df.get("Quantity", 0), errors="coerce") * pd.to_numeric(df.get("Unit_Price", 0), errors="coerce")
    df["Category"] = df.get("Category", "Unknown").fillna("Unknown")
    return df.dropna(subset=["Revenue"])

@st.cache_data
def load_suppliers():
    if not os.path.exists(SUPPLIERS_XLSX): return None
    df = pd.read_excel(SUPPLIERS_XLSX)
    if "Amount" in df.columns:
        df["Order_Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    elif "AMOUNT" in df.columns:
        df["Order_Amount"] = pd.to_numeric(df["AMOUNT"], errors="coerce")
    else:
        df["Order_Amount"] = pd.to_numeric(df.get("Price", 0), errors="coerce") * pd.to_numeric(df.get("CTN_Box", 0), errors="coerce")
    if "New_Year" in df.columns: df["Year"] = df["New_Year"]
    df["ShopName"] = df.get("Shop", df.get("ShopName", "Unknown")).astype(str)
    df["Category"] = df.get("Category", "Unknown").fillna("Unknown")
    return df.dropna(subset=["Order_Amount"])

sales     = load_sales()
suppliers = load_suppliers()

H, M = 180, dict(l=4, r=4, t=20, b=4)

# ---------- GRID LAYOUT ----------
# Row 1
c1, c2 = st.columns(2)
if sales is not None:
    monthly = sales.groupby("Month", as_index=False)["Revenue"].sum()
    fig1 = px.line(monthly, x="Month", y="Revenue", markers=True)
    fig1.update_layout(height=H, margin=M, showlegend=False)
    c1.plotly_chart(fig1, use_container_width=True)

    cat_rev = sales.groupby("Category", as_index=False)["Revenue"].sum().sort_values("Revenue", ascending=False).head(6)
    color_seq = [CAT_COLORS.get(c, "#64748b") for c in cat_rev["Category"]]
    fig2 = px.bar(cat_rev, x="Revenue", y="Category", orientation="h", text_auto=".2s", color="Category", color_discrete_sequence=color_seq)
    fig2.update_layout(height=H, margin=M, showlegend=False)
    c2.plotly_chart(fig2, use_container_width=True)

# Row 2
c3, c4 = st.columns(2)
if suppliers is not None:
    sup_cat_year = suppliers.groupby(["Year","Category"], as_index=False)["Order_Amount"].sum()
    fig3 = px.line(sup_cat_year, x="Year", y="Order_Amount", color="Category", markers=True,
                   color_discrete_sequence=[CAT_COLORS.get(c,"#64748b") for c in sup_cat_year["Category"].unique()])
    fig3.update_layout(height=H, margin=M, legend=dict(font=dict(size=8)))
    c3.plotly_chart(fig3, use_container_width=True)

    top5 = suppliers.groupby("ShopName", as_index=False)["Order_Amount"].sum().sort_values("Order_Amount", ascending=False).head(5)
    merged = suppliers[suppliers["ShopName"].isin(top5["ShopName"])]
    fig4 = px.bar(merged, x="ShopName", y="Order_Amount", color="Category", barmode="stack",
                  color_discrete_sequence=[CAT_COLORS.get(c,"#64748b") for c in merged["Category"].unique()])
    fig4.update_layout(height=H, margin=M, legend=dict(font=dict(size=8)))
    c4.plotly_chart(fig4, use_container_width=True)

# Row 3
c5 = st.container()
if suppliers is not None and "T_QTY" in suppliers.columns:
    qty = suppliers.groupby("Year", as_index=False)["T_QTY"].sum()
    fig5 = px.bar(qty, x="Year", y="T_QTY", text_auto=".2s", color_discrete_sequence=["#2563eb"])
    fig5.update_layout(height=H, margin=M, showlegend=False)
    c5.plotly_chart(fig5, use_container_width=True)

st.caption("📊 One-page EDA — Monthly trend, category revenue, supplier trends & concentration. Colors locked for consistency with the report.")
