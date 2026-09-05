import streamlit as st
import hashlib
from PIL import Image, ImageDraw, ImageFont
import urllib.request
import io
import re
import pandas as pd


#กลุ่มเครื่องมือจัดการข้อมูล (Static Class)
class Formatter:
    """คลาสรวมเครื่องมือจัดรูปแบบข้อมูลตัวเลขและข้อความ"""
    
    @staticmethod
    def generate_order_id(tx_time):
        return str(int(hashlib.md5(str(tx_time).encode()).hexdigest(), 16))[-5:].zfill(5)

    @staticmethod
    def safe_float(val):
        try:
            return float(str(val).replace(',', '').strip())
        except:
            return 0.0

#สร้างใบเสร็จ 
class ReceiptService:
    """คลาสสำหรับประมวลผลและสร้างใบเสร็จรับเงินทั้ง HTML และรูปภาพ"""
    
    def __init__(self):
        # โหลดฟอนต์ไทยเก็บไว้ในความทรงจำของ Object ตั้งแต่เริ่มต้น
        self.font_title = self._get_thai_font(32)
        self.font_body = self._get_thai_font(22)
        self.font_small = self._get_thai_font(18)

    def _get_thai_font(self, size):
        try:
            url = "https://github.com/google/fonts/raw/main/ofl/prompt/Prompt-Regular.ttf"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            font_bytes = urllib.request.urlopen(req, timeout=5).read()
            return ImageFont.truetype(io.BytesIO(font_bytes), size)
        except Exception:
            return ImageFont.load_default()

    def create_assets(self, tx_time, c_name, c_phone, c_addr, date_start, date_end, total_rent, note, final_status, sel_items, edited_base_total=None):
        clean_note = str(note).strip()
        shipping_fee = 0.0
        discount_pct = 0
        discount_amt = 0.0
        
        match_ship = re.search(r'\[ค่าจัดส่ง:\s*([\d,]+(?:\.\d+)?)\s*(?:฿|THB)?\]', clean_note)
        if match_ship:
            fee_str = match_ship.group(1).replace(',', '')
            shipping_fee = float(fee_str)
            clean_note = clean_note.replace(match_ship.group(0), '').strip()
            
        match_disc = re.search(r'\[ส่วนลด:\s*(\d+)%\s*\(\-([\d,]+(?:\.\d+)?)\s*(?:฿|THB)?\)\]', clean_note)
        if match_disc:
            discount_pct = int(match_disc.group(1))
            discount_amt = float(match_disc.group(2).replace(',', ''))
            clean_note = clean_note.replace(match_disc.group(0), '').strip()

        if clean_note.lower() in ['nan', 'none', '']: clean_note = "-"

        if final_status == "เช่าอยู่" or final_status == "คืนสินค้าแล้ว": doc_type = "ใบเสร็จรับเงิน (RECEIPT)"
        elif final_status == "ยกเลิก": doc_type = "ใบยกเลิกรายการ (CANCELED)"
        else: doc_type = "ใบจองสินค้า (BOOKING)"
        
        order_no = Formatter.generate_order_id(tx_time) 
        original_base_total = sum([Formatter.safe_float(row.get('price', 0)) for _, row in sel_items.iterrows()])
        
        display_base = float(edited_base_total) if edited_base_total is not None else float(original_base_total)
        price_changed = (display_base != original_base_total)

        # --- ส่วนสร้าง HTML (เอาไว้โชว์บนเว็บ) ---
        items_html = ""
        for _, row in sel_items.iterrows():
            price_val = Formatter.safe_float(row.get('price', 0))
            price_text = "" if price_changed else f"<span style='float:right;'>{price_val:,.0f} ฿</span>"
            items_html += f"<li style='margin-bottom:8px;'><span style='color:#6B7280'>{row['id']}</span> <b>{row['name']}</b> <span style='font-size:0.8rem; color:#4B5563;'>(สี: {row.get('color', '-')}, ไซส์: {row.get('size', '-')})</span>{price_text}</li>"
        
        items_html += f"<hr style='border:1px dashed #E5E7EB; margin:12px 0;'>"
        items_html += f"<li style='margin-bottom:6px;'><span style='color:#6B7280'></span> <b>รวมค่าสินค้า</b><span style='float:right;'>{display_base:,.0f} ฿</span></li>"
        
        if discount_amt > 0:
            items_html += f"<li style='margin-bottom:6px;'><span style='color:#EF4444'>-</span> <b style='color:#EF4444'>ส่วนลด ({discount_pct}%)</b><span style='float:right; color:#EF4444;'>-{discount_amt:,.0f} ฿</span></li>"
        if shipping_fee > 0:
            items_html += f"<li style='margin-bottom:6px;'><span style='color:#6B7280'>+</span> <b>ค่าบริการจัดส่ง</b><span style='float:right;'>{shipping_fee:,.0f} ฿</span></li>"

        shop_name = st.session_state.get('shop_name', 'Store Management')

        html_content = f"""
        <div class="receipt-box" style="margin-bottom: 0;">
            <h3 style="text-align:center; color:#111827; margin-bottom:5px;">{shop_name}</h3>
            <p style="text-align:center; color:#6B7280; font-size:0.9rem; margin-top:0;">{doc_type}<br>{tx_time}</p>
            <hr style="border:1px dashed #9CA3AF">
            <p style="font-size:0.9rem; line-height: 1.5;">
                <b>เลขที่รายการ (Order No):</b> <span style="color:#2563EB; font-weight:bold;">#{order_no}</span><br>
                <b>ชื่อลูกค้า:</b> {c_name} ({c_phone})<br>
                <b>วันที่รับสินค้า:</b> {date_start}<br>
                <b style="color:#DC2626;">กำหนดส่งคืน: {date_end}</b><br>
                <b>หมายเหตุ:</b> {clean_note}
            </p>
            <hr style="border:1px dashed #9CA3AF">
            <ul style="list-style-type:none; padding-left:0; font-size:0.95rem;">{items_html}</ul>
            <hr style="border:1px dashed #9CA3AF">
            <h3 style="text-align:right; color:#2563EB !important;">ยอดชำระสุทธิ: ฿ {total_rent:,.2f}</h3>
            <div style="text-align:center; margin-top:25px; padding-top: 15px; border-top: 1px solid #E5E7EB;">
                <p style="font-size:0.85rem; margin-bottom: 5px; color:#4B5563;">ใบเสร็จรับเงิน / ค่าบริการเช่าชุด</p> 
                <p style="font-size:0.8rem; margin-top:0; color:#6B7280;">ขอบคุณที่ไว้วางใจใช้บริการของเราค่ะ 💖</p> 
            </div>
        </div>
        """
        
        # --- ส่วนสร้างรูปภาพ (เอาไว้โหลดลงเครื่อง) ---
        base_h = 600 
        item_h = len(sel_items) * 35
        item_h += 45 
        if discount_amt > 0: item_h += 35
        if shipping_fee > 0: item_h += 35

        img = Image.new('RGB', (600, base_h + item_h), color=(255, 255, 255))
        d = ImageDraw.Draw(img)

        def draw_item_row(y_pos, left_text, right_text="", text_color=(75,85,99)):
            d.text((60, y_pos), left_text, font=self.font_body, fill=text_color)
            if right_text:
                d.text((560, y_pos), right_text, font=self.font_body, fill=text_color, anchor="rt")
            return y_pos + 35

        y = 30
        title_text = "@Dressmebesties.co - " + ("CANCELED" if final_status=="ยกเลิก" else ("BOOKING" if final_status=="จองแล้ว" else "RECEIPT"))
        d.text((300, y), title_text, font=self.font_title, fill=(31,41,55), anchor="mt")
        y += 50
        d.text((40, y), f"วันที่ทำรายการ: {tx_time}", font=self.font_small, fill=(107,114,128))
        y += 30
        d.line([(40, y), (560, y)], fill=(229,231,235), width=2)
        y += 20
        d.text((40, y), f"เลขที่รายการ: #{order_no}", font=self.font_body, fill=(37,99,235))
        y += 35
        d.text((40, y), f"ชื่อลูกค้า: {c_name} ({c_phone})", font=self.font_body, fill=(31,41,55))
        y += 35
        d.text((40, y), f"วันที่รับสินค้า: {date_start}", font=self.font_body, fill=(31,41,55))
        y += 35
        d.text((40, y), f"กำหนดส่งคืน: {date_end}", font=self.font_body, fill=(220,38,38))
        y += 45
        d.text((40, y), "รายละเอียดสินค้า:", font=self.font_body, fill=(31,41,55))
        y += 35
        
        for _, row in sel_items.iterrows():
            item_text = f"- {row['id']} {row['name']} ({row.get('color', '-')}/{row.get('size', '-')})"
            price_val = Formatter.safe_float(row.get('price', 0))
            price_str = "" if price_changed else f"{price_val:,.0f} THB"
            y = draw_item_row(y, item_text, price_str)
        
        y += 5
        d.line([(60, y), (560, y)], fill=(229,231,235), width=1)
        y += 15
        
        y = draw_item_row(y, "รวมค่าสินค้า", f"{display_base:,.0f} THB", text_color=(31,41,55))
        
        if discount_amt > 0:
            y = draw_item_row(y, f"- ส่วนลด ({discount_pct}%)", f"-{discount_amt:,.0f} THB", text_color=(220,38,38))
            
        if shipping_fee > 0:
            y = draw_item_row(y, "+ ค่าบริการจัดส่ง", f"{shipping_fee:,.0f} THB", text_color=(31,41,55))

        y += 10
        d.line([(40, y), (560, y)], fill=(229,231,235), width=2)
        y += 20
        d.text((40, y), f"หมายเหตุ: {clean_note}", font=self.font_body, fill=(31,41,55))
        y += 60
        d.text((560, y), f"ยอดชำระสุทธิ: {total_rent:,.2f} THB", font=self.font_title, fill=(37,99,235), anchor="rt")
        
        y += 50
        d.line([(40, y), (560, y)], fill=(229,231,235), width=1)
        y += 20
        d.text((300, y), "IG: @Dressmebesties.co  |  LINE: @Dressme", font=self.font_small, fill=(75,85,99), anchor="mt")
        y += 25
        d.text((300, y), "ขอบคุณที่ใช้บริการค่ะ 💖 รีวิวแท็ก IG รับส่วนลด 10% น้า", font=self.font_small, fill=(107,114,128), anchor="mt")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return html_content, buf.getvalue()

