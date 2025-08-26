# app.py – Clean EDA Dashboard (No Correlation Matrix)

import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ---- PAGE ----
st.set_page_config(page_title="Baba Jina | EDA One Page", layout="wide")

st.markdown("## Exploratory Data Overview")

DATA_DIR = "data"
SALES_XLSX     = os.path.join(DATA_DIR, "(3) BABA JINA SALES DATA.xlsx")
SUPPLIERS_XLSX = os.path.join(DATA_DIR, "suppliers_data_cleaned.xlsx")

# ---- LOADERS ----
@st.cache_data
def load_sales():
    if not os.path.exists(SALES_XLSX): return None
    df = pd.read_excel(SALES_XLSX)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    df["Year"] = df["Date"].dt.year
    df["Revenue"] = pd.to_numeric(df.get("Total_Amount", df.get("Quantity", 0) * df.get("Unit_Price", 0)), errors="coerce")
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
    if "New_Year" in df.columns:
        df["Year"] = df["New_Year"]
    return df.dropna(subset=["Order_Amount"])

sales = load_sales()
suppliers = load_suppliers()

# ---- LAYOUT: 2 columns left (sales) | 3 columns right (suppliers + qty) ----
left_col, right_col = st.columns([2, 2])

# LEFT COL
with left_col:
    if sales is not None:
        # 1. Monthly Revenue Trend
        st.markdown("### Monthly Revenue Trend (2017–2024)")
        monthly = sales.groupby("Month", as_index=False)["Revenue"].sum()
        fig1 = px.line(monthly, x="Month", y="Revenue", markers=True)
        fig1.update_layout(height=300, margin=dict(l=6,r=6,t=30,b=6))
        st.plotly_chart(fig1, use_container_width=True)

        # 2. Annual Order Amount Trend by Category (line chart)
        st.markdown("### Annual Order Amount Trend by Category")
        if suppliers is not None:
            agg = suppliers.groupby(["Year","Category"], as_index=False)["Order_Amount"].sum()
            fig2 = px.line(agg, x="Year", y="Order_Amount", color="Category", markers=True)
            fig2.update_layout(height=300, margin=dict(l=6,r=6,t=30,b=6))
            st.plotly_chart(fig2, use_container_width=True)

# RIGHT COL
with right_col:
    if sales is not None:
        # 3. Revenue by Product Category
        st.markdown("### Revenue by Product Category")
        cat_rev = sales.groupby("Category", as_index=False)["Revenue"].sum().sort_values("Revenue", ascending=False).head(6)
        fig3 = px.bar(cat_rev, x="Revenue", y="Category", orientation="h", text_auto=".2s")
        fig3.update_layout(height=260, margin=dict(l=6,r=6,t=30,b=6))
        st.plotly_chart(fig3, use_container_width=True)

    if suppliers is not None:
        # 4. Top 5 Shops by Order Amount (stacked)
        st.markdown("### Category Mix across Top 5 Shops")
        top5 = suppliers.groupby("Shop", as_index=False)["Order_Amount"].sum().sort_values("Order_Amount", ascending=False).head(5)
        merged = suppliers[suppliers["Shop"].isin(top5["Shop"])]
        fig4 = px.bar(merged, x="Shop", y="Order_Amount", color="Category", barmode="stack")
        fig4.update_layout(height=260, margin=dict(l=6,r=6,t=30,b=6))
        st.plotly_chart(fig4, use_container_width=True)

        # 5. Total Product Quantity Ordered per Year
        st.markdown("### Total Product Quantity Ordered per Year")
        qty = suppliers.groupby("Year", as_index=False)["T_QTY"].sum() if "T_QTY" in suppliers.columns else None
        if qty is not None and not qty.empty:
            fig5 = px.bar(qty, x="Year", y="T_QTY", text_auto=".2s")
            fig5.update_layout(height=260, margin=dict(l=6,r=6,t=30,b=6))
            st.plotly_chart(fig5, use_container_width=True)

st.caption("📊 One-page EDA — Monthly trend, category revenue, supplier trends & concentration. Colors unified for consistency with the report.")
