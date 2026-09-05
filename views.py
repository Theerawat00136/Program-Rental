import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta, time
import plotly.express as px
import calendar
import utils
import re
from streamlit_calendar import calendar as st_calendar

CAT_LIST = ["เสื้อ", "เสื้อคลุม", "ชุดเดรส", "กางเกง", "กระโปรง", "หมวก", "กระเป๋า", "เครื่องประดับ", "รองเท้า", "ชุดเซ็ท", "อื่นๆ"]
PREFIX_MAP = {
    "เสื้อ": "S-", "เสื้อคลุม": "C-", "ชุดเดรส": "D-", "กางเกง": "P-", "กระโปรง": "SK-",
    "หมวก": "H-", "กระเป๋า": "B-", "เครื่องประดับ": "A-", "รองเท้า": "SH-", "ชุดเซ็ท": "SET-", "อื่นๆ": "O-"
}
STATUS_LIST = ["ว่าง", "จองแล้ว", "เช่าอยู่", "รอซัก", "ไม่พร้อมใช้งาน", "สูญหาย", "ยกเลิกจำหน่าย"]
SIZE_LIST = ["XS", "S", "M", "L", "XL", "XXL", "Free Size", "อื่นๆ"]
COLOR_LIST = ["ขาว", "ดำ", "เทา", "แดง", "ชมพู", "ส้ม", "เหลือง", "เขียว", "ฟ้า", "น้ำเงิน", "ม่วง", "น้ำตาล", "อื่นๆ"]

