# Tchokos SARL — PROJECT LOG

Dernière mise à jour: 2026-01-26

## Objectif
Créer un site e-commerce (acheteur simple + revendeur) pour l’influenceur Tchokos :
- Catalogue produits + variantes (tailles)
- Stock réel par taille (admin)
- Panier + checkout
- Suivi commande
- Dashboard admin (KPIs + gestion statut)
- Paiement Mobile Money (plus tard)

---

## Stack / Structure
- Django 6.0.1
- Python 3.13 (Mac)
- DB: SQLite (db.sqlite3)
- Apps:
  - `storefront` (pages + templates)
  - `catalog` (produits/variantes/stock)
  - `orders` (commandes + items + tracking + dashboard API)

---

## Frontend (Template / Maquette)
- Maquette validée : **V5 – design V6 (Apple Light) v4**
- Fichiers:
  - Template: `templates/storefront/index.html`
  - CSS: `static/assets/app.css`
  - JS: `static/assets/app.js`

### Navigation
Onglets: Boutique / Revendeur / Suivi / Dashboard

### Point important
- Stock affiché = **stock DB** (Variant.stock_qty), plus de “stock aléatoire” localStorage.
- Track UI corrigé + wrapper possible (`track-wrap`) pour bordures.

---

## Modèles Django

### catalog
- `Product` (sku, brand, name, category, description, retail_price, reseller_price, reseller_moq, ...)
- `Size` (value)
- `Variant` (product FK, size FK, stock_qty)

### orders
- `Order`:
  - order_no (unique), status (`received`, `preparing`, `shipped`, `delivered`)
  - customer_name, customer_phone, city, quarter, address
  - pay_method, shipping_fee, subtotal, total
  - created_at
- `OrderItem`:
  - order FK, variant FK
  - sku, product_name, size_value
  - unit_price, qty, line_total

---

## API Endpoints (OK)

### Catalogue
- `GET /api/products/`  
  Retourne les produits + variantes + stock par taille.

### Checkout (réel)
- `POST /api/checkout/`  
  - Vérifie stock en transaction
  - Crée `Order` + `OrderItem`
  - Décrémente `Variant.stock_qty`
  - Retourne `{ ok:true, orderNo:"TKxxxxxx" }`
- CSRF: OK (token envoyé via `X-CSRFToken`)

### Tracking (réel)
- `GET /api/track/<order_no>/`  
  Retourne les infos commande + items.

### Dashboard (réel)
- `GET /api/admin/stats/?days=ALL|7|30`
  - revenue, orders, avg_order
  - FIX: gère `"ALL"` correctement.
- `GET /api/admin/orders/`
  - liste des 50 dernières commandes
- `POST /api/admin/order/<order_no>/status/`
  - change le statut (received → preparing → shipped → delivered)
  - Branché depuis les boutons du dashboard

---

## Frontend — fonctions clés (OK)
- `loadProductsFromApi()` : charge produits + remplit `stockMap`
- `stockOf(sku,size)` / `totalStockOfSku(sku)` : lisent `stockMap`
- `payNow()` : envoie checkout réel à Django + affiche orderNo + refresh produits/stock
- `renderTrackingFromApi(orderNo)` : affiche suivi réel (fallback money si `fmtMoney` manquant)
- `renderDashboard()` : charge stats + orders + affiche KPIs + table + boutons statut
- Event delegation sur `#ordersTable` pour update status

---

## Ce qui reste à faire (Backlog priorisé)

### Étape 9 — Analytics dashboard
- Remplir:
  - `#topProducts` (best sellers par quantité)
  - `#revenueByZone` (CA par ville/quartier)
- Créer endpoint:
  - `GET /api/admin/analytics/?days=ALL|7|30`

### Étape 10 — Inventaire (stockTable) réel
- Remplir `#stockTable` depuis DB (variants par SKU)
- Alerte stock bas (<3)
- Actions: +1 / -1 stock (admin) via API sécurisée

### Étape 11 — Sécurité / rôles
- Aujourd’hui: rôles “demo” côté front
- À faire: auth Django + permissions admin réelles (ou token admin simple)

### Étape 12 — Paiement OM / MTN réel
- Choix provider (agrégateur ou API direct)
- Créer:
  - “init payment”
  - callback webhook
  - update status payment (paid/unpaid)

