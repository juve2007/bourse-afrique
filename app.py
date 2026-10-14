"""
Serveur du site "Bourses Afrique" — version avec comptes et abonnement.

Authentification (session cookie Flask, mot de passe haché) :
- GET  /inscription, POST /inscription   -> créer un compte, puis atterrir sur les bourses
- GET  /connexion,  POST /connexion      -> se connecter
- POST /deconnexion                      -> fermer la session
- GET  /                                 -> le site (redirigé vers /connexion si non connecté)

API (toute privée, sauf le webhook) :
- GET  /api/me               -> compte connecté + état de l'abonnement + bourses débloquées
- GET  /api/scholarships     -> JSON des bourses actives (connecté uniquement)
- GET  /api/config           -> configuration publique pour les widgets KKiaPay
- POST /api/subscribe/verify -> vérifie le paiement d'abonnement côté serveur,
                                puis active l'accès complet 30 jours
- POST /api/unlock/verify    -> vérifie le paiement à l'unité (500 FCFA) d'UNE bourse
- GET  /api/unlock/check     -> liste des bourses débloquées par le compte
- POST /api/unlock/webhook   -> notification KKiaPay (filet de sécurité)

Lancer avec : python app.py (en local) ou gunicorn app:app (en production,
comme sur Render — voir render.yaml).
"""
import os
import secrets
import threading
import time
from functools import wraps


def _load_dotenv(path=None):
    """Charge un fichier .env simple (VAR=valeur par ligne) dans os.environ,
    sans écraser ce qui est déjà défini. Aucune dépendance externe ; si
    python-dotenv est installé, il fait le travail à notre place."""
    try:
        from dotenv import load_dotenv as _ldn
        _ldn(path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        return
    except ImportError:
        pass
    env_path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


_load_dotenv()

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
)

from models import (
    init_db,
    get_active_scholarships,
    get_active_subscription,
    get_unlocked_scholarship_ids,
    create_user,
    get_user_by_id,
    get_user_by_email,
    verify_user_password,
    create_pending_subscription,
    activate_subscription,
    create_pending_unlock,
    mark_unlock_paid,
    SUBSCRIPTION_DAYS,
)
from payments.kkiapay_client import (
    verify_transaction,
    webhook_secret_is_valid,
    _is_sandbox,
)


def _load_secret_key():
    """Clé de signature des cookies de session : variable d'environnement si
    fournie, sinon clé aléatoire persistée à côté de la base (pour que les
    sessions survivent aux redémarrages)."""
    env_key = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if env_key:
        return env_key
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".flask_secret")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    return key


app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = _load_secret_key()
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# À passer à "true" une fois le site servi en HTTPS en production :
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower() == "true"
)

# Au démarrage (y compris sous gunicorn, qui importe app:app sans jamais
# exécuter le bloc __main__) : on crée les tables si besoin et on amorce la
# base avec les bourses vérifiées si elle est vide (premier lancement sur un
# serveur neuf, disque vierge).
init_db()
from seed_data import seed_if_empty