# 1. Service Classes (คลาสจัดการลอจิกเฉพาะทาง)
class PricingService:
    @staticmethod
    def calc_rent_price(days, p1, p3, p5, p7):
        try: d = max(1, int(days))
        except: d = 1
            
        def sf(val):
            if pd.isna(val): return 0.0
            try: 
                v = float(val)
                if str(v).lower() == 'nan': return 0.0
                return v
            except: return 0.0
                
        p1, p3, p5, p7 = sf(p1), sf(p3), sf(p5), sf(p7)
        
        total = 0
        if d >= 7 and p7 > 0: total += (d // 7) * p7; d = d % 7
        if d >= 5 and p5 > 0: total += (d // 5) * p5; d = d % 5
        if d >= 3 and p3 > 0: total += (d // 3) * p3; d = d % 3
        if d >= 1 and p1 > 0: total += d * p1
        elif d > 0 and p1 == 0:
            if p3 > 0: total += d * (p3/3)
            elif p5 > 0: total += d * (p5/5)
            elif p7 > 0: total += d * (p7/7)
        return total

#2. View Classes (คลาสจัดการหน้าจอแต่ละหน้า)

class DashboardView:
    def __init__(self, df_prod, df_cus, df_orders, df_items):
        self.df_prod = df_prod
        self.df_cus = df_cus
        self.df_orders = df_orders
        self.df_items = df_items

    def render(self):
        st.markdown("<h2 style='margin-bottom:0;'>รายงานภาพรวมระบบ (Dashboard)</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#6B7280; font-size:1rem; margin-top:0;'>แสดงข้อมูลสถิติ สถานะสินค้า และรายงานผลประกอบการ</p>", unsafe_allow_html=True)
        st.write("")

        active_prod = self.df_prod[self.df_prod['status'].astype(str).str.strip() != 'ยกเลิกจำหน่าย']
        total_items = len(active_prod)
        total_customers = len(self.df_cus)

        if not self.df_orders.empty:
            # กรองเอาเฉพาะบิลที่ไม่ถูกยกเลิกมาคำนวณยอด
            valid_orders = self.df_orders[self.df_orders['status'].astype(str).str.strip() != 'ยกเลิก'].copy()
            total_orders = len(valid_orders)
            
            if not valid_orders.empty:
                valid_orders['date_dt'] = pd.to_datetime(valid_orders['order_date'], errors='coerce')
                valid_orders['date_only'] = valid_orders['date_dt'].dt.date
                
                # นำ df_orders มา Join กับ df_items เพื่อหายอดเงินรวม (ค่าเช่าชุด + ค่าจัดส่ง)
                # รวมค่าเช่าจาก order_items ก่อน
                if not self.df_items.empty:
                    item_revenues = self.df_items.groupby('order_id')['rent_price'].sum().reset_index()
                    # เอาไปรวมกับ orders
                    merged_orders = pd.merge(valid_orders, item_revenues, on='order_id', how='left')
                    merged_orders['rent_price'] = merged_orders['rent_price'].fillna(0)
                    
                    # รายได้สุทธิต่อบิล = ค่าเช่า + ค่าส่ง
                    merged_orders['net_revenue'] = pd.to_numeric(merged_orders['rent_price'], errors='coerce').fillna(0) + \
                                                   pd.to_numeric(merged_orders['shipping_fee'], errors='coerce').fillna(0)
                else:
                    merged_orders = valid_orders.copy()
                    merged_orders['net_revenue'] = pd.to_numeric(merged_orders['shipping_fee'], errors='coerce').fillna(0)

                total_income = merged_orders['net_revenue'].sum()
                
                # คำนวณรายได้รายวัน
                daily_income = merged_orders.groupby('date_only')['net_revenue'].sum().reset_index()
                daily_income.columns = ['date', 'income']
                daily_income = daily_income.sort_values('date', ascending=False).head(7)
            else:
                total_income, total_orders, daily_income = 0, 0, pd.DataFrame()
        else:
            total_income, total_orders, daily_income = 0, 0, pd.DataFrame()

        # 3 กล่องสถิติด้านบน
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"<div style='padding:20px; border-radius:10px; border:1px solid #E5E7EB;'><div style='color:#6B7280; font-size:0.9rem;'>จำนวนคำสั่งซื้อรวม (รายการ)</div><div style='font-size:1.5rem; font-weight:bold;'>{total_orders:,}</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div style='padding:20px; border-radius:10px; border:1px solid #E5E7EB;'><div style='color:#6B7280; font-size:0.9rem;'>จำนวนลูกค้า (ราย)</div><div style='font-size:1.5rem; font-weight:bold;'>{total_customers:,}</div></div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div style='padding:20px; border-radius:10px; border:1px solid #E5E7EB;'><div style='color:#6B7280; font-size:0.9rem;'>สินค้าในระบบทั้งหมด (รายการ)</div><div style='font-size:1.5rem; font-weight:bold;'>{total_items:,}</div></div>", unsafe_allow_html=True)

        # กล่องยอดรายได้สีเข้ม
        st.markdown(f"""
        <div style='background-color:#111827; color:white; padding:30px; border-radius:10px; margin-top:20px; margin-bottom:20px;'>
            <div style='color:#9CA3AF; font-size:1rem; margin-bottom:5px;'>ยอดรายได้สะสมสุทธิ (THB)</div>
            <div style='font-size:3rem; font-weight:bold;'>฿ {total_income:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

        # 4 กล่องสถานะ
        status_counts = active_prod['status'].astype(str).str.strip().value_counts()
        c_free = status_counts.get('ว่าง', 0)
        c_book = status_counts.get('จองแล้ว', 0)
        c_rent = status_counts.get('เช่าอยู่', 0)
        c_wash = status_counts.get('รอซัก', 0)

        st.markdown("<b>สถานะคำสั่งซื้อและสินค้าปัจจุบัน</b>", unsafe_allow_html=True)
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1: st.markdown(f"<div style='text-align:center; padding:15px; border-radius:10px; border:1px solid #E5E7EB; border-bottom: 4px solid #10B981;'><div style='color:#6B7280; font-size:0.9rem;'>พร้อมใช้งาน</div><div style='font-size:1.8rem; font-weight:bold; color:#10B981;'>{c_free}</div></div>", unsafe_allow_html=True)
        with sc2: st.markdown(f"<div style='text-align:center; padding:15px; border-radius:10px; border:1px solid #E5E7EB; border-bottom: 4px solid #3B82F6;'><div style='color:#6B7280; font-size:0.9rem;'>ถูกจองล่วงหน้า</div><div style='font-size:1.8rem; font-weight:bold; color:#3B82F6;'>{c_book}</div></div>", unsafe_allow_html=True)
        with sc3: st.markdown(f"<div style='text-align:center; padding:15px; border-radius:10px; border:1px solid #E5E7EB; border-bottom: 4px solid #EF4444;'><div style='color:#6B7280; font-size:0.9rem;'>อยู่ระหว่างใช้งาน</div><div style='font-size:1.8rem; font-weight:bold; color:#EF4444;'>{c_rent}</div></div>", unsafe_allow_html=True)
        with sc4: st.markdown(f"<div style='text-align:center; padding:15px; border-radius:10px; border:1px solid #E5E7EB; border-bottom: 4px solid #F59E0B;'><div style='color:#6B7280; font-size:0.9rem;'>รอทำความสะอาด</div><div style='font-size:1.8rem; font-weight:bold; color:#F59E0B;'>{c_wash}</div></div>", unsafe_allow_html=True)

        st.write("---")
        chart_col, list_col = st.columns(2)
        with chart_col:
            st.markdown("<b>สัดส่วนสถานะสินค้าในระบบ</b>", unsafe_allow_html=True)
            if not active_prod.empty:
                df_status = status_counts.reset_index()
                df_status.columns = ['สถานะ', 'จำนวน']
                color_map = {'ว่าง': '#10B981', 'เช่าอยู่': '#EF4444', 'จองแล้ว': '#3B82F6', 'รอซัก': '#F59E0B', 'ไม่พร้อมใช้งาน': '#6B7280', 'สูญหาย': '#111827'}
                fig_pie = px.pie(df_status, values='จำนวน', names='สถานะ', hole=0.6, color='สถานะ', color_discrete_map=color_map)
                fig_pie.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=300)
                st.plotly_chart(fig_pie, use_container_width=True)

        with list_col:
            st.markdown("<b>รายงานรายได้ประจำวัน (7 วันล่าสุด)</b>", unsafe_allow_html=True)
            if not daily_income.empty:
                for _, row in daily_income.iterrows():
                    dt_obj = pd.to_datetime(row['date'])
                    st.markdown(f"""
                    <div style='display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid #E5E7EB;'>
                        <span style='color:#4B5563;'>{dt_obj.strftime('%A, %d/%m/%Y')}</span>
                        <span style='color:#10B981; font-weight:bold;'>+ ฿ {row['income']:,.2f}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("ยังไม่มีข้อมูลรายได้")

class POSView:
    def __init__(self, db_conn, df_prod, df_cus, df_orders, df_items):
        self.db = db_conn
        self.df_prod = df_prod
        self.df_cus = df_cus
        self.df_orders = df_orders
        self.df_items = df_items

    def render(self):
        if 'show_receipt_data' in st.session_state:
            rd = st.session_state['show_receipt_data']
            utils.display_receipt_modal(rd['html'], rd['img'], rd['filename'])

        st.markdown("<h2 style='margin-bottom:0;'>จัดการหน้าร้าน (Point of Sale)</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#6B7280; font-size:1.1rem; margin-top:0;'>ระบบบันทึกรายการเช่า จอง รับคืน และจัดการฐานข้อมูลเบื้องต้น</p>", unsafe_allow_html=True)
        st.write("")

        action_mode = st.radio("กรุณาเลือกประเภทรายการ:", 
                               ["บันทึกการเช่า / จองสินค้า", "บันทึกการรับคืนสินค้า", "จัดการฐานข้อมูลสินค้า"], 
                               horizontal=True)
        st.write("---")

        if action_mode == "บันทึกการเช่า / จองสินค้า":
            self._render_booking()
        elif action_mode == "บันทึกการรับคืนสินค้า":
            self._render_return()
        elif action_mode == "จัดการฐานข้อมูลสินค้า":
            self._render_inventory()

    def _render_booking(self):
        st.markdown("##### 1. เลือกระยะเวลาการใช้งาน")
        c_date, c_time, _ = st.columns([1.5, 1, 1.5])
        with c_date: dates = st.date_input("ระยะเวลาเช่า (ระบุวันรับ - วันคืน)", value=[], key="p_date", format="DD/MM/YYYY")
        with c_time: start_time = st.time_input("เวลาที่รับสินค้า", value=time(8, 0))

        num_days = 1
        start_dt_str, return_dt_str = "", ""
        req_start_dt, req_end_dt = None, None

        if len(dates) == 2:
            num_days = (dates[1] - dates[0]).days + 1
            req_start_dt = datetime.combine(dates[0], start_time)
            req_end_dt = req_start_dt + timedelta(days=num_days)
            start_dt_str = req_start_dt.strftime("%Y-%m-%d %H:%M:%S")
            return_dt_str = req_end_dt.strftime("%Y-%m-%d %H:%M:%S")
            st.info(f"📌 ระยะเวลาใช้งานรวม: **{num_days} วัน** (กำหนดส่งคืน: {req_end_dt.strftime('%d/%m/%Y %H:%M')})")
        st.write("")

        col_l, col_r = st.columns([1.5, 1.2])
        with col_l:
            with st.container(border=True):
                st.subheader("2. เลือกรายการสินค้า")
                
                # --- กู้คืนระบบดักวันซ้ำและวันดีเลย์ (Date Overlap & Buffer Days) ---
                delay_days = 1 # จำนวนวันดีเลย์เผื่อส่งซักหรือเตรียมชุด (ปรับตัวเลขได้ตามต้องการ)
                busy_product_ids = set()

                if len(dates) == 2 and not self.df_orders.empty and not self.df_items.empty:
                    # ดึงบิลที่กำลังเช่าหรือจองอยู่
                    active_orders = self.df_orders[self.df_orders['status'].astype(str).str.strip().isin(['จองแล้ว', 'เช่าอยู่', 'รอซัก'])].copy()
                    
                    for _, order in active_orders.iterrows():
                        try:
                            exist_start = pd.to_datetime(order['start_date'])
                            exist_end = pd.to_datetime(order['end_date'])
                            
                            # ขยายระยะเวลาของบิลเดิมออกไปตามวันดีเลย์
                            exist_start_with_delay = exist_start - timedelta(days=delay_days)
                            exist_end_with_delay = exist_end + timedelta(days=delay_days)
                            
                            # ตรวจสอบว่าวันที่ลูกค้าเลือก ทับซ้อนกับบิลเดิมที่บวกวันดีเลย์ไว้หรือไม่
                            if req_start_dt <= exist_end_with_delay and req_end_dt >= exist_start_with_delay:
                                # ถ้าทับซ้อน ให้เอารหัสชุดในบิลนั้นไปใส่บัญชีดำ (busy_product_ids)
                                o_id = order['order_id']
                                items_in_order = self.df_items[self.df_items['order_id'] == o_id]['product_id'].tolist()
                                busy_product_ids.update(items_in_order)
                        except:
                            continue

                # กรองสินค้าโชว์เฉพาะตัวที่ไม่โดนแบน (ไม่ได้อยู่ในช่วงเวลาที่ทับซ้อน) และต้องไม่ถูกยกเลิกจำหน่าย
                if len(dates) == 2:
                    df_free = self.df_prod[
                        (~self.df_prod['product_id'].isin(busy_product_ids)) & 
                        (self.df_prod['status'].astype(str).str.strip() != 'ยกเลิกจำหน่าย')
                    ].copy()
                else:
                    df_free = pd.DataFrame() # บังคับให้เลือกวันก่อนถึงจะโชว์ชุด

                # -------------------------------------------------------------

                if not df_free.empty and len(dates) == 2:
                    df_free = df_free.sort_values(by=['product_id'])
                    
                    selected_options = st.multiselect(
                        "ค้นหารหัสสินค้า หรือ ชื่อสินค้า", 
                        df_free.apply(lambda r: f"{r['product_id']} - {r['product_name']} (ไซส์: {r.get('size', '-')}, สี: {r.get('color', '-')})", axis=1).tolist(), 
                        key="pos_sel"
                    )

                    p_ids = [s.split(" - ")[0] for s in selected_options]
                    if p_ids:
                        sel_items = self.df_prod[self.df_prod['product_id'].isin(p_ids)].copy()
                        # คำนวณราคาเบื้องต้น (ใช้ราคา 1 วันคูณจำนวนวันไปก่อน หากต้องการใช้ Step วันให้ปรับแก้ตรงนี้)
                        sel_items['price'] = sel_items['price_1d'] * num_days 
                        base_total = sel_items['price'].sum()

                        st.write("---")
                        dynamic_key = f"edit_base_{'_'.join(p_ids)}_{num_days}"
                        edited_base_total = st.number_input("รวมค่าสินค้าทั้งหมด", min_value=0, value=int(base_total), step=50, key=dynamic_key, label_visibility="collapsed")

                        c_d1, c_d2 = st.columns(2)
                        with c_d1: discount_pct = st.number_input("ส่วนลด (%)", min_value=0, max_value=100, value=0, step=5, key="disc_pct")
                        with c_d2: shipping_fee = st.number_input("ค่าบริการจัดส่ง (บาท)", min_value=0, value=0, step=10, key="ship_fee")

                        discount_amt = edited_base_total * (discount_pct / 100)
                        grand_total = (edited_base_total - discount_amt) + shipping_fee

                        st.markdown(f"""<div style='background-color:#F8FAFC; padding:15px; border-radius:8px;'>
                            ยอดชำระสุทธิ (Grand Total): <span style='color:#1D4ED8; font-size:1.5rem; font-weight:bold;'>฿ {grand_total:,.2f}</span>
                        </div>""", unsafe_allow_html=True)
                elif len(dates) != 2:
                    st.info("กรุณาระบุระยะเวลาเช่าเพื่อตรวจสอบชุดที่ว่าง")
                else:
                    st.warning("ไม่มีสินค้าว่างในช่วงเวลาดังกล่าว")

        with col_r:
            with st.container(border=True):
                st.subheader("3. ข้อมูลลูกค้าและการชำระเงิน")
                cus_list = self.df_cus['customer_name'].tolist() if not self.df_cus.empty else []
                cus_choice = st.selectbox("เลือกข้อมูลลูกค้า", ["-- ลูกค้าทั่วไป --"] + cus_list, key="pos_cus")
                
                c_info = {}
                if cus_choice != "-- ลูกค้าทั่วไป --":
                    c_info = self.df_cus[self.df_cus['customer_name'] == cus_choice].iloc[0].to_dict()
                    st.markdown(f"<div style='background-color:#E5E7EB; padding:15px; border-radius:8px;'><b>{cus_choice}</b><br>เบอร์โทร: {c_info.get('phone', '')}</div>", unsafe_allow_html=True)

                rent_type = st.radio("ประเภทการทำรายการ:", ["รับสินค้าทันที", "จองล่วงหน้า (ระบุวันรับสินค้า)"], horizontal=True)
                note = st.text_input("รายละเอียดเพิ่มเติม / ค่ามัดจำ", key="p_note")
                st.write("")

                if st.button("บันทึกรายการและออกใบเสร็จ", key="p_btn", type="primary", use_container_width=True):
                    if 'p_ids' in locals() and p_ids and len(dates) == 2:
                        final_status = "เช่าอยู่" if "รับสินค้าทันที" in rent_type else "จองแล้ว"
                        
                        # --- 1. จัดรูปแบบข้อความให้ utils.py ดึงส่วนลด/ค่าส่ง ไปแยกบรรทัดได้ ---
                        note_parts = []
                        if discount_pct > 0:
                            note_parts.append(f"[ส่วนลด: {discount_pct}% (-{discount_amt:g} ฿)]")
                        if shipping_fee > 0:
                            note_parts.append(f"[ค่าจัดส่ง: {shipping_fee:g} ฿]")
                        if note.strip():
                            note_parts.append(note.strip())
                        final_note = " ".join(note_parts)
                        if not final_note: final_note = "-"
                        # -----------------------------------------------------------------

                        current_time = datetime.now()
                        display_tx_time = current_time.strftime("%d/%m/%Y %H:%M:%S")
                        
                        import utils
                        new_order_id = utils.Formatter.generate_order_id(display_tx_time)
                        
                        order_data = {
                            "order_id": new_order_id,
                            "order_date": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "customer_id": c_info.get('customer_id', 'CUS-000'), 
                            "start_date": start_dt_str, "end_date": return_dt_str,
                            "shipping_fee": shipping_fee, "status": final_status, "note": final_note,
                            "staff_username": st.session_state.get('current_user', 'admin')
                        }

                        # --- 2. ดึงราคาจริงของชุด x จำนวนวัน (ยกเลิกระบบหารเฉลี่ย) ---
                        order_items_data = []
                        receipt_items = []
                        for pid in p_ids:
                            p_row = self.df_prod[self.df_prod['product_id'] == pid].iloc[0]
                            actual_price = float(p_row['price_1d']) * num_days
                            
                            order_items_data.append({
                                "order_id": new_order_id, "product_id": pid, "rent_price": actual_price, "item_status": final_status
                            })
                            receipt_items.append({
                                'id': pid, 'name': p_row['product_name'], 'color': p_row.get('color', '-'), 'size': p_row.get('size', '-'), 'price': actual_price
                            })
                        # ---------------------------------------------------------

                        if self.db.create_order(order_data, order_items_data):
                            try:
                                df_receipt_items = pd.DataFrame(receipt_items)
                                
                                cus_name_display = cus_choice if cus_choice != "-- ลูกค้าทั่วไป --" else "ลูกค้าทั่วไป"
                                cus_phone_display = c_info.get('phone', '-') if cus_choice != "-- ลูกค้าทั่วไป --" else "-"
                                cus_addr_display = c_info.get('address', '-') if cus_choice != "-- ลูกค้าทั่วไป --" else "-"
                                
                                receipt_service = utils.ReceiptService()
                                html_receipt, img_receipt = receipt_service.create_assets(
                                    tx_time=display_tx_time, c_name=cus_name_display, c_phone=cus_phone_display, c_addr=cus_addr_display,
                                    date_start=req_start_dt.strftime("%d/%m/%Y"), date_end=req_end_dt.strftime("%d/%m/%Y"),
                                    total_rent=grand_total, note=final_note, final_status=final_status,
                                    sel_items=df_receipt_items, edited_base_total=edited_base_total
                                )
                                
                                filename = f"Receipt_{new_order_id}.png"
                                st.session_state['show_receipt_data'] = {'html': html_receipt, 'img': img_receipt, 'filename': filename}
                                
                                keys_to_clear = ['pos_sel', 'p_date', 'pos_cus', 'p_note', 'disc_pct', 'ship_fee']
                                for k in keys_to_clear:
                                    if k in st.session_state: del st.session_state[k]
                                st.toast("✅ บันทึกรายการและสร้างใบเสร็จเสร็จสิ้น!")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"บันทึกข้อมูลสำเร็จ แต่เกิดข้อผิดพลาดในการสร้างใบเสร็จ: {e}")
                        else:
                            st.error("เกิดข้อผิดพลาดในการบันทึกข้อมูลลงฐานข้อมูล")
                    else:
                        st.error("กรุณาระบุข้อมูลให้ครบถ้วน")

    def _render_return(self):
        # (ลอจิครับคืนแบบ 3NF ที่แก้ไว้แล้ว)
        with st.container(border=True):
            st.subheader("บันทึกการรับคืนสินค้า")
            if not self.df_orders.empty and not self.df_items.empty:
                df_merged = pd.merge(self.df_items, self.df_orders, on='order_id', how='inner')
                active_rent_trans = df_merged[df_merged['item_status'].astype(str).str.strip() == 'เช่าอยู่'].copy()
            else:
                active_rent_trans = pd.DataFrame()

            if not active_rent_trans.empty:
                def make_ret_display(r):
                    p_info = self.df_prod[self.df_prod['product_id'] == r['product_id']].iloc[0] if r['product_id'] in self.df_prod['product_id'].values else {}
                    cus_name = r.get('customers', {}).get('customer_name', r.get('customer_id', 'ไม่ทราบชื่อ')) if isinstance(r.get('customers'), dict) else r.get('customer_id', 'ไม่ทราบชื่อ')
                    return f"[#{r['order_id']}] {r['product_id']} {p_info.get('product_name','')} - ลค. {cus_name}"

                ret_options = active_rent_trans.apply(make_ret_display, axis=1).tolist()
                selected_ret = st.multiselect("ค้นหารหัสสินค้าเพื่อทำรายการรับคืน", ret_options, key="ret_sel")

                if selected_ret:
                    sel_order_ids = [s.split("]")[0].replace("[#", "") for s in selected_ret]
                    sel_pids = [s.split("] ")[1].split(" ")[0] for s in selected_ret]

                    total_late_fine = 0
                    for i in range(len(sel_pids)):
                        oid, pid = sel_order_ids[i], sel_pids[i]
                        target_trans = active_rent_trans[(active_rent_trans['order_id'] == oid) & (active_rent_trans['product_id'] == pid)].iloc[0]
                        p_inf = self.df_prod[self.df_prod['product_id'] == pid].iloc[0] if pid in self.df_prod['product_id'].values else {}
                        try: due_dt = pd.to_datetime(target_trans['end_date'])
                        except: due_dt = datetime.now()
                        if datetime.now() > due_dt:
                            late_days = (datetime.now() - due_dt).days
                            if late_days > 0:
                                fine = late_days * p_inf.get('fine_per_day', 0)
                                st.error(f"รหัส {pid}: เกินกำหนด (ค่าปรับ {fine} บาท)")
                                total_late_fine += fine
                        else:
                            st.success(f"รหัส {pid}: ส่งคืนตรงเวลา")

                    final_late_fine = st.number_input("ค่าปรับส่งคืนล่าช้า (บาท)", min_value=0, value=int(total_late_fine))
                    ret_condition = st.radio("สถานะสินค้า:", ["ปกติ (ส่งทำความสะอาด)", "ชำรุด (ต้องการซ่อมแซม)"], horizontal=True)
                    if st.button("ยืนยันการรับคืนสินค้า", type="primary", use_container_width=True):
                        new_stat = "รอซัก" if "ปกติ" in ret_condition else "ไม่พร้อมใช้งาน"
                        self.db.update_product_status(sel_pids, new_stat)
                        for pid, oid in zip(sel_pids, sel_order_ids):
                            self.db.supabase.table('order_items').update({'item_status': 'คืนสินค้าแล้ว'}).eq('order_id', oid).eq('product_id', pid).execute()
                        st.success("บันทึกข้อมูลรับคืนเสร็จสิ้น")
                        st.rerun()
            else:
                st.info("ไม่พบรายการที่กำลังเช่าอยู่")

    def _render_inventory(self):
        st.subheader("ระบบจัดการฐานข้อมูลสินค้า")
        # เปลี่ยนชื่อคอลัมน์ให้ตรง 3NF ทั้งหมด
        show_cols = ['product_id', 'product_name', 'category_id', 'size', 'color', 'fine_per_day', 'status', 'price_1d', 'price_3d', 'price_5d', 'price_7d']
        display_df = self.df_prod[self.df_prod['status'].astype(str).str.strip() != 'ยกเลิกจำหน่าย'].copy()

        if not display_df.empty:
            display_df = display_df.sort_values(by=['product_id']).reset_index(drop=True)
            st.dataframe(display_df[[c for c in show_cols if c in display_df.columns]], use_container_width=True, hide_index=True)

        with st.expander("เพิ่ม / แก้ไข ข้อมูลสินค้า", expanded=True):
            prod_mode = st.radio("โหมด:", ["✨ เพิ่มรายการใหม่", "✏️ แก้ไข/ลบ ข้อมูลเดิม"], horizontal=True, label_visibility="collapsed")
            
            if prod_mode == "✨ เพิ่มรายการใหม่":
                col1, col2 = st.columns(2)
                with col1:
                    ncat = st.selectbox("หมวดหมู่สินค้า", CAT_LIST, key="a_cat")
                    prefix = PREFIX_MAP.get(ncat, "O-")
                    nid = st.text_input(f"รหัสสินค้า (เริ่มด้วย {prefix})", value=f"{prefix}001", key="a_id")
                    nname = st.text_input("ชื่อสินค้า", key="a_name")
                with col2:
                    c_s, c_c = st.columns(2)
                    with c_s: nsize = st.selectbox("ขนาด (Size)", SIZE_LIST, key="a_size")
                    with c_c: ncolor = st.selectbox("สี", COLOR_LIST, key="a_color")

                c_p1, c_p3, c_p5, c_p7, c_ef = st.columns(5)
                with c_p1: n_p1 = st.number_input("ราคา 1 วัน", min_value=0, key="a_p1")
                with c_p3: n_p3 = st.number_input("ราคา 3 วัน", min_value=0, key="a_p3")
                with c_p5: n_p5 = st.number_input("ราคา 5 วัน", min_value=0, key="a_p5")
                with c_p7: n_p7 = st.number_input("ราคา 7 วัน", min_value=0, key="a_p7")
                with c_ef: nfine = st.number_input("ค่าปรับ/วัน", min_value=0, key="a_fine")

                if st.button("บันทึกข้อมูลสินค้าใหม่", type="primary", use_container_width=True):
                    if nid and nname: 
                        if self.db.add_product(nid, nname, ncat, n_p1, n_p3, n_p5, n_p7, 0, nfine, nsize, ncolor):
                            st.toast("เพิ่มข้อมูลสินค้าสำเร็จ! ✨")
                            st.rerun()
                        else:
                            st.error("บันทึกไม่สำเร็จ (รหัสอาจซ้ำ)")
                    else:
                        st.warning("กรุณากรอกรหัสและชื่อสินค้า")
            else:
                eid = st.selectbox("ค้นหารหัสเพื่อแก้ไขข้อมูล", [""] + display_df['product_id'].tolist(), key="e_sel")
                if eid:
                    curr = self.df_prod[self.df_prod['product_id'] == eid].iloc[0]
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        ename = st.text_input("ชื่อสินค้าใหม่", value=curr['product_name'], key="e_name")
                        estatus = st.selectbox("สถานะสินค้า", STATUS_LIST, key="e_status")
                    with col_e2:
                        e_p1 = st.number_input("ราคา 1 วัน", value=int(curr.get('price_1d', 0)), key="e_p1")
                        efine = st.number_input("อัตราค่าปรับ/วัน", value=int(curr.get('fine_per_day', 0)), key="e_fine")

                    c_btn1, c_btn2 = st.columns([3, 1])
                    with c_btn1:
                        if st.button("อัปเดตข้อมูลสินค้า", type="primary", use_container_width=True):
                            # อัปเดตราคาและสถานะ
                            self.db.supabase.table('products').update({'product_name': ename, 'price_1d': e_p1, 'fine_per_day': efine, 'status': estatus}).eq('product_id', eid).execute()
                            st.toast("อัปเดตข้อมูลสินค้าสำเร็จ! ✅")
                            st.rerun()
                    with c_btn2:
                        if st.button("🗑️ ลบสินค้า", use_container_width=True):
                            self.db.update_product_status([eid], "ยกเลิกจำหน่าย")
                            st.toast("ลบสินค้าสำเร็จ 🗑️")
                            st.rerun()
class OrdersView:
    def __init__(self, db_conn, df_prod, df_orders, df_items):
        self.db = db_conn
        self.df_prod = df_prod
        self.df_orders = df_orders
        self.df_items = df_items

    def render(self):
        st.markdown("<h2 style='margin-bottom:0;'>ระบบจัดการคำสั่งซื้อ (Order Management)</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#6B7280; font-size:1rem; margin-top:0;'>ตรวจสอบและอัปเดตสถานะคำสั่งซื้อทั้งหมดของระบบ</p>", unsafe_allow_html=True)

        if 'show_receipt_data' in st.session_state:
            rd = st.session_state['show_receipt_data']
            utils.display_receipt_modal(rd['html'], rd['img'], rd['filename'])

        if self.df_orders.empty:
            st.info("ยังไม่มีข้อมูลคำสั่งซื้อในระบบ")
            return

        # เตรียมข้อมูล Orders
        display_orders = self.df_orders.copy()
        display_orders = display_orders.sort_values(by='order_date', ascending=False)
        
        # ตัวกรอง
        c_filter1, c_filter2, c_filter3 = st.columns([2, 1, 1])
        with c_filter1:
            status_filter = st.radio("สถานะออเดอร์", ["ทั้งหมด", "จองล่วงหน้า", "อยู่ระหว่างเช่า", "คืนสินค้าแล้ว", "ยกเลิก"], horizontal=True, label_visibility="collapsed")
        with c_filter2:
            search_txt = st.text_input("ค้นหาตามออเดอร์", placeholder="เช่น #ORD-...", label_visibility="collapsed")
        with c_filter3:
            search_date = st.date_input("ค้นหาตามวันที่ใช้งาน", value=None, label_visibility="collapsed")

        # กรองข้อมูล
        filtered_df = display_orders.copy()
        if status_filter != "ทั้งหมด":
            status_map = {"จองล่วงหน้า": "จองแล้ว", "อยู่ระหว่างเช่า": "เช่าอยู่", "คืนสินค้าแล้ว": "คืนสินค้าแล้ว", "ยกเลิก": "ยกเลิก"}
            filtered_df = filtered_df[filtered_df['status'].str.strip() == status_map.get(status_filter, "")]
        if search_txt:
            filtered_df = filtered_df[filtered_df['order_id'].str.contains(search_txt, case=False)]
        if search_date:
            search_dt_str = search_date.strftime("%Y-%m-%d") # ปรับ format ตามตาราง orders
            filtered_df = filtered_df[filtered_df['start_date'].astype(str).str.contains(search_dt_str) | filtered_df['end_date'].astype(str).str.contains(search_dt_str)]

        st.write("---")

        # แสดงผลแบบ Card
        for _, row in filtered_df.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2.5, 1.5, 1.5])
                
                # ดึงข้อมูลลูกค้าจากที่ Join ไว้
                cus_info = row.get('customers', {})
                if not isinstance(cus_info, dict): cus_info = {}
                cus_name = cus_info.get('customer_name', row.get('customer_id', 'ไม่ทราบชื่อ'))
                cus_phone = cus_info.get('phone', '-')

                with c1:
                    try:
                        display_date = pd.to_datetime(row['order_date']).strftime("%d/%m/%Y %H:%M")
                    except:
                        display_date = row['order_date']
                        
                    st.markdown(f"<div style='color:#6B7280; font-size:0.8rem;'>เวลาทำรายการ: {display_date} | <span style='color:#3B82F6;'>#{row['order_id']}</span></div>", unsafe_allow_html=True)
                    st.markdown(f"<b>{cus_name}</b><br><span style='font-size:0.9rem;'>เบอร์ติดต่อ: {cus_phone}</span>", unsafe_allow_html=True)

                with c2:
                    # ค้นหาชุดที่อยู่ในบิลนี้ จาก df_items
                    order_items = self.df_items[self.df_items['order_id'] == row['order_id']] if not self.df_items.empty else pd.DataFrame()
                    items_list = []
                    total_price = 0
                    
                    for _, item in order_items.iterrows():
                        p_name = item.get('products', {}).get('product_name', '') if isinstance(item.get('products'), dict) else ''
                        items_list.append(f"{item['product_id']} {p_name}")
                        total_price += item.get('rent_price', 0)
                        
                    # บวกค่าส่งเพิ่มเข้าไปใน total_price
                    total_price += row.get('shipping_fee', 0)
                    
                    items_html = "".join([f"<li>{item}</li>" for item in items_list])
                    st.markdown(f"<div style='font-size:0.9rem;'><b>รายการสินค้า ({len(items_list)} ชิ้น)</b><ul style='margin:0; padding-left:20px; color:#4B5563;'>{items_html}</ul><div style='color:#6B7280; margin-top:5px;'>ระยะเวลา: {row['start_date']} ถึง {row['end_date']}</div></div>", unsafe_allow_html=True)

                with c3:
                    st.markdown(f"<div style='text-align:right; font-size:1.2rem; font-weight:bold;'>฿ {total_price:,.2f}</div>", unsafe_allow_html=True)
                    status_color = "#10B981" if "ชำระ" in row['status'] or "คืน" in row['status'] else ("#3B82F6" if "จอง" in row['status'] else ("#EF4444" if "เช่า" in row['status'] else "#6B7280"))
                    st.markdown(f"<div style='text-align:right;'><span style='background-color:{status_color}20; color:{status_color}; padding:4px 12px; border-radius:20px; font-size:0.8rem; font-weight:bold;'>{row['status']}</span></div>", unsafe_allow_html=True)

                with c4:
                    if st.button("📄 พิมพ์ใบเสร็จ", key=f"btn_receipt_{row['order_id']}", use_container_width=True):
                            mock_items_list = []
                            for _, r in order_items.iterrows():
                                pid = r.get('product_id', '')
                                p_name = r.get('products', {}).get('product_name', '') if isinstance(r.get('products'), dict) else pid
                                
                                # ค้นหา สี/ไซส์ จากตาราง products หลัก
                                p_color, p_size = '-', '-'
                                if not self.df_prod.empty and pid in self.df_prod['product_id'].values:
                                    prod_row = self.df_prod[self.df_prod['product_id'] == pid].iloc[0]
                                    p_color = prod_row.get('color', '-')
                                    p_size = prod_row.get('size', '-')
                                    # ถ้าหาชื่อไม่เจอจากตอนแรก ให้ดึงจากตาราง products แทน
                                    if not p_name or p_name == pid:
                                        p_name = prod_row.get('product_name', pid)

                                mock_items_list.append({
                                    'id': pid,
                                    'name': p_name,
                                    'color': p_color,
                                    'size': p_size,
                                    'price': float(r.get('rent_price', 0)) # ดึงราคาจริงที่บันทึกไว้ในบิล
                                })
                            
                            html_content, img_bytes = utils.ReceiptService().create_assets(
                                display_date, cus_name, cus_phone, "",
                                str(row['start_date']), str(row['end_date']), total_price, row.get('note', ''), row['status'], pd.DataFrame(mock_items_list), total_price
                            )
                            st.session_state['show_receipt_data'] = {'html': html_content, 'img': img_bytes, 'filename': f"Receipt_{row['order_id']}.png"}
                            st.rerun()

                    if row['status'] in ['จองแล้ว', 'เช่าอยู่']:
                        if st.button("❌ ยกเลิกออเดอร์", key=f"btn_cancel_{row['order_id']}", use_container_width=True):
                            # ปรับสถานะบิลเป็นยกเลิก
                            self.db.supabase.table('orders').update({'status': 'ยกเลิก'}).eq('order_id', row['order_id']).execute()
                            # ปรับรายการสินค้าในบิลให้ยกเลิก
                            self.db.supabase.table('order_items').update({'item_status': 'ยกเลิก'}).eq('order_id', row['order_id']).execute()
                            
                            # ปรับสถานะชุดคืนให้ว่าง
                            pids_to_free = order_items['product_id'].tolist()
                            if pids_to_free:
                                self.db.update_product_status(pids_to_free, "ว่าง")
                                
                            st.toast("ยกเลิกคำสั่งซื้อสำเร็จ!")
                            st.rerun()

                    if row['status'] == 'จองแล้ว':
                            if st.button("📦 ยืนยันการรับชุด", key=f"btn_pickup_{row['order_id']}", use_container_width=True, type="primary"):
                                # อัปเดตสถานะในตารางหลัก
                                self.db.supabase.table('orders').update({'status': 'เช่าอยู่'}).eq('order_id', row['order_id']).execute()
                                # อัปเดตสถานะในตารางสินค้าย่อย
                                self.db.supabase.table('order_items').update({'item_status': 'เช่าอยู่'}).eq('order_id', row['order_id']).execute()
                                
                                st.toast("✅ อัปเดตสถานะเป็น 'เช่าอยู่' เรียบร้อย!")
                                import time
                                time.sleep(0.5)
                                st.rerun()

