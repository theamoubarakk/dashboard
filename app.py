# app.py — EDA One Page (title padding + nicer palette)

import os
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# ---------- PAGE ----------
st.set_page_config(page_title="Baba Jina | EDA One Page", layout="wide")

# Fix cropped header + lighter page padding
st.markdown(
    """
    <style>
      .block-container {padding-top: 2.25rem; padding-bottom: 0.5rem;}
      h2, h3 {margin-top: 0.25rem; margin-bottom: 0.35rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## Exploratory Data Overview")

DATA_DIR = "data"
SALES_XLSX     = os.path.join(DATA_DIR, "(3) BABA JINA SALES DATA.xlsx")
SUPPLIERS_XLSX = os.path.join(DATA_DIR, "suppliers_data_cleaned.xlsx")

# ---------- PALETTE ----------
# Soft modern palette (works on light/dark + colorblind-friendly hues)
PALETTE = [
    "#2563EB",  # blue
    "#10B981",  # teal
    "#F59E0B",  # amber
    "#EF4444",  # red
    "#8B5CF6",  # violet
    "#14B8A6",  # cyan-teal
    "#F97316",  # orange
    "#84CC16",  # lime
]

# Optional named colors for categories you have
CAT_COLORS = {
    "Christmas": "#2563EB",
    "Toys": "#10B981",
    "Summer": "#F59E0B",
    "Halloween": "#EF4444",
    "Birthdays/Celebrations": "#8B5CF6",
    "Fees/Admin": "#64748B",
}

def color_for_list(keys):
    # Build a color sequence that respects CAT_COLORS where possible
    seq = []
    for i, k in enumerate(keys):
        seq.append(CAT_COLORS.get(k, PALETTE[i % len(PALETTE)]))
    return seq

# ---------- LOADERS ----------
@st.cache_data(show_spinner=False)
def load_sales():
    if not os.path.exists(SALES_XLSX):
        return None
    df = pd.read_excel(SALES_XLSX)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
        df["Year"] = df["Date"].dt.year
    # Revenue normalization
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
    sup = pd.read_excel(SUPPLIERS_XLSX)
    # Order amount normalization
    if "Amount" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["Amount"], errors="coerce")
    elif "AMOUNT" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["AMOUNT"], errors="coerce")
    else:
        sup["Order_Amount"] = pd.to_numeric(sup.get("Price", 0), errors="coerce") * pd.to_numeric(sup.get("CTN_Box", 0), errors="coerce")
    # Year normalization
    if "New_Year" in sup.columns:
        sup["Year"] = sup["New_Year"]
    # Shop name best-guess
    for g in ["Shop", "ShopName", "Supplier", "Vendor", "Name"]:
        if g in sup.columns:
            sup["ShopName"] = sup[g].astype(str)
            break
    if "ShopName" not in sup.columns:
        sup["ShopName"] = "Unknown"
    sup["Category"] = sup.get("Category", "Unknown").fillna("Unknown")
    return sup.dropna(subset=["Order_Amount"])

sales = load_sales()
suppliers = load_suppliers()

# ---------- LAYOUT (2 left, 3 right) ----------
# Tight heights + margins so everything fits 1 page on laptops (no scroll)
H_SMALL  = 210
H_MEDIUM = 230
MARGIN   = dict(l=6, r=6, t=10, b=6)

col_left, col_right = st.columns([1, 1])

# LEFT COLUMN (2 charts)
with col_left:
    if sales is not None and "Month" in sales.columns:
        st.subheader("Monthly Revenue Trend (2017–2024)")
        monthly = sales.groupby("Month", as_index=False)["Revenue"].sum().sort_values("Month")
        fig1 = px.line(monthly, x="Month", y="Revenue", markers=True,
                       color_discrete_sequence=[PALETTE[0]])
        fig1.update_layout(height=H_MEDIUM, margin=MARGIN, showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    if suppliers is not None and "Year" in suppliers.columns and "Category" in suppliers.columns:
        st.subheader("Annual Order Amount Trend by Category")
        agg = suppliers.groupby(["Year", "Category"], as_index=False)["Order_Amount"].sum().sort_values(["Year", "Category"])
        # sort legend consistently
        cats = list(agg["Category"].unique())
        fig2 = px.line(
            agg, x="Year", y="Order_Amount", color="Category", markers=True,
            color_discrete_sequence=color_for_list(cats),
            category_orders={"Category": cats}
        )
        fig2.update_layout(height=H_SMALL, margin=MARGIN, legend_title_text="", legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
        st.plotly_chart(fig2, use_container_width=True)

# RIGHT COLUMN (3 charts)
with col_right:
    if sales is not None:
        st.subheader("Revenue by Product Category")
        cat_rev = sales.groupby("Category", as_index=False)["Revenue"].sum().sort_values("Revenue", ascending=False).head(6)
        fig3 = px.bar(
            cat_rev
