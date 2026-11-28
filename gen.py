code_html = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Empire Boost - Panel</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0f172a; color: #fff; padding: 20px; max-width: 500px; margin: auto; }
        .card { background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 15px; }
        input, select { width: 100%; padding: 10px; margin: 8px 0; background: #0f172a; border: 1px solid #475569; color: #fff; border-radius: 5px; }
        button { width: 100%; padding: 10px; background: #e11d48; color: #fff; border: none; font-weight: bold; border-radius: 5px; cursor: pointer; }
        button:hover { background: #be123c; }
        pre { background: #0f172a; padding: 10px; border-radius: 5px; overflow-x: auto; font-size: 12px; }
    </style>
</head>
<body>
    <h1>🏴‍☠️ Empire Boost</h1>
    <div class="card">
        <h3>1. Inscription (3 jours d'essai)</h3>
        <input type="text" id="reg-username" placeholder="Nom d'utilisateur">
        <input type="text" id="reg-phone" placeholder="Numéro de téléphone">
        <button onclick="registerUser()">S'inscrire</button>
    </div>
    <div class="card">
        <h3>2. Lancer un Boost</h3>
        <input type="number" id="boost-userid" placeholder="ID Utilisateur">
        <select id="boost-platform">
            <option value="TikTok">TikTok</option>
            <option value="Instagram">Instagram</option>
            <option value="Facebook">Facebook</option>
        </select>
        <input type="text" id="boost-url" placeholder="Lien de la vidéo">
        <button onclick="launchBoost()">Lancer le Boost</button>
    </div>
    <div class="card">
        <h3>3. Valider un Abonnement (5$, 15$, 20$)</h3>
        <input type="number" id="pay-userid" placeholder="ID Utilisateur">
        <select id="pay-plan">
            <option value="semaine">Pass Semaine (5 USD - 7j)</option>
            <option value="mensuel">Pass Mensuel (15 USD - 30j)</option>
            <option value="vip">Pass VIP (20 USD - 30j)</option>
        </select>
        <input type="text" id="pay-method" placeholder="Méthode (M-Pesa / Airtel)">
        <input type="text" id="pay-txid" placeholder="ID de Transaction">
        <button onclick="verifyPayment()">Valider le Paiement</button>
    </div>
    <div class="card">
        <h3>Console / Réponse :</h3>
        <pre id="output">En attente d'action...</pre>
    </div>
    <script>
        const API_URL = "http://127.0.0.1:8000";
        async function registerUser() {
            const username = document.getElementById('reg-username').value;
            const phone = document.getElementById('reg-phone').value;
            const res = await fetch(`${API_URL}/register`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username, phone})
            });
            const data = await res.json();
            document.getElementById('output').innerText = JSON.stringify(data, null, 2);
            if(data.user_id) { alert(`Inscription réussie ! Ton ID est : ${data.user_id}`); }
        }
        async function launchBoost() {
            const user_id = parseInt(document.getElementById('boost-userid').value);
            const platform = document.getElementById('boost-platform').value;
            const video_url = document.getElementById('boost-url').value;
            const res = await fetch(`${API_URL}/launch-free-boost`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id, platform, video_url})
            });
            const data = await res.json();
            document.getElementById('output').innerText = JSON.stringify(data, null, 2);
        }
        async function verifyPayment() {
            const user_id = parseInt(document.getElementById('pay-userid').value);
            const plan_type = document.getElementById('pay-plan').value;
            const payment_method = document.getElementById('pay-method').value;
            const transaction_id = document.getElementById('pay-txid').value;
            const res = await fetch(`${API_URL}/verify-payment`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id, plan_type, payment_method, transaction_id})
            });
            const data = await res.json();
            document.getElementById('output').innerText = JSON.stringify(data, null, 2);
        }
    </script>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(code_html)

print("Fichier index.html généré avec succès !")