from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime, timedelta

app = FastAPI(title="Empire Boost API")

# Initialisation de la base de données
def init_db():
    conn = sqlite3.connect("empire_boost.db")
    cursor = conn.cursor()
    # Table des utilisateurs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'essai',
            expires_at DATETIME
        )
    """)
    # Table pour l'historique des paiements
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_type TEXT,
            amount REAL,
            payment_method TEXT,
            transaction_id TEXT,
            created_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)
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

@app.post("/register")
def register_user(user: UserRegister):
    conn = sqlite3.connect("empire_boost.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, phone, status) VALUES (?, ?, 'essai')", (user.username, user.phone))
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return {"message": "Utilisateur enregistré avec succès", "user_id": user_id}

@app.post("/launch-free-boost")
def launch_free_boost(boost: BoostRequest):
    return {"message": f"Boost {boost.platform} lancé avec succès pour l'utilisateur {boost.user_id} !"}

@app.post("/verify-payment")
def verify_payment(payment: PaymentVerify):
    conn = sqlite3.connect("empire_boost.db")
    cursor = conn.cursor()
    
    prices = {"semaine": 5.0, "mensuel": 15.0, "vip": 20.0}
    days_map = {"semaine": 7, "mensuel": 30, "vip": 30}
    
    amount = prices.get(payment.plan_type, 5.0)
    days = days_map.get(payment.plan_type, 7)
    expires_at = datetime.now() + timedelta(days=days)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        UPDATE users 
        SET status = ?, expires_at = ? 
        WHERE user_id = ?
    """, (f"actif_{payment.plan_type}", expires_at.strftime("%Y-%m-%d %H:%M:%S"), payment.user_id))
    
    cursor.execute("""
        INSERT INTO transactions (user_id, plan_type, amount, payment_method, transaction_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (payment.user_id, payment.plan_type, amount, payment.payment_method, payment.transaction_id, now_str))
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": f"Paiement de {amount}$ validé et enregistré pour le pass {payment.plan_type} !",
        "user_id": payment.user_id,
        "amount": f"{amount}$",
        "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/admin/transactions")
def get_transactions():
    conn = sqlite3.connect("empire_boost.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.tx_id, u.username, t.plan_type, t.amount, t.payment_method, t.transaction_id, t.created_at
        FROM transactions t
        JOIN users u ON t.user_id = u.user_id
        ORDER BY t.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append({
            "tx_id": r[0],
            "username": r[1],
            "plan_type": r[2],
            "amount": f"{r[3]}$",
            "payment_method": r[4],
            "transaction_id": r[5],
            "created_at": r[6]
        })
    return {"total_transactions": len(results), "transactions": results}

@app.get("/")
def read_index():
    return FileResponse("index.html")