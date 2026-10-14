# Bourses Afrique — bot + site + paiement

Site web qui affiche des bourses d'études vérifiées, alimenté par un scraper
automatique. Quand une nouvelle bourse apparaît sur une source officielle,
elle est ajoutée au site et une alerte part sur Telegram. Quand sa date
limite est dépassée, elle disparaît automatiquement du site.

Le site est privé : il faut **créer un compte ou se connecter** pour y accéder.
Une fois connecté, on tombe directement sur les bourses — le résumé et les
dates sont visibles gratuits ; les conditions détaillées, les étapes de
candidature et le lien officiel se débloquent de deux façons (paiement
KKiaPay, mobile money) :
- **l'abonnement à 2500 FCFA** : ouvre tous les détails de toutes les bourses
  pendant 30 jours (durée réglable via `SUBSCRIPTION_DAYS`) ;
- **le déblocage à l'unité à 500 FCFA** : ouvre le détail d'une seule bourse,
  définitivement, sans s'abonner.

**Important : ce projet doit tourner sur ta propre machine ou un petit
serveur avec accès internet.** Il ne peut pas fonctionner dans l'environnement
où il a été généré, qui n'a accès qu'aux dépôts de paquets (pip/npm), pas aux
sites de bourses, ni à l'API Telegram, ni à l'API KKiaPay.

## 1. Installation

```bash
python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.9 ou plus récent est nécessaire.

## 2. Amorcer la base avec les 8 bourses déjà vérifiées

```bash
python seed_data.py
```

Ça crée `bourses.db` (SQLite) à côté du projet, avec les 8 bourses de départ.

Si tu avais déjà une `bourses.db` créée avant l'ajout des comptes et des
abonnements, supprime-la puis relance `python seed_data.py` : le schéma a
évolué (tables `users` et `subscriptions`, déblocages rattachés aux comptes).

## 3. Lancer le site

```bash
python app.py
```

Le site démarre sur http://localhost:5000 — ouvre cette adresse et **crée un compte** (nom, email, mot de passe) ou connecte-toi : tu arrives alors
directement sur les 8 bourses de départ (résumé et dates en libre accès,
détails verrouillés tant qu'aucun paiement n'a été confirmé).

Note : si la variable d'environnement `PORT` est déjà définie (certains
environnements le font), Flask utilise ce port à la place de 5000 — regarde
la ligne `Running on ...` affichée au démarrage.

## 4. Configurer le bot Telegram

1. Sur Telegram, parle à **@BotFather**, envoie `/newbot`, choisis un nom.
   Il te donne un token (une longue chaîne du type `123456:ABC-def...`).
2. Crée un canal ou groupe Telegram pour recevoir les alertes, ajoute ton bot
   dedans en tant qu'administrateur.
3. Pour connaître l'identifiant du canal/groupe (`TELEGRAM_CHAT_ID`) :
   - Pour un canal public : utilise directement `@nom_du_canal`.
   - Sinon, envoie un message dans le canal puis ouvre dans un navigateur :
     `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` — l'identifiant
     numérique apparaît dans la réponse (`"chat":{"id": ...}`).
4. Définis les variables d'environnement avant de lancer le scraper :

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-def..."
export TELEGRAM_CHAT_ID="@mon_canal_bourses"
```

## 5. Configurer l'extraction par IA

Le scraper utilise l'API Claude pour lire chaque page et en extraire les
bourses (voir `scraper/ai_extract.py` pour le pourquoi). Il te faut une clé
API personnelle :

1. Crée un compte sur https://console.anthropic.com et génère une clé API.
2. Définis-la :

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

L'usage est facturé à la requête (quelques centimes pour un passage sur les
8 sources). Le scraper utilise `claude-haiku-4-5-20251001` par défaut (rapide
et économique) — modifiable via la variable `BOURSES_AI_MODEL` si tu veux
plus de précision avec un modèle plus capable.

## 6. Configurer le paiement KKiaPay

1. Crée un compte marchand sur https://app.kkiapay.me.
2. Dans le tableau de bord, section **Clés API**, récupère tes trois clés :
   clé publique, clé privée, et le secret. En sandbox (mode test, sans vrai
   argent) et en production, les clés sont différentes — commence en sandbox.
