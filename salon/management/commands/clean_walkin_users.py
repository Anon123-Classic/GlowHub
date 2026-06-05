from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from salon.utils import generate_walkin_username


class Command(BaseCommand):
    help = 'Clean up existing walk-in user records — update usernames and clear placeholder emails.'

    def handle(self, *args, **options):
        walkins = User.objects.filter(username__startswith='walkin_')
        cleaned = 0
        skipped = 0

        for user in walkins:
            name = user.first_name or 'walkin'
            new_username = generate_walkin_username(name)

            if new_username == user.username:
                skipped += 1
                continue

            old_username = user.username
            user.username = new_username
            if user.email and 'walkin.local' in user.email:
                user.email = ''
            user.save()
            cleaned += 1
            self.stdout.write(f'  {old_username} -> {new_username}')

        self.stdout.write(self.style.SUCCESS(
            f'Done: {cleaned} walk-in users cleaned, {skipped} already clean.'
        ))
