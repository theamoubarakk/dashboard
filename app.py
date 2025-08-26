# app.py — Baba Jina | EDA One Page (compact, no scroll)

import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ================== PAGE / THEME ==================
st.set_page_config(page_title="Baba Jina | EDA One Page", layout="wide")

# Adjust padding so big title never clips
st.markdown(
    """
    <style>
      .block-container {
          padding-top: 2.2rem !important;   /* more top space */
          padding-bottom: 0.4rem;
      }
      h2, h3 {
          margin-top: .25rem;
          margin-bottom: .35rem;
      }
      .stPlotlyChart {
          margin-top: .2rem;
          margin-bottom: .2rem;
      }
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
PALETTE = ["#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#F97316", "#84CC16"]
CAT_COLORS = {
    "Christmas": "#2563EB",
    "Toys": "#10B981",
    "Summer": "#F59E0B",
    "Halloween": "#EF4444",
    "Birthdays/Celebrations": "#8B5CF6",
    "Fees/Admin": "#64748B",
}
def color_for(keys):
    return [CAT_COLORS.get(k, PALETTE[i % len(PALETTE)]) for i, k in enumerate(keys)]

# ================== LOADERS ==================
@st.cache_data(show_spinner=False)
def load_sales():
    if not os.path.exists(SALES_XLSX):
        return None
    df = pd.read_excel(SALES_XLSX)

    # Dates/periods
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
        df["Year"]  = df["Date"].dt.year

    # Revenue
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

    # Order amount
    if "Amount" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["Amount"], errors="coerce")
    elif "AMOUNT" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["AMOUNT"], errors="coerce")
    else:
        sup["Order_Amount"] = (
            pd.to_numeric(sup.get("Price", 0), errors="coerce")
            * pd.to_numeric(sup.get("CTN_Box", 0), errors="coerce")
        )

    # Year
    if "New_Year" in sup.columns:
        sup["Year"] = sup["New_Year"]

    # Shop name normalization
    for guess in ["Shop", "ShopName", "Supplier", "Vendor", "Name"]:
        if guess in sup.columns:
            sup["ShopName"] = sup[guess].astype(str)
            break
    if "ShopName" not in sup.columns:
        sup["ShopName"] = "Unknown"

    # Category fill
    sup["Category"] = sup.get("Category", "Unknown").fillna("Unknown")
    return sup.dropna(subset=["Order_Amount"])

sales = load_sales()
suppliers = load_suppliers()

# ================== SIZING (compact to avoid scroll) ==================
H_TALL   = 210
H_MED    = 190
H_SHORT  = 150
MARGIN   = dict(l=4, r=4, t=6, b=4)

# ================== LAYOUT ==================
col_left, col_right = st.columns([1, 1])

# ----- LEFT (2 charts) -----
with col_left:
    if sales is not None and "Month" in sales.columns:
        st.subheader("Monthly Revenue Trend (2017–2024)")
        monthly = (
            sales.groupby("Month", as_index=False)["Revenue"]
            .sum().sort_values("Month")
        )
        fig1 = px.line(
            monthly, x="Month", y="Revenue", markers=True,
            color_discrete_sequence=[PALETTE[0]],
        )
        fig1.update_layout(height=H_TALL, margin=MARGIN, showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    if suppliers is not None and "Year" in suppliers.columns:
        st.subheader("Annual Supplier Order Amount by Category")
        cat_year = suppliers.groupby(["Year", "Category"], as_index=False)["Order_Amount"].sum()
        cats = list(cat_year["Category"].unique())
        fig2 = px.line(
            cat_year, x="Year", y="Order_Amount", color="Category", markers=True,
            color_discrete_sequence=color_for(cats),
        )
        fig2.update_layout(height=H_MED, margin=MARGIN, legend=dict(orientation="h", y=1.05, x=0))
        st.plotly_chart(fig2, use_container_width=True)

# ----- RIGHT (3 charts) -----
with col_right:
    # 1) Revenue by Product Category (dynamic ticks, raw $)
    if sales is not None:
        st.subheader("Revenue by Product Category")

        cat_rev = (
            sales.groupby("Category", as_index=False)["Revenue"]
            .sum()
            .sort_values("Revenue", ascending=False)
            .head(6)
        )

        fig3 = px.bar(
            cat_rev,
            x="Revenue",            # raw dollars
            y="Category",
            orientation="h",
            color="Category",
            text_auto=".0f",
            color_discrete_sequence=color_for(cat_rev["Category"].tolist()),
        )

        # Dynamic ticks to avoid overcrowding
        max_x = float(cat_rev["Revenue"].max() or 0)
        if max_x >= 5_000_000:
            xaxis_args = dict(tickformat="~s", tickprefix="$")                # e.g., $6.8M
            value_text = "$%{x:,.0f}"
        elif max_x >= 1_000_000:
            xaxis_args = dict(dtick=200_000, tickformat=",", ticks="outside")
            value_text = "$%{x:,.0f}"
        elif max_x >= 500_000:
            xaxis_args = dict(dtick=100_000, tickformat=",", ticks="outside")
            value_text = "$%{x:,.0f}"
        else:
            xaxis_args = dict(dtick=50_000,  tickformat=",", ticks="outside")
            value_text = "$%{x:,.0f}"

        fig3.update_layout(
            height=H_SHORT,
            margin=MARGIN,
            legend_title_text="",
            xaxis_title="Total Revenue ($)",
            xaxis=xaxis_args,
            hovermode="y"
        )
        fig3.update_traces(
            hovertemplate="<b>%{y}</b><br>Revenue: " + value_text + "<extra></extra>",
            texttemplate=value_text,
            textposition="outside",
            cliponaxis=False
        )
        st.plotly_chart(fig3, use_container_width=True)

    # 2) Category Distribution for Top 5 Shops (stacked bar)
    if suppliers is not None:
        st.subheader("Category Distribution for Top 5 Shops (by Order Amount)")

        shop_tot = (
            suppliers.groupby("ShopName", as_index=False)["Order_Amount"]
            .sum()
            .sort_values("Order_Amount", ascending=False)
        )
        top5_shops = shop_tot.head(5)["ShopName"]

        stack = (
            suppliers[suppliers["ShopName"].isin(top5_shops)]
            .groupby(["ShopName", "Category"], as_index=False)["Order_Amount"]
            .sum()
        )

        shop_order = (
            shop_tot.set_index("ShopName")
            .loc[top5_shops]["Order_Amount"]
            .sort_values(ascending=False)
            .index.astype(str)
            .tolist()
        )
        stack["ShopName"] = stack["ShopName"].astype(str)

        unique_cats = stack["Category"].unique().tolist()
        color_map = {c: CAT_COLORS.get(c) for c in unique_cats}
        if any(v is None for v in color_map.values()):
            filled = color_for(unique_cats)
            for c, col in zip(unique_cats, filled):
                color_map[c] = color_map.get(c) or col

        fig4 = px.bar(
            stack,
            x="ShopName",
            y="Order_Amount",
            color="Category",
            barmode="stack",
            category_orders={"ShopName": shop_order},
            text_auto=".2s",
            color_discrete_map=color_map,
        )
        fig4.update_layout(
            height=H_SHORT,
            margin=MARGIN,
            legend_title_text="Category",
            yaxis=dict(tickformat=","),
            hovermode="x unified",
        )
        st.plotly_chart(fig4, use_container_width=True)

    # 3) Quantity per Year
    if suppliers is not None and "T_QTY" in suppliers.columns:
        st.subheader("Total Product Quantity Ordered per Year")
        qty = suppliers.groupby("Year", as_index=False)["T_QTY"].sum()
        fig5 = px.bar(qty, x="Year", y="T_QTY", text_auto=".2s",
                      color_discrete_sequence=[PALETTE[0]])
        fig5.update_layout(height=H_SHORT, margin=MARGIN)
        st.plotly_chart(fig5, use_container_width=True)

# ================== FOOTER ==================
st.caption(
    "One-page EDA — Monthly trend, category revenue, supplier trends & concentration. "
    "Compact layout designed to fit without scrolling."
)
