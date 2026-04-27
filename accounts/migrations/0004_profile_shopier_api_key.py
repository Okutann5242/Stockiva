# Generated manually — shopier_api_key alanı eklendi
# Webhook'tan gelen istekleri doğru kullanıcıya eşleştirmek için kullanılır.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_remove_profile_is_admin_profile_iyzico_token_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='shopier_api_key',
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name='Shopier API Anahtarı',
                help_text='Webhook geldiğinde hangi hesaba ait olduğunu belirler.'
            ),
        ),
        migrations.AddField(
            model_name='profile',
            name='is_admin',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
    model_name='profile',
    name='shopier_webhook_secret',
    field=models.CharField(
        blank=True,
        max_length=255,
        null=True,
        verbose_name='Shopier Webhook Secret',
    ),
),
    ]