---

## Checklist reprise (si conversation perdue)
1) Lancer env + serveur:
   - `source .venv/bin/activate`
   - `python manage.py runserver`
2) Vérifier API:
   - `/api/products/`
   - `/api/checkout/` (POST)
   - `/api/track/TKxxxxxx/`
   - `/api/admin/stats/?days=7`
   - `/api/admin/orders/`
   - `/api/admin/order/TKxxxxxx/status/` (POST)
3) Continuer: Étape 9 (analytics)

---

## Notes / Erreurs résolues
- `TemplateDoesNotExist`: corrigé par placement templates + settings TEMPLATES DIRS
- `include not defined`: import `include` dans `config/urls.py`
- `No module named catalog.urls`: création `catalog/urls.py`
- Dashboard JSON parse `<` : causé par `days=ALL` non géré → fix backend stats
- Update status 404 : route manquante → ajout `admin/order/<order_no>/status/`

## 2026-01-27 — Onboarding Revendeur (Modal Apple + API Django)

### ✅ Avancement
- Maquette validée : **V5 + design V6 Apple Light**
- Django projet `tchokos_sarl` OK (templates + static OK).
- Modal "Devenir revendeur" : **s’ouvre OK**.
- Bug JS bloquant résolu : **app.js était inclus 2 fois** → causait `SyntaxError: duplicate variable 'query'` → aucun event ne marchait.

### 🔧 Correctifs techniques faits
- Suppression du double include de `static/assets/app.js` dans le template (ne garder qu’un seul).
- Event minimal ajouté pour ouvrir le modal via `#applyResellerBtn` → `#resellerModal`.

### 🧩 Feature en cours : App Django `accounts` (revendeur onboarding)
Objectif :
- Un utilisateur connecté (ex: `client1`) peut soumettre une demande revendeur.
- Le backend stocke la demande avec statut (`none/pending/approved/rejected`).
- Le frontend affiche le statut et empêche la confusion.

Statut actuel :
- App `accounts` créée et ajoutée à `INSTALLED_APPS`.
- Route incluse dans `config/urls.py` :
  - `path("api/", include("accounts.urls")),`

### ❌ Problèmes rencontrés (en cours de correction)
- Erreurs imports dans `accounts/views.py` :
  - `NameError: require_http_methods is not defined`
  - `NameError: require_POST is not defined`
➡️ Solution :
- Ajouter les imports suivants dans `accounts/views.py` :
  - `from django.views.decorators.http import require_http_methods, require_POST`
  - (ou supprimer `@require_POST` et utiliser seulement `@require_http_methods(["POST"])`)

### 📌 Next steps (ordre exact)
1) Fix imports `accounts/views.py` → relancer `runserver` sans erreur.
2) Ajouter le modèle `ResellerApplication` + migrations.
3) Implémenter endpoints:
   - `GET /api/reseller/status/`
   - `POST /api/reseller/apply/`
4) Brancher `submitResellerApplication()` dans `static/assets/app.js`
   - POST JSON vers `/api/reseller/apply/` avec CSRF.
5) Test E2E :
   - `client1` → apply → status = `pending`
   - Admin approuve (temporairement via /admin/) → user passe reseller (après logout/login).
6) (Option pro) Ajouter une page/section Admin pour approuver/refuser sans passer par `/admin/`.


### 28/01/2026
Ajouter des statuts complets : received → preparing → shipped → delivered → canceled → failed
Enregistrer l’historique (qui a changé quoi, quand)
Bloquer certaines transitions (ex: livré → préparation = non)
2) Notifications client (WhatsApp/SMS/email)
Objectif : réduire les “où est ma commande ?”.
À faire :
À la création : envoyer N° commande + résumé
À chaque changement statut : notification automatique
Plus tard : intégration WhatsApp Business / SMS provider
3) Paiement “réel” Orange Money / MTN MoMo (si tu veux)
Objectif : passer du “paiement simulé” à “confirmé”.
À faire :
Créer un modèle PaymentTransaction
Lancer une transaction via provider
Recevoir webhook/callback → marquer paid
Si échec → rollback stock (ou stock réservé)
4) Réservation stock (anti double-vente)
Objectif : éviter de vendre 2 fois la même taille.
À faire :
À checkout : stock “réservé” (15–30 min)
À paiement confirmé : stock “déduit”
Expiration : stock “libéré”
5) Onboarding revendeur (c’est exactement là où on est)
Objectif : transformer un client en revendeur + prix revendeur + MOQ + packs.
À faire :
Demande → pending → validation admin → rôle reseller
UX claire : “Tu es revendeur” + avantages + conditions
6) Admin catalogue complet (images, variantes, prix, promos)
Objectif : gérer produits sans toucher au code.
À faire :
Upload images produit
Variantes (taille/couleur), prix détail/revendeur, MOQ
Promo/coupon simple
7) Sécurité + permissions
Objectif : fermer les trous avant mise en ligne.
À faire :
Protéger endpoints admin (role check)
CSRF ok, CORS/headers
Logs + rate limit sur login + validation inputs
8) Déploiement + domaine + sauvegardes
Objectif : site stable et récupérable si problème.
À faire :
DB prod (Postgres), stockage médias (S3/Cloudinary)
Backup automatique + PROJECT_LOG.md
Monitoring (Sentry) + analytics (Plausible/GA)
Si tu veux avancer “sans erreur”, je te propose qu’on prenne la prochaine étape la plus rentable :
👉 Stock réservé + statuts pro (ça sécurise tout le reste).


# Tchokos SARL — PROJECT_LOG (HANDOFF PROPRE)

**Dernière mise à jour : 2026-01-28**  
**Objectif :** E-commerce “Retail + Revendeur” pour Tchokoss : catalogue, stock réel par tailles, checkout, tracking, dashboard admin, onboarding revendeur.

---

## 0) Résumé (état actuel)

- ✅ UI maquette validée : **V5 + design V6 Apple Light (v4)** (Boutique / Revendeur / Suivi / Dashboard)
- ✅ Catalogue + stock **réel DB** (Variant.stock_qty) exposé via `/api/products/`
- ✅ Checkout **transactionnel** : lock variants, vérif stock, création Order/OrderItem, décrément stock
- ✅ Tracking commande via `/api/track/<order_no>/`
- ✅ Dashboard admin : stats, orders, analytics, inventory + adjust stock + update status
- ✅ Auth API : `/api/admin/me/` + login/logout (session)
- ✅ Onboarding revendeur : apply/status + admin approve/reject via endpoints API (sans passer par /admin)
- ⚠️ Prochaine grosse étape : **pricing revendeur (backend + sécurité MOQ)**

---

## 1) Stack & structure

### Tech
- Django 6.0.1
- Python 3.13 (Mac)
- SQLite : `db.sqlite3`

### Apps
- `storefront` : page home + template principal
- `catalog` : produits/tailles/variantes/stock
- `orders` : commandes + items + checkout + tracking + dashboard endpoints
- `accounts` : auth + revendeur onboarding + endpoints admin approve/reject

### Fichiers clés
- Template : `templates/storefront/index.html`
- Static :
  - CSS : `static/assets/app.css`
  - JS : `static/assets/app.js`
- Log : `PROJECT_LOG.md`

---

## 2) UI / règles d’accès

### Onglets
- Boutique (public)
- Revendeur (seulement role reseller)
- Suivi (public)
- Dashboard (seulement role admin)

### Règles
- Visiteur : voit bouton “Devenir revendeur” → doit être redirigé vers login/création compte
- User connecté : peut postuler revendeur (pending) + suivre statut
- Reseller : accès Packs + prix reseller + MOQ
- Admin : accès Dashboard + **ne doit pas voir** “Devenir revendeur” ni accéder au formulaire

---

## 3) Modèles (DB)

### catalog
- `Product` : `sku, brand, name, category, description, retail_price, reseller_price, reseller_moq, ...`
- `Size` : `value`
- `Variant` : `product(FK), size(FK), stock_qty`

### orders
- `Order` :
  - `order_no` (unique)
  - `status` : `received / preparing / shipped / delivered`
  - client : `customer_name, customer_phone, city, quarter, address`
  - paiement : `pay_method`
  - totaux : `shipping_fee, subtotal, total`
  - `created_at`
