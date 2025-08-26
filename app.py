# app.py
# Baba Jina Toys – Executive Dashboard (Plotly version)

import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
from pandas.tseries.offsets import MonthEnd

st.set_page_config(page_title="Baba Jina Toys – Executive Dashboard", layout="wide")

# -------------------- File paths --------------------
DEFAULT_SALES_PATH     = "(3) BABA JINA SALES DATA.xlsx"
DEFAULT_SUPPLIERS_PATH = "suppliers_data_cleaned.xlsx"
DEFAULT_RENTALS_PATH   = "rentals.xlsx"

# -------------------- Loaders --------------------
@st.cache_data
def load_sales(path):
    df = pd.read_excel(path)
    # normalize column names
    df.columns = [c.lower().strip() for c in df.columns]
    date_col = [c for c in df.columns if "date" in c][0]
    revenue_col = [c for c in df.columns if "amount" in c or "revenue" in c or "total" in c][0]
    cat_col = [c for c in df.columns if "category" in c][0]
    df["date"] = pd.to_datetime(df[date_col])
    df["revenue"] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)
    df["category"] = df[cat_col].astype(str)
    return df

@st.cache_data
def load_suppliers(path):
    df = pd.read_excel(path)
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.rename(columns={
        "shop":"supplier", "supplier":"supplier",
        "order_amount":"order_amount", "amount":"order_amount",
        "category":"category", "year":"year"
    })
    return df

@st.cache_data
def load_rentals(path):
    df = pd.read_excel(path)
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.rename(columns={
        "mascot":"mascot", "mascot_name":"mascot",
        "start_date":"start", "end_date":"end"
    })
    df["start"] = pd.to_datetime(df["start"])
    df["end"]   = pd.to_datetime(df["end"])
    return df

# -------------------- Business logic --------------------
def monthly_sales_with_forecast(df, cat_filter):
    df = df[df["category"].isin(cat_filter)] if cat_filter else df
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp("M")
    monthly = df.groupby("month", as_index=False)["revenue"].sum()
    monthly["year"] = monthly["month"].dt.year
    monthly["m"] = monthly["month"].dt.month
    hist = monthly[monthly["year"]<=2024]
    ref = hist.groupby("m")["revenue"].mean().reset_index()
    fut = pd.date_range("2025-01-31","2025-12-31",freq="M")
    forecast = pd.DataFrame({"month":fut})
    forecast["m"] = forecast["month"].dt.month
    forecast = forecast.merge(ref,on="m",how="left").rename(columns={"revenue":"forecast"})
    return monthly, forecast

def rentals_utilization(rentals):
    bookings=[]
    for _,r in rentals.iterrows():
        days=pd.date_range(r["start"],r["end"],freq="D")
        for d in days: bookings.append({"mascot":r["mascot"],"date":d})
    used=pd.DataFrame(bookings)
    used["month"]=used["date"].dt.to_period("M").dt.to_timestamp("M")
    num=used.groupby(["mascot","month"])["date"].nunique().reset_index()
    num["days_in_month"]=num["month"].dt.days_in_month
    num["utilization%"]=(num["date"]/num["days_in_month"]*100).round(1)
    return num

# -------------------- Data load --------------------
sales = load_sales(DEFAULT_SALES_PATH)
suppliers = load_suppliers(DEFAULT_SUPPLIERS_PATH)
rentals = load_rentals(DEFAULT_RENTALS_PATH)

# -------------------- Filters --------------------
st.title("🎯 Baba Jina Toys – Executive Dashboard")
years = sorted(sales["date"].dt.year.unique())
cats  = sorted(sales["category"].unique())
col1,col2,col3=st.columns(3)
year_sel=col1.multiselect("Years",years,[2023,2024])
cat_sel =col2.multiselect("Categories",cats,["Toys","Halloween","Christmas"])
show_fc=col3.toggle("Show 2025 Forecast",True)

