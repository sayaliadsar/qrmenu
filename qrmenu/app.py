from flask import Flask, render_template, request, redirect, url_for, session
import qrcode
import io
import base64
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'hotel-secret-123'  # must aahe

ALL_ORDERS = {}

MENU_ITEMS = [
    {'id': 1, 'name': 'Vadapav', 'price': 20, 'category': 'veg', 'icon': ''},
    {'id': 2, 'name': 'Misal Pav', 'price': 50, 'category': 'veg', 'icon': ''},
    {'id': 3, 'name': 'Paneer Tikka', 'price': 120, 'category': 'veg', 'icon': '🧀'},
    {'id': 4, 'name': 'Veg Biryani', 'price': 100, 'category': 'veg', 'icon': ''},
    {'id': 5, 'name': 'Samosa', 'price': 15, 'category': 'veg', 'icon': '🥟'}
    {'id': 6, 'name': 'Margherita Pizza', 'price': 299, 'category': 'veg', 'icon': '🍕'},
    {'id': 8, 'name': 'Masala Dosa', 'price': 140, 'category': 'veg', 'icon': '🥞'},
    {'id': 9, 'name': 'Veg Thali', 'price': 250, 'category': 'veg', 'icon': '🍽️'}
    {'id': 10, 'name': 'Chicken Biryani', 'price': 150, 'category': 'non-veg', 'icon': ''},
    {'id': 11, 'name': 'Mutton Curry', 'price': 200, 'category': 'non-veg', 'icon': ''},
    {'id': 12, 'name': 'Egg Roll', 'price': 60, 'category': 'non-veg', 'icon': ''},
    {'id': 13, 'name': 'Fish Fry', 'price': 180, 'category': 'non-veg', 'icon': ''},
    {'id': 14, 'name': 'Chicken 65', 'price': 130, 'category': 'non-veg', 'icon': ''},
]

def generate_qr_base64(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/table/<int:table_id>')
def show_qr(table_id):
    menu_url = request.host_url + f"menu/{table_id}"
    qr_image = generate_qr_base64(menu_url)
    return render_template('qr_page.html', table_id=table_id, menu_url=menu_url, qr_image=qr_image)

@app.route('/menu/<int:table_id>')
def menu(table_id):
    session['table_id'] = table_id
    if 'cart' not in session:
        session['cart'] = {}
    return render_template('menu.html', menu_items=MENU_ITEMS, table_id=table_id, cart=session['cart'])

@app.route('/add_to_cart/<int:item_id>')
def add_to_cart(item_id):
    cart = session.get('cart', {})
    item_id_str = str(item_id)
    
    # Add item
    if item_id_str in cart:
        cart[item_id_str] += 1
    else:
        cart[item_id_str] = 1
    
    session['cart'] = cart
    session.modified = True  # he line must aahe
    
    table_id = session.get('table_id', 1)
    return redirect(url_for('menu', table_id=table_id))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    table_id = session.get('table_id', 1)
    cart_items = []
    total = 0
    for item_id_str, qty in cart.items():
        item = next((i for i in MENU_ITEMS if i['id'] == int(item_id_str)), None)
        if item:
            item_total = item['price'] * qty
            cart_items.append({'name': item['name'], 'qty': qty, 'price': item['price'], 'total': item_total, 'icon': item['icon'], 'category': item['category']})
            total += item_total
    return render_template('cart.html', cart_items=cart_items, total=total, table_id=table_id)

@app.route('/place_order')
def place_order():
    global ALL_ORDERS
    table_id = session.get('table_id', 1)
    cart = session.get('cart', {})
    
    if not cart:
        return f"<h1>Cart Rikama Aahe!</h1><a href='/menu/{table_id}'>Menu var ja</a>"
    
    total = 0
    order_items = []
    for item_id_str, qty in cart.items():
        item = next((i for i in MENU_ITEMS if i['id'] == int(item_id_str)), None)
        if item:
            order_items.append({'name': item['name'], 'qty': qty, 'price': item['price'], 'icon': item['icon'], 'category': item['category']})
            total += item['price'] * qty
    
    if table_id not in ALL_ORDERS:
        ALL_ORDERS[table_id] = []
    ALL_ORDERS[table_id].append({
        'items': order_items,
        'total': total,
        'time': datetime.now().strftime("%H:%M:%S")
    })
    
    session['cart'] = {}
    session.modified = True
    return render_template('order_success.html', table_id=table_id, total=total)

@app.route('/chef')
def chef():
    return render_template('chef.html', orders=ALL_ORDERS)
@app.route('/cancel_item/<int:item_id>')
def cancel_item(item_id):

    cart = session.get('cart', {})
    print("Item ID:", item_id)
    print("Cart Before:", cart)

    item_id_str = str(item_id)

    if item_id_str in cart:
        del cart[item_id_str]

    session['cart'] = cart
    session.modified = True

    print("Cart After:", cart)

    return redirect('/cart')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000, use_reloader=False)


