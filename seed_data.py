# -*- coding: utf-8 -*-
"""
Amorce la base avec les 8 bourses vérifiées manuellement (état à sept. 2026).
À lancer une seule fois, avant le premier démarrage du site :

    python seed_data.py

Le scraper automatique (scraper/run_scraper.py) prend ensuite le relais pour
ajouter les nouvelles bourses et désactiver celles qui ne sont plus valables.
"""
from models import init_db, upsert_scholarship, DB_PATH

SEED = [
    {
        "id": "chevening-uk",
        "name": "Chevening Scholarships",
        "provider": "Chevening — gouvernement britannique",
        "country": "Royaume-Uni",
        "level": "Master",
        "funding": "Complète",
        "region": "Pays éligibles Chevening (la plupart des pays africains)",
        "deadline_date": "2026-10-06",
        "deadline_text": "6 octobre 2026, 11h00 UTC",
        "summary": "Bourse phare du gouvernement britannique pour un master d'un an dans n'importe quelle université du Royaume-Uni, réservée aux professionnels au potentiel de leadership affirmé.",
        "benefits": ["Frais de scolarité intégralement couverts", "Indemnité mensuelle de subsistance", "Billets d'avion aller-retour vers le Royaume-Uni", "Frais de visa et allocations diverses"],
        "eligibility": ["Être ressortissant d'un pays ou territoire éligible à Chevening", "Avoir au moins deux ans d'expérience professionnelle cumulée", "S'engager à retourner dans son pays au moins deux ans après la bourse"],
        "steps": ["Créer un compte sur le portail Chevening et choisir jusqu'à trois formations de master", "Rédiger les essais de candidature (leadership, réseau, plan de carrière)", "Soumettre le dossier avant la clôture", "Si présélectionné, passer un entretien avec l'ambassade britannique locale"],
        "url": "https://www.chevening.org",
        "source_domain": "chevening.org",
    },
    {
        "id": "commonwealth-master-uk",
        "name": "Commonwealth Master's Scholarships",
        "provider": "Commonwealth Scholarship Commission (Royaume-Uni)",
        "country": "Royaume-Uni",
        "level": "Master",
        "funding": "Complète",
        "region": "Pays du Commonwealth à revenu faible ou intermédiaire",
        "deadline_date": None,
        "deadline_text": "Ouverture prévue dès septembre 2026 — clôture généralement en octobre ou décembre selon le pays",
        "summary": "Bourses financées par le gouvernement britannique pour des études de master, réservées aux candidats qui n'auraient pas les moyens d'étudier au Royaume-Uni autrement.",
        "benefits": ["Scolarité complète dans une université britannique", "Indemnité mensuelle de subsistance", "Billets d'avion aller-retour", "Allocations familiales pour les accompagnants éligibles"],
        "eligibility": ["Être citoyen d'un pays du Commonwealth à revenu faible ou intermédiaire", "Ne pas pouvoir financer ses études sans cette bourse", "Être nominé par l'organisme national désigné dans son pays"],
        "steps": ["Vérifier quel est l'organisme national désigné pour son pays", "Constituer le dossier académique et les lettres de recommandation", "Candidater via le portail en ligne de la Commonwealth Scholarship Commission"],
        "url": "https://cscuk.fcdo.gov.uk",
        "source_domain": "cscuk.fcdo.gov.uk",
    },
    {
        "id": "erasmus-mundus",
        "name": "Erasmus Mundus Joint Master Degrees",
        "provider": "Commission européenne — consortiums universitaires",
        "country": "Union européenne (plusieurs pays)",
        "level": "Master",
        "funding": "Complète",
        "region": "Ouvert aux étudiants de tous les pays hors Union européenne",
        "deadline_date": "2027-01-31",
        "deadline_text": "Autour du 31 janvier 2027 (date précise variable selon le programme choisi)",
        "summary": "Masters conjoints enseignés dans au moins deux pays européens par un consortium d'universités, avec une bourse couvrant la totalité du parcours.",
        "benefits": ["Frais de scolarité pris en charge", "Indemnité mensuelle de 1000 à 1400 €", "Frais de voyage et d'installation", "Assurance santé pour toute la durée du master"],
        "eligibility": ["Être titulaire d'un premier diplôme universitaire (licence)", "Ne pas avoir résidé plus de 12 mois dans un pays du programme au cours des cinq dernières années"],
        "steps": ["Parcourir le catalogue des masters Erasmus Mundus par domaine", "Sélectionner deux à trois programmes correspondant à son profil", "Candidater directement sur le site de chaque consortium avant sa date limite propre"],
        "url": "https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en",
        "source_domain": "eacea.ec.europa.eu",
    },
    {
        "id": "daad-in-country",
        "name": "DAAD In-Country / In-Region Scholarships",
        "provider": "DAAD — Office allemand d'échanges universitaires",
        "country": "Afrique subsaharienne (études sur le continent)",
        "level": "Master",
        "funding": "Complète",
        "region": "Ressortissants d'Afrique subsaharienne",
        "deadline_date": None,
        "deadline_text": "Cycle annuel — clôture généralement fin novembre, prochaine échéance attendue en novembre 2026",
        "summary": "Bourses allemandes finançant des masters à orientation développement, suivis directement dans son pays ou dans un pays voisin d'Afrique subsaharienne.",
        "benefits": ["Bourse mensuelle de subsistance", "Frais de scolarité pris en charge", "Allocations pour la recherche"],
        "eligibility": ["Être ressortissant d'un pays d'Afrique subsaharienne", "Avoir un premier diplôme universitaire", "Les candidatures féminines sont particulièrement encouragées"],
        "steps": ["Identifier le programme correspondant à son pays sur le portail DAAD", "Préparer le dossier académique et les lettres de recommandation", "Candidater via le portail DAAD avant la clôture annuelle"],
        "url": "https://www.daad.de",
        "source_domain": "daad.de",
    },
    {
        "id": "mastercard-foundation",
        "name": "Mastercard Foundation Scholars Program",
        "provider": "Mastercard Foundation — via universités partenaires (Cambridge, Makerere, Pretoria…)",
        "country": "Variable selon l'université partenaire",
        "level": "Licence",
        "funding": "Complète",
        "region": "Étudiants africains issus de milieux économiquement défavorisés",
        "deadline_date": None,
        "deadline_text": "Candidatures 2027/2028 ouvertes depuis septembre 2026 — chaque université partenaire fixe sa propre date de clôture",
        "summary": "Réseau de bourses complètes porté par différentes universités partenaires, avec un accompagnement en leadership en plus du financement des études.",
        "benefits": ["Frais de scolarité et hébergement couverts", "Billets d'avion aller-retour", "Allocation pour ordinateur portable"],
        "eligibility": ["Être ressortissant d'un pays africain", "Venir d'un milieu socio-économique modeste", "Être admis dans le programme de l'université partenaire choisie"],
        "steps": ["Choisir une université partenaire du programme", "Candidater à l'admission académique en indiquant sa demande de bourse", "Fournir les justificatifs de situation économique demandés"],
        "url": "https://mastercardfdn.org/all/scholars/",
        "source_domain": "mastercardfdn.org",
    },
    {
        "id": "fulbright-fsp",
        "name": "Fulbright Foreign Student Program",
        "provider": "Département d'État américain — ambassades des États-Unis",
        "country": "États-Unis",
        "level": "Master",
        "funding": "Complète",
        "region": "Ouvert à la quasi-totalité des pays africains, via l'ambassade américaine locale",
        "deadline_date": None,
        "deadline_text": "Dates variables selon le pays, généralement entre février et mai — à confirmer auprès de l'ambassade américaine locale",
        "summary": "Programme historique du gouvernement américain permettant d'étudier dans une université américaine, avec une sélection organisée par chaque ambassade des États-Unis.",
        "benefits": ["Frais de scolarité et frais universitaires couverts", "Indemnité mensuelle de subsistance", "Billets d'avion aller-retour"],
        "eligibility": ["Être ressortissant du pays où l'on candidate", "Avoir un diplôme universitaire de premier cycle", "Avoir un bon niveau d'anglais"],
        "steps": ["Contacter l'ambassade des États-Unis ou le centre culturel américain de son pays", "Vérifier la date limite propre à son pays", "Préparer relevés de notes, lettres de recommandation et projet d'études"],
        "url": "https://foreign.fulbrightonline.org",
        "source_domain": "foreign.fulbrightonline.org",
    },
    {
        "id": "chine-csc",
        "name": "Chinese Government Scholarship",
        "provider": "China Scholarship Council — ambassades de Chine",
        "country": "Chine",
        "level": "Licence",
        "funding": "Complète ou partielle",
        "region": "Ouvert à la plupart des pays africains via l'ambassade de Chine",
        "deadline_date": None,
        "deadline_text": "Généralement fin septembre — la clôture est proche, à vérifier sans tarder auprès de l'ambassade de Chine",
        "summary": "Large programme de bourses chinoises couvrant tous les niveaux d'études, avec une sélection organisée chaque année par les ambassades de Chine dans chaque pays.",
        "benefits": ["Frais de scolarité pris en charge", "Hébergement sur le campus ou allocation logement", "Allocation mensuelle de subsistance"],
        "eligibility": ["Répondre aux critères d'âge et de santé fixés selon le niveau visé", "Avoir le niveau académique requis pour le cycle demandé"],
        "steps": ["Contacter l'ambassade de Chine ou l'institut Confucius de son pays", "Choisir une université chinoise et un programme d'études", "Constituer le dossier avant la clôture nationale fixée par l'ambassade"],
        "url": "https://www.campuschina.org",
        "source_domain": "campuschina.org",
    },
    {
        "id": "mext-japon",
        "name": "MEXT — bourse du gouvernement japonais",
        "provider": "MEXT — ministère japonais de l'Éducation, ambassades du Japon",
        "country": "Japon",
        "level": "Licence",
        "funding": "Complète",
        "region": "Ouvert à la plupart des pays africains via l'ambassade du Japon",
        "deadline_date": None,
        "deadline_text": "Cycle 2027 clôturé — prochaine campagne attendue entre avril et mai 2027",
        "summary": "Bourse historique du gouvernement japonais, avec une procédure par ambassade incluant des épreuves écrites et un entretien avant la recommandation finale à Tokyo.",
        "benefits": ["Frais de scolarité intégralement couverts", "Billets d'avion aller-retour vers le Japon", "Allocation mensuelle de subsistance"],
        "eligibility": ["Répondre aux limites d'âge fixées selon le niveau visé", "Avoir complété le nombre d'années de scolarité requis", "Réussir les épreuves écrites organisées par l'ambassade du Japon"],
        "steps": ["Suivre les annonces de l'ambassade du Japon dans son pays, généralement en avril", "Déposer un dossier papier avant la date fixée localement", "Passer les épreuves écrites puis un entretien à l'ambassade"],
        "url": "https://www.studyinjapan.go.jp",
        "source_domain": "studyinjapan.go.jp",
    },
]

def seed_if_empty():
    """Amorce la base uniquement si elle ne contient aucune bourse (premier
    lancement sur un disque vierge, typiquement un hébergement neuf).
    Renvoie True si un amorçage a eu lieu. Idempotent : une base déjà
    remplie par le scraper ou par une exécution précédente n'est pas touchée."""
    import sqlite3

    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        count = conn.execute("SELECT COUNT(*) FROM scholarships").fetchone()[0]
    finally:
        conn.close()
    if count:
        return False
    for item in SEED:
        upsert_scholarship(item)
    return True


if __name__ == "__main__":
    init_db()
    for item in SEED:
        is_new = upsert_scholarship(item)
        print(("[+] nouvelle" if is_new else "[=] mise à jour"), "-", item["name"])
