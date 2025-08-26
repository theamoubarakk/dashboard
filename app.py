# app.py — Baba Jina | EDA One Page (polished colors + non-cropped title)

import os
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# ================== PAGE / THEME ==================
st.set_page_config(page_title="Baba Jina | EDA One Page", layout="wide")

# Fix big title clipping + tighten global paddings
st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; padding-bottom: 0.4rem; }
      h2, h3 { margin-top: .25rem; margin-bottom: .35rem; }
      /* Slightly tighter spacing for Plotly modebar */
      .stPlotlyChart { margin-top: .25rem; margin-bottom: .25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## Exploratory Data Overview")

# ================== FILES ==================
DATA_DIR        = "data"
SALES_XLSX      = os.path.join(DATA_DIR, "(3) BABA JINA SALES DATA.xlsx")
SUPPLIERS_XLSX  = os.path.join(DATA_DIR, "suppliers_data_cleaned.xlsx")

# ================== COLORS ==================
# Soft, modern, colorblind-friendly palette
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

CAT_COLORS = {
    "Christmas": "#2563EB",
    "Toys": "#10B981",
    "Summer": "#F59E0B",
    "Halloween": "#EF4444",
    "Birthdays/Celebrations": "#8B5CF6",
    "Fees/Admin": "#64748B",
}

def color_for(keys):
    seq = []
    for i, k in enumerate(keys):
        seq.append(CAT_COLORS.get(k, PALETTE[i % len(PALETTE)]))
    return seq

# ================== LOADERS ==================
@st.cache_data(show_spinner=False)
def load_sales():
    if not os.path.exists(SALES_XLSX):
        return None
    df = pd.read_excel(SALES_XLSX)
    # Normalize time
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
        df["Year"] = df["Date"].dt.year
    # Revenue
    if "Total_Amount" in df.columns:
        df["Revenue"] = pd.to_numeric(df["Total_Amount"], errors="coerce")
    else:
        q = pd.to_numeric(df.get("Quantity", 0), errors="coerce")
        p = pd.to_numeric(df.get("Unit_Price", 0), errors="coerce")
        df["Revenue"] = q * p
    # Categories
    df["Category"] = df.get("Category", "Unknown").fillna("Unknown")
    return df.dropna(subset=["Revenue"])

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
        sup["Order_Amount"] = pd.to_numeric(sup.get("Price", 0), errors="coerce") * \
                              pd.to_numeric(sup.get("CTN_Box", 0), errors="coerce")

    # Year
    if "New_Year" in sup.columns:
        sup["Year"] = sup["New_Year"]

    # Shop name
    for guess in ["Shop", "ShopName", "Supplier", "Vendor", "Name"]:
        if guess in sup.columns:
            sup["ShopName"] = sup[guess].astype(str)
            break
    if "ShopName" not in sup.columns:
        sup["ShopName"] = "Unknown"

    # Category
    sup["Category"] = sup.get("Category", "Unknown").fillna("Unknown")

    return sup.dropna(subset=["Order_Amount"])

sales = load_sales()
suppliers = load_suppliers()

# ================== SIZING (to minimize scroll) ==================
# These heights + tight margins typically fit on a 13–15" laptop as a single page.
H_TALL   = 260
H_MED    = 220
H_SHORT  = 210
MARGIN   = dict(l=6, r=6, t=8, b=6)

# ================== LAYOUT (2 left / 3 right) ==================
col_left, col_right = st.columns([1, 1])

# ----- LEFT (2 charts) -----
with col_left:
    if sales is not None and "Month" in sales.columns:
        st.subheader("Monthly Revenue Trend (2017–2024)")
        monthly = (sales
                   .groupby("Month", as_index=False)["Revenue"]
                   .sum()
                   .sort_values("Month"))
        fig1 = px.line(
            monthly, x="Month", y="Revenue", markers=True,
            color_discrete_sequence=[PALETTE[0]]
        )
        fig1.update_layout(height=H_TALL, margin=MARGIN, showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    if suppliers is not None and "Year" in suppliers.columns and "Category" in suppliers.columns:
        st.subheader("Annual Supplier Order Amount by Category")
        cat_year = (suppliers
                    .groupby(["Year", "Category"], as_index=False)["Order_Amount"]
                    .sum()
                    .sort_values(["Year", "Category"]))
        cats = list(cat_year["Category"].unique())
        fig2 = px.line(
            cat_year, x="Year", y="Order_Amount", color="Category", markers=True,
            color_discrete_sequence=color_for(cats),
            category_orders={"Category": cats}
        )
        fig2.update_layout(
            height=H_MED, margin=MARGIN,
            legend_title_text="", legend=dict(orientation="h", y=1.08, x=0)
        )
        st.plotly_chart(fig2, use_container_width=True)

# ----- RIGHT (3 charts) -----
with col_right:
    if sales is not None:
        st.subheader("Revenue by Product Category")
        cat_rev = (sales
                   .groupby("Category", as_index=False)["Revenue"]
                   .sum()
                   .sort_values("Revenue", ascending=False)
                   .head(6))
        fig3 = px.bar(
            cat_rev, x="Revenue", y="Category", orientation="h",
            color="Category",
            color_discrete_sequence=color_for(cat_rev["Category"].tolist()),
            text_auto=".2s"
        )
        fig3.update_layout(
            height=H_MED, margin=MARGIN, legend_title_text="",
            yaxis=dict(categoryorder="total ascending")
        )
        st.plotly_chart(fig3, use_container_width=True)

    if suppliers is not None:
        st.subheader("Category Mix across Top 5 Shops")
        by_shop = (suppliers.groupby("ShopName", as_index=False)["Order_Amount"]
                   .sum()
                   .sort_values("Order_Amount", ascending=False)
                   .head(5))
        top5 = suppliers[suppliers["ShopName"].isin(by_shop["ShopName"])]
        # Keep legend colors consistent across categories
        cats2 = list(top5["Category"].unique())
        fig4 = px.bar(
            top5, x="ShopName", y="Order_Amount", color="Category", barmode="stack",
            color_discrete_sequence=color_for(cats2),
        )
        fig4.update_layout(height=H_MED, margin=MARGIN, legend_title_text="")
        st.plotly_chart(fig4, use_container_width=True)

    # Quantity per year: prefer suppliers['T_QTY'], else derive from sales Quantity
    if suppliers is not None and "T_QTY" in suppliers.columns:
        qty = (suppliers.groupby("Year", as_index=False)["T_QTY"].sum()
               .sort_values("Year"))
        y_col = "T_QTY"
        y_title = "T_QTY"
    elif sales is not None and "Year" in sales.columns and "Quantity" in sales.columns:
        qty = (sales.groupby("Year", as_index=False)["Quantity"].sum()
               .sort_values("Year"))
        y_col = "Quantity"
        y_title = "Quantity"
    else:
        qty = None

    if qty is not None and not qty.empty:
        st.subheader("Total Product Quantity Ordered per Year")
        fig5 = px.bar(qty, x="Year", y=y_col, text_auto=".2s",
                      color_discrete_sequence=[PALETTE[0]])
        fig5.update_layout(height=H_SHORT, margin=MARGIN, yaxis_title=y_title)
        st.plotly_chart(fig5, use_container_width=True)

# ================== FOOTER ==================
st.caption("📊 One-page EDA — monthly revenue trend, category revenue, supplier trends & concentration. Colors unified for consistency with your report.")
