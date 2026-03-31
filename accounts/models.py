from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    monthly_revenue_goal = models.FloatField(default=100000.0, verbose_name="Aylık Ciro Hedefi")
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    two_factor_auth = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    

    def __str__(self):
        return self.user.username
    