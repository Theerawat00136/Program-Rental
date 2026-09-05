import streamlit as st
import database as db
import utils 
import views 
import pandas as pd

#ตั้งชื่อแอปบนแท็บเบราว์เซอร์
st.set_page_config(page_title="Dressme Rental Management System", layout="wide", initial_sidebar_state="expanded")

try:
    utils.apply_custom_css()
except Exception as e:
    pass
#ชื่อร้าน
if 'shop_name' not in st.session_state:
    st.session_state['shop_name'] = "Dressme Rental"
    
if 'shop_desc' not in st.session_state:
    st.session_state['shop_desc'] = "ระบบบริหารจัดการร้านเช่าชุด (Store Management System)"

#Login System
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state['logged_in']:
    st.markdown("<div style='margin-top: 100px;'></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        with st.form("login_form", border=True):
            st.markdown(f"<h2 style='text-align: center; color: #2563EB !important;'>{st.session_state['shop_name']}</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; color: #6B7280; margin-bottom: 20px;'>{st.session_state['shop_desc']}</p>", unsafe_allow_html=True)
            
            # เพิ่มช่อง Username และ Password
            username = st.text_input("ชื่อผู้ใช้งาน (Username)", placeholder="กรุณากรอกชื่อผู้ใช้งาน")
            pwd = st.text_input("รหัสผ่าน (Password)", type="password", placeholder="กรุณากรอกรหัสผ่านเพื่อเข้าสู่ระบบ")
            
            # ปุ่ม Submit ของฟอร์ม
            if st.form_submit_button("เข้าสู่ระบบ (Login)", type="primary", use_container_width=True):
                # 1. เชื่อมต่อและดึงข้อมูลจากตาราง users
                db_conn = db.DatabaseManager(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
                df_users = db_conn.get_users()
                
                # 2. ค้นหาชื่อผู้ใช้และรหัสผ่านที่กรอกมา (บังคับให้เป็น String ก่อนเทียบ)
                user_match = df_users[(df_users['username'].astype(str).str.strip() == username.strip()) & (df_users['password_hash'].astype(str).str.strip() == pwd.strip())]
                
                if not user_match.empty:
                    # ตรวจสอบสถานะบัญชี
                    user_status = user_match.iloc[0]['status']
                    if user_status == 'Active':
                        st.session_state['logged_in'] = True
                        st.session_state['current_user'] = username
                        st.session_state['role'] = user_match.iloc[0]['role']
                        st.rerun()
                    else:
                        st.error("บัญชีของคุณถูกระงับการใช้งาน กรุณาติดต่อผู้ดูแลระบบ")
                else:
                    st.error("❌ ชื่อผู้ใช้งาน หรือ รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง")
            
            st.write("")
            st.caption("ระบบได้รับการป้องกันความปลอดภัย กรุณาเก็บรักษารหัสผ่านเป็นความลับ")
            
    st.stop()

 #Main App
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

if 'db_manager' not in st.session_state:
    st.session_state.db_manager = db.DatabaseManager(SUPABASE_URL, SUPABASE_KEY)

db_conn = st.session_state.db_manager

df_prod = db_conn.get_products()

# ดึงข้อมูลบิลและรายละเอียดบิลแบบ 3NF
df_orders = db_conn.get_orders()
df_items = db_conn.get_order_items()

df_cus = db_conn.get_customers()
if not df_cus.empty and 'note' not in df_cus.columns:
    df_cus['note'] = '-'

#เมนูด้านซ้ายและRouter
st.sidebar.title(f"👗 {st.session_state['shop_name']}")
st.sidebar.caption(st.session_state['shop_desc'])
st.sidebar.divider()

menu_options = [
    "ภาพรวมระบบ (Dashboard)", 
    "จัดการหน้าร้าน (POS)", 
    "ระบบคำสั่งซื้อ (Orders)", 
    "ตารางกำหนดการ (Calendar)", 
    "จัดการสินค้าส่งซัก (Laundry)", 
    "ฐานข้อมูลลูกค้า (Customers)", 
    "รายงานการเงิน (Finance)"
]
choice = st.sidebar.radio("เมนูหลัก (Main Menu)", menu_options, label_visibility= "collapsed")

st.sidebar.divider()
if st.sidebar.button("ออกจากระบบ (Logout)", use_container_width=True):
    st.session_state['logged_in'] = False
    st.session_state.clear()
    st.rerun()

try:
    if choice == "ภาพรวมระบบ (Dashboard)":
        views.render_dashboard(df_prod, df_cus, df_orders, df_items)
    elif choice == "จัดการหน้าร้าน (POS)":
        views.render_pos(db_conn, df_prod, df_cus, df_orders, df_items)
    elif choice == "ระบบคำสั่งซื้อ (Orders)":
        views.render_orders(db_conn, df_prod, df_orders, df_items)
    elif choice == "ตารางกำหนดการ (Calendar)":
        views.render_calendar(df_prod, df_orders, df_items)
    elif choice == "จัดการสินค้าส่งซัก (Laundry)":
        views.render_laundry(db_conn, df_prod)
    elif choice == "ฐานข้อมูลลูกค้า (Customers)":
        views.render_customers(db_conn, df_cus)
    elif choice == "รายงานการเงิน (Finance)":
        views.render_accounting(db_conn, df_orders, df_items, df_prod)
except Exception as e:
    st.error(f"เกิดข้อผิดพลาดในการโหลดหน้า '{choice}': {str(e)}")

if 'show_receipt_data' in st.session_state:
    data = st.session_state['show_receipt_data']
    try:
        utils.display_receipt_model(data['html'], data['img'], data['filename'])
    except Exception as e:
        st.error("เกิดข้อผิดพลาดในการสร้างหรือแสดงใบเสร็จ")
        