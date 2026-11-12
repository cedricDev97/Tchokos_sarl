# eKAKO — Stabilisation V1
Branche de travail : `ekako-stabilisation-v1` depuis `ekako-redesign`.

## Maintenance
`EKAKO_MAINTENANCE=1` active la maintenance au prochain redémarrage de l'application.
`EKAKO_MAINTENANCE=0` la désactive. La boutique renvoie HTTP 503 ; les API
publiques reçoivent une réponse JSON et les opérations de commande sont bloquées.
`/admin/` reste accessible pour les opérateurs autorisés. Les utilisateurs
administrateurs déjà connectés gardent accès aux pages et API administratives.
Cette V1 n'a pas encore d'interrupteur de maintenance dans le tableau de bord.

## Turnstile
La protection est **désactivée par défaut** ; il faut créer un widget dans
Cloudflare Turnstile pour obtenir les vraies clés avant de l'activer.
Configurer chez l'hébergeur :
- `EKAKO_TURNSTILE_ENABLED=1`
- `EKAKO_TURNSTILE_SITE_KEY=...` (publique)
- `EKAKO_TURNSTILE_SECRET_KEY=...` (privée, ne pas committer)
- `EKAKO_TURNSTILE_HOSTNAME=exemple.com` (sans https, recommandé)

Les actions sécurisées sont : login, register, reseller, checkout. Le serveur
vérifie le token Siteverify, l'action et le hostname configuré.
Important : Turnstile ne remplace pas le rate limiting.
Sur les requêtes de paiement répétées, tester l'idempotence et les erreurs
réseau, car les jetons Turnstile ne sont pas réutilisables.

## Tests sur Mac
```bash
git fetch origin
git switch ekako-stabilisation-v1
source .venv/bin/activate
python3 manage.py check
python3 manage.py test config.tests_stabilisation orders.tests
```
En production, vérifier aussi `python3 manage.py check --deploy`,
les reverse proxies et le stockage persistant des photos produits.

## Validation avant fusion
- Pages 400/403/404/500 et 503, sur smartphone et desktop.
- Maintenances ON/OFF ; erreurs API 503 ; accès admin.
- Panier vide, recherche infructueuse et erreur catalogue.
- Connexion/inscription, demande revendeur, création d'une commande.
- CAPTCHA avec clés réelles : valide, absent, expiré, réutilisé.
- Idempotence checkout, absence de double décrément stock.
- Les frais de livraison V2 et paiements réels ne sont pas modifiés.

## Vérification Turnstile en local sans clés personnelles
Cloudflare fournit des clés de test publiques. Avec DEBUG=True et une paire de
clés de test officielles, l'application accepte l'absence du champ `action`
dans la réponse Siteverify, ce qui correspond au comportement documenté.
**En production, cette exception est désactivée et les clés de test sont interdites.**

Arrêter le serveur, puis lancer depuis la racine du projet :
```bash
EKAKO_TURNSTILE_ENABLED=1 \
EKAKO_TURNSTILE_SITE_KEY=1x00000000000000000000AA \
EKAKO_TURNSTILE_SECRET_KEY=1x0000000000000000000000000000000AA \
python3 manage.py runserver 127.0.0.1:8001
```
Dans le navigateur, tester connexion, inscription, revendeur et commande.
Le widget client envoie un jeton distinct à chaque tentative.
Utiliser uniquement des données de test pour ne pas modifier les stocks réels.

Pour couper le CAPTCHA local, faire Ctrl+C et redémarrer normalement :
```bash
python3 manage.py runserver 127.0.0.1:8001
```

Pour une vraie activation, créer un widget depuis Cloudflare Turnstile,
renseigner les clés chez l'hébergeur, configurer le nom de domaine et tester
le parcours réel sur un environnement de recette.
