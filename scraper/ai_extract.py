# -*- coding: utf-8 -*-
"""
Extraction structurée par IA plutôt que par sélecteurs CSS.

Pourquoi : les pages de bourses n'ont aucune structure commune — chaque
ministère ou université a son propre site, qui change sans prévenir. Un
scraper classique (BeautifulSoup + sélecteurs CSS codés en dur) casse à la
moindre refonte de page. On envoie donc le texte brut de la page à Claude,
qui renvoie une liste d'offres au format attendu par la base de données.
C'est l'approche que plusieurs projets similaires utilisent déjà en
production, précisément parce qu'elle survit aux changements de page.

Nécessite la variable d'environnement ANTHROPIC_API_KEY (clé personnelle à
créer sur console.anthropic.com). L'usage est facturé à la requête, mais
quelques appels par jour sur 8 sources coûte quelques centimes.
"""
import json
import os

import anthropic

MODEL = os.environ.get("BOURSES_AI_MODEL", "claude-haiku-4-5-20251001")

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

EXTRACTION_PROMPT = """Tu extrais des offres de bourses d'études depuis le texte brut d'une page web officielle.

Page source : {source_name}
URL : {source_url}

Analyse le texte ci-dessous et renvoie UNIQUEMENT un tableau JSON (aucun texte autour, aucun bloc de code) contenant une entrée par bourse distincte encore valable trouvée sur la page, avec exactement ces champs :

- "name": nom de la bourse
- "level": "Licence", "Master" ou "Doctorat" (le plus proche si plusieurs niveaux sont couverts)
- "funding": "Complète" ou "Partielle"
- "country": pays d'accueil des études
- "region": qui peut candidater (zone géographique éligible)
- "deadline_date": date limite au format AAAA-MM-JJ si une date précise est indiquée sur la page, sinon null
- "deadline_text": la date limite telle que décrite, en une phrase en français
- "summary": résumé en une phrase, en français
- "benefits": liste de 2 à 5 avantages, en français
- "eligibility": liste de 2 à 5 conditions d'éligibilité, en français
- "steps": liste de 2 à 5 étapes de candidature, en français
- "url": lien de candidature ou d'information s'il est mentionné, sinon l'URL de la page source

Si la page ne décrit aucune bourse encore valable, renvoie un tableau vide [].

Texte de la page :
{page_text}
"""


def extract_scholarships(source_name, source_url, page_text):
    """Renvoie une liste de dicts (éventuellement vide) — jamais d'exception
    pour une page mal formée : une source en échec ne doit pas bloquer les
    sept autres."""
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": EXTRACTION_PROMPT.format(
                source_name=source_name,
                source_url=source_url,
                page_text=page_text[:12000],
            ),
        }],
    )
    raw = "".join(block.text for block in message.content if block.type == "text").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        print(f"[ai_extract] réponse non-JSON pour {source_name}, ignorée")
        return []
