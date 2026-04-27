import logging
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('accounts')

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # KİŞİSEL BİLGİLER
    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name='Telefon')

    # GÖSTERGE PANELİ AYARLARI
    monthly_revenue_goal = models.FloatField(default=100000.0, verbose_name='Aylık Ciro Hedefi (₺)')
    email_notifications = models.BooleanField(default=True, verbose_name='E-posta Bildirimleri')

    # ADMIN
    is_admin = models.BooleanField(default=False)

    # PRO ABONELİK & YENİLEME
    is_pro = models.BooleanField(default=False)
    auto_renew = models.BooleanField(default=True, verbose_name='Otomatik Yenileme') # YENİ ALAN
    subscription_end_date = models.DateTimeField(blank=True, null=True)
    
    # ÖDEME — İyzico token geçici olarak burada tutulur
    iyzico_token = models.CharField(max_length=255, blank=True, null=True)
    shopier_api_key = models.TextField(
        blank=True, 
        null=True,
        verbose_name='Shopier API Anahtarı',
        help_text='Shopier API erişimi için kullanılan uzun erişim anahtarı.'
    )

    class Meta:
        verbose_name = 'Profil'
        verbose_name_plural = 'Profiller'

    def __str__(self):
        return f'{self.user.username} Profili'

    def check_subscription(self) -> bool:
        """
        PRO aboneliğin geçerliliğini kontrol eder.
        Süre dolduysa is_pro'yu kapatır ve kaydeder.
        """
        if not self.is_pro:
            return False
        
        if self.subscription_end_date and timezone.now() > self.subscription_end_date:
            self.is_pro = False
            self.auto_renew = False # Süre bittiyse yenilemeyi de kapat
            self.save(update_fields=['is_pro', 'auto_renew'])
            logger.info(f'PRO aboneliği sona erdi: {self.user.username}')
            return False
        return True

    @property
    def get_loyalty_discount(self) -> int:
        """
        Kullanıcının kayıt süresine göre (Sadakat) indirim oranını döndürür.
        3 Ay: %20, 6 Ay: %30, 12 Ay: %50
        """
        delta = timezone.now() - self.user.date_joined
        months = delta.days // 30 
        
        if months >= 12: return 50
        if months >= 6: return 30
        if months >= 3: return 20
        return 0 # 3 aydan az ise indirim yok (veya varsayılanı HTML'de verebilirsin)

    @property
    def subscription_days_remaining(self) -> int:
        """Aboneliğin kaç gün kaldığını döner."""
        if not self.is_pro or not self.subscription_end_date:
            return 0
        delta = self.subscription_end_date - timezone.now()
        return max(0, delta.days)