#ฟังก์ชันสำหรับ UI 
def apply_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #F8FAFC !important; font-family: 'Prompt', sans-serif; }
        html, body, p, span, h1, h2, h3, h4, h5, h6, label, li, .stMarkdown { color: #111827 !important; }
        .stButton>button { background-color: #2563EB !important; border: none; border-radius: 8px; padding: 0.5rem 1rem; }
        .stButton>button p, .stButton>button span { color: #FFFFFF !important; font-weight: 600; }
        .stButton>button:hover { background-color: #1D4ED8 !important; }
        
        div[data-baseweb="input"] > div, div[data-baseweb="base-input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {
            background-color: #FFFFFF !important; border: 1px solid #D1D5DB !important; border-radius: 8px !important;
        }
        div[data-baseweb="input"] input, div[data-baseweb="base-input"] input, div[data-baseweb="base-input"] textarea, div[data-testid="stDateInput"] input {
            color: #000000 !important; -webkit-text-fill-color: #000000 !important; background-color: transparent !important; font-weight: 500;
        }
        div[data-baseweb="select"] div, div[data-baseweb="select"] span { color: #000000 !important; }
        span[data-baseweb="tag"] { background-color: #DBEAFE !important; color: #1E40AF !important; }

        div[data-baseweb="popover"] > div, div[data-baseweb="popover"] > div > div, div[data-baseweb="popover"] ul, div[data-baseweb="menu"] { background-color: #FFFFFF !important; }
        div[data-baseweb="popover"] li { color: #111827 !important; background-color: #FFFFFF !important; }
        div[data-baseweb="popover"] li:hover { background-color: #F3F4F6 !important; }
        div[data-baseweb="popover"] span { color: #111827 !important; }

        [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E5E7EB; }
        .receipt-box { border: 1px solid #E5E7EB; padding: 30px; background: #FFFFFF; border-radius: 16px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); margin-bottom: 20px; }
        
        .dash-top-card { background-color: #FFFFFF; padding: 15px 20px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #E5E7EB; margin-bottom: 15px; }
        .dash-top-title { font-size: 0.9rem; color: #6B7280; font-weight: 500; }
        .dash-top-val { font-size: 1.5rem; font-weight: 700; color: #111827; }
        
        .dash-card-dark { background-color: #0F172A; color: white !important; padding: 30px 40px; border-radius: 16px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); margin-bottom: 25px; }
        .dash-title-dark { font-size: 1.1rem; color: #94A3B8 !important; font-weight: 500; margin-bottom: 8px; }
        .dash-val-white { font-size: 3.5rem; font-weight: 800; color: #FFFFFF !important; line-height: 1.1; }
        
        .dash-card-light { background-color: #FFFFFF; padding: 20px 24px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #E5E7EB; text-align: center; margin-bottom: 20px; }
        .card-free { border-top: 4px solid #10B981; }
        .card-book { border-top: 4px solid #3B82F6; }
        .card-rent { border-top: 4px solid #EF4444; }
        .card-wash { border-top: 4px solid #F59E0B; }
        
        .dash-title { font-size: 0.95rem; color: #6B7280 !important; font-weight: 600; margin-bottom: 5px; }
        .dash-value { font-size: 2rem; font-weight: 800; line-height: 1.2; }
        
        .status-badge { padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; display: inline-block; }
        .bg-booking { background-color: #DBEAFE; color: #1E40AF; border: 1px solid #BFDBFE; }
        .bg-renting { background-color: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }
        .bg-returned { background-color: #D1FAE5; color: #065F46; border: 1px solid #A7F3D0; }
        .bg-canceled { background-color: #FEE2E2; color: #991B1B; border: 1px solid #FECACA; }
        .bg-damaged { background-color: #F3F4F6; color: #374151; border: 1px solid #D1D5DB; }
        .bg-fine { background-color: #FEF3C7; color: #B45309; border: 1px solid #FCD34D; }
        
        .chart-container { background-color: #FFFFFF; padding: 20px; border-radius: 16px; border: 1px solid #E5E7EB; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        .metric-card { background: #FFFFFF; padding: 20px; border-radius: 12px; border: 1px solid #E5E7EB; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .metric-profit { background: #0F172A; padding: 20px; border-radius: 12px; margin-bottom: 15px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border: 1px solid #1E293B; }
    </style>
    """, unsafe_allow_html=True)

try:
    dialog_func = st.dialog
except AttributeError:
    try:
        dialog_func = st.experimental_dialog
    except AttributeError:
        dialog_func = None

if dialog_func:
    @dialog_func("ใบเสร็จรับเงิน")
    def display_receipt_modal(html_content, img_bytes, file_name):
        st.markdown(html_content, unsafe_allow_html=True)
        st.write("")
        c_dl, c_close = st.columns(2)
        with c_dl:
            st.download_button("บันทึกไฟล์รูปภาพ", data=img_bytes, file_name=file_name, mime="image/png", use_container_width=True)
        with c_close:
            if st.button("ปิดหน้าต่าง", use_container_width=True):
                del st.session_state['show_receipt_data']
                st.rerun()
else:
    def display_receipt_modal(html_content, img_bytes, file_name):
        st.markdown("---")
        st.subheader("ใบเสร็จรับเงิน")
        st.markdown(html_content, unsafe_allow_html=True)
        c_dl, c_close = st.columns(2)
        with c_dl:
            st.download_button("บันทึกไฟล์รูปภาพ", data=img_bytes, file_name=file_name, mime="image/png", use_container_width=True)
        with c_close:
            if st.button("ปิดหน้าต่าง", use_container_width=True):
                del st.session_state['show_receipt_data']
                st.rerun()
        st.markdown("---")