import sqlite3
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Empire Boost API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "empire_boost.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'essai',
            free_boost_used INTEGER DEFAULT 0,
            expires_at DATETIME
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS free_boosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            video_url TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_type TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            transaction_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cols = [row["name"] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]
    if "free_boost_used" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN free_boost_used INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


init_db()


class UserRegister(BaseModel):
    username: str
    phone: str


class BoostRequest(BaseModel):
    user_id: int
    platform: str
    video_url: str


class PaymentVerify(BaseModel):
    user_id: int
    plan_type: str
    payment_method: str
    transaction_id: str


@app.get("/")
def serve_index():
    return FileResponse("index.html")


@app.post("/register")
def register_user(user: UserRegister):
    conn = get_db()
    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT user_id, status, free_boost_used FROM users WHERE phone = ?",
        (user.phone,),
    ).fetchone()

    if existing:
        conn.close()
        return {
            "message": "Utilisateur connecté avec succès",
            "user_id": existing["user_id"],
            "status": existing["status"],
            "free_boost_used": bool(existing["free_boost_used"]),
        }

    expires_at = (datetime.utcnow() + timedelta(days=3)).isoformat()
    cursor.execute(
        "INSERT INTO users (username, phone, status, free_boost_used, expires_at) VALUES (?, ?, 'essai', 0, ?)",
        (user.username, user.phone, expires_at),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return {
        "message": "Utilisateur enregistré avec succès",
        "user_id": user_id,
        "status": "essai",
        "free_boost_used": False,
    }


@app.post("/launch-free-boost")
def launch_free_boost(boost: BoostRequest):
    conn = get_db()
    cursor = conn.cursor()

    user = cursor.execute(
        "SELECT user_id, status, free_boost_used FROM users WHERE user_id = ?",
        (boost.user_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user["free_boost_used"] == 1 and user["status"] != "actif":
        conn.close()
        raise HTTPException(
            status_code=403,
            detail="Limite d'essai atteinte : 1 seule vidéo gratuite autorisée. Passez à l'abonnement.",
        )

    cursor.execute(
        "INSERT INTO free_boosts (user_id, platform, video_url) VALUES (?, ?, ?)",
        (boost.user_id, boost.platform, boost.video_url),
    )

    if user["status"] != "actif":
        cursor.execute(
            "UPDATE users SET free_boost_used = 1 WHERE user_id = ?",
            (boost.user_id,),
        )

    conn.commit()
    conn.close()

    return {
        "message": f"Boost {boost.platform} lancé avec succès pour l'utilisateur {boost.user_id} !"
    }


@app.post("/verify-payment")
def verify_payment(payment: PaymentVerify):
    conn = get_db()
    cursor = conn.cursor()

    user = cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (payment.user_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    days = 30 if "30" in payment.plan_type or "Mois" in payment.plan_type else 7
    expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()

    cursor.execute(
        "INSERT INTO payments (user_id, plan_type, payment_method, transaction_id) VALUES (?, ?, ?, ?)",
        (payment.user_id, payment.plan_type, payment.payment_method, payment.transaction_id),
    )
    cursor.execute(
        "UPDATE users SET status = 'actif', expires_at = ? WHERE user_id = ?",
        (expires_at, payment.user_id),
    )
    conn.commit()
    conn.close()

    return {
        "message": f"Abonnement ({payment.plan_type}) validé via {payment.payment_method} pour l'utilisateur {payment.user_id} !"
    }