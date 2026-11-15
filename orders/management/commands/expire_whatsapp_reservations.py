from django.core.management.base import BaseCommand
from orders.whatsapp_reservations import expire_whatsapp_reservations


class Command(BaseCommand):
    help = "Libère les stocks des demandes WhatsApp expirées (à planifier régulièrement)."

    def handle(self, *args, **options):
        count = expire_whatsapp_reservations()
        self.stdout.write(f"Réservations WhatsApp expirées : {count}")