class CalendarView:
    def __init__(self, df_prod, df_orders, df_items):
        self.df_prod = df_prod
        self.df_orders = df_orders
        self.df_items = df_items

    def render(self):
        st.markdown("<h2 style='margin-bottom:0;'>ตารางกำหนดการ (Calendar)</h2>", unsafe_allow_html=True)
        st.write("---")
        
        if not self.df_orders.empty:
            # กรองเฉพาะบิลที่กำลังเช่าหรือจอง
            active_orders = self.df_orders[self.df_orders['status'].astype(str).str.strip().isin(['จองแล้ว', 'เช่าอยู่'])].copy()
            
            if active_orders.empty:
                st.success("ไม่มีคิวการจองหรือเช่าในขณะนี้")
            else:
                events = []
                table_data = [] 
                current_time = datetime.now()
                
                for _, row in active_orders.iterrows():
                    order_id = row['order_id']
                    
                    # ค้นหาชุดทั้งหมดที่อยู่ในบิลนี้
                    order_items = self.df_items[self.df_items['order_id'] == order_id] if not self.df_items.empty else pd.DataFrame()
                    
                    prod_details = []
                    for _, item in order_items.iterrows():
                        pid = item['product_id']
                        # อัปเดตการดึงชื่อเป็น product_name
                        p_name = item.get('products', {}).get('product_name', '') if isinstance(item.get('products'), dict) else ''
                        if not p_name:
                            p_info = self.df_prod[self.df_prod['product_id'] == pid]
                            p_name = p_info.iloc[0].get('product_name', '') if not p_info.empty else ''
                            
                        prod_details.append(f"{pid} - {p_name}")
                            
                    prod_detail_str = '\n'.join(prod_details)
                    
                    cus_info = row.get('customers', {})
                    if not isinstance(cus_info, dict): cus_info = {}
                    cus_name = cus_info.get('customer_name', row.get('customer_id', 'ไม่ทราบชื่อ'))

                    try:
                        start_dt_obj = pd.to_datetime(row['start_date'])
                        end_dt_obj = pd.to_datetime(row['end_date'])
                    except:
                        start_dt_obj = pd.to_datetime(row['start_date'], dayfirst=True, errors='coerce')
                        end_dt_obj = pd.to_datetime(row['end_date'], dayfirst=True, errors='coerce')

                    if pd.isna(start_dt_obj): start_dt_obj = datetime.now()
                    if pd.isna(end_dt_obj): end_dt_obj = datetime.now()

                    start_dt = start_dt_obj.strftime("%Y-%m-%dT%H:%M:%S")
                    end_dt = end_dt_obj.strftime("%Y-%m-%dT%H:%M:%S")
                    
                    db_status = str(row['status']).strip()
                    display_status = ""
                    bg_color = ""
                    
                    if db_status == "จองแล้ว":
                        display_status = "จอง (รอรับชุด)"
                        bg_color = "#3B82F6"
                    elif db_status == "เช่าอยู่":
                        if current_time >= end_dt_obj or (end_dt_obj - current_time).days < 1:
                            display_status = "เตือน! ถึงกำหนดคืน / เกินกำหนด"
                            bg_color = "#EF4444"
                        else:
                            display_status = "เช่าอยู่ (กำลังใช้งาน)"
                            bg_color = "#10B981"
                    
                    items_count = len(prod_details)
                    item_text = f" ({items_count} ชุด)" if items_count > 1 else ""
                    short_title = f"#{order_id} | ลค.{cus_name}{item_text}"
                    
                    events.append({
                        "title": short_title,
                        "start": start_dt,
                        "end": end_dt,
                        "backgroundColor": bg_color,
                        "borderColor": bg_color,
                        "extendedProps": {
                            "order_no": f"#{order_id}",
                            "prod_detail": prod_detail_str.replace('\n', '<br>'),
                            "cus_name": cus_name,
                            "status": display_status,
                            "start_date": row['start_date'],
                            "end_date": row['end_date'],
                            "note": row.get('note', '-')
                        }
                    })
                    
                    table_data.append({
                        'Order_No': f"#{order_id}",
                        'Product_Detail': prod_detail_str,
                        'cus_name': cus_name,
                        'start_date': row['start_date'],
                        'end_date': row['end_date'],
                        'status': db_status
                    })
                
                calendar_options = {
                    "initialView": "dayGridMonth",
                    "headerToolbar": {
                        "left": "today prev,next",
                        "center": "title",
                        "right": "dayGridMonth,timeGridWeek,timeGridDay",
                    },
                    "slotMinTime": "06:00:00",
                    "slotMaxTime": "22:00:00",
                    "eventDisplay": "block",
                    "displayEventTime": False,
                }
                
                c_leg1, c_leg2, c_leg3 = st.columns(3)
                with c_leg1: st.markdown("🔵 **สีน้ำเงิน:** จองล่วงหน้า (รอรับชุด)")
                with c_leg2: st.markdown("🟢 **สีเขียว:** เช่าอยู่ (กำลังใช้งาน)")
                with c_leg3: st.markdown("🔴 **สีแดง:** แจ้งเตือน! คืนวันนี้/เกินกำหนด")
                st.write("")
                
                try:
                    from streamlit_calendar import calendar as st_calendar
                    cal_result = st_calendar(events=events, options=calendar_options)
                    
                    if cal_result and "callback" in cal_result and cal_result["callback"] == "eventClick":
                        evt = cal_result["eventClick"]["event"]["extendedProps"]
                        st.markdown("### 🔍 รายละเอียดออเดอร์ที่เลือก")
                        st.info(f"""
                        **หมายเลขออเดอร์:** {evt['order_no']}\n
                        **ชื่อลูกค้า:** คุณ {evt['cus_name']}\n
                        **รายละเอียดสินค้า:**<br> {evt['prod_detail']}\n
                        **สถานะการเช่า:** {evt['status']}\n
                        **วันที่รับชุด:** {evt['start_date']}\n
                        **กำหนดส่งคืน:** {evt['end_date']}\n
                        **หมายเหตุ:** {evt['note']}
                        """)
                except ImportError:
                    st.warning("ไม่พบไลบรารี streamlit_calendar กรุณาติดตั้งหรือตรวจสอบการนำเข้า")
                
                st.write("---")
                st.markdown("#### 📋 สรุปคิวงานแบบตาราง")
                if table_data:
                    df_table = pd.DataFrame(table_data)
                    st.dataframe(df_table, use_container_width=True, hide_index=True)
        else:
            st.info("ยังไม่มีข้อมูลคิวงานในระบบ")

