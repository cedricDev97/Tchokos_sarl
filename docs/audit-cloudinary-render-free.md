# eKAKO : audit Cloudinary sur Render Free (sans Shell)

Le service Render Free n'a pas accès à Shell ou SSH. Une URL interne de
diagnostic permet de déclencher la **commande de lecture seule** existante
depuis une session eKAKO authentifiée en tant que superutilisateur.

## Sécurité

- Endpoint `GET /api/admin/cloudinary-audit/?limit=25`.
- **Superutilisateur Django actif et authentifié obligatoire** : autres
  utilisateurs renvoyés à la page de connexion.
- Le rapport ne contient aucune clé d'API Cloudinary ni donnée personnelle.
- Cache désactivé, indexation découragée.
- Limite 1 à 100 références par requête ; la commande ne modifie rien.
- Répond 503 si Cloudinary n'est pas activé.
- L'URL est uniquement un outil de préproduction. Ne pas communiquer sa
  réponse publiquement : les chemins internes des fichiers sont visibles.

## Recette

1. Local : `python3 manage.py test catalog.tests_cloudinary_audit_http catalog.tests_audit_cloudinary_images`.
2. Déployer `ekako-stabilisation-v1` dans le service Render de préproduction.
3. Se connecter au compte superutilisateur eKAKO en HTTPS.
4. Ouvrir dans le même navigateur :
   `https://ekako-preproduction.onrender.com/api/admin/cloudinary-audit/?limit=25`
5. Lire `report` et `warning`. Ne pas modifier les images sans avoir
   identifié les originaux.
6. Pour un audit plus large : `?limit=100`. L'outil utilise le premier lot
   de références uniquement, **ce n'est pas une pagination**.

Un refus de connexion ou une redirection signifie que le compte n'a pas les
droits superutilisateur Django. Ne pas abaisser les protections pour contourner
ce refus.
