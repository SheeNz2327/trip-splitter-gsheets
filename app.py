import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import uuid
import base64

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="Trip Splitter Cloud", page_icon="🧳", layout="centered")

# 2. ฝัง Custom CSS สไตล์ Soft Purple
custom_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .stApp { background: radial-gradient(circle at 50% -20%, rgba(167, 139, 250, 0.1) 0%, #0b0811 40%); }
    .stButton > button[kind="primary"] {
        background-color: #a78bfa !important; color: #1e1b4b !important;
        border-radius: 30px !important; font-weight: 600 !important; border: none !important;
        box-shadow: 0 4px 15px rgba(167, 139, 250, 0.2); transition: all 0.3s ease;
    }
    .stButton > button[kind="primary"]:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(167, 139, 250, 0.35); }
    .stButton > button[kind="secondary"] { border-radius: 30px !important; border: 1px solid rgba(255,255,255,0.15) !important; background-color: transparent !important; }
    .stAlert, .streamlit-expanderHeader { background-color: rgba(255, 255, 255, 0.03) !important; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.05) !important; border-radius: 12px !important; }
    .stTextInput > div > div > input, .stSelectbox > div > div > div, .stMultiSelect > div > div { background-color: rgba(25, 20, 35, 0.8) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 8px !important; color: #f1f5f9 !important; }
    .stMultiSelect [data-baseweb="tag"] { background-color: rgba(167, 139, 250, 0.15) !important; border: 1px solid rgba(167, 139, 250, 0.3) !important; border-radius: 6px !important; }
    .stMultiSelect [data-baseweb="tag"] span { color: #f1f5f9 !important; font-weight: 400 !important; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { color: #a78bfa !important; border-bottom-color: #a78bfa !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# เตรียมพื้นที่จำลองสำหรับเก็บสถานะการยืนยันลบ
if 'delete_confirm_id' not in st.session_state:
    st.session_state.delete_confirm_id = None

# 3. เชื่อมต่อ Google Sheets สดแบบ Real-time
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_exp = conn.read(worksheet="expenses", ttl=0).dropna(subset=["id"])
except Exception:
    df_exp = pd.DataFrame(columns=["trip", "id", "item", "amount", "payer", "involved", "settled"])

try:
    df_meta = conn.read(worksheet="metadata", ttl=0).dropna(subset=["trip", "category"])
except Exception:
    df_meta = pd.DataFrame(columns=["trip", "category", "key", "value"])

# ตรวจสอบทริปตั้งต้น
all_trips = df_meta["trip"].unique().tolist()
if not all_trips:
    all_trips = ["ทริปพัทยา"]
    default_members = ["โจน่า", "ชีน", "แปม", "มาช่า", "ตะโก้", "แพท", "ซี"]
    new_rows = [{"trip": "ทริปพัทยา", "category": "member", "key": "", "value": m} for m in default_members]
    df_meta = pd.concat([df_meta, pd.DataFrame(new_rows)], ignore_index=True)
    conn.update(worksheet="metadata", data=df_meta)
    st.rerun()

if 'current_trip' not in st.session_state or st.session_state.current_trip not in all_trips:
    st.session_state.current_trip = all_trips[0]

# 4. เมนูด้านข้าง (Sidebar) จัดการทริป
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3176/3176366.png", width=50)
    st.header("Trips Management")
    
    new_trip = st.text_input("ตั้งชื่อทริปใหม่", placeholder="เช่น ทริปสมุย...")
    if st.button("➕ สร้างทริปใหม่", use_container_width=True, type="primary"):
        if new_trip and new_trip.strip() not in all_trips:
            new_row = pd.DataFrame([{"trip": new_trip.strip(), "category": "member", "key": "", "value": "เพื่อน 1"}])
            df_meta = pd.concat([df_meta, new_row], ignore_index=True)
            conn.update(worksheet="metadata", data=df_meta)
            st.session_state.current_trip = new_trip.strip()
            st.success("สร้างทริปสำเร็จ!")
            st.rerun()

    st.divider()
    selected_trip = st.selectbox("📌 เลือกทริปปัจจุบัน", all_trips, index=all_trips.index(st.session_state.current_trip))
    if selected_trip != st.session_state.current_trip:
        st.session_state.current_trip = selected_trip
        st.rerun()

    if st.button("🗑️ ลบทริปนี้ทิ้ง", type="secondary", use_container_width=True):
        df_meta = df_meta[df_meta["trip"] != st.session_state.current_trip]
        df_exp = df_exp[df_exp["trip"] != st.session_state.current_trip]
        conn.update(worksheet="metadata", data=df_meta)
        conn.update(worksheet="expenses", data=df_exp)
        st.session_state.current_trip = None
        st.rerun()

# 5. พื้นที่หลักทำงานตามทริป
if st.session_state.current_trip:
    current_trip = st.session_state.current_trip
    st.title(f"✨ {current_trip}")
    
    tab_members, tab_expenses, tab_summary = st.tabs(["👥 จัดการสมาชิก", "📝 บันทึกบิล", "📊 สรุปยอดและโอนเงิน"])
    
    # ================= แท็บ 1: จัดการสมาชิก =================
    with tab_members:
        st.subheader("รายชื่อผู้ร่วมทริปในปัจจุบัน")
        active_members = df_meta[(df_meta["trip"] == current_trip) & (df_meta["category"] == "member")]["value"].tolist()
        
        for name in active_members:
            col1, col2 = st.columns([4, 1])
            with col1: st.write(f"👤 {name}")
            with col2:
                if st.button("❌ ลบ", key=f"del_mem_{name}"):
                    df_meta = df_meta[~((df_meta["trip"] == current_trip) & (df_meta["category"] == "member") & (df_meta["value"] == name))]
                    conn.update(worksheet="metadata", data=df_meta)
                    st.rerun()
        st.write("---")
        add_name = st.text_input("เพิ่มชื่อเพื่อนผู้ร่วมทริปใหม่")
        if st.button("➕ เพิ่มสมาชิก"):
            if add_name.strip() and add_name.strip() not in active_members:
                new_row = pd.DataFrame([{"trip": current_trip, "category": "member", "key": "", "value": add_name.strip()}])
                df_meta = pd.concat([df_meta, new_row], ignore_index=True)
                conn.update(worksheet="metadata", data=df_meta)
                st.rerun()

    # ================= แท็บ 2: บันทึกบิลค่าใช้จ่าย =================
    with tab_expenses:
        df_trip_exp = df_exp[df_exp["trip"] == current_trip]
        if not active_members:
            st.warning("⚠️ กรุณาเพิ่มชื่อสมาชิกก่อนครับ")
        else:
            past_items = df_trip_exp["item"].unique().tolist()
            if past_items:
                item_choice = st.selectbox("ค่าอะไร?", ["➕ พิมพ์รายการใหม่..."] + past_items)
                item = st.text_input("พิมพ์ชื่อรายการ", placeholder="เช่น ค่าเรือ") if item_choice == "➕ พิมพ์รายการใหม่..." else item_choice
            else:
                item = st.text_input("ค่าอะไร?", placeholder="เช่น ค่าที่พัก")
                
            amount = st.number_input("ยอดเงินรวม (บาท)", min_value=0.0, step=10.0)
            col_p, col_i = st.columns(2)
            with col_p: payer = st.selectbox("ใครออกเงินไปก่อน?", active_members)
            with col_i: involved = st.multiselect("ใครต้องหารบิลนี้?", active_members, default=active_members)
            is_settled = st.checkbox("✅ จ่ายแยก/เคลียร์เงินกันเสร็จสิ้นแล้ว (บันทึกไว้ดูยอดรวมทริปเท่านั้น ไม่นำไปคำนวณสัญญากู้หนี้นะจ๊ะ อะฮิๆ)")

            if st.button("เก็บบิลนี้", type="primary", use_container_width=True):
                if item and amount > 0 and involved:
                    new_row = pd.DataFrame([{
                        "trip": current_trip, "id": uuid.uuid4().hex, "item": item,
                        "amount": amount, "payer": payer, "involved": ",".join(involved),
                        "settled": "TRUE" if is_settled else "FALSE"
                    }])
                    df_exp = pd.concat([df_exp, new_row], ignore_index=True)
                    conn.update(worksheet="expenses", data=df_exp)
                    st.success("บันทึกบิลลง Google Sheets สำเร็จ!")
                    st.rerun()

        st.divider()
        st.subheader("ประวัติบิลทั้งหมด")
        if df_trip_exp.empty:
            st.info("ยังไม่มีการบันทึกบิลครับ")
        else:
            for idx, row in df_trip_exp.iloc[::-1].iterrows():
                box_col, del_col = st.columns([5, 1])
                with box_col:
                    # 🌟 ปรับแก้จุดตรวจสอบตรงนี้ให้รองรับค่า Boolean จาก Google Sheets ครับ
                    status = "🟢 [เคลียร์หน้างานแล้ว]" if str(row["settled"]).upper() == "TRUE" else "⏳ [ค้างเคลียร์ยอด]"
                    st.info(f"**{row['item']}** ({float(row['amount']):,.2f} บาท) {status}\n\n👤 จ่ายโดย: {row['payer']} | 👥 หาร: {row['involved']}")
                
                with del_col:
                    if st.session_state.delete_confirm_id == row['id']:
                        st.write("⚠️ ลบ?")
                        c1, c2 = st.columns(2)
                        if c1.button("✅", key=f"conf_y_{row['id']}", help="ยืนยันการลบ"):
                            df_exp = df_exp[df_exp["id"] != row["id"]]
                            conn.update(worksheet="expenses", data=df_exp)
                            st.session_state.delete_confirm_id = None
                            st.rerun()
                        if c2.button("❌", key=f"conf_n_{row['id']}", help="ยกเลิก"):
                            st.session_state.delete_confirm_id = None
                            st.rerun()
                    else:
                        if st.button("❌", key=f"del_exp_{row['id']}", help="กดเพื่อลบรายการนี้"):
                            st.session_state.delete_confirm_id = row['id']
                            st.rerun()

    # ================= แท็บ 3: สรุปยอดและโอนเงิน =================
    with tab_summary:
        df_trip_exp = df_exp[df_exp["trip"] == current_trip]
        if df_trip_exp.empty:
            st.info("ยังไม่มีข้อมูลค่าใช้จ่ายให้คำนวณครับ")
        else:
            balances = {m: 0.0 for m in active_members}
            total_trip_cost = 0.0
            
            for idx, row in df_trip_exp.iterrows():
                amt = float(row["amount"])
                total_trip_cost += amt
                # 🌟 ปรับแก้จุดคัดกรองหนี้สินตรงนี้ด้วยเช่นกันครับ เพื่อให้ข้ามบิลที่จ่ายแล้วได้ถูกต้อง
                if str(row["settled"]).upper() == "TRUE": continue
                
                inv_list = [p.strip() for p in row["involved"].split(",") if p.strip() in balances]
                if not inv_list: continue
                
                split_amt = amt / len(inv_list)
                if row["payer"] in balances: balances[row["payer"]] += amt
                for person in inv_list: balances[person] -= split_amt

            st.metric(label="💰 ยอดรวมค่าใช้จ่ายทั้งทริป", value=f"฿ {total_trip_cost:,.2f}")
            st.divider()
            
            debtors = [[p, abs(b)] for p, b in balances.items() if b < -0.01]
            creditors = [[p, b] for p, b in balances.items() if b > 0.01]
            transfer_list = []
            
            while debtors and creditors:
                debtors.sort(key=lambda x: x[1], reverse=True)
                creditors.sort(key=lambda x: x[1], reverse=True)
                transfer_amt = min(debtors[0][1], creditors[0][1])
                transfer_list.append({"from": debtors[0][0], "to": creditors[0][0], "amount": transfer_amt})
                debtors[0][1] -= transfer_amt
                creditors[0][1] -= transfer_amt
                if debtors[0][1] < 0.01: debtors.pop(0)
                if creditors[0][1] < 0.01: creditors.pop(0)
                
            if transfer_list:
                st.markdown("### 💬 ช่วยเคลียร์หนี้ด้วยนะจ๊ะ")
                table_view = [{"ผู้โอน (🔴)": t["from"], "ผู้รับเงิน (🟢)": t["to"], "ยอดโอน": f"{t['amount']:,.2f} ฿"} for t in transfer_list]
                st.dataframe(pd.DataFrame(table_view), use_container_width=True, hide_index=True)
                
                # --- ส่วนแนบหลักฐานสลิปหลายไฟล์ ---
                st.divider()
                st.subheader("📤 แนบสลิปยืนยันการโอนเงิน")
                for t in transfer_list:
                    slip_key = f"{t['from']}->{t['to']}"
                    slip_rows = df_meta[(df_meta["trip"] == current_trip) & (df_meta["category"] == "slip") & (df_meta["key"] == slip_key)]
                    
                    with st.expander(f"🧾 สลิปจาก {t['from']} โอนให้ {t['to']} ({t['amount']:,.2f} ฿)"):
                        uploaded_slips = st.file_uploader("เลือกรูปสลิปจากมือถือ", type=['png', 'jpg', 'jpeg'], key=f"sl_file_{slip_key}", accept_multiple_files=True)
                        if uploaded_slips:
                            df_meta = df_meta[~((df_meta["trip"] == current_trip) & (df_meta["category"] == "slip") & (df_meta["key"] == slip_key))]
                            new_slips = [{"trip": current_trip, "category": "slip", "key": slip_key, "value": base64.b64encode(s.getvalue()).decode("utf-8")} for s in uploaded_slips]
                            df_meta = pd.concat([df_meta, pd.DataFrame(new_slips)], ignore_index=True)
                            conn.update(worksheet="metadata", data=df_meta)
                            st.rerun()
                        
                        if not slip_rows.empty:
                            for idx, s_row in enumerate(slip_rows.itertuples()):
                                try:
                                    st.image(base64.b64decode(s_row.value), width=230, caption=f"ใบที่ {idx+1}")
                                except Exception: st.write("ไม่สามารถแสดงรูปภาพได้")
                            if st.button("🗑️ ลบสลิปทั้งหมด", key=f"del_slips_{slip_key}"):
                                df_meta = df_meta[~((df_meta["trip"] == current_trip) & (df_meta["category"] == "slip") & (df_meta["key"] == slip_key))]
                                conn.update(worksheet="metadata", data=df_meta)
                                st.rerun()

                # --- ส่วนข้อมูลพร้อมเพย์ / QR เจ้าหนี้ ---
                st.divider()
                st.subheader("📱 ช่องทางรับเงิน (สำหรับผู้รับเงิน)")
                unique_creditors = list(set([t["to"] for t in transfer_list]))
                for creditor in unique_creditors:
                    with st.expander(f"ข้อมูลบัญชี / QR ของ: {creditor}"):
                        pp_row = df_meta[(df_meta["trip"] == current_trip) & (df_meta["category"] == "payment") & (df_meta["key"] == creditor)]
                        current_pp = pp_row["value"].values[0] if not pp_row.empty else ""
                        
                        pp_val = st.text_input("พร้อมเพย์ / เลขบัญชี", value=current_pp, key=f"pp_{creditor}")
                        if pp_val != current_pp:
                            if not pp_row.empty:
                                df_meta.loc[(df_meta["trip"] == current_trip) & (df_meta["category"] == "payment") & (df_meta["key"] == creditor), "value"] = pp_val
                            else:
                                df_meta = pd.concat([df_meta, pd.DataFrame([{"trip": current_trip, "category": "payment", "key": creditor, "value": pp_val}])], ignore_index=True)
                            conn.update(worksheet="metadata", data=df_meta)
                            st.rerun()
                            
                        qr_row = df_meta[(df_meta["trip"] == current_trip) & (df_meta["category"] == "qr") & (df_meta["key"] == creditor)]
                        uploaded_qr = st.file_uploader("อัปโหลด QR Code ประจำตัว", type=['png', 'jpg', 'jpeg'], key=f"qr_file_{creditor}")
                        if uploaded_qr is not None:
                            qr_base64 = base64.b64encode(uploaded_qr.getvalue()).decode("utf-8")
                            if not qr_row.empty:
                                df_meta.loc[(df_meta["trip"] == current_trip) & (df_meta["category"] == "qr") & (df_meta["key"] == creditor), "value"] = qr_base64
                            else:
                                df_meta = pd.concat([df_meta, pd.DataFrame([{"trip": current_trip, "category": "qr", "key": creditor, "value": qr_base64}])], ignore_index=True)
                            conn.update(worksheet="metadata", data=df_meta)
                            st.rerun()
                            
                        if not qr_row.empty and qr_row["value"].values[0]:
                            try: st.image(base64.b64decode(qr_row["value"].values[0]), width=180)
                            except Exception: pass
                            if st.button("ลบ QR", key=f"del_qr_{creditor}"):
                                df_meta = df_meta[~((df_meta["trip"] == current_trip) & (df_meta["category"] == "qr") & (df_meta["key"] == creditor))]
                                conn.update(worksheet="metadata", data=df_meta)
                                st.rerun()
            else:
                st.success("🎉 ทุกคนเจ๊ากันพอดี ไม่ต้องโอนเงินครับ!")
