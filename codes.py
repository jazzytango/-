import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. 設定與連線 ---
st.set_page_config(page_title="播商商品編號生成系統", layout="wide")

# 連線邏輯 (保持不變)
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

# 請確保 ID 正確
sh = client.open_by_key("1D8O0A-l_ncl8n6P2Zp4_167R_QWp_V0R5V-jU0H1Ems") 
ws = sh.get_worksheet(0)

# --- 2. 記憶功能初始化 (Session State) ---
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

# --- 3. 核心邏輯：精準找尋下一個流水號 ---
def get_next_sequence(prefix, df, seq_len):
    if df.empty or '最終料號' not in df.columns:
        return "1".zfill(seq_len)
    
    # 確保最終料號欄位是字串，並篩選符合前綴的資料
    df['最終料號'] = df['最終料號'].astype(str)
    matched = df[df['最終料號'].str.startswith(prefix)]
    
    if matched.empty:
        return "1".zfill(seq_len)
    
    # 取得該前綴下的最後一個號碼
    last_sku = matched['最終料號'].iloc[-1]
    # 規則：前綴之後的所有數字就是流水號
    # 例如：A-TWN-MFR001-RA 之後接的是 0001
    suffix = last_sku.replace(prefix, "").replace("-", "")
    try:
        last_num = int(suffix)
        return str(last_num + 1).zfill(seq_len)
    except:
        return "1".zfill(seq_len)

# --- 4. UI 介面 ---
st.title("🚀 播商料號自動生成系統 (專業版)")

# 登入區：如果沒輸入名字，就卡住不給過
if not st.session_state.user_name:
    name_input = st.text_input("👋 請輸入您的姓名開始作業：")
    if st.button("進入系統"):
        if name_input:
            st.session_state.user_name = name_input
            st.rerun()
        else:
            st.warning("請輸入名字喔！")
    st.stop()

# 顯示登入狀態與登出按鈕
col_u1, col_u2 = st.columns([8, 2])
with col_u1:
    st.write(f"✅ 當前作業員：**{st.session_state.user_name}**")
with col_u2:
    if st.button("更換人員"):
        st.session_state.user_name = ""
        st.rerun()

# 讀取最新歷史紀錄
records = ws.get_all_records()
df_history = pd.DataFrame(records)

st.divider()

# --- STEP 1: 分類設定 ---
c1, c2, c3 = st.columns(3)
with c1:
    main_body = st.selectbox("營運主體", ["A - 播商", "B - 元序"])
    main_code = main_body.split(" - ")[0]
with c2:
    country = st.selectbox("國家", ["TWN - 台灣", "CHN - 大陸", "MYS - 馬來西亞", "KOR - 韓國"])
    country_code = country.split(" - ")[0]
with c3:
    v_type = st.selectbox("供應商類型", ["MFR - 製造商", "AGT - 貿易商", "LOG - 物流", "TEC - 資訊", "GEN - 庶務"])
    v_type_code = v_type.split(" - ")[0]

base_v_prefix = f"{main_code}-{country_code}-{v_type_code}"

# --- STEP 2: 供應商連動 ---
st.subheader("🏢 供應商設定")
existing_vendors = ["+ 新增供應商"]
if not df_history.empty:
    v_list = sorted(df_history["供應商名稱"].unique().tolist())
    existing_vendors.extend(v_list)

v_choice = st.selectbox("選擇或搜尋既有供應商", existing_vendors)

if v_choice == "+ 新增供應商":
    v_name = st.text_input("新供應商全名 (例如: 雲上珠寶)")
    # 計算該類型供應商的下一個序號 (例如 MFR001)
    v_seq = get_next_sequence(base_v_prefix, df_history, 3)
    final_v_prefix = f"{base_v_prefix}{v_seq}"
    final_v_name = v_name
else:
    # 既有供應商：反推它的固定代碼
    v_row = df_history[df_history["供應商名稱"] == v_choice].iloc[0]
    final_v_prefix = "-".join(str(v_row["最終料號"]).split("-")[:3])
    final_v_name = v_choice
    st.info(f"💡 該供應商固定代碼：{final_v_prefix}")

# --- STEP 3: 商品連動 ---
st.subheader("📦 商品設定")
p_options = {"RA - 宗教藝品": "RA", "FB - 食品": "FB", "BP - 美妝個護": "BP", "HP - 保健品": "HP", "K - 組合套組": "K"}
p_sel = st.selectbox("商品大類", list(p_options.keys()))
p_type_code = p_options[p_sel]

# 過濾該供應商領過的品項
existing_products = ["+ 新增品項"]
if not df_history.empty and v_choice != "+ 新增供應商":
    p_mask = df_history["供應商名稱"] == v_choice
    p_list = sorted(df_history[p_mask]["商品品名"].unique().tolist())
    existing_products.extend(p_list)

p_choice = st.selectbox("選擇既有品項", existing_products)
final_p_name = st.text_input("輸入新商品品名") if p_choice == "+ 新增品項" else p_choice

# --- STEP 4: 生成與儲存 ---
full_prefix = f"{final_v_prefix}-{p_type_code}"
next_p_seq = get_next_sequence(full_prefix, df_history, 4)
final_sku = f"{full_prefix}{next_p_seq}"

st.divider()
st.markdown(f"### 🎯 預計生成料號： `{final_sku}`")

if st.button("🔥 確認領取並存檔", type="primary"):
    if not final_v_name or not final_p_name:
        st.error("請檢查供應商或商品名稱是否漏填！")
    else:
        try:
            # 即時刷新檢查防撞
            df_refresh = pd.DataFrame(ws.get_all_records())
            
            # 防重複檢查
            is_dup = False
            if not df_refresh.empty:
                is_dup = not df_refresh[(df_refresh["供應商名稱"] == final_v_name) & 
                                        (df_refresh["商品品名"] == final_p_name) & 
                                        (df_refresh["最終料號"] == final_sku)].empty
            
            if is_dup:
                st.warning("⚠️ 偵測到重複！該品項已領過此料號。")
            else:
                new_row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    st.session_state.user_name,
                    final_v_name,
                    final_p_name,
                    full_prefix,
                    next_p_seq,
                    final_sku
                ]
                ws.append_row(new_row)
                st.success(f"🎊 儲存成功！已將 {final_sku} 寫入 Google Sheet")
                st.balloons()
                # 提示使用者可以繼續領下一筆
                st.info("您可以直接修改上方選項來領取下一個號碼。")
                
        except Exception as e:
            st.error(f"儲存失敗，錯誤訊息：{e}")
