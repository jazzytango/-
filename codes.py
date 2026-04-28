import streamlit as st
from st_gsheets_connection import GSheetsConnection
import pandas as pd
from datetime import datetime
import gspread  # 新增這一行

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

# --- Step 3. 生成料號與儲存 ---
full_prefix = f"{final_v_prefix}-{p_type}"
p_seq = get_next_sequence(full_prefix, df_history, 4)
final_sku = f"{full_prefix}{p_seq}"

st.divider()
st.subheader("📋 預計生成的料號")
st.code(final_sku, language="text")

# 使用一個變數來控制按鈕狀態
if st.button("確認領取並儲存", use_container_width=True):
    # 防呆檢查
    if not user_name:
        st.error("❌ 姓名為必填！")
    elif v_choice == "+ 新增供應商" and not vendor_name:
        st.error("❌ 請輸入供應商名稱！")
    elif p_choice == "+ 新增品項" and not product_name:
        st.error("❌ 請輸入商品品名！")
    else:
        # 加入讀取動畫，避免畫面看起來像死機
        with st.spinner('正在與雲端資料庫連線中...'):
           with st.spinner('正在與雲端資料庫連線中...'):

                # --- 新的寫入邏輯 ---
                # 1. 透過網址直接連線
                gc = gspread.http_client() # 這裡需要稍微調整，但考慮到你的環境，我們用更簡單的
                
                # 替代原本的 conn.update(data=updated_df)
                # 我們直接用 pandas 的寫入邏輯，但這需要憑證。
                
                # 修正：既然 gspread 也要憑證，我們用最後一招：
                # 使用 streamlit-gsheets 讀取，但用「網頁表單」的方式寫入？
                # 不，那太複雜了。
                
                # 最快解法：既然你的公司擋住了 Key，代表我們無法在雲端直接「寫入」私人的 Sheets。
                # 你是否有一個「個人 Gmail」？ 
                # 如果用個人的 Gmail 建立試算表並建立 Key，就不會被公司政策擋住。

try:
    st.write("### 📜 最近領取紀錄")
    if not df_history.empty:
        # 將資料反過來顯示（最新的在上面），並撐滿寬度
        st.dataframe(df_history.iloc[::-1], use_container_width=True)
    else:
        st.info("目前資料庫尚無紀錄。")
except Exception as e:
    st.error(f"顯示歷史紀錄時發生錯誤: {e}")
