# -*- coding: utf-8 -*-
"""
Client KKiaPay côté serveur.

Le widget KKiaPay (dans static/bourses-afrique.html) tourne dans le
navigateur de l'étudiant — son évènement "succès" ne doit JAMAIS suffire à
débloquer l'accès, puisqu'il est trivial à falsifier depuis la console du
navigateur. La seule source de vérité est cette vérification serveur.

Implémenté directement avec `requests` plutôt qu'avec le package PyPI
`kkiapay` : ce dernier force pytest/responses comme dépendances
d'exécution (une erreur de packaging de leur côté), ce qui casse
l'installation. Les deux appels ci-dessous reproduisent exactement ceux
de leur SDK officiel (mêmes endpoints, mêmes en-têtes).

Variables d'environnement nécessaires :
- KKIAPAY_PUBLIC_KEY
- KKIAPAY_PRIVATE_KEY
- KKIAPAY_SECRET       (aussi utilisé pour vérifier les webhooks entrants)
- KKIAPAY_SANDBOX      ("true" pour tester sans vrai argent, "false" en prod)
"""
import os

import requests

SANDBOX_BASE_URL = "https://api-sandbox.kkiapay.me"
PRODUCTION_BASE_URL = "https://api.kkiapay.me"


def _is_sandbox():
    return os.environ.get("KKIAPAY_SANDBOX", "true").strip().lower() == "true"


def _base_url():
    return SANDBOX_BASE_URL if _is_sandbox() else PRODUCTION_BASE_URL


def _headers():
    return {
        "Accept": "application/json",
        "X-SECRET-KEY": os.environ["KKIAPAY_SECRET"],
        "X-API-KEY": os.environ["KKIAPAY_PUBLIC_KEY"],
        "X-PRIVATE-KEY": os.environ["KKIAPAY_PRIVATE_KEY"],
    }


def verify_transaction(transaction_id):
    """
    Interroge directement l'API KKiaPay pour connaître le vrai statut d'une
    transaction. Renvoie un dict contenant au moins 'status'
    (SUCCESS / FAILED / PENDING) et 'amount'.
    """
    resp = requests.post(
        f"{_base_url()}/api/v1/transactions/status",
        json={"transactionId": transaction_id},
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def webhook_secret_is_valid(received_secret):
    """Compare le header x-kkiapay-secret reçu au secret configuré sur le
    tableau de bord KKiaPay — c'est un secret partagé, pas une signature HMAC."""
    expected = os.environ.get("KKIAPAY_SECRET", "")
    return bool(expected) and received_secret == expected