class LaundryView:
    def __init__(self, db_conn, df_prod):
        self.db = db_conn
        self.df_prod = df_prod

    def render(self):
        st.markdown("<h2 style='margin-bottom:0;'>จัดการสินค้าส่งซัก (Laundry)</h2>", unsafe_allow_html=True)
        st.write("---")
        
        if self.df_prod.empty:
            st.success("🎉 ไม่มีสินค้าตกค้างในระบบทำความสะอาดครับ!")
            return
            
        wash_df = self.df_prod[self.df_prod['status'].astype(str).str.strip() == 'รอซัก'].copy()
        
        if wash_df.empty:
            st.success("🎉 ไม่มีสินค้าตกค้างในระบบทำความสะอาดครับ!")
        else:
            # ปรับชื่อคอลัมน์ให้ตรงกับ 3NF (ตาราง Products)
            show_cols = ['product_id', 'product_name', 'category_id', 'color', 'size', 'status']
            valid_cols = [c for c in show_cols if c in wash_df.columns]
            
            st.dataframe(wash_df[valid_cols], use_container_width=True, hide_index=True)
            st.write("")
            
            with st.container(border=True):
                st.markdown("#### 🧺 อัปเดตสถานะหลังซักเสร็จ")
                
                # นำรหัสและชื่อชุดมาเชื่อมกัน เพื่อให้พนักงานเลือกง่ายขึ้น (ไม่สับสนรหัส)
                options = wash_df['product_id'].astype(str) + " - " + wash_df['product_name'].astype(str)
                selected_val = st.selectbox("เลือกรหัสสินค้าที่ทำความสะอาดเรียบร้อยแล้ว", options.tolist())
                
                if st.button("บันทึกว่าพร้อมใช้งาน (เปลี่ยนสถานะเป็น 'ว่าง')", type="primary"):
                    if selected_val:
                        # แยกรหัสสินค้าออกมาจากข้อความที่เลือก
                        finish_id = selected_val.split(" - ")[0]
                        
                        # อัปเดตลงฐานข้อมูล (ส่งค่าแบบ String เดี่ยวๆ)
                        self.db.update_product_status(finish_id, "ว่าง")
                        
                        st.success(f"อัปเดตสถานะ {finish_id} เป็น 'ว่าง' เรียบร้อย ระบบพร้อมนำไปปล่อยเช่าต่อครับ!")
                        st.rerun()
