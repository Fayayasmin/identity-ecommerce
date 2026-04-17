from flask import Flask, render_template, request, redirect, session
import sqlite3, random, smtplib, os
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "secretkey"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- EMAIL CONFIG ----------------
EMAIL = "identityecommerce@gmail.com"
APP_PASSWORD = "cisugujynvwnoxfz"

def send_otp(receiver_email, otp):
    try:
        msg = MIMEText(f"Your OTP is: {otp}")
        msg['Subject'] = "OTP Verification"
        msg['From'] = EMAIL
        msg['To'] = receiver_email

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()

        print("OTP SENT:", otp)

    except Exception as e:
        print("EMAIL ERROR:", e)

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE,
        email TEXT,
        password TEXT,
        role TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price INTEGER,
        image TEXT,
        seller_id TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        total INTEGER
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ----------------
@app.route('/')
def home():
    return redirect('/login')

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        session['temp_user'] = {
            "user_id": request.form['user_id'],
            "email": request.form['email'],
            "password": generate_password_hash(request.form['password']),
            "role": request.form['role']
        }

        otp = str(random.randint(1000, 9999))
        session['otp'] = otp

        send_otp(session['temp_user']['email'], otp)

        return redirect('/verify_register')

    return render_template("register.html")

# ---------------- VERIFY REGISTER ----------------
@app.route('/verify_register', methods=['GET', 'POST'])
def verify_register():
    if request.method == 'POST':

        if request.form['otp'] == session.get('otp'):

            user = session.get('temp_user')

            conn = get_db()
            cursor = conn.cursor()

            try:
                cursor.execute(
                    "INSERT INTO users (user_id, email, password, role) VALUES (?, ?, ?, ?)",
                    (user['user_id'], user['email'], user['password'], user['role'])
                )
                conn.commit()
            except:
                return "User already exists"

            conn.close()

            session.pop('otp', None)
            session.pop('temp_user', None)

            return redirect('/login')

        return "Invalid OTP"

    return render_template("verify.html")

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        user_id = request.form['user_id']
        password = request.form['password']
        role = request.form['role']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):

            if role != user["role"]:
                return "Role mismatch"

            session['user_id'] = user["user_id"]
            session['role'] = user["role"]
            session['email'] = user["email"]

            otp = str(random.randint(1000, 9999))
            session['otp'] = otp

            send_otp(user["email"], otp)

            return redirect('/verify')

        return "Invalid login"

    return render_template("login.html")

# ---------------- VERIFY LOGIN ----------------
@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':

        if request.form['otp'] == session.get('otp'):

            role = session.get('role')
            session.pop('otp', None)

            if role == "admin":
                return redirect('/admin')
            elif role == "seller":
                return redirect('/seller')
            else:
                return redirect('/dashboard')

        return "Wrong OTP"

    return render_template("verify.html")

# ---------------- USER DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if session.get('role') != "user":
        return redirect('/login')

    category = request.args.get('category')

    conn = get_db()
    cursor = conn.cursor()

    if category:
        cursor.execute("SELECT * FROM products WHERE name LIKE ?", (f"%{category}%",))
    else:
        cursor.execute("SELECT * FROM products")

    products = cursor.fetchall()
    conn.close()

    return render_template("dashboard.html", products=products)

# ---------------- ADD TO CART ----------------
@app.route('/add_to_cart/<int:pid>')
def add_to_cart(pid):
    if 'cart' not in session:
        session['cart'] = []

    session['cart'].append(pid)
    session.modified = True

    return redirect('/cart')

# ---------------- CART ----------------
@app.route('/cart')
def cart():

    conn = get_db()
    cursor = conn.cursor()

    products = []
    total = 0

    if 'cart' in session:
        for pid in session['cart']:
            cursor.execute("SELECT * FROM products WHERE id=?", (pid,))
            item = cursor.fetchone()
            if item:
                products.append(item)
                total += item["price"]

    conn.close()

    return render_template("cart.html", products=products, total=total)

# ---------------- BUY ----------------
@app.route('/buy')
def buy():
    if 'cart' not in session or len(session['cart']) == 0:
        return "Cart is empty"

    return render_template("payment.html")

# ---------------- PAYMENT ----------------
@app.route('/payment', methods=['POST'])
def payment():

    conn = get_db()
    cursor = conn.cursor()

    total = 0

    if 'cart' in session:
        for pid in session['cart']:
            cursor.execute("SELECT * FROM products WHERE id=?", (pid,))
            item = cursor.fetchone()
            if item:
                total += item["price"]

    cursor.execute(
        "INSERT INTO orders (user_id, total) VALUES (?, ?)",
        (session['user_id'], total)
    )

    conn.commit()
    conn.close()

    session.pop('cart', None)

    return redirect('/orders')

# ---------------- ORDERS ----------------
@app.route('/orders')
def orders():
    if session.get('role') != "user":
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE user_id=?", (session['user_id'],))
    orders = cursor.fetchall()

    conn.close()

    return render_template("orders.html", orders=orders)

# ---------------- SELLER ----------------
@app.route('/seller')
def seller():
    if session.get('role') != "seller":
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products WHERE seller_id=?", (session['user_id'],))
    products = cursor.fetchall()

    conn.close()

    return render_template("seller.html", products=products)

# ---------------- ADD PRODUCT ----------------
@app.route('/add_product', methods=['POST'])
def add_product():
    if session.get('role') != "seller":
        return redirect('/login')

    name = request.form['name']
    price = request.form['price']
    image = request.files['image']

    if image.filename == "":
        return "No file selected"

    filename = image.filename
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    image.save(path)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO products (name, price, image, seller_id) VALUES (?, ?, ?, ?)",
        (name, price, filename, session['user_id'])
    )

    conn.commit()
    conn.close()

    return redirect('/seller')

# ---------------- ADMIN ----------------
@app.route('/admin')
def admin():
    if session.get('role') != "admin":
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    conn.close()

    return render_template("admin.html", users=users)

# ---------------- DELETE USER ----------------
@app.route('/delete_user/<int:id>')
def delete_user(id):
    if session.get('role') != "admin":
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/admin')

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)