"""Audit en lecture seule des références d'images eKAKO sur Cloudinary.

Ne téléverse, ne supprime et ne modifie rien. Utiliser sur Render Shell avec
la configuration Cloudinary du service de préproduction.
"""
from collections import Counter

import cloudinary.api
from cloudinary.exceptions import NotFound
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog.models import Product, ProductGalleryImage
from config.cloudinary_storage import CloudinaryMediaStorage


class Command(BaseCommand):
    help = "Vérifie les images principales et galeries dans Cloudinary (lecture seule)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Limiter le nombre de références contrôlées (0 = toutes)."
        )

    def handle(self, *args, **options):
        if settings.EKAKO_MEDIA_STORAGE != "cloudinary":
            raise CommandError(
                "Audit distant refusé : EKAKO_MEDIA_STORAGE doit valoir cloudinary."
            )
        limit = options["limit"]
        if limit < 0:
            raise CommandError("--limit ne peut pas être négatif.")
        # Initialise le SDK sans exposer les identifiants dans les logs.
        CloudinaryMediaStorage()

        counts = Counter()
        examined = 0
        failures = []
        seen = {}

        sources = (
            (p.sku, "principale", p.image.name)
            for p in Product.objects.exclude(image="").exclude(image__isnull=True)
                .order_by("sku").only("sku", "image").iterator()
        )
        gallery = (
            (g.product.sku, "galerie", g.image.name)
            for g in ProductGalleryImage.objects.select_related("product")
                .order_by("product__sku", "id").iterator()
        )

        from itertools import chain
        for sku, kind, name in chain(sources, gallery):
            if limit and examined >= limit:
                break
            examined += 1
            try:
                public_id, _ = CloudinaryMediaStorage._asset(name)
            except Exception:
                status = "REFERENCE_INVALIDE"
            else:
                if public_id in seen:
                    status = seen[public_id]
                else:
                    try:
                        cloudinary.api.resource(public_id, resource_type="image")
                    except NotFound:
                        status = "ABSENTE"
                    except Exception:
                        status = "ERREUR_API"
                    else:
                        status = "OK"
                    seen[public_id] = status

            counts[status] += 1
            # SKU et identifiant du fichier uniquement : aucune donnée client,
            # clé Cloudinary ou image n'est écrite dans le rapport.
            if status != "OK":
                failures.append((sku, kind, status, name))
            self.stdout.write(f"{status} | SKU={sku} | {kind} | {name}")

        self.stdout.write("")
        self.stdout.write(
            "BILAN | références={} | OK={} | ABSENTE={} | REFERENCE_INVALIDE={} | ERREUR_API={}"
            .format(examined, counts["OK"], counts["ABSENTE"],
                    counts["REFERENCE_INVALIDE"], counts["ERREUR_API"])
        )
        if failures:
            self.stdout.write(
                "Audit uniquement : aucune correction automatique ni suppression effectuée."
            )
        if counts["ERREUR_API"]:
            self.stderr.write(
                "Certaines vérifications ont échoué côté API : ne pas les interpréter comme des images absentes."
            )
