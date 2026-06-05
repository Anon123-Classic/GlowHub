from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from salon.models import Appointment, NotificationLog
from salon.utils import send_appointment_reminder


class Command(BaseCommand):
    help = 'Send reminder emails for appointments scheduled within the next 24 hours.'

    def handle(self, *args, **options):
        now = timezone.now()
        window_start = now + timedelta(hours=1)
        window_end = now + timedelta(hours=24)

        appointments = Appointment.objects.filter(
            date__gte=window_start.date(),
            date__lte=window_end.date(),
            status__in=['pending', 'approved']
        )

        sent_count = 0
        for appointment in appointments:
            appointment_dt = datetime.combine(appointment.date, appointment.time)
            if timezone.is_naive(appointment_dt):
                appointment_dt = timezone.make_aware(appointment_dt)

            reminder_exists = NotificationLog.objects.filter(
                appointment=appointment,
                notification_type='reminder',
                status='sent'
            ).exists()
            if reminder_exists:
                continue

            if window_start <= appointment_dt <= window_end:
                send_appointment_reminder(appointment)
                sent_count += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent_count} reminder email(s).'))