# -------------------- KPIs --------------------
c1,c2,c3,c4=st.columns(4)
df_filt=sales[sales["category"].isin(cat_sel)]
total23=df_filt[df_filt["date"].dt.year==2023]["revenue"].sum()
total24=df_filt[df_filt["date"].dt.year==2024]["revenue"].sum()
growth=(total24-total23)/total23*100 if total23>0 else 0
c1.metric("Total Sales 2024",f"${total24:,.0f}",f"{growth:+.1f}% vs 2023")

monthly,forecast=monthly_sales_with_forecast(sales,cat_sel)
if not forecast.empty:
    peak=forecast.sort_values("forecast",ascending=False).iloc[0]
    c2.metric("Peak Month 2025",peak["month"].strftime("%B"),f"${peak['forecast']:,.0f}")
else:
    c2.metric("Peak Month 2025","—","—")

dep = suppliers.groupby("supplier")["order_amount"].sum().sort_values(ascending=False)
dep_ratio=dep.head(2).sum()/dep.sum()*100 if dep.sum()>0 else 0
c3.metric("Supplier Dependence",f"{dep_ratio:.1f}%","Top 2 share")

active=sales[sales["date"]>sales["date"].max()-pd.Timedelta(days=180)]["category"].count()
c4.metric("Active Customers (proxy)",f"{active:,}","last 180 days")

# -------------------- Sales & Forecast --------------------
st.subheader("📈 Sales & Forecast")
fig1 = px.line(monthly,x="month",y="revenue",title="Monthly Sales",labels={"revenue":"Revenue"})
if show_fc:
    fig1.add_scatter(x=forecast["month"],y=forecast["forecast"],mode="lines",name="Forecast 2025")
st.plotly_chart(fig1,use_container_width=True)

# -------------------- Suppliers --------------------
st.subheader("🏭 Top Suppliers")
top5 = suppliers.groupby("supplier")["order_amount"].sum().nlargest(5).index
sup_plot=suppliers[suppliers["supplier"].isin(top5)]
fig2 = px.bar(sup_plot,x="order_amount",y="supplier",color="category",orientation="h",title="Top 5 Suppliers")
st.plotly_chart(fig2,use_container_width=True)

# -------------------- Rentals --------------------
st.subheader("🎭 Mascot Rentals Utilization")
util=rentals_utilization(rentals)
fig3 = px.density_heatmap(util,x="month",y="mascot",z="utilization%",color_continuous_scale="Blues")
st.plotly_chart(fig3,use_container_width=True)

# -------------------- Loyalty Snapshot (proxy) --------------------
st.subheader("💳 Loyalty Snapshot (RFM Proxy)")
rfm = sales.groupby("category")["revenue"].sum().reset_index()
fig4 = px.bar(rfm,x="category",y="revenue",title="Revenue by Category (proxy loyalty)")
st.plotly_chart(fig4,use_container_width=True)

# -------------------- Delivery Simulator --------------------
st.subheader("🚚 Delivery Subsidy Simulator")
with st.form("sim"):
    orders=st.number_input("Monthly Orders",0,500,100)
    subsidy=st.number_input("Subsidy per Order $",0.0,20.0,3.5)
    uplift=st.number_input("Basket Uplift %",0.0,100.0,15.0)
    margin=st.number_input("Gross Margin %",0.0,100.0,35.0)
    run=st.form_submit_button("Run")
if run:
    base_basket=28
    new_basket=base_basket*(1+uplift/100)
    gp=new_basket*(margin/100)*orders
    cost=subsidy*orders
    net=gp-cost
    st.metric("Net Monthly Impact",f"${net:,.0f}")

# -------------------- Downloads --------------------
st.subheader("⬇️ Data Exports")
c1,c2,c3=st.columns(3)
c1.download_button("Download Sales CSV",sales.to_csv(index=False).encode(),"sales.csv","text/csv")
c2.download_button("Download Suppliers CSV",suppliers.to_csv(index=False).encode(),"suppliers.csv","text/csv")
c3.download_button("Download Rentals CSV",rentals.to_csv(index=False).encode(),"rentals.csv","text/csv")
