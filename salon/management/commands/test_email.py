from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = "Send a test email to verify Gmail SMTP configuration"

    def add_arguments(self, parser):
        parser.add_argument("email", nargs="?", help="Recipient email address")

    def handle(self, *args, **options):
        recipient = options["email"]
        if not recipient:
            recipient = settings.EMAIL_HOST_USER
            if not recipient:
                raise CommandError(
                    "No recipient provided and EMAIL_HOST_USER is not set. "
                    "Usage: python manage.py test_email you@example.com"
                )

        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            self.stdout.write(self.style.WARNING(
                "WARNING: EMAIL_HOST_USER or EMAIL_HOST_PASSWORD is empty in .env"
            ))
            if not settings.EMAIL_HOST_USER:
                self.stdout.write(self.style.WARNING("  EMAIL_HOST_USER is not set"))
            if not settings.EMAIL_HOST_PASSWORD:
                self.stdout.write(self.style.WARNING("  EMAIL_HOST_PASSWORD is not set"))
            self.stdout.write(self.style.WARNING("  Update your .env file and try again."))
            return

        self.stdout.write(f"EMAIL_BACKEND:    {settings.EMAIL_BACKEND}")
        self.stdout.write(f"EMAIL_HOST:        {settings.EMAIL_HOST}")
        self.stdout.write(f"EMAIL_PORT:        {settings.EMAIL_PORT}")
        self.stdout.write(f"EMAIL_USE_TLS:     {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"EMAIL_HOST_USER:   {settings.EMAIL_HOST_USER}")
        self.stdout.write(
            f"EMAIL_HOST_PASSWORD: {'***set***' if settings.EMAIL_HOST_PASSWORD else '(empty)'}"
        )
        self.stdout.write(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Recipient:         {recipient}")
        self.stdout.write("")

        subject = "GlowHub — Test Email"
        message = (
            "This is a test email from GlowHub.\n\n"
            "If you received this, your Gmail SMTP configuration is working correctly."
        )
        html_message = (
            "<p>This is a test email from <strong>GlowHub</strong>.</p>"
            "<p>If you received this, your Gmail SMTP configuration is working correctly.</p>"
        )

        self.stdout.write("Sending test email...")
        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL,
                [recipient],
                html_message=html_message,
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Test email sent to {recipient}"))
        except Exception as e:
            raise CommandError(f"Failed to send email: {e}")
