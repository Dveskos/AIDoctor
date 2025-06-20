from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_mysqldb import MySQL
import bcrypt
import stripe
import uuid
from datetime import datetime, timedelta
from AIConn import question  # Η συνάρτηση που στέλνει ερώτηση στο AI
from flask_mail import Mail, Message
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="crypt.env")  # Φόρτωσε τις μεταβλητές από το .env

host = os.getenv("HOST")
user = os.getenv("USER")
password = os.getenv("PASSWORD")
database = os.getenv("DATABASE")
mail_user = os.getenv("MAIL_USER")
mail_password = os.getenv("MAIL_PASSWORD")
APPKEY = os.getenv("APPKEY")
skey = os.getenv("STRIPE_SECRET_KEY")


app = Flask(__name__)
app.secret_key = APPKEY  # Το μυστικό κλειδί για τη συνεδρία

# MySQL config
app.config['MYSQL_HOST'] = host
app.config['MYSQL_USER'] = user
app.config['MYSQL_PASSWORD'] = password
app.config['MYSQL_DB'] = database
mysql = MySQL(app)

# Στο app.py, μετά το app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = mail_user
app.config['MAIL_PASSWORD'] = mail_password  # Το 16-ψήφιο app password
app.config['MAIL_DEFAULT_SENDER'] = mail_user

mail = Mail(app)

# Stripe config
stripe.api_key = skey  # Το Stripe Secret Key

CREDIT_PACKAGES = {'10': 0.99, '20': 1.99, '50': 4.99, '100': 9.99, '200': 19.99, '500': 49.99, '1000': 99.99, 'unlimited': 199.99}

# -------- Βοηθητικές Συναρτήσεις --------
def get_user_by_email(email):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    return user

def get_user_by_id(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()
    return user

from datetime import datetime, timedelta

def update_user_credits(user_id, new_credits):
    cur = mysql.connection.cursor()
    if new_credits == 'unlimited':
        expiry = datetime.now() + timedelta(days=30)
        cur.execute("UPDATE users SET credits=%s, unlimited_expiry=%s WHERE id=%s", (new_credits, expiry, user_id))
    else:
        cur.execute("UPDATE users SET credits=%s, unlimited_expiry=NULL WHERE id=%s", (new_credits, user_id))
    mysql.connection.commit()
    cur.close()


def save_question(user_id, question_text, answer_text):
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO questions (user_id, question_text, answer_text) VALUES (%s, %s, %s)",
                (user_id, question_text, answer_text))
    mysql.connection.commit()
    cur.close()

def save_payment(user_id, amount, payment_id, credits_granted, status='pending'):
    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, amount, status, payment_id, credits_granted) VALUES (%s, %s, %s, %s, %s)",
        (user_id, amount, status, payment_id, credits_granted)
    )
    mysql.connection.commit()
    cur.close()

def update_payment_status(payment_id, status):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE payments SET status=%s WHERE payment_id=%s", (status, payment_id))
    mysql.connection.commit()
    cur.close()

def set_forgot_token(email, token, expiry):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET forgot_password_token=%s, forgot_password_expiry=%s WHERE email=%s", (token, expiry, email))
    mysql.connection.commit()
    cur.close()

