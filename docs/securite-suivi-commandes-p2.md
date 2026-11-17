# eKAKO V1 — P2 Protection du suivi de commande

Le suivi `POST /api/track/<order_no>/` accepte un numéro de commande et
le téléphone du client. P2 limite les essais pour réduire les risques
de recherche systématique des commandes et d'accès aux données clients.

## Protections
- 5 tentatives incorrectes par couple adresse REMOTE_ADDR + référence commande,
  ou 20 erreurs par adresse IP en 15 minutes. Réponse 429, `Retry-After`.
- Une recherche valide réinitialise le compteur du couple ciblé uniquement.
- Une référence inconnue compte comme une erreur, tout comme un téléphone erroné.
- Clés HMAC avec espaces de noms propres au suivi, différentes de la connexion.
- Pas de migration : les compteurs existants PostgreSQL sont réutilisés.
- **Aucune modification d'état d'une commande, stock ou paiement.**

## Validation
```bash
python3 manage.py check
python3 manage.py test orders.tests_tracking_throttle
python3 manage.py test
```

Après validation, déploiement manuel sur `ekako-preproduction`, puis une
consultation normale de commande et une recherche erronée (une fois seulement).
Éviter de déclencher un blocage pendant la recette Render.

## Points restant à vérifier
Le service Render pourrait fournir une adresse REMOTE_ADDR de proxy partagée.
Vérifier ce comportement avant généralisation. Ne jamais utiliser
`X-Forwarded-For` sans configuration de proxy fiable.
Les limites freinent les tentatives mais n'éliminent pas tous les risques ;
prévoir un monitoring et, si nécessaire, un CAPTCHA dédié au suivi.
