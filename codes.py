import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. 設定與連線 ---
st.set_page_config(page_title="播商商品號自動生成系統", layout="centered")

# Google Sheets 連線設定
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

# 請更換為您的試算表名稱
spreadsheet_name = "播商編碼資料庫" 
sh = client.open(spreadsheet_name)
ws = sh.get_worksheet(0)

# --- 2. 核心邏輯函數 ---

def get_next_sequence(prefix, df, seq_len):
    """
    功能：自動在歷史紀錄中尋找同前綴的最後一個號碼並 +1
    prefix: 前綴 (如 A-TWN-MFR)
    df: 歷史資料 DataFrame
    seq_len: 流水號長度 (如 3 或 4)
    """
    if df.empty or '最終料號' not in df.columns:
        return "1".zfill(seq_len)
    
    # 篩選出所有符合該前綴的料號
    matched = df[df['最終料號'].str.startswith(prefix, na=False)]
    if matched.empty:
        return "1".zfill(seq_len)
    
    # 提取最後一個流水號並轉為數字
    last_sku = matched['最終料號'].iloc[-1]
    try:
        # 假設結構是 A-TWN-MFR-001，取最後一段
        last_num = int(last_sku.replace(prefix, "").replace("-", ""))
        return str(last_num + 1).zfill(seq_len)
    except:
        return "1".zfill(seq_len)

# --- 3. 網頁介面開始 ---
st.title("💎 播商料號自動生成器")
st.write("請依照下方步驟選擇或輸入資訊，系統將自動生成具延續性的料號。")

# 讀取最新歷史紀錄
df_history = pd.DataFrame(ws.get_all_records())

# 員工姓名輸入
user_name = st.text_input("👤 領取人姓名", placeholder="例如：小明")

if user_name:
    st.divider()
    
    # --- STEP 1: 基礎分類 (第1-3碼) ---
    col1, col2 = st.columns(2)
    with col1:
        main_body = st.selectbox("1. 營運主體", ["A - 播商", "B - 元序"])
        main_code = "A" if "播商" in main_body else "B"
        
        country = st.selectbox("2. 供應商國家", ["TWN - 台灣", "CHN - 大陸", "MYS - 馬來西亞", "KOR - 韓國"])
        country_code = country.split(" - ")[0]
        
    with col2:
        v_type = st.selectbox("3. 供應商類型", [
            "MFR - 製造商", "AGT - 貿易商", "LOG - 物流", "MKT - 行銷", "TEC - 資訊", "GEN - 庶務"
        ])
        v_type_code = v_type.split(" - ")[0]

    # --- STEP 2: 供應商選擇 (記憶延續) ---
    st.subheader("🏢 供應商資訊")
    # 這裡的前綴是用來判斷是否為「同類型」供應商
    base_v_prefix = f"{main_code}-{country_code}-{v_type_code}"
    
    existing_vendors = ["+ 新增供應商"]
    if not df_history.empty:
        v_list = sorted(df_history["供應商名稱"].unique().tolist())
        existing_vendors.extend(v_list)
    
    v_choice = st.selectbox("選擇既有供應商", existing_vendors)
    
    if v_choice == "+ 新增供應商":
        vendor_name = st.text_input("請輸入新供應商全名")
        # 新供應商需要分配一個 MFR001 這種號碼
        v_seq_prefix = f"{base_v_prefix}"
        v_seq = get_next_sequence(v_seq_prefix, df_history, 3)
        final_v_code = f"{v_seq_prefix}{v_seq}"
        final_v_name = vendor_name
    else:
        # 既有供應商：直接從歷史紀錄抓它當初的代碼
        v_row = df_history[df_history["供應商名稱"] == v_choice].iloc[-1]
        # 拆解出 A-TWN-MFR001 這一段
        final_v_code = "-".join(v_row["最終料號"].split("-")[:3])
        final_v_name = v_choice
        st.info(f"📍 已鎖定供應商代碼：{final_v_code}")

    # --- STEP 3: 商品分類與流水號 ---
    st.subheader("📦 商品資訊")
    p_options = {
        "RA - 宗教藝品": "RA", "FB - 食品": "FB", "BP - 美妝個護": "BP",
        "HP - 保健品": "HP", "CL - 服飾": "CL", "K - 組合套組": "K"
    }
    p_sel = st.selectbox("4. 商品類型", list(p_options.keys()))
    p_type = p_options[p_sel]

    # 過濾該供應商領過的品項
    existing_products = ["+ 新增品項"]
    if not df_history.empty and v_choice != "+ 新增供應商":
        p_mask = df_history["供應商名稱"] == v_choice
        p_list = sorted(df_history[p_mask]["商品品名"].unique().tolist())
        existing_products.extend(p_list)
    
    p_choice = st.selectbox("5. 選擇既有品項", existing_products)
    final_p_name = st.text_input("確認商品品名") if p_choice == "+ 新增品項" else p_choice

    # --- STEP 4: 生成料號 ---
    # 最終前綴結構：A-TWN-MFR001-RA
    full_prefix = f"{final_v_code}-{p_type}"
    p_seq = get_next_sequence(full_prefix, df_history, 4)
    final_sku = f"{full_prefix}{p_seq}"

    st.divider()
    st.subheader("📋 預計生成料號")
    st.code(final_sku, language="text")

    # --- STEP 5: 儲存按鈕 (防撞版) ---
    if st.button("🚀 確認領取並儲存", type="primary", use_container_width=True):
        if not final_v_name or not final_p_name:
            st.error("❌ 請填寫完整的供應商與商品名稱！")
        else:
            try:
                # 再次重新抓取，確保按下瞬間沒人領過
                latest_df = pd.DataFrame(ws.get_all_records())
                
                # 檢查是否重複領取
                is_duplicate = False
                if not latest_df.empty:
                    is_duplicate = not latest_df[
                        (latest_df["供應商名稱"] == final_v_name) & 
                        (latest_df["商品品名"] == final_p_name) & 
                        (latest_df["最終料號"] == final_sku)
                    ].empty
                
                if is_duplicate:
                    st.warning(f"⚠️ 提醒：{final_v_name} 的 {final_p_name} 已經領過這個號碼了。")
                else:
                    save_data = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        user_name,
                        final_v_name,
                        final_p_name,
                        full_prefix,
                        p_seq,
                        final_sku
                    ]
                    ws.append_row(save_data)
                    st.success(f"✅ 儲存成功！您的料號是：{final_sku}")
                    st.balloons()
            except Exception as e:
                st.error(f"系統錯誤：{e}")

else:
    st.info("👋 您好！請先在上方輸入您的姓名以開始使用。")
