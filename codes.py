import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="播商智慧料號系統 V2.1", layout="wide")

# --- 1. 連結 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_history():
    try:
        # ttl=0 確保每次操作都抓到最新數據，避免多人同時領號衝突
        return conn.read(ttl=0)
    except:
        return pd.DataFrame(columns=["生成時間", "員工姓名", "供應商名", "商品品名", "編碼前綴", "流水號", "最終料號"])

# --- 2. 算號邏輯優化 ---
def get_next_sequence(prefix, df_history, length=4):
    if df_history.empty:
        return "1".zfill(length)
    
    # 找尋前綴完全吻合的紀錄
    matches = df_history[df_history["編碼前綴"] == prefix]
    if matches.empty:
        return "1".zfill(length)
    
    # 轉為數字找最大值
    last_seq = pd.to_numeric(matches["流水號"]).max()
    return str(int(last_seq) + 1).zfill(length)

# --- 3. 介面設計 ---
st.title("🛡️ 播商智慧料號系統 (精準續號版)")
df_history = get_history()

with st.sidebar:
    st.header("👤 使用者設定")
    user_name = st.text_input("您的姓名", placeholder="請輸入姓名")
    st.divider()
    st.info("提示：若清單找不到供應商，請選擇「+ 新增供應商」")

# --- Step 1. 供應商選擇 ---
st.header("Step 1. 供應商(MFR/AGT...)資訊")
col1, col2 = st.columns(2)

with col1:
    # 這裡把註解直接寫進選項中
    e_options = {"A - 播商": "A", "B - 元序": "B"}
    g_options = {"TWN - 台灣": "TWN", "CHN - 大陸": "CHN", "MYS - 馬來西亞": "MYS", "KOR - 韓國": "KOR"}
    v_options = {
        "MFR - 製造商": "MFR", 
        "AGT - 貿易商": "AGT", 
        "LOG - 物流": "LOG", 
        "MKT - 行銷": "MKT", 
        "TEC - 技術": "TEC", 
        "GEN - 庶務": "GEN"
    }
    
    e_sel = st.selectbox("營運主體", list(e_options.keys()))
    g_sel = st.selectbox("地理位置", list(g_options.keys()))
    v_sel = st.selectbox("供應商類型", list(v_options.keys()))
    
    # 提取真正的代碼 (例如從 "A - 播商" 提取出 "A")
    e_val = e_options[e_sel]
    g_val = g_options[g_sel]
    v_val = v_options[v_sel]
    
    base_v_prefix = f"{e_val}-{g_val}-{v_val}"

with col2:
    # 從歷史紀錄中過濾出符合此分類的供應商名單
    existing_vendors = ["+ 新增供應商"]
    if not df_history.empty:
        # 過濾出相同類型(如 MFR)的現有廠商
        v_mask = df_history["編碼前綴"].str.contains(f"{e_map[e_c]}-{g_map[g_c]}-{v_map[v_c]}")
        v_list = df_history[v_mask]["供應商名"].unique().tolist()
        existing_vendors.extend(v_list)
    
    v_choice = st.selectbox("選擇既有供應商", existing_vendors)
    
    if v_choice == "+ 新增供應商":
        vendor_name = st.text_input("輸入新供應商全名")
        # 算新廠商的流水號 (3位)
        v_seq = get_next_sequence(base_v_prefix, df_history, 3)
        final_v_prefix = f"{base_v_prefix}{v_seq}"
    else:
        vendor_name = v_choice
        # 抓取該廠商已有的 ID
        v_row = df_history[df_history["供應商名"] == v_choice].iloc[0]
        # 從 A-TWN-MFR001-FB0001 拆出 A-TWN-MFR001
        final_v_prefix = "-".join(v_row["最終料號"].split("-")[:3])
        st.success(f"已鎖定供應商代碼：{final_v_prefix}")

# --- Step 2. 商品類型與序號 ---
st.header("Step 2. 商品資訊")
col3, col4 = st.columns(2)

with col3:
    p_options = {
        "K - 組合套組": "K", 
        "P - 促銷品": "P", 
        "FB - 食品飲料": "FB", 
        "HP - 保健品": "HP", 
        "BP - 美妝護理": "BP", 
        "RA - 宗教藝品": "RA", 
        "EA - 3C家電": "EA"
    }
    p_sel = st.selectbox("商品類型", list(p_options.keys()))
    p_type = p_options[p_sel]

with col4:
    # 同理，檢查該廠商下是否已有相同類型的商品
    existing_products = ["+ 新增品項"]
    if not df_history.empty:
        p_mask = (df_history["供應商名"] == vendor_name) & (df_history["最終料號"].str.contains(f"-{p_type}"))
        p_list = df_history[p_mask]["商品品名"].unique().tolist()
        existing_products.extend(p_list)
    
    p_choice = st.selectbox("選擇或查看既有品項", existing_products)
    
    if p_choice == "+ 新增品項":
        product_name = st.text_input("輸入新商品品名")
    else:
        product_name = p_choice
        st.warning(f"注意：此品項已存在，若再次領取將生成新的流水號")

# --- Step 3. 生成料號 ---
# 最終編碼前綴格式：A-TWN-MFR001-FB
full_prefix = f"{final_v_prefix}-{p_type}"
p_seq = get_next_sequence(full_prefix, df_history, 4)
final_sku = f"{full_prefix}{p_seq}"

st.divider()
st.subheader("📋 預計生成的料號")
st.code(final_sku, language="text")

if st.button("確認領取並儲存", use_container_width=True):
    if not user_name or not vendor_name or not product_name:
        st.error("❌ 姓名、供應商與品名皆為必填！")
    else:
        new_data = pd.DataFrame([[
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            user_name, vendor_name, product_name, full_prefix, p_seq, final_sku
        ]], columns=["生成時間", "員工姓名", "供應商名", "商品品名", "編碼前綴", "流水號", "最終料號"])
        
        updated_df = pd.concat([df_history, new_data], ignore_index=True)
        # 替代 conn.update 的更穩定寫法
        try:
            conn.update(worksheet="Sheet1", data=updated_df)
            st.success("✅ 資料已成功同步至 Google Sheets！")
            st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"儲存失敗，請檢查 Google Sheets 權限。錯誤代碼: {e}")
        st.success("✅ 資料已成功同步至 Google Sheets！")
        st.balloons()
        st.rerun()

# 顯示歷史紀錄
st.write("### 📜 最近領取紀錄")
st.dataframe(df_history.iloc[::-1], use_container_width=True)
