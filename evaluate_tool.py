#!/usr/bin/env python
# coding: utf-8

# In[3]:


import streamlit as st
import pandas as pd
import json
import io
import datetime

st.set_page_config(page_title="公司&債券評價全功能工具", layout="wide")
st.title("公司&債券評價全功能工具 (上市/未上市/創投/資產/債券/市場/特殊)")

# === 管理員密碼 ===
ADMIN_PASSWORD = "tbb1840"

# ====== 所有評價欄位（帶中文註解）======
default_fields = [
    {"name": "股價", "key": "stock_price"},
    {"name": "流通股數", "key": "shares"},
    {"name": "EPS（每股盈餘）", "key": "eps"},
    {"name": "淨利（Net Income）", "key": "net_income"},
    {"name": "本益比（PE倍數）", "key": "pe_ratio"},
    {"name": "每股淨值（BVPS）", "key": "bvps"},
    {"name": "股東權益（Equity）", "key": "equity"},
    {"name": "本淨比（PB倍數）", "key": "pb_ratio"},
    {"name": "EBITDA（稅息折舊攤提前獲利）", "key": "ebitda"},
    {"name": "EV/EBITDA倍數", "key": "ev_ebitda_ratio"},
    {"name": "現金（Cash）", "key": "cash"},
    {"name": "有息負債（Debt）", "key": "debt"},
    {"name": "併購價格/案例參考（Precedent Transaction Price）", "key": "precedent_price"},
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
]

# ====== 公式（所有評價方法＋債券）======
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
}

default_methods = [
    {"name": "市價法", "key": "market_price"},
    {"name": "同業PE倍數法", "key": "pe_comp"},
    {"name": "同業PB倍數法", "key": "pb_comp"},
    {"name": "同業EV/EBITDA", "key": "ev_ebitda_comp"},
    {"name": "併購交易法", "key": "precedent_trans"},
    {"name": "DCF現金流折現法", "key": "dcf"},
    {"name": "EVA經濟附加價值法", "key": "eva"},
    {"name": "盈餘資本化法", "key": "cap_earnings"},
    {"name": "股利折現法(DDM)", "key": "ddm"},
    {"name": "帳面資產法", "key": "book_asset"},
    {"name": "資產重估法", "key": "asset_reval"},
    {"name": "清算價值法", "key": "liquidation"},
    {"name": "創投-回推法", "key": "vc_exit"},
    {"name": "創投-倍數法", "key": "vc_multiple"},
    {"name": "創投-股權分割法", "key": "vc_equity"},
    {"name": "創投-市值倒推法", "key": "vc_rev_valuation"},
    {"name": "選擇權定價法", "key": "real_option"},
    {"name": "分段混合法SOTP", "key": "sotp"},
    {"name": "行業自定指標", "key": "custom_industry"},
    # 債券
    {"name": "債券現值法（DCF）", "key": "bond_pv"},
    {"name": "當期殖利率法", "key": "bond_current_yield"},
    {"name": "平價法", "key": "bond_par_value"},
    {"name": "YTM說明", "key": "bond_ytm_info"},
]

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

v = {f['key']: safe_float(st.session_state.inputs.get(f['key'], "")) for f in st.session_state.fields}

st.sidebar.header("請輸入公司或債券評價資料")
for f in st.session_state.fields:
    val = st.sidebar.text_input(
        f['name'],
        value=st.session_state.inputs.get(f['key'], ""),
        key=f['key']
    )
    st.session_state.inputs[f['key']] = val

results = {}
for m in st.session_state.methods:
    key = m["key"]
    formula = st.session_state.formulas.get(key, "None")
    try:
        results[m['name']] = eval(formula, {}, v)
    except Exception as e:
        results[m['name']] = None

st.header("公司與債券評價方法總覽")
df = pd.DataFrame([
    {"評價方法": k, "估值（元/比率/說明）": (f"{val:,.4f}" if isinstance(val, float) and val is not None else val if val is not None else "")}
    for k, val in results.items()
])
st.table(df)

# ====== 匯出 Excel ======
st.header("匯出 Excel")
if st.button("匯出Excel"):
    df_input = pd.DataFrame([(f['name'], st.session_state.inputs.get(f['key'], "")) for f in st.session_state.fields], columns=["項目", "輸入值"])
    df_out = pd.DataFrame([
        (k, (f"{val:,.4f}" if isinstance(val, float) and val is not None else val if val is not None else "")) for k, val in results.items()
    ], columns=["評價方法", "估值（元/比率/說明）"])
    with pd.ExcelWriter("公司債券評價結果.xlsx", engine="openpyxl") as writer:
        df_input.to_excel(writer, sheet_name="輸入數據", index=False)
        df_out.to_excel(writer, sheet_name="評價總表", index=False)
    with open("公司債券評價結果.xlsx", "rb") as file:
        st.download_button("下載Excel", file, file_name="公司債券評價結果.xlsx")

# ====== 一鍵清除 ======
if st.button("一鍵清除"):
    st.session_state.inputs = {f['key']: "" for f in st.session_state.fields}
    st.rerun()

# ====== 管理員功能 ======
with st.expander("管理員功能（欄位/公式/匯出/還原）", expanded=False):
    st.markdown("**目前所有公式如下：**")
    st.code(json.dumps(st.session_state.formulas, ensure_ascii=False, indent=2), language="json")
    # 管理員登入/登出狀態
    if not st.session_state.admin_mode:
        pwd = st.text_input("請輸入管理密碼", type="password")
        if pwd == ADMIN_PASSWORD:
            st.session_state.admin_mode = True
            st.experimental_rerun()
    else:
        st.success("管理員已登入。")
        # 登出按鈕
        if st.button("登出管理員模式"):
            st.session_state.admin_mode = False
            st.experimental_rerun()

        # 強制備份目前欄位&公式設定
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

        # === 欄位管理 ===
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
                st.rerun()
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
            st.rerun()

        # === 欄位/公式設定 匯出/匯入 ===
        st.markdown("### 欄位與公式設定匯出/還原")
        # 匯出
        if st.button("手動匯出欄位清單"):
            st.download_button("下載欄位清單.json", io.BytesIO(field_json.encode("utf-8")), file_name="欄位清單.json")
        if st.button("手動匯出公式清單"):
            st.download_button("下載公式.json", io.BytesIO(formula_json.encode("utf-8")), file_name="公式清單.json")
        # 匯入
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
                    st.rerun()
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
                    st.rerun()
                else:
                    st.error("格式錯誤")
            except Exception as e:
                st.error(f"上傳錯誤：{e}")

        # === 公式即時編輯 ===
        st.markdown("---")
        st.subheader("公式管理（可即時修改）")
        for k in st.session_state.formulas:
            new_formula = st.text_input(f"{k} 公式", value=st.session_state.formulas[k], key=f"formula_{k}")
            st.session_state.formulas[k] = new_formula
        if st.button("儲存公式（即時生效）"):
            st.success("已更新公式，立即套用！")
            st.rerun()


# In[ ]:




