# Generated manually — default değer düzeltmeleri
# shipping_cost: 40.0 → 0.0
# commission_rate: 15.0 → 0.0
# accounts/Profile: shopier_api_key alanı eklendi

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_product_cost_price_alter_product_selling_price_and_more'),
    ]

    operations = [
        # DÜZELTME: Eski default'lar (40₺ kargo, %15 komisyon) küçük fiyatlı
        # ürünlerde kârı otomatik eksilere çekiyordu. Artık 0.0 başlıyor,
        # kullanıcı kendi ürününe göre manuel giriyor.
        migrations.AlterField(
            model_name='product',
            name='shipping_cost',
            field=models.FloatField(
                default=0.0,
                verbose_name='Kargo Ücreti (₺)',
                help_text='Varsayılan 0. Ürüne göre manuel girin.'
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='commission_rate',
            field=models.FloatField(
                default=0.0,
                verbose_name='Pazar Yeri Komisyon Oranı (%)',
                help_text='Varsayılan 0. Ürüne göre manuel girin.'
            ),
        ),
    ]
