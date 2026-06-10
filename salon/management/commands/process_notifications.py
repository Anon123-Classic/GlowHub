import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import F, Q
from django.utils import timezone

from salon.models import NotificationLog
from salon.utils import send_booking_confirmation, send_payment_confirmation


NOTIFICATION_SENDERS = {
    'booking_confirmation': send_booking_confirmation,
    'payment_successful': send_payment_confirmation,
}


class Command(BaseCommand):
    help = 'Process queued notification emails.'

    def add_arguments(self, parser):
        parser.add_argument('--watch', action='store_true')
        parser.add_argument('--poll-interval', type=float, default=2.0)
        parser.add_argument('--batch-size', type=int, default=20)
        parser.add_argument('--max-attempts', type=int, default=5)

    def handle(self, *args, **options):
        while True:
            processed = self.process_batch(
                batch_size=options['batch_size'],
                max_attempts=options['max_attempts'],
            )
            if not options['watch']:
                self.stdout.write(self.style.SUCCESS(
                    f'Processed {processed} notification(s).'
                ))
                return
            if processed == 0:
                time.sleep(options['poll_interval'])

    def process_batch(self, batch_size, max_attempts):
        now = timezone.now()
        stale_before = now - timedelta(minutes=10)
        eligible = NotificationLog.objects.filter(
            notification_type__in=NOTIFICATION_SENDERS,
            attempts__lt=max_attempts,
            available_at__lte=now,
        ).filter(
            Q(status__in=['pending', 'failed']) |
            Q(status='processing', processing_started_at__lt=stale_before)
        ).order_by('available_at', 'pk')[:batch_size]

        processed = 0
        for notification_id in list(eligible.values_list('pk', flat=True)):
            claimed = NotificationLog.objects.filter(
                pk=notification_id,
                attempts__lt=max_attempts,
            ).filter(
                Q(status__in=['pending', 'failed']) |
                Q(status='processing', processing_started_at__lt=stale_before)
            ).update(
                status='processing',
                processing_started_at=now,
                attempts=F('attempts') + 1,
            )
            if not claimed:
                continue

            notification = NotificationLog.objects.select_related(
                'appointment__service',
                'appointment__user',
            ).get(pk=notification_id)
            sender = NOTIFICATION_SENDERS[notification.notification_type]
            sent = sender(
                notification.appointment,
                notification=notification,
            )
            if not sent:
                notification.refresh_from_db(fields=['attempts'])
                delay_minutes = min(2 ** notification.attempts, 60)
                NotificationLog.objects.filter(pk=notification.pk).update(
                    available_at=timezone.now() + timedelta(minutes=delay_minutes)
                )
            processed += 1

        return processed
