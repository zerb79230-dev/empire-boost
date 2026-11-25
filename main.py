import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Empire Boost Pro API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "empire_boost.db"
ADMIN_PIN = "2026"  # Code PIN administrateur pour valider les paiements


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            identifier TEXT UNIQUE NOT NULL,
            full_name TEXT,
            password TEXT,
            free_trial_used INTEGER DEFAULT 0,
            subscription_status TEXT DEFAULT 'inactive',
            plan_type TEXT,
            subscription_expires_at TEXT,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            objective TEXT NOT NULL,
            video_url TEXT NOT NULL,
            is_free_trial INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Actif',
            views_delivered INTEGER DEFAULT 0,
            likes_delivered INTEGER DEFAULT 0,
            reach_delivered INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_type TEXT NOT NULL,
            amount_usd REAL NOT NULL,
            payment_method TEXT NOT NULL,
            transaction_ref TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


init_db()


class AuthRequest(BaseModel):
    provider: str  # 'google', 'icloud', 'phone'
    identifier: str
    full_name: Optional[str] = ""
    password: Optional[str] = ""


class BoostRequest(BaseModel):
    user_id: int
    platform: str
    objective: str
    video_url: str


class PaymentSubmitRequest(BaseModel):
    user_id: int
    plan_type: str
    payment_method: str
    transaction_ref: str


class AdminActionRequest(BaseModel):
    admin_pin: str
    payment_id: int
    action: str  # 'approve' ou 'reject'


def compute_live_stats(campaign_row):
    created = datetime.fromisoformat(campaign_row["created_at"])
    elapsed_minutes = max(1, int((datetime.utcnow() - created).total_seconds() // 60))
    is_trial = campaign_row["is_free_trial"] == 1

    if is_trial:
        views = min(1250, 140 + elapsed_minutes * 37)
        likes = int(views * 0.14)
        reach = int(views * 1.35)
    else:
        views = min(25000, 850 + elapsed_minutes * 210)
        likes = int(views * 0.18)
        reach = int(views * 1.55)

    return {
        "id": campaign_row["id"],
        "platform": campaign_row["platform"],
        "objective": campaign_row["objective"],
        "video_url": campaign_row["video_url"],
        "is_free_trial": is_trial,
        "status": "En diffusion" if views < (1250 if is_trial else 25000) else "Terminé",
        "views": views,
        "likes": likes,
        "reach": reach,
        "engagement_rate": round((likes / max(1, views)) * 100, 1),
        "created_at": campaign_row["created_at"],
    }


@app.get("/")
def serve_frontend():
    return FileResponse("index.html")


@app.post("/api/auth")
def authenticate(req: AuthRequest):
    identifier = req.identifier.strip().lower()
    provider = req.provider.strip().lower()
    full_name = (req.full_name or "").strip()
    password = (req.password or "").strip()

    if not identifier:
        raise HTTPException(status_code=400, detail="Identifiant obligatoire.")

    if provider in ("google", "icloud"):
        if "@" not in identifier or "." not in identifier:
            raise HTTPException(status_code=400, detail="Veuillez saisir une adresse e-mail valide.")
        if not full_name:
            raise HTTPException(status_code=400, detail="Veuillez entrer votre nom complet.")
    elif provider == "phone":
        if not identifier.startswith("+") or len(identifier) < 8:
            raise HTTPException(status_code=400, detail="Numéro international invalide (ex: +243...).")
        if len(password) < 4:
            raise HTTPException(status_code=400, detail="Mot de passe requis (4 caractères minimum).")
    else:
        raise HTTPException(status_code=400, detail="Méthode de connexion non reconnue.")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE identifier = ?", (identifier,))
    user = cur.fetchone()

    if user:
        if provider == "phone" and user["password"] and user["password"] != password:
            conn.close()
            raise HTTPException(status_code=401, detail="Mot de passe incorrect pour ce numéro.")
        user_id = user["id"]
    else:
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO users (provider, identifier, full_name, password, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (provider, identifier, full_name or identifier, password, now),
        )
        conn.commit()
        user_id = cur.lastrowid

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    fresh_user = dict(cur.fetchone())
    fresh_user.pop("password", None)
    conn.close()
    return {"user": fresh_user}


@app.get("/api/user/{user_id}")
def get_user_state(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    cur.execute("SELECT * FROM campaigns WHERE user_id = ? ORDER BY id DESC", (user_id,))
    campaigns = [compute_live_stats(row) for row in cur.fetchall()]

    cur.execute("SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC", (user_id,))
    payments = [dict(row) for row in cur.fetchall()]

    user_dict = dict(user)
    user_dict.pop("password", None)
    conn.close()
    return {
        "user": user_dict,
        "campaigns": campaigns,
        "payments": payments,
    }


@app.post("/api/boost")
def launch_boost(req: BoostRequest):
    url = req.video_url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Veuillez coller un lien vidéo valide (https://...).")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (req.user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    is_subscribed = user["subscription_status"] == "active"
    trial_used = user["free_trial_used"] == 1

    if not is_subscribed and trial_used:
        conn.close()
        raise HTTPException(
            status_code=403,
            detail="Votre essai gratuit d'1 vidéo est déjà utilisé. Passez à un abonnement validé pour continuer.",
        )

    is_free_trial = 0 if is_subscribed else 1
    now = datetime.utcnow().isoformat()

    cur.execute(
        """
        INSERT INTO campaigns (user_id, platform, objective, video_url, is_free_trial, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (req.user_id, req.platform, req.objective, url, is_free_trial, now),
    )

    if is_free_trial == 1:
        cur.execute("UPDATE users SET free_trial_used = 1 WHERE id = ?", (req.user_id,))

    conn.commit()
    campaign_id = cur.lastrowid
    cur.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    new_campaign = compute_live_stats(cur.fetchone())
    conn.close()

    return {
        "message": "Campagne lancée avec succès ! Vos statistiques sont disponibles en direct.",
        "campaign": new_campaign,
    }


@app.post("/api/subscribe")
def submit_subscription(req: PaymentSubmitRequest):
    ref = req.transaction_ref.strip()
    if len(ref) < 6:
        raise HTTPException(status_code=400, detail="Référence de transaction invalide ou trop courte.")

    amount = 5.0 if "Semaine" in req.plan_type else 15.0

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (req.user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT INTO payments (user_id, plan_type, amount_usd, payment_method, transaction_ref, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """,
        (req.user_id, req.plan_type, amount, req.payment_method, ref, now),
    )
    cur.execute("UPDATE users SET subscription_status = 'pending' WHERE id = ?", (req.user_id,))
    conn.commit()
    conn.close()

    return {
        "status": "pending",
        "message": f"Demande enregistrée (Réf: {ref}). Votre paiement {req.payment_method} est en attente de vérification par l'administrateur.",
    }


@app.get("/api/admin/payments")
def list_payments(admin_pin: str):
    if admin_pin != ADMIN_PIN:
        raise HTTPException(status_code=401, detail="Code PIN administrateur incorrect.")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, u.identifier, u.full_name
        FROM payments p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.id DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"payments": rows}


@app.post("/api/admin/review")
def review_payment(req: AdminActionRequest):
    if req.admin_pin != ADMIN_PIN:
        raise HTTPException(status_code=401, detail="Code PIN administrateur incorrect.")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payments WHERE id = ?", (req.payment_id,))
    payment = cur.fetchone()
    if not payment:
        conn.close()
        raise HTTPException(status_code=404, detail="Paiement introuvable.")

    now = datetime.utcnow().isoformat()
    if req.action == "approve":
        days = 7 if "Semaine" in payment["plan_type"] else 30
        expires = (datetime.utcnow() + timedelta(days=days)).isoformat()
        cur.execute(
            "UPDATE payments SET status = 'approved', reviewed_at = ? WHERE id = ?",
            (now, req.payment_id),
        )
        cur.execute(
            """
            UPDATE users
            SET subscription_status = 'active', plan_type = ?, subscription_expires_at = ?
            WHERE id = ?
            """,
            (payment["plan_type"], expires, payment["user_id"]),
        )
        msg = "Paiement approuvé et abonnement activé."
    else:
        cur.execute(
            "UPDATE payments SET status = 'rejected', reviewed_at = ? WHERE id = ?",
            (now, req.payment_id),
        )
        cur.execute(
            "UPDATE users SET subscription_status = 'rejected' WHERE id = ?",
            (payment["user_id"],),
        )
        msg = "Paiement rejeté."

    conn.commit()
    conn.close()
    return {"message": msg}