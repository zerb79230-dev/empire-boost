import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "empire_boost.db"


def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            password_hash TEXT,
            provider TEXT DEFAULT 'phone',
            provider_email TEXT,
            trial_ends_at TEXT NOT NULL,
            is_vip INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_name TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            amount_usd REAL NOT NULL,
            status TEXT DEFAULT 'active',
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS boost_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            service_type TEXT NOT NULL,
            target_link TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()


def create_user(phone=None, password=None, provider="phone", provider_email=None):
    now = datetime.utcnow()
    trial_end = now + timedelta(days=3)
    pw_hash = generate_password_hash(password) if password else None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (phone, password_hash, provider, provider_email, trial_ends_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (phone, pw_hash, provider, provider_email, trial_end.isoformat(), now.isoformat()))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def verify_phone_login(phone, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    user = cur.fetchone()
    conn.close()
    if user and user["password_hash"] and check_password_hash(user["password_hash"], password):
        return dict(user)
    return None


def has_active_access(user):
    if user.get("is_vip"):
        return True
    try:
        trial_end = datetime.fromisoformat(user["trial_ends_at"])
        return datetime.utcnow() <= trial_end
    except Exception:
        return False


def activate_subscription(user_id, plan_name, payment_method, amount_usd, days=30):
    now = datetime.utcnow()
    expires_at = now + timedelta(days=days)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO subscriptions (user_id, plan_name, payment_method, amount_usd, status, expires_at, created_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?)
    """, (user_id, plan_name, payment_method, amount_usd, expires_at.isoformat(), now.isoformat()))
    cur.execute("UPDATE users SET is_vip = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()