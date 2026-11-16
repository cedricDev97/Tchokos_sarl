# eKAKO V1 — Images produits via Cloudinary

## Objectif
Enregistrer les fichiers des champs `catalog.Product.image` et
`catalog.ProductGalleryImage.image` hors du disque éphémère Render.
Les fichiers statiques restent gérés par WhiteNoise. Pas de migration
PostgreSQL ni de changement des champs ImageField.

## Configuration
Dans Render > ekako-preproduction > Environment :
- `CLOUDINARY_CLOUD_NAME` — valeur du tableau de bord Cloudinary
- `CLOUDINARY_API_KEY` — clé API, ne pas committer
- `CLOUDINARY_API_SECRET` — secret API, ne pas committer
- `EKAKO_MEDIA_STORAGE=cloudinary` — active le stockage distant

Le paramètre `EKAKO_MEDIA_STORAGE` est `local` par défaut et peut
être fixé à `cloudinary` en développement pour effectuer une recette dédiée.
Sans les trois valeurs, Django refuse le démarrage si le stockage distant est activé.

## Séquence de déploiement
1. Enregistrer les variables Cloudinary et le drapeau `EKAKO_MEDIA_STORAGE=cloudinary`
   sur le service Render, avec *Save only*.
2. Déployer manuellement le dernier commit de `ekako-stabilisation-v1`.
3. Vérifier `/healthz/` = 200, la boutique, les CSS et le Django admin.
4. Remplacer la photo du produit de préproduction déjà créé : son ancien fichier
   résidait sur le stockage local Render et n'est pas transféré automatiquement.
5. Vérifier `/api/products/` : `image_url` commence par
   `https://res.cloudinary.com/` et l'image est visible dans la boutique.
6. Déployer manuellement à nouveau ; vérifier que l'image reste visible.

En cas d'échec du déploiement, ne pas activer le checkout. Lire les
journaux Build/Runtime, notamment les erreurs liées aux secrets
et à la connexion Cloudinary. Rétablir `EKAKO_MEDIA_STORAGE=local`
n'est pas une récupération des anciennes images : les références Cloudinary
créées pendant la recette nécessitent le stockage distant.

Ne jamais communiquer les clés ou la Cloudinary URL avec ses identifiants.
Surveiller les quotas et prévoir sauvegarde/export des médias avant lancement.
