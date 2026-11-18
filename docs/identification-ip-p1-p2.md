# eKAKO — Identification IP anti-abus P1 et P2

## Pourquoi
Render place Cloudflare et des proxys devant les applications. `REMOTE_ADDR`
peut désigner un proxy commun, ce qui biaise les limites anti-bruteforce
des connexions et du suivi de commande.

## Choix
`EKAKO_CLIENT_IP_SOURCE=remote` reste la valeur par défaut.
Un mode optionnel `EKAKO_CLIENT_IP_SOURCE=cloudflare` utilise
`CF-Connecting-IP` validé strictement (IPv4 ou IPv6 unique), sinon
`REMOTE_ADDR`. Les en-têtes `X-Forwarded-For` ne sont jamais lus
directement, car une chaîne XFF peut contenir des valeurs ajoutées par
le visiteur.

**Condition de sécurité impérative :** n'activer `cloudflare` que sur
Render et seulement après confirmation que toute requête atteint Django
via le chemin Cloudflare/Render qui remplace ou contrôle l'en-tête
`CF-Connecting-IP`. Une origine directe ou un proxy qui laisse passer
le header du client rendrait ce mode falsifiable. Le drapeau exige
`IS_PRODUCTION=True` et `RENDER_SERVICE_ID`, mais ces variables ne
prouvent pas à elles seules la confiance du réseau.

## Vérification locale
```bash
python3 manage.py check
python3 manage.py test config.tests_client_ip accounts.tests_login_throttle orders.tests_tracking_throttle config.tests_admin_security
python3 manage.py test
```

## Préproduction
- Ne pas activer le mode cloudflare avant revue du chemin de proxy.
- Déployer le code d'abord avec `EKAKO_CLIENT_IP_SOURCE=remote`.
- Vérifier connexion administrateur et recherche normale d'une commande.
- Ne jamais publier des adresses IP brutes dans une route de diagnostic.
- Vérifier le comportement dans les logs/observabilité privée ou les
  mécanismes Render officiels avant d'activer la variable.
- L'activation de `cloudflare` est une modification de configuration
  impliquant un redéploiement. Prévoir une marche arrière via `remote`.

## Documents
- Render : https://render.com/articles/how-render-handles-ddos-attacks
- Cloudflare : https://developers.cloudflare.com/fundamentals/reference/http-headers/
