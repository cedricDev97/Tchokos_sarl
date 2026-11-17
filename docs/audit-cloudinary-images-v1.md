# Audit des images Cloudinary eKAKO V1

Cet audit vise les anciennes références d'images conservées dans PostgreSQL
après le passage du stockage local Render à Cloudinary.

## Avant de lancer

Le service **ekako-preproduction** doit avoir `EKAKO_MEDIA_STORAGE=cloudinary`
et ses trois identifiants Cloudinary correctement configurés. Ne jamais
communiquer ces identifiants ou exporter de secrets dans le rapport.

Dans le **Render Shell** du service (pas sur le Mac local) :

```bash
python manage.py audit_cloudinary_images
```

Pour limiter le volume à cinq références :

```bash
python manage.py audit_cloudinary_images --limit 5
```

La commande **ne modifie aucune ligne en base ni aucun fichier Cloudinary**.
Elle effectue uniquement des lectures en base et des consultations de l'API
Cloudinary. Les résultats possibles :

- `OK` : l'identifiant Cloudinary est accessible via l'API Admin.
- `ABSENTE` : Cloudinary a explicitement renvoyé une absence.
- `REFERENCE_INVALIDE` : chemin incompatible avec le stockage eKAKO.
- `ERREUR_API` : impossible de statuer (problème d'authentification,
  de connexion, de quota ou autre) ; **ne pas traiter comme absent**.

Le contrôle concerne les images principales et galeries, même pour les produits
inactifs. Le listing contient SKU, type d'image, statut et chemin du fichier.
Il ne contient pas de données personnelles client ou de secrets.

## Après l'audit

Ne corriger automatiquement aucune référence. Vérifier la disponibilité des
originaux, puis utiliser le Dashboard eKAKO pour remplacer explicitement les
photos manquantes par SKU et couleur, après sauvegarde PostgreSQL. Les anciennes
références ne sont pas migrées automatiquement. Vérifier l'URL publique après
chaque remplacement.

Tests locaux sans aucun appel Cloudinary réel :

```bash
python3 manage.py test catalog.tests_audit_cloudinary_images
```
