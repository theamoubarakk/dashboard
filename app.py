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
      h2, h3 { margin-top: .25rem; margin-bottom: .35rem; }
      .stPlotlyChart { margin-top: .2rem; margin-bottom: .2rem; }
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

    # Revenue (alias for Total_Amount)
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

# ================== SIDEBAR CONTROLS ==================
def year_list(series):
    if series is None:
        return []
    return sorted([int(y) for y in pd.Series(series).dropna().unique()])

source_choices = []
if sales is not None:
    source_choices.append("Sales (by year)")
if suppliers is not None:
    source_choices.append("Suppliers (by year)")
if not source_choices:
    st.stop()

source_pick = st.sidebar.radio("Source for 'Revenue by Product Category'", source_choices, index=0)

sales_year = None
sup_year = None

if "Sales" in source_pick and sales is not None and "Year" in sales.columns:
    s_years = year_list(sales["Year"])
    sales_year = st.sidebar.selectbox("Sales year", s_years, index=len(s_years)-1)
elif "Suppliers" in source_pick and suppliers is not None and "Year" in suppliers.columns:
    sp_years = year_list(suppliers["Year"])
    sup_year = st.sidebar.selectbox("Suppliers year", sp_years, index=len(sp_years)-1)

# ================== SIZING (compact to avoid scroll) ==================
H_TALL   = 210
H_MED    = 190
H_SHORT  = 150
MARGIN   = dict(l=4, r=4, t=6, b=4)

def pick_dtick(max_val):
    """Choose a dtick so we have about <= 8 ticks."""
    # step candidates in dollars
    steps = [50_000, 100_000, 200_000, 250_000, 500_000, 1_000_000]
    for s in steps:
        if max_val / s <= 8:
            return s
    return 2_000_000

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
    # 1) Revenue by Product Category — based on sidebar choice
    if "Sales" in source_pick and sales is not None:
        scope = sales if sales_year is None else sales[sales["Year"] == sales_year]
        st.subheader(f"Revenue by Product Category ({sales_year})" if sales_year else "Revenue by Product Category")

        cat_rev = (
            scope.groupby("Category", as_index=False)["Revenue"]
            .sum()
            .sort_values("Revenue", ascending=False)
            .head(6)
        )

        fig3 = px.bar(
            cat_rev,
            x="Revenue",  # raw dollars
            y="Category",
            orientation="h",
            color="Category",
            text_auto=".0f",
            color_discrete_sequence=color_for(cat_rev["Category"].tolist()),
        )
        max_x = float(cat_rev["Revenue"].max() or 0.0)
        dt = pick_dtick(max_x)
        upper = int(np.ceil(max_x / dt) * dt)
        fig3.update_layout(
            height=H_SHORT,
            margin=MARGIN,
            legend_title_text="",
            xaxis_title="Total Revenue ($)",
            xaxis=dict(tickformat=",", dtick=dt, range=[0, upper], ticks="outside"),
            hovermode="y"
        )
        fig3.update_traces(
            hovertemplate="<b>%{y}</b><br>Revenue: $%{x:,.0f}<extra></extra>",
            texttemplate="$%{x:,.0f}",
            textposition="outside",
            cliponaxis=False
        )
        st.plotly_chart(fig3, use_container_width=True)

    elif "Suppliers" in source_pick and suppliers is not None:
        scope = suppliers if sup_year is None else suppliers[suppliers["Year"] == sup_year]
        st.subheader(f"Revenue by Product Category ({sup_year}) — Suppliers")

        cat_rev = (
            scope.groupby("Category", as_index=False)["Order_Amount"]
            .sum()
            .sort_values("Order_Amount", ascending=False)
            .head(6)
        )

        fig3 = px.bar(
            cat_rev,
            x="Order_Amount",
            y="Category",
            orientation="h",
            color="Category",
            text_auto=".0f",
            color_discrete_sequence=color_for(cat_rev["Category"].tolist()),
        )
        max_x = float(cat_rev["Order_Amount"].max() or 0.0)
        dt = pick_dtick(max_x)
        upper = int(np.ceil(max_x / dt) * dt)
        fig3.update_layout(
            height=H_SHORT,
            margin=MARGIN,
            legend_title_text="",
            xaxis_title="Total Revenue ($)",
            xaxis=dict(tickformat=",", dtick=dt, range=[0, upper], ticks="outside"),
            hovermode="y"
        )
        fig3.update_traces(
            hovertemplate="<b>%{y}</b><br>Revenue: $%{x:,.0f}<extra></extra>",
            texttemplate="$%{x:,.0f}",
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
        fig5 = px.bar(
            qty, x="Year", y="T_QTY", text_auto=".2s",
            color_discrete_sequence=[PALETTE[0]]
        )
        fig5.update_layout(height=H_SHORT, margin=MARGIN)
        st.plotly_chart(fig5, use_container_width=True)

# ================== FOOTER ==================
st.caption(
    "One-page EDA — Monthly trend, category revenue, supplier trends & concentration. "
    "Compact layout designed to fit without scrolling."
)
