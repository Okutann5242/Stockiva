from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    cost_price = models.FloatField(default=0)
    selling_price = models.FloatField(default=0)
    stock_quantity = models.IntegerField(default=0)
    commission_rate = models.FloatField(default=15.0, verbose_name="Pazar Yeri Komisyon Oranı (%)") 
    shipping_cost = models.FloatField(default=40.0, verbose_name="Kargo Ücreti (₺)")
    monthly_revenue_goal = models.FloatField(default=100000.0, verbose_name="Aylık Ciro Hedefi (₺)")
    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="Telefon Numarası")
    two_factor_auth = models.BooleanField(default=False, verbose_name="İki Adımlı Doğrulama")
    email_notifications = models.BooleanField(default=True, verbose_name="E-Posta Bildirimleri")
    def __str__(self):
        return self.name

from django.db import models

class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE) 
    quantity = models.FloatField()
    price = models.FloatField(default=0)
    date = models.DateField()

    def __str__(self):
        return f"{self.product} - {self.date}"