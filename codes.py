import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- 1. 設定連線函數 (使用您下載的 JSON Secrets) ---
@st.cache_resource
def get_gspread_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # 對應您在 Streamlit Secrets 貼的 [gcp_service_account]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

# --- 2. 執行連線並取得資料 ---
try:
    gc = get_gspread_client()
    
    # ⚠️ 這裡請換成您那份 Google Sheet 的網址
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1pHmoUVvjbIc1kh7nnChLELWVgU9wwe9WpreAAkuWr7I/edit"
    
    sh = gc.open_by_url(spreadsheet_url)
    worksheet = sh.get_worksheet(0) # 讀取第一個分頁
    
    # 讀取資料
    data = worksheet.get_all_records()
    df_history = pd.DataFrame(data)

except Exception as e:
    st.error(f"❌ 連線 Google Sheet 失敗: {e}")
    st.stop()

def get_history():
    try:                     # <--- 這裡前面要有 4 個空白鍵
        return conn.read(ttl=0) # <--- 這裡前面要有 8 個空白鍵
    except:                  # <--- 這裡前面要有 4 個空白鍵
        return pd.DataFrame(columns=["生成時間", "員工姓名", "供應商名稱", "商品名稱", "編碼前綴", "流水號", "最終料號"])

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
# --- Step 1. 供應商選擇 (動態連動版) ---
        existing_vendors = ["+ 新增供應商"]
        if not df_history.empty:
            # 直接從歷史紀錄中抓取「所有」不重複的供應商名稱
            v_list = sorted(df_history["供應商名稱"].unique().tolist())
            existing_vendors.extend(v_list)

        v_choice = st.selectbox("選擇既有供應商", existing_vendors)

        if v_choice == "+ 新增供應商":
            vendor_name = st.text_input("請輸入新供應商全名")
            # 這裡需要計算新供應商的流水號 (例如 MFR001)
            v_seq = get_next_sequence(base_v_prefix, df_history, 3)
            final_v_prefix = f"{base_v_prefix}{v_seq}"
            final_v_name = vendor_name
        else:
            # 💡 既有供應商：從歷史紀錄中反推它的代碼 (例如 A-TWN-MFR001)
            v_row = df_history[df_history["供應商名稱"] == v_choice].iloc[0]
            # 這裡假設您的料號結構是 A-TWN-MFR001-RA... 拆出前三個段落
            final_v_prefix = "-".join(v_row["最終料號"].split("-")[:3])
            final_v_name = v_choice
            st.success(f"已鎖定供應商代碼：{final_v_prefix}")

        # --- Step 2. 商品品項選擇 (根據供應商連動) ---
        existing_products = ["+ 新增品項"]
        if not df_history.empty and v_choice != "+ 新增供應商":
            # 💡 關鍵：只抓取「該供應商」過去領過的品項
            p_mask = df_history["供應商名稱"] == v_choice
            p_list = sorted(df_history[p_mask]["商品品名"].unique().tolist())
            existing_products.extend(p_list)

        p_choice = st.selectbox("選擇或查看既有品項", existing_products)

        if p_choice == "+ 新增品項":
            product_name = st.text_input("請輸入新商品品名")
            final_p_name = product_name
        else:
            final_p_name = p_choice
            st.warning(f"注意：此品項已存在，若再次領取將生成新的流水號")

        # --- Step 3. 生成料號與顯示 ---
        # 此處確保 full_prefix 包含供應商與商品分類 (如 RA)
            full_prefix = f"{final_v_prefix}-{p_type}" 
            p_seq = get_next_sequence(full_prefix, df_history, 4)
            final_sku = f"{full_prefix}{p_seq}"
            
            st.divider()
            st.subheader("📋 預計生成的料號")
            st.code(final_sku, language="text")
        # --- 3. 儲存按鈕 (防撞 + 防重複版) ---
        if st.button("確認領取並儲存", type="primary", use_container_width=True):
            try:
                # 🔄 第一步：按下瞬間重新讀取 Sheet，確保拿到的是「此時此刻」最新的資料
                # 避免兩個人同時打開網頁看到同一個號碼
                refresh_data = sh.get_worksheet(0).get_all_records()
                refresh_df = pd.DataFrame(refresh_data)
        
        # 🔄 第二步：重新計算「真正的」下一個序號
                actual_seq = get_next_sequence(full_prefix, refresh_df, 4)
                actual_sku = f"{full_prefix}{actual_seq}"
            
            # 🔍 第三步：防重複檢查 (如果同廠商、同商品、同料號已存在，就不重複寫入)
            # 取得正確的廠商與產品名稱
                final_v_name = vendor_name if v_choice == "+ 新增供應商" else v_choice
                final_p_name = product_name if p_choice == "+ 新增品項" else p_choice
                
                # 🔄 修改後的防重複檢查邏輯
                is_duplicate = False
                if not refresh_df.empty:
                    is_duplicate = not refresh_df[
                        (refresh_df.iloc[:, 2] == final_v_name) &   # 第 3 欄 (C欄)
                        (refresh_df.iloc[:, 3] == final_p_name) &   # 第 4 欄 (D欄)
                        (refresh_df.iloc[:, 6] == actual_sku)      # 第 7 欄 (G欄)
                    ].empty
            
            if is_duplicate:
                st.warning(f"⚠️ 偵測到重複：{final_v_name} 的 {final_p_name} 已經領過 {actual_sku} 了！")
            else:
                # 🚀 第四步：打包資料並寫入
                save_data = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    user_name,
                    final_v_name,
                    final_p_name,
                    full_prefix,
                    str(actual_seq),
                    actual_sku
                ]
                
                sh.get_worksheet(0).append_row(save_data)
                st.success(f"🎉 儲存成功！領取料號：{actual_sku}")
                st.balloons()
                
            except Exception as e:
                # 📢 報錯敘述優化
                st.error(f"❌ 哎呀！系統在儲存時卡住了。錯誤原因：{str(e)}")
                st.info("💡 小撇步：請檢查網路連線，或確認 Google Sheet 沒有被其他人意外刪除欄位。")
                    
# --- 4. 輔助資訊顯示 ---
st.info(f"💡 提示：點擊上方按鈕後，資料將自動同步至公司 Google 試算表。")
