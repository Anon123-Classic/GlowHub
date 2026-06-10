from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salon', '0013_notification_queue'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(
                fields=['user', 'status', 'date'],
                name='apt_user_status_date_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(
                fields=['user', 'date', 'time'],
                name='apt_user_date_time_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(
                fields=['date', 'status'],
                name='apt_date_status_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(
                fields=['assigned_staff', 'date', 'status'],
                name='apt_staff_date_status_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='blockedtimeslot',
            index=models.Index(
                fields=['date'],
                name='blocked_date_idx',
            ),
        ),
    ]