- `OrderItem` :
  - `order(FK), variant(FK)`
  - `sku, product_name, size_value, unit_price, qty, line_total`

### accounts
- `ResellerApplication` :
  - `user(FK)`
  - `status` : `pending / approved / rejected`
  - données formulaire
  - timestamps + reviewer

---

## 4) Endpoints (confirmés)

### Catalogue
- `GET /api/products/`

### Checkout / Tracking
- `POST /api/checkout/`
- `GET /api/track/<str:order_no>/`

### Dashboard admin
- `GET /api/admin/stats/?days=ALL|7|30`
- `GET /api/admin/orders/`
- `POST /api/admin/order/<str:order_no>/status/`
- `GET /api/admin/analytics/?days=ALL|7|30`
- `GET /api/admin/inventory/`
- `POST /api/admin/inventory/adjust/`

### Auth (session)
- `GET /api/admin/me/`
- `POST /api/admin/login/`
- `POST /api/admin/logout/`

### Onboarding revendeur
- `GET /api/reseller/status/`
- `POST /api/reseller/apply/`

### Admin approvals (sans /admin Django)
- `GET /api/admin/reseller/applications/`
- `POST /api/admin/reseller/applications/<int:app_id>/approve/`
- `POST /api/admin/reseller/applications/<int:app_id>/reject/`

---

## 5) Front JS — fonctions clés

### Data
- `loadProductsFromApi()` : fetch `/api/products/` → remplit `products` + `stockMap` (stock DB réel)
- `stockOf(sku,size)` / `totalStockOfSku(sku)` : lit `stockMap`

### Checkout
- `payNow()` :
  - valide MOQ (côté UI)
  - valide stock tailles (UI)
  - POST `/api/checkout/`
  - vide panier + reload `/api/products/` pour stock à jour

### Tracking
- `renderTrackingFromApi(orderNo)` : GET `/api/track/<orderNo>/` + affiche résultat

### Dashboard
- `renderDashboard()` :
  - stats + orders + analytics + inventory
  - event delegation pour update status et adjust stock

### Auth UI
- `syncRoleFromBackend()` :
  - GET `/api/admin/me/`
  - met à jour `role` / gates / boutons login/logout / mode retail vs reseller

---

## 6) Checkout API (résumé logique actuelle)

- Parse payload : `customer`, `items`
- `transaction.atomic()`:
  - Génère order_no unique
  - Pour chaque item :
    - lock Variant (`select_for_update`)
    - vérifie `variant.stock_qty >= qty`
    - calcule line_total
  - calcule total = subtotal + shipping_fee
  - crée `Order` + `OrderItem`
  - décrémente `variant.stock_qty`

⚠️ Actuellement `unit_price = product.retail_price` (pricing revendeur à faire)

---

## 7) Onboarding revendeur — flow produit (objectif réel)

### Pourquoi c’est utile pour Tchokoss
- Construire un réseau de revendeurs “officiels”
- Appliquer un prix revendeur + MOQ
- Répartir les ventes (revendeurs commandent en quantité)
- Piloter via dashboard (top produits, zones, stocks)

### Flow
1) Visiteur clique “Devenir revendeur”
   - si pas connecté → login / création compte
2) User connecté → submit application (pending)
3) Admin voit la liste → approve/reject
4) Si approved :
   - `/api/admin/me/` renvoie `role=reseller`
   - l’UI débloque onglet Revendeur + prix reseller + MOQ

### Règles backend
- Admin ne peut pas postuler (403)
- Déjà reseller → ne peut pas re-postuler (400)
- Application pending → pas de re-postulation (400)

---

## 8) Bugs rencontrés (et leçons)

- `TemplateDoesNotExist` → fix config templates + dossier `/templates`
- `include` non importé → fix `from django.urls import path, include`
- `catalog.urls` manquant → création du fichier
- JSON parse error `"<"` → réponse HTML (404/500) → fix route / days param
- 404 update status → route manquante → ajout endpoint
- **Bug critique** : `app.js` inclus 2 fois → “duplicate variable / events morts” → fix : une seule inclusion

---

## 9) Checklist reprise rapide

### Lancer
```bash
source .venv/bin/activate
python3 manage.py runserver
