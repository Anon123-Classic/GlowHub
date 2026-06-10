import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0012_update_staff_roles_and_specializations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificationlog',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('sent', 'Sent'),
                    ('failed', 'Failed'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='notificationlog',
            name='sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notificationlog',
            name='attempts',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='notificationlog',
            name='available_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='notificationlog',
            name='processing_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notificationlog',
            name='queued_at',
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name='notificationlog',
            index=models.Index(
                fields=['status', 'available_at'],
                name='notification_queue_idx',
            ),
        ),
    ]
