import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import webbrowser 
from datetime import datetime 
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
import io 

# 設定 Streamlit 頁面配置
st.set_page_config(page_title="股票估值工具 V2", layout="wide")
st.title("📈 股票估值分析工具 v2")

@st.cache_data
def load_stock_list():
    """
    載入台灣和美國的股票列表。
    台灣股票資料從公開資訊觀測站 (MOPS) 取得，需要發送 POST 請求並解析 HTML。
    美國股票資料從維基百科上的 S&P 500 成分股列表取得 (更穩定)。
    """
    # 載入台灣股票列表
    url_tw = "https://mops.twse.com.tw/mops/web/ajax_t51sb01"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "queryName": "co_id",
        "inpuType": "co_id",
        "TYPEK": "all", 
        "isQuery": "Y"
    }
    
    taiwan_df = pd.DataFrame(columns=["股票代號", "公司名稱"]) 
    try:
        response = requests.post(url_tw, headers=headers, data=data, timeout=10) 
        response.encoding = 'utf-8' 
        
        soup = BeautifulSoup(response.text, 'html.parser')
        tables = soup.find_all('table') 
        
        found_table = False
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) > 1: 
                header_cols = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
                if '公司代號' in header_cols and '公司名稱' in header_cols:
                    data_rows = []
                    for row in rows[1:]: 
                        cols = row.find_all('td')
                        if len(cols) >= 2: 
                            stock_id = cols[0].get_text(strip=True)
                            company_name = cols[1].get_text(strip=True)
                            data_rows.append([stock_id, company_name])
                    
                    if data_rows:
                        taiwan_df = pd.DataFrame(data_rows, columns=["股票代號", "公司名稱"])
                        found_table = True
                        break 
        
        if not found_table:
            st.warning("無法從公開資訊觀測站取得台股資料的表格。這可能是網站結構改變或網路問題。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
            
    except requests.exceptions.RequestException as e:
        st.error(f"載入台股列表時發生網路錯誤: {e}。請檢查您的網路連線或稍後再試。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
    except Exception as e:
        st.error(f"載入台股列表時發生解析錯誤: {e}。這可能是網站結構改變導致。**台股資料來源為網頁爬蟲，易受網站更新影響。**")

    # 載入美國股票列表 (S&P 500 成分股)
    us_df = pd.DataFrame(columns=["Symbol", "Name"]) 
    try:
        us_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(us_url)
        if tables:
            temp_us_df = tables[0] 
            if 'Symbol' in temp_us_df.columns and 'Security' in temp_us_df.columns:
                us_df = temp_us_df.rename(columns={'Security': 'Name'}) 
                us_df = us_df[['Symbol', 'Name']] 
            else:
                st.warning("載入美股列表成功，但缺少預期的 'Symbol' 或 'Security' 欄位。這可能是維基百科表格格式改變。")
        else:
            st.warning("從維基百科載入美股列表時，未找到任何表格。")

    except requests.exceptions.RequestException as e:
        st.error(f"載入美股列表時發生網路錯誤: {e}。請檢查您的網路連線或稍後再試。")
    except ImportError: 
        st.error("載入美股列表失敗：缺少必要的 'lxml' 函式庫。請在您的 Streamlit 環境中執行以下指令安裝：`pip install lxml` 或 `conda install lxml`。")
    except Exception as e:
        st.error(f"載入美股列表時發生解析錯誤: {e}。這可能是維基百科表格結構改變。")
        
    return taiwan_df, us_df

def search_symbol(keyword, market):
    """
    根據關鍵字和市場搜尋股票代號或名稱。
    """
    tw, us = load_stock_list()
    if market == "台股":
        df = tw
        if df.empty:
            st.info("台股列表資料未載入，無法搜尋。請檢查上方錯誤訊息。") 
            return pd.DataFrame(columns=["股票代號", "公司名稱"]) 
        
        if keyword.isdigit():
            results = df[df["股票代號"].astype(str).str.contains(keyword)]
        else:
            results = df[df["公司名稱"].astype(str).str.contains(keyword, case=False)]
        return results[["股票代號", "公司名稱"]]
    else: # 美股
        df = us
        if df.empty:
            st.info("美股列表資料未載入，無法搜尋。請檢查上方錯誤訊息。") 
            return pd.DataFrame(columns=["Symbol", "Name"]) 

        return df[df["Name"].astype(str).str.contains(keyword, case=False) | df["Symbol"].astype(str).str.contains(keyword, case=False)]

def get_dividends_tw(stock_id):
    """
    從 Goodinfo! 網站取得台灣股票的股利政策資料。
    """
    url = f"https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID={stock_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    div_df = pd.DataFrame() 
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8' 
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", class_="b1 p4_2 r10 box_shadow")
        if table:
            dfs_from_html = pd.read_html(str(table))
            if dfs_from_html:
                df = dfs_from_html[0] 
                df.columns = df.columns.droplevel(0) 
                df = df.rename(columns={"年度": "Year", "現金股利": "Cash", "股票股利": "Stock"})
                df = df[["Year", "Cash", "Stock"]].dropna() 
                df = df.head(3) 
                df[["Cash", "Stock"]] = df[["Cash", "Stock"]].replace("--", 0).astype(float)
                div_df = df
            else:
                st.warning(f"從 Goodinfo! 取得 {stock_id} 的股利資料，但未找到有效的表格數據。這可能是網站結構改變。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
        else:
            st.warning(f"無法從 Goodinfo! 取得 {stock_id} 的股利資料表格。這可能是網站結構改變或無資料。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
    except requests.exceptions.RequestException as e:
        st.error(f"取得股利資料時發生網路錯誤: {e}。請檢查您的網路連線或稍後再試。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
    except Exception as e:
        st.error(f"解析股利資料時發生錯誤: {e}。這可能是網站結構改變。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
    return div_df

def show_dividend_chart(div_df):
    """
    顯示股利政策的長條圖。
    """
    fig, ax = plt.subplots(figsize=(5,3))
    ax.bar(div_df["Year"], div_df["Cash"], label="現金股利")
    ax.bar(div_df["Year"], div_df["Stock"], bottom=div_df["Cash"], label="股票股利")
    ax.set_ylabel("股利")
    ax.set_title("近三年股利政策")
    ax.legend()
    st.pyplot(fig) 

def calculate_fair_value_pe(current_eps, pe_range):
    """
    根據 EPS 和本益比區間計算合理股價。
    """
    return current_eps * np.array(pe_range)

def calculate_fair_value_pb(current_bvps, pb_range):
    """
    根據 BVPS 和股價淨值比區間計算合理股價。
    """
    return current_bvps * np.array(pb_range)

# --- Streamlit UI 介面 ---
market = st.radio("選擇市場：", ["台股", "美股"], horizontal=True)
keyword = st.text_input("輸入股票代號或名稱：")

if keyword:
    result = search_symbol(keyword, market)
    if not result.empty:
        if market == "台股":
            selection_options = result.values.tolist()
            format_func = lambda x: f"{x[0]} - {x[1]}"
        else: 
            selection_options = result[['Symbol', 'Name']].values.tolist()
            format_func = lambda x: f"{x[0]} - {x[1]}"

        selection = st.selectbox("選擇股票：", selection_options, format_func=format_func)
        
        if market == "台股":
            code = selection[0]
            ticker = f"{code}.TW"
            st.markdown(f"[🔗 Google 財經連結](https://www.google.com/finance/quote/{code}:TPE?hl=zh-TW)")
        else: 
            code = selection[0]
            ticker = code
            st.markdown(f"[🔗 Google 財經連結](https://www.google.com/finance/quote/{code}:NASDAQ?hl=zh-TW)") 

        stock = yf.Ticker(ticker)
        try:
            info = stock.info
            if not info: 
                st.error(f"無法取得 {ticker} 的股票資訊，請確認代號是否正確或稍後再試。")
                st.stop() 
        except Exception as e:
            st.error(f"取得 {ticker} 股票資訊時發生錯誤: {e}")
            st.stop() 


        st.subheader(f"� {info.get('longName', '未知公司')} 基本資料")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"目前價格：{info.get('currentPrice', '-')}")
            st.write(f"EPS：{info.get('trailingEps', '-')}")
            st.write(f"本益比 PE：{info.get('trailingPE', '-')}")
        with col2:
            st.write(f"每股淨值 BVPS：約 {info.get('bookValue', '-')}")
            st.write(f"股價淨值比 PB：約 {info.get('priceToBook', '-')}")

        if market == "台股":
            div_df = get_dividends_tw(code)
            if not div_df.empty:
                show_dividend_chart(div_df)
            else:
                st.info("台股股利資料可能無法取得或不存在。")

        st.subheader("📐 合理價位與價差建議")
        try:
            pe = info.get("trailingPE")
            eps = info.get("trailingEps")
            price = info.get("currentPrice")

            if pe is None or eps is None or price is None:
                st.warning("無法取得完整的 PE、EPS 或目前價格資料，無法計算 PE 合理價。")
            else:
                pe = float(pe)
                eps = float(eps)
                price = float(price)

                pe_range = [pe * 0.8, pe, pe * 1.2]
                fair_price = calculate_fair_value_pe(eps, pe_range)
                df_pe = pd.DataFrame({"PE": pe_range, "估算價格": fair_price, "價差%": (fair_price - price)/price*100})
                st.dataframe(df_pe.round(2)) 
        except Exception as e:
            st.warning(f"計算 PE 合理價時發生錯誤: {e}")

        st.subheader("🔍 其他估值試算")
        tab1, tab2, tab3 = st.tabs(["PE 法", "PB 法", "DCF (簡版)"])
        
        default_pe = float(info.get("trailingPE", 15.0))
        default_eps = float(info.get("trailingEps", 1.0))
        default_pb = float(info.get("priceToBook", 2.0))
        default_bvps = float(info.get("bookValue", 10.0))

        with tab1:
            try:
                pe_input = st.slider("預期本益比", 5.0, 50.0, default_pe, step=0.1) 
                eps_input = st.number_input("預估 EPS", value=default_eps, format="%.2f")
                if eps_input is not None and pe_input is not None:
                    fair = pe_input * eps_input
                    st.write(f"📌 預估股價：{fair:.2f}")
                else:
                    st.warning("請輸入有效的 EPS。")
            except Exception as e:
                st.warning(f"PE 法估值計算錯誤: {e}")

        with tab2:
            try:
                pb_input = st.slider("預期 PB 倍數", 0.5, 10.0, default_pb, step=0.1) 
                bvps_input = st.number_input("每股淨值", value=default_bvps, format="%.2f")
                if bvps_input is not None and pb_input is not None:
                    fair = pb_input * bvps_input
                    st.write(f"📌 預估股價：{fair:.2f}")
                else:
                    st.warning("請輸入有效的每股淨值。")
            except Exception as e:
                st.warning(f"PB 法估值計算錯誤: {e}")

        with tab3:
            try:
                if default_eps is None or default_eps == 0:
                    st.warning("無法取得有效的 EPS，無法進行 DCF 估值。")
                else:
                    future_eps_growth = st.number_input("每年 EPS 成長率 (%)", value=5.0, format="%.2f")
                    years = st.slider("預估年數", 1, 10, 5)
                    discount = st.slider("折現率 (%)", 5.0, 15.0, 10.0, step=0.1)
                    
                    eps_list = [default_eps * ((1 + future_eps_growth / 100) ** i) for i in range(1, years + 1)]
                    discount_rate = discount / 100
                    
                    dcf = sum([e / ((1 + discount_rate) ** (i + 1)) for i, e in enumerate(eps_list)])
                    st.write(f"📌 DCF 預估價值：約 {dcf:.2f}")
            except Exception as e:
                st.warning(f"DCF 計算錯誤: {e}")
    else:
        st.info("找不到符合條件的股票，請嘗試其他關鍵字。")
�
