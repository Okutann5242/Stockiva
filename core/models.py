import logging
from django.db import models
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

from django.db import models
from django.contrib.auth.models import User

logger = logging.getLogger('core')


def send_stock_alert(product):
    """
    Ürün stoğu kritik seviyeye (<=5) düştüğünde e-posta uyarısı gönderir.
    Kullanıcı profili yoksa veya bildirim kapalıysa sessizce atlar.
    """
    try:
        profile = product.user.profile
        if not getattr(profile, 'email_notifications', False):
            return
        if product.stock_quantity <= 5:
            send_mail(
                subject='⚠️ Kritik Stok Uyarısı — Stockiva',
                message=(
                    f'Merhaba {product.user.first_name or product.user.username},\n\n'
                    f'"{product.name}" ürününüzün stoğu kritik seviyeye düştü.\n'
                    f'Kalan stok: {product.stock_quantity} adet\n\n'
                    f'Stok yönetiminizi güncellemek için Stockiva paneline giriş yapın.\n\n'
                    f'— Stockiva Ekibi'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[product.user.email],
                fail_silently=True,
            )
            logger.info(f'Stok uyarısı gönderildi: {product.name} (kullanıcı: {product.user.username})')
    except Exception as e:
        # Hata durumunda sistemi durdurma ama logla
        logger.error(f'send_stock_alert hatası — ürün_id={product.id}: {e}')


class Product(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255, verbose_name='Ürün Adı')

    # FİYAT BİLGİLERİ
    # Not: null=True/blank=True CSV yüklemelerinde boş değerlere izin verir.
    cost_price = models.FloatField(default=0.0, null=True, blank=True, verbose_name='Maliyet Fiyatı (₺)')
    selling_price = models.FloatField(default=0.0, null=True, blank=True, verbose_name='Satış Fiyatı (₺)')
    stock_quantity = models.IntegerField(default=0, null=True, blank=True, verbose_name='Stok Miktarı')

    # GİDER ORANLARI
    # DÜZELTME: Önceki default'lar (komisyon %15, kargo 40₺) küçük fiyatlı
    # ürünlerde kârı otomatik olarak eksilere çekiyordu. Artık 0 başlıyor,
    # kullanıcı kendi ürününe göre girer.
    commission_rate = models.FloatField(default=0.0, verbose_name='Pazar Yeri Komisyon Oranı (%)')
    shipping_cost = models.FloatField(default=0.0, verbose_name='Kargo Ücreti (₺)')

    category = models.CharField(max_length=100, default='Genel', verbose_name='Ürün Kategorisi')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ürün'
        verbose_name_plural = 'Ürünler'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # HESAPLAMA METODLARI — View'larda tekrar eden formüller buraya taşındı
    # ------------------------------------------------------------------

    def get_commission_amount(self):
    # Alanların None gelme ihtimaline karşı tam koruma
        price = self.selling_price or 0.0
        rate = self.commission_rate or 0.0
        return price * (rate / 100)

    def get_net_profit_per_unit(self):
        """Bir birim satıştan elde edilen net kâr."""
        return (
            (self.selling_price or 0)
            - (self.cost_price or 0)
            - self.get_commission_amount()
            - (self.shipping_cost or 0)
        )

    def get_profit_margin(self):
        """Kâr marjı (%). Satış fiyatı 0 ise 0 döner."""
        if not self.selling_price:
            return 0.0
        return (self.get_net_profit_per_unit() / self.selling_price) * 100

    def get_stock_value(self):
        """Mevcut stokun maliyet değeri."""
        return (self.stock_quantity or 0) * (self.cost_price or 0)


class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    quantity = models.FloatField(default=1.0, verbose_name='Adet')
    price = models.FloatField(default=0.0, null=True, blank=True, verbose_name='Satış Fiyatı (₺)')
    date = models.DateField(verbose_name='Satış Tarihi')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Satış'
        verbose_name_plural = 'Satışlar'
        ordering = ['-date']

    def __str__(self):
        product_name = self.product.name if self.product_id else 'Silinmiş Ürün'
        return f'{product_name} — {self.date}'

    def get_revenue(self):
        return (self.quantity or 0) * (self.price or 0)

    def get_cost(self):
        return (self.product.cost_price or 0) * (self.quantity or 0)

    def get_profit(self):
        revenue = self.get_revenue()
        cost = self.get_cost()
        commission = (self.price or 0) * ((self.product.commission_rate or 0) / 100) * (self.quantity or 0)
        shipping = (self.product.shipping_cost or 0) * (self.quantity or 0)
        return revenue - cost - commission - shipping
    



class SupportTicket(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=100, null=True, blank=True) # null=True ekledik
    email = models.EmailField(null=True, blank=True) # null=True ekledik
    subject = models.CharField(max_length=200, null=True, blank=True) # null=True ekledik
    message = models.TextField()
    ai_response = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.subject} - {self.full_name}"