3. Toujours dans **Clés API > Webhook**, ajoute un webhook : l'URL sera
   `https://<ton-domaine>/api/unlock/webhook` une fois le site en ligne (pas
   utilisable en local), et le secret hash doit être exactement le même que
   `KKIAPAY_SECRET` ci-dessous. Ce webhook est un filet de sécurité — le
   déblocage marche déjà sans lui, via la vérification directe après paiement.
4. Définis les variables d'environnement :

```bash
export KKIAPAY_PUBLIC_KEY="pk_..."
export KKIAPAY_PRIVATE_KEY="sk_..."
export KKIAPAY_SECRET="..."
export KKIAPAY_SANDBOX="true"          # "false" seulement quand tu factures pour de vrai
export SUBSCRIPTION_AMOUNT_FCFA="2500"  # prix de l'abonnement (accès complet 30 j)
export SUBSCRIPTION_DAYS="30"           # durée de l'abonnement, optionnel
export UNLOCK_AMOUNT_FCFA="500"        # prix du déblocage d'une seule bourse
```

5. Teste : relance `python app.py`, connecte-toi, puis soit clique sur
   "S'abonner" (2500 FCFA, toutes les bourses 30 j), soit sur "Débloquer
   cette bourse seulement" (500 FCFA). En sandbox, KKiaPay fournit des
   numéros de test (voir leur documentation) pour simuler un paiement Mobile
   Money sans vrai argent.

Les clés se rangent dans un fichier `.env` à côté de `app.py` (déjà ignoré
par git) — `python app.py` le charge automatiquement, donc aucun export
manuel n'est nécessaire en local.

**Test automatisé de bout en bout :** `test_payment_e2e.py` pilote le vrai
widget KKiaPay dans un navigateur (connexion, remplissage du formulaire
Mobile Money avec un numéro de test sandbox, paiement, vérification serveur,
contrôle que l'abonnement/déblocage est bien actif) :

```bash
pip install playwright && playwright install chromium   # une seule fois
python test_payment_e2e.py           # abonnement 2500 FCFA
python test_payment_e2e.py unlock    # déblocage unité 500 FCFA
```

Le site doit tourner au préalable (`python app.py`). Le script sort en 0 si
le paiement est confirmé par le serveur et l'accès ouvert, 1 sinon.

**Important — sécurité :** aucun accès ne se déclenche sur la seule foi de ce
que renvoie le navigateur. `app.py` rappelle systématiquement l'API KKiaPay
depuis le serveur (`payments/kkiapay_client.py`) pour confirmer qu'un
paiement a réellement été accepté — et le rattache alors au compte connecté
(abonnement daté, ou bourse débloquée) — avant d'ouvrir quoi que ce soit.

## 7. Lancer le scraper manuellement (pour tester)

```bash
python -m scraper.run_scraper
```

Il affiche dans le terminal ce qu'il a trouvé, ajouté et expiré. Rafraîchis
le site pour voir les changements.

## 8. Automatiser avec cron

Pour que le scraper tourne tout seul, par exemple toutes les 6 heures :

```bash
crontab -e
```

Ajoute une ligne (adapte les chemins) :

```
0 */6 * * * cd /chemin/vers/bourses-bot && /chemin/vers/venv/bin/python -m scraper.run_scraper >> scraper.log 2>&1
```

N'oublie pas que les variables d'environnement (`TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`) doivent être disponibles pour la
tâche cron — le plus simple est de les mettre dans un fichier `.env` chargé
en haut du crontab, ou dans `/etc/environment`.

## 9. Mettre le site en ligne (Render)

Le projet est prêt pour **Render** (render.com) : plan Starter (~7 $/mois),
toujours actif, disque persistant pour SQLite, HTTPS automatique — donc une
URL publique stable pour les webhooks KKiaPay. Le fichier `render.yaml` à la
racine décrit tout le service (build, démarrage gunicorn, variables, disque) :
Render l'applique automatiquement en reliant le dépôt GitHub.

Le plan gratuit Render ne convient pas ici (veille après 15 min sans visite,
pas de disque persistant → comptes et paiements perdu aux redéploiements),
d'où le Starter.

### Étapes (une seule fois)

1. **Dépôt GitHub** : crée un dépôt vide sur github.com, puis pousse le
   projet (le `.gitignore` exclut déjà `.env`, `bourses.db`, `venv/`, les
   logs — aucune clé ne part sur GitHub) :

   ```bash
   git init
   git add .
   git commit -m "Bourses Afrique"
   git remote add origin https://github.com/<toi>/bourses-afrique.git
   git push -u origin master   # ou main, selon la branche créée
   ```

2. **Compte Render** : inscris-toi sur render.com, ajoute un moyen de
   paiement (le plan Starter est payant), puis **New + → Blueprint** et
   sélectionne ton dépôt GitHub. Render lit `render.yaml` et crée le
   service, le disque persistant et les variables.

3. **Variables secrètes** (Render → ton service → Environment) — marquées
   `sync: false` dans le `render.yaml`, elles ne sont jamais écrites dans
   le dépôt :

   | Variable | Valeur |
   |---|---|
   | `KKIAPAY_PUBLIC_KEY` | clé **Live** (onglet Live du tableau KKiaPay) |
   | `KKIAPAY_PRIVATE_KEY` | clé **Live** |
   | `KKIAPAY_SECRET` | secret **Live** |
   | `ANTHROPIC_API_KEY` | clé console.anthropic.com (extraction IA) |
   | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | optionnel (alertes) |

   Déjà réglées par le blueprint : `KKIAPAY_SANDBOX=false` (live),
   `SESSION_COOKIE_SECURE=true`, `FLASK_SECRET_KEY` (généré par Render),
   `BOURSES_DB_PATH=/data/bourses.db` (disque persistant),
   `SCRAPER_INTERVAL_HOURS=6`.

4. **Premier déploiement** : Render installe `requirements.txt`, lance
   `gunicorn app:app`, crée la base sur le disque et l'amorce avec les
   bourses de `seed_data.py` si elle est vide. Le site est en ligne sur
   `https://<nom>.onrender.com` (HTTPS inclus).

5. **Webhook KKiaPay** : dans le tableau de bord KKiaPay (onglet Webhook),
   renseigne `https://<ton-site>.onrender.com/api/unlock/webhook` avec le
   même secret que `KKIAPAY_SECRET` — filet de sécurité si l'onglet se ferme
   juste après un paiement.

6. **Redéploiements** : chaque `git push` déclenche une mise en ligne ; le
   disque persistant conserve comptes, abonnements et bourses.

### Après le lancement

- Teste une fois inscription + paiement live sur l'URL publique.
- Le scraper tourne toutes les 6 h dans le service
  (`SCRAPER_INTERVAL_HOURS`) : pas besoin de cron sur Render. En local la
  variable est absente, donc le cron local (section 8) reste valable.
- Pour re-passage en test sans argent : `KKIAPAY_SANDBOX=true` + clés
  sandbox dans Environment, puis redéploie.

## Comment ça s'articule

```
scraper/run_scraper.py       -> lit les sources, extrait via IA, écrit dans models.py
models.py                    -> base SQLite : comptes, bourses, abonnements, déblocages, statuts
app.py                       -> auth par session + /api/me, /api/scholarships, /api/config,
                               /api/subscribe/*, /api/unlock/*, et le site
payments/kkiapay_client.py   -> vérifie chaque paiement directement auprès de KKiaPay
templates/                   -> pages d'inscription et de connexion
static/bourses-afrique.html  -> interroge l'API, s'auto-actualise, gère le verrouillage des détails
bot/telegram_notify.py       -> alerte dès qu'une bourse jamais vue est ajoutée
```

## Limites connues à garder en tête

- Certaines pages (surtout celles qui chargent leur contenu en JavaScript)
  ne seront pas correctement lues par `requests` + BeautifulSoup — il
  faudra alors basculer cette source sur Playwright.
- L'extraction par IA peut se tromper ou rater une bourse mal formulée sur
  la page — pense à relire de temps en temps ce qui a été ajouté.
- La liste des 8 sources dans `scraper/sources.py` est un point de départ :
  ajoute-en d'autres au fur et à mesure, une entrée suffit.
- Le paiement utilise directement l'API HTTP de KKiaPay (voir
  `payments/kkiapay_client.py`) plutôt que leur package PyPI officiel
  `kkiapay`, qui force `pytest`/`responses` comme dépendances d'exécution et
  casse l'installation — les deux appels utilisés sont identiques à ceux de
  leur SDK, juste sans ce bagage.
