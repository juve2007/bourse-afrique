"""
Base de données SQLite pour les bourses.
Toute la logique d'ajout, de mise à jour et d'expiration passe par ce module —
le site (app.py) et le scraper (scraper/run_scraper.py) ne font que l'appeler.
"""
import sqlite3
import json
import os
import secrets
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get(
    "BOURSES_DB_PATH", os.path.join(os.path.dirname(__file__), "bourses.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS scholarships (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT,
    country TEXT,
    level TEXT,
    funding TEXT,
    region TEXT,
    deadline_date TEXT,
    deadline_text TEXT,
    summary TEXT,
    benefits TEXT,
    eligibility TEXT,
    steps TEXT,
    url TEXT,
    source_domain TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_verified TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unlocks (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    scholarship_id TEXT,
    amount INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    transaction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    amount INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    expires_at TEXT
);
"""

SUBSCRIPTION_DAYS = int(os.environ.get("SUBSCRIPTION_DAYS", "30"))


def get_conn(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    conn = get_conn(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def compute_status(deadline_date_iso):
    """Statut recalculé à la volée à chaque lecture, jamais figé en base."""
    if not deadline_date_iso:
        return "bientot"
    try:
        d = datetime.strptime(deadline_date_iso, "%Y-%m-%d").date()
    except ValueError:
        return "bientot"
    days = (d - date.today()).days
    if days < 0:
        return "cloture"
    if days <= 30:
        return "urgent"
    return "ouvert"


def _row_to_dict(row):
    item = dict(row)
    item["benefits"] = json.loads(item["benefits"] or "[]")
    item["eligibility"] = json.loads(item["eligibility"] or "[]")
    item["steps"] = json.loads(item["steps"] or "[]")
    item["status"] = compute_status(item["deadline_date"])
    return item


def get_active_scholarships(db_path=None):
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM scholarships WHERE active = 1 "
        "ORDER BY (deadline_date IS NULL), deadline_date ASC"
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def upsert_scholarship(data, db_path=None):
    """
    Insère ou met à jour une bourse. Retourne True si c'est une toute
    nouvelle bourse (jamais vue avant) — ce signal déclenche l'alerte Telegram.
    """
    conn = get_conn(db_path)
    now = datetime.utcnow().isoformat()
    existing = conn.execute(
        "SELECT id FROM scholarships WHERE id = ?", (data["id"],)
    ).fetchone()
    is_new = existing is None

    fields = (
        data["name"], data.get("provider", ""), data.get("country", ""),
        data.get("level", ""), data.get("funding", ""), data.get("region", ""),
        data.get("deadline_date"), data.get("deadline_text", ""),
        data.get("summary", ""),
        json.dumps(data.get("benefits", []), ensure_ascii=False),
        json.dumps(data.get("eligibility", []), ensure_ascii=False),
        json.dumps(data.get("steps", []), ensure_ascii=False),
        data.get("url", ""), data.get("source_domain", ""),
    )

    if is_new:
        conn.execute(
            """INSERT INTO scholarships
               (name, provider, country, level, funding, region, deadline_date,
                deadline_text, summary, benefits, eligibility, steps, url,
                source_domain, active, first_seen, last_verified, id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
            fields + (now, now, data["id"]),
        )
    else:
        conn.execute(
            """UPDATE scholarships SET
               name=?, provider=?, country=?, level=?, funding=?, region=?,
               deadline_date=?, deadline_text=?, summary=?, benefits=?,
               eligibility=?, steps=?, url=?, source_domain=?, active=1,
               last_verified=?
               WHERE id=?""",
            fields + (now, data["id"]),
        )
    conn.commit()
    conn.close()
    return is_new


def expire_past_deadlines(db_path=None):
    """
    À lancer régulièrement (voir crontab dans le README). Désactive toute
    bourse dont la deadline connue est dépassée : elle disparaît alors du
    site automatiquement, puisque get_active_scholarships() ne renvoie que
    les bourses actives. Retourne la liste de celles qui viennent d'expirer.
    """
    conn = get_conn(db_path)
    today = date.today().isoformat()
    rows = conn.execute(
        "SELECT id, name FROM scholarships "
        "WHERE active = 1 AND deadline_date IS NOT NULL AND deadline_date < ?",
        (today,),
    ).fetchall()
    conn.execute(
        "UPDATE scholarships SET active = 0 "
        "WHERE active = 1 AND deadline_date IS NOT NULL AND deadline_date < ?",
        (today,),
    )
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]


def deactivate_missing(source_domain, seen_ids, db_path=None):
    """
    Si une bourse d'une source donnée n'apparaît plus du tout sur la page
    source (retirée par l'organisme) alors qu'elle n'avait pas de deadline
    connue, on la désactive aussi — sinon elle resterait affichée pour
    toujours faute de date à comparer.
    """
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT id FROM scholarships WHERE active = 1 AND source_domain = ?",
        (source_domain,),
    ).fetchall()
    to_deactivate = [r["id"] for r in rows if r["id"] not in seen_ids]
    if to_deactivate:
        conn.executemany(
            "UPDATE scholarships SET active = 0 WHERE id = ?",
            [(i,) for i in to_deactivate],
        )
        conn.commit()
    conn.close()
    return to_deactivate# ---------------------------------------------------------------------------
# Comptes utilisateurs (inscription / connexion)
# ---------------------------------------------------------------------------

