# -*- coding: utf-8 -*-
"""
Test de bout en bout du paiement d'abonnement KKiaPay en SANDBOX.

Parcours réel dans un navigateur :
  connexion -> clic "S'abonner maintenant" -> widget KKiaPay (iframe) ->
  remplissage du formulaire Mobile Money (numéro de test sandbox) ->
  clic "Payer" -> retour du widget -> /api/subscribe/verify côté serveur ->
  vérification que l'abonnement 30 jours est actif sur /api/me.

Aucune donnée réelle : numéros de test documentés par KKiaPay
(https://docs.kkiapay.me/v1/compte/kkiapay-sandbox-guide-de-test).

Lancer d'abord le site (python app.py), puis :
    python test_payment_e2e.py
"""
import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"
DEMO_EMAIL = "demo@bourses.ci"
DEMO_PASSWORD = "demo12345"
# Numéro MOOV Money de succès documenté en sandbox (Bénin, +229)
TEST_PHONE = "68000000"
TEST_NAME = "Koffi"
TEST_FIRSTNAME = "Demo"
TEST_EMAIL = "demo@bourses.ci"


def kframe(page):
    """Renvoie la frame du widget KKiaPay (ou la dernière frame connue)."""
    for fr in page.frames:
        if "kkiapay" in (fr.url or ""):
            return fr
    return page.frames[-1]


def dump(frame, label):
    """Affiche l'état d'une frame (champs + texte utile) pour diagnostiquer."""
    try:
        state = frame.evaluate(
            """() => ({
                text: (document.body && document.body.innerText || '').slice(0, 400),
                inputs: Array.from(document.querySelectorAll('input')).map(i => ({
                    type: i.type, name: i.name, id: i.id,
                    ph: i.placeholder, value: i.value
                })),
                buttons: Array.from(document.querySelectorAll('button'))
                    .map(b => (b.innerText || '').trim()).filter(Boolean)
            })"""
        )
    except Exception as e:
        print(f"  [{label}] frame injoignable : {e}")
        return None
    print(f"  [{label}] boutons : {state['buttons']}")
    for i in state["inputs"]:
        print(f"  [{label}] input {i}")
    return state


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # Mode : "subscribe" (abonnement 2500, par défaut) ou "unlock" (500, une bourse)
    mode = sys.argv[1] if len(sys.argv) > 1 else "subscribe"
    assert mode in ("subscribe", "unlock"), f"mode inconnu : {mode}"
    verify_url = "/api/subscribe/verify" if mode == "subscribe" else "/api/unlock/verify"
    trigger_text = "S'abonner maintenant" if mode == "subscribe" else "Débloquer cette bourse seulement"
    results = {"mode": mode, "steps": [], "ok": False}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        api_verify = {}

        def on_response(resp):
            if verify_url in resp.url:
                api_verify["status"] = resp.status
                try:
                    api_verify["body"] = resp.json()
                except Exception as e:
                    try:
                        api_verify["text"] = resp.text()[:500]
                    except Exception:
                        api_verify["text"] = f"<illisible: {e}>"

        page.on("response", on_response)

        # --- Connexion -----------------------------------------------------
        page.goto(f"{BASE}/connexion", wait_until="domcontentloaded")
        page.fill('input[name="email"]', DEMO_EMAIL)
        page.fill('input[name="password"]', DEMO_PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{BASE}/", timeout=10000)
        me_before = page.evaluate("fetch('/api/me').then(r => r.json())")
        print("Avant paiement :", json.dumps(me_before.get("subscription"), ensure_ascii=False))
        results["subscription_before"] = me_before.get("subscription")

        if me_before.get("subscription", {}).get("active"):
            print("Abonnement déjà actif : on continue quand même (le widget reste testable).")

        # --- Ouverture du widget -------------------------------------------
        if mode == "subscribe":
            page.click("text=S'abonner maintenant")
        else:
            # Déblocage à l'unité : ouvrir d'abord la première fiche (accordéon),
            # puis cliquer sur son bouton de déblocage
            page.locator("button.dossier-head").first.click()
            page.wait_for_selector("button.dossier-head[aria-expanded='true']", timeout=5000)
            time.sleep(0.5)
            page.get_by_role("button", name="Débloquer cette bourse seulement").first.click()
        page.wait_for_selector("iframe[src*='kkiapay']", timeout=15000)
        time.sleep(5)
        frame = page.frame_locator("iframe[src*='kkiapay']")
        print("Widget chargé.")

        # Certains comptes affichent d'abord un écran de choix du moyen de paiement.
        state = dump(kframe(page), "écran 1")
        results["steps"].append({"screen": "initial", "state": state})

        # Bascule éventuelle sur l'onglet Mobile Money
        try:
            page.frame_locator("iframe[src*='kkiapay']").get_by_text("Mobile Money", exact=False).first.click(timeout=4000)
            time.sleep(1)
        except Exception:
            pass  # déjà sur Mobile Money

        # Remplissage du formulaire
        f = page.frame_locator("iframe[src*='kkiapay']")
        filled = {}
        for label, value in (("Nom", TEST_NAME), ("Prénoms", TEST_FIRSTNAME), ("Email", TEST_EMAIL)):
            try:
                f.get_by_label(label, exact=False).first.fill(value, timeout=4000)
                filled[label] = value
            except Exception:
                try:
                    f.get_by_placeholder("", exact=False)  # noop pour clarifier l'erreur
                except Exception:
                    pass
                # Repli : champ par position de texte proche
                try:
                    loc = f.locator(f"input[type='text']").nth(len(filled))
                    loc.fill(value, timeout=2000)
                    filled[label] = value + " (par position)"
                except Exception as e:
                    print(f"  champ {label} introuvable : {e}")
        print("Champs remplis :", filled)
        results["filled"] = filled

        # Numéro Mobile Money (le champ country +229 est préfixé côté widget)
        phone_ok = False
        for sel in ["input[type='tel']", "input[inputmode='tel']", "input[type='text']:last-of-type"]:
            try:
                loc = f.locator(sel).last
                loc.fill(TEST_PHONE, timeout=3000)
                phone_ok = True
                print(f"Numéro saisi via {sel}")
                break
            except Exception:
                continue
        results["phone_ok"] = phone_ok
        state = dump(kframe(page), "formulaire")
        results["steps"].append({"screen": "form_filled", "state": state})

        # --- Paiement --------------------------------------------------------
        pay_btn = f.get_by_role("button", name=re.compile("Payer"))
        try:
            pay_btn.first.click(timeout=6000)
        except Exception as e:
            # Repli : dernier bouton de la frame
            print(f"  bouton Payer (role) injoignable ({e}), repli dernier <button>")
            kframe(page).locator("button").last.click()
        print("Clic sur Payer.")
        results["steps"].append({"screen": "pay_clicked"})

        # Le widget peut afficher un écran OTP / confirmation en sandbox.
        deadline = time.time() + 25
        advanced = False
        while time.time() < deadline:
            time.sleep(1)
            fr = kframe(page)
            try:
                txt = fr.evaluate("() => (document.body.innerText || '').slice(0, 300)")
            except Exception:
                txt = ""
            if "OTP" in txt or "code" in txt.lower():
                state = dump(fr, "OTP")
                results["steps"].append({"screen": "otp", "state": state})
                # En sandbox carte, l'OTP de test documenté est 12345
                for sel in ["input[type='text']", "input[type='tel']", "input[inputmode='numeric']"]:
                    try:
                        fr.locator(sel).first.fill("12345", timeout=2000)
                        fr.get_by_role("button", name=re.compile("Valider|Confirmer|Continuer|Payer")).first.click(timeout=2000)
                        print("OTP 12345 saisi + validation.")
                        advanced = True
                        break
                    except Exception:
                        continue
                if advanced:
                    break
            if api_verify:
                break

        # Attente du retour /api/subscribe/verify
        waited = 0
        while not api_verify and waited < 40:
            time.sleep(1)
            waited += 1
        results["verify_response"] = api_verify
        print("Réponse", verify_url, ":", json.dumps(api_verify, ensure_ascii=False))

        # --- Vérification finale --------------------------------------------
        time.sleep(1)
        me_after = page.evaluate("fetch('/api/me').then(r => r.json())")
        results["subscription_after"] = me_after.get("subscription")
        print("Après paiement :", json.dumps(me_after.get("subscription"), ensure_ascii=False))

        ok = bool(api_verify.get("body", {}).get("ok"))
        if mode == "subscribe":
            ok = ok and bool(me_after.get("subscription", {}).get("active"))
            print("Abonnement après paiement :", json.dumps(me_after.get("subscription"), ensure_ascii=False))
        else:
            ok = ok and len(me_after.get("unlocked_ids") or []) > 0
            print("Bourses débloquées après paiement :", me_after.get("unlocked_ids"))
        results["ok"] = ok
        browser.close()

    print("\n=== RÉSULTAT :", "SUCCÈS ✅" if ok else "ÉCHEC ❌", "===")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