if seed_if_empty():
    print("[app] base vide : bourses de depart inserees")


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def login_required(fn):
    """Toute la maison est privée : sans session valide, le site renvoie vers
    /connexion (ou 401 pour les appels API du front)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "connexion requise"}), 401
            return redirect("/connexion")
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Pages d'authentification
# ---------------------------------------------------------------------------

@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    if session.get("user_id"):
        return redirect("/")
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not name or not email or not password:
            error = "Tous les champs sont obligatoires."
        elif len(password) < 6:
            error = "Le mot de passe doit faire au moins 6 caractères."
        else:
            try:
                user = create_user(name, email, password)
            except ValueError:
                error = "Un compte existe déjà avec cet email."
            else:
                session.clear()
                session["user_id"] = user["id"]
                return redirect("/")
    return render_template("inscription.html", error=error)


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if session.get("user_id"):
        return redirect("/")
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_email(email)
        if user and verify_user_password(user, password):
            session.clear()
            session["user_id"] = user["id"]
            next_url = request.args.get("next", "")
            # On ne redirige que vers un chemin local, jamais vers un site externe.
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect("/")
        error = "Email ou mot de passe incorrect."
    return render_template("connexion.html", error=error)


@app.route("/deconnexion", methods=["POST"])
def deconnexion():
    session.clear()
    return redirect("/connexion")


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    return send_from_directory(app.static_folder, "bourses-afrique.html")


@app.route("/api/me")
@login_required
def api_me():
    user = current_user()
    subscription = get_active_subscription(user["id"])
    return jsonify({
        "user": {"name": user["name"], "email": user["email"]},
        "subscription": {
            "active": subscription is not None,
            "expires_at": subscription["expires_at"] if subscription else None,
        },
        "unlocked_ids": get_unlocked_scholarship_ids(user["id"]),
        "subscription_days": SUBSCRIPTION_DAYS,
    })


@app.route("/api/scholarships")
@login_required
def api_scholarships():
    return jsonify(get_active_scholarships())


@app.route("/api/config")
@login_required
def api_config():
    """Tout ce dont les widgets KKiaPay ont besoin côté navigateur. La clé
    publique est faite pour être exposée — jamais la clé privée ni le secret."""
    return jsonify({
        "kkiapay_public_key": os.environ.get("KKIAPAY_PUBLIC_KEY", ""),
        "kkiapay_sandbox": _is_sandbox(),
        "unlock_amount": int(os.environ.get("UNLOCK_AMOUNT_FCFA", "500")),
        "subscription_amount": int(os.environ.get("SUBSCRIPTION_AMOUNT_FCFA", "2500")),
    })


# ---------------------------------------------------------------------------
# Abonnement (accès complet 30 jours)
# ---------------------------------------------------------------------------

@app.route("/api/subscribe/verify", methods=["POST"])
@login_required
def api_subscribe_verify():
    """
    Appelé par le site juste après que le widget KKiaPay a signalé un
    paiement réussi côté navigateur. On ne fait confiance qu'à ce que KKiaPay
    nous répond ici, jamais à l'évènement du navigateur seul. Le paiement
    est ensuite crédité sur le compte connecté pour 30 jours.
    """
    data = request.get_json(silent=True) or {}
    transaction_id = data.get("transactionId")
    if not transaction_id:
        return jsonify({"ok": False, "error": "transactionId manquant"}), 400

    user = current_user()
    expected_amount = int(os.environ.get("SUBSCRIPTION_AMOUNT_FCFA", "2500"))
    create_pending_subscription(transaction_id, user["id"], expected_amount)

    try:
        transaction = verify_transaction(transaction_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"vérification impossible : {e}"}), 502

    status = (transaction or {}).get("status")
    if status == "SUCCESS":
        paid_amount = (transaction or {}).get("amount")
        try:
            if paid_amount is not None and int(paid_amount) < expected_amount:
                return jsonify({"ok": False, "error": "montant payé insuffisant"}), 402
        except (TypeError, ValueError):
            pass  # KKiaPay n'a pas renvoyé de montant lisible : on fait confiance au statut
        expires_at = activate_subscription(transaction_id)
        return jsonify({"ok": True, "expires_at": expires_at})

    return jsonify({"ok": False, "status": status or "INCONNU"})


# ---------------------------------------------------------------------------
# Déblocage à l'unité (une bourse, 500 FCFA)
# ---------------------------------------------------------------------------

@app.route("/api/unlock/verify", methods=["POST"])
@login_required
def api_unlock_verify():
    """
    Même principe que l'abonnement, mais pour débloquer UNE bourse précise
    et la rattacher au compte connecté.
    """
    data = request.get_json(silent=True) or {}
    transaction_id = data.get("transactionId")
    scholarship_id = data.get("scholarshipId")
    if not transaction_id or not scholarship_id:
        return jsonify({"ok": False, "error": "transactionId ou scholarshipId manquant"}), 400

    user = current_user()
    create_pending_unlock(transaction_id, user["id"], scholarship_id)

    try:
        transaction = verify_transaction(transaction_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"vérification impossible : {e}"}), 502

    status = (transaction or {}).get("status")
    if status == "SUCCESS":
        mark_unlock_paid(transaction_id)
        return jsonify({"ok": True, "unlocked_ids": get_unlocked_scholarship_ids(user["id"])})

    return jsonify({"ok": False, "status": status or "INCONNU"})


@app.route("/api/unlock/check")
@login_required
def api_unlock_check():
    return jsonify({"unlocked_ids": get_unlocked_scholarship_ids(current_user()["id"])})


@app.route("/api/unlock/webhook", methods=["POST"])
def api_unlock_webhook():
    """
    Filet de sécurité : si l'étudiant ferme l'onglet juste après avoir payé
    (avant que les routes /verify n'aient le temps de répondre), ce webhook
    confirme quand même la transaction dès que KKiaPay le notifie. À
    configurer dans le tableau de bord KKiaPay (Clés API > Webhook) avec
    l'URL publique de cette route et le même secret que KKIAPAY_SECRET.
    """
    received_secret = request.headers.get("x-kkiapay-secret", "")
    if not webhook_secret_is_valid(received_secret):
        return jsonify({"error": "secret invalide"}), 401

    payload = request.get_json(silent=True) or {}
    transaction_id = payload.get("transactionId")
    if transaction_id and payload.get("isPaymentSucces"):
        create_pending_unlock(transaction_id, user_id="webhook")
        mark_unlock_paid(transaction_id)

    return jsonify({"received": True}), 200


# ---------------------------------------------------------------------------
# Scraper planifié — remplace le cron système sur un hébergement partagé
# ---------------------------------------------------------------------------

def _start_scraper_scheduler():
    """Lance le scraper toutes les SCRAPER_INTERVAL_HOURS (0 ou absente =
    désactivé, comportement local inchangé). Tourne dans un thread daemon :
    prévoir un seul worker gunicorn (voir render.yaml) pour qu'il n'y ait
    qu'une seule instance de ce planning."""
    try:
        hours = float(os.environ.get("SCRAPER_INTERVAL_HOURS", "0"))
    except ValueError:
        hours = 0.0
    if hours <= 0:
        return

    def _loop():
        while True:
            time.sleep(hours * 3600)
            try:
                from scraper.run_scraper import run as run_scraper
                run_scraper()
            except Exception as e:
                print(f"[scheduler] echec du passage du scraper : {e}")

    threading.Thread(target=_loop, daemon=True, name="scraper-scheduler").start()
    print(f"[scheduler] scraper automatique toutes les {hours} h")


_start_scraper_scheduler()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "").strip().lower() == "true"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=debug)