class CustomersView:
    def __init__(self, db_conn, df_cus):
        self.db = db_conn
        self.df_cus = df_cus

    def render(self):
        st.markdown("<h2 style='margin-bottom:0;'>ระบบจัดการฐานข้อมูลลูกค้า (Customers)</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#6B7280;'>บริหารจัดการข้อมูลลูกค้าสำหรับการทำรายการ</p>", unsafe_allow_html=True)
        st.write("---")

        # ตารางแสดงข้อมูลลูกค้า
        if not self.df_cus.empty:
            show_cols = ['customer_id', 'customer_name', 'phone', 'address', 'note']
            valid_cols = [c for c in show_cols if c in self.df_cus.columns]
            
            df_show = self.df_cus[valid_cols].copy()
            df_show.columns = ['รหัสลูกค้า', 'ชื่อ-นามสกุล', 'เบอร์ติดต่อ', 'ที่อยู่', 'หมายเหตุ'][:len(valid_cols)]
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        else:
            st.info("ยังไม่มีข้อมูลลูกค้าในระบบ")

        with st.expander("เพิ่ม / แก้ไข ข้อมูลลูกค้า", expanded=True):
            mode = st.radio("โหมด:", ["✨ เพิ่มรายการใหม่", "✏️ แก้ไขข้อมูลเดิม"], horizontal=True, label_visibility="collapsed")
            
            if mode == "✨ เพิ่มรายการใหม่":
                c_name = st.text_input("ชื่อ-นามสกุล")
                c_phone = st.text_input("เบอร์ติดต่อ")
                c_address = st.text_area("ที่อยู่")
                c_note = st.text_input("หมายเหตุเพิ่มเติม (เช่น สัดส่วน อก-เอว-สะโพก)")
                
                if st.button("บันทึกข้อมูลลูกค้า", type="primary", use_container_width=True):
                    if c_name:
                        from datetime import datetime
                        # สร้างรหัสลูกค้าอัตโนมัติ
                        new_cid = f"CUS-{datetime.now().strftime('%y%m%d%H%M')}"
                        
                        # แพ็กข้อมูลรวมกันเป็น Dictionary 1 ก้อน ส่งให้ Database (แก้บักพารามิเตอร์เกิน)
                        customer_data = {
                            "customer_id": new_cid,
                            "customer_name": c_name,
                            "phone": c_phone,
                            "address": c_address,
                            "note": c_note
                        }
                        
                        if self.db.add_customer(customer_data):
                            st.success("เพิ่มข้อมูลลูกค้าเรียบร้อย!")
                            st.rerun()
                        else:
                            st.error("เกิดข้อผิดพลาดในการบันทึกข้อมูล")
                    else:
                        st.warning("กรุณากรอกชื่อ-นามสกุล")
            
            else:
                if not self.df_cus.empty:
                    e_cid = st.selectbox("เลือกลูกค้าที่ต้องการแก้ไข", self.df_cus['customer_id'].tolist())
                    if e_cid:
                        curr_cus = self.df_cus[self.df_cus['customer_id'] == e_cid].iloc[0]
                        e_name = st.text_input("ชื่อ-นามสกุล (ใหม่)", value=curr_cus.get('customer_name', ''))
                        e_phone = st.text_input("เบอร์ติดต่อ (ใหม่)", value=curr_cus.get('phone', ''))
                        e_address = st.text_area("ที่อยู่ (ใหม่)", value=curr_cus.get('address', ''))
                        e_note = st.text_input("หมายเหตุ (ใหม่)", value=curr_cus.get('note', ''))
                        
                        if st.button("อัปเดตข้อมูลลูกค้า", type="primary", use_container_width=True):
                            update_data = {
                                "customer_name": e_name,
                                "phone": e_phone,
                                "address": e_address,
                                "note": e_note
                            }
                            try:
                                self.db.supabase.table('customers').update(update_data).eq('customer_id', e_cid).execute()
                                st.success("อัปเดตข้อมูลเรียบร้อย!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"เกิดข้อผิดพลาด: {e}")

class FinanceView:
    def __init__(self, db_conn, df_orders, df_items, df_prod):
        self.db = db_conn
        self.df_orders = df_orders
        self.df_items = df_items
        self.df_prod = df_prod

    def render(self):
        st.markdown("<h2 style='margin-bottom:0;'>รายงานการเงินและบัญชี (Financial Report)</h2>", unsafe_allow_html=True)
        st.write("---")
        
        if self.df_orders.empty:
            st.info("ยังไม่มีข้อมูลการทำรายการ")
            return

        # ==========================================
        # 1. เตรียมข้อมูลแบบ 3NF
        # ==========================================
        df_orders_clean = self.df_orders.copy()
        df_orders_clean['date_dt'] = pd.to_datetime(df_orders_clean['order_date'], errors='coerce')
        df_orders_clean['shipping_fee'] = pd.to_numeric(df_orders_clean['shipping_fee'], errors='coerce').fillna(0)

        # แยกบิลรายรับ (ไม่รวมที่ยกเลิก) และ บิลรายจ่าย
        valid_orders = df_orders_clean[~df_orders_clean['status'].astype(str).str.strip().isin(['รายจ่าย', 'ยกเลิก'])].copy()
        expenses = df_orders_clean[df_orders_clean['status'].astype(str).str.strip() == 'รายจ่าย'].copy()

        # นำ df_items มาคำนวณยอดค่าเช่ารวมต่อบิล
        if not self.df_items.empty and not valid_orders.empty:
            item_revenues = self.df_items.groupby('order_id')['rent_price'].sum().reset_index()
            # ดึงรหัสชุดทั้งหมดมาต่อกันเป็น String ไว้โชว์ในตาราง
            item_list = self.df_items.groupby('order_id')['product_id'].apply(lambda x: ', '.join(x)).reset_index()
            
            valid_income = pd.merge(valid_orders, item_revenues, on='order_id', how='left')
            valid_income = pd.merge(valid_income, item_list, on='order_id', how='left')
            
            valid_income['rent_price'] = valid_income['rent_price'].fillna(0)
            valid_income['total_price'] = valid_income['rent_price'] + valid_income['shipping_fee']
        else:
            valid_income = valid_orders.copy()
            valid_income['total_price'] = valid_income['shipping_fee']
            valid_income['product_id'] = "-"

        if not expenses.empty:
            # รายจ่ายมักจะไม่มีใน order_items เลยไปดึงจาก note ที่เราบันทึกไว้แทน หรือถ้ามีใน shipping_fee ก็ใช้ได้
            # สมมติว่าค่าใช้จ่ายถูกบันทึกลงใน shipping_fee ตอนสร้างบิลรายจ่าย
            expenses['total_price'] = expenses['shipping_fee']
            expenses['product_id'] = "-"

        # ==========================================
        # 2. สรุปยอดรวม (Top Cards)
        # ==========================================
        total_rev = valid_income['total_price'].sum() if not valid_income.empty else 0
        total_ship = valid_income['shipping_fee'].sum() if not valid_income.empty else 0
        total_exp = expenses['total_price'].sum() if not expenses.empty else 0
        net_profit = total_rev - total_exp
        order_count = len(valid_income)

        # 5 กล่องสรุปยอด
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.markdown(f"<div style='padding:15px; border-radius:8px; border:1px solid #E5E7EB; border-top:4px solid #3B82F6;'><div style='font-size:0.8rem;'>รายได้สะสมรวม</div><div style='font-size:1.5rem; font-weight:bold; color:#3B82F6;'>฿{total_rev:,.2f}</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div style='padding:15px; border-radius:8px; border:1px solid #E5E7EB; border-top:4px solid #8B5CF6;'><div style='font-size:0.8rem;'>รายได้ค่าจัดส่ง</div><div style='font-size:1.5rem; font-weight:bold; color:#8B5CF6;'>฿{total_ship:,.2f}</div></div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div style='padding:15px; border-radius:8px; border:1px solid #E5E7EB; border-top:4px solid #EF4444;'><div style='font-size:0.8rem;'>ค่าใช้จ่ายสะสม</div><div style='font-size:1.5rem; font-weight:bold; color:#EF4444;'>฿{total_exp:,.2f}</div></div>", unsafe_allow_html=True)
        with c4: st.markdown(f"<div style='padding:15px; border-radius:8px; background-color:#111827; color:white;'><div style='font-size:0.8rem; color:#9CA3AF;'>กำไรสุทธิสะสม</div><div style='font-size:1.5rem; font-weight:bold;'>฿{net_profit:,.2f}</div></div>", unsafe_allow_html=True)
        with c5: st.markdown(f"<div style='padding:15px; border-radius:8px; border:1px solid #E5E7EB; border-top:4px solid #10B981;'><div style='font-size:0.8rem;'>จำนวนคำสั่งซื้อ</div><div style='font-size:1.5rem; font-weight:bold; color:#10B981;'>{order_count} รายการ</div></div>", unsafe_allow_html=True)

        st.write("")
        
        # ==========================================
        # 3. ฟอร์มบันทึกค่าใช้จ่าย
        # ==========================================
        with st.expander("💸 บันทึกรายการค่าใช้จ่าย"):
            ec1, ec2, ec3 = st.columns([1, 2, 1])
            with ec1: ex_date = st.date_input("วันที่ทำรายการ")
            with ec2: ex_title = st.text_input("รายละเอียดค่าใช้จ่าย (เช่น ค่าซักรีด, ค่าโฆษณา)")
            with ec3: ex_amt = st.number_input("จำนวนเงิน (บาท)", min_value=0)
            
            if st.button("บันทึกค่าใช้จ่าย", type="primary"):
                if ex_title and ex_amt > 0:
                    ex_dt_str = datetime.combine(ex_date, datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S")
                    import utils
                    new_order_id = utils.Formatter.generate_order_id(datetime.combine(ex_date, datetime.now().time()).strftime("%d/%m/%Y %H:%M:%S"))
                    
                    # บันทึกเป็นบิลสถานะ 'รายจ่าย' ในตาราง orders
                    expense_data = {
                        "order_id": new_order_id,
                        "order_date": ex_dt_str,
                        "customer_id": "CUS-000", # หรือรหัสลูกค้า dummy สำหรับร้าน
                        "shipping_fee": ex_amt,   # ยืมช่อง shipping_fee เก็บยอดรายจ่าย
                        "status": "รายจ่าย",
                        "note": ex_title,
                        "staff_username": st.session_state.get('current_user', 'admin')
                    }
                    self.db.supabase.table('orders').insert(expense_data).execute()
                    
                    st.success("บันทึกค่าใช้จ่ายเรียบร้อย")
                    st.rerun()

        st.write("---")
        
        # ==========================================
        # 4. รายงานและดาวน์โหลด
        # ==========================================
        st.markdown("#### ข้อมูลบัญชีและรายงาน")
        
        # รวมข้อมูลรายรับและรายจ่ายเข้าด้วยกันเพื่อทำรายงาน
        all_reports = pd.concat([valid_income, expenses], ignore_index=True) if not expenses.empty else valid_income.copy()
        
        if all_reports.empty:
            st.info("ไม่พบข้อมูลสำหรับสร้างรายงาน")
            return

        report_type = st.radio("เลือกรูปแบบรายงาน:", ["สรุปรายเดือน", "สรุปรายวัน"], horizontal=True)
        
        if report_type == "สรุปรายเดือน":
            all_reports['period'] = all_reports['date_dt'].dt.strftime('%Y-%m')
        else:
            all_reports['period'] = all_reports['date_dt'].dt.strftime('%Y-%m-%d')
            
        periods = all_reports['period'].dropna().unique().tolist()
        periods.sort(reverse=True)
        sel_period = st.selectbox(f"เลือก{'เดือน' if report_type == 'สรุปรายเดือน' else 'วันที่'}", periods if periods else ["-"])
        
        filtered_data = all_reports[all_reports['period'] == sel_period]

        if not filtered_data.empty:
            f_inc = filtered_data[filtered_data['status'] != 'รายจ่าย'].copy()
            f_exp = filtered_data[filtered_data['status'] == 'รายจ่าย'].copy()
            
            p_rev = f_inc['total_price'].sum() if not f_inc.empty else 0
            p_exp = f_exp['total_price'].sum() if not f_exp.empty else 0
            p_net = p_rev - p_exp
            
            st.info(f"📊 **สรุปยอด {sel_period}:** รายรับ ฿{p_rev:,.2f} | รายจ่าย ฿{p_exp:,.2f} | **กำไรสุทธิ ฿{p_net:,.2f}** | คำสั่งซื้อ {len(f_inc)} รายการ")
            
            # เตรียมไฟล์ CSV
            csv_export = filtered_data[['order_date', 'customer_id', 'product_id', 'total_price', 'status', 'note']].copy()
            csv_export.columns = ['วันที่', 'รหัสลูกค้า', 'รหัสสินค้า', 'จำนวนเงิน', 'สถานะ', 'หมายเหตุ']
            csv = csv_export.to_csv(index=False).encode('utf-8-sig')
            
            st.download_button(label=f"ดาวน์โหลดรายงาน {sel_period} (.csv)", data=csv, file_name=f"report_{sel_period}.csv", mime='text/csv', use_container_width=True)
            
            tab1, tab2 = st.tabs(["รายรับ", "รายจ่าย"])
            with tab1: 
                display_inc = f_inc[['order_date', 'customer_id', 'product_id', 'total_price', 'status']].copy()
                display_inc.columns = ['วันที่', 'รหัสลูกค้า', 'รหัสสินค้า', 'ยอดเงิน', 'สถานะ']
                st.dataframe(display_inc, use_container_width=True, hide_index=True)
            with tab2: 
                display_exp = f_exp[['order_date', 'note', 'total_price']].copy()
                display_exp.columns = ['วันที่', 'รายการ', 'ยอดเงิน']
                st.dataframe(display_exp, use_container_width=True, hide_index=True)

# ==========================
# 3. Router Functions
# ==========================
def render_dashboard(df_prod, df_cus, df_orders, df_items):
    view = DashboardView(df_prod, df_cus, df_orders, df_items)
    view.render()

def render_pos(db_conn, df_prod, df_cus, df_orders, df_items):
    view = POSView(db_conn, df_prod, df_cus, df_orders, df_items)
    view.render()

def render_orders(db_conn, df_prod, df_orders, df_items):
    view = OrdersView(db_conn, df_prod, df_orders, df_items)
    view.render()

def render_calendar(df_prod, df_orders, df_items):
    view = CalendarView(df_prod, df_orders, df_items)
    view.render()

def render_laundry(db_conn, df_prod):
    view = LaundryView(db_conn, df_prod)
    view.render()

def render_customers(db_conn, df_cus):
    view = CustomersView(db_conn, df_cus)
    view.render()

def render_accounting(db_conn, df_orders, df_items, df_prod):
    view = FinanceView(db_conn, df_orders, df_items, df_prod)
    view.render()