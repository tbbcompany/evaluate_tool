import streamlit as st
import pandas as pd
import numpy as np
import datetime
import requests
from io import StringIO
import matplotlib.pyplot as plt
import json
import io
import re

# ====== 頁面基本設定 ======
st.set_page_config(page_title="綜合財務工具", layout="wide")
st.title("多功能財務工具")

# ====== 主選單 ======
tool_choice = st.sidebar.radio(
    "請選擇您要使用的工具：",
    ["股票估值工具", "公司&債券評價工具"]
)

# ====== 股票估值工具 (來自你的第一個程式碼) ======
def run_stock_valuation_tool():
    st.subheader("📈 股票估值工具 v2")

    @st.cache_data
    def load_tw_stock_list():
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers)
        df = pd.read_html(r.text)[0]
        df.columns = df.iloc[0]
        df = df[1:]
        df = df[~df["有價證券代號及名稱"].isna()]
        df["代號"] = df["有價證券代號及名稱"].apply(lambda x: str(x).split()[0])
        df["名稱"] = df["有價證券代號及名稱"].apply(lambda x: str(x).split()[1] if len(str(x).split()) > 1 else "")
        return df[["代號", "名稱"]]

    @st.cache_data
    def get_google_finance_price(stock_code):
        url = f"https://www.google.com/finance/quote/{stock_code}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            return None
        try:
            price_str = r.text.split('data-last-price="')[1].split('"')[0]
            return float(price_str.replace(",", ""))
        except Exception:
            return None

    def get_sample_dividend_data(stock_code):
        np.random.seed(abs(hash(stock_code)) % (10 ** 8))
        years = [datetime.datetime.now().year - i for i in range(3)][::-1]
        dividends = np.round(np.random.uniform(1, 5, size=3), 2)
        return pd.DataFrame({"年度": years, "現金股利": dividends})

    def plot_dividend_chart(div_df):
        fig, ax = plt.subplots(figsize=(5,3))
        ax.bar(div_df["年度"], div_df["現金股利"], color="skyblue")
        ax.set_title("近三年股利政策")
        ax.set_ylabel("現金股利 (元)")
        st.pyplot(fig)

    def calculate_fair_value(div_df, pe=15):
        avg_div = div_df["現金股利"].mean()
        estimated_eps = avg_div * 1.2
        fair_price = estimated_eps * pe
        return round(fair_price, 2)

    stock_type = st.radio("選擇市場類型", ["台股", "美股"], horizontal=True)

    code = ""
    name = ""
    price = None

    if stock_type == "台股":
        df_stocks = load_tw_stock_list()
        keyword = st.text_input("輸入股票代號或名稱（模糊搜尋）", "")
        matched = df_stocks[df_stocks["代號"].str.contains(keyword) | df_stocks["名稱"].str.contains(keyword)]
        selected_stock = st.selectbox("請選擇股票", matched["代號"] + " - " + matched["名稱"] if not matched.empty else [])
        if selected_stock:
            code = selected_stock.split(" - ")[0]
            name = selected_stock.split(" - ")[1]
            price = get_google_finance_price(f"TPE:{code}")
    else:
        code = st.text_input("請輸入美股代號，例如 AAPL")
        name = code
        if code:
            price = get_google_finance_price(code)

    if code and price:
        st.subheader(f"目前股價：${price:.2f}")

        div_df = get_sample_dividend_data(code)
        plot_dividend_chart(div_df)

        fair_price = calculate_fair_value(div_df)
        delta = price - fair_price
        suggestion = "✅ 低估" if delta < 0 else "⚠️ 高估"

        st.metric("估算合理價位", fair_price, delta)
        st.info(f"評價建議：{suggestion}")

        st.markdown("---")
        st.subheader("🧮 估值計算")
        pe = st.slider("本益比參數", 5, 30, 15)
        pb = st.slider("股價淨值比參數", 0.5, 5.0, 1.5, step=0.1)
        eps = st.number_input("預估每股盈餘 EPS", value=div_df["現金股利"].mean()*1.2)
        bvps = st.number_input("每股淨值 BVPS", value=15.0)

        fair_by_pe = round(eps * pe, 2)
        fair_by_pb = round(bvps * pb, 2)
        dcf_fair = round((eps * 1.1) * 12, 2)

        st.write(f"📊 PE 法估值：{fair_by_pe}")
        st.write(f"📊 PB 法估值：{fair_by_pb}")
        st.write(f"📊 DCF 簡化估值：{dcf_fair}")
    elif code:
        st.warning("無法取得股票資料，請檢查代號或稍後再試。")
    else:
        st.warning("請先輸入正確代號或選擇股票。")

