import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- 設定區：您可以隨時改這裡的名稱 ---
HISTORY_FILE = "編碼生成_Database.csv"  # 您的資料庫檔名
APP_TITLE = "播商自動編碼生成管理工具" # 網頁最上方的標題

# --- 功能函式：讀取紀錄與自動算號 ---
def get_history():
    if os.path.exists(HISTORY_FILE):
        return pd.read_csv(HISTORY_FILE)
    else:
        # 建立初始資料表
        return pd.DataFrame(columns=["生成時間", "員工姓名", "編碼前綴", "流水號", "最終料號"])

def get_next_sequence(prefix, seq_type="vendor"):
    df = get_history()
    matches = df[df["編碼前綴"] == prefix]
    
    if matches.empty:
        return "001" if seq_type == "vendor" else "0001"
    
    # 找到該分類下最大的號碼並 +1
    last_seq = matches["流水號"].astype(int).max()
    next_seq = last_seq + 1
    
    return f"{next_seq:03d}" if seq_type == "vendor" else f"{next_seq:04d}"

# --- 網頁介面介面 ---
st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title(f"🚀 {APP_TITLE}")

user_name = st.text_input("👤 領號人姓名 (必填)", value="")

st.info("請依序選擇分類，系統將自動比對資料庫並產出下一個可用料號。")

# --- 選擇規則區 ---
col1, col2 = st.columns(2)

with col1:
    # 1. 營運主體
    e_map = {"播商": "A", "元序": "B", "C": "C", "D": "D"}
    e_choice = st.selectbox("1. 營運主體", [f"{v} ({k})" for k, v in e_map.items()])
    c1 = e_choice.split(" ")[0]

    # 2. 地理位置 (改為您要求的三位字母代碼)
    g_map = {"台灣": "TWN", "大陸": "CHN", "馬來西亞": "MYS", "韓國": "KOR"}
    g_choice = st.selectbox("2. 地理位置", [f"{v} ({k})" for k, v in g_map.items()])
    c2 = g_choice.split(" ")[0]

    # 3. 供應商類型
    v_map = {"製造商": "MFR", "貿易商": "AGT", "物流": "LOG", "廣告": "MKT", "技術": "TEC"}
    v_choice = st.selectbox("3. 供應商類型", [f"{v} ({k})" for k, v in v_map.items()])
    v_type = v_choice.split(" ")[0]

with col2:
    # 供應商自動算號 (前綴：A-TWN-MFR)
    v_prefix = f"{c1}-{c2}-{v_type}"
    v_seq = st.text_input("4. 供應商流水號 (自動偵測)", value=get_next_sequence(v_prefix, "vendor"))

    # 5. 商品類型
    p_map = {"食品飲料": "FB", "保健品": "HP", "美妝護理": "BP", "宗教藝品": "RA", "居家生活": "HL"}
    p_choice = st.selectbox("5. 商品類型", [f"{v} ({k})" for k, v in p_map.items()])
    p_type = p_choice.split(" ")[0]

    # 商品自動算號 (前綴：A-TWN-MFR001-FB)
    p_prefix = f"{c1}-{c2}-{v_type}{v_seq}-{p_type}"
    p_seq = st.text_input("6. 商品流水號 (自動偵測)", value=get_next_sequence(p_prefix, "product"))

# --- 生成結果 ---
final_sku = f"{c1}-{c2}-{v_type}{v_seq}-{p_type}{p_seq}"

st.divider()
st.subheader("📋 預計產出的料號：")
st.code(final_sku, language="text")

if st.button("確認領取此料號並存檔"):
    if not user_name:
        st.error("❌ 請輸入姓名後再存檔！")
    else:
        df = get_history()
        # 最終檢查是否有人剛好領走
        if final_sku in df["最終料號"].values:
            st.error("❌ 糟糕！這個料號剛剛被別人領走了，請重新整理頁面。")
        else:
            new_data = pd.DataFrame([[
                datetime.now().strftime("%Y-%m-%d %H:%M"), 
                user_name, p_prefix, p_seq, final_sku
            ]], columns=["生成時間", "員工姓名", "編碼前綴", "流水號", "最終料號"])
            
            df = pd.concat([df, new_data], ignore_index=True)
            df.to_csv(HISTORY_FILE, index=False, encoding="utf-8-sig")
            st.success(f"✅ 成功！料號 {final_sku} 已紀錄至 {HISTORY_FILE}")
            st.balloons()
            st.rerun()

# --- 顯示歷史紀錄 ---
st.divider()
st.write("### 🕒 最近領號紀錄 (料號_Database)")
history_df = get_history()
st.dataframe(history_df.iloc[::-1], use_container_width=True)