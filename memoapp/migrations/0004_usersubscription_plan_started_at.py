from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('memoapp', '0003_usersubscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersubscription',
            name='plan_started_at',
            field=models.DateTimeField(default=timezone.now),
        ),
    ]
