import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="播商智慧料號系統 V2", layout="wide")

# --- 1. 連結 Google Sheets ---
# 請確保 Secrets 已設定 spreadsheet 網址
conn = st.connection("gsheets", type=GSheetsConnection)

def get_history():
    try:
        # 強制不緩存，確保多人同時使用時數據最即時
        return conn.read(ttl=0)
    except:
        return pd.DataFrame(columns=["生成時間", "員工姓名", "供應商名", "商品品名", "編碼前綴", "流水號", "最終料號"])

# --- 2. 核心邏輯：自動算號 ---
def get_next_sequence(prefix, df_history, seq_type="vendor"):
    if df_history.empty:
        return "001" if seq_type == "vendor" else "0001"
    
    matches = df_history[df_history["編碼前綴"] == prefix]
    if matches.empty:
        return "001" if seq_type == "vendor" else "0001"
    
    last_seq = pd.to_numeric(matches["流水號"]).max()
    next_seq = int(last_seq) + 1
    return f"{next_seq:03d}" if seq_type == "vendor" else f"{next_seq:04d}"

# --- 3. 介面設計 ---
st.title("🛡️ 播商智慧料號生成器 (語義加強版)")
st.markdown("##### 讓料號不再只是冷冰冰的數字，實現名稱與代碼同步管理")

df_history = get_history()

with st.expander("👤 使用者資訊", expanded=True):
    user_name = st.text_input("輸入您的姓名", placeholder="例如：王小明")

# --- 第一階段：供應商定義 ---
st.header("Step 1. 供應商資訊")
col1, col2, col3 = st.columns(3)

with col1:
    e_map = {"播商": "A", "元序": "B", "C": "C", "D": "D"}
    e_choice = st.selectbox("營運主體", [f"{v} ({k})" for k, v in e_map.items()])
    c1 = e_choice.split(" ")[0]

    g_map = {"台灣": "TWN", "大陸": "CHN", "馬來西亞": "MYS", "韓國": "KOR"}
    g_choice = st.selectbox("地理位置", [f"{v} ({k})" for k, v in g_map.items()])
    c2 = g_choice.split(" ")[0]

with col2:
    v_map = {"製造商": "MFR", "貿易商": "AGT", "物流": "LOG", "行銷": "MKT", "技術": "TEC", "庶務": "GEN"}
    v_type_choice = st.selectbox("供應商類型", [f"{v} ({k})" for k, v in v_map.items()])
    v_type = v_type_choice.split(" ")[0]

    # 檢查該類別下已有的供應商，供快速參考
    v_prefix_for_check = f"{c1}-{c2}-{v_type}"
    existing_vendors = df_history[df_history["編碼前綴"].str.startswith(v_prefix_for_check, na=False)]["供應商名"].unique()
    if len(existing_vendors) > 0:
        st.caption(f"💡 此類別已有廠商：{', '.join(existing_vendors)}")

with col3:
    vendor_name = st.text_input("供應商全名", placeholder="例如：衡昱生技")
    
    # 決定供應商流水號
    # 邏輯：如果廠商名已存在，就沿用舊號；如果新廠商，就自動編號
    vendor_match = df_history[df_history["供應商名"] == vendor_name]
    if not vendor_match.empty and vendor_name != "":
        # 提取舊有的流水號 (假設格式是 A-TWN-MFR001)
        old_sku = vendor_match.iloc[0]["最終料號"]
        v_seq = old_sku.split("-")[2].replace(v_type, "")
        st.success(f"偵測到既有供應商，自動沿用編號：{v_seq}")
    else:
        v_prefix = f"{c1}-{c2}-{v_type}"
        v_seq = get_next_sequence(v_prefix, df_history, "vendor")
        st.info(f"新供應商，預計編號：{v_seq}")

# --- 第二階段：商品定義 ---
st.header("Step 2. 商品資訊")
col4, col5 = st.columns(2)

with col4:
    p_map = {"組合套組": "K", "促銷品": "P", "食品飲料": "FB", "保健品": "HP", "美妝護理": "BP", "宗教藝品": "RA", "3C家電": "EA"}
    p_choice = st.selectbox("商品類型", [f"{v} ({k})" for k, v in p_map.items()])
    p_type = p_choice.split(" ")[0]

with col5:
    product_name = st.text_input("商品品名", placeholder="例如：高濃度維他命C粉")
    
    p_prefix = f"{c1}-{c2}-{v_type}{v_seq}-{p_type}"
    p_seq = get_next_sequence(p_prefix, df_history, "product")

# --- 第三階段：生成與確認 ---
final_sku = f"{c1}-{c2}-{v_type}{v_seq}-{p_type}{p_seq}"

st.divider()
st.subheader("🎉 生成料號預覽")
res_col1, res_col2 = st.columns([1, 2])
with res_col1:
    st.code(final_sku, language="text")
with res_col2:
    st.write(f"**對應資訊：** {vendor_name} | {product_name}")

if st.button("確認領取並儲存至雲端資料庫", use_container_width=True):
    if not user_name or not vendor_name or not product_name:
        st.error("❌ 錯誤：請填寫完整姓名、供應商名及商品品名！")
    elif not df_history.empty and final_sku in df_history["最終料號"].values:
        st.error(f"❌ 錯誤：料號 {final_sku} 已經被領取過了！")
    else:
        new_row = pd.DataFrame([[
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            user_name, vendor_name, product_name, p_prefix, p_seq, final_sku
        ]], columns=["生成時間", "員工姓名", "供應商名", "商品品名", "編碼前綴", "流水號", "最終料號"])
        
        updated_df = pd.concat([df_history, new_row], ignore_index=True)
        conn.update(data=updated_df)
        st.success(f"✅ 成功！料號 {final_sku} 已綁定【{vendor_name}-{product_name}】")
        st.balloons()
        st.rerun()

# --- 歷史紀錄 ---
st.divider()
st.write("### 📜 完整料號對照表 (Google Sheets 直連)")
st.dataframe(df_history.iloc[::-1], use_container_width=True)
