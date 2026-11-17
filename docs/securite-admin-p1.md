# eKAKO V1 — P1 Protection des comptes administrateurs

## Objectif
Sécuriser l'interface Django `/admin/` sans changer la connexion eKAKO
(`/api/admin/login/`) déjà dotée de contrôles CAPTCHA et anti-bruteforce.

## Changements
- Middleware `DjangoAdminLoginThrottleMiddleware` : 5 tentatives échouées
  sur le couple IP/identifiant ou 20 par IP sur 15 minutes, via les compteurs
  PostgreSQL existants. Une erreur CSRF 403 n'est pas comptée.
- Les accès aux administrateurs Django `auth.User` et `auth.Group` sont
  réservés aux **superutilisateurs actifs**, y compris si un agent dispose
  directement des permissions Django `auth.change_user` ou `auth.change_group`.
  Cette mesure empêche un agent de s'attribuer le groupe `super_admin`
  via l'administration native.
- Les superutilisateurs conservent l'administration des comptes et groupes.
- Aucun schéma ou donnée commerciale n'est modifié.

## Vérifications locales
```bash
python3 manage.py check
python3 manage.py test config.tests_admin_security accounts.tests_login_throttle
```
Effectuer ensuite les tests de non-régression applicatifs.

## Vérifications préproduction
- Connexion normale d'un superutilisateur au Django Admin.
- Un agent staff non-superuser ne peut pas accéder à la gestion Users/Groups.
- Le Dashboard eKAKO et les permissions métier restent fonctionnels.
- **Ne pas provoquer volontairement cinq échecs de connexion sur Render** :
  réaliser ce test uniquement sur la base de test locale.

## Limites
Le throttling se base sur `REMOTE_ADDR`. Si Render communique uniquement
l'IP du proxy commun, les connexions d'utilisateurs différents pourraient
partager les compteurs IP. Vérifier cette hypothèse avant une ouverture large,
sans faire confiance à un en-tête `X-Forwarded-For` non validé.
