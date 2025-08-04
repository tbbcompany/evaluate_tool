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
import json
import re

# --- 主應用程式設定 ---
# 備註：此應用程式需要安裝 xlsxwriter 套件才能正常匯出 Excel。
# 請在您的環境中執行: pip install xlsxwriter
st.set_page_config(page_title="多功能財務分析工具", layout="wide")
st.title("📈 多功能財務分析工具")

# --- 工具一：股票估值工具 (簡易版) ---
def run_stock_valuation_app():
    """
    執行簡易版的股票估值工具。
    """
    st.header("股票估值工具 (簡易版)")
    st.markdown("---")

    @st.cache_data
    def load_stock_list():
        """
        載入台灣和美國的股票列表。
        """
        # 載入台灣股票列表
        url_tw = "https://mops.twse.com.tw/mops/web/ajax_t51sb01"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1",
            "queryName": "co_id", "inpuType": "co_id", "TYPEK": "all", "isQuery": "Y"
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

    def search_symbol(keyword, market, tw_df, us_df):
        if market == "台股":
            if tw_df.empty:
                st.info("台股列表資料未載入，無法搜尋。請檢查上方錯誤訊息。")
                return pd.DataFrame(columns=["股票代號", "公司名稱"])
            
            if keyword.isdigit():
                results = tw_df[tw_df["股票代號"].astype(str).str.contains(keyword)]
            else:
                results = tw_df[tw_df["公司名稱"].astype(str).str.contains(keyword, case=False)]
            return results[["股票代號", "公司名稱"]]
        else: # 美股
            if us_df.empty:
                st.info("美股列表資料未載入，無法搜尋。請檢查上方錯誤訊息。")
                return pd.DataFrame(columns=["Symbol", "Name"])
            return us_df[us_df["Name"].astype(str).str.contains(keyword, case=False) | us_df["Symbol"].astype(str).str.contains(keyword, case=False)]

    def get_dividends_tw(stock_id):
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
                    st.warning(f"從 Goodinfo! 取得 {stock_id} 的股利資料，但未找到有效的表格數據。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
            else:
                st.warning(f"無法從 Goodinfo! 取得 {stock_id} 的股利資料表格。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
        except requests.exceptions.RequestException as e:
            st.error(f"取得股利資料時發生網路錯誤: {e}。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
        except Exception as e:
            st.error(f"解析股利資料時發生錯誤: {e}。**台股資料來源為網頁爬蟲，易受網站更新影響。**")
        return div_df

    def show_dividend_chart(div_df):
        fig, ax = plt.subplots(figsize=(5,3))
        ax.bar(div_df["Year"], div_df["Cash"], label="現金股利")
        ax.bar(div_df["Year"], div_df["Stock"], bottom=div_df["Cash"], label="股票股利")
        ax.set_ylabel("股利")
        ax.set_title("近三年股利政策")
        ax.legend()
        st.pyplot(fig)

    # --- UI 介面 ---
    taiwan_df, us_df = load_stock_list()

    market = st.radio("選擇市場：", ["台股", "美股"], horizontal=True, key="stock_market_selector")
    keyword = st.text_input("輸入股票代號或名稱：", key="stock_keyword_input")

    if keyword:
        result = search_symbol(keyword, market, taiwan_df, us_df)
        if not result.empty:
            if market == "台股":
                selection_options = result.values.tolist()
                format_func = lambda x: f"{x[0]} - {x[1]}"
            else:
                selection_options = result[['Symbol', 'Name']].values.tolist()
                format_func = lambda x: f"{x[0]} - {x[1]}"

            selection = st.selectbox("選擇股票：", selection_options, format_func=format_func, key="stock_selector")
            
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
                if not info or 'currentPrice' not in info:
                    st.error(f"無法取得 {ticker} 的股票資訊，請確認代號是否正確或稍後再試。")
                    st.stop()
            except Exception as e:
                st.error(f"取得 {ticker} 股票資訊時發生錯誤: {e}")
                st.stop()

            st.subheader(f"📊 {info.get('longName', '未知公司')} 基本資料")
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
                    with col1:
                        show_dividend_chart(div_df)
                else:
                    st.info("台股股利資料可能無法取得或不存在。")

            st.subheader("📐 合理價位與價差建議")
            # --- Price-to-Earnings (P/E) Ratio Valuation ---
            st.write("**本益比 (P/E Ratio) 估值**")
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
                    fair_price = eps * np.array(pe_range)
                    df_pe = pd.DataFrame({"PE": pe_range, "估算價格": fair_price, "價差%": (fair_price - price)/price*100})
                    st.dataframe(df_pe.round(2))
            except Exception as e:
                st.warning(f"計算 PE 合理價時發生錯誤: {e}")

            # --- Price-to-Sales (P/S) Ratio Valuation ---
            st.write("---")
            st.write("**股價營收比 (P/S Ratio) 估值**")
            try:
                ps = info.get("priceToSalesTrailing12Months")
                sps = info.get("revenuePerShare")
                price = info.get("currentPrice")

                if ps is None or sps is None or price is None:
                    st.info("無法取得完整的 P/S 或 每股營收 資料，無法計算 P/S 合理價。")
                else:
                    ps = float(ps)
                    sps = float(sps)
                    price = float(price)
                    ps_range = [ps * 0.8, ps, ps * 1.2]
                    fair_price_ps = sps * np.array(ps_range)
                    df_ps = pd.DataFrame({"P/S": ps_range, "估算價格": fair_price_ps, "價差%": (fair_price_ps - price)/price*100})
                    st.dataframe(df_ps.round(2))
            except Exception as e:
                st.warning(f"計算 P/S 合理價時發生錯誤: {e}")


            # --- Classic Value Metrics ---
            st.subheader("經典價值指標")
            col_g, col_d = st.columns(2)

            # Graham Number
            with col_g:
                st.write("**葛拉漢價值 (Graham Number)**")
                try:
                    eps = info.get('trailingEps')
                    bvps = info.get('bookValue')
                    if eps is not None and bvps is not None and eps > 0 and bvps > 0:
                        graham_number = np.sqrt(22.5 * eps * bvps)
                        st.metric(label="葛拉漢數字", value=f"{graham_number:.2f}")
                        st.caption("衡量合理價的保守指標，適用於穩定獲利公司。")
                    else:
                        st.info("EPS 或每股淨值為負或缺失，不適用葛拉漢數字。")
                except Exception as e:
                    st.warning(f"計算葛拉漢價值時出錯: {e}")

            # Dividend Yield Valuation
            with col_d:
                st.write("**股利回推價值**")
                try:
                    div_rate = info.get('dividendRate')
                    avg_div_yield = info.get('fiveYearAvgDividendYield') # This is in percent, e.g., 2.5 for 2.5%

                    if div_rate is not None and avg_div_yield is not None and avg_div_yield > 0:
                        fair_value_div = div_rate / (avg_div_yield / 100)
                        st.metric(label="五年平均股息回推價", value=f"{fair_value_div:.2f}")
                        st.caption("以五年平均殖利率回推的價值，適用於穩定發放股利的公司。")
                    else:
                        st.info("缺少股利或五年平均殖利率資料，不適用此估值法。")
                except Exception as e:
                    st.warning(f"計算股利回推價值時出錯: {e}")


            st.subheader("🔍 手動估值試算")
            tab1, tab2, tab3 = st.tabs(["PE 法", "PB 法", "DCF (簡版)"])
            
            default_pe = float(info.get("trailingPE", 15.0)) if info.get("trailingPE") else 15.0
            default_eps = float(info.get("trailingEps", 1.0)) if info.get("trailingEps") else 1.0
            default_pb = float(info.get("priceToBook", 2.0)) if info.get("priceToBook") else 2.0
            default_bvps = float(info.get("bookValue", 10.0)) if info.get("bookValue") else 10.0

            with tab1:
                try:
                    pe_input = st.slider("預期本益比", 5.0, 50.0, default_pe, step=0.1, key="pe_slider")
                    eps_input = st.number_input("預估 EPS", value=default_eps, format="%.2f", key="eps_input_pe")
                    if eps_input is not None and pe_input is not None:
                        fair = pe_input * eps_input
                        st.write(f"📌 預估股價：{fair:.2f}")
                except Exception as e:
                    st.warning(f"PE 法估值計算錯誤: {e}")

            with tab2:
                try:
                    pb_input = st.slider("預期 PB 倍數", 0.5, 10.0, default_pb, step=0.1, key="pb_slider")
                    bvps_input = st.number_input("每股淨值", value=default_bvps, format="%.2f", key="bvps_input_pb")
                    if bvps_input is not None and pb_input is not None:
                        fair = pb_input * bvps_input
                        st.write(f"📌 預估股價：{fair:.2f}")
                except Exception as e:
                    st.warning(f"PB 法估值計算錯誤: {e}")

            with tab3:
                try:
                    if default_eps is None or default_eps == 0:
                        st.warning("無法取得有效的 EPS，無法進行 DCF 估值。")
                    else:
                        future_eps_growth = st.number_input("每年 EPS 成長率 (%)", value=5.0, format="%.2f", key="dcf_growth")
                        years = st.slider("預估年數", 1, 10, 5, key="dcf_years")
                        discount = st.slider("折現率 (%)", 5.0, 15.0, 10.0, step=0.1, key="dcf_discount")
                        
                        eps_list = [default_eps * ((1 + future_eps_growth / 100) ** i) for i in range(1, years + 1)]
                        discount_rate = discount / 100
                        
                        dcf = sum([e / ((1 + discount_rate) ** (i + 1)) for i, e in enumerate(eps_list)])
                        st.write(f"📌 DCF 預估價值：約 {dcf:.2f}")
                except Exception as e:
                    st.warning(f"DCF 計算錯誤: {e}")
        else:
            st.info("找不到符合條件的股票，請嘗試其他關鍵字。")


# --- 工具二：公司&債券評價全功能工具 (專業版) ---
def run_comprehensive_valuation_app():
    """
    執行專業版的公司與債券評價工具。
    """
    st.header("公司&債券評價全功能工具 (專業版)")
    st.markdown("---")

    ADMIN_PASSWORD = "tbb1840"

    # ====== 預設欄位、公式、評價方法 ======
    default_fields = [
        {"name": "股價", "key": "stock_price"}, {"name": "流通股數", "key": "shares"},
        {"name": "EPS（每股盈餘）", "key": "eps"}, {"name": "淨利（Net Income）", "key": "net_income"},
        {"name": "本益比（PE倍數）", "key": "pe_ratio"}, {"name": "每股帳面價值", "key": "bvps"},
        {"name": "股東權益（Equity）", "key": "equity"}, {"name": "本淨比（PB倍數）", "key": "pb_ratio"},
        {"name": "EBITDA（稅息折舊攤提前獲利）", "key": "ebitda"}, {"name": "EV/EBITDA倍數", "key": "ev_ebitda_ratio"},
        {"name": "現金（Cash）", "key": "cash"}, {"name": "有息負債（Debt）", "key": "debt"},
        {"name": "併購價格/案例參考", "key": "precedent_price"},
        # DCF
        {"name": "FCF_1（第1年自由現金流）", "key": "fcf1"}, {"name": "FCF_2（第2年自由現金流）", "key": "fcf2"},
        {"name": "FCF_3（第3年自由現金流）", "key": "fcf3"}, {"name": "FCF_4（第4年自由現金流）", "key": "fcf4"},
        {"name": "FCF_5（第5年自由現金流）", "key": "fcf5"}, {"name": "折現率（Discount Rate, r）", "key": "discount_rate"},
        {"name": "永續成長率（Perpetual Growth, g）", "key": "perpetual_growth"},
        # EVA
        {"name": "稅後營運利潤（NOPAT）", "key": "nopat"}, {"name": "投入資本（Capital）", "key": "capital"},
        {"name": "資本成本率（Cost of Capital）", "key": "cost_of_capital"},
        # 盈餘資本化
        {"name": "預期盈餘", "key": "expected_earnings"}, {"name": "資本化率", "key": "capitalization_rate"},
        # DDM
        {"name": "每股股利", "key": "dividend_per_share"}, {"name": "股利成長率", "key": "dividend_growth"},
        # 資產法
        {"name": "資產總額", "key": "assets"}, {"name": "負債總額", "key": "liabilities"},
        {"name": "資產重估值", "key": "revalued_assets"},
        # 清算
        {"name": "清算資產", "key": "liquidation_assets"}, {"name": "清算負債", "key": "liquidation_liabilities"},
        # 創投/私募/特殊
        {"name": "預期退出市值", "key": "future_valuation"}, {"name": "目標年化報酬率（%）", "key": "target_return_rate"},
        {"name": "投資年數", "key": "years"}, {"name": "投資金額", "key": "investment"},
        {"name": "目標倍數", "key": "target_multiple"}, {"name": "換得股權比例（0~1）", "key": "ownership"},
        {"name": "預期未來每股價", "key": "future_stock_price"},
        # 分段混合/子事業
        {"name": "子事業價值1（例：A事業部）", "key": "sub_value1"}, {"name": "子事業價值2（例：B事業部）", "key": "sub_value2"},
        {"name": "子事業價值3（例：C事業部）", "key": "sub_value3"},
        # 行業自定
        {"name": "自定行業指標（例：SaaS_LTV/CAC）", "key": "custom_metric"},
        # 債券
        {"name": "債券面額（Face Value）", "key": "bond_face_value"}, {"name": "年票面利率（%）", "key": "bond_coupon_rate"},
        {"name": "債券現價", "key": "bond_market_price"}, {"name": "每年付息次數", "key": "bond_coupon_freq"},
        {"name": "到期年數", "key": "bond_years"}, {"name": "市場折現率（YTM, %）", "key": "bond_ytm"},
        # 互斥防呆專用
        {"name": "每股營收", "key": "sales_per_share"}, {"name": "營收總額", "key": "sales_total"},
    ]

    default_formulas = {
        "market_price": "stock_price * shares if stock_price and shares else None",
        "pe_comp": "pe_ratio * net_income if pe_ratio and net_income else None",
        "pb_comp": "pb_ratio * equity if pb_ratio and equity else None",
        "ev_ebitda_comp": "ev_ebitda_ratio * ebitda + cash - debt if ev_ebitda_ratio and ebitda and cash is not None and debt is not None else None",
        "precedent_trans": "precedent_price if precedent_price else None",
        "dcf": "sum([fcf1/(1+discount_rate)**1, fcf2/(1+discount_rate)**2, fcf3/(1+discount_rate)**3, fcf4/(1+discount_rate)**4, fcf5/(1+discount_rate)**5]) + (fcf5*(1+perpetual_growth)/(discount_rate-perpetual_growth))/(1+discount_rate)**5 if all(x is not None for x in [fcf1, fcf2, fcf3, fcf4, fcf5, discount_rate, perpetual_growth]) and (discount_rate > perpetual_growth) else None",
        "eva": "(nopat - capital*cost_of_capital) if nopat and capital and cost_of_capital else None",
        "cap_earnings": "expected_earnings / capitalization_rate if expected_earnings and capitalization_rate else None",
        "ddm": "dividend_per_share / (discount_rate - dividend_growth) * shares if dividend_per_share and discount_rate and dividend_growth and shares and (discount_rate > dividend_growth) else None",
        "book_asset": "assets - liabilities if assets is not None and liabilities is not None else None",
        "asset_reval": "revalued_assets - liabilities if revalued_assets is not None and liabilities is not None else None",
        "liquidation": "liquidation_assets - liquidation_liabilities if liquidation_assets is not None and liquidation_liabilities is not None else None",
        "vc_exit": "future_valuation / (1 + target_return_rate/100)**years if future_valuation and target_return_rate and years else None",
        "vc_multiple": "investment * target_multiple if investment and target_multiple else None",
        "vc_equity": "investment / ownership if investment and ownership else None",
        "vc_rev_valuation": "future_stock_price * shares / (1 + target_return_rate/100)**years if future_stock_price and shares and target_return_rate and years else None",
        "real_option": "None",
        "sotp": "sum(filter(None, [sub_value1, sub_value2, sub_value3]))",
        "custom_industry": "custom_metric if custom_metric else None",
        "bond_pv": "(sum([bond_face_value * bond_coupon_rate / bond_coupon_freq / 100 / (1 + bond_ytm/100/bond_coupon_freq) ** (i+1) for i in range(int(bond_years * bond_coupon_freq))]) + bond_face_value / (1 + bond_ytm/100/bond_coupon_freq) ** (bond_years * bond_coupon_freq)) if all(x is not None for x in [bond_face_value, bond_coupon_rate, bond_coupon_freq, bond_ytm, bond_years]) else None",
        "bond_current_yield": "(bond_face_value * bond_coupon_rate / 100) / bond_market_price if bond_face_value and bond_coupon_rate and bond_market_price else None",
        "bond_par_value": "bond_face_value if bond_face_value else None",
        "bond_ytm_info": "'到期殖利率(YTM)為使債券現值等於市價時的折現率，通常需用專業計算器或Excel IRR求解'",
        "sales_total_autofill": "sales_per_share * shares if sales_per_share and shares and not sales_total else sales_total if sales_total else None",
    }

    default_methods = [
        {"name": "市價法", "key": "market_price"}, {"name": "同業PE倍數法", "key": "pe_comp"},
        {"name": "同業PB倍數法", "key": "pb_comp"}, {"name": "同業EV/EBITDA", "key": "ev_ebitda_comp"},
        {"name": "併購交易法", "key": "precedent_trans"}, {"name": "DCF現金流折現法", "key": "dcf"},
        {"name": "EVA經濟附加價值法", "key": "eva"}, {"name": "盈餘資本化法", "key": "cap_earnings"},
        {"name": "股利折現法(DDM)", "key": "ddm"}, {"name": "帳面資產法", "key": "book_asset"},
        {"name": "資產重估法", "key": "asset_reval"}, {"name": "清算價值法", "key": "liquidation"},
        {"name": "創投-回推法", "key": "vc_exit"}, {"name": "創投-倍數法", "key": "vc_multiple"},
        {"name": "創投-股權分割法", "key": "vc_equity"}, {"name": "創投-市值倒推法", "key": "vc_rev_valuation"},
        {"name": "選擇權定價法", "key": "real_option"}, {"name": "分段混合法SOTP", "key": "sotp"},
        {"name": "行業自定指標", "key": "custom_industry"},
        # 債券
        {"name": "債券現值法（DCF）", "key": "bond_pv"}, {"name": "當期殖利率法", "key": "bond_current_yield"},
        {"name": "平價法", "key": "bond_par_value"}, {"name": "YTM說明", "key": "bond_ytm_info"},
        # 新增：營收總額自動計算結果也展示
        {"name": "營收總額(自動計算)", "key": "sales_total_autofill"},
    ]

    # 初始化 session_state
    if "comp_fields" not in st.session_state:
        st.session_state.comp_fields = default_fields.copy()
    if "comp_formulas" not in st.session_state:
        st.session_state.comp_formulas = default_formulas.copy()
    if "comp_methods" not in st.session_state:
        st.session_state.comp_methods = default_methods.copy()
    if "comp_inputs" not in st.session_state:
        st.session_state.comp_inputs = {f['key']: "" for f in st.session_state.comp_fields}
    if "comp_admin_mode" not in st.session_state:
        st.session_state.comp_admin_mode = False

    def safe_float(val):
        try:
            return float(str(val).replace(',', '').replace(' ', ''))
        except (ValueError, TypeError):
            return None

    # ====== 欄位輸入 ======
    st.sidebar.header("專業版：請輸入評價資料")
    for f in st.session_state.comp_fields:
        val = st.sidebar.text_input(
            f['name'],
            value=st.session_state.comp_inputs.get(f['key'], ""),
            key=f"comp_{f['key']}"
        )
        st.session_state.comp_inputs[f['key']] = val

    # ====== 互斥防呆提醒 ======
    if (st.session_state.comp_inputs.get("sales_per_share") and st.session_state.comp_inputs.get("sales_total")):
        st.warning("⚠️ 請勿同時填寫『每股營收』與『營收總額』，僅需擇一輸入！如都填將以『營收總額』為主計算。")
    elif (st.session_state.comp_inputs.get("sales_per_share") and st.session_state.comp_inputs.get("shares")):
        try:
            auto_sales_total = float(st.session_state.comp_inputs["sales_per_share"]) * float(st.session_state.comp_inputs["shares"])
            st.info(f"自動計算營收總額：{auto_sales_total:,.0f}（僅供參考，如已填『營收總額』則以輸入值為主）")
        except:
            pass

    # ====== 公式計算 ======
    def parse_variables(expr):
        reserved = set(['if', 'else', 'None', 'sum', 'lambda', 'range', 'float', 'int', 'str', 'for', 'in', 'True', 'False', 'filter'])
        found = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expr))
        return found - reserved

    v = {f['key']: safe_float(st.session_state.comp_inputs.get(f['key'], "")) for f in st.session_state.comp_fields}
    
    formulas = st.session_state.comp_formulas.copy()
    dependencies = {k: parse_variables(expr) for k, expr in formulas.items()}

    def topo_evaluate(formulas, v):
        result = v.copy()
        pending = set(formulas.keys())
        error_msgs = {}
        max_iter = len(formulas) + 5
        iter_count = 0
        while pending and iter_count < max_iter:
            evaluated_this_round = False
            for k in list(pending):
                deps = dependencies.get(k, set())
                if deps.issubset(result.keys()):
                    try:
                        result[k] = eval(formulas[k], {"__builtins__": {}}, result)
                        evaluated_this_round = True
                    except Exception as e:
                        result[k] = None
                        error_msgs[k] = f"公式錯誤：{str(e)}"
                    pending.remove(k)
            if not evaluated_this_round and pending: # 避免無限循環
                break
            iter_count += 1
        for k in pending:
            error_msgs[k] = "欄位依賴未解決（可能有循環或公式錯誤/不存在欄位）"
            result[k] = None
        return result, error_msgs

    results, error_msgs = topo_evaluate(formulas, v)

    st.subheader("公司與債券評價方法總覽")
    df = pd.DataFrame([
        {"評價方法": m["name"], "估值（元/比率/說明）": (f"{results.get(m['key']):,.4f}" if isinstance(results.get(m['key']), (int, float)) else str(results.get(m['key'], '')))}
        for m in st.session_state.comp_methods
    ])
    st.table(df)

    if error_msgs and st.session_state.comp_admin_mode:
        st.error("⚠️ 有公式錯誤或依賴問題如下：")
        for k, msg in error_msgs.items():
            st.write(f"【{k}】：{msg}")

    # ====== 功能按鈕 ======
    col1, col2 = st.columns(2)
    with col1:
        if st.button("一鍵清除所有輸入", key="comp_clear"):
            st.session_state.comp_inputs = {f['key']: "" for f in st.session_state.comp_fields}
            st.rerun()
    with col2:
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_input = pd.DataFrame([(f['name'], st.session_state.comp_inputs.get(f['key'], "")) for f in st.session_state.comp_fields], columns=["項目", "輸入值"])
                df_out = df.copy()
                df_input.to_excel(writer, sheet_name="輸入數據", index=False)
                df_out.to_excel(writer, sheet_name="評價總表", index=False)
            
            st.download_button(
                label="匯出Excel報告",
                data=output.getvalue(),
                file_name="公司債券評價結果.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ImportError:
            st.error("匯出 Excel 需要 'xlsxwriter' 套件。請執行 `pip install xlsxwriter` 安裝。")
        except Exception as e:
            st.error(f"匯出 Excel 時發生錯誤: {e}")

    # ====== 管理員功能 ======
    with st.expander("管理員功能（欄位/公式/匯出/還原）", expanded=False):
        if not st.session_state.comp_admin_mode:
            pwd = st.text_input("請輸入管理密碼", type="password", key="comp_admin_pwd")
            # 新增一個按鈕來觸發密碼驗證和頁面重新執行
            if st.button("登入管理員模式", key="comp_admin_login_button"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.comp_admin_mode = True
                    st.rerun()
                else:
                    st.error("密碼錯誤，請重新輸入。")
        else:
            st.success("管理員已登入。")
            if st.button("登出管理員模式", key="comp_admin_logout"):
                st.session_state.comp_admin_mode = False
                st.rerun()
            
            st.markdown("### 欄位與公式管理")
            # 編輯公式
            st.subheader("公式管理（可即時修改）")
            for k in st.session_state.comp_formulas:
                new_formula = st.text_area(f"{k} 公式", value=st.session_state.comp_formulas[k], key=f"formula_{k}", height=50)
                st.session_state.comp_formulas[k] = new_formula
            
            if st.button("儲存所有公式變更", key="comp_save_formulas"):
                st.success("已更新公式！")
                st.rerun()

            st.markdown("---")
            # 匯出/還原設定
            st.subheader("設定檔匯出與還原")
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            config_data = {
                "fields": st.session_state.comp_fields,
                "formulas": st.session_state.comp_formulas,
                "methods": st.session_state.comp_methods
            }
            config_json = json.dumps(config_data, ensure_ascii=False, indent=2)
            st.download_button(
                label=f"下載當前完整設定檔",
                data=io.BytesIO(config_json.encode("utf-8")),
                file_name=f"valuation_config_{now_str}.json",
                mime="application/json"
            )

            uploaded_file = st.file_uploader("上傳設定檔(.json)進行還原", type=["json"], key="config_restore")
            if uploaded_file:
                try:
                    data = json.load(uploaded_file)
                    if "fields" in data and "formulas" in data and "methods" in data:
                        st.session_state.comp_fields = data["fields"]
                        st.session_state.comp_formulas = data["formulas"]
                        st.session_state.comp_methods = data["methods"]
                        # 重置輸入以匹配新欄位
                        st.session_state.comp_inputs = {f['key']: "" for f in st.session_state.comp_fields}
                        st.success("設定檔已成功還原！頁面將重新整理。")
                        st.rerun()
                    else:
                        st.error("設定檔格式錯誤，缺少必要的 'fields', 'formulas', 或 'methods' 鍵。")
                except Exception as e:
                    st.error(f"上傳或解析錯誤：{e}")

            if st.button("還原為系統預設值", key="comp_restore_default"):
                st.session_state.comp_fields = default_fields.copy()
                st.session_state.comp_formulas = default_formulas.copy()
                st.session_state.comp_methods = default_methods.copy()
                st.session_state.comp_inputs = {f['key']: "" for f in st.session_state.comp_fields}
                st.success("已還原為系統預設值！")
                st.rerun()

# --- 主應用程式選擇邏輯 ---
# 初始化 session_state
if 'app_choice' not in st.session_state:
    st.session_state.app_choice = "股票估值工具 (簡易版)" # 預設顯示簡易版

st.sidebar.title("工具選單")

if st.sidebar.button("股票估值工具 (簡易版)", use_container_width=True):
    st.session_state.app_choice = "股票估值工具 (簡易版)"

if st.sidebar.button("公司&債券評價工具 (專業版)", use_container_width=True):
    st.session_state.app_choice = "公司&債券評價工具 (專業版)"


# 根據選擇顯示對應的應用程式
if st.session_state.app_choice == "股票估值工具 (簡易版)":
    run_stock_valuation_app()
elif st.session_state.app_choice == "公司&債券評價工具 (專業版)":
    run_comprehensive_valuation_app()
