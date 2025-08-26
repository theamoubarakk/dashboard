# app.py
import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Baba Jina | Capstone Dashboard", layout="wide")

# -------------------- THEME / CARDS --------------------
CARD_CSS = """
<style>
.card {background: #ffffff; border-radius: 14px; padding: 18px 18px; box-shadow: 0 4px 18px rgba(0,0,0,0.06); border: 1px solid #eef0f4;}
.kpi {font-size: 14px; color: #6b7280; margin-bottom: 6px;}
.kpi-val {font-size: 26px; font-weight: 700; margin-bottom: 2px;}
.kpi-sub {font-size: 12px; color: #9aa2af;}
.section-title {font-size: 22px; font-weight: 800; margin: 2px 0 14px;}
.section-sub {font-size: 12px; color: #64748b; margin-bottom: 6px;}
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

# -------------------- FIXED RELATIVE PATHS --------------------
SALES_PATH     = "data/(3) BABA JINA SALES DATA.xlsx"
SUPPLIERS_PATH = "data/suppliers_data_cleaned.xlsx"
RENTALS_PATH   = "data/rentals.xlsx"

def _ensure_exists(path, label):
    if not os.path.exists(path):
        st.error(
            f"Missing required file: **{path}**. "
            f"Add it to your repo (create a `data/` folder at the project root) and redeploy.\n\n"
            f"- Expected: `{path}` for {label}."
        )
        st.stop()

_ensure_exists(SALES_PATH, "Sales")
_ensure_exists(SUPPLIERS_PATH, "Suppliers")
_ensure_exists(RENTALS_PATH, "Rentals")

# -------------------- LOADERS (ROBUST) --------------------
@st.cache_data(show_spinner=False)
def load_sales():
    df = pd.read_excel(SALES_PATH)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Year"]  = df["Date"].dt.year
        df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    if "Total_Amount" in df.columns:
        df["Revenue"] = pd.to_numeric(df["Total_Amount"], errors="coerce")
    else:
        q = pd.to_numeric(df.get("Quantity", np.nan), errors="coerce")
        p = pd.to_numeric(df.get("Unit_Price", np.nan), errors="coerce")
        df["Revenue"] = q * p
    df["Category"]    = df.get("Category", "Unknown").fillna("Unknown")
    df["Subcategory"] = df.get("Subcategory", "Unknown").fillna("Unknown")
    return df.dropna(subset=["Revenue"])

@st.cache_data(show_spinner=False)
def load_suppliers():
    sup = pd.read_excel(SUPPLIERS_PATH)
    if "Amount" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["Amount"], errors="coerce")
    elif "AMOUNT" in sup.columns:
        sup["Order_Amount"] = pd.to_numeric(sup["AMOUNT"], errors="coerce")
    else:
        price = pd.to_numeric(sup.get("Price"), errors="coerce")
        ctn   = pd.to_numeric(sup.get("CTN_Box"), errors="coerce")
        sup["Order_Amount"] = price * ctn
    if "New_Year" in sup.columns:
        sup["Year"] = sup["New_Year"]
    elif "Year" not in sup.columns:
        sup["Year"] = np.nan
    sup["Category"] = sup.get("Category", "Unknown").fillna("Unknown")
    return sup.dropna(subset=["Order_Amount"])

@st.cache_data(show_spinner=False)
def load_rentals():
    ren = pd.read_excel(RENTALS_PATH)
    for col in ["Start_Date","End_Date","start_date","end_date","Date","date"]:
        if col in ren.columns:
            ren[col] = pd.to_datetime(ren[col], errors="coerce")
    ren["start_any"] = None
    for c in ["Start_Date","start_date","Date","date"]:
        if c in ren.columns:
            ren["start_any"] = ren[c]; break
    for guess in ["Rental Price","Rental_Price","rent_price","Price","price"]:
        if guess in ren.columns:
            ren["RentalPrice"] = pd.to_numeric(ren[guess], errors="coerce"); break
    for guess in ["Mascot Name","Mascot_Name","Name","name","Mascot"]:
        if guess in ren.columns:
            ren["Mascot"] = ren[guess].astype(str); break
    return ren

sales     = load_sales()
suppliers = load_suppliers()
rentals   = load_rentals()

# -------------------- SIDEBAR FILTERS --------------------
with st.sidebar:
    st.header("Filters")
    if "Date" in sales.columns and not sales.empty:
        min_d, max_d = sales["Date"].min(), sales["Date"].max()
        d1, d2 = st.date_input(
            "Sales date range", value=(min_d.date(), max_d.date()),
            min_value=min_d.date(), max_value=max_d.date()
        )
        mask_date = (sales["Date"].dt.date >= d1) & (sales["Date"].dt.date <= d2)
    else:
        mask_date = np.ones(len(sales)).astype(bool)

    cats = sorted(sales.get("Category", pd.Series(dtype=str)).dropna().unique().tolist())
    pick_cats = st.multiselect("Sales categories", cats, default=cats)
    mask_cat = sales.get("Category", pd.Series(["Unknown"]*len(sales))).isin(pick_cats) if len(cats) else np.ones(len(sales)).astype(bool)

    years = [y for y in sorted(suppliers.get("Year", pd.Series(dtype=float)).dropna().unique().tolist()) if pd.notna(y)]
    year_sel = st.multiselect("Supplier years", years, default=years)

    if not rentals.empty and rentals["start_any"].notna().any():
        min_r, max_r = rentals["start_any"].min(), rentals["start_any"].max()
        r1, r2 = st.date_input("Rental period", value=(min_r.date(), max_r.date()),
                               min_value=min_r.date(), max_value=max_r.date())
        mask_r = (rentals["start_any"].dt.date >= r1) & (rentals["start_any"].dt.date <= r2)
    else:
        mask_r = np.ones(len(rentals)).astype(bool)

sales_f     = sales[mask_date & mask_cat].copy()
suppliers_f = suppliers[suppliers["Year"].isin(year_sel)] if years else suppliers.copy()
rentals_f   = rentals[mask_r].copy()

# ==================== BAND 1: RETAIL SALES (Outbound) ====================
st.markdown('<div class="section-title">Retail Sales (Outbound)</div>', unsafe_allow_html=True)
top_l, top_m, top_r = st.columns([1.1, 1.6, 1.6])

with top_l:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Key Performance</div>', unsafe_allow_html=True)
    revenue = float(sales_f["Revenue"].sum()) if len(sales_f) else 0.0
    orders  = int(sales_f.shape[0])
    aov     = (revenue / orders) if orders else 0.0
    top_cat = sales_f.groupby("Category")["Revenue"].sum().sort_values(ascending=False).head(1) if len(sales_f) else pd.Series(dtype=float)
    top_cat_name = top_cat.index[0] if len(top_cat) else "—"
    top_cat_val  = float(top_cat.iloc[0]) if len(top_cat) else 0.0

    st.markdown(f'<div class="kpi">Revenue (filtered)</div><div class="kpi-val">${revenue:,.0f}</div><div class="kpi-sub">Sum of Total_Amount</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi">Avg Order Value</div><div class="kpi-val">${aov:,.0f}</div><div class="kpi-sub">Revenue / rows</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi">Top Category</div><div class="kpi-val">{top_cat_name}</div><div class="kpi-sub">${top_cat_val:,.0f}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with top_m:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Revenue by Category</div>', unsafe_allow_html=True)
    if len(sales_f):
        cat_rev = sales_f.groupby("Category", as_index=False)["Revenue"].sum().sort_values("Revenue", ascending=False)
        fig = px.bar(cat_rev, x="Category", y="Revenue", text_auto=".2s")
        fig.update_traces(textposition="outside")
        fig.update_layout(margin=dict(l=6,r=6,t=6,b=6), height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No sales data in the current filter.")
    st.markdown('</div>', unsafe_allow_html=True)

with top_r:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Monthly Revenue Trend</div>', unsafe_allow_html=True)
    if "Month" in sales_f.columns and len(sales_f):
        m = sales_f.groupby("Month", as_index=False)["Revenue"].sum()
        fig = px.area(m, x="Month", y="Revenue")
        fig.update_layout(margin=dict(l=6,r=6,t=6,b=6), height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Add a Date column to show monthly trend.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# ==================== BAND 2: SUPPLY & RENTALS (Inbound) ====================
st.markdown('<div class="section-title">Supply & Rentals (Inbound)</div>', unsafe_allow_html=True)
bot_l, bot_m, bot_r = st.columns([1.1, 1.6, 1.6])

with bot_l:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Operations Snapshot</div>', unsafe_allow_html=True)
    spend = float(suppliers_f["Order_Amount"].sum()) if len(suppliers_f) else 0.0
    st.markdown(f'<div class="kpi">Supplier Spend</div><div class="kpi-val">${spend:,.0f}</div><div class="kpi-sub">Filtered years</div>', unsafe_allow_html=True)
    if "RentalPrice" in rentals_f.columns:
        mascots = rentals_f["Mascot"].nunique() if "Mascot" in rentals_f.columns else rentals_f.shape[0]
        avg_price = float(rentals_f["RentalPrice"].mean())
        st.markdown(f'<div class="kpi">Mascots</div><div class="kpi-val">{mascots:,}</div><div class="kpi-sub">Unique items</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi">Avg Rental Price</div><div class="kpi-val">${avg_price:,.0f}</div><div class="kpi-sub">Per mascot</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="kpi">Mascots</div><div class="kpi-val">{rentals_f.shape[0]:,}</div><div class="kpi-sub">Items in rentals.xlsx</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi">Avg Rental Price</div><div class="kpi-val">—</div><div class="kpi-sub">Add a price column</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with bot_m:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Top Supplier Categories</div>', unsafe_allow_html=True)
    if len(suppliers_f):
        cat_spend = suppliers_f.groupby("Category", as_index=False)["Order_Amount"].sum().sort_values("Order_Amount", ascending=False)
        fig = px.bar(cat_spend.head(12), x="Category", y="Order_Amount", text_auto=".2s")
        fig.update_traces(textposition="outside")
        fig.update_layout(margin=dict(l=6,r=6,t=6,b=6), height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No supplier rows available for the selected years.")
    st.markdown('</div>', unsafe_allow_html=True)

with bot_r:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Supplier Spend / Rentals Over Time</div>', unsafe_allow_html=True)
    if len(suppliers_f) and suppliers_f["Year"].notna().any():
        y = suppliers_f.groupby("Year", as_index=False)["Order_Amount"].sum().sort_values("Year")
        fig = px.area(y, x="Year", y="Order_Amount")
        fig.update_layout(margin=dict(l=6,r=6,t=6,b=6), height=320)
        st.plotly_chart(fig, use_container_width=True)
    elif not rentals_f.empty and rentals_f["start_any"].notna().any():
        r = rentals_f.dropna(subset=["start_any"]).copy()
        r["Month"] = r["start_any"].dt.to_period("M").dt.to_timestamp()
        r_agg = r.groupby("Month", as_index=False).size().rename(columns={"size":"Bookings"})
        fig = px.area(r_agg, x="Month", y="Bookings")
        fig.update_layout(margin=dict(l=6,r=6,t=6,b=6), height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Add supplier Year or rental dates to show a timeline.")
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== FOOTER ====================
st.caption("Layout scaffold only — plug in richer business logic/KPIs as you finalize columns & calculations.")