def create_user(name, email, password, db_path=None):
    """
    Crée un compte. Lève ValueError si l'email est déjà utilisé.
    Le mot de passe est haché (werkzeug/scrypt) — jamais stocké en clair.
    """
    email = (email or "").strip().lower()
    name = (name or "").strip()
    if not name or not email or not password:
        raise ValueError("Champs manquants.")
    conn = get_conn(db_path)
    if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        conn.close()
        raise ValueError("Un compte existe déjà avec cet email.")
    user_id = secrets.token_hex(16)
    conn.execute(
        """INSERT INTO users (id, name, email, password_hash, created_at)
           VALUES (?,?,?,?,?)""",
        (user_id, name, email, generate_password_hash(password),
         datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return get_user_by_id(user_id, db_path)


def get_user_by_id(user_id, db_path=None):
    conn = get_conn(db_path)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email, db_path=None):
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", ((email or "").strip().lower(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_user_password(user, password):
    """Vérifie le mot de passe d'un compte (user = dict issu de la base)."""
    return bool(user) and check_password_hash(user["password_hash"], password or "")


# ---------------------------------------------------------------------------
# Abonnement (KKiaPay) — accès complet pendant 30 jours
# ---------------------------------------------------------------------------

def create_pending_subscription(transaction_id, user_id, amount=None, db_path=None):
    """
    Enregistre (ou retrouve, si l'appel est refait) l'abonnement associé à
    cette transaction KKiaPay — il ne devient actif qu'après confirmation
    côté serveur (activate_subscription). Idempotent par transaction_id.
    """
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    if row:
        conn.close()
        return dict(row)
    conn.execute(
        """INSERT INTO subscriptions (transaction_id, user_id, amount, status, created_at)
           VALUES (?,?,?, 'pending', ?)""",
        (transaction_id, user_id, amount, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return get_subscription_by_transaction(transaction_id, db_path)


def get_subscription_by_transaction(transaction_id, db_path=None):
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def activate_subscription(transaction_id, db_path=None):
    """
    Confirme un abonnement une fois le paiement vérifié côté serveur auprès
    de KKiaPay, et le fait durer SUBSCRIPTION_DAYS jours (30 par défaut).
    Idempotent : rejouer une transaction déjà payée renvoie la même
    date d'expiration. Retourne expires_at, ou None si transaction inconnue.
    """
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    if row["status"] == "paid" and row["expires_at"]:
        conn.close()
        return row["expires_at"]
    now = datetime.utcnow()
    expires_at = (now + timedelta(days=SUBSCRIPTION_DAYS)).isoformat()
    conn.execute(
        """UPDATE subscriptions SET status = 'paid', confirmed_at = ?, expires_at = ?
           WHERE transaction_id = ?""",
        (now.isoformat(), expires_at, transaction_id),
    )
    conn.commit()
    conn.close()
    return expires_at


def get_active_subscription(user_id, db_path=None):
    """
    Renvoie l'abonnement payé le plus récent s'il est encore valide
    (expiration dans le futur), sinon None. Jamais figé : recalculé à chaque
    lecture, donc un abonnement expiré cesse immédiatement de donner accès.
    """
    conn = get_conn(db_path)
    row = conn.execute(
        """SELECT * FROM subscriptions
           WHERE user_id = ? AND status = 'paid' AND expires_at IS NOT NULL
           ORDER BY expires_at DESC LIMIT 1""",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        expires = datetime.fromisoformat(row["expires_at"])
    except ValueError:
        return None
    if expires <= datetime.utcnow():
        return None
    return dict(row)


# ---------------------------------------------------------------------------
# Déblocage à l'unité (KKiaPay) — une bourse payée 500 FCFA, liée au compte
# ---------------------------------------------------------------------------

def create_pending_unlock(transaction_id, user_id, scholarship_id=None,
                           amount=None, db_path=None):
    """
    Appelé dès que le widget KKiaPay renvoie un succès côté client. Crée (ou
    retrouve, si l'appel est refait) le déblocage lié à cette transaction et
    à l'utilisateur connecté — il ne devient utilisable qu'après confirmation
    côté serveur (mark_unlock_paid). Idempotent par transaction_id.
    """
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM unlocks WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    if row:
        conn.close()
        return dict(row)
    conn.execute(
        """INSERT INTO unlocks (transaction_id, user_id, scholarship_id, amount, status, created_at)
           VALUES (?,?,?,?, 'pending', ?)""",
        (transaction_id, user_id, scholarship_id, amount,
         datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return get_unlock_by_transaction(transaction_id, db_path)


def get_unlock_by_transaction(transaction_id, db_path=None):
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM unlocks WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_unlock_paid(transaction_id, db_path=None):
    """
    Confirme un déblocage une fois le paiement vérifié côté serveur auprès de
    KKiaPay (jamais sur la seule foi de l'évènement du navigateur).
    """
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT 1 FROM unlocks WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute(
        "UPDATE unlocks SET status = 'paid', confirmed_at = ? WHERE transaction_id = ?",
        (datetime.utcnow().isoformat(), transaction_id),
    )
    conn.commit()
    conn.close()
    return True


def get_unlocked_scholarship_ids(user_id, db_path=None):
    """
    Liste des ids de bourses débloquées individuellement par un utilisateur
    (payées une à une). Un abonnement actif rend cette liste inutile côté UI.
    """
    conn = get_conn(db_path)
    rows = conn.execute(
        """SELECT scholarship_id FROM unlocks
           WHERE user_id = ? AND status = 'paid' AND scholarship_id IS NOT NULL""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [r["scholarship_id"] for r in rows]