# ====== 公司&債券評價工具 (來自你的第二個程式碼) ======
def run_valuation_tool():
    st.subheader("公司&債券評價全功能工具")

    ADMIN_PASSWORD = "tbb1840"

    # ====== 欄位、公式、評價方法（預設）======
    default_fields = [
        {"name": "股價", "key": "stock_price"},
        {"name": "流通股數", "key": "shares"},
        {"name": "EPS（每股盈餘）", "key": "eps"},
        {"name": "淨利（Net Income）", "key": "net_income"},
        {"name": "本益比（PE倍數）", "key": "pe_ratio"},
        {"name": "每股帳面價值", "key": "bvps"},
        {"name": "股東權益（Equity）", "key": "equity"},
        {"name": "本淨比（PB倍數）", "key": "pb_ratio"},
        {"name": "EBITDA（稅息折舊攤提前獲利）", "key": "ebitda"},
        {"name": "EV/EBITDA倍數", "key": "ev_ebitda_ratio"},
        {"name": "現金（Cash）", "key": "cash"},
        {"name": "有息負債（Debt）", "key": "debt"},
        {"name": "併購價格/案例參考", "key": "precedent_price"},
        # DCF
        {"name": "FCF_1（第1年自由現金流）", "key": "fcf1"},
        {"name": "FCF_2（第2年自由現金流）", "key": "fcf2"},
        {"name": "FCF_3（第3年自由現金流）", "key": "fcf3"},
        {"name": "FCF_4（第4年自由現金流）", "key": "fcf4"},
        {"name": "FCF_5（第5年自由現金流）", "key": "fcf5"},
        {"name": "折現率（Discount Rate, r）", "key": "discount_rate"},
        {"name": "永續成長率（Perpetual Growth, g）", "key": "perpetual_growth"},
        # EVA
        {"name": "稅後營運利潤（NOPAT）", "key": "nopat"},
        {"name": "投入資本（Capital）", "key": "capital"},
        {"name": "資本成本率（Cost of Capital）", "key": "cost_of_capital"},
        # 盈餘資本化
        {"name": "預期盈餘", "key": "expected_earnings"},
        {"name": "資本化率", "key": "capitalization_rate"},
        # DDM
        {"name": "每股股利", "key": "dividend_per_share"},
        {"name": "股利成長率", "key": "dividend_growth"},
        # 資產法
        {"name": "資產總額", "key": "assets"},
        {"name": "負債總額", "key": "liabilities"},
        {"name": "資產重估值", "key": "revalued_assets"},
        # 清算
        {"name": "清算資產", "key": "liquidation_assets"},
        {"name": "清算負債", "key": "liquidation_liabilities"},
        # 創投/私募/特殊
        {"name": "預期退出市值", "key": "future_valuation"},
        {"name": "目標年化報酬率（%）", "key": "target_return_rate"},
        {"name": "投資年數", "key": "years"},
        {"name": "投資金額", "key": "investment"},
        {"name": "目標倍數", "key": "target_multiple"},
        {"name": "換得股權比例（0~1）", "key": "ownership"},
        {"name": "預期未來每股價", "key": "future_stock_price"},
        # 分段混合/子事業
        {"name": "子事業價值1（例：A事業部）", "key": "sub_value1"},
        {"name": "子事業價值2（例：B事業部）", "key": "sub_value2"},
        {"name": "子事業價值3（例：C事業部）", "key": "sub_value3"},
        # 行業自定
        {"name": "自定行業指標（例：SaaS_LTV/CAC）", "key": "custom_metric"},
        # 債券
        {"name": "債券面額（Face Value）", "key": "bond_face_value"},
        {"name": "年票面利率（%）", "key": "bond_coupon_rate"},
        {"name": "債券現價", "key": "bond_market_price"},
        {"name": "每年付息次數", "key": "bond_coupon_freq"},
        {"name": "到期年數", "key": "bond_years"},
        {"name": "市場折現率（YTM, %）", "key": "bond_ytm"},
        # 互斥防呆專用
        {"name": "每股營收", "key": "sales_per_share"},
        {"name": "營收總額", "key": "sales_total"},
    ]

    default_formulas = {
        "market_price": "stock_price * shares if stock_price and shares else None",
        "pe_comp": "pe_ratio * net_income if pe_ratio and net_income else None",
        "pb_comp": "pb_ratio * equity if pb_ratio and equity else None",
        "ev_ebitda_comp": "ev_ebitda_ratio * ebitda + cash - debt if ev_ebitda_ratio and ebitda and cash is not None and debt is not None else None",
        "precedent_trans": "precedent_price if precedent_price else None",
        "dcf": "sum([fcf1/(1+discount_rate)**1, fcf2/(1+discount_rate)**2, fcf3/(1+discount_rate)**3, fcf4/(1+discount_rate)**4, fcf5/(1+discount_rate)**5]) + (fcf5*(1+perpetual_growth)/(discount_rate-perpetual_growth))/(1+discount_rate)**5 if all(x is not None for x in [fcf1, fcf2, fcf3, fcf4, fcf5, discount_rate, perpetual_growth]) else None",
        "eva": "(nopat - capital*cost_of_capital) if nopat and capital and cost_of_capital else None",
        "cap_earnings": "expected_earnings / capitalization_rate if expected_earnings and capitalization_rate else None",
        "ddm": "dividend_per_share / (discount_rate - dividend_growth) * shares if dividend_per_share and discount_rate and dividend_growth and shares else None",
        "book_asset": "assets - liabilities if assets and liabilities else None",
        "asset_reval": "revalued_assets - liabilities if revalued_assets and liabilities else None",
        "liquidation": "liquidation_assets - liquidation_liabilities if liquidation_assets and liquidation_liabilities else None",
        "vc_exit": "future_valuation / (1 + target_return_rate/100)**years if future_valuation and target_return_rate and years else None",
        "vc_multiple": "investment * target_multiple if investment and target_multiple else None",
        "vc_equity": "investment / ownership if investment and ownership else None",
        "vc_rev_valuation": "future_stock_price * shares / (1 + target_return_rate/100)**years if future_stock_price and shares and target_return_rate and years else None",
        "real_option": "None",
        "sotp": "sum([sub_value1, sub_value2, sub_value3]) if all(x is not None for x in [sub_value1, sub_value2, sub_value3]) else None",
        "custom_industry": "custom_metric if custom_metric else None",
        "bond_pv": "(sum([bond_face_value * bond_coupon_rate / bond_coupon_freq / 100 / (1 + bond_ytm/100/bond_coupon_freq) ** (i+1) for i in range(int(bond_years * bond_coupon_freq))]) + bond_face_value / (1 + bond_ytm/100/bond_coupon_freq) ** (bond_years * bond_coupon_freq)) if all(x is not None for x in [bond_face_value, bond_coupon_rate, bond_coupon_freq, bond_ytm, bond_years]) else None",
        "bond_current_yield": "(bond_face_value * bond_coupon_rate / 100) / bond_market_price if bond_face_value and bond_coupon_rate and bond_market_price else None",
        "bond_par_value": "bond_face_value if bond_face_value else None",
        "bond_ytm_info": "'到期殖利率(YTM)為使債券現值等於市價時的折現率，通常需用專業計算器或Excel IRR求解' ",
        # 銜接互斥：自動用其中一欄推算總額
        "sales_total_autofill": "sales_per_share * shares if sales_per_share and shares and not sales_total else sales_total if sales_total else None",
    }

    if "fields" not in st.session_state:
        st.session_state.fields = default_fields.copy()
    if "formulas" not in st.session_state:
        st.session_state.formulas = default_formulas.copy()
    if "methods" not in st.session_state:
        st.session_state.methods = default_methods.copy()
    if "inputs" not in st.session_state:
        st.session_state.inputs = {f['key']: "" for f in st.session_state.fields}
    if "admin_mode" not in st.session_state:
        st.session_state.admin_mode = False

    def safe_float(val):
        try:
            return float(str(val).replace(',', '').replace(' ', ''))
        except:
            return None

    # ====== 側邊欄資料輸入 ======
    st.sidebar.header("請輸入公司或債券評價資料")
    for f in st.session_state.fields:
        val = st.sidebar.text_input(
            f['name'],
            value=st.session_state.inputs.get(f['key'], ""),
            key=f['key']
        )
        st.session_state.inputs[f['key']] = val

    # ====== 互斥防呆提醒（每股營收vs營收總額）======
    if (st.session_state.inputs.get("sales_per_share") and st.session_state.inputs.get("sales_total")):
        st.warning("⚠️ 請勿同時填寫『每股營收』與『營收總額』，僅需擇一輸入！如都填將以『營收總額』為主計算。")
    elif (st.session_state.inputs.get("sales_per_share") and st.session_state.inputs.get("shares")):
        try:
            auto_sales_total = float(st.session_state.inputs["sales_per_share"]) * float(st.session_state.inputs["shares"])
            st.info(f"自動計算營收總額：{auto_sales_total:,.0f}（僅供參考，如已填『營收總額』則以輸入值為主）")
        except:
            pass

    # ====== 公式依賴遞推 ======
    def parse_variables(expr):
        reserved = set(['if', 'else', 'None', 'sum', 'lambda', 'range', 'float', 'int', 'str', 'for', 'in', 'True', 'False'])
        found = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expr))
        return found - reserved

    v = {f['key']: safe_float(st.session_state.inputs.get(f['key'], "")) for f in st.session_state.fields}

    formulas = st.session_state.formulas.copy()
    dependencies = {k: parse_variables(expr) for k, expr in formulas.items()}

    def topo_evaluate(formulas, v):
        result = v.copy()
        pending = set(formulas.keys())
        error_msgs = {}
        max_iter = len(formulas) + 5
        iter_count = 0
        while pending and iter_count < max_iter:
            for k in list(pending):
                if dependencies[k] <= set(result.keys()):
                    try:
                        result[k] = eval(formulas[k], {}, result)
                    except Exception as e:
                        result[k] = None
                        error_msgs[k] = f"公式錯誤：{str(e)}"
                    pending.remove(k)
            iter_count += 1
        for k in pending:
            error_msgs[k] = "欄位依賴未解決（可能有循環或公式錯誤/不存在欄位）"
            result[k] = None
        return result, error_msgs

    results, error_msgs = topo_evaluate(formulas, v)

    st.header("公司與債券評價方法總覽")
    df = pd.DataFrame([
        {"評價方法": m["name"], "估值（元/比率/說明）": (f"{results[m['key']]:,.4f}" if isinstance(results[m['key']], float) and results[m['key']] is not None else results[m['key']] if results[m['key']] is not None else "")}
        for m in st.session_state.methods
    ])
    st.table(df)

    if error_msgs and st.session_state.admin_mode:
        st.error("⚠️ 有公式錯誤或依賴問題如下：")
        for k, msg in error_msgs.items():
            st.write(f"【{k}】：{msg}")

    # ====== 匯出 Excel ======
    st.header("匯出 Excel")
    if st.button("匯出Excel"):
        df_input = pd.DataFrame([(f['name'], st.session_state.inputs.get(f['key'], "")) for f in st.session_state.fields], columns=["項目", "輸入值"])
        df_out = pd.DataFrame([
            (m['name'], (f"{results[m['key']]:,.4f}" if isinstance(results[m['key']], float) and results[m['key']] is not None else results[m['key']] if results[m['key']] is not None else "")) for m in st.session_state.methods
        ], columns=["評價方法", "估值（元/比率/說明）"])
        with pd.ExcelWriter("公司債券評價結果.xlsx", engine="openpyxl") as writer:
            df_input.to_excel(writer, sheet_name="輸入數據", index=False)
            df_out.to_excel(writer, sheet_name="評價總表", index=False)
        with open("公司債券評價結果.xlsx", "rb") as file:
            st.download_button("下載Excel", file, file_name="公司債券評價結果.xlsx")

    # ====== 一鍵清除 ======
    if st.button("一鍵清除"):
        st.session_state.inputs = {f['key']: "" for f in st.session_state.fields}
        st.experimental_rerun()

    # ====== 管理員功能 ======
    with st.expander("管理員功能（欄位/公式/匯出/還原）", expanded=False):
        st.markdown("**目前所有公式如下：**")
        st.code(json.dumps(st.session_state.formulas, ensure_ascii=False, indent=2), language="json")
        if not st.session_state.admin_mode:
            pwd = st.text_input("請輸入管理密碼", type="password")
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_mode = True
                st.experimental_rerun()
        else:
            st.success("管理員已登入。")
            if st.button("登出管理員模式"):
                st.session_state.admin_mode = False
                st.experimental_rerun()
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            field_json = json.dumps(st.session_state.fields, ensure_ascii=False, indent=2)
            st.download_button(
                label=f"立即下載欄位清單 (強制備份)",
                data=io.BytesIO(field_json.encode("utf-8")),
                file_name=f"欄位清單_{now_str}.json",
                mime="application/json"
            )
            formula_json = json.dumps(st.session_state.formulas, ensure_ascii=False, indent=2)
            st.download_button(
                label=f"立即下載公式清單 (強制備份)",
                data=io.BytesIO(formula_json.encode("utf-8")),
                file_name=f"公式清單_{now_str}.json",
                mime="application/json"
            )
            # 欄位管理
            st.subheader("欄位管理")
            st.table(pd.DataFrame(st.session_state.fields))
            new_name = st.text_input("新增欄位中文名稱", key="addfield_name")
            new_key = st.text_input("新增欄位英文key", key="addfield_key")
            new_formula = st.text_input("（選填）對應公式內容，空則預設為None", key="addfield_formula")
            if st.button("新增欄位並新增對應公式"):
                if new_name and new_key and not any(f['key'] == new_key for f in st.session_state.fields):
                    st.session_state.fields.append({"name": new_name, "key": new_key})
                    st.session_state.inputs[new_key] = ""
                    if new_formula.strip():
                        st.session_state.formulas[new_key] = new_formula.strip()
                    else:
                        st.session_state.formulas[new_key] = "None"
                    st.success(f"已新增欄位：{new_name} ({new_key})，並自動新增對應公式")
                    st.experimental_rerun()
                elif any(f['key'] == new_key for f in st.session_state.fields):
                    st.error("此英文key已存在，請換一個。")
                else:
                    st.error("欄位名稱與key皆需填寫。")
            # 刪除欄位
            del_options = [f"{f['name']} ({f['key']})" for f in st.session_state.fields]
            del_choice = st.selectbox("選擇要刪除的欄位", del_options, key="del_field_choice")
            if st.button("刪除選定欄位"):
                del_key = st.session_state.fields[del_options.index(del_choice)]['key']
                st.session_state.fields = [f for f in st.session_state.fields if f['key'] != del_key]
                st.session_state.inputs.pop(del_key, None)
                if del_key in st.session_state.formulas:
                    st.session_state.formulas.pop(del_key)
                st.success("已刪除欄位（並同步移除對應公式）")
                st.experimental_rerun()
            # 匯出/還原
            st.markdown("### 欄位與公式設定匯出/還原")
            if st.button("手動匯出欄位清單"):
                st.download_button("下載欄位清單.json", io.BytesIO(field_json.encode("utf-8")), file_name="欄位清單.json")
            if st.button("手動匯出公式清單"):
                st.download_button("下載公式.json", io.BytesIO(formula_json.encode("utf-8")), file_name="公式清單.json")
            up_field_file = st.file_uploader("上傳欄位清單(.json)進行還原", type=["json"], key="fields_restore")
            if up_field_file:
                try:
                    data = json.load(up_field_file)
                    if isinstance(data, list) and all("key" in d and "name" in d for d in data):
                        st.session_state.fields = data
                        for k in list(st.session_state.inputs.keys()):
                            if k not in [f["key"] for f in data]:
                                st.session_state.inputs.pop(k)
                        st.success("欄位清單已還原")
                        st.experimental_rerun()
                    else:
                        st.error("格式錯誤")
                except Exception as e:
                    st.error(f"上傳錯誤：{e}")
            uploaded_file = st.file_uploader("上傳公式(.json)進行還原", type=["json"], key="formulas_restore")
            if uploaded_file:
                try:
                    data = json.load(uploaded_file)
                    if isinstance(data, dict):
                        st.session_state.formulas = data
                        st.success("已成功還原所有公式，立即生效！")
                        st.experimental_rerun()
                    else:
                        st.error("格式錯誤")
                except Exception as e:
                    st.error(f"上傳錯誤：{e}")
            # 公式即時編輯
            st.markdown("---")
            st.subheader("公式管理（可即時修改）")
            for k in st.session_state.formulas:
                new_formula = st.text_input(f"{k} 公式", value=st.session_state.formulas[k], key=f"formula_{k}")
                st.session_state.formulas[k] = new_formula
            if st.button("儲存公式（即時生效）"):
                st.success("已更新公式，立即套用！")
                st.experimental_rerun()

# ====== 根據使用者選擇來執行對應的工具 ======
if tool_choice == "股票估值工具":
    run_stock_valuation_tool()
else:
    run_valuation_tool()