def reset_password(token, new_hash):
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE users
        SET password_hash=%s, forgot_password_token=NULL, forgot_password_expiry=NULL
        WHERE forgot_password_token=%s
        """, (new_hash, token))
    mysql.connection.commit()
    cur.close()

# -------- Routes --------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (email, password_hash, credits) VALUES (%s, %s, %s)", (email, hashed, '1'))
            mysql.connection.commit()
            msg = 'Registration successful! Please log in.'
        except Exception as e:
            msg = 'Email already exists.'
        cur.close()
        return render_template('register.html', msg=msg)
    return render_template('register.html', msg=msg)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user_by_email(email)
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
            session['user_id'] = user[0]
            session['credits'] = user[5]
            return redirect(url_for('dashboard'))
        else:
            msg = 'Invalid credentials.'
    return render_template('login.html', msg=msg)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = get_user_by_id(session['user_id'])
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM questions WHERE user_id=%s ORDER BY created_at DESC", (session['user_id'],))
    questions = cur.fetchall()
    cur.close()
    unlimited_expiry = user[8]  # ή το σωστό index
    return render_template('dashboard.html', email=user[1], credits=user[5], questions=questions, unlimited_expiry=unlimited_expiry)


@app.route('/ask', methods=['POST'])
def ask():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    question_text = request.form['question_text']
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    credits = user[5]
    unlimited_expiry = user[8]  # Αν το unlimited_expiry είναι το 9ο πεδίο (ξεκινάει από 0)

    # Έλεγχος αν έχει unlimited και αν έχει λήξει
    if credits == 'unlimited':
        if unlimited_expiry and datetime.now() > unlimited_expiry:
            # Έληξε το unlimited, μηδένισε credits
            update_user_credits(user_id, '0')
            credits = '0'
            session['credits'] = '0'

    if credits == '0' or credits == '':
        return render_template('dashboard.html', email=user[1], credits=credits, error="Δεν έχετε διαθέσιμα credits.")

    # Μείωσε credits αν δεν είναι unlimited
    if credits != 'unlimited':
        new_credits = str(int(credits) - 1)
        update_user_credits(user_id, new_credits)
        session['credits'] = new_credits

    # Στείλε την ερώτηση στο AI
    answer = question(question_text)
    save_question(user_id, question_text, answer)
    return render_template('answer.html', answer=answer)


@app.route('/create-payment', methods=['POST'])
def create_payment():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 403
    package = request.json['package']
    if package not in CREDIT_PACKAGES:
        return jsonify({'error': 'Invalid package'}), 400
    price = CREDIT_PACKAGES[package]
    session_stripe = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': f'Πακέτο {package} credits'},
                'unit_amount': int(price * 100),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('dashboard', _external=True),
        metadata={'user_id': session['user_id'], 'package': package}
    )
    # Αποθήκευσε το payment ως pending
    save_payment(session['user_id'], price, session_stripe.id, package)
    return jsonify({'url': session_stripe.url})

@app.route('/payment-success')
def payment_success():
    session_id = request.args.get('session_id')
    if not session_id:
        return "No session id.", 400
    checkout_session = stripe.checkout.Session.retrieve(session_id)
    user_id = checkout_session.metadata['user_id']
    package = checkout_session.metadata['package']
    # Ενημέρωσε credits
    update_user_credits(user_id, package)
    update_payment_status(session_id, 'completed')
    if 'user_id' in session and str(session['user_id']) == str(user_id):
        session['credits'] = package
    return "Πληρωμή επιτυχής! Τα credits προστέθηκαν στον λογαριασμό σας. <a href='/dashboard'>Επιστροφή</a>"

from flask_mail import Message

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    msg = ''
    if request.method == 'POST':
        email = request.form['email']
        user = get_user_by_email(email)
        if user:
            token = str(uuid.uuid4())
            expiry = datetime.now() + timedelta(hours=1)
            set_forgot_token(email, token, expiry)
            reset_link = url_for('reset_password_route', token=token, _external=True)
            try:
                message = Message(
                    subject="Επαναφορά κωδικού AI Γιατρός",
                    recipients=[email],
                    body=f"Πατήστε στον παρακάτω σύνδεσμο για να αλλάξετε τον κωδικό σας:\n{reset_link}\n\nΑν δεν ζητήσατε εσείς επαναφορά, αγνοήστε αυτό το email."
                )
                mail.send(message)
                msg = "Ένα email αποκατάστασης στάλθηκε στη διεύθυνσή σας."
            except Exception as e:
                msg = f"Σφάλμα κατά την αποστολή email: {e}"
        else:
            msg = "Δεν βρέθηκε χρήστης με αυτό το email."
    return render_template('forgot_password.html', msg=msg)


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password_route():
    token = request.args.get('token')
    msg = ''
    if request.method == 'POST':
        new_password = request.form['password']
        new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        reset_password(token, new_hash)
        msg = 'Ο κωδικός άλλαξε επιτυχώς! Μπορείτε να συνδεθείτε.'
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token, msg=msg)

# GDPR - Διαγραφή λογαριασμού
@app.route('/delete-account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    mysql.connection.commit()
    cur.close()
    session.clear()
    return "Ο λογαριασμός σας διαγράφηκε (GDPR)."

@app.route('/delete-question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM questions WHERE id=%s AND user_id=%s", (question_id, user_id))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('dashboard'))

@app.route('/delete-all-questions', methods=['POST'])
def delete_all_questions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM questions WHERE user_id=%s", (user_id,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
