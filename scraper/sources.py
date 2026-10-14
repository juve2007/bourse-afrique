# -*- coding: utf-8 -*-
"""
Liste blanche des sources officielles interrogées par le scraper.

C'est cette liste qui fait la différence entre "bourses certifiées" et
"scraping de n'importe quel site trouvé sur Google" — n'y ajoute que des
organismes officiels. Pour ajouter une nouvelle source, il suffit d'ajouter
une entrée ici ; le reste du pipeline (extraction, base, site) suit
automatiquement.
"""

SOURCES = [
    {"name": "Chevening", "domain": "chevening.org",
     "url": "https://www.chevening.org/scholarships/"},
    {"name": "Commonwealth Scholarships", "domain": "cscuk.fcdo.gov.uk",
     "url": "https://cscuk.fcdo.gov.uk/scholarships/"},
    {"name": "Erasmus Mundus", "domain": "eacea.ec.europa.eu",
     "url": "https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en"},
    {"name": "DAAD", "domain": "daad.de",
     "url": "https://www.daad.de/en/study-and-research-in-germany/scholarships/"},
    {"name": "Mastercard Foundation", "domain": "mastercardfdn.org",
     "url": "https://mastercardfdn.org/all/scholars/"},
    {"name": "Fulbright", "domain": "foreign.fulbrightonline.org",
     "url": "https://foreign.fulbrightonline.org/"},
    {"name": "China Scholarship Council", "domain": "campuschina.org",
     "url": "https://www.campuschina.org/"},
    {"name": "MEXT Japon", "domain": "studyinjapan.go.jp",
     "url": "https://www.studyinjapan.go.jp/en/"},
]
