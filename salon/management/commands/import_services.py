from django.core.management.base import BaseCommand
from salon.models import Service


class Command(BaseCommand):
    help = 'Import a predefined list of salon services into the database.'

    SERVICE_DATA = [
        {'name': 'Ladies Hair Braiding', 'price': 3500, 'duration_text': '4 Hours', 'category': 'hair'},
        {'name': 'Knotless Braids', 'price': 4500, 'duration_text': '5 Hours', 'category': 'hair'},
        {'name': 'Men Haircut & Fade', 'price': 800, 'duration_text': '45 Minutes', 'category': 'barber'},
        {'name': 'Kids Haircut', 'price': 500, 'duration_text': '30 Minutes', 'category': 'barber'},
        {'name': 'Dreadlocks Retwist', 'price': 2500, 'duration_text': '3 Hours', 'category': 'hair'},
        {'name': 'Wig Installation', 'price': 2500, 'duration_text': '2 Hours', 'category': 'hair'},
        {'name': 'Hair Coloring', 'price': 4000, 'duration_text': '2.5 Hours', 'category': 'hair'},
        {'name': 'Facial Treatment', 'price': 3000, 'duration_text': '1.5 Hours', 'category': 'facial'},
        {'name': 'Manicure', 'price': 1200, 'duration_text': '1 Hour', 'category': 'nails'},
        {'name': 'Pedicure', 'price': 1500, 'duration_text': '1 Hour 15 Min', 'category': 'nails'},
        {'name': 'Gel Polish', 'price': 1800, 'duration_text': '1 Hour', 'category': 'nails'},
        {'name': 'Bridal Makeup', 'price': 6000, 'duration_text': '2 Hours', 'category': 'makeup'},
        {'name': 'Normal Makeup', 'price': 3500, 'duration_text': '1.5 Hours', 'category': 'makeup'},
        {'name': 'Hair Wash & Blow Dry', 'price': 1500, 'duration_text': '1 Hour', 'category': 'hair'},
        {'name': 'Relaxing & Treatment', 'price': 3500, 'duration_text': '2 Hours', 'category': 'spa'},
        {'name': 'Beard Grooming', 'price': 700, 'duration_text': '30 Minutes', 'category': 'barber'},
        {'name': 'Eyebrow Shaping', 'price': 500, 'duration_text': '20 Minutes', 'category': 'barber'},
        {'name': 'Steam & Spa Treatment', 'price': 4500, 'duration_text': '2 Hours', 'category': 'spa'},
        {'name': 'Massage Therapy', 'price': 5000, 'duration_text': '1 Hour', 'category': 'spa'},
        {'name': 'Acrylic Nails', 'price': 2500, 'duration_text': '2 Hours', 'category': 'nails'},
    ]

    def parse_duration(self, duration_text):
        text = duration_text.lower().replace('minutes', 'minute').replace('hours', 'hour').replace('mins', 'minute').replace('min', 'minute')
        parts = text.split()
        if 'hour' in parts:
            try:
                hours = float(parts[0])
                return int(hours * 60)
            except ValueError:
                pass
        if 'minute' in parts:
            try:
                minutes = float(parts[0])
                return int(minutes)
            except ValueError:
                pass
        # Handle composite time like '1 hour 15 minute'
        total = 0
        i = 0
        while i < len(parts):
            try:
                value = float(parts[i])
                if i + 1 < len(parts) and parts[i + 1].startswith('hour'):
                    total += int(value * 60)
                    i += 2
                    continue
                if i + 1 < len(parts) and parts[i + 1].startswith('minute'):
                    total += int(value)
                    i += 2
                    continue
            except ValueError:
                pass
            i += 1
        return total or 0

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        for service_data in self.SERVICE_DATA:
            duration = self.parse_duration(service_data['duration_text'])
            defaults = {
                'description': f"{service_data['name']} service.",
                'price': service_data['price'],
                'duration': duration,
                'category': service_data['category'],
                'is_active': True,
            }
            service, created_flag = Service.objects.update_or_create(
                name=service_data['name'],
                defaults=defaults,
            )
            if created_flag:
                created += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'Service import complete: {created} created, {skipped} updated.'
        ))
