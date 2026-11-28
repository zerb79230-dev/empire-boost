import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sqlite3
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "empire_boost.db")

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                postnom TEXT NOT NULL,
                avenue TEXT NOT NULL,
                phone TEXT NOT NULL,
                tier TEXT DEFAULT 'GRATUIT',
                friends INTEGER DEFAULT 142,
                visits INTEGER DEFAULT 1284,
                tiktok INTEGER DEFAULT 1420,
                instagram INTEGER DEFAULT 980,
                facebook INTEGER DEFAULT 650,
                youtube INTEGER DEFAULT 400
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author TEXT NOT NULL,
                initials TEXT NOT NULL,
                city TEXT DEFAULT 'Kinshasa 🇨🇩',
                tier TEXT DEFAULT 'MEMBRE',
                grad TEXT DEFAULT 'vvip-grad',
                text TEXT NOT NULL,
                banner TEXT DEFAULT '',
                likes INTEGER DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                text TEXT DEFAULT '',
                mine INTEGER DEFAULT 1,
                photo TEXT
            )
            """
        )
        conn.commit()


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "database": os.path.basename(DB_PATH)})


@app.route("/api/posts", methods=["GET", "POST"])
def handle_posts():
    with get_db() as conn:
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            text = (data.get("text") or "").strip()
            if not text:
                return jsonify({"error": "Message vide"}), 400
            author = (data.get("author") or "Kabongo Mbuyi").strip()
            initials = (data.get("initials") or "KM").strip()[:2].upper()
            city = (data.get("city") or "Kinshasa 🇨🇩").strip()
            tier = (data.get("tier") or "MEMBRE").strip()
            grad = (data.get("grad") or "vvip-grad").strip()
            banner = (data.get("banner") or "Nouvelle Publication • Réseau Mondial Empire-Boost").strip()

            cur = conn.execute(
                """
                INSERT INTO posts (author, initials, city, tier, grad, text, banner, likes)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (author, initials, city, tier, grad, text, banner),
            )
            conn.commit()
            return jsonify({"id": cur.lastrowid, "status": "saved"}), 201

        rows = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
        return jsonify([dict(r) for r in rows])


@app.route("/api/messages/<int:chat_id>", methods=["GET", "POST"])
def handle_messages(chat_id):
    with get_db() as conn:
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            text = (data.get("text") or "").strip()
            photo = data.get("photo")
            mine = 1 if data.get("mine", True) else 0
            if not text and not photo:
                return jsonify({"error": "Message vide"}), 400

            cur = conn.execute(
                "INSERT INTO messages (chat_id, text, mine, photo) VALUES (?, ?, ?, ?)",
                (chat_id, text, mine, photo),
            )
            conn.commit()
            return jsonify({"id": cur.lastrowid, "status": "saved"}), 201

        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])

PHONE_REGEX = re.compile(r"^\+[1-9]\d{6,14}$")


def ensure_app_tables():
    init_db()
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE,
                password_hash TEXT,
                provider TEXT NOT NULL DEFAULT 'phone',
                provider_email TEXT,
                trial_ends_at TEXT NOT NULL,
                is_vip INTEGER NOT NULL DEFAULT 0,
                payment_method TEXT,
                vip_expires_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS boost_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                target_url TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES app_accounts (id)
            )
        """)


ensure_app_tables()


def check_access_status(row):
    now = datetime.utcnow()
    if row["is_vip"] and row["vip_expires_at"]:
        if now <= datetime.fromisoformat(row["vip_expires_at"]):
            return {"has_access": True, "plan": "vip", "trial_active": False}
    trial_end = datetime.fromisoformat(row["trial_ends_at"])
    if now <= trial_end:
        return {
            "has_access": True,
            "plan": "trial_3_days",
            "trial_active": True,
            "trial_ends_at": row["trial_ends_at"],
        }
    return {"has_access": False, "plan": "expired", "trial_active": False}


@app.post("/api/auth/register")
def api_auth_register():
    data = request.get_json(force=True) or {}
    provider = (data.get("provider") or "phone").strip().lower()
    now = datetime.utcnow()
    trial_end = (now + timedelta(days=3)).isoformat()

    if provider == "phone":
        phone = (data.get("phone") or "").strip()
        password = data.get("password") or ""
        if not PHONE_REGEX.match(phone):
            return jsonify({"ok": False, "error": "Numéro international invalide (ex: +243..., +33..., +225...)"}), 400
        if len(password) < 6:
            return jsonify({"ok": False, "error": "Mot de passe : 6 caractères minimum"}), 400
        try:
            with get_db() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO app_accounts (phone, password_hash, provider, trial_ends_at, created_at)
                    VALUES (?, ?, 'phone', ?, ?)
                    """,
                    (phone, generate_password_hash(password), trial_end, now.isoformat()),
                )
                account_id = cur.lastrowid
            return jsonify({"ok": True, "account_id": account_id, "trial_days": 3, "trial_ends_at": trial_end}), 201
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "Ce numéro est déjà enregistré"}), 409

    if provider in ("google", "icloud"):
        email = (data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "Adresse e-mail Google ou iCloud requise"}), 400
        with get_db() as conn:
            existing = conn.execute(
                "SELECT * FROM app_accounts WHERE provider_email = ?", (email,)
            ).fetchone()
            if existing:
                return jsonify({"ok": True, "account_id": existing["id"], **check_access_status(existing)}), 200
            cur = conn.execute(
                """
                INSERT INTO app_accounts (provider, provider_email, trial_ends_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (provider, email, trial_end, now.isoformat()),
            )
            account_id = cur.lastrowid
        return jsonify({"ok": True, "account_id": account_id, "trial_days": 3, "trial_ends_at": trial_end}), 201

    return jsonify({"ok": False, "error": "Mode de connexion non supporté"}), 400


@app.post("/api/auth/login")
def api_auth_login():
    data = request.get_json(force=True) or {}
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM app_accounts WHERE phone = ?", (phone,)).fetchone()
    if not row or not row["password_hash"] or not check_password_hash(row["password_hash"], password):
        return jsonify({"ok": False, "error": "Numéro ou mot de passe incorrect"}), 401
    return jsonify({"ok": True, "account_id": row["id"], **check_access_status(row)}), 200


@app.post("/api/subscription/activate")
def api_subscription_activate():
    data = request.get_json(force=True) or {}
    account_id = data.get("account_id")
    method = (data.get("payment_method") or "").strip().lower()
    days = int(data.get("days") or 30)

    if method not in ("mpesa", "airtel", "visa"):
        return jsonify({"ok": False, "error": "Moyen de paiement autorisé : mpesa, airtel ou visa"}), 400
    if not account_id:
        return jsonify({"ok": False, "error": "account_id requis"}), 400

    now = datetime.utcnow()
    vip_end = (now + timedelta(days=days)).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            UPDATE app_accounts
            SET is_vip = 1, payment_method = ?, vip_expires_at = ?
            WHERE id = ?
            """,
            (method, vip_end, account_id),
        )
    return jsonify({"ok": True, "payment_method": method, "vip_expires_at": vip_end}), 200

init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)