# app.py — Baba Jina | EDA One Page (compact, no scroll)

import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ================== PAGE / THEME ==================
st.set_page_config(page_title="Baba Jina | EDA One Page", layout="wide")

st.markdown(
    """
    <style>
      .block-container {
          padding-top: 2.2rem !important;
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
    "Birthdays/Celebrations": "#2563EB",
    "Christmas": "#10B981",
    "Fees/Admin": "#94A3B8",
    "Halloween": "#EF4444",
    "Summer": "#EAB308",
    "Toys": "#22C55E",
}
def color_for(keys):
    return [CAT_COLORS.get(k, PALETTE[i % len(PALETTE)]) for i, k in enumerate(keys)]

# ================== LOADERS ==================
@st.cache_data(show_spinner=False)
def load_sales():
    if not os.path.exists(SALES_XLSX):
        return None
    df = pd.read_excel(SALES_XLSX)

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
        df["Year"]  = df["Date"].dt.year

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

    if "Amount" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["Amount"], errors="coerce")
    elif "AMOUNT" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["AMOUNT"], errors="coerce")
    else:
        sup["Order_Amount"] = (
            pd.to_numeric(sup.get("Price", 0), errors="coerce")
            * pd.to_numeric(sup.get("CTN_Box", 0), errors="coerce")
        )

    if "New_Year" in sup.columns:
        sup["Year"] = sup["New_Year"]

    for guess in ["Shop", "ShopName", "Supplier", "Vendor", "Name"]:
        if guess in sup.columns:
            sup["ShopName"] = sup[guess].astype(str)
            break
    if "ShopName" not in sup.columns:
        sup["ShopName"] = "Unknown"

    sup["Category"] = sup.get("Category", "Unknown").fillna("Unknown")
    return sup.dropna(subset=["Order_Amount"])

sales = load_sales()
suppliers = load_suppliers()

# ================== SIDEBAR: GLOBAL YEAR RANGE FILTER ==================
def collect_years():
    yrs = []
    if sales is not None and "Year" in sales.columns:
        yrs += sales["Year"].dropna().astype(int).unique().tolist()
    if suppliers is not None and "Year" in suppliers.columns:
        yrs += suppliers["Year"].dropna().astype(int).unique().tolist()
    if not yrs:
        return None, None
    yrs = sorted(set(yrs))
    return yrs[0], yrs[-1]

min_year, max_year = collect_years()
if min_year is None:
    st.stop()

year_start, year_end = st.sidebar.slider(
    "Select Year Range",
    min_value=int(min_year),
    max_value=int(max_year),
    value=(int(min_year), int(max_year)),
    step=1,
)

def in_range(df, col="Year"):
    return df[(df[col] >= year_start) & (df[col] <= year_end)]

sales_f = in_range(sales) if sales is not None else None
suppliers_f = in_range(suppliers) if suppliers is not None else None

# ================== SIZING ==================
H_TALL   = 210
H_MED    = 190
H_SHORT  = 150
MARGIN   = dict(l=4, r=4, t=6, b=4)

def pick_dtick(max_val):
    steps = [50_000, 100_000, 200_000, 250_000, 500_000, 1_000_000]
    for s in steps:
        if max_val / s <= 8:
            return s
    return 2_000_000

def range_label():
    return f"{year_start}" if year_start == year_end else f"{year_start}–{year_end}"

# ================== LAYOUT ==================
col_left, col_right = st.columns([1, 1])

# LEFT CHARTS
with col_left:
    if sales_f is not None and not sales_f.empty:
        st.subheader(f"Monthly Revenue Trend ({range_label()})")
        monthly = sales_f.groupby("Month", as_index=False)["Revenue"].sum().sort_values("Month")
        fig1 = px.line(monthly, x="Month", y="Revenue", markers=True,
                       color_discrete_sequence=[PALETTE[0]])
        fig1.update_layout(height=H_TALL, margin=MARGIN, showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    if suppliers_f is not None and not suppliers_f.empty:
        st.subheader(f"Annual Supplier Order Amount by Category ({range_label()})")
        cat_year = suppliers_f.groupby(["Year", "Category"], as_index=False)["Order_Amount"].sum()
        cats = list(cat_year["Category"].unique())
        fig2 = px.line(cat_year, x="Year", y="Order_Amount", color="Category",
                       markers=True, color_discrete_sequence=color_for(cats))
        fig2.update_layout(height=H_MED, margin=MARGIN,
                           legend=dict(orientation="h", y=1.05, x=0))
        st.plotly_chart(fig2, use_container_width=True)

# RIGHT CHARTS
with col_right:
    # Revenue by Category
    if sales_f is not None and not sales_f.empty:
        st.subheader(f"Revenue by Product Category ({range_label()})")
        cat_rev = sales_f.groupby("Category", as_index=False)["Revenue"].sum().sort_values("Revenue", ascending=False)
        fig3 = px.bar(cat_rev, x="Revenue", y="Category", orientation="h",
                      color="Category", text_auto=".0f",
                      color_discrete_sequence=color_for(cat_rev["Category"].tolist()))
        max_x = float(cat_rev["Revenue"].max() or 0.0)
        dt = pick_dtick(max_x)
        upper = int(np.ceil(max_x / dt) * dt)
        fig3.update_layout(height=H_SHORT, margin=MARGIN, legend_title_text="",
                           xaxis_title="Total Revenue ($)",
                           xaxis=dict(tickformat=",", dtick=dt, range=[0, upper], ticks="outside"))
        st.plotly_chart(fig3, use_container_width=True)

    # Category Distribution for Top 5 Shops
    if suppliers_f is not None and not suppliers_f.empty:
        st.subheader(f"Category Distribution for Top 5 Shops (by Order Amount) ({range_label()})")

        shop_tot = suppliers_f.groupby("ShopName", as_index=False)["Order_Amount"].sum().sort_values("Order_Amount", ascending=False)
        top5 = shop_tot.head(5)["ShopName"].astype(str).tolist()

        stack = suppliers_f[suppliers_f["ShopName"].astype(str).isin(top5)].groupby(["ShopName", "Category"], as_index=False)["Order_Amount"].sum()
        stack["ShopName"] = stack["ShopName"].astype(str)

        unique_cats = stack["Category"].unique().tolist()
        color_map = {c: CAT_COLORS.get(c, PALETTE[i % len(PALETTE)]) for i, c in enumerate(unique_cats)}

        fig4 = px.bar(stack, y="ShopName", x="Order_Amount", orientation="h",
                      color="Category", barmode="stack",
                      category_orders={"ShopName": top5, "Category": unique_cats},
                      color_discrete_map=color_map)

        fig4.update_layout(
            height=H_SHORT,
            margin=MARGIN,
            legend=dict(orientation="v", y=0.5, x=1.02),
            legend_title_text="Category",
            xaxis=dict(title="Total Amount (Monetary Units)", tickformat=","),
            yaxis=dict(title="Shop ID"),
            hovermode="y unified",
            bargap=0.25,
        )

        st.plotly_chart(fig4, use_container_width=True)

    # Quantity per year
    if suppliers_f is not None and "T_QTY" in suppliers_f.columns and not suppliers_f.empty:
        st.subheader(f"Total Product Quantity Ordered per Year ({range_label()})")
        qty = suppliers_f.groupby("Year", as_index=False)["T_QTY"].sum()
        fig5 = px.bar(qty, x="Year", y="T_QTY", text_auto=".2s", color_discrete_sequence=[PALETTE[0]])
        fig5.update_layout(height=H_SHORT, margin=MARGIN)
        st.plotly_chart(fig5, use_container_width=True)

# FOOTER
st.caption("One-page EDA — Monthly trend, category revenue, supplier trends & concentration. Global year-range filter applies to all charts.")
