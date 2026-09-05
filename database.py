import pandas as pd
from supabase import create_client, Client
import streamlit as st

class DatabaseManager:
    """คลาสสำหรับจัดการการเชื่อมต่อและดึงข้อมูลจาก Supabase (เวอร์ชัน 3NF แข็งแกร่ง)"""
    
    def __init__(self, url: str, key: str):
        self.supabase: Client = create_client(url, key)

    # ==========================================
    # แผนกดึงข้อมูล (READ) - กันบั๊กตารางว่าง
    # ==========================================
    def get_products(self):
        try:
            res = self.supabase.table('products').select('*').execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
        # ถ้าไม่มีข้อมูล หรือดึงพัง ให้ส่งโครงตารางเปล่าที่มีคอลัมน์ครบไปแทน (กันบั๊ก KeyError)
        return pd.DataFrame(columns=['product_id', 'product_name', 'category_id', 'color', 'size', 'price_1d', 'price_3d', 'price_5d', 'price_7d', 'fine_per_day', 'status'])

    def get_customers(self):
        try:
            res = self.supabase.table('customers').select('*').execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
        return pd.DataFrame(columns=['customer_id', 'customer_name', 'phone', 'address', 'note'])

    def get_users(self):
        try:
            res = self.supabase.table('users').select('*').execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
        return pd.DataFrame(columns=['username', 'password_hash', 'role', 'status'])

    def get_orders(self):
        try:
            res = self.supabase.table('orders').select('*, customers(customer_name, phone)').execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
        return pd.DataFrame(columns=['order_id', 'order_date', 'customer_id', 'start_date', 'end_date', 'shipping_fee', 'status', 'note', 'staff_username', 'customers'])

    def get_order_items(self):
        try:
            res = self.supabase.table('order_items').select('*, products(product_name)').execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
        return pd.DataFrame(columns=['order_id', 'product_id', 'rent_price', 'item_status', 'products'])

    # ==========================================
    # แผนกบันทึกและแก้ไขข้อมูล (WRITE / UPDATE)
    # ==========================================
    def create_order(self, order_data: dict, order_items_data: list):
        try:
            self.supabase.table('orders').insert(order_data).execute()
            if order_items_data:
                self.supabase.table('order_items').insert(order_items_data).execute()
            for item in order_items_data:
                self.supabase.table('products').update({'status': item['item_status']}).eq('product_id', item['product_id']).execute()
            return True
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการบันทึกบิล: {e}")
            return False

    def add_customer(self, customer_data: dict):
        try:
            self.supabase.table('customers').insert(customer_data).execute()
            return True
        except: return False
            
    def update_product_status(self, product_ids, new_status: str):
        try:
            if isinstance(product_ids, str): product_ids = [product_ids]
            for pid in product_ids:
                self.supabase.table('products').update({'status': new_status}).eq('product_id', pid).execute()
            return True
        except: return False

    def add_product(self, pid, name, cat_name, p1, p3, p5, p7, cost, fine, size, color):
        try:
            # แปลงชื่อหมวดหมู่ไทย ให้เป็นรหัส CAT-XX ก่อนบันทึกลงฐานข้อมูล
            cat_map = {"ชุดราตรี": "CAT-01", "ชุดไทย": "CAT-02", "สูทผู้ชาย": "CAT-03", "เครื่องประดับ": "CAT-04"}
            db_cat_id = cat_map.get(cat_name, cat_name)
            
            data = {
                'product_id': pid, 'product_name': name, 'category_id': db_cat_id,
                'color': color, 'size': size, 'price_1d': p1, 'price_3d': p3, 
                'price_5d': p5, 'price_7d': p7, 'fine_per_day': fine, 'status': 'ว่าง'
            }
            self.supabase.table('products').insert(data).execute()
            return True
        except Exception as e: 
            return False

    def edit_product_full(self, old_id, new_id, name, cat_name, p1, p3, p5, p7, cost, fine, size, color):
        try:
            cat_map = {"ชุดราตรี": "CAT-01", "ชุดไทย": "CAT-02", "สูทผู้ชาย": "CAT-03", "เครื่องประดับ": "CAT-04"}
            db_cat_id = cat_map.get(cat_name, cat_name)
            
            data = {
                'product_id': new_id, 'product_name': name, 'category_id': db_cat_id,
                'color': color, 'size': size, 'price_1d': p1, 'price_3d': p3, 
                'price_5d': p5, 'price_7d': p7, 'fine_per_day': fine
            }
            self.supabase.table('products').update(data).eq('product_id', old_id).execute()
            return True
        except: return False