import re
from flask import Blueprint, request, jsonify, session
from database import create_user, verify_phone_login, get_conn, has_active_access, activate_subscription

auth_bp = Blueprint("auth_bp", __name__)

PHONE_REGEX = re.compile(r"^\+[1-9]\d{6,14}$")


@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    provider = data.get("provider", "phone")

    if provider == "phone":
        phone = (data.get("phone") or "").strip()
        password = data.get("password") or ""
        if not PHONE_REGEX.match(phone):
            return jsonify({"error": "Numéro international invalide (ex: +243..., +33..., +1...)"}), 400
        if len(password) < 6:
            return jsonify({"error": "Mot de passe : 6 caractères minimum"}), 400
        try:
            user_id = create_user(phone=phone, password=password, provider="phone")
            session["user_id"] = user_id
            return jsonify({"message": "Compte créé avec 3 jours d'essai gratuit", "user_id": user_id}), 201
        except Exception:
            return jsonify({"error": "Ce numéro existe déjà"}), 409

    if provider in ("google", "icloud"):
        email = (data.get("email") or "").strip().lower()
        if not email:
            return jsonify({"error": "Adresse e-mail requise"}), 400
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE provider_email = ?", (email,))
        existing = cur.fetchone()
        conn.close()
        if existing:
            session["user_id"] = existing["id"]
            return jsonify({"message": f"Connexion {provider} réussie", "user_id": existing["id"]}), 200
        user_id = create_user(provider=provider, provider_email=email)
        session["user_id"] = user_id
        return jsonify({"message": f"Compte {provider} créé (3 jours d'essai)", "user_id": user_id}), 201

    return jsonify({"error": "Méthode non prise en charge"}), 400


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""
    user = verify_phone_login(phone, password)
    if not user:
        return jsonify({"error": "Identifiants incorrects"}), 401
    session["user_id"] = user["id"]
    return jsonify({
        "message": "Connexion réussie",
        "user_id": user["id"],
        "access_active": has_active_access(user),
        "is_vip": bool(user["is_vip"])
    }), 200


@auth_bp.route("/api/subscribe", methods=["POST"])
def subscribe():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Connexion requise"}), 401

    data = request.get_json(force=True)
    method = (data.get("payment_method") or "").lower()
    plan_name = data.get("plan_name") or "Abonnement VIP"
    amount_usd = float(data.get("amount_usd") or 9.0)

    if method not in ("mpesa", "airtel", "visa"):
        return jsonify({"error": "Choisis M-Pesa, Airtel Money ou Carte Visa"}), 400

    activate_subscription(user_id, plan_name, method, amount_usd)
    return jsonify({"message": f"Abonnement activé via {method.upper()}"}), 200