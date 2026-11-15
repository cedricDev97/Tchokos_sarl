# eKAKO V1 — Commandes finalisées via WhatsApp

## Portée

Cette V1 conserve la création de commande et le calcul des prix **sur le serveur Django**.
Le client clique sur un lien wa.me prérempli et doit lui-même envoyer le message. **Aucun message
WhatsApp n'est transmis automatiquement, aucune API de paiement n'est appelée.**

1. Le client prépare son panier et renseigne ses coordonnées.
2. Django enregistre une commande **non payée** et décrémente provisoirement la disponibilité.
3. L'interface affiche le récapitulatif, le numéro, le délai et le bouton WhatsApp.
4. Le client envoie le message depuis WhatsApp ; le conseiller vérifie le fournisseur.
5. Dans le Dashboard, le gestionnaire ayant le droit `payments` confirme le mode convenu
   (MTN Mobile Money, Orange Money ou COD sous réserve d'acceptation).
6. Pour Mobile Money, l'encaissement est **vérifié manuellement** sur le compte marchand,
   puis marqué « payé » avec référence réelle et confirmation explicite.
7. Les règles de sourcing et de livraison continuent à s'appliquer.

**Attention :** une demande créée n'est pas une vente encaissée. L'ouverture de WhatsApp
ne prouve pas que le message a été envoyé. Une capture d'écran d'un versement n'est pas
une preuve de réception des fonds.

## Variables d'environnement

- `EKAKO_CHECKOUT_MODE=closed` : bloque le Checkout (valeur par défaut en production).
- `EKAKO_CHECKOUT_MODE=sandbox` : recettes locales historiques uniquement, **interdit en production**.
- `EKAKO_CHECKOUT_MODE=whatsapp` : active le parcours avec réservation temporaire.
- `EKAKO_WHATSAPP_NUMBER=2376XXXXXXXX` : numéro **professionnel** destinataire (chiffres uniquement).
- `EKAKO_WHATSAPP_RESERVATION_MINUTES=60` : durée des réservations non confirmées, de 15 à 240 min.
- `EKAKO_WHATSAPP_EXPIRATION_JOB_READY=1` : garde-fou de production à renseigner
  **uniquement après** déploiement et vérification réelle de la tâche planifiée.

Le mode WhatsApp ne peut démarrer sans numéro professionnel configuré ; aucun numéro n'est enregistré en dur.
L'environnement de production continue d'exiger PostgreSQL, Turnstile et les autres secrets déjà prévus.

## Expiration

Exécuter régulièrement (p. ex. toutes les cinq minutes) dans le même environnement
Django/BD que le site :

```bash
python3 manage.py expire_whatsapp_reservations
```

La commande expire les demandes WhatsApp sans paiement enregistré et sans validation
fournisseur, restitue les stocks et journalise l'annulation. Elle est **idempotente**.
Elle ne rembourse pas un paiement tardif : ce cas exige un rapprochement manuel.

Les commandes dont le fournisseur a déjà confirmé/collecté les articles ne sont pas
annulées automatiquement. Le responsable doit les examiner et régler les réservations
avec le commerçant. Une commande COD confirmée ne conserve pas de délai d'expiration :
elle nécessite une supervision opérationnelle des abandons.

Avant toute mise en production, installer la tâche planifiée et tester le processus
d'expiration/restauration, ainsi que la concurrence sur PostgreSQL.

## Tests sans toucher aux commandes réelles

```bash
python3 manage.py check
python3 manage.py makemigrations --check --dry-run
python3 manage.py test orders.tests_checkout_stabilisation -v 2
```

Django crée et détruit sa propre base de test. Prévoir une sauvegarde avant
l'application de la migration `orders.0012` à une base existante.
Ne jamais tester le Checkout en mode WhatsApp sur les stocks locaux de production.

## Mise en ligne

Ne pas passer `EKAKO_CHECKOUT_MODE=whatsapp` en production avant :
- numéro professionnel et politique de gestion des conversations validés ;
- cron d'expiration réellement opérationnel ;
- tests sur base de recette, incluant messages abandonnés et paiements tardifs ;
- conditions de remboursement, disponibilité fournisseurs et tarification livraison validées ;
- contrôles d'accès, CSRF, anti-bot, HTTPS et supervision approuvés.
