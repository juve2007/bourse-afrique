# -*- coding: utf-8 -*-
"""
Notifie un canal ou un chat Telegram dès qu'une nouvelle bourse est détectée
par le scraper.

Variables d'environnement nécessaires :
- TELEGRAM_BOT_TOKEN : token du bot, obtenu auprès de @BotFather sur Telegram
- TELEGRAM_CHAT_ID   : identifiant du canal/groupe/chat où poster
                       (ex: "@mon_canal_bourses" ou un ID numérique)

Si l'une des deux n'est pas définie, les alertes sont simplement ignorées —
utile pour tester le scraper avant même d'avoir créé le bot.
"""
import os

import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def notify_new_scholarship(entry):
    if not BOT_TOKEN or not CHAT_ID:
        return False

    text = (
        f"Nouvelle bourse : {entry.get('name','')}\n"
        f"Niveau : {entry.get('level','—')} · Financement : {entry.get('funding','—')}\n"
        f"Échéance : {entry.get('deadline_text','à vérifier')}\n"
        f"{entry.get('url','')}"
    )
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text},
            timeout=10,
        )
        return resp.ok
    except requests.RequestException as e:
        print(f"[telegram_notify] échec d'envoi : {e}")
        return False
