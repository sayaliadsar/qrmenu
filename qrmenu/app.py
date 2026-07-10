from flask import Flask, render_template, request, redirect, url_for, session, make_response
import mysql.connector
import qrcode
import io
import base64
from datetime import datetime
import requests  # SMS पाठवण्यासाठी

# PDF जनरेशनसाठी
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
# 🔐 सेशन सुरक्षित ठेवण्यासाठी गुप्त की (Secret Key) चेंज करा
app.secret_key = 'hotel-taj-super-secret-key-9876'

# ⚠️ तुमच्या Fast2SMS चा API Key इथे सुरक्षित पेस्ट करा
FAST2SMS_API_KEY = ""

# MySQL कनेक्शन फंक्शन
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="sayali12",  
        database="hotel_db"
    )

# क्यूआर कोड जनरेटर
def generate_qr_base64(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

# २. सुरुवातीचे लॉगिन पेज काढून थेट डॅशबोर्डवर पाठवणे
@app.route('/', methods=['GET', 'POST'])
def login():
    # लॉगिन पेज न दाखवता थेट डॅशबोर्डवर रिडायरेक्ट करणे
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/table/<int:table_id>')
def show_qr(table_id):
    menu_url = request.host_url + f"menu/{table_id}"
    qr_image = generate_qr_base64(menu_url)
    return render_template('qr_page.html', table_id=table_id, menu_url=menu_url, qr_image=qr_image)

# मेनू कार्ड (सर्व डेटा एकत्र लोड करणे - सुरक्षित पद्धत)
@app.route('/menu/<int:table_id>')
def menu(table_id):
    session['table_id'] = table_id
    if 'cart' not in session:
        session['cart'] = {}

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM menu")
    all_items = cursor.fetchall()
    cursor.close()
    db.close()

    clean_cart = {str(k): int(v) for k, v in session['cart'].items()}
    return render_template('menu.html', menu_items=all_items, table_id=table_id, cart=clean_cart)

@app.route('/add_to_cart/<int:item_id>')
def add_to_cart(item_id):
    if 'cart' not in session:
        session['cart'] = {}
    cart = session['cart']
    item_id_str = str(item_id)
    cart[item_id_str] = cart.get(item_id_str, 0) + 1
    session['cart'] = cart
    session.modified = True
    return redirect(f"/menu/{session.get('table_id', 1)}")

@app.route('/cancel_item/<int:item_id>')
def cancel_item(item_id):
    cart = session.get('cart', {})
    item_id_str = str(item_id)
    if item_id_str in cart:
        if cart[item_id_str] > 1:
            cart[item_id_str] -= 1
        else:
            cart.pop(item_id_str, None)
    session['cart'] = cart
    session.modified = True
    return redirect(f"/menu/{session.get('table_id', 1)}")

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    table_id = session.get('table_id', 1)
    cart_items = []
    total = 0

    if cart:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        for item_id_str, qty in cart.items():
            cursor.execute("SELECT * FROM menu WHERE id = %s", (int(item_id_str),))
            item = cursor.fetchone()
            if item:
                item_total = item['price'] * qty
                cart_items.append({
                    'id': item['id'], 'name': item['name'], 'qty': qty,
                    'price': item['price'], 'total': item_total, 'icon': item['icon']
                })
                total += item_total
        cursor.close()
        db.close()
    return render_template('cart.html', cart_items=cart_items, total=total, table_id=table_id)

# 🚀 ऑर्डर सबमिट करणे (SQL Injection सुरक्षित)
@app.route('/place_order', methods=['POST'])
def place_order():
    cart = session.get('cart', {})
    table_no = session.get('table_id', 1)
    if not cart:
        return redirect(url_for('view_cart'))

    customer_name = request.form.get('customer_name', 'Guest').strip()
    mobile = request.form.get('mobile', '').strip()

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    total = 0
    cart_items = []
    for item_id_str, qty in cart.items():
        cursor.execute("SELECT * FROM menu WHERE id = %s", (int(item_id_str),))
        item = cursor.fetchone()
        if item:
            total += item['price'] * qty
            cart_items.append((item['id'], qty, item['price']))

    # %s वापरल्यामुळे SQL Injection चा धोका पूर्णपणे संपतो
    cursor.execute("INSERT INTO orders (table_no, customer_name, mobile, total, status) VALUES (%s, %s, %s, %s, 'Pending')", 
                   (table_no, customer_name, mobile, total))
    order_id = cursor.lastrowid

    for menu_id, quantity, price in cart_items:
        cursor.execute("INSERT INTO order_items (order_id, menu_id, quantity, price) VALUES (%s, %s, %s, %s)", 
                       (order_id, menu_id, quantity, price))

    db.commit()
    cursor.close()
    db.close()
    session.pop('cart', None)
    return render_template('order_success.html', order_id=order_id, total=total, table_no=table_no)

# पीडीएफ बिल डाउनलोड
@app.route('/download_pdf/<int:order_id>')
def download_pdf(order_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    order = cursor.fetchone()
    
    cursor.execute("SELECT oi.*, m.name AS item_name FROM order_items oi JOIN menu m ON oi.menu_id = m.id WHERE oi.order_id = %s", (order_id,))
    items = cursor.fetchall()
    cursor.close()
    db.close()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(100, 750, "HOTEL TAJ DIGITAL BILL")
    p.setFont("Helvetica", 12)
    p.drawString(100, 720, f"Order ID: {order['order_id']}")
    p.drawString(100, 705, f"Table No: {order['table_no']}")
    p.drawString(100, 690, f"Customer: {order['customer_name']}")
    p.drawString(100, 660, "-------------------------------------------------------------")
    y = 630
    for item in items:
        p.drawString(100, y, f"{item['item_name']} x {item['quantity']} = Rs.{item['quantity'] * item['price']}")
        y -= 20
    p.drawString(100, y, "-------------------------------------------------------------")
    p.drawString(100, y-20, f"Grand Total: Rs. {order['total']}")
    p.showPage()
    p.save()
    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    return response

@app.route('/admin')
def admin():
    return render_template('admin_login.html')

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form.get('username')
    password = request.form.get('password')
    # 🔐 व्यावसायिक सिस्टीमसाठी युझरनेम आणि पासवर्ड सुरक्षित तपासणी
    if username == "admin" and password == "1234":
        session['admin'] = True
        return redirect('/chef')
    return "<h2>Wrong Credentials</h2><a href='/admin'>Try Again</a>"

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/admin')

# शेफ डॅशबोर्ड
@app.route('/chef')
def chef():
    if not session.get('admin'):
        return redirect('/admin')

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM orders WHERE status='Pending' ORDER BY order_time DESC")
    pending_orders = cursor.fetchall()
    for order in pending_orders:
        cursor.execute("SELECT oi.*, m.name AS item_name FROM order_items oi JOIN menu m ON oi.menu_id = m.id WHERE oi.order_id=%s", (order['order_id'],))
        order['order_foods'] = cursor.fetchall()

    cursor.execute("SELECT * FROM orders ORDER BY order_time DESC")
    all_history = cursor.fetchall()

    cursor.execute("SELECT IFNULL(SUM(total),0) AS total_sales FROM orders WHERE DATE(order_time)=CURDATE()")
    today_sales = cursor.fetchone()['total_sales']

    cursor.execute("SELECT COUNT(*) AS total_orders FROM orders WHERE DATE(order_time)=CURDATE()")
    total_orders = cursor.fetchone()['total_orders']

    cursor.execute("SELECT m.name, SUM(oi.quantity) AS total_qty, m.icon FROM order_items oi JOIN menu m ON oi.menu_id = m.id GROUP BY oi.menu_id ORDER BY total_qty DESC LIMIT 5")
    most_ordered = cursor.fetchall()

    cursor.close()
    db.close()
    return render_template("chef.html", orders=pending_orders, all_history=all_history, today_sales=today_sales, total_orders=total_orders, most_ordered=most_ordered)

# 🍳 शेफने ऑर्डर स्वीकारल्यावर खरोखरचा SMS पाठवणे
@app.route('/complete_order/<int:order_id>', methods=['POST'])
def complete_order(order_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("UPDATE orders SET status='Completed' WHERE order_id=%s", (order_id,))
    db.commit()
    
    cursor.execute("SELECT * FROM orders WHERE order_id=%s", (order_id,))
    order_data = cursor.fetchone()
    cursor.close()
    db.close()
    
    customer_mobile = order_data['mobile']
    customer_name = order_data['customer_name']
    
    if customer_mobile and len(customer_mobile) == 10:
        message_text = f"Hello {customer_name}, Hotel Taj madhe tumchi Order #{order_id} accept zali ahe ani jevan tayar hot ahe! 🍳"
        url = "https://fast2sms.com"
        payload = {"message": message_text, "language": "english", "route": "q", "numbers": customer_mobile}
        headers = {'authorization': FAST2SMS_API_KEY, 'Content-Type': "application/x-www-form-urlencoded", 'Cache-Control': "no-cache"}
        try:
            response = requests.post(url, data=payload, headers=headers)
            print("Fast2SMS Response:", response.json())
        except Exception as e:
            print("SMS Error:", e)
            return redirect('/chef')
        @app.route('/delete_order/int:order_id', methods=['POST'] )
        def delete_order(order_id):
         if not session.get('admin'):
          return redirect('/admin')
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
        db.commit()
        cursor.close()
        db.close()
        return redirect ('/chef')
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

