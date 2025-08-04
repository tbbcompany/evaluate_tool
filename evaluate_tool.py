import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import webbrowser
from datetime import datetime
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="股票估值工具 V2", layout="wide")
st.title("📈 股票估值分析工具 v2")

@st.cache_data
def load_stock_list():
    taiwan = pd.read_csv("https://mops.twse.com.tw/mops/web/ajax_t51sb01", encoding="utf-8", on_bad_lines='skip')
    us = pd.read_csv("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv")
    return taiwan, us

def search_symbol(keyword, market):
    tw, us = load_stock_list()
    if market == "台股":
        df = tw
        if keyword.isdigit():
            results = df[df["股票代號"].astype(str).str.contains(keyword)]
        else:
            results = df[df["公司名稱"].str.contains(keyword)]
        return results[["股票代號", "公司名稱"]]
    else:
        df = us
        return df[df["Name"].str.contains(keyword, case=False) | df["Symbol"].str.contains(keyword, case=False)]

def get_dividends_tw(stock_id):
    url = f"https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID={stock_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", class_="b1 p4_2 r10 box_shadow")
    if table:
        df = pd.read_html(str(table))[0]
        df.columns = df.columns.droplevel(0)
        df = df.rename(columns={"年度": "Year", "現金股利": "Cash", "股票股利": "Stock"})
        df = df[["Year", "Cash", "Stock"]].dropna()
        df = df.head(3)
        df[["Cash", "Stock"]] = df[["Cash", "Stock"]].replace("--", 0).astype(float)
        return df
    return pd.DataFrame()

def show_dividend_chart(div_df):
    fig, ax = plt.subplots(figsize=(5,3))
    bar1 = ax.bar(div_df["Year"], div_df["Cash"], label="Cash")
    bar2 = ax.bar(div_df["Year"], div_df["Stock"], bottom=div_df["Cash"], label="Stock")
    ax.set_ylabel("股利")
    ax.set_title("三年股利政策")
    ax.legend()
    st.pyplot(fig)

def calculate_fair_value_pe(current_eps, pe_range):
    return current_eps * np.array(pe_range)

def calculate_fair_value_pb(current_bvps, pb_range):
    return current_bvps * np.array(pb_range)

# --- UI ---
market = st.radio("選擇市場：", ["台股", "美股"], horizontal=True)
keyword = st.text_input("輸入股票代號或名稱：")

if keyword:
    result = search_symbol(keyword, market)
    if not result.empty:
        selection = st.selectbox("選擇股票：", result.values.tolist(), format_func=lambda x: f"{x[0]} - {x[1]}")
        code = selection[0]

        if market == "台股":
            ticker = f"{code}.TW"
            st.markdown(f"[🔗 Google 財經連結](https://www.google.com/finance/quote/{code}:TPE?hl=zh-TW)")
        else:
            ticker = code
            st.markdown(f"[🔗 Google 財經連結](https://www.google.com/finance/quote/{code}:NASDAQ?hl=zh-TW)")

        stock = yf.Ticker(ticker)
        info = stock.info

        st.subheader(f"📊 {info.get('longName', '')} 基本資料")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"目前價格：{info.get('currentPrice', '-')}")
            st.write(f"EPS：{info.get('trailingEps', '-')}")
            st.write(f"本益比 PE：{info.get('trailingPE', '-')}")
        with col2:
            st.write(f"每股淨值 BVPS：約 {info.get('bookValue', '-')}")
            st.write(f"股價淨值比 PB：約 {info.get('priceToBook', '-')}")

        # 股利圖表（僅台股）
        if market == "台股":
            div_df = get_dividends_tw(code)
            if not div_df.empty:
                show_dividend_chart(div_df)

        # 合理價位預估
        st.subheader("📐 合理價位與價差建議")
        try:
            pe = info.get("trailingPE", 10)
            eps = info.get("trailingEps", 1)
            price = info.get("currentPrice", 1)
            pe_range = [pe * 0.8, pe, pe * 1.2]
            fair_price = calculate_fair_value_pe(eps, pe_range)
            df_pe = pd.DataFrame({"PE": pe_range, "估算價格": fair_price, "價差%": (fair_price - price)/price*100})
            st.write(df_pe.round(2))
        except:
            st.warning("無法計算 PE 合理價")

        # 估值功能區
        st.subheader("🔍 其他估值試算")
        tab1, tab2, tab3 = st.tabs(["PE 法", "PB 法", "DCF (簡版)"])
        with tab1:
            try:
                pe_input = st.slider("預期本益比", 5.0, 30.0, float(pe))
                eps_input = st.number_input("預估 EPS", value=float(eps))
                fair = pe_input * eps_input
                st.write(f"📌 預估股價：{fair:.2f}")
            except:
                st.warning("無法輸入 EPS")

        with tab2:
            try:
                pb_input = st.slider("預期 PB 倍數", 0.5, 5.0, float(info.get("priceToBook", 1)))
                bvps_input = st.number_input("每股淨值", value=float(info.get("bookValue", 1)))
                fair = pb_input * bvps_input
                st.write(f"📌 預估股價：{fair:.2f}")
            except:
                st.warning("無法輸入 BVPS")

        with tab3:
            try:
                future_eps = st.number_input("每年 EPS 成長率 (%)", value=5.0)
                years = st.slider("預估年數", 1, 10, 5)
                discount = st.slider("折現率 (%)", 5.0, 15.0, 10.0)
                eps_list = [eps * ((1 + future_eps / 100) ** i) for i in range(1, years+1)]
                discount_rate = discount / 100
                dcf = sum([e / ((1 + discount_rate) ** (i+1)) for i, e in enumerate(eps_list)])
                st.write(f"📌 DCF 預估價值：約 {dcf:.2f}")
            except:
                st.warning("DCF 計算錯誤")
