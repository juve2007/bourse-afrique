# -*- coding: utf-8 -*-
"""
Orchestrateur du scraper — à lancer périodiquement (voir crontab dans le
README, par exemple toutes les 6 heures).

Pour chaque source officielle de la liste blanche (scraper/sources.py) :
  1. récupère la page
  2. l'IA en extrait les bourses au format structuré (scraper/ai_extract.py)
  3. chaque bourse est enregistrée ou mise à jour en base (models.py)
  4. une bourse jamais vue avant déclenche une alerte Telegram (bot/telegram_notify.py)

Puis, à la fin : les bourses dont la deadline connue est dépassée sont
désactivées — c'est ce qui les fait disparaître automatiquement du site.
"""
import re
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import init_db, upsert_scholarship, expire_past_deadlines, deactivate_missing
from scraper.sources import SOURCES
from scraper.ai_extract import extract_scholarships
from bot.telegram_notify import notify_new_scholarship

HEADERS = {"User-Agent": "BoursesAfriqueBot/1.0 (usage personnel non commercial)"}


def slugify(name, source_domain):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    prefix = source_domain.split(".")[0]
    return f"{prefix}-{base}"[:80]


def fetch_page_text(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def run():
    init_db()
    total_new = 0

    for source in SOURCES:
        try:
            page_text = fetch_page_text(source["url"])
        except requests.RequestException as e:
            print(f"[scraper] échec de récupération pour {source['name']} : {e}")
            continue

        entries = extract_scholarships(source["name"], source["url"], page_text)
        seen_ids = []

        for entry in entries:
            entry["id"] = slugify(entry["name"], source["domain"])
            entry["source_domain"] = source["domain"]
            entry.setdefault("url", source["url"])
            seen_ids.append(entry["id"])

            is_new = upsert_scholarship(entry)
            if is_new:
                total_new += 1
                notify_new_scholarship(entry)
                print(f"[scraper] nouvelle bourse détectée : {entry['name']} ({source['name']})")

        deactivate_missing(source["domain"], seen_ids)

    expired = expire_past_deadlines()
    for e in expired:
        print(f"[scraper] bourse expirée, retirée du site : {e['name']}")

    print(f"[scraper] terminé — {total_new} nouvelle(s) bourse(s), {len(expired)} expirée(s)")


if __name__ == "__main__":
    run()
