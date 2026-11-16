# eKAKO V1 — Préproduction Render (initialement sans commandes)

## État de départ
- Dépôt : `cedricDev97/Tchokos_sarl`
- Branche cible : `ekako-stabilisation-v1`
- Le site utilise Django 6, PostgreSQL, Gunicorn et WhiteNoise.
- **Ne jamais déployer les données de `db_whatsapp_recette.sqlite3`.**
- Démarrer avec `EKAKO_CHECKOUT_MODE=closed` et un catalogue neuf de préproduction.
- Les comptes administrateurs doivent être créés séparément sur la base de préproduction.

## Services à créer dans Render

1. Base **Render Postgres** payante, région identique au service web.
   Le plan 1 Go RAM affiché sur Render est à 19 $/mois à la rédaction.
   Définir un nom, un utilisateur, un mot de passe et des sauvegardes testées.
2. Service **Web Service > Python**, dépôt `cedricDev97/Tchokos_sarl`,
   branche `ekako-stabilisation-v1`, calcul **Starter** (7 $/mois).
   - Build command : `bash render-build.sh`
   - Pre-deploy command : `python manage.py migrate --noinput`
     (disponible sur un service web payant)
   - Start command : `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60 --access-logfile - --error-logfile -`
   - Health check path : `/healthz/`
   - Deploy automatique : recommandé de le désactiver jusqu'à validation de la recette.
3. **Disque persistant** pour les images produit : monter un disque sur
   `/opt/render/project/src/media` (minimum recommandé : 1 Go pour l'essai).
   Les images stockées ailleurs que sur ce chemin ne survivent pas aux redéploiements.
   Le disque Render ne peut pas être partagé avec un cron job.
   Prévoir une copie de sauvegarde externe et une vérification de restauration.
4. **Cron Job** (avant ouverture des commandes WhatsApp), même dépôt/branche et région :
   - Schedule : `*/5 * * * *` (UTC)
   - Command : `python manage.py expire_whatsapp_reservations`
   - Même accès PostgreSQL et `DJANGO_SECRET_KEY`, avec les variables de
     configuration correspondantes. Aucun accès disque média nécessaire.
   - Lancer un essai manuel, puis contrôler les journaux d'exécution.
   - Ne définir `EKAKO_WHATSAPP_EXPIRATION_JOB_READY=1` sur le web
     **qu'après** avoir observé le bon fonctionnement du job.

## Configuration Render : variables du service web

Définir les valeurs dans **Environment**, pas dans GitHub.

| Variable | Valeur |
| --- | --- |
| `EKAKO_ENV` | `production` (active DEBUG=False) |
| `EKAKO_DB_ENGINE` | `postgresql` |
| `EKAKO_DB_NAME` | nom réel de la base Render |
| `EKAKO_DB_USER` | utilisateur PostgreSQL Render |
| `EKAKO_DB_PASSWORD` | mot de passe PostgreSQL Render, secret |
| `EKAKO_DB_HOST` | nom d'hôte interne PostgreSQL Render |
| `EKAKO_DB_PORT` | `5432`, sauf indication contraire |
| `EKAKO_DB_SSLMODE` | `require`, vérifier la compatibilité TLS de l'URL interne |
| `DJANGO_SECRET_KEY` | clé aléatoire robuste, secrète, >= 50 caractères |
| `DJANGO_ALLOWED_HOSTS` | nom d'hôte HTTPS réel sans `https://` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://<nom-d-hote-reel>` |
| `DJANGO_TRUST_X_FORWARDED_PROTO` | `1` seulement si l'en-tête HTTPS provient du reverse proxy de confiance |
| `EKAKO_CHECKOUT_MODE` | **`closed` initialement** |
| `EKAKO_MAINTENANCE` | `0` pour vérifier la vitrine (checkout demeure fermé) |
| `EKAKO_TURNSTILE_ENABLED` | `1` |
| `EKAKO_TURNSTILE_SITE_KEY` | vraie clé publique Turnstile, jamais de clé de test |
| `EKAKO_TURNSTILE_SECRET_KEY` | vraie clé privée Turnstile, secret |
| `EKAKO_TURNSTILE_HOSTNAME` | nom d'hôte du site sur lequel Turnstile est autorisé |
| `EKAKO_WHATSAPP_NUMBER` | numéro professionnel réel au format `2376XXXXXXXX` |
| `EKAKO_WHATSAPP_EXPIRATION_JOB_READY` | `0` ou absent en préproduction |

**Important :** le code de eKAKO utilise les variables `EKAKO_DB_*` individuelles ;
une seule `DATABASE_URL` ne configure pas cette version du projet.
Ne pas définir `EKAKO_SQLITE_TEST_DB=1` en production.

## Vérifications avant lancement

- `python manage.py check --deploy` avec les variables Render.
- `GET /healthz/` = 200 en cas de base disponible ; 503 sinon.
- Vérifier `collectstatic` et les images uploadées sur disque persistant.
- Tester l'accès HTTPS public, CSRF, login/logout, et refus d'accès aux API internes.
- Créer un administrateur de préproduction via Render Shell : `python manage.py createsuperuser`.
- Tester la boutique et le catalogue avec quelques articles de **préproduction**.
- Vérifier les vraies clés Turnstile en contexte HTTPS.
- Tester le mécanisme d'expiration en conditions PostgreSQL (y compris concurrence et erreurs).
- Installer les sauvegardes automatiques PostgreSQL et les copies média hors serveur ;
  effectuer un test réel de restauration.
- Contrôler les procédures de disponibilité fournisseur, gestion des retours,
  remboursement après paiement, assistance client, délais et tarification livraison.
- Ne passer à `EKAKO_CHECKOUT_MODE=whatsapp` qu'après validation de cette liste
  et de `EKAKO_WHATSAPP_EXPIRATION_JOB_READY=1`.

## Coûts indicatifs hors domaine, taxes et dépassements

- Web starter : 7 $/mois
- PostgreSQL 1 Go RAM : 19 $/mois
- Cron : à partir de 1 $/mois
- Disque 1 Go : 0,25 $/mois
- **Base estimée : 27,25 $/mois** avant sauvegardes externes et extras

Consulter la tarification en vigueur : https://render.com/pricing